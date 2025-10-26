#!/usr/bin/env python3
# Copyright (C) 2024 Gaspard Douté
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Automatisation complète du flash du BMCU-C.

Ce script orchestre de bout en bout la procédure de mise à jour du BMCU
en s'appuyant sur les utilitaires disponibles dans ce dépôt. Chaque étape
est abondamment journalisée et interrompue dès qu'une erreur est
rencontrée afin d'éviter tout état incohérent sur le matériel.

Le flux d'exécution suit les étapes suivantes :

0. Initialisation et nettoyage.
1. Pré-vérification (lecture de la version courante du firmware).
2. Préparation du flash (mode maintenance + transfert du binaire).
3. Exécution du flash.
4. Post-vérification et validation.

Le script produit un journal détaillé dans un dossier horodaté et un
rapport d'échec en cas de problème critique.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import importlib.util
import logging
from logging.handlers import RotatingFileHandler
import shlex
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Optional


# ---------------------------------------------------------------------------
# Bannière de démarrage
# ---------------------------------------------------------------------------


def display_logo() -> None:
    """Affiche le logo ASCII si disponible."""

    logo_path = Path(__file__).resolve().parents[1] / "logo" / "banner.txt"
    try:
        logo = logo_path.read_text(encoding="utf-8").rstrip()
    except FileNotFoundError:
        return

    if logo:
        print(logo)
        print()


# ---------------------------------------------------------------------------
# Exceptions personnalisées
# ---------------------------------------------------------------------------


class StepError(Exception):
    """Erreur contrôlée pour une étape spécifique."""

    def __init__(self, step_label: str, message: str, *, cause: Optional[Exception] = None):
        super().__init__(message)
        self.step_label = step_label
        self.message = message
        self.cause = cause


class CommandExecutionError(Exception):
    """Erreur lors de l'exécution d'une commande shell."""

    def __init__(self, command: str, result: subprocess.CompletedProcess[str]):
        super().__init__(f"La commande '{command}' a échoué avec le code {result.returncode}")
        self.command = command
        self.result = result


# ---------------------------------------------------------------------------
# Structures de données
# ---------------------------------------------------------------------------


@dataclass
class ExecutionContext:
    """Conteneur pour l'état partagé entre les étapes."""

    log_dir: Path
    log_file: Path
    bmc_host: str
    bmc_user: str
    bmc_password: str
    ssh_port: int
    remote_firmware_path: str
    initial_version: Optional[str] = None
    final_version: Optional[str] = None
    dry_run: bool = False
    firmware_local_path: Optional[Path] = None
    firmware_size: Optional[int] = None
    firmware_sha256: Optional[str] = None


# ---------------------------------------------------------------------------
# Outils de logging et d'exécution
# ---------------------------------------------------------------------------


LOG_FORMAT = "[%(asctime)s] [%(levelname)s] - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(log_file: Path) -> None:
    """Configure les handlers de logging pour le fichier et la console."""

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Handler fichier : niveau DEBUG pour conserver tous les détails avec rotation (5 Mo, 4 sauvegardes).
    file_handler = RotatingFileHandler(
        log_file,
        mode="a",
        maxBytes=5 * 1024 * 1024,
        backupCount=4,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

    # Handler console : limité aux messages de progression.
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def flush_logs() -> None:
    """Force le vidage des buffers de logging."""

    for handler in logging.getLogger().handlers:
        handler.flush()


def format_command(command: Iterable[str] | str) -> str:
    """Retourne une représentation sûre d'une commande shell."""

    if isinstance(command, str):
        return command
    return " ".join(shlex.quote(part) for part in command)


def run_command(command: Iterable[str] | str, *, timeout: Optional[int] = None) -> subprocess.CompletedProcess[str]:
    """Exécute une commande shell et journalise les sorties."""

    display_cmd = format_command(command)
    logging.debug("Exécution de la commande : %s", display_cmd)

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )

    logging.debug("Commande terminée avec le code %s", completed.returncode)

    if completed.stdout:
        logging.debug("--- STDOUT ---\n%s", completed.stdout.rstrip())
    if completed.stderr:
        logging.debug("--- STDERR ---\n%s", completed.stderr.rstrip())

    if completed.returncode != 0:
        raise CommandExecutionError(display_cmd, completed)

    return completed


def execute_step(step_number: int, step_name: str, func, *args, **kwargs):
    """Exécute une étape avec journalisation et gestion d'erreur centralisée."""

    step_label = f"Étape {step_number} : {step_name}"
    logging.info("%s... EN COURS", step_label)
    try:
        result = func(*args, **kwargs)
    except StepError:
        logging.error("%s... ÉCHEC", step_label)
        raise
    except CommandExecutionError as err:
        logging.error("%s... ÉCHEC", step_label)
        raise StepError(step_label, str(err)) from err
    except Exception as err:  # pragma: no cover - sécurité supplémentaire
        logging.exception("%s... ERREUR INATTENDUE", step_label)
        raise StepError(step_label, str(err)) from err
    else:
        logging.info("%s... OK", step_label)
        return result


# ---------------------------------------------------------------------------
# Vérifications des dépendances
# ---------------------------------------------------------------------------


def ensure_command_available(step_label: str, command: str) -> None:
    """Vérifie la présence d'une commande système."""

    if shutil.which(command) is None:
        raise StepError(step_label, f"La dépendance système '{command}' est introuvable dans le PATH")
    logging.debug("Dépendance '%s' détectée", command)


def ensure_module_available(step_label: str, module: str) -> None:
    """Vérifie la présence d'un module Python."""

    if importlib.util.find_spec(module) is None:
        raise StepError(step_label, f"Le module Python '{module}' est introuvable")
    logging.debug("Module Python '%s' disponible", module)


# ---------------------------------------------------------------------------
# Fonctions utilitaires spécifiques BMC
# ---------------------------------------------------------------------------


def build_ipmitool_command(host: str, user: str, password: str, *arguments: str) -> list[str]:
    """Construit la commande ipmitool standardisée."""

    return [
        "ipmitool",
        "-I",
        "lanplus",
        "-H",
        host,
        "-U",
        user,
        "-P",
        password,
        *arguments,
    ]


def read_bmc_firmware_version(context: ExecutionContext) -> str:
    """Récupère la version du firmware en interrogeant le BMC via IPMI."""

    try:
        result = run_command(build_ipmitool_command(context.bmc_host, context.bmc_user, context.bmc_password, "mc", "info"))
    except CommandExecutionError as err:
        raise StepError("Lecture version firmware", str(err)) from err

    version = None
    for line in result.stdout.splitlines():
        if "Firmware Revision" in line:
            _, value = line.split(":", maxsplit=1)
            version = value.strip()
            break

    if not version:
        raise StepError("Lecture version firmware", "Impossible d'extraire la version du firmware depuis ipmitool")

    logging.info("Version du firmware détectée : %s", version)
    return version


def run_remote_command(context: ExecutionContext, remote_command: str, *, timeout: Optional[int] = None) -> subprocess.CompletedProcess[str]:
    """Exécute une commande distante via SSH en utilisant sshpass."""

    if context.dry_run:
        logging.info("Mode test à blanc : la commande distante suivante est simulée : %s", remote_command)
        return subprocess.CompletedProcess(
            args=["ssh", "(dry-run)", remote_command],
            returncode=0,
            stdout="(dry-run) Commande non exécutée.",
            stderr="",
        )

    ssh_command = [
        "sshpass",
        "-p",
        context.bmc_password,
        "ssh",
        "-p",
        str(context.ssh_port),
        "-o",
        "StrictHostKeyChecking=no",
        f"{context.bmc_user}@{context.bmc_host}",
        f"set -euo pipefail; {remote_command}",
    ]

    return run_command(ssh_command, timeout=timeout)


def compute_firmware_metadata(firmware_path: Path) -> tuple[int, str]:
    """Calcule la taille et le hash SHA-256 d'un firmware."""

    try:
        size = firmware_path.stat().st_size
    except OSError as err:
        raise StepError("Préparation du flash", f"Impossible de lire le firmware '{firmware_path}': {err}") from err

    hasher = sha256()
    try:
        with firmware_path.open("rb") as firmware_file:
            for chunk in iter(lambda: firmware_file.read(65536), b""):
                hasher.update(chunk)
    except OSError as err:
        raise StepError("Préparation du flash", f"Impossible de calculer le hash du firmware : {err}") from err

    return size, hasher.hexdigest()


def copy_firmware(context: ExecutionContext, firmware_path: Path) -> None:
    """Copie du firmware vers l'équipement distant via SCP."""

    if not firmware_path.is_file():
        raise StepError("Préparation du flash", f"Le fichier firmware '{firmware_path}' est introuvable")

    if context.dry_run:
        logging.info(
            "Mode test à blanc : la copie du firmware %s est simulée (destination %s)",
            firmware_path,
            context.remote_firmware_path,
        )
        return

    scp_command = [
        "sshpass",
        "-p",
        context.bmc_password,
        "scp",
        "-P",
        str(context.ssh_port),
        str(firmware_path),
        f"{context.bmc_user}@{context.bmc_host}:{context.remote_firmware_path}",
    ]

    run_command(scp_command)


def wait_for_host(host: str, *, timeout: int, interval: int = 5) -> None:
    """Attend qu'un hôte réponde au ping."""

    logging.debug("Attente du retour en ligne de %s (timeout=%ss)...", host, timeout)
    deadline = _dt.datetime.now() + _dt.timedelta(seconds=timeout)
    while _dt.datetime.now() < deadline:
        try:
            run_command(["ping", "-c", "1", "-W", "1", host])
        except CommandExecutionError:
            logging.debug("Ping en échec, nouvel essai dans %ss", interval)
            _sleep(interval)
            continue
        else:
            logging.info("L'hôte %s répond au ping", host)
            return

    raise StepError("Post-vérification", f"L'hôte {host} ne répond pas au ping après {timeout} secondes")


def _sleep(seconds: int) -> None:
    """Wrapper de sommeil testable (facilité de mock)."""

    import time

    time.sleep(seconds)


# ---------------------------------------------------------------------------
# Étapes du processus
# ---------------------------------------------------------------------------


def step_initialisation(args: argparse.Namespace, context: ExecutionContext) -> None:
    """Vérifie les dépendances et prépare l'environnement de logging."""

    step_label = "Étape 0 : Initialisation et nettoyage"
    logging.info("%s - vérification des dépendances", step_label)

    for command in args.required_commands:
        ensure_command_available(step_label, command)

    for module in args.required_modules:
        ensure_module_available(step_label, module)

    logging.debug("Répertoire des logs : %s", context.log_dir)
    logging.debug("Fichier de logs : %s", context.log_file)


def step_precheck(context: ExecutionContext) -> None:
    """Pré-vérifie l'état du BMC en lisant la version du firmware."""

    if context.dry_run:
        context.initial_version = "(dry-run)"
        logging.info("Mode test à blanc : la lecture de la version initiale est ignorée")
        return

    context.initial_version = read_bmc_firmware_version(context)
    logging.info("Version initiale enregistrée : %s", context.initial_version)


def step_preparation(args: argparse.Namespace, context: ExecutionContext) -> None:
    """Met le BMC en mode maintenance et transfère le firmware."""

    firmware_path = Path(args.firmware_file).resolve()
    context.firmware_local_path = firmware_path

    size, fingerprint = compute_firmware_metadata(firmware_path)
    context.firmware_size = size
    context.firmware_sha256 = fingerprint

    logging.info("Firmware local : %s (taille : %s octets)", firmware_path, size)
    logging.info("Empreinte SHA-256 calculée : %s", fingerprint)

    if args.firmware_sha256:
        expected = args.firmware_sha256.strip().lower()
        if expected != fingerprint.lower():
            raise StepError(
                "Préparation du flash",
                "Le hash SHA-256 du firmware ne correspond pas à la valeur attendue",
            )
        logging.info("Empreinte SHA-256 attendue confirmée")

    if args.backup_command:
        logging.info("Exécution de la commande de sauvegarde avant le flash")
        logging.debug("Commande de sauvegarde : %s", args.backup_command)
        backup_result = run_remote_command(context, args.backup_command)
        if backup_result.stdout:
            logging.info("Sortie de la sauvegarde :\n%s", backup_result.stdout.rstrip())
        if backup_result.stderr:
            logging.info("Sortie d'erreur de la sauvegarde :\n%s", backup_result.stderr.rstrip())

    if args.pre_update_command:
        logging.debug("Commande de mise en maintenance : %s", args.pre_update_command)
        run_remote_command(context, args.pre_update_command)

    copy_firmware(context, firmware_path)
    logging.info(
        "Firmware transféré vers %s:%s",
        context.bmc_host,
        context.remote_firmware_path,
    )


def step_flash(args: argparse.Namespace, context: ExecutionContext) -> None:
    """Lance la commande de flash principale sur le BMC."""

    flash_cmd = args.flash_command.format(
        firmware=shlex.quote(context.remote_firmware_path),
        firmware_path=shlex.quote(context.remote_firmware_path),
    )

    logging.debug("Commande de flash finale : %s", flash_cmd)
    result = run_remote_command(context, flash_cmd, timeout=args.flash_timeout)

    # Journalisation explicite (au niveau INFO) pour garantir la présence dans le log.
    if result.stdout:
        logging.info("Sortie standard du flash :\n%s", result.stdout.rstrip())
    if result.stderr:
        logging.info("Sortie d'erreur du flash :\n%s", result.stderr.rstrip())


def step_post_verification(args: argparse.Namespace, context: ExecutionContext) -> None:
    """Attend le redémarrage du BMC et valide la version flashée."""

    if context.dry_run:
        context.final_version = "(dry-run)"
        if args.wait_for_reboot:
            logging.info("Mode test à blanc : l'attente de redémarrage est ignorée")
        logging.info("Mode test à blanc : aucune lecture de version finale n'est effectuée")
        if args.expected_final_version:
            logging.warning(
                "Impossible de vérifier la version cible '%s' en mode test à blanc",
                args.expected_final_version,
            )
        return

    if args.wait_for_reboot:
        logging.info("Attente du redémarrage du BMC (%ss maximum)", args.reboot_timeout)
        wait_for_host(context.bmc_host, timeout=args.reboot_timeout, interval=args.reboot_check_interval)

    context.final_version = read_bmc_firmware_version(context)
    logging.info("Version finale détectée : %s", context.final_version)

    if args.expected_final_version and context.final_version != args.expected_final_version:
        raise StepError(
            "Post-vérification",
            (
                "La version finale détectée (%s) ne correspond pas à la version attendue (%s)."
                % (context.final_version, args.expected_final_version)
            ),
        )

    if context.initial_version == context.final_version:
        message = (
            "La version du firmware est identique avant et après le flash (%s). "
            "Vérifiez que le nouveau firmware a bien été appliqué." % context.final_version
        )
        if not args.allow_same_version:
            raise StepError("Post-vérification", message)
        logging.warning(message)


# ---------------------------------------------------------------------------
# Gestion des échecs critiques
# ---------------------------------------------------------------------------


def handle_failure(context: ExecutionContext, failure: StepError) -> None:
    """Construit le rapport d'échec et l'affiche clairement."""

    flush_logs()

    logging.error("### ÉCHEC CRITIQUE ###")
    logging.error("%s - %s", failure.step_label, failure.message)
    flush_logs()
    print("### ÉCHEC CRITIQUE ###")

    failure_report = context.log_dir / "FAILURE_REPORT.txt"
    try:
        log_lines = context.log_file.read_text(encoding="utf-8").splitlines()
        tail = "\n".join(log_lines[-50:])
    except OSError as err:
        tail = f"Impossible de lire le journal : {err}"

    report_body = textwrap.dedent(
        f"""
        Étape en échec : {failure.step_label}
        Message d'erreur : {failure.message}

        Dernières lignes du journal :
        {tail}
        """
    ).strip()

    try:
        failure_report.write_text(report_body, encoding="utf-8")
    except OSError as err:
        logging.error("Impossible d'écrire le fichier FAILURE_REPORT.txt : %s", err)
    else:
        logging.error("Rapport d'échec enregistré dans %s", failure_report)


# ---------------------------------------------------------------------------
# Analyse des arguments
# ---------------------------------------------------------------------------


def parse_arguments(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Définit et analyse les arguments de la ligne de commande."""

    parser = argparse.ArgumentParser(
        description="Automatisation complète du flash BMCU vers Klipper",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--bmc-host", required=True, help="Adresse IP ou nom d'hôte du BMC")
    parser.add_argument("--bmc-user", default="root", help="Utilisateur SSH/IPMI du BMC")
    parser.add_argument("--bmc-password", required=True, help="Mot de passe SSH/IPMI du BMC")
    parser.add_argument("--firmware-file", required=True, help="Chemin local du firmware à transférer")
    parser.add_argument(
        "--remote-firmware-path",
        default="/tmp/klipper_firmware.bin",
        help="Chemin cible sur le BMC pour le fichier firmware",
    )
    parser.add_argument("--ssh-port", type=int, default=22, help="Port SSH du BMC")
    parser.add_argument(
        "--pre-update-command",
        default="",
        help=(
            "Commande distante à exécuter avant le transfert du firmware (mise en maintenance). "
            "Laisser vide pour ignorer."
        ),
    )
    parser.add_argument(
        "--flash-command",
        default="socflash -s {firmware}",
        help=(
            "Commande distante de flash. Utiliser {firmware} ou {firmware_path} comme placeholder pour le chemin sur le BMC."
        ),
    )
    parser.add_argument("--flash-timeout", type=int, default=1800, help="Timeout (en secondes) pour la commande de flash")
    parser.add_argument(
        "--wait-for-reboot",
        action="store_true",
        help="Attend le retour en ligne du BMC après le flash avant de poursuivre",
    )
    parser.add_argument(
        "--reboot-timeout",
        type=int,
        default=600,
        help="Temps maximum d'attente du redémarrage lorsque --wait-for-reboot est activé",
    )
    parser.add_argument(
        "--reboot-check-interval",
        type=int,
        default=10,
        help="Intervalle (secondes) entre deux vérifications de ping",
    )
    parser.add_argument(
        "--allow-same-version",
        action="store_true",
        help="Ne pas considérer comme une erreur le cas où la version reste inchangée",
    )
    parser.add_argument(
        "--expected-final-version",
        "--target-version",
        dest="expected_final_version",
        default="",
        help="Version de firmware attendue après flash. Laisse vide pour désactiver la vérification.",
    )
    parser.add_argument(
        "--firmware-sha256",
        "--firmware-checksum",
        dest="firmware_sha256",
        default="",
        help="Empreinte SHA-256 attendue du firmware local pour vérifier l'intégrité.",
    )
    parser.add_argument(
        "--backup-command",
        default="",
        help="Commande distante pour réaliser une sauvegarde avant le flash.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Active le mode test à blanc : aucune opération distante n'est exécutée",
    )
    parser.add_argument(
        "--log-root",
        default="logs",
        help="Répertoire parent pour les journaux horodatés",
    )
    parser.add_argument(
        "--required-commands",
        nargs="*",
        default=["ipmitool", "sshpass", "scp", "ping"],
        help="Liste des commandes système dont la présence est obligatoire",
    )
    parser.add_argument(
        "--required-modules",
        nargs="*",
        default=[],
        help="Modules Python requis (ex : python_ipmi)",
    )

    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    display_logo()

    args = parse_arguments(argv)

    timestamp = _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_root = Path(args.log_root)
    log_dir = log_root / f"flash_test_{timestamp}"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "debug.log"

    configure_logging(log_file)

    logging.info("Initialisation du processus d'automatisation du flash")
    if args.dry_run:
        logging.warning("Mode test à blanc activé : aucune action distante ne sera exécutée")

    context = ExecutionContext(
        log_dir=log_dir,
        log_file=log_file,
        bmc_host=args.bmc_host,
        bmc_user=args.bmc_user,
        bmc_password=args.bmc_password,
        ssh_port=args.ssh_port,
        remote_firmware_path=args.remote_firmware_path,
        dry_run=args.dry_run,
    )

    try:
        execute_step(0, "Initialisation et nettoyage", step_initialisation, args, context)
        execute_step(1, "Pré-vérification", step_precheck, context)
        execute_step(2, "Préparation du flash", step_preparation, args, context)
        execute_step(3, "Exécution du flash", step_flash, args, context)
        execute_step(4, "Post-vérification", step_post_verification, args, context)
    except StepError as failure:
        handle_failure(context, failure)
        return 1

    logging.info("Flash du BMC terminé avec succès")
    logging.info("Ancienne version : %s", context.initial_version)
    logging.info("Nouvelle version : %s", context.final_version)
    return 0


if __name__ == "__main__":  # pragma: no cover - point d'entrée CLI
    sys.exit(main())


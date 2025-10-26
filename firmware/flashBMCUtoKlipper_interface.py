#!/usr/bin/env python3
"""Interface interactive pour faciliter l'usage du script d'automatisation.

Ce module fournit une CLI conviviale autour de
``flashBMCUtoKlipper_automation.py``. L'objectif est de guider
l'utilisateur pas-à-pas, de rappeler les prérequis critiques avant de
lancer le flash et de générer automatiquement un *prompt* d'assistance en
cas d'échec. Ce *prompt* peut être copié/collé dans une discussion avec un
assistant afin d'accélérer le diagnostic.

Fonctionnalités principales :

* Présentation de la procédure et de l'objectif du script.
* Checklist interactive des vérifications à réaliser avant d'aller plus
  loin.
* Saisie guidée de tous les paramètres requis par le script
  d'automatisation.
* Confirmation récapitulative avant exécution, avec possibilité d'annuler.
* Lancement du script principal tout en laissant passer sa sortie
  standard/erreur pour conserver les journaux détaillés.
* Analyse du résultat : en cas d'échec, génération automatique d'un
  *prompt* contenant les informations nécessaires pour demander de
  l'assistance (commande exécutée, contexte, extrait du journal).

Ce fichier n'introduit aucune dépendance externe : seule la bibliothèque
standard est utilisée afin de pouvoir être exécuté sur tout environnement
compatible Python 3.
"""

from __future__ import annotations

import getpass
import shlex
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


# ---------------------------------------------------------------------------
# Structures de données
# ---------------------------------------------------------------------------


@dataclass
class UserChoices:
    """Paramètres collectés auprès de l'utilisateur."""

    bmc_host: str
    bmc_user: str
    bmc_password: str
    firmware_file: Path
    remote_firmware_path: str
    ssh_port: int
    pre_update_command: str
    flash_command: str
    flash_timeout: int
    wait_for_reboot: bool
    reboot_timeout: int
    reboot_check_interval: int
    allow_same_version: bool
    expected_final_version: str
    firmware_sha256: str
    dry_run: bool
    log_root: Path


CHECKLIST_ITEMS = [
    "Le BMCU-C est alimenté et connecté au réseau (ping possible).",
    "Vous disposez des identifiants SSH/IPMI (utilisateur et mot de passe).",
    "Le firmware Klipper cible a été généré et son chemin local est connu.",
    "Toutes les imprimantes/enclos dépendant du BMCU-C sont à l'arrêt.",
    "Vous avez sauvegardé la configuration actuelle du BMCU-C si nécessaire.",
]


INTRO_TEXT = """
Bienvenue dans l'assistant de flash du BMCU-C vers Klipper.

Ce guide interactif va :
  • rappeler les points de contrôle indispensables ;
  • collecter les paramètres nécessaires au script
    `flashBMCUtoKlipper_automation.py` ;
  • lancer le processus et analyser le résultat ;
  • en cas d'échec, générer un prompt prêt à l'emploi pour demander
    de l'aide.

⚠️ Cette procédure peut rendre le module inopérant si elle est interrompue
ou mal paramétrée. Assurez-vous de comprendre chaque étape avant de
poursuivre.
"""


def print_block(message: str) -> None:
    """Affiche un bloc de texte avec indentation homogène."""

    formatted = textwrap.dedent(message).strip()
    print()
    print(formatted)
    print()


def ask_yes_no(question: str, *, default: bool | None = None) -> bool:
    """Demande une confirmation oui/non à l'utilisateur."""

    if default is True:
        suffix = " [O/n] "
    elif default is False:
        suffix = " [o/N] "
    else:
        suffix = " [o/n] "

    while True:
        answer = input(question + suffix).strip().lower()
        if not answer and default is not None:
            return default
        if answer in {"o", "oui", "y", "yes"}:
            return True
        if answer in {"n", "non", "no"}:
            return False
        print("Réponse invalide. Merci d'indiquer 'o' pour oui ou 'n' pour non.")


def ask_text(question: str, *, default: str | None = None, required: bool = True) -> str:
    """Récupère une chaîne de caractères en respectant un défaut éventuel."""

    while True:
        prompt = f"{question}"
        if default:
            prompt += f" [{default}]"
        prompt += " : "

        value = input(prompt).strip()
        if not value:
            if default is not None:
                return default
            if not required:
                return ""
            print("Ce champ est obligatoire.")
            continue
        return value


def ask_int(question: str, *, default: int) -> int:
    """Demande un entier avec validation."""

    while True:
        answer = ask_text(question, default=str(default), required=True)
        try:
            return int(answer)
        except ValueError:
            print("Merci de saisir une valeur numérique valide.")


def ask_password(question: str) -> str:
    """Demande un mot de passe sans l'afficher."""

    while True:
        password = getpass.getpass(prompt=f"{question} : ")
        if password:
            return password
        print("Le mot de passe ne peut pas être vide.")


def ensure_firmware_path(path_str: str) -> Path:
    """Valide l'existence du fichier firmware fourni."""

    firmware_path = Path(path_str).expanduser().resolve()
    if not firmware_path.is_file():
        raise FileNotFoundError(f"Le fichier '{firmware_path}' est introuvable.")
    return firmware_path


def gather_user_choices() -> UserChoices:
    """Collecte toutes les informations nécessaires."""

    print_block(INTRO_TEXT)

    print("Checklist des prérequis :")
    for index, item in enumerate(CHECKLIST_ITEMS, start=1):
        print(f"  {index}. {item}")
    print()

    if not ask_yes_no("Avez-vous validé chacun des points ci-dessus ?", default=True):
        print("Veuillez préparer l'environnement puis relancer l'assistant.")
        sys.exit(0)

    bmc_host = ask_text("Adresse IP ou nom d'hôte du BMC", required=True)
    bmc_user = ask_text("Utilisateur SSH/IPMI", default="root")
    bmc_password = ask_password("Mot de passe SSH/IPMI")

    while True:
        firmware_input = ask_text("Chemin local du firmware Klipper", required=True)
        try:
            firmware_file = ensure_firmware_path(firmware_input)
        except FileNotFoundError as err:
            print(err)
            continue
        else:
            break

    remote_firmware_path = ask_text(
        "Chemin de destination sur le BMC",
        default="/tmp/klipper_firmware.bin",
    )
    ssh_port = ask_int("Port SSH", default=22)
    pre_update_command = ask_text(
        "Commande distante de mise en maintenance (laisser vide pour ignorer)",
        default="",
        required=False,
    )
    flash_command = ask_text(
        "Commande de flash (utiliser {firmware} comme placeholder)",
        default="socflash -s {firmware}",
    )
    flash_timeout = ask_int("Timeout de la commande de flash (secondes)", default=1800)
    wait_for_reboot = ask_yes_no("Attendre automatiquement le redémarrage du BMC ?", default=True)
    if wait_for_reboot:
        reboot_timeout = ask_int("Timeout de redémarrage (secondes)", default=600)
        reboot_check_interval = ask_int("Intervalle entre deux vérifications (secondes)", default=10)
    else:
        reboot_timeout = 600
        reboot_check_interval = 10

    allow_same_version = ask_yes_no(
        "Accepter que la version finale soit identique à l'initiale ?",
        default=False,
    )
    expected_final_version = ask_text(
        "Version finale attendue (laisser vide pour ignorer)",
        default="",
        required=False,
    )
    firmware_sha256 = ask_text(
        "Empreinte SHA-256 attendue (laisser vide pour ignorer)",
        default="",
        required=False,
    )
    dry_run = ask_yes_no("Activer le mode test à blanc (aucune action distante) ?", default=False)
    log_root_input = ask_text("Répertoire où stocker les journaux", default="logs")
    log_root = Path(log_root_input).expanduser().resolve()

    return UserChoices(
        bmc_host=bmc_host,
        bmc_user=bmc_user,
        bmc_password=bmc_password,
        firmware_file=firmware_file,
        remote_firmware_path=remote_firmware_path,
        ssh_port=ssh_port,
        pre_update_command=pre_update_command,
        flash_command=flash_command,
        flash_timeout=flash_timeout,
        wait_for_reboot=wait_for_reboot,
        reboot_timeout=reboot_timeout,
        reboot_check_interval=reboot_check_interval,
        allow_same_version=allow_same_version,
        expected_final_version=expected_final_version,
        firmware_sha256=firmware_sha256,
        dry_run=dry_run,
        log_root=log_root,
    )


def summarize_choices(choices: UserChoices) -> None:
    """Affiche un résumé des paramètres retenus."""

    summary = f"""
    Récapitulatif de la configuration sélectionnée :

      • BMC            : {choices.bmc_user}@{choices.bmc_host}:{choices.ssh_port}
      • Firmware local : {choices.firmware_file}
      • Chemin distant : {choices.remote_firmware_path}
      • Commande flash : {choices.flash_command}
      • Timeout flash  : {choices.flash_timeout} s
      • Attendre reboot: {'oui' if choices.wait_for_reboot else 'non'}
      • Autoriser même version : {'oui' if choices.allow_same_version else 'non'}
      • Version attendue       : {choices.expected_final_version or 'non définie'}
      • Empreinte SHA-256      : {choices.firmware_sha256 or 'non vérifiée'}
      • Mode test à blanc      : {'oui' if choices.dry_run else 'non'}
      • Répertoire de logs     : {choices.log_root}
    """

    print_block(summary)


def build_command(choices: UserChoices) -> list[str]:
    """Construit la commande d'invocation du script d'automatisation."""

    script_path = Path(__file__).resolve().with_name("flashBMCUtoKlipper_automation.py")
    command: list[str] = [
        sys.executable,
        str(script_path),
        "--bmc-host",
        choices.bmc_host,
        "--bmc-user",
        choices.bmc_user,
        "--bmc-password",
        choices.bmc_password,
        "--firmware-file",
        str(choices.firmware_file),
        "--remote-firmware-path",
        choices.remote_firmware_path,
        "--ssh-port",
        str(choices.ssh_port),
        "--flash-command",
        choices.flash_command,
        "--flash-timeout",
        str(choices.flash_timeout),
        "--log-root",
        str(choices.log_root),
    ]

    if choices.pre_update_command:
        command.extend(["--pre-update-command", choices.pre_update_command])
    if choices.wait_for_reboot:
        command.append("--wait-for-reboot")
        command.extend(["--reboot-timeout", str(choices.reboot_timeout)])
        command.extend(["--reboot-check-interval", str(choices.reboot_check_interval)])
    if choices.allow_same_version:
        command.append("--allow-same-version")
    if choices.expected_final_version:
        command.extend(["--expected-final-version", choices.expected_final_version])
    if choices.firmware_sha256:
        command.extend(["--firmware-sha256", choices.firmware_sha256])
    if choices.dry_run:
        command.append("--dry-run")

    return command


def run_automation(command: list[str]) -> subprocess.CompletedProcess[None]:
    """Lance le script d'automatisation et retourne le résultat."""

    print("Lancement du processus d'automatisation...\n")
    print("Commande exécutée :")
    print("  " + format_command(command))
    print()

    completed = subprocess.run(command, check=False)
    return completed


def format_command(command: Iterable[str]) -> str:
    """Formate une commande sous forme de chaîne safe."""

    return " ".join(shlex.quote(part) for part in command)


def find_latest_log_dir(log_root: Path) -> Path | None:
    """Retourne le dernier dossier de log généré dans le répertoire cible."""

    if not log_root.exists():
        return None

    candidates = [
        entry for entry in log_root.iterdir() if entry.is_dir()
    ]
    if not candidates:
        return None

    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def extract_log_tail(log_dir: Path, *, limit: int = 40) -> str:
    """Lit les dernières lignes du fichier de log principal."""

    log_file = log_dir / "debug.log"
    if not log_file.exists():
        return "(journal introuvable)"

    try:
        lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as err:
        return f"Impossible de lire le fichier de log : {err}"

    tail = lines[-limit:]
    return "\n".join(tail)


def generate_assistance_prompt(
    choices: UserChoices,
    command: list[str],
    log_dir: Path | None,
    exit_code: int,
) -> str:
    """Construit un prompt d'assistance à partir du contexte."""

    log_tail = ""
    log_path_display = "(indisponible)"
    if log_dir is not None:
        log_tail = extract_log_tail(log_dir)
        log_path_display = str(log_dir / "debug.log")

    timestamp = datetime.now().isoformat(timespec="seconds")
    context = textwrap.dedent(
        f"""
        J'ai exécuté le script d'automatisation du flash BMCU-C via l'interface
        interactive le {timestamp}. Voici le contexte :

        - Commande : {format_command(command)}
        - Hôte BMC : {choices.bmc_host}
        - Utilisateur : {choices.bmc_user}
        - Chemin firmware local : {choices.firmware_file}
        - Chemin distant : {choices.remote_firmware_path}
        - Mode test à blanc : {'oui' if choices.dry_run else 'non'}
        - Code de sortie : {exit_code}
        - Journal détaillé : {log_path_display}

        Dernières lignes du journal :
        ```
        {log_tail or '(aucune sortie disponible)'}
        ```

        Merci de m'aider à diagnostiquer et corriger le problème rencontré.
        """
    ).strip()

    return context


def main() -> int:
    try:
        choices = gather_user_choices()
    except KeyboardInterrupt:
        print("\nInterruption par l'utilisateur. Fin de l'assistant.")
        return 1

    summarize_choices(choices)

    if not ask_yes_no("Confirmez-vous le lancement du flash ?", default=True):
        print("Opération annulée. Aucun flash n'a été lancé.")
        return 0

    choices.log_root.mkdir(parents=True, exist_ok=True)

    command = build_command(choices)
    result = run_automation(command)

    latest_log_dir = find_latest_log_dir(choices.log_root)

    if result.returncode == 0:
        print("\n✅ Flash terminé avec succès !")
        if latest_log_dir is not None:
            print(f"Journaux disponibles dans : {latest_log_dir}")
        return 0

    print("\n❌ Le script d'automatisation a signalé une erreur (code de sortie"
          f" {result.returncode}).")
    if latest_log_dir is not None:
        print(f"Consultez le journal : {latest_log_dir / 'debug.log'}")

    prompt = generate_assistance_prompt(choices, command, latest_log_dir, result.returncode)

    print("\n--- Prompt d'assistance suggéré ---")
    print(prompt)
    print("--- Fin du prompt ---\n")

    return result.returncode


if __name__ == "__main__":  # pragma: no cover - point d'entrée CLI
    sys.exit(main())


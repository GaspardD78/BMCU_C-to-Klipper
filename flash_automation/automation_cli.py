#!/usr/bin/env python3
"""Interface d'automatisation inspirée de KIAUH pour le BMCU-C.

Ce script propose un menu interactif permettant de chaîner les scripts
existants de ce dépôt (compilation, flash local ou distant, etc.).
Toutes les opérations sont journalisées dans ``logs/automation_cli.log``
avec rotation (5 Mo, 4 sauvegardes) afin de faciliter le diagnostic.
"""
from __future__ import annotations

import argparse
import getpass
import logging
from logging.handlers import RotatingFileHandler
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from stat import S_IMODE
from typing import Callable, Dict, Iterable, Optional

from stop_utils import (
    DEFAULT_EXTERNAL_LOG_ROOT,
    StopController,
    StopRequested,
    cleanup_repository,
)

FLASH_DIR = Path(__file__).resolve().parent
LOGS_DIR = (DEFAULT_EXTERNAL_LOG_ROOT / "automation_cli").resolve()
LOG_FILE = LOGS_DIR / "automation_cli.log"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


class AutomationError(RuntimeError):
    """Erreur générique pour les opérations d'automatisation."""


@dataclass(frozen=True)
class MenuAction:
    """Représente une action disponible dans le menu interactif."""

    key: str
    label: str
    handler: Callable[["AutomationContext"], None]


class AutomationContext:
    """État partagé entre les actions."""

    def __init__(self, *, dry_run: bool = False, stop_controller: StopController, log_dir: Path):
        self.dry_run = dry_run
        self.stop_controller = stop_controller
        self.log_dir = log_dir
        self.logger = logging.getLogger("automation")

    def run_command(
        self,
        command: Iterable[str],
        *,
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
    ) -> None:
        """Exécute une commande tout en la journalisant proprement."""

        cmd_list = list(command)
        printable = shlex.join(cmd_list)
        if description:
            self.logger.info("%s", description)
        self.logger.info("Commande: %s", printable)

        self.stop_controller.raise_if_requested()

        if self.dry_run:
            self.logger.warning("Mode --dry-run actif, la commande n'est pas exécutée")
            return

        process = subprocess.Popen(
            cmd_list,
            cwd=str(cwd) if cwd else None,
            env={**os.environ, **env} if env else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        self.stop_controller.register_process(process)

        try:
            assert process.stdout is not None  # pour mypy/pyright
            for line in process.stdout:
                cleaned = line.rstrip()
                if cleaned:
                    self.logger.info("[sortie] %s", cleaned)
                if self.stop_controller.stop_requested:
                    break

            return_code = process.wait()
        except KeyboardInterrupt:
            if not self.stop_controller.stop_requested:
                self.stop_controller.request_stop(reason="interruption clavier")
            raise StopRequested()
        finally:
            self.stop_controller.unregister_process(process)

        if self.stop_controller.stop_requested:
            raise StopRequested()

        if return_code != 0:
            raise AutomationError(f"La commande '{printable}' a échoué avec le code {return_code}")


# ---------------------------------------------------------------------------
# Initialisation du logging
# ---------------------------------------------------------------------------

def configure_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=4,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


# ---------------------------------------------------------------------------
# Actions disponibles
# ---------------------------------------------------------------------------

def ensure_permissions(context: AutomationContext) -> None:
    """Rend exécutables les scripts shell nécessaires."""

    context.stop_controller.raise_if_requested()
    context.logger.info("Vérification des permissions d'exécution")
    for script in ("build.sh", "flash_automation.sh"):
        target = FLASH_DIR / script
        if not target.exists():
            context.logger.warning("Le script %s est introuvable", target)
            continue
        current_mode = S_IMODE(target.stat().st_mode)
        desired_mode = current_mode | 0o111
        if current_mode != desired_mode:
            context.logger.debug("Application du mode exécutable sur %s", target)
            if context.dry_run:
                context.logger.warning("Mode --dry-run : chmod ignoré pour %s", target)
            else:
                target.chmod(desired_mode)
        else:
            context.logger.debug("Les permissions sont déjà correctes pour %s", target)
    context.logger.info("Permissions vérifiées")


def install_python_dependencies(context: AutomationContext) -> None:
    """Installe les dépendances Python listées dans requirements.txt."""

    context.stop_controller.raise_if_requested()
    requirements = FLASH_DIR / "requirements.txt"
    if not requirements.exists():
        raise AutomationError("Le fichier requirements.txt est introuvable")

    context.run_command(
        [sys.executable, "-m", "pip", "install", "-r", str(requirements)],
        cwd=FLASH_DIR,
        description="Installation des dépendances Python",
    )


def build_firmware(context: AutomationContext) -> None:
    """Lance la compilation du firmware via build.sh."""

    context.stop_controller.raise_if_requested()
    context.run_command(["./build.sh"], cwd=FLASH_DIR, description="Compilation du firmware Klipper")


def flash_interactive(context: AutomationContext) -> None:
    """Démarre le flash interactif (python3 flash.py)."""

    context.stop_controller.raise_if_requested()
    context.run_command([sys.executable, "flash.py"], cwd=FLASH_DIR, description="Flash interactif du BMCU-C")


def flash_cli(context: AutomationContext) -> None:
    """Flash minimal via le script shell."""

    context.stop_controller.raise_if_requested()
    context.run_command(["./flash_automation.sh"], cwd=FLASH_DIR, description="Flash minimal en ligne de commande")


def remote_orchestration(context: AutomationContext) -> None:
    """Collecte les paramètres et exécute l'automatisation distante."""

    context.stop_controller.raise_if_requested()
    firmware_path = input("Chemin local du firmware à transférer : ").strip()
    if not firmware_path:
        raise AutomationError("Un chemin de firmware est requis")
    context.stop_controller.raise_if_requested()
    bmc_host = input("Adresse IP / hôte du BMC : ").strip()
    if not bmc_host:
        raise AutomationError("L'hôte du BMC est requis")
    context.stop_controller.raise_if_requested()
    bmc_user = input("Utilisateur SSH/IPMI [root] : ").strip() or "root"
    bmc_password = getpass.getpass("Mot de passe SSH/IPMI : ")
    if not bmc_password:
        raise AutomationError("Le mot de passe est requis")
    context.stop_controller.raise_if_requested()
    remote_path = input("Chemin distant du firmware [/tmp/klipper_firmware.bin] : ").strip() or \
        "/tmp/klipper_firmware.bin"
    wait_reboot = input("Attendre le redémarrage après flash ? [o/N] : ").strip().lower().startswith("o")
    context.stop_controller.raise_if_requested()

    command = [
        sys.executable,
        "flashBMCtoKlipper_automation.py",
        "--bmc-host",
        bmc_host,
        "--bmc-password",
        bmc_password,
        "--firmware-file",
        firmware_path,
        "--remote-firmware-path",
        remote_path,
    ]
    if bmc_user:
        command.extend(["--bmc-user", bmc_user])
    if wait_reboot:
        command.append("--wait-for-reboot")

    context.run_command(command, cwd=FLASH_DIR, description="Automatisation distante du flash")


def clean_build_artifacts(context: AutomationContext) -> None:
    """Propose un nettoyage des artefacts de compilation."""

    context.stop_controller.raise_if_requested()
    cache_dir = FLASH_DIR / ".cache" / "klipper"
    if not cache_dir.exists():
        context.logger.warning("Le répertoire %s est introuvable, rien à nettoyer", cache_dir)
        return

    makefile = cache_dir / "Makefile"
    out_dir = cache_dir / "out"

    if makefile.exists():
        try:
            context.run_command(["make", "clean"], cwd=cache_dir, description="Nettoyage via make clean")
            return
        except AutomationError as exc:
            context.logger.error("make clean a échoué : %s", exc)
            if not out_dir.exists():
                return
            context.logger.info("Suppression manuelle du dossier out/")

    if out_dir.exists():
        if context.dry_run:
            context.logger.warning("Mode --dry-run : suppression de %s ignorée", out_dir)
        else:
            shutil.rmtree(out_dir)
        context.logger.info("Répertoire out/ supprimé")
    else:
        context.logger.info("Aucun artefact de compilation à supprimer")


def handle_manual_stop(context: AutomationContext) -> None:
    """Nettoyage global lors d'une interruption manuelle."""

    context.logger.warning("Arrêt manuel détecté. Nettoyage en cours...")
    logging.shutdown()
    print(f"Journaux disponibles dans : {context.log_dir}")
    cleanup_repository()


ACTIONS = (
    MenuAction("1", "Vérifier les permissions des scripts", ensure_permissions),
    MenuAction("2", "Installer les dépendances Python", install_python_dependencies),
    MenuAction("3", "Compiler le firmware", build_firmware),
    MenuAction("4", "Flash interactif (flash.py)", flash_interactive),
    MenuAction("5", "Flash minimal (flash_automation.sh)", flash_cli),
    MenuAction("6", "Automatisation distante", remote_orchestration),
    MenuAction("7", "Nettoyer les artefacts de compilation", clean_build_artifacts),
)
ACTION_MAP = {action.key: action for action in ACTIONS}


# ---------------------------------------------------------------------------
# Boucle principale
# ---------------------------------------------------------------------------

def display_banner() -> None:
    banner = (FLASH_DIR / "banner.txt")
    if banner.exists():
        try:
            content = banner.read_text(encoding="utf-8").rstrip()
        except OSError as exc:
            logging.getLogger("automation").warning("Impossible de lire la bannière : %s", exc)
        else:
            if content:
                print(content)
                print()


def interactive_menu(context: AutomationContext) -> None:
    display_banner()
    context.logger.info("Menu d'automatisation prêt. Sélectionnez une option.")

    while True:
        context.stop_controller.raise_if_requested()
        print("\n=== Gestionnaire BMCU-C ===")
        for action in ACTIONS:
            print(f" {action.key}. {action.label}")
        print(" X. Quitter")

        choice = input("Votre choix : ").strip().upper()
        if choice in {"X", "Q"}:
            context.logger.info("Fermeture du gestionnaire sur demande utilisateur")
            break
        action = ACTION_MAP.get(choice)
        if not action:
            context.logger.error("Choix '%s' invalide", choice)
            continue
        try:
            action.handler(context)
            context.logger.info("Action '%s' terminée", action.label)
        except AutomationError as error:
            context.logger.error("Action '%s' interrompue : %s", action.label, error)
        except StopRequested:
            raise
        except KeyboardInterrupt:
            context.logger.warning("Action '%s' interrompue par l'utilisateur", action.label)
            raise StopRequested()
        except Exception as unexpected:
            context.logger.exception("Erreur inattendue lors de l'action '%s'", action.label)


def parse_arguments(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automatisation du BMCU-C inspirée de KIAUH",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--action",
        choices=[action.key for action in ACTIONS],
        help="Exécute une action précise sans lancer le menu interactif",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche les commandes sans les exécuter",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    configure_logging()
    stop_controller = StopController(enable_input_listener=False)
    stop_controller.start()

    logger = logging.getLogger("automation")
    logger.info("Bouton stop : pressez Ctrl+C pour interrompre proprement.")
    logger.info("Les journaux sont enregistrés dans %s", LOG_FILE)

    args = parse_arguments(argv)
    context = AutomationContext(dry_run=args.dry_run, stop_controller=stop_controller, log_dir=LOGS_DIR)

    try:
        if args.action:
            action = ACTION_MAP[args.action]
            try:
                action.handler(context)
            except AutomationError as error:
                context.logger.error("Action '%s' interrompue : %s", action.label, error)
                return 1
            return 0

        interactive_menu(context)
        return 0
    except StopRequested:
        handle_manual_stop(context)
        return 130
    except KeyboardInterrupt:
        if not stop_controller.stop_requested:
            stop_controller.request_stop(reason="interruption clavier")
        handle_manual_stop(context)
        return 130


if __name__ == "__main__":
    sys.exit(main())

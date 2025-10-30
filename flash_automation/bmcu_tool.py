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

"""Interface interactive simplifiée pour la préparation et le flash."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import textwrap
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from pathlib import Path
import time

from .orchestrator import (
    detect_environment_defaults,
    EnvironmentDefaults,
    find_default_firmware,
    Orchestrator,
    BuildManagerError,
    FlashManagerError,
    PipInstallError,
)
from .flash_manager import FlashManager

# ---------------------------------------------------------------------------
# Constantes de couleurs
# ---------------------------------------------------------------------------

class Colors:
    """Codes de couleur ANSI pour la sortie terminal."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def colorize(text: str, color: str) -> str:
    """Enrobe un texte de codes de couleur ANSI."""
    if not sys.stdout.isatty():
        return text
    return f"{color}{text}{Colors.ENDC}"

# ---------------------------------------------------------------------------
# Bannière de démarrage
# ---------------------------------------------------------------------------

def display_logo() -> None:
    """Affiche le logo ASCII si disponible."""
    logo_path = Path(__file__).resolve().parent / "banner.txt"
    try:
        logo = logo_path.read_text(encoding="utf-8").rstrip()
    except FileNotFoundError:
        return
    if logo:
        print(logo)
        print()

# ---------------------------------------------------------------------------
# Gestion du profil utilisateur
# ---------------------------------------------------------------------------

CONFIG_FILE = Path(__file__).resolve().with_name("flash_profile.json")

@dataclass
class QuickProfile:
    """Préférences simplifiées mémorisées entre deux exécutions."""
    serial_device: str = ""

def load_profile() -> QuickProfile:
    """Charge le profil utilisateur si disponible."""
    if not CONFIG_FILE.exists():
        return QuickProfile()
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return QuickProfile()
    return QuickProfile(**{**asdict(QuickProfile()), **data})

def save_profile(profile: QuickProfile) -> None:
    """Sauvegarde le profil utilisateur."""
    try:
        CONFIG_FILE.write_text(json.dumps(asdict(profile), indent=2), encoding="utf-8")
    except OSError as err:
        print(colorize(f"Impossible d'enregistrer le profil : {err}", Colors.WARNING))

# ---------------------------------------------------------------------------
# Fonctions d'interaction utilisateur
# ---------------------------------------------------------------------------

def print_block(message: str) -> None:
    """Affiche un bloc de texte avec indentation homogène."""
    formatted = textwrap.dedent(message).strip()
    print()
    print(formatted)
    print()

def ask_yes_no(question: str, *, default: bool | None = None) -> bool:
    """Demande une confirmation oui/non à l'utilisateur."""
    suffix = " [O/n] " if default is True else " [o/N] " if default is False else " [o/n] "
    while True:
        prompt = colorize(question, Colors.OKCYAN) + suffix
        answer = input(prompt).strip().lower()
        if not answer and default is not None:
            return default
        if answer in {"o", "oui", "y", "yes"}:
            return True
        if answer in {"n", "non", "no"}:
            return False
        print(colorize("Réponse invalide.", Colors.WARNING))

def ask_text(question: str, *, default: str | None = None, required: bool = True) -> str:
    """Récupère une chaîne de caractères."""
    while True:
        prompt = colorize(f"{question}", Colors.OKCYAN)
        if default:
            prompt += f" [{default}]"
        prompt += " : "
        value = input(prompt).strip()
        if not value:
            if default is not None:
                return default
            if not required:
                return ""
            print(colorize("Ce champ est obligatoire.", Colors.WARNING))
            continue
        return value

def ask_menu(options: list[str], *, default_index: int = 0) -> int:
    """Propose un menu numéroté simple."""
    for index, option in enumerate(options, start=1):
        print(f"  {index}. {option}")
    prompt = colorize("Choix", Colors.OKCYAN) + f" [{default_index + 1}] : "
    while True:
        answer = input(prompt).strip()
        if not answer:
            return default_index
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return int(answer) - 1
        print(colorize("Merci d'entrer un numéro valide.", Colors.WARNING))

@contextmanager
def progress_step(title: str):
    """Affiche un indicateur simple de progression."""
    print(colorize(f"⏳ {title}...", Colors.OKBLUE))
    start = time.monotonic()
    try:
        yield
    except Exception:
        duration = time.monotonic() - start
        print(colorize(f"❌ {title} ({duration:.1f}s)", Colors.FAIL))
        raise
    else:
        duration = time.monotonic() - start
        print(colorize(f"✅ {title} ({duration:.1f}s)", Colors.OKGREEN))

# ---------------------------------------------------------------------------
# Logique de l'interface principale
# ---------------------------------------------------------------------------

def run_dependency_check(orchestrator: Orchestrator):
    """Vérifie et propose d'installer les dépendances."""
    print_block(colorize("Vérification des dépendances système...", Colors.HEADER))
    pm, all_deps, missing = orchestrator.get_system_dependencies()

    if not missing:
        print(colorize("Toutes les dépendances système semblent déjà installées.", Colors.OKGREEN))
    elif pm:
        print(colorize(f"Dépendances manquantes détectées pour '{pm}':", Colors.WARNING))
        for pkg in missing:
            print(f"  - {pkg}")

        install_commands = {
            "apt": f"sudo apt install -y {' '.join(missing)}",
            "dnf": f"sudo dnf install -y {' '.join(missing)}",
            "pacman": f"sudo pacman -S --noconfirm {' '.join(missing)}",
        }
        install_command = install_commands.get(pm)
        print(f"\nLa commande suivante peut être exécutée : {colorize(install_command, Colors.BOLD)}")

        if ask_yes_no("Voulez-vous lancer cette commande maintenant ?", default=True):
            with progress_step("Installation des dépendances"):
                if orchestrator.install_system_dependencies(pm, missing):
                    print(colorize("Installation terminée avec succès !", Colors.OKGREEN))
                else:
                    print(colorize("L'installation a échoué.", Colors.FAIL))
        else:
            print(colorize("Installation annulée.", Colors.WARNING))
    else:
        print(colorize("Votre système d'exploitation n'est pas auto-détecté.", Colors.WARNING))
        print("Veuillez installer manuellement les dépendances suivantes :")
        for pkg in sorted(all_deps):
            print(f"  - {pkg}")

    input("\nAppuyez sur Entrée pour continuer...")

def run_python_dependency_check(orchestrator: Orchestrator):
    """Vérifie et propose d'installer les dépendances Python."""
    print_block(colorize("Vérification des dépendances Python (pip)...", Colors.HEADER))
    _, missing = orchestrator.get_python_dependencies()

    if not missing:
        print(colorize("Toutes les dépendances Python semblent déjà installées.", Colors.OKGREEN))
    else:
        print(colorize("Dépendances Python manquantes détectées :", Colors.WARNING))
        for pkg in missing:
            print(f"  - {pkg}")

        if ask_yes_no("Voulez-vous les installer avec pip maintenant ?", default=True):
            try:
                with progress_step("Installation des dépendances Python"):
                    orchestrator.install_python_dependencies()
                print(colorize("Installation terminée avec succès !", Colors.OKGREEN))
            except PipInstallError as e:
                error_title = colorize("Erreur d'installation pip", Colors.FAIL)
                print_block(
                    f"{error_title}\n"
                    "L'installation a échoué. Voici les détails :\n"
                    f"--------------------------------------------------\n{e}\n"
                    "--------------------------------------------------"
                )
        else:
            print(colorize("Installation annulée.", Colors.WARNING))

    input("\nAppuyez sur Entrée pour continuer...")

def run_build_flow(orchestrator: Orchestrator):
    """Gère le sous-menu de gestion du firmware."""
    from .build_manager import BuildManager # Importation locale pour l'accès aux méthodes

    build_manager = BuildManager(orchestrator.base_dir)

    while True:
        print_block(colorize("Gestion du Firmware", Colors.HEADER))
        selection = ask_menu([
            "Configurer le firmware (menuconfig)",
            "Compiler le firmware",
            "Sauvegarder la configuration actuelle",
            "Charger une configuration",
            "Retour au menu principal"
        ], default_index=1)

        if selection == 0:
            try:
                build_manager.launch_menuconfig()
            except BuildManagerError as e:
                print(colorize(f"Erreur: {e}", Colors.FAIL))
        elif selection == 1:
            try:
                with progress_step("Compilation du firmware Klipper"):
                    # Nous compilons avec la configuration actuelle, pas celle par défaut
                    build_manager.compile_firmware(use_default_config=False)
                print(colorize("Build terminé.", Colors.OKGREEN))
            except (BuildManagerError, FileNotFoundError) as e:
                print(colorize(f"La compilation a échoué: {e}", Colors.FAIL))
        elif selection == 2:
            name = ask_text("Nom pour la sauvegarde", default="ma_config")
            try:
                build_manager.save_config(name)
            except BuildManagerError as e:
                print(colorize(f"Erreur de sauvegarde: {e}", Colors.FAIL))
        elif selection == 3:
            # Idéalement, on listerait les configs disponibles. Simplifions pour l'instant.
            name = ask_text("Nom de la configuration à charger")
            try:
                build_manager.load_config(name)
            except BuildManagerError as e:
                print(colorize(f"Erreur de chargement: {e}", Colors.FAIL))
        elif selection == 4:
            return

def run_flash_flow(orchestrator: Orchestrator, profile: QuickProfile):
    """Gère le processus de flashage."""
    firmware_path = find_default_firmware()
    if firmware_path and ask_yes_no(f"Utiliser le firmware {firmware_path} ?", default=True):
        pass  # On utilise le firmware par défaut
    else:
        while True:
            path_str = ask_text("Chemin du firmware", required=True)
            candidate_path = Path(path_str).expanduser().resolve()
            if candidate_path.is_file():
                firmware_path = candidate_path
                break
            print(colorize(f"Fichier '{candidate_path}' introuvable. Veuillez réessayer.", Colors.FAIL))

    flash_manager = FlashManager(Path(__file__).resolve().parent)
    detected_devices = flash_manager.detect_serial_devices()

    serial_device = ""
    if detected_devices:
        print(colorize("Périphériques USB détectés :", Colors.HEADER))
        for i, dev in enumerate(detected_devices, 1):
            print(f"  {i}. {dev}")
        choice = ask_menu([f"Utiliser {dev}" for dev in detected_devices] + ["Saisir un autre chemin"], default_index=0)
        if choice < len(detected_devices):
            serial_device = detected_devices[choice]
        else:
            serial_device = ask_text("Chemin du périphérique USB", default=profile.serial_device)
    else:
        serial_device = ask_text("Chemin du périphérique USB", default=profile.serial_device)

    profile.serial_device = serial_device
    save_profile(profile)

    if not ask_yes_no("Lancer le flash ?", default=True):
        print(colorize("Opération annulée.", Colors.WARNING))
        return

    try:
        with progress_step("Flashage du firmware"):
            orchestrator.run_flash(firmware_path, serial_device)
        print(colorize("\nFlash terminé avec succès !", f"{Colors.BOLD}{Colors.OKGREEN}"))
    except FlashManagerError as e:
        error_title = colorize("Rapport d'erreur de flashage", Colors.FAIL)
        bootloader_instructions = f"""
        {colorize('Procédure pour le mode Bootloader Manuel :', f'{Colors.BOLD}{Colors.WARNING}')}
        Certaines cartes nécessitent une intervention manuelle pour entrer en mode flash.
        Veuillez suivre ces étapes et réessayer :
          1. Débranchez la carte de l'ordinateur.
          2. Maintenez le bouton 'BOOT' (ou 'B') enfoncé.
          3. Tout en le maintenant, rebranchez la carte.
          4. Relâchez le bouton.
          5. Relancez l'opération de flashage.
        """
        print_block(
            f"{error_title}\n"
            "Le flashage a échoué. Voici les détails de l'erreur :\n"
            f"--------------------------------------------------\n{e}\n"
            f"--------------------------------------------------\n"
            f"{textwrap.dedent(bootloader_instructions)}"
        )

def display_dashboard(orchestrator: Orchestrator):
    """Affiche le tableau de bord dynamique."""
    status = orchestrator.get_system_status()

    # Formatage des statuts
    repo_status = colorize("[✓] Cloné", Colors.OKGREEN) if status.klipper_repo_exists else colorize("[✗] Non trouvé", Colors.FAIL)
    firmware_status = colorize("[✓] Compilé", Colors.OKGREEN) if status.firmware_exists else colorize("[✗] Non compilé", Colors.FAIL)

    if status.detected_devices:
        device_status = colorize(f"[✓] {status.detected_devices[0]}", Colors.OKGREEN)
        if len(status.detected_devices) > 1:
            device_status += colorize(f" (+{len(status.detected_devices) - 1} autres)", Colors.OKCYAN)
    else:
        device_status = colorize("[!] Aucune carte détectée", Colors.WARNING)

    dashboard = f"""
    {colorize('Assistant BMCU → Klipper', f'{Colors.BOLD}{Colors.OKBLUE}')}
    /-------------------------------------------------------\\
    | ÉTAT DU SYSTÈME :                                      |
    |-------------------------------------------------------|
    | 1. Dépôt Klipper : {repo_status:<46} |
    | 2. Firmware BMCU-C : {firmware_status:<46} |
    | 3. Carte connectée : {device_status:<46} |
    \\-------------------------------------------------------/
    """
    print_block(dashboard)


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(description="Assistant interactif pour flasher le BMCU vers Klipper")
    parser.parse_args(argv)

    display_logo()
    profile = load_profile()
    base_dir = Path(__file__).resolve().parent
    orchestrator = Orchestrator(base_dir)

    while True:
        display_dashboard(orchestrator)

        selection = ask_menu(
            [
                "Gestion du firmware",
                "Flasher le firmware",
                "Vérifier les dépendances (avancé)",
                "Quitter",
            ],
            default_index=0,
        )

        if selection == 0:
            run_build_flow(orchestrator)
        elif selection == 1:
            run_flash_flow(orchestrator, profile)
        elif selection == 2:
            run_dependency_check(orchestrator)
            run_python_dependency_check(orchestrator)
        elif selection == 3:
            print(colorize("À bientôt !", Colors.OKBLUE))
            return 0

if __name__ == "__main__":
    sys.exit(main())

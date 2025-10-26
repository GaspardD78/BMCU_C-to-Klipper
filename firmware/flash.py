#!/usr/bin/env python3
"""Interface interactive pour faciliter l'usage du script d'automatisation.

Ce module fournit une CLI conviviale autour de
``flashBMCUtoKlipper_automation.py``. L'objectif est de guider
l'utilisateur pas-à-pas, de rappeler les prérequis critiques avant de
lancer le flash et de générer automatiquement un *prompt* d'assistance en
cas d'échec. Ce *prompt* peut être copié/collé dans une discussion avec un
assistant afin d'accélérer le diagnostic.
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
    if default is True:
        suffix = " [O/n] "
    elif default is False:
        suffix = " [o/N] "
    else:
        suffix = " [o/n] "

    while True:
        answer = input(colorize(question, Colors.OKCYAN) + suffix).strip().lower()
        if not answer and default is not None:
            return default
        if answer in {"o", "oui", "y", "yes"}:
            return True
        if answer in {"n", "non", "no"}:
            return False
        print(colorize("Réponse invalide. Merci d'indiquer 'o' pour oui ou 'n' pour non.", Colors.WARNING))


def ask_text(question: str, *, default: str | None = None, required: bool = True) -> str:
    """Récupère une chaîne de caractères en respectant un défaut éventuel."""
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


def ask_int(question: str, *, default: int) -> int:
    """Demande un entier avec validation."""
    while True:
        answer = ask_text(question, default=str(default), required=True)
        try:
            return int(answer)
        except ValueError:
            print(colorize("Merci de saisir une valeur numérique valide.", Colors.WARNING))


def ask_password(question: str) -> str:
    """Demande un mot de passe sans l'afficher."""
    while True:
        password = getpass.getpass(prompt=colorize(f"{question} : ", Colors.OKCYAN))
        if password:
            return password
        print(colorize("Le mot de passe ne peut pas être vide.", Colors.WARNING))


def ensure_firmware_path(path_str: str) -> Path:
    """Valide l'existence du fichier firmware fourni."""
    firmware_path = Path(path_str).expanduser().resolve()
    if not firmware_path.is_file():
        raise FileNotFoundError(colorize(f"Le fichier '{firmware_path}' est introuvable.", Colors.FAIL))
    return firmware_path


def gather_user_choices() -> UserChoices:
    """Collecte toutes les informations nécessaires."""
    intro_text = f"""
{colorize('Bienvenue dans l\'assistant de flash du BMCU-C vers Klipper.', f'{Colors.BOLD}{Colors.OKBLUE}')}

Ce guide interactif va :
  • rappeler les points de contrôle indispensables ;
  • collecter les paramètres nécessaires au script
    `flashBMCUtoKlipper_automation.py` ;
  • lancer le processus et analyser le résultat ;
  • en cas d'échec, générer un prompt prêt à l'emploi pour demander
    de l'aide.

{colorize('⚠️ Cette procédure peut rendre le module inopérant si elle est interrompue ou mal paramétrée. Assurez-vous de comprendre chaque étape avant de poursuivre.', Colors.WARNING)}
"""
    print_block(intro_text)

    print(colorize("Checklist des prérequis :", Colors.HEADER))
    for index, item in enumerate(CHECKLIST_ITEMS, start=1):
        print(f"  {index}. {item}")
    print()

    if not ask_yes_no("Avez-vous validé chacun des points ci-dessus ?", default=True):
        print(colorize("Veuillez préparer l'environnement puis relancer l'assistant.", Colors.WARNING))
        sys.exit(0)

    print()
    print(colorize("Paramètres de connexion :", Colors.HEADER))
    bmc_host = ask_text("Adresse IP ou nom d'hôte du BMC", required=True)
    bmc_user = ask_text("Utilisateur SSH/IPMI", default="root")
    bmc_password = ask_password("Mot de passe SSH/IPMI")
    ssh_port = ask_int("Port SSH", default=22)

    print()
    print(colorize("Configuration du firmware :", Colors.HEADER))
    while True:
        firmware_input = ask_text("Chemin local du firmware Klipper", required=True)
        try:
            firmware_file = ensure_firmware_path(firmware_input)
            break
        except FileNotFoundError as err:
            print(err)

    remote_firmware_path = ask_text(
        "Chemin de destination sur le BMC",
        default="/tmp/klipper_firmware.bin",
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

    print()
    print(colorize("Commandes et timeouts :", Colors.HEADER))
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

    print()
    print(colorize("Options de post-vérification :", Colors.HEADER))
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

    print()
    print(colorize("Configuration de l'assistant :", Colors.HEADER))
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
    {colorize('Récapitulatif de la configuration sélectionnée :', f'{Colors.BOLD}{Colors.OKBLUE}')}

      • {colorize('BMC', Colors.BOLD)}                  : {choices.bmc_user}@{choices.bmc_host}:{choices.ssh_port}
      • {colorize('Firmware local', Colors.BOLD)}       : {choices.firmware_file}
      • {colorize('Chemin distant', Colors.BOLD)}       : {choices.remote_firmware_path}
      • {colorize('Commande flash', Colors.BOLD)}       : {choices.flash_command}
      • {colorize('Timeout flash', Colors.BOLD)}        : {choices.flash_timeout} s
      • {colorize('Attendre reboot', Colors.BOLD)}      : {colorize('oui' if choices.wait_for_reboot else 'non', Colors.OKGREEN if choices.wait_for_reboot else Colors.WARNING)}
      • {colorize('Autoriser même version', Colors.BOLD)}: {colorize('oui' if choices.allow_same_version else 'non', Colors.WARNING if choices.allow_same_version else Colors.OKGREEN)}
      • {colorize('Version attendue', Colors.BOLD)}     : {choices.expected_final_version or 'non définie'}
      • {colorize('Empreinte SHA-256', Colors.BOLD)}    : {choices.firmware_sha256 or 'non vérifiée'}
      • {colorize('Mode test à blanc', Colors.BOLD)}    : {colorize('oui' if choices.dry_run else 'non', Colors.WARNING if choices.dry_run else Colors.OKGREEN)}
      • {colorize('Répertoire de logs', Colors.BOLD)}   : {choices.log_root}
    """
    print_block(summary)


def build_command(choices: UserChoices) -> list[str]:
    """Construit la commande d'invocation du script d'automatisation."""
    script_path = Path(__file__).resolve().with_name("flashBMCUtoKlipper_automation.py")
    command: list[str] = [
        sys.executable,
        str(script_path),
        "--bmc-host", choices.bmc_host,
        "--bmc-user", choices.bmc_user,
        "--bmc-password", choices.bmc_password,
        "--firmware-file", str(choices.firmware_file),
        "--remote-firmware-path", choices.remote_firmware_path,
        "--ssh-port", str(choices.ssh_port),
        "--flash-command", choices.flash_command,
        "--flash-timeout", str(choices.flash_timeout),
        "--log-root", str(choices.log_root),
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
    print(colorize("Lancement du processus d'automatisation...", Colors.OKBLUE) + "\n")
    print(colorize("Commande exécutée :", Colors.HEADER))
    print("  " + format_command(command))
    print()

    # Utilise Popen pour un affichage en temps réel
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace') as process:
        if process.stdout:
            for line in process.stdout:
                print(line, end='')
        process.wait()
        return subprocess.CompletedProcess(process.args, process.returncode)


def format_command(command: Iterable[str]) -> str:
    """Formate une commande sous forme de chaîne safe."""
    return " ".join(shlex.quote(part) for part in command)


def find_latest_log_dir(log_root: Path) -> Path | None:
    """Retourne le dernier dossier de log généré dans le répertoire cible."""
    if not log_root.exists():
        return None
    candidates = [entry for entry in log_root.iterdir() if entry.is_dir()]
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
        return "\n".join(lines[-limit:])
    except OSError as err:
        return f"Impossible de lire le fichier de log : {err}"


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
    return textwrap.dedent(
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


def main() -> int:
    try:
        choices = gather_user_choices()
    except KeyboardInterrupt:
        print(colorize("\nInterruption par l'utilisateur. Fin de l'assistant.", Colors.WARNING))
        return 1

    summarize_choices(choices)

    if not ask_yes_no("Confirmez-vous le lancement du flash ?", default=True):
        print(colorize("Opération annulée. Aucun flash n'a été lancé.", Colors.WARNING))
        return 0

    choices.log_root.mkdir(parents=True, exist_ok=True)
    command = build_command(choices)
    result = run_automation(command)
    latest_log_dir = find_latest_log_dir(choices.log_root)

    if result.returncode == 0:
        print(colorize("\n✅ Flash terminé avec succès !", f"{Colors.BOLD}{Colors.OKGREEN}"))
        if latest_log_dir is not None:
            print(f"Journaux disponibles dans : {latest_log_dir}")
        return 0

    print(colorize(f"\n❌ Le script d'automatisation a signalé une erreur (code de sortie {result.returncode}).", f"{Colors.BOLD}{Colors.FAIL}"))
    if latest_log_dir is not None:
        print(f"Consultez le journal : {latest_log_dir / 'debug.log'}")

    prompt = generate_assistance_prompt(choices, command, latest_log_dir, result.returncode)
    print(colorize("\n--- Prompt d'assistance suggéré ---", Colors.HEADER))
    print(prompt)
    print(colorize("--- Fin du prompt ---", Colors.HEADER) + "\n")

    return result.returncode


if __name__ == "__main__":  # pragma: no cover - point d'entrée CLI
    sys.exit(main())

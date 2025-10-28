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

"""Interface interactive simplifiée pour la préparation et le flash.

Ce module fournit une CLI légère autour de
``flashBMCUtoKlipper_automation.py`` et ``build.sh``. L'objectif est de
proposer, dès le clonage du dépôt, un point d'entrée unique pour :

* préparer le firmware Klipper ;
* lancer le flash via l'hôte passerelle (Raspberry Pi ou CB2) ;
* limiter au maximum les questions longues ou répétitives.

Les réglages essentiels sont mémorisés pour les exécutions suivantes et
une assistance reste disponible en cas d'échec.
"""

from __future__ import annotations

import getpass
import json
import shlex
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass, asdict
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
# Structures pour les vérifications
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    """Résultat d'une vérification de prérequis."""

    label: str
    success: bool
    detail: str = ""


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
    serial_device: str


CONFIG_FILE = Path(__file__).resolve().with_name("flash_profile.json")


@dataclass
class QuickProfile:
    """Préférences simplifiées mémorisées entre deux exécutions."""

    gateway_host: str = ""
    gateway_user: str = "pi"
    remote_firmware_path: str = "/tmp/klipper_firmware.bin"
    log_root: str = "logs"
    wait_for_reboot: bool = True
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
# Vérifications automatisées
# ---------------------------------------------------------------------------


def display_check_results(title: str, results: Iterable[CheckResult]) -> None:
    """Affiche un bloc synthétique avec le résultat des vérifications."""

    print(colorize(title, Colors.HEADER))
    for result in results:
        status = colorize("OK", Colors.OKGREEN) if result.success else colorize("KO", Colors.FAIL)
        print(f"  • {result.label}: {status}")
        if result.detail:
            detail = textwrap.indent(result.detail.strip(), "      ")
            print(detail)
    print()


def check_command_available(command: str) -> CheckResult:
    """Vérifie la présence d'une commande système locale."""

    location = shutil.which(command)
    if location:
        return CheckResult(label=f"Commande '{command}'", success=True, detail=location)
    return CheckResult(
        label=f"Commande '{command}'",
        success=False,
        detail="Introuvable dans le PATH. Installez la dépendance avant de poursuivre.",
    )


def check_required_file(path: Path) -> CheckResult:
    """Confirme la présence d'un fichier requis."""

    if path.exists():
        return CheckResult(label=f"Fichier '{path.name}'", success=True, detail=str(path))
    return CheckResult(
        label=f"Fichier '{path.name}'",
        success=False,
        detail="Le fichier est introuvable. Vérifiez votre clone du dépôt.",
    )


def run_local_prerequisite_checks() -> list[CheckResult]:
    """Exécute les vérifications locales avant toute interaction distante."""

    flash_dir = Path(__file__).resolve().parent
    results = [
        check_command_available("sshpass"),
        check_command_available("scp"),
        check_command_available("ping"),
        check_required_file(flash_dir / "flashBMCUtoKlipper_automation.py"),
    ]
    return results


def run_remote_command(
    host: str,
    user: str,
    password: str,
    port: int,
    command: str,
    *,
    timeout: int = 15,
) -> subprocess.CompletedProcess[str]:
    """Exécute une commande distante via SSH en capturant la sortie."""

    ssh_command = [
        "sshpass",
        "-p",
        password,
        "ssh",
        "-p",
        str(port),
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "BatchMode=no",
        f"{user}@{host}",
        command,
    ]

    return subprocess.run(
        ssh_command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def prioritize_serial_devices(devices: list[str]) -> list[str]:
    """Trie les périphériques détectés par pertinence."""

    def priority(path: str) -> tuple[int, str]:
        lowered = path.lower()
        if "1a86" in lowered:
            return (0, path)
        if "wch" in lowered or "ch32" in lowered:
            return (1, path)
        if "/dev/serial/by-id/" in path:
            return (2, path)
        return (3, path)

    unique: list[str] = []
    seen: set[str] = set()
    for device in devices:
        if device not in seen:
            seen.add(device)
            unique.append(device)

    return [device for _, device in sorted((priority(dev), dev) for dev in unique)]


def detect_remote_serial_devices(
    host: str,
    user: str,
    password: str,
    port: int,
) -> tuple[list[str], str]:
    """Récupère la liste des périphériques série/USB visibles depuis la passerelle."""

    remote_script = (
        "sh -c 'for path in /dev/serial/by-id/* /dev/ttyUSB* /dev/ttyACM* "
        "/dev/ttyAMA* /dev/ttyS* /dev/ttyCH*; do "
        '[ -e "$path" ] && printf "%s\\n" "$path"; '
        "done'"
    )
    result = run_remote_command(host, user, password, port, remote_script)

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"Code retour {result.returncode}"
        return [], detail

    devices = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return prioritize_serial_devices(devices), result.stdout.strip()


def run_remote_prerequisite_checks(
    host: str,
    user: str,
    password: str,
    port: int,
) -> tuple[list[CheckResult], list[str]]:
    """Effectue les vérifications dépendant de la passerelle BMCU."""

    results: list[CheckResult] = []

    try:
        probe = run_remote_command(host, user, password, port, "printf '__bmcu__'")
    except FileNotFoundError as err:
        return (
            [
                CheckResult(
                    label="Connexion SSH",
                    success=False,
                    detail=f"sshpass introuvable : {err}",
                )
            ],
            [],
        )
    except subprocess.TimeoutExpired:
        return (
            [
                CheckResult(
                    label="Connexion SSH",
                    success=False,
                    detail="Timeout atteint lors de la tentative de connexion SSH.",
                )
            ],
            [],
        )

    if probe.returncode != 0 or "__bmcu__" not in probe.stdout:
        detail = probe.stderr.strip() or probe.stdout.strip() or f"Code retour {probe.returncode}"
        results.append(CheckResult(label="Connexion SSH", success=False, detail=detail))
        return results, []

    results.append(
        CheckResult(
            label="Connexion SSH",
            success=True,
            detail="Authentification réussie.",
        )
    )

    devices: list[str]
    detection_detail: str
    try:
        devices, detection_detail = detect_remote_serial_devices(host, user, password, port)
    except subprocess.TimeoutExpired:
        results.append(
            CheckResult(
                label="Détection USB",
                success=False,
                detail="Timeout pendant l'énumération des périphériques USB.",
            )
        )
        return results, []

    if devices:
        formatted = "\n".join(devices)
        results.append(
            CheckResult(
                label="Détection USB",
                success=True,
                detail=formatted,
            )
        )
        return results, devices

    detail = detection_detail or "Aucun périphérique série détecté sur la passerelle."
    results.append(
        CheckResult(
            label="Détection USB",
            success=False,
            detail=detail,
        )
    )
    return results, []


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


def ask_password(question: str) -> str:
    """Demande un mot de passe sans l'afficher."""
    while True:
        password = getpass.getpass(prompt=colorize(f"{question} : ", Colors.OKCYAN))
        if password:
            return password
        print(colorize("Le mot de passe ne peut pas être vide.", Colors.WARNING))


def prompt_serial_device(detected_devices: list[str], previous: str) -> str:
    """Propose une sélection de périphérique USB ou un champ libre."""

    if detected_devices:
        print(colorize("Périphériques USB détectés :", Colors.HEADER))
        for index, device in enumerate(detected_devices, start=1):
            print(f"  {index}. {device}")

        options = [f"Utiliser {device}" for device in detected_devices]
        options.append("Saisir un autre chemin")
        options.append("Ignorer pour l'instant")

        choice = ask_menu(options, default_index=0)
        if choice < len(detected_devices):
            return detected_devices[choice]
        if choice == len(detected_devices):
            manual_default = previous or detected_devices[0]
            return ask_text("Chemin du périphérique USB", default=manual_default, required=False)
        return ""

    manual_default = previous or ""
    return ask_text("Chemin du périphérique USB", default=manual_default, required=False)


def ensure_firmware_path(path_str: str) -> Path:
    """Valide l'existence du fichier firmware fourni."""
    firmware_path = Path(path_str).expanduser().resolve()
    if not firmware_path.is_file():
        raise FileNotFoundError(colorize(f"Le fichier '{firmware_path}' est introuvable.", Colors.FAIL))
    return firmware_path


def find_default_firmware() -> Path | None:
    """Tente de localiser automatiquement le firmware généré."""

    base_dir = Path(__file__).resolve().parent
    candidates = [
        base_dir / ".cache/klipper/out/klipper.bin",
        base_dir / "klipper.bin",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def ask_menu(options: list[str], *, default_index: int = 0) -> int:
    """Propose un menu numéroté simple."""

    for index, option in enumerate(options, start=1):
        print(f"  {index}. {option}")

    prompt = colorize("Choix", Colors.OKCYAN) + f" [{default_index + 1}] : "
    while True:
        answer = input(prompt).strip()
        if not answer:
            return default_index
        if answer.isdigit():
            value = int(answer)
            if 1 <= value <= len(options):
                return value - 1
        print(colorize("Merci d'entrer un numéro valide.", Colors.WARNING))


def gather_user_choices(profile: QuickProfile) -> UserChoices:
    """Collecte les informations essentielles en mode simplifié."""

    intro_text = f"""
{colorize("Assistant BMCU → Klipper", f"{Colors.BOLD}{Colors.OKBLUE}")}

1. Vérifie trois prérequis.
2. Récupère les infos minimales.
3. Lance l'automatisation.

Tout passe par l'hôte passerelle (Raspberry Pi ou CB2).
"""
    print_block(intro_text)

    local_checks = run_local_prerequisite_checks()
    display_check_results("Diagnostic local :", local_checks)
    if not all(result.success for result in local_checks):
        print(colorize("Préparez l'environnement local puis relancez l'assistant.", Colors.FAIL))
        sys.exit(1)

    print(colorize("Connexion passerelle :", Colors.HEADER))
    host_question = "IP/nom du Raspberry ou CB2"
    if profile.gateway_host:
        bmc_host = ask_text(host_question, default=profile.gateway_host)
    else:
        bmc_host = ask_text(host_question, required=True)
    profile.gateway_host = bmc_host

    if profile.gateway_user:
        bmc_user = ask_text("Utilisateur SSH", default=profile.gateway_user)
    else:
        bmc_user = ask_text("Utilisateur SSH", default="pi")
    profile.gateway_user = bmc_user

    bmc_password = ask_password("Mot de passe SSH")
    ssh_port = 22

    remote_checks, detected_devices = run_remote_prerequisite_checks(
        bmc_host, bmc_user, bmc_password, ssh_port
    )
    display_check_results("Diagnostic passerelle :", remote_checks)
    ssh_ok = any(result.label == "Connexion SSH" and result.success for result in remote_checks)
    if not ssh_ok:
        print(colorize("Connexion SSH impossible : corrigez l'accès distant avant de continuer.", Colors.FAIL))
        sys.exit(1)

    serial_device = prompt_serial_device(detected_devices, profile.serial_device)
    profile.serial_device = serial_device

    print()
    print(colorize("Firmware :", Colors.HEADER))
    detected_firmware = find_default_firmware()
    firmware_file: Path
    if detected_firmware and ask_yes_no(
        f"Utiliser {detected_firmware}?", default=True
    ):
        firmware_file = detected_firmware
    else:
        while True:
            firmware_input = ask_text("Chemin du firmware", required=True)
            try:
                firmware_file = ensure_firmware_path(firmware_input)
                break
            except FileNotFoundError as err:
                print(err)

    if profile.remote_firmware_path:
        remote_firmware_path = ask_text(
            "Chemin distant (SSH)", default=profile.remote_firmware_path
        )
    else:
        remote_firmware_path = ask_text(
            "Chemin distant (SSH)", default="/tmp/klipper_firmware.bin"
        )
    profile.remote_firmware_path = remote_firmware_path

    wait_for_reboot = ask_yes_no(
        "Attendre le reboot automatique ?", default=profile.wait_for_reboot
    )
    profile.wait_for_reboot = wait_for_reboot
    reboot_timeout = 600
    reboot_check_interval = 10

    log_default = profile.log_root or "logs"
    log_root_input = ask_text("Dossier de logs", default=log_default)
    profile.log_root = log_root_input
    log_root = Path(log_root_input).expanduser().resolve()

    return UserChoices(
        bmc_host=bmc_host,
        bmc_user=bmc_user,
        bmc_password=bmc_password,
        firmware_file=firmware_file,
        remote_firmware_path=remote_firmware_path,
        ssh_port=ssh_port,
        pre_update_command="",
        flash_command="socflash -s {firmware}",
        flash_timeout=1800,
        wait_for_reboot=wait_for_reboot,
        reboot_timeout=reboot_timeout,
        reboot_check_interval=reboot_check_interval,
        allow_same_version=False,
        expected_final_version="",
        firmware_sha256="",
        dry_run=False,
        log_root=log_root,
        serial_device=serial_device,
    )


def summarize_choices(choices: UserChoices) -> None:
    """Affiche un résumé compact des paramètres retenus."""

    summary = f"""
    {colorize('Récapitulatif rapide :', f'{Colors.BOLD}{Colors.OKBLUE}')}

      • {colorize('Passerelle', Colors.BOLD)}     : {choices.bmc_user}@{choices.bmc_host}:{choices.ssh_port}
      • {colorize('Firmware', Colors.BOLD)}       : {choices.firmware_file}
      • {colorize('Copie distante', Colors.BOLD)} : {choices.remote_firmware_path}
      • {colorize('Périphérique USB', Colors.BOLD)} : {choices.serial_device or 'non défini'}
      • {colorize('Commande', Colors.BOLD)}       : {choices.flash_command}
      • {colorize('Timeout', Colors.BOLD)}        : {choices.flash_timeout} s
      • {colorize('Attendre reboot', Colors.BOLD)}: {colorize('oui' if choices.wait_for_reboot else 'non', Colors.OKGREEN if choices.wait_for_reboot else Colors.WARNING)}
      • {colorize('Logs', Colors.BOLD)}           : {choices.log_root}
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
    if choices.serial_device:
        command.extend(["--serial-device", choices.serial_device])
    if choices.allow_same_version:
        command.append("--allow-same-version")
    if choices.expected_final_version:
        command.extend(["--expected-final-version", choices.expected_final_version])
    if choices.firmware_sha256:
        command.extend(["--firmware-sha256", choices.firmware_sha256])
    if choices.dry_run:
        command.append("--dry-run")

    return command


def run_build() -> bool:
    """Lance le script de build et retourne le succès."""

    build_script = Path(__file__).resolve().with_name("build.sh")
    if not build_script.exists():
        print(colorize("Script build.sh introuvable.", Colors.FAIL))
        return False

    print(colorize("Compilation du firmware Klipper…", Colors.OKBLUE))
    try:
        subprocess.run([str(build_script)], check=True)
    except subprocess.CalledProcessError as err:
        print(colorize(f"La compilation a échoué (code {err.returncode}).", Colors.FAIL))
        return False

    print(colorize("✅ Build terminé.", Colors.OKGREEN))
    return True


def run_flash_flow(profile: QuickProfile) -> int:
    """Enchaîne la collecte d'infos puis le flash."""

    try:
        choices = gather_user_choices(profile)
    except KeyboardInterrupt:
        print(colorize("\nInterruption utilisateur.", Colors.WARNING))
        return 1

    save_profile(profile)
    summarize_choices(choices)

    if not ask_yes_no("On lance le flash ?", default=True):
        print(colorize("Opération annulée.", Colors.WARNING))
        return 0

    choices.log_root.mkdir(parents=True, exist_ok=True)
    command = build_command(choices)
    result = run_automation(command)
    latest_log_dir = find_latest_log_dir(choices.log_root)

    if result.returncode == 0:
        print(colorize("\n✅ Flash terminé avec succès !", f"{Colors.BOLD}{Colors.OKGREEN}"))
        if latest_log_dir is not None:
            print(f"Journaux : {latest_log_dir}")
        return 0

    print(colorize(
        f"\n❌ Le script d'automatisation a signalé une erreur (code de sortie {result.returncode}).",
        f"{Colors.BOLD}{Colors.FAIL}",
    ))
    if latest_log_dir is not None:
        print(f"Consultez le journal : {latest_log_dir / 'debug.log'}")

    prompt = generate_assistance_prompt(choices, command, latest_log_dir, result.returncode)
    print(colorize("\n--- Prompt d'assistance suggéré ---", Colors.HEADER))
    print(prompt)
    print(colorize("--- Fin du prompt ---", Colors.HEADER) + "\n")

    return result.returncode


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
        - Périphérique USB : {choices.serial_device or '(non défini)'}
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
    """Point d'entrée CLI."""

    display_logo()
    profile = load_profile()

    intro_text = """
    Bienvenue ! Choisissez une action :
      1. Construire le firmware Klipper.
      2. Lancer le flash.
      3. Quitter.

    Appuyez sur Entrée pour le choix par défaut.
    """
    print_block(intro_text)

    while True:
        print(colorize("Menu rapide :", Colors.HEADER))
        selection = ask_menu(
            [
                "Préparer le firmware (build.sh)",
                "Flasher le BMCU",
                "Quitter",
            ],
            default_index=0,
        )

        if selection == 0:
            build_success = run_build()
            if build_success and ask_yes_no("Enchaîner avec le flash ?", default=True):
                return run_flash_flow(profile)
            continue

        if selection == 1:
            return run_flash_flow(profile)

        print(colorize("À bientôt !", Colors.OKBLUE))
        return 0


if __name__ == "__main__":  # pragma: no cover - point d'entrée CLI
    sys.exit(main())

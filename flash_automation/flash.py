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
    gateway_usb_device: str | None


CONFIG_FILE = Path(__file__).resolve().with_name("flash_profile.json")


@dataclass
class QuickProfile:
    """Préférences simplifiées mémorisées entre deux exécutions."""

    gateway_host: str = ""
    gateway_user: str = "pi"
    remote_firmware_path: str = "/tmp/klipper_firmware.bin"
    log_root: str = "logs"
    wait_for_reboot: bool = True
    gateway_usb_device: str = ""


@dataclass
class CheckResult:
    """Résultat d'une vérification automatique."""

    label: str
    success: bool
    details: str = ""
    payload: object | None = None


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


def check_command_available(command: str) -> bool:
    """Indique si une commande est accessible dans le PATH."""

    return shutil.which(command) is not None


def detect_local_serial_devices() -> list[str]:
    """Recense les périphériques série disponibles localement."""

    candidates: list[str] = []
    serial_by_id = Path("/dev/serial/by-id")
    if serial_by_id.is_dir():
        for path in serial_by_id.iterdir():
            if path.exists():
                candidates.append(str(path.resolve()))

    patterns = [
        "/dev/ttyUSB*",
        "/dev/ttyACM*",
        "/dev/ttyAMA*",
        "/dev/ttyS*",
        "/dev/ttyCH*",
    ]
    for pattern in patterns:
        for match in Path("/").glob(pattern.lstrip("/")):
            if match.exists():
                candidates.append(str(match.resolve()))

    seen: dict[str, None] = {}
    ordered: list[str] = []
    for candidate in candidates:
        if candidate not in seen:
            seen[candidate] = None
            ordered.append(candidate)
    return ordered


def detect_local_dfu_devices() -> list[str]:
    """Liste les périphériques DFU détectés via dfu-util."""

    if not check_command_available("dfu-util"):
        return []

    try:
        result = subprocess.run(
            ["dfu-util", "-l"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []

    devices: list[str] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if "Found DFU:" in line:
            devices.append(line)
    return devices


def format_check_icon(success: bool) -> str:
    """Retourne une icône colorée selon le statut."""

    if success:
        return colorize("✅", Colors.OKGREEN)
    return colorize("❌", Colors.FAIL)


def print_check_results(results: Iterable[CheckResult]) -> None:
    """Affiche un tableau compact des vérifications exécutées."""

    print(colorize("Diagnostic automatique :", Colors.HEADER))
    for result in results:
        icon = format_check_icon(result.success)
        print(f"  {icon} {result.label}")
        if result.details:
            for line in result.details.splitlines():
                print(f"      {line}")
    print()


def run_remote_probe(choices: UserChoices, remote_command: str, *, timeout: int = 15) -> subprocess.CompletedProcess[str]:
    """Exécute une commande sur la passerelle BMC via SSH."""

    ssh_command = [
        "sshpass",
        "-p",
        choices.bmc_password,
        "ssh",
        "-p",
        str(choices.ssh_port),
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "BatchMode=no",
        "-o",
        "ConnectTimeout=5",
        f"{choices.bmc_user}@{choices.bmc_host}",
        f"set -euo pipefail; {remote_command}",
    ]

    return subprocess.run(
        ssh_command,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def check_required_commands() -> CheckResult:
    """Vérifie la présence des commandes indispensables en local."""

    required = ["sshpass", "ssh", "scp", "ipmitool"]
    missing = [cmd for cmd in required if not check_command_available(cmd)]
    if missing:
        details = "Commandes manquantes : " + ", ".join(sorted(missing))
        return CheckResult("Outils locaux", False, details)
    return CheckResult("Outils locaux", True, "sshpass, ssh, scp et ipmitool sont disponibles.")


def check_local_usb_devices() -> CheckResult:
    """Contrôle la présence d'un périphérique USB accessible directement."""

    serial_devices = detect_local_serial_devices()
    dfu_devices = detect_local_dfu_devices()
    if not serial_devices and not dfu_devices:
        return CheckResult(
            "Périphérique USB local",
            False,
            "Aucun port série ou périphérique DFU détecté sur cette machine.",
        )

    details_lines: list[str] = []
    if serial_devices:
        details_lines.append("Ports série :")
        details_lines.extend(f"    - {device}" for device in serial_devices)
    if dfu_devices:
        details_lines.append("DFU (dfu-util) :")
        details_lines.extend(f"    - {device}" for device in dfu_devices)

    return CheckResult("Périphérique USB local", True, "\n".join(details_lines))


def check_remote_connection(choices: UserChoices) -> CheckResult:
    """Tente une connexion SSH rapide vers la passerelle."""

    if not choices.bmc_host:
        return CheckResult("Connexion SSH", False, "Aucune passerelle définie.")

    if not check_command_available("sshpass") or not check_command_available("ssh"):
        return CheckResult(
            "Connexion SSH",
            False,
            "sshpass ou ssh est introuvable ; impossible de tester la passerelle.",
        )

    try:
        result = run_remote_probe(choices, "echo connexion_ok")
    except subprocess.TimeoutExpired:
        return CheckResult("Connexion SSH", False, "Délai dépassé lors de la connexion SSH.")
    except OSError as err:
        return CheckResult("Connexion SSH", False, f"Impossible d'exécuter ssh : {err}")

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "Connexion refusée."
        return CheckResult("Connexion SSH", False, detail)

    return CheckResult("Connexion SSH", True, "Connexion établie avec la passerelle.")


def check_remote_usb_devices(choices: UserChoices) -> CheckResult:
    """Interroge la passerelle pour répertorier les ports USB accessibles."""

    if not choices.bmc_host:
        return CheckResult("Périphérique USB passerelle", False, "Aucune passerelle définie.")

    try:
        result = run_remote_probe(
            choices,
            (
                "python3 - <<'PY'\n"
                "import glob\n"
                "patterns = [\n"
                "    '/dev/serial/by-id/*',\n"
                "    '/dev/ttyUSB*',\n"
                "    '/dev/ttyACM*',\n"
                "    '/dev/ttyAMA*',\n"
                "    '/dev/ttyS*',\n"
                "    '/dev/ttyCH*',\n"
                "]\n"
                "devices = []\n"
                "for pattern in patterns:\n"
                "    devices.extend(glob.glob(pattern))\n"
                "seen = {}\n"
                "ordered = []\n"
                "for item in devices:\n"
                "    if item not in seen:\n"
                "        seen[item] = None\n"
                "        ordered.append(item)\n"
                "print('\\n'.join(ordered))\n"
                "PY"
            ),
            timeout=20,
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            "Périphérique USB passerelle",
            False,
            "Délai dépassé lors de la détection des périphériques USB sur la passerelle.",
        )
    except OSError as err:
        return CheckResult("Périphérique USB passerelle", False, f"Impossible de lancer ssh : {err}")

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "Commande distante en échec."
        return CheckResult("Périphérique USB passerelle", False, detail)

    devices = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not devices:
        return CheckResult(
            "Périphérique USB passerelle",
            False,
            "Aucun périphérique série détecté sur la passerelle.",
            payload=[],
        )

    details = "Ports détectés :\n" + "\n".join(f"    - {dev}" for dev in devices)
    return CheckResult("Périphérique USB passerelle", True, details, payload=devices)


def perform_prerequisite_checks(choices: UserChoices) -> list[CheckResult]:
    """Exécute l'ensemble des vérifications automatiques."""

    results: list[CheckResult] = []
    results.append(check_required_commands())
    results.append(check_local_usb_devices())
    ssh_result = check_remote_connection(choices)
    results.append(ssh_result)
    if ssh_result.success:
        results.append(check_remote_usb_devices(choices))
    else:
        results.append(
            CheckResult(
                "Périphérique USB passerelle",
                False,
                "Connexion SSH indisponible : détection impossible.",
                payload=[],
            )
        )
    return results


def select_gateway_usb_device(
    detected_devices: Iterable[str],
    previous_choice: str | None,
) -> str | None:
    """Permet à l'utilisateur de choisir le port USB utilisé pour le BMCU."""

    devices = [device for device in detected_devices]
    print(colorize("Périphérique USB BMCU :", Colors.HEADER))

    default_choice: str | None = None
    if previous_choice and previous_choice in devices:
        default_choice = previous_choice
    elif len(devices) == 1:
        default_choice = devices[0]

    if devices:
        print("Détection automatique :")
        for index, device in enumerate(devices, start=1):
            marker = " (défaut)" if default_choice == device else ""
            print(f"  {index}. {device}{marker}")

        prompt = "Numéro du périphérique ou chemin absolu"
        if default_choice:
            prompt += f" [{default_choice}]"

        while True:
            answer = input(colorize(f"{prompt} : ", Colors.OKCYAN)).strip()
            if not answer and default_choice:
                return default_choice
            if not answer:
                return None
            if answer.isdigit():
                value = int(answer)
                if 1 <= value <= len(devices):
                    return devices[value - 1]
            if answer.startswith("/"):
                return answer
            print(colorize("Sélection invalide. Entrez un numéro ou un chemin absolu commençant par '/'.", Colors.WARNING))

    print(colorize("Aucun périphérique détecté automatiquement.", Colors.WARNING))
    default = previous_choice or ""
    manual = ask_text("Chemin du périphérique USB BMCU", default=default, required=False)
    return manual or None

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

    print(colorize("Les prérequis seront vérifiés automatiquement après la saisie.", Colors.OKBLUE))
    print()
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
        gateway_usb_device=None,
    )


def summarize_choices(choices: UserChoices) -> None:
    """Affiche un résumé compact des paramètres retenus."""

    summary = f"""
    {colorize('Récapitulatif rapide :', f'{Colors.BOLD}{Colors.OKBLUE}')}

      • {colorize('Passerelle', Colors.BOLD)}     : {choices.bmc_user}@{choices.bmc_host}:{choices.ssh_port}
      • {colorize('USB passerelle', Colors.BOLD)} : {choices.gateway_usb_device or 'non spécifié'}
      • {colorize('Firmware', Colors.BOLD)}       : {choices.firmware_file}
      • {colorize('Copie distante', Colors.BOLD)} : {choices.remote_firmware_path}
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

    results = perform_prerequisite_checks(choices)
    print_check_results(results)

    detected_devices: Iterable[str] = []
    for result in results:
        if result.label == "Périphérique USB passerelle" and isinstance(result.payload, list):
            detected_devices = result.payload
            break

    selected_device = select_gateway_usb_device(detected_devices, profile.gateway_usb_device or None)
    choices.gateway_usb_device = selected_device
    profile.gateway_usb_device = selected_device or ""

    if selected_device:
        print(colorize(f"Périphérique retenu : {selected_device}", Colors.OKBLUE))
    else:
        print(colorize("Aucun périphérique USB sélectionné pour la passerelle.", Colors.WARNING))

    save_profile(profile)
    summarize_choices(choices)

    failures = [result for result in results if not result.success]
    if failures:
        print(colorize("Des prérequis semblent manquants ou incomplets.", Colors.WARNING))
        if not ask_yes_no("Continuer malgré tout ?", default=False):
            print(colorize("Opération annulée.", Colors.WARNING))
            return 0

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

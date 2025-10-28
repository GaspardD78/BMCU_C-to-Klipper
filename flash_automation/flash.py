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

import argparse
import getpass
import json
import platform
import shlex
import shutil
import subprocess
import sys
import textwrap
import threading
import time
from contextlib import contextmanager
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


@dataclass(frozen=True)
class SystemInfo:
    """Informations système utiles pour l'auto-configuration."""

    model: str
    os_release: dict[str, str]
    machine: str


@dataclass(frozen=True)
class EnvironmentDefaults:
    """Valeurs par défaut déterminées à partir de l'environnement."""

    label: str = "Environnement générique"
    host: str = ""
    user: str = getpass.getuser()
    remote_path: str = "/tmp/klipper_firmware.bin"
    serial_device: str = ""
    log_root: str = "logs"


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
# Détection d'environnement
# ---------------------------------------------------------------------------


def read_os_release() -> dict[str, str]:
    """Parse le fichier /etc/os-release si disponible."""

    path = Path("/etc/os-release")
    if not path.exists():
        return {}
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    result: dict[str, str] = {}
    for line in data.splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"')
    return result


def read_system_info() -> SystemInfo:
    """Collecte des informations système pour la détection de plateforme."""

    model_path = Path("/sys/firmware/devicetree/base/model")
    try:
        model = model_path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        model = platform.platform()

    return SystemInfo(model=model, os_release=read_os_release(), machine=platform.machine())


def detect_environment_defaults(info: SystemInfo | None = None) -> EnvironmentDefaults:
    """Déduit des valeurs par défaut en fonction de la plateforme courante."""

    info = info or read_system_info()
    model = info.model.lower()
    os_id = info.os_release.get("ID", "").lower()
    os_like = info.os_release.get("ID_LIKE", "").lower()

    if "raspberry pi" in model or "raspbian" in os_id or "raspbian" in os_like:
        return EnvironmentDefaults(label="Raspberry Pi", host="localhost", user="pi")

    if "bambu" in model or "cb2" in model or "bambu" in os_id:
        return EnvironmentDefaults(label="Bambu Lab CB2", host="localhost", user=getpass.getuser())

    if info.machine.startswith("arm") or info.machine.startswith("aarch"):
        return EnvironmentDefaults(label="Plateforme ARM", host="localhost", user=getpass.getuser())

    return EnvironmentDefaults()


def apply_environment_defaults(profile: QuickProfile, defaults: EnvironmentDefaults) -> None:
    """Complète le profil avec les valeurs détectées lorsqu'elles manquent."""

    if not profile.gateway_host:
        profile.gateway_host = defaults.host
    if not profile.gateway_user:
        profile.gateway_user = defaults.user
    if not profile.remote_firmware_path:
        profile.remote_firmware_path = defaults.remote_path
    if not profile.serial_device and defaults.serial_device:
        profile.serial_device = defaults.serial_device
    if not profile.log_root:
        profile.log_root = defaults.log_root


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


class PromptTimer:
    """Affiche périodiquement un message d'aide pendant une saisie."""

    def __init__(self, prompt: str, message: str | None, *, interval: float = 15.0):
        self.prompt = prompt
        self.message = message
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _worker(self) -> None:
        if not self.message:
            return
        elapsed = 0.0
        while not self._stop.wait(self.interval):
            elapsed += self.interval
            print()
            print(
                colorize(
                    f"⌛ En attente ({int(elapsed)}s) : {self.message}",
                    Colors.WARNING,
                )
            )
            if self.prompt:
                print(self.prompt, end="", flush=True)

    def __enter__(self):
        if self.message:
            self._thread = threading.Thread(target=self._worker, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval)
        return False


def ask_yes_no(question: str, *, default: bool | None = None, help_message: str | None = None) -> bool:
    """Demande une confirmation oui/non à l'utilisateur."""
    if default is True:
        suffix = " [O/n] "
    elif default is False:
        suffix = " [o/N] "
    else:
        suffix = " [o/n] "

    while True:
        prompt = colorize(question, Colors.OKCYAN) + suffix
        with PromptTimer(prompt, help_message):
            answer = input(prompt).strip().lower()
        if not answer and default is not None:
            return default
        if answer in {"o", "oui", "y", "yes"}:
            return True
        if answer in {"n", "non", "no"}:
            return False
        print(colorize("Réponse invalide. Merci d'indiquer 'o' pour oui ou 'n' pour non.", Colors.WARNING))


def ask_text(
    question: str,
    *,
    default: str | None = None,
    required: bool = True,
    help_message: str | None = None,
) -> str:
    """Récupère une chaîne de caractères en respectant un défaut éventuel."""
    while True:
        prompt = colorize(f"{question}", Colors.OKCYAN)
        if default:
            prompt += f" [{default}]"
        prompt += " : "

        with PromptTimer(prompt, help_message):
            value = input(prompt).strip()
        if not value:
            if default is not None:
                return default
            if not required:
                return ""
            print(colorize("Ce champ est obligatoire.", Colors.WARNING))
            continue
        return value


def ask_password(question: str, *, help_message: str | None = None) -> str:
    """Demande un mot de passe sans l'afficher."""
    while True:
        prompt = colorize(f"{question} : ", Colors.OKCYAN)
        with PromptTimer(prompt, help_message):
            password = getpass.getpass(prompt=prompt)
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


def gather_user_choices(profile: QuickProfile, environment: EnvironmentDefaults) -> UserChoices:
    """Collecte les informations essentielles en mode simplifié."""

    intro_text = f"""
{colorize("Assistant BMCU → Klipper", f"{Colors.BOLD}{Colors.OKBLUE}")}

1. Vérifie trois prérequis.
2. Récupère les infos minimales.
3. Lance l'automatisation.

Tout passe par l'hôte passerelle (Raspberry Pi ou CB2).
"""
    print_block(intro_text)

    with progress_step("Diagnostic local"):
        local_checks = run_local_prerequisite_checks()
    display_check_results("Diagnostic local :", local_checks)
    if not all(result.success for result in local_checks):
        print(colorize("Préparez l'environnement local puis relancez l'assistant.", Colors.FAIL))
        sys.exit(1)

    print(colorize("Connexion passerelle :", Colors.HEADER))
    print_block(
        """
        Le script ouvre ses propres connexions SSH pour copier le firmware et lancer
        les commandes de flash. Renseignez donc l'adresse IP ou le nom d'hôte de la
        passerelle (Raspberry Pi ou CB2) sur laquelle le BMCU est branché. Si vous
        exécutez l'assistant directement depuis cette machine, indiquez simplement
        « localhost » (ou 127.0.0.1).
        """
    )

    host_question = "IP/nom du Raspberry ou CB2"
    host_default = profile.gateway_host or environment.host or "localhost"
    user_default = profile.gateway_user or environment.user or "pi"
    ssh_port = 22

    attempt = 0
    detected_devices: list[str] = []
    while True:
        if attempt == 0:
            bmc_host = ask_text(
                host_question,
                default=host_default,
                required=True,
                help_message="Merci de saisir l'adresse IP ou le nom d'hôte de la passerelle (ex. 192.168.0.42).",
            )
            bmc_user = ask_text(
                "Utilisateur SSH",
                default=user_default,
                required=True,
                help_message="Merci de saisir l'utilisateur SSH autorisé (ex. pi, bambu).",
            )
        else:
            print(colorize("Réessayons la connexion. Ajustez les informations si nécessaire.", Colors.WARNING))
            bmc_host = ask_text(
                host_question,
                default=bmc_host or host_default,
                required=True,
                help_message="Merci de saisir un hôte atteignable (localhost si vous êtes sur la passerelle).",
            )
            bmc_user = ask_text(
                "Utilisateur SSH",
                default=bmc_user or user_default,
                required=True,
                help_message="Merci de saisir un utilisateur SSH valide (pi, bambu, utilisateur courant, ...).",
            )
        bmc_password = ask_password(
            "Mot de passe SSH",
            help_message="Merci de saisir le mot de passe SSH (aucune frappe n'apparaît, Ctrl+C pour annuler).",
        )

        with progress_step("Diagnostic de la passerelle"):
            remote_checks, detected_devices = run_remote_prerequisite_checks(
                bmc_host, bmc_user, bmc_password, ssh_port
            )
        display_check_results("Diagnostic passerelle :", remote_checks)
        ssh_ok = any(result.label == "Connexion SSH" and result.success for result in remote_checks)
        if ssh_ok:
            break

        attempt += 1
        print(
            colorize(
                "Connexion SSH impossible : corrigez l'accès distant avant de continuer.",
                Colors.FAIL,
            )
        )
        if not ask_yes_no(
            "Souhaitez-vous réessayer ?",
            default=True,
            help_message="Merci de confirmer si vous souhaitez retenter la connexion après vos ajustements.",
        ):
            print(colorize("Opération annulée.", Colors.WARNING))
            sys.exit(1)

    profile.gateway_host = bmc_host
    profile.gateway_user = bmc_user

    serial_device = prompt_serial_device(detected_devices, profile.serial_device)
    profile.serial_device = serial_device

    print()
    print(colorize("Firmware :", Colors.HEADER))
    detected_firmware = find_default_firmware()
    firmware_file: Path
    if detected_firmware and ask_yes_no(
        f"Utiliser {detected_firmware}?",
        default=True,
        help_message="Merci de confirmer si vous souhaitez réutiliser le firmware déjà détecté.",
    ):
        firmware_file = detected_firmware
    else:
        while True:
            firmware_input = ask_text(
                "Chemin du firmware",
                required=True,
                help_message="Utilisez ./klipper.bin ou un chemin absolu vers le firmware.",
            )
            try:
                firmware_file = ensure_firmware_path(firmware_input)
                break
            except FileNotFoundError as err:
                print(err)

    remote_default = profile.remote_firmware_path or environment.remote_path
    remote_firmware_path = ask_text(
        "Chemin distant (SSH)",
        default=remote_default,
        help_message="Merci de préciser où copier le firmware sur la passerelle (chemin absolu).",
    )
    profile.remote_firmware_path = remote_firmware_path

    wait_for_reboot = ask_yes_no(
        "Attendre le reboot automatique ?",
        default=profile.wait_for_reboot,
        help_message="Merci de confirmer si l'assistant doit surveiller automatiquement le redémarrage du BMCU.",
    )
    profile.wait_for_reboot = wait_for_reboot
    reboot_timeout = 600
    reboot_check_interval = 10

    log_default = profile.log_root or environment.log_root
    log_root_input = ask_text(
        "Dossier de logs",
        default=log_default,
        help_message="Merci d'indiquer le dossier qui accueillera les rapports d'exécution.",
    )
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


def update_profile_from_choices(profile: QuickProfile, choices: UserChoices) -> None:
    """Met à jour le profil simplifié avec les dernières informations."""

    profile.gateway_host = choices.bmc_host
    profile.gateway_user = choices.bmc_user
    profile.remote_firmware_path = choices.remote_firmware_path
    profile.wait_for_reboot = choices.wait_for_reboot
    profile.serial_device = choices.serial_device
    profile.log_root = str(choices.log_root)


def gather_choices_from_args(
    args: argparse.Namespace,
    profile: QuickProfile,
    environment: EnvironmentDefaults,
) -> UserChoices:
    """Construit les choix utilisateur à partir des arguments CLI."""

    missing: list[str] = []

    bmc_host = (
        args.bmc_host
        or profile.gateway_host
        or environment.host
        or "localhost"
    )
    if not bmc_host:
        missing.append("--bmc-host")

    bmc_user = args.bmc_user or profile.gateway_user or environment.user or "pi"
    if not bmc_user:
        missing.append("--bmc-user")

    bmc_password = args.bmc_password
    if not bmc_password:
        missing.append("--bmc-password")

    firmware_path: Path | None = None
    if args.firmware_file:
        try:
            firmware_path = ensure_firmware_path(args.firmware_file)
        except FileNotFoundError as err:
            raise ValueError(str(err)) from err
    else:
        firmware_path = find_default_firmware()
        if firmware_path is None:
            missing.append("--firmware-file")

    if missing:
        missing_args = ", ".join(missing)
        raise ValueError(
            "Mode non interactif : paramètres obligatoires manquants "
            f"({missing_args})."
        )

    remote_firmware_path = (
        args.remote_firmware_path
        or profile.remote_firmware_path
        or environment.remote_path
    )

    ssh_port = args.ssh_port if args.ssh_port is not None else 22
    flash_command = args.flash_command or "socflash -s {firmware}"
    flash_timeout = args.flash_timeout if args.flash_timeout is not None else 1800
    wait_for_reboot = (
        profile.wait_for_reboot if args.wait_for_reboot is None else args.wait_for_reboot
    )
    reboot_timeout = args.reboot_timeout if args.reboot_timeout is not None else 600
    reboot_check_interval = (
        args.reboot_check_interval if args.reboot_check_interval is not None else 10
    )
    log_root_str = (
        args.log_root
        or profile.log_root
        or environment.log_root
        or "logs"
    )
    log_root = Path(log_root_str).expanduser().resolve()
    serial_device = args.serial_device or profile.serial_device or environment.serial_device
    pre_update_command = args.pre_update_command or ""
    allow_same_version = args.allow_same_version
    expected_final_version = args.expected_final_version or ""
    firmware_sha256 = args.firmware_sha256 or ""
    dry_run = args.dry_run

    return UserChoices(
        bmc_host=bmc_host,
        bmc_user=bmc_user,
        bmc_password=bmc_password,
        firmware_file=firmware_path,
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
        serial_device=serial_device or "",
    )


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

    try:
        with progress_step("Compilation du firmware Klipper"):
            subprocess.run([str(build_script)], check=True)
    except subprocess.CalledProcessError as err:
        print(colorize(f"La compilation a échoué (code {err.returncode}).", Colors.FAIL))
        return False

    print(colorize("✅ Build terminé.", Colors.OKGREEN))
    return True


def run_flash_flow(
    profile: QuickProfile,
    environment: EnvironmentDefaults,
    *,
    preset_choices: UserChoices | None = None,
    ask_confirmation: bool = True,
) -> int:
    """Enchaîne la collecte d'infos puis le flash."""

    if preset_choices is None:
        try:
            choices = gather_user_choices(profile, environment)
        except KeyboardInterrupt:
            print(colorize("\nInterruption utilisateur.", Colors.WARNING))
            return 1
    else:
        choices = preset_choices

    update_profile_from_choices(profile, choices)
    save_profile(profile)
    summarize_choices(choices)

    if ask_confirmation:
        if not ask_yes_no(
            "On lance le flash ?",
            default=True,
            help_message="Validez pour démarrer immédiatement le processus de flash.",
        ):
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


def build_home_summary(profile: QuickProfile, environment: EnvironmentDefaults) -> str:
    """Construit le bloc récapitulatif affiché au démarrage."""

    firmware = find_default_firmware()
    firmware_display = str(firmware) if firmware else "à générer (build.sh)"
    host_display = profile.gateway_host or environment.host or "(à définir)"
    user_display = profile.gateway_user or environment.user or "(à définir)"
    remote_display = profile.remote_firmware_path or environment.remote_path
    serial_display = profile.serial_device or "(auto)"
    log_display = profile.log_root or environment.log_root

    return f"""
    {colorize('Assistant BMCU → Klipper', f'{Colors.BOLD}{Colors.OKBLUE}')}

      • Environnement détecté : {environment.label}
      • Passerelle suggérée   : {user_display}@{host_display}
      • Firmware local        : {firmware_display}
      • Copie distante        : {remote_display}
      • Périphérique USB      : {serial_display}
      • Dossier de logs       : {log_display}
    """


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """Analyse les paramètres en ligne de commande."""

    parser = argparse.ArgumentParser(
        description="Assistant interactif pour flasher le BMCU vers Klipper",
    )
    parser.add_argument(
        "--non-interactif",
        action="store_true",
        help="Exécute le flash directement avec les options passées en paramètres.",
    )
    parser.add_argument(
        "--auto-confirm",
        action="store_true",
        help="Skippe la confirmation finale avant de lancer le flash.",
    )
    parser.add_argument("--bmc-host", help="Adresse IP ou nom DNS de la passerelle.")
    parser.add_argument("--bmc-user", help="Utilisateur SSH sur la passerelle.")
    parser.add_argument(
        "--bmc-password",
        help="Mot de passe SSH correspondant (requis en mode non interactif).",
    )
    parser.add_argument(
        "--ssh-port",
        type=int,
        help="Port SSH utilisé pour joindre la passerelle.",
    )
    parser.add_argument(
        "--firmware-file",
        help="Chemin vers le firmware Klipper à flasher.",
    )
    parser.add_argument(
        "--remote-firmware-path",
        help="Chemin distant de dépôt du firmware sur la passerelle.",
    )
    parser.add_argument(
        "--serial-device",
        help="Chemin du périphérique série sur la passerelle (ex. /dev/ttyUSB0).",
    )
    parser.add_argument(
        "--log-root",
        help="Répertoire local où stocker les journaux de flash.",
    )
    parser.add_argument(
        "--flash-command",
        help="Commande de flash exécutée côté passerelle.",
    )
    parser.add_argument(
        "--flash-timeout",
        type=int,
        help="Durée maximale (en secondes) autorisée pour l'étape de flash.",
    )
    wait_group = parser.add_mutually_exclusive_group()
    wait_group.add_argument(
        "--wait-for-reboot",
        dest="wait_for_reboot",
        action="store_true",
        help="Force l'attente du redémarrage automatique.",
    )
    wait_group.add_argument(
        "--no-wait-for-reboot",
        dest="wait_for_reboot",
        action="store_false",
        help="Désactive l'attente automatique du redémarrage.",
    )
    parser.set_defaults(wait_for_reboot=None)
    parser.add_argument(
        "--reboot-timeout",
        type=int,
        help="Temps maximal (en secondes) pour attendre le retour en ligne.",
    )
    parser.add_argument(
        "--reboot-check-interval",
        type=int,
        help="Intervalle entre deux vérifications du reboot.",
    )
    parser.add_argument(
        "--pre-update-command",
        help="Commande préliminaire à exécuter sur la passerelle avant le flash.",
    )
    parser.add_argument(
        "--allow-same-version",
        action="store_true",
        help="Autorise le flash même si la version cible semble identique.",
    )
    parser.add_argument(
        "--expected-final-version",
        help="Version attendue après flash pour validation.",
    )
    parser.add_argument(
        "--firmware-sha256",
        help="Empreinte SHA-256 attendue du firmware (sécurité supplémentaire).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Active le mode test à blanc sans exécuter de commande distante.",
    )

    return parser.parse_args(argv)


def show_main_screen(profile: QuickProfile, environment: EnvironmentDefaults) -> int:
    """Affiche l'écran d'accueil unique avec les options principales."""

    print_block(build_home_summary(profile, environment))
    print(colorize("Choisissez une action :", Colors.HEADER))
    return ask_menu(
        [
            "Flasher le BMCU (assistant complet)",
            "Construire le firmware Klipper (build.sh)",
            "Quitter",
        ],
        default_index=0,
    )


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée CLI."""

    args = parse_arguments(argv)
    display_logo()
    profile = load_profile()
    environment = detect_environment_defaults()
    apply_environment_defaults(profile, environment)

    if args.non_interactif:
        try:
            choices = gather_choices_from_args(args, profile, environment)
        except ValueError as err:
            print(colorize(str(err), Colors.FAIL))
            return 2
        return run_flash_flow(
            profile,
            environment,
            preset_choices=choices,
            ask_confirmation=not (args.auto_confirm or args.non_interactif),
        )

    selection = show_main_screen(profile, environment)

    if selection == 0:
        return run_flash_flow(profile, environment, ask_confirmation=not args.auto_confirm)

    if selection == 1:
        build_success = run_build()
        if build_success and ask_yes_no(
            "Enchaîner avec le flash ?",
            default=True,
            help_message="Acceptez pour utiliser directement le firmware fraîchement compilé.",
        ):
            return run_flash_flow(
                profile,
                environment,
                ask_confirmation=not args.auto_confirm,
            )
        return 0 if build_success else 1

    print(colorize("À bientôt !", Colors.OKBLUE))
    return 0


if __name__ == "__main__":  # pragma: no cover - point d'entrée CLI
    sys.exit(main())

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

"""Ce module orchestre les opérations de haut niveau (build, flash) sans gérer
directement l'interface utilisateur.
"""

from __future__ import annotations

import getpass
import hashlib
import platform
import string
import subprocess
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Structures de données (sans dépendances UI)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Utilitaires de bas niveau
# ---------------------------------------------------------------------------

def find_default_firmware() -> Path | None:
    """Tente de localiser automatiquement le firmware généré."""

    base_dir = Path(__file__).resolve().parent
    candidates = [
        base_dir / ".cache/firmware/klipper.bin",
        base_dir / "klipper.bin",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


import sys
from importlib.metadata import version, PackageNotFoundError


class PipInstallError(Exception):
    """Exception pour les erreurs d'installation pip."""


from .build_manager import BuildManager, BuildManagerError
from .flash_manager import FlashManager, FlashManagerError


__all__ = ["BuildManagerError", "FlashManagerError", "PipInstallError", "Orchestrator"]


class Orchestrator:
    """Point d'entrée pour les opérations de haut niveau."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def run_build(self) -> bool:
        """Lance le script de build et retourne le succès."""
        manager = BuildManager(self.base_dir)
        manager.compile_firmware()
        return True

    def run_flash(self, firmware_path: Path, serial_device: str) -> bool:
        """Lance le flash et retourne le succès."""
        manager = FlashManager(self.base_dir)
        manager.flash("serial", firmware_path, serial_device)
        return True

    def get_system_dependencies(self) -> tuple[str | None, list[str], list[str]]:
        """Détecte le gestionnaire de paquets et retourne les dépendances."""
        os_info = read_os_release()
        os_id = os_info.get("ID", "").lower()
        os_like = os_info.get("ID_LIKE", "").lower()

        # Définir les paquets pour chaque gestionnaire
        deps = {
            "apt": ["git", "python3", "python3-venv", "python3-pip", "make", "curl", "tar", "build-essential", "sshpass", "ipmitool"],
            "dnf": ["git", "python3", "python3-pip", "make", "curl", "tar", "gcc", "gcc-c++", "sshpass", "ipmitool"],
            "pacman": ["git", "python", "python-pip", "make", "curl", "tar", "base-devel", "sshpass", "ipmitool"],
        }

        # Détecter le gestionnaire de paquets
        if any(dist in ("debian", "ubuntu", "raspbian", "armbian") for dist in [os_id, os_like]):
            pm = "apt"
            check_cmd = ["dpkg", "-s"]
        elif any(dist in ("fedora", "centos", "rhel") for dist in [os_id, os_like]):
            pm = "dnf"
            check_cmd = ["rpm", "-q"]
        elif "arch" in os_id or "arch" in os_like:
            pm = "pacman"
            check_cmd = ["pacman", "-Q"]
        else:
            return None, list(set(p for backend_deps in deps.values() for p in backend_deps)), []

        required = deps[pm]
        missing = [pkg for pkg in required if subprocess.run([*check_cmd, pkg], capture_output=True).returncode != 0]
        return pm, required, missing

    def install_system_dependencies(self, package_manager: str, packages: list[str]) -> bool:
        """Installe les dépendances système en utilisant le gestionnaire de paquets détecté."""
        commands = {
            "apt": f"sudo apt install -y {' '.join(packages)}",
            "dnf": f"sudo dnf install -y {' '.join(packages)}",
            "pacman": f"sudo pacman -S --noconfirm {' '.join(packages)}",
        }
        install_command = commands.get(package_manager)
        if not install_command:
            print(f"Gestionnaire de paquets '{package_manager}' non supporté.")
            return False

        try:
            subprocess.run(install_command, shell=True, check=True)
            return True
        except FileNotFoundError:
            print(f"\nErreur: Impossible de lancer la commande d'installation via '{package_manager}'.")
            print("Vérifiez que 'sudo' et le gestionnaire de paquets sont installés et accessibles.")
            return False
        except subprocess.CalledProcessError as e:
            print(f"\nL'installation a échoué (code de sortie {e.returncode}).")
            print("Veuillez consulter les messages d'erreur ci-dessus.")
            return False

    def get_python_dependencies(self) -> tuple[list[str], list[str]]:
        """Vérifie les dépendances Python depuis requirements.txt."""
        req_file = self.base_dir / "requirements.txt"
        if not req_file.is_file():
            return [], []

        missing = []
        required = []
        with req_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Extrait le nom du paquet (ex: "pyserial>=3.5" -> "pyserial")
                pkg_name = line.split("==")[0].split(">=")[0].split("<=")[0].split("!=")[0].strip()
                required.append(pkg_name)
                try:
                    version(pkg_name)
                except PackageNotFoundError:
                    missing.append(pkg_name)
        return required, missing

    def install_python_dependencies(self) -> None:
        """Installe les dépendances depuis requirements.txt."""
        req_file = self.base_dir / "requirements.txt"
        if not req_file.is_file():
            print("Fichier requirements.txt introuvable.")
            return

        command = [sys.executable, "-m", "pip", "install", "-r", str(req_file)]
        try:
            subprocess.run(
                command, check=True, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
        except FileNotFoundError as e:
            raise PipInstallError("La commande 'pip' est introuvable. Assurez-vous que Python et pip sont correctement installés.") from e
        except subprocess.CalledProcessError as e:
            error_message = (
                f"La commande `{' '.join(command)}` a échoué (code {e.returncode}).\n"
                f"--- STDOUT ---\n{e.stdout}\n"
                f"--- STDERR ---\n{e.stderr}"
            )
            raise PipInstallError(error_message) from e

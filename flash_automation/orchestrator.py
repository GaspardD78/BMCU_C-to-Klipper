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


from .build_manager import BuildManager
from .flash_manager import FlashManager


class Orchestrator:
    """Point d'entrée pour les opérations de haut niveau."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def run_build(self) -> bool:
        """Lance le script de build et retourne le succès."""
        try:
            manager = BuildManager(self.base_dir)
            manager.compile_firmware()
        except (subprocess.CalledProcessError, FileNotFoundError) as err:
            print(f"La compilation a échoué : {err}")
            return False
        return True

    def run_flash(self, firmware_path: Path, serial_device: str) -> bool:
        """Lance le flash et retourne le succès."""
        try:
            manager = FlashManager(self.base_dir)
            manager.flash("serial", firmware_path, serial_device)
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as err:
            print(f"Le flashage a échoué : {err}")
            return False
        return True

    def get_system_dependencies(self) -> tuple[list[str], list[str]]:
        """Retourne les paquets système requis et ceux qui sont manquants."""
        os_info = read_os_release()
        os_id = os_info.get("ID", "").lower()
        os_like = os_info.get("ID_LIKE", "").lower()

        if not any(dist in ("debian", "ubuntu", "raspbian", "armbian") for dist in [os_id, os_like]):
            return [], []

        base_packages = ["git", "python3", "python3-venv", "python3-pip", "make", "curl", "tar", "build-essential", "sshpass", "ipmitool"]

        missing_packages = []
        for pkg in base_packages:
            status = subprocess.run(["dpkg", "-s", pkg], capture_output=True, text=True).returncode
            if status != 0:
                missing_packages.append(pkg)

        return base_packages, missing_packages

    def install_system_dependencies(self, packages: list[str]) -> bool:
        """Installe les dépendances système via apt."""
        install_command = f"sudo apt install -y {' '.join(packages)}"
        try:
            process = subprocess.run(install_command, shell=True, check=True)
            return process.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"Erreur lors de l'installation des dépendances : {e}")
            return False

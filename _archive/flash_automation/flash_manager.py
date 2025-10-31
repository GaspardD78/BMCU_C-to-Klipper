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

"""Gère le flashage du firmware Klipper sur le BMCU-C.

Ce module remplace la logique du script flash_automation.sh par une approche
native en Python, offrant une meilleure intégration, testabilité et
maintenance.
"""

from __future__ import annotations

import glob
import subprocess
from pathlib import Path

class FlashManagerError(Exception):
    """Exception spécifique pour les erreurs de flashage."""


class FlashManager:
    """Orchestre le flashage du firmware Klipper."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def _run_command(self, command: list[str]) -> None:
        """Exécute une commande et lève une exception détaillée en cas d'échec."""
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as e:
            raise FlashManagerError(f"La commande '{command[0]}' est introuvable. Est-elle installée et dans le PATH ?") from e
        except subprocess.CalledProcessError as e:
            error_message = (
                f"La commande `{' '.join(command)}` a échoué (code {e.returncode}).\n"
                f"--- STDOUT ---\n{e.stdout}\n"
                f"--- STDERR ---\n{e.stderr}"
            )
            raise FlashManagerError(error_message) from e

    def detect_serial_devices(self) -> list[str]:
        """Détecte les périphériques série disponibles."""
        devices = []
        patterns = [
            "/dev/serial/by-id/*",
            "/dev/ttyUSB*",
            "/dev/ttyACM*",
            "/dev/ttyAMA*",
            "/dev/ttyS*",
            "/dev/ttyCH*",
        ]
        for pattern in patterns:
            devices.extend(glob.glob(pattern))
        return devices

    def flash(self, method: str, firmware_path: Path, device: str | None = None) -> None:
        """Lance le processus de flashage en utilisant la méthode spécifiée."""
        if method == "serial":
            self.flash_serial(firmware_path, device)
        else:
            raise NotImplementedError(f"La méthode de flash '{method}' n'est pas encore implémentée.")

    def flash_serial(self, firmware_path: Path, device: str | None) -> None:
        """Flashe le firmware en utilisant la méthode série (flash_usb.py)."""
        if not device:
            raise FlashManagerError("Un périphérique série est requis pour la méthode de flash série.")

        # Le script flash_usb.py est un artefact généré par la compilation de Klipper.
        flash_script = self.base_dir / ".cache/klipper/lib/flash_usb.py"
        if not flash_script.exists():
            raise FlashManagerError(
                f"Le script de flash '{flash_script}' est introuvable.\n"
                "Ce fichier est généré lors de la compilation de Klipper. "
                "Veuillez compiler le firmware avant de tenter de flasher."
            )

        print(f"Flashage de '{firmware_path.name}' sur '{device}'...")
        command = ["python3", str(flash_script), "-d", device, "-f", str(firmware_path)]
        self._run_command(command)

if __name__ == "__main__":
    manager = FlashManager(Path(__file__).resolve().parent)
    print("Périphériques série détectés :", manager.detect_serial_devices())

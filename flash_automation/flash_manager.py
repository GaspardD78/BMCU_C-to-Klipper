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

class FlashManager:
    """Orchestre le flashage du firmware Klipper."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

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
            raise ValueError("Un périphérique série est requis pour la méthode de flash série.")

        flash_script = self.base_dir / ".cache/scripts/flash_usb.py"
        if not flash_script.exists():
            raise FileNotFoundError(f"Le script de flash {flash_script} est introuvable. Veuillez d'abord compiler le firmware.")

        print(f"Flashage de {firmware_path} sur {device} en utilisant {flash_script}...")
        subprocess.run(
            ["python3", str(flash_script), "-d", device, "-f", str(firmware_path)],
            check=True
        )

if __name__ == "__main__":
    manager = FlashManager(Path(__file__).resolve().parent)
    print("Périphériques série détectés :", manager.detect_serial_devices())

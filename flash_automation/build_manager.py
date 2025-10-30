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

"""Gère la compilation du firmware Klipper pour le BMCU-C.

Ce module remplace la logique du script build.sh par une approche
native en Python, offrant une meilleure intégration, testabilité et
maintenance.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

class BuildManager:
    """Orchestre la compilation du firmware Klipper."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.cache_root = self.base_dir / ".cache"
        self.klipper_dir = self.cache_root / "klipper"
        self.klipper_repo_url = "https://github.com/Klipper3d/klipper.git"
        self.klipper_ref = "master"

    def ensure_klipper_repo(self) -> None:
        """S'assure que le dépôt Klipper est cloné et à jour."""
        if not self.klipper_dir.exists() or not (self.klipper_dir / ".git").exists():
            print("Clonage du dépôt Klipper...")
            subprocess.run(
                [
                    "git", "clone", "--depth", "1", "--branch", self.klipper_ref,
                    self.klipper_repo_url, str(self.klipper_dir)
                ],
                check=True
            )
        else:
            print("Mise à jour du dépôt Klipper...")
            subprocess.run(["git", "-C", str(self.klipper_dir), "pull"], check=True)

    def compile_firmware(self) -> Path:
        """Compile le firmware et retourne le chemin vers le binaire."""
        print("Compilation du firmware Klipper...")
        self.ensure_klipper_repo()

        # Copie de la configuration
        config_src = self.base_dir / "klipper.config"
        config_dest = self.klipper_dir / ".config"
        print(f"Copie de {config_src} vers {config_dest}")
        shutil.copy(config_src, config_dest)

        # Lancement de la compilation
        subprocess.run(["make", "clean"], cwd=self.klipper_dir, check=True)
        subprocess.run(["make"], cwd=self.klipper_dir, check=True)

        firmware_path = self.klipper_dir / "out/klipper.bin"
        if not firmware_path.exists():
            raise FileNotFoundError("Le binaire du firmware n'a pas été trouvé après la compilation.")

        print(f"Firmware compilé avec succès : {firmware_path}")
        return firmware_path

if __name__ == "__main__":
    import shutil

    manager = BuildManager(Path(__file__).resolve().parent)
    manager.compile_firmware()

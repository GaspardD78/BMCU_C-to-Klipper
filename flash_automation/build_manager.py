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

import json
import shutil
import subprocess
from pathlib import Path

class BuildManagerError(Exception):
    """Exception spécifique pour les erreurs de compilation."""

class BuildManager:
    """Orchestre la compilation du firmware Klipper."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.cache_root = self.base_dir / ".cache"
        self.klipper_dir = self.cache_root / "klipper"
        self._load_config()

    def _load_config(self) -> None:
        """Charge la configuration depuis le fichier config.json."""
        config_path = self.base_dir / "config.json"
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            self.klipper_repo_url = data["klipper"]["repository_url"]
            self.klipper_ref = data["klipper"]["git_ref"]
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            raise BuildManagerError(
                f"Le fichier de configuration '{config_path}' est manquant, invalide ou incomplet."
            ) from e

    def _run_command(self, command: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
        """Exécute une commande et lève une exception détaillée en cas d'échec."""
        try:
            return subprocess.run(
                command,
                cwd=cwd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as e:
            raise BuildManagerError(f"La commande '{command[0]}' est introuvable. Est-elle installée et dans le PATH ?") from e
        except subprocess.CalledProcessError as e:
            error_message = (
                f"La commande `{' '.join(command)}` a échoué (code {e.returncode}).\n"
                f"--- STDOUT ---\n{e.stdout}\n"
                f"--- STDERR ---\n{e.stderr}"
            )
            raise BuildManagerError(error_message) from e

    def ensure_klipper_repo(self) -> None:
        """S'assure que le dépôt Klipper est cloné et à la bonne version."""
        if not self.klipper_dir.exists() or not (self.klipper_dir / ".git").exists():
            print(f"Clonage du dépôt Klipper à la version {self.klipper_ref}...")
            # Cloner directement le tag désiré
            git_clone_cmd = [
                "git", "clone", "--branch", self.klipper_ref,
                self.klipper_repo_url, str(self.klipper_dir)
            ]
            self._run_command(git_clone_cmd, cwd=self.base_dir)
        else:
            print(f"Vérification de la version du dépôt Klipper (cible: {self.klipper_ref})...")
            self._run_command(["git", "fetch", "origin", "--tags"], cwd=self.klipper_dir)
            self._run_command(["git", "checkout", self.klipper_ref], cwd=self.klipper_dir)

    def _run_interactive_command(self, command: list[str], *, cwd: Path) -> None:
        """Exécute une commande interactive."""
        try:
            subprocess.run(command, cwd=cwd, check=True)
        except FileNotFoundError as e:
            raise BuildManagerError(f"La commande '{command[0]}' est introuvable.") from e
        except subprocess.CalledProcessError as e:
            raise BuildManagerError(f"La commande `{' '.join(command)}` a échoué.") from e

    def launch_menuconfig(self) -> bool:
        """Lance `menuconfig` et détecte si la configuration a été sauvegardée.

        Returns:
            True si la configuration a été modifiée, False sinon.
        """
        self.ensure_klipper_repo()
        config_file = self.klipper_dir / ".config"

        # Obtenir l'état initial du fichier de configuration
        try:
            initial_mtime = config_file.stat().st_mtime
        except FileNotFoundError:
            initial_mtime = None

        print("Lancement de l'interface de configuration de Klipper (menuconfig)...")
        self._run_interactive_command(["make", "menuconfig"], cwd=self.klipper_dir)

        # Obtenir l'état final et comparer
        try:
            final_mtime = config_file.stat().st_mtime
        except FileNotFoundError:
            # Si le fichier n'existe toujours pas, aucune sauvegarde n'a eu lieu.
            return False

        if initial_mtime is None:
            # Le fichier a été créé, donc il y a eu une sauvegarde.
            return True

        # Comparer le temps de modification pour voir s'il y a eu un changement.
        return final_mtime > initial_mtime

    def save_config(self, name: str) -> Path:
        """Sauvegarde la configuration actuelle sous un nom donné."""
        config_src = self.klipper_dir / ".config"
        if not config_src.exists():
            raise BuildManagerError("Aucun fichier .config à sauvegarder. Veuillez d'abord lancer la configuration.")

        config_dir = self.base_dir / "configs"
        config_dir.mkdir(exist_ok=True)
        config_dest = config_dir / f"{name}.config"

        shutil.copy(config_src, config_dest)
        print(f"Configuration sauvegardée sous : {config_dest}")
        return config_dest

    def load_config(self, name: str) -> None:
        """Charge une configuration sauvegardée."""
        config_src = self.base_dir / f"configs/{name}.config"
        if not config_src.exists():
            raise BuildManagerError(f"La configuration '{name}' est introuvable.")

        config_dest = self.klipper_dir / ".config"
        self.ensure_klipper_repo()
        shutil.copy(config_src, config_dest)
        print(f"Configuration '{name}' chargée.")

    def compile_firmware(self, use_default_config: bool = True) -> Path:
        """Compile le firmware et retourne le chemin vers le binaire."""
        print("Compilation du firmware Klipper...")
        self.ensure_klipper_repo()

        if use_default_config:
            config_src = self.base_dir / "klipper.config"
            config_dest = self.klipper_dir / ".config"
            if not config_src.exists():
                raise BuildManagerError(f"Le fichier de configuration par défaut '{config_src}' est introuvable.")
            print(f"Utilisation de la configuration par défaut : {config_src}")
            shutil.copy(config_src, config_dest)

        print("Nettoyage de l'environnement de compilation...")
        out_dir = self.klipper_dir / "out"
        if out_dir.exists():
            shutil.rmtree(out_dir)

        print("Préparation de la configuration Klipper...")
        self._run_command(["make", "olddefconfig"], cwd=self.klipper_dir)

        print("Lancement de la compilation...")
        make_process = self._run_command(["make"], cwd=self.klipper_dir)

        firmware_path = self.klipper_dir / "out/klipper.bin"
        if not firmware_path.exists():
            error_details = (
                "Le binaire du firmware n'a pas été trouvé après la compilation, "
                "même si la commande 'make' s'est terminée sans erreur.\n"
                "Ceci indique un problème probable avec la chaîne de compilation (cross-compiler).\n\n"
                f"--- STDOUT ---\n{make_process.stdout}\n"
                f"--- STDERR ---\n{make_process.stderr}"
            )
            raise BuildManagerError(error_details)

        print(f"Firmware compilé avec succès : {firmware_path}")
        return firmware_path

if __name__ == "__main__":
    import shutil

    manager = BuildManager(Path(__file__).resolve().parent)
    manager.compile_firmware()

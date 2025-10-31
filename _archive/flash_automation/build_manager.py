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
import os
import shutil
import subprocess
import tarfile
import urllib.request
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
        self.toolchain_dir = self.cache_root / self.toolchain_subdirectory

    def _load_config(self) -> None:
        """Charge la configuration depuis le fichier config.json."""
        config_path = self.base_dir / "config.json"
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            self.klipper_repo_url = data["klipper"]["repository_url"]
            self.klipper_ref = data["klipper"]["git_ref"]
            self.toolchain_url = data["toolchain"]["url"]
            self.toolchain_subdirectory = data["toolchain"]["subdirectory"]
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            raise BuildManagerError(
                f"Le fichier de configuration '{config_path}' est manquant, invalide ou incomplet."
            ) from e

    def _run_command(self, command: list[str], *, cwd: Path, use_toolchain: bool = False) -> subprocess.CompletedProcess:
        """Exécute une commande et lève une exception détaillée en cas d'échec."""
        env = os.environ.copy()
        if use_toolchain:
            toolchain_bin = self.toolchain_dir / "bin"
            if not toolchain_bin.exists():
                raise BuildManagerError(f"Le répertoire bin de la toolchain '{toolchain_bin}' est introuvable.")
            env["PATH"] = f"{toolchain_bin}{os.pathsep}{env['PATH']}"

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
                env=env,
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

    def ensure_toolchain(self) -> None:
        """S'assure que la toolchain RISC-V est téléchargée et extraite."""
        if self.toolchain_dir.exists():
            print("La toolchain RISC-V est déjà présente.")
            return

        print("Téléchargement de la toolchain RISC-V...")
        self.cache_root.mkdir(exist_ok=True)
        archive_path = self.cache_root / "riscv-toolchain.tar.gz"

        try:
            with urllib.request.urlopen(self.toolchain_url) as response, open(archive_path, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
        except Exception as e:
            raise BuildManagerError(f"Échec du téléchargement de la toolchain : {e}") from e

        print(f"Extraction de l'archive de la toolchain vers {self.toolchain_dir}...")
        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                # Extraire dans un répertoire temporaire d'abord pour pouvoir le renommer
                temp_extract_dir = self.cache_root / "temp_toolchain_extract"
                tar.extractall(path=temp_extract_dir)

                # Le contenu est souvent dans un sous-répertoire, trouvons-le
                extracted_dirs = [d for d in temp_extract_dir.iterdir() if d.is_dir()]
                if not extracted_dirs:
                    raise BuildManagerError("L'archive de la toolchain est vide ou a un format inattendu.")

                # Renommer le répertoire extrait avec le nom de destination final
                shutil.move(str(extracted_dirs[0]), str(self.toolchain_dir))
                shutil.rmtree(temp_extract_dir)

        except tarfile.TarError as e:
            raise BuildManagerError(f"Échec de l'extraction de l'archive de la toolchain : {e}") from e
        finally:
            # Nettoyer l'archive téléchargée
            if archive_path.exists():
                archive_path.unlink()

        print("Toolchain installée avec succès.")

    def _run_interactive_command(self, command: list[str], *, cwd: Path, use_toolchain: bool = False) -> None:
        """Exécute une commande interactive."""
        env = os.environ.copy()
        if use_toolchain:
            toolchain_bin = self.toolchain_dir / "bin"
            if not toolchain_bin.exists():
                raise BuildManagerError(f"Le répertoire bin de la toolchain '{toolchain_bin}' est introuvable.")
            env["PATH"] = f"{toolchain_bin}{os.pathsep}{env['PATH']}"
        try:
            subprocess.run(command, cwd=cwd, check=True, env=env)
        except FileNotFoundError as e:
            raise BuildManagerError(f"La commande '{command[0]}' est introuvable.") from e
        except subprocess.CalledProcessError as e:
            raise BuildManagerError(f"La commande `{' '.join(command)}` a échoué.") from e

    def _apply_klipper_overrides(self) -> None:
        """Applique les fichiers et patchs spécifiques au projet sur le dépôt Klipper."""
        print("Application des surcharges Klipper pour le CH32V20X...")
        overrides_src = self.base_dir / "klipper_overrides"
        if not overrides_src.exists():
            print("Avertissement : Le répertoire des surcharges Klipper n'a pas été trouvé.")
            return

        # Copier les fichiers sources (écrase les fichiers existants)
        shutil.copytree(overrides_src, self.klipper_dir, dirs_exist_ok=True)

        # Appliquer les patchs nécessaires
        patches = ["Makefile.patch", "src/Kconfig.patch"]
        for patch_name in patches:
            patch_path = overrides_src / patch_name
            if patch_path.exists():
                print(f"Application du patch : {patch_name}...")
                try:
                    self._run_command(["git", "apply", str(patch_path)], cwd=self.klipper_dir)
                except BuildManagerError as e:
                    # Ignorer l'erreur si le patch a déjà été appliqué
                    if "patch has already been applied" in e.args[0]:
                        print(f"Le patch {patch_name} a déjà été appliqué.")
                    else:
                        raise
            else:
                print(f"Avertissement : Patch '{patch_path}' non trouvé.")

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
        self._run_interactive_command(["make", "menuconfig"], cwd=self.klipper_dir, use_toolchain=True)

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
        self.ensure_toolchain()
        self._apply_klipper_overrides()

        if use_default_config:
            config_src = self.base_dir / "klipper.config"
            config_dest = self.klipper_dir / ".config"
            if not config_src.exists():
                raise BuildManagerError(f"Le fichier de configuration par défaut '{config_src}' est introuvable.")
            print(f"Utilisation de la configuration par défaut : {config_src}")
            shutil.copy(config_src, config_dest)

        print("Nettoyage de l'environnement de compilation...")
        self._run_command(["make", "clean"], cwd=self.klipper_dir, use_toolchain=True)
        # Forcer la suppression du répertoire 'out' au cas où 'make clean'
        # ne serait pas suffisant, en ignorant les erreurs de permission.
        out_dir = self.klipper_dir / "out"
        if out_dir.exists():
            shutil.rmtree(out_dir, ignore_errors=True)

        print("Préparation de la configuration Klipper...")
        self._run_command(["make", "olddefconfig"], cwd=self.klipper_dir, use_toolchain=True)

        print("Lancement de la compilation...")
        make_process = self._run_command(["make"], cwd=self.klipper_dir, use_toolchain=True)

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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MatrixFlow - Étape 2 : Compilation du firmware.

Ce script utilise l'environnement préparé par l'étape 1 pour compiler
le firmware Klipper pour la carte BMCU-C.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

class BuildError(Exception):
    """Exception personnalisée pour les erreurs de cette étape."""
    pass

class BuildManager:
    """Gère la compilation du firmware Klipper."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.cache_dir = self.base_dir / ".cache"
        self.config_path = self.base_dir / "config.json"
        self.klipper_dir = self.cache_dir / "klipper"
        self.overrides_dir = self.base_dir / "klipper_overrides"
        self.default_kconfig_path = self.base_dir / "klipper.config"
        self._load_config()
        self.toolchain_dir = self.cache_dir / self.config["toolchain"]["subdirectory"]
        self.firmware_path = self.klipper_dir / "out/klipper.bin"

    def _load_config(self):
        """Charge la configuration depuis config.json."""
        try:
            with self.config_path.open("r", encoding="utf-8") as f:
                self.config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise BuildError(f"Le fichier de configuration '{self.config_path}' est manquant ou invalide.") from e

    def _run_command(self, command: list[str], cwd: Path):
        """Exécute une commande avec la toolchain et lève une exception en cas d'échec."""
        env = os.environ.copy()
        toolchain_bin = self.toolchain_dir.resolve() / "bin"
        if not toolchain_bin.is_dir():
            raise BuildError(f"Le répertoire bin de la toolchain '{toolchain_bin}' est introuvable. Avez-vous exécuté l'étape 1 ?")
        env["PATH"] = f"{str(toolchain_bin)}{os.pathsep}{env['PATH']}"

        try:
            process = subprocess.run(
                command,
                cwd=cwd,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            return process
        except FileNotFoundError as e:
            raise BuildError(f"La commande '{command[0]}' est introuvable. Est-elle installée ?") from e
        except subprocess.CalledProcessError as e:
            error_message = (
                f"La commande `{' '.join(command)}` a échoué (code {e.returncode}).\n"
                f"--- STDOUT ---\n{e.stdout}\n"
                f"--- STDERR ---\n{e.stderr}"
            )
            raise BuildError(error_message) from e

    def _apply_overrides(self):
        """Applique les fichiers et patchs spécifiques au projet."""
        print("Application des surcharges pour le CH32V20X...")
        if not self.overrides_dir.is_dir():
            print("Avertissement : Le répertoire des surcharges n'a pas été trouvé.")
            return

        # Copie des fichiers sources (écrase les fichiers existants)
        shutil.copytree(self.overrides_dir, self.klipper_dir, dirs_exist_ok=True)

    def run(self):
        """Exécute toutes les étapes de la compilation."""
        print("--- Étape 2: Compilation du firmware ---")

        if not self.klipper_dir.is_dir():
            raise BuildError("Le répertoire de Klipper est introuvable. Avez-vous exécuté l'étape 1 ?")

        self._apply_overrides()

        print(f"Utilisation de la configuration : {self.default_kconfig_path}")
        if not self.default_kconfig_path.is_file():
            raise BuildError(f"Le fichier de configuration '{self.default_kconfig_path}' est introuvable.")
        shutil.copy(self.default_kconfig_path, self.klipper_dir / ".config")

        print("Préparation de la configuration Klipper...")
        self._run_command(["make", "olddefconfig"], cwd=self.klipper_dir)

        print("Nettoyage de l'environnement de compilation...")
        self._run_command(["make", "clean"], cwd=self.klipper_dir)

        print("Lancement de la compilation...")
        make_process = self._run_command(["make"], cwd=self.klipper_dir)

        if not self.firmware_path.is_file():
            error_details = (
                "Le binaire du firmware n'a pas été trouvé après la compilation.\n"
                f"--- STDOUT ---\n{make_process.stdout}\n"
                f"--- STDERR ---\n{make_process.stderr}"
            )
            raise BuildError(error_details)

        print("-----------------------------------------")
        print(f"Firmware compilé avec succès : {self.firmware_path}")
        return self.firmware_path

def main():
    """Point d'entrée du script."""
    base_dir = Path(__file__).parent.resolve()
    try:
        manager = BuildManager(base_dir)
        manager.run()
    except BuildError as e:
        print(f"\nERREUR : {e}", file=os.sys.stderr)
        exit(1)

if __name__ == "__main__":
    main()

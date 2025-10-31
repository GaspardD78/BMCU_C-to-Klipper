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
import threading
import itertools
import time
from pathlib import Path
import ui

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

    def _run_command_with_spinner(self, command: list[str], cwd: Path, title: str):
        """Exécute une commande avec un spinner et lève une exception en cas d'échec."""
        env = os.environ.copy()
        toolchain_bin = self.toolchain_dir.resolve() / "bin"
        if not toolchain_bin.is_dir():
            raise BuildError(f"Le répertoire bin de la toolchain '{toolchain_bin}' est introuvable. Avez-vous exécuté l'étape 1 ?")
        env["PATH"] = f"{str(toolchain_bin)}{os.pathsep}{env['PATH']}"

        spinner = itertools.cycle(['-', '/', '|', '\\'])
        done = threading.Event()

        process = None

        def spin():
            while not done.is_set():
                sys.stdout.write(f'\r{title} {next(spinner)}')
                sys.stdout.flush()
                time.sleep(0.1)
            sys.stdout.write(f'\r{" " * (len(title) + 2)}\r')
            sys.stdout.flush()

        spinner_thread = threading.Thread(target=spin)
        spinner_thread.start()

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
        finally:
            done.set()
            spinner_thread.join()


    def _apply_overrides(self):
        """Applique les fichiers et patchs spécifiques au projet."""
        ui.print_info("Application des surcharges pour le CH32V20X...")
        if not self.overrides_dir.is_dir():
            ui.print_warning("Le répertoire des surcharges n'a pas été trouvé.")
            return

        shutil.copytree(self.overrides_dir, self.klipper_dir, dirs_exist_ok=True)
        ui.print_success("Surcharges appliquées.")

    def run(self):
        """Exécute toutes les étapes de la compilation."""
        if not self.klipper_dir.is_dir():
            raise BuildError("Le répertoire de Klipper est introuvable. Avez-vous exécuté l'étape 1 ?")

        self._apply_overrides()

        ui.print_info(f"Utilisation de la configuration : {self.default_kconfig_path}")
        if not self.default_kconfig_path.is_file():
            raise BuildError(f"Le fichier de configuration '{self.default_kconfig_path}' est introuvable.")
        shutil.copy(self.default_kconfig_path, self.klipper_dir / ".config")

        self._run_command_with_spinner(["make", "olddefconfig"], cwd=self.klipper_dir, title="Préparation de la configuration Klipper...")
        ui.print_success("Configuration Klipper préparée.")

        self._run_command_with_spinner(["make", "clean"], cwd=self.klipper_dir, title="Nettoyage de l'environnement de compilation...")
        ui.print_success("Environnement de compilation nettoyé.")

        make_process = self._run_command_with_spinner(["make"], cwd=self.klipper_dir, title="Compilation du firmware...")

        if not self.firmware_path.is_file():
            error_details = (
                "Le binaire du firmware n'a pas été trouvé après la compilation.\n"
                f"--- STDOUT ---\n{make_process.stdout}\n"
                f"--- STDERR ---\n{make_process.stderr}"
            )
            raise BuildError(error_details)

        ui.print_success(f"Firmware compilé avec succès : {self.firmware_path}")
        return self.firmware_path

def main():
    """Point d'entrée du script."""
    base_dir = Path(__file__).parent.resolve()
    try:
        manager = BuildManager(base_dir)
        manager.run()
    except BuildError as e:
        ui.print_error(str(e))
        exit(1)

if __name__ == "__main__":
    main()

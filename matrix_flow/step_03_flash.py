#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MatrixFlow - Étape 3 : Flashage du firmware.

Ce script prend le firmware compilé et le téléverse sur la carte BMCU-C.
"""

import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

class FlashError(Exception):
    """Exception personnalisée pour les erreurs de cette étape."""
    pass

class FlashManager:
    """Gère le flashage du firmware."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.klipper_dir = self.base_dir / ".cache/klipper"
        self.firmware_path = self.klipper_dir / "out/klipper.bin"

    def _run_command(self, command: list[str], ignore_errors: bool = False):
        """Exécute une commande et gère les erreurs."""
        env = os.environ.copy()
        bin_dir = self.base_dir / "bin"
        env["PATH"] = f"{str(bin_dir.resolve())}{os.pathsep}{env['PATH']}"
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            if not ignore_errors:
                error_message = (
                    f"La commande `{' '.join(command)}` a échoué.\n"
                    f"--- STDOUT ---\n{e.stdout}\n"
                    f"--- STDERR ---\n{e.stderr}"
                )
                raise FlashError(error_message) from e
            else:
                print(f"Avertissement : La commande `{' '.join(command)}` a échoué, mais l'erreur est ignorée.")

    def _manage_klipper_service(self, action: str):
        """Démarre ou arrête le service Klipper."""
        if not shutil.which("sudo"):
            print("Avertissement : 'sudo' n'est pas installé. Impossible de gérer le service Klipper.")
            return

        print(f"{action.capitalize()} du service Klipper...")
        self._run_command(["sudo", "systemctl", action, "klipper.service"], ignore_errors=True)

    def detect_serial_devices(self) -> list[str]:
        """Détecte les périphériques série potentiels."""
        patterns = ["/dev/serial/by-id/*", "/dev/ttyUSB*", "/dev/ttyACM*"]
        devices = []
        for pattern in patterns:
            devices.extend(glob.glob(pattern))
        return devices

    def run(self, serial_device: str | None):
        """Exécute toutes les étapes du flashage."""
        print("--- Étape 3: Flashage du firmware ---")

        if not self.firmware_path.is_file():
            raise FlashError(f"Le firmware '{self.firmware_path}' est introuvable. Avez-vous exécuté l'étape 2 ?")

        bin_dir = self.base_dir / "bin"
        env_path = f"{str(bin_dir.resolve())}{os.pathsep}{os.environ['PATH']}"
        if not shutil.which("wchisp", path=env_path):
            raise FlashError("L'outil 'wchisp' est introuvable. Assurez-vous qu'il est installé et dans le PATH.")

        if not serial_device:
            print("Aucun port série spécifié. Tentative de détection automatique...")
            available_devices = self.detect_serial_devices()
            if not available_devices:
                raise FlashError("Aucun port série détecté. Veuillez en spécifier un avec l'argument --device.")
            serial_device = available_devices[0]
            print(f"Port série détecté : {serial_device}")

        self._manage_klipper_service("stop")
        try:
            print(f"Flashage de '{self.firmware_path.name}' sur '{serial_device}' avec wchisp...")
            command = ["wchisp", "--serial", "--port", serial_device, "flash", str(self.firmware_path)]
            self._run_command(command)
            print("Flashage réussi !")
        finally:
            self._manage_klipper_service("start")

        print("------------------------------------")

def main():
    """Point d'entrée du script."""
    import argparse
    parser = argparse.ArgumentParser(description="Flashe le firmware Klipper sur la BMCU-C.")
    parser.add_argument("-d", "--device", help="Chemin vers le port série (ex: /dev/ttyUSB0).")
    args = parser.parse_args()

    base_dir = Path(__file__).parent.resolve()
    try:
        manager = FlashManager(base_dir)
        manager.run(args.device)
    except FlashError as e:
        print(f"\nERREUR : {e}", file=sys.stderr)
        exit(1)

if __name__ == "__main__":
    main()

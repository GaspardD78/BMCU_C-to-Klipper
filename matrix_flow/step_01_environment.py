#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MatrixFlow - Étape 1 : Préparation de l'environnement.

Ce script s'assure que toutes les dépendances et les sources nécessaires
sont en place pour les étapes de compilation et de flashage.
"""

import json
import os
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

class EnvironmentError(Exception):
    """Exception personnalisée pour les erreurs de cette étape."""
    pass

class EnvironmentManager:
    """Gère la préparation de l'environnement."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.cache_dir = self.base_dir / ".cache"
        self.config_path = self.base_dir / "config.json"
        self.klipper_dir = self.cache_dir / "klipper"
        self._load_config()
        self.toolchain_dir = self.cache_dir / self.config["toolchain"]["subdirectory"]

    def _load_config(self):
        """Charge la configuration depuis config.json."""
        try:
            with self.config_path.open("r", encoding="utf-8") as f:
                self.config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise EnvironmentError(f"Le fichier de configuration '{self.config_path}' est manquant ou invalide.") from e

    def _run_command(self, command: list[str], cwd: Path):
        """Exécute une commande et lève une exception en cas d'échec."""
        try:
            subprocess.run(
                command,
                cwd=cwd,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as e:
            raise EnvironmentError(f"La commande '{command[0]}' est introuvable. Est-elle installée ?") from e
        except subprocess.CalledProcessError as e:
            error_message = (
                f"La commande `{' '.join(command)}` a échoué (code {e.returncode}).\n"
                f"--- STDOUT ---\n{e.stdout}\n"
                f"--- STDERR ---\n{e.stderr}"
            )
            raise EnvironmentError(error_message) from e

    def check_system_dependencies(self):
        """Vérifie la présence des dépendances système de base."""
        print("Vérification des dépendances système...")
        dependencies = ["git", "make", "python3"]
        missing = [dep for dep in dependencies if not shutil.which(dep)]
        if missing:
            raise EnvironmentError(f"Dépendances système manquantes : {', '.join(missing)}. Veuillez les installer.")
        print("Dépendances système OK.")

    def ensure_klipper_repo(self):
        """S'assure que le dépôt Klipper est cloné et à la bonne version."""
        klipper_config = self.config["klipper"]
        repo_url = klipper_config["repository_url"]
        git_ref = klipper_config["git_ref"]

        if not self.klipper_dir.is_dir() or not (self.klipper_dir / ".git").is_dir():
            print(f"Clonage de Klipper (version {git_ref})...")
            self.cache_dir.mkdir(exist_ok=True)
            self._run_command(["git", "clone", "--branch", git_ref, repo_url, str(self.klipper_dir)], cwd=self.cache_dir)
        else:
            print(f"Vérification du dépôt Klipper (cible: {git_ref})...")
            self._run_command(["git", "fetch", "origin", "--tags"], cwd=self.klipper_dir)
            self._run_command(["git", "checkout", git_ref], cwd=self.klipper_dir)
        print("Dépôt Klipper OK.")

    def ensure_toolchain(self):
        """S'assure que la toolchain RISC-V est téléchargée et extraite."""
        if self.toolchain_dir.is_dir():
            print("La toolchain RISC-V est déjà présente.")
            return

        print("Téléchargement de la toolchain RISC-V...")
        self.cache_dir.mkdir(exist_ok=True)
        archive_path = self.cache_dir / "riscv-toolchain.tar.gz"
        toolchain_url = self.config["toolchain"]["url"]

        try:
            with urllib.request.urlopen(toolchain_url) as response, open(archive_path, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
        except Exception as e:
            raise EnvironmentError(f"Échec du téléchargement de la toolchain : {e}") from e

        print(f"Extraction de l'archive vers {self.toolchain_dir}...")
        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                temp_extract_dir = self.cache_dir / "temp_toolchain_extract"
                tar.extractall(path=temp_extract_dir)

                extracted_dirs = list(temp_extract_dir.iterdir())
                if not extracted_dirs:
                    raise EnvironmentError("L'archive de la toolchain est vide.")

                shutil.move(str(extracted_dirs[0]), str(self.toolchain_dir))
                shutil.rmtree(temp_extract_dir)

        except tarfile.TarError as e:
            raise EnvironmentError(f"Échec de l'extraction de l'archive de la toolchain : {e}") from e
        finally:
            if archive_path.exists():
                archive_path.unlink()

        print("Toolchain RISC-V OK.")

    def run(self):
        """Exécute toutes les étapes de préparation."""
        print("--- Étape 1: Préparation de l'environnement ---")
        self.check_system_dependencies()
        self.ensure_klipper_repo()
        self.ensure_toolchain()
        print("-------------------------------------------------")
        print("Environnement prêt.")


def main():
    """Point d'entrée du script."""
    # Le script est exécuté depuis la racine du projet, donc le base_dir est matrix_flow
    base_dir = Path(__file__).parent.resolve()
    try:
        manager = EnvironmentManager(base_dir)
        manager.run()
    except EnvironmentError as e:
        print(f"\nERREUR : {e}", file=os.sys.stderr)
        exit(1)

if __name__ == "__main__":
    main()

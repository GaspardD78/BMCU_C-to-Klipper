#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MatrixFlow - Orchestrateur du workflow complet.

Ce script exécute séquentiellement toutes les étapes nécessaires pour
préparer, compiler, flasher et configurer le firmware Klipper pour la BMCU-C.
"""

import argparse
import sys
from pathlib import Path

# Ajoute le répertoire parent au path pour permettre les imports
sys.path.append(str(Path(__file__).parent))

from step_01_environment import main as run_step_01
from step_02_build import main as run_step_02
from step_03_flash import main as run_step_03
from step_04_configure import main as run_step_04

def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Workflow complet pour le firmware BMCU-C.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "-d", "--device",
        help="Chemin vers le port série pour l'étape de flashage (ex: /dev/ttyUSB0)."
    )
    parser.add_argument(
        "--skip-flash",
        action="store_true",
        help="Passer l'étape de flashage (utile pour ne faire que la compilation)."
    )
    args = parser.parse_args()

    # Sauvegarde des arguments originaux pour les passer aux sous-scripts
    original_argv = sys.argv

    try:
        print("="*60)
        print(" DÉBUT DU WORKFLOW MATRIXFLOW ")
        print("="*60)

        # --- Étape 1: Environnement ---
        print("\n>>> LANCEMENT DE L'ÉTAPE 1: PRÉPARATION DE L'ENVIRONNEMENT <<<\n")
        sys.argv = [original_argv[0]] # Réinitialise les arguments
        run_step_01()
        print("\n>>> ÉTAPE 1 TERMINÉE AVEC SUCCÈS <<<\n")

        # --- Étape 2: Compilation ---
        print("\n>>> LANCEMENT DE L'ÉTAPE 2: COMPILATION DU FIRMWARE <<<\n")
        sys.argv = [original_argv[0]]
        run_step_02()
        print("\n>>> ÉTAPE 2 TERMINÉE AVEC SUCCÈS <<<\n")

        # --- Étape 3: Flashage ---
        if not args.skip_flash:
            print("\n>>> LANCEMENT DE L'ÉTAPE 3: FLASHAGE DU FIRMWARE <<<\n")
            flash_args = [original_argv[0]]
            if args.device:
                flash_args.extend(["--device", args.device])
            sys.argv = flash_args
            run_step_03()
            print("\n>>> ÉTAPE 3 TERMINÉE AVEC SUCCÈS <<<\n")
        else:
            print("\n>>> ÉTAPE 3 IGNORÉE (skip-flash) <<<\n")

        # --- Étape 4: Configuration ---
        print("\n>>> LANCEMENT DE L'ÉTAPE 4: AIDE À LA CONFIGURATION <<<\n")
        sys.argv = [original_argv[0]]
        run_step_04()
        print("\n>>> ÉTAPE 4 TERMINÉE AVEC SUCCÈS <<<\n")

        print("="*60)
        print(" WORKFLOW MATRIXFLOW TERMINÉ AVEC SUCCÈS ")
        print("="*60)

    except SystemExit as e:
        if e.code != 0:
            print("\n" + "="*60, file=sys.stderr)
            print(" ERREUR: LE WORKFLOW A ÉCHOUÉ À UNE ÉTAPE. ", file=sys.stderr)
            print("="*60, file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"\nUne erreur inattendue est survenue: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

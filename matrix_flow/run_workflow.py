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
import ui

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
    parser.add_argument(
        "--ci-check",
        action="store_true",
        help="Exécute uniquement les étapes de validation pour l'intégration continue (env + build)."
    )
    args = parser.parse_args()

    # Sauvegarde des arguments originaux pour les passer aux sous-scripts
    original_argv = sys.argv

    try:
        ui.print_banner()
        ui.print_header("DÉBUT DU WORKFLOW MATRIXFLOW")

        # --- Étape 1: Environnement ---
        ui.print_header("ÉTAPE 1: PRÉPARATION DE L'ENVIRONNEMENT")
        sys.argv = [original_argv[0]] # Réinitialise les arguments
        run_step_01()
        ui.print_success("ÉTAPE 1 TERMINÉE AVEC SUCCÈS")

        # --- Étape 2: Compilation ---
        ui.print_header("ÉTAPE 2: COMPILATION DU FIRMWARE")
        sys.argv = [original_argv[0]]
        run_step_02()
        ui.print_success("ÉTAPE 2 TERMINÉE AVEC SUCCÈS")

        # Si c'est un test CI, on s'arrête ici avec succès.
        if args.ci_check:
            ui.print_header("VÉRIFICATION CI TERMINÉE AVEC SUCCÈS")
            sys.exit(0)

        # --- Étape 3: Flashage ---
        if not args.skip_flash:
            ui.print_header("ÉTAPE 3: FLASHAGE DU FIRMWARE")
            flash_args = [original_argv[0]]
            if args.device:
                flash_args.extend(["--device", args.device])
            sys.argv = flash_args
            run_step_03()
            ui.print_success("ÉTAPE 3 TERMINÉE AVEC SUCCÈS")
        else:
            ui.print_warning("ÉTAPE 3 IGNORÉE (skip-flash)")

        # --- Étape 4: Configuration ---
        ui.print_header("ÉTAPE 4: AIDE À LA CONFIGURATION")
        sys.argv = [original_argv[0]]
        run_step_04()
        ui.print_success("ÉTAPE 4 TERMINÉE AVEC SUCCÈS")

        ui.print_header("WORKFLOW MATRIXFLOW TERMINÉ AVEC SUCCÈS")

    except SystemExit as e:
        if e.code != 0:
            ui.print_error("LE WORKFLOW A ÉCHOUÉ À UNE ÉTAPE.")
            sys.exit(1)
    except Exception as e:
        ui.print_error(f"Une erreur inattendue est survenue: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

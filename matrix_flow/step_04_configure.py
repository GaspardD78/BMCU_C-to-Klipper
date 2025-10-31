#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MatrixFlow - Étape 4 : Aide à la configuration.

Ce script aide l'utilisateur à configurer Klipper après le flashage
en générant le bloc de configuration `[bmcu]` nécessaire.
"""

import glob
import sys
from pathlib import Path

class ConfigHelper:
    """Génère la configuration Klipper pour le BMCU."""

    def detect_serial_device(self) -> str | None:
        """Détecte le port série le plus probable pour la carte."""
        # Priorité aux liens 'by-id' qui sont plus stables
        patterns = [
            "/dev/serial/by-id/usb-Klipper_*",
            "/dev/serial/by-id/usb-1a86_USB_Serial*",
            "/dev/ttyCH*", # Caractéristique des puces WCH
            "/dev/ttyACM*",
            "/dev/ttyUSB*",
        ]
        for pattern in patterns:
            devices = glob.glob(pattern)
            if devices:
                print(f"Port série détecté : {devices[0]}")
                return devices[0]
        return None

    def run(self):
        """Exécute l'aide à la configuration."""
        print("--- Étape 4: Aide à la configuration ---")

        serial_device = self.detect_serial_device()
        if not serial_device:
            print("\nAvertissement : Aucun port série n'a pu être détecté automatiquement.", file=sys.stderr)
            print("Veuillez trouver le port manuellement et l'insérer dans le bloc ci-dessous.", file=sys.stderr)
            serial_device = "/dev/tty...."

        config_block = f"""
#--------------------------------------------------------------------
# Section de configuration pour la carte BMCU-C
#
# 1. Copiez ce bloc de code.
# 2. Collez-le à la fin de votre fichier 'printer.cfg'.
# 3. Assurez-vous que le 'serial' correspond bien à votre carte.
# 4. Redémarrez Klipper.
#--------------------------------------------------------------------
[mcu bmcu]
serial: {serial_device}

[bmcu]
# Décommentez les lignes suivantes et ajustez les broches
# si vous utilisez des fonctionnalités spécifiques.
#
# filament_sensor_pin: bmcu:PA0
# extruder_temp_pin:   bmcu:PA1
# heater_bed_temp_pin: bmcu:PA2
#--------------------------------------------------------------------
"""
        print("\n" + "="*50)
        print(" CONFIGURATION KLIPPER POUR LA BMCU-C ")
        print("="*50)
        print(config_block)
        print("----------------------------------------")

def main():
    """Point d'entrée du script."""
    helper = ConfigHelper()
    helper.run()

if __name__ == "__main__":
    main()

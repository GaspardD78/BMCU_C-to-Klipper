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
import ui

class ConfigHelper:
    """Génère la configuration Klipper pour le BMCU."""

    def detect_serial_device(self) -> str | None:
        """Détecte le port série le plus probable pour la carte."""
        ui.print_info("Détection du port série de la carte BMCU-C...")
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
                ui.print_success(f"Port série détecté : {devices[0]}")
                return devices[0]
        return None

    def run(self):
        """Exécute l'aide à la configuration."""
        serial_device = self.detect_serial_device()
        if not serial_device:
            ui.print_warning("Aucun port série n'a pu être détecté automatiquement.")
            ui.print_info("Veuillez trouver le port manuellement et l'insérer dans le bloc ci-dessous.")
            serial_device = "/dev/tty...."

        config_block = f"""
#--------------------------------------------------------------------
# {ui.AnsiColors.WHITE}Section de configuration pour la carte BMCU-C{ui.AnsiColors.RESET}
#
# {ui.AnsiColors.CYAN}1. Copiez ce bloc de code.{ui.AnsiColors.RESET}
# {ui.AnsiColors.CYAN}2. Collez-le à la fin de votre fichier 'printer.cfg'.{ui.AnsiColors.RESET}
# {ui.AnsiColors.CYAN}3. Assurez-vous que le 'serial' correspond bien à votre carte.{ui.AnsiColors.RESET}
# {ui.AnsiColors.CYAN}4. Redémarrez Klipper.{ui.AnsiColors.RESET}
#--------------------------------------------------------------------
{ui.AnsiColors.GREEN}[mcu bmcu]{ui.AnsiColors.RESET}
serial: {ui.AnsiColors.YELLOW}{serial_device}{ui.AnsiColors.RESET}

{ui.AnsiColors.GREEN}[bmcu]{ui.AnsiColors.RESET}
# {ui.AnsiColors.GREY}Décommentez les lignes suivantes et ajustez les broches
# si vous utilisez des fonctionnalités spécifiques.{ui.AnsiColors.RESET}
#
# {ui.AnsiColors.GREY}filament_sensor_pin: bmcu:PA0{ui.AnsiColors.RESET}
# {ui.AnsiColors.GREY}extruder_temp_pin:   bmcu:PA1{ui.AnsiColors.RESET}
# {ui.AnsiColors.GREY}heater_bed_temp_pin: bmcu:PA2{ui.AnsiColors.RESET}
#--------------------------------------------------------------------
"""
        print("\n")
        ui.print_header("CONFIGURATION KLIPPER POUR LA BMCU-C")
        print(config_block)

def main():
    """Point d'entrée du script."""
    helper = ConfigHelper()
    helper.run()

if __name__ == "__main__":
    main()

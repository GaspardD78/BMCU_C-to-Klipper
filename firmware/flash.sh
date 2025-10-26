#!/bin/bash
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

set -euo pipefail

# Script pour flasher le firmware Klipper sur le BMCU-C

# Se déplacer à la racine du projet
cd "$(dirname "$0")/.."

# Vérifier si le firmware a été compilé
if [ ! -f "klipper/out/klipper.bin" ]; then
    echo "  Le firmware n'a pas été trouvé. Veuillez d'abord lancer firmware/build.sh"
    exit 1
fi

# Instructions pour l'utilisateur
echo "  Pour flasher le BMCU-C, vous devez le mettre en mode bootloader :"
echo "  1. Maintenez le bouton BOOT0 enfoncé."
echo "  2. Appuyez et relâchez le bouton RESET."
echo "  3. Relâchez le bouton BOOT0."
echo ""
read -p "  Appuyez sur Entrée lorsque vous êtes prêt..."

# Flasher le firmware
echo "  Flashage du firmware..."
wchisp -d 30 -c ch32v20x flash klipper/out/klipper.bin

echo "  Flashage terminé."

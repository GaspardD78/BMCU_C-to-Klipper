#!/bin/bash
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

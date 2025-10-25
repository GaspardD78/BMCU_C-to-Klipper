#!/bin/bash
set -euo pipefail

# Script pour compiler le firmware Klipper pour le BMCU-C

# Se déplacer à la racine du projet
cd "$(dirname "$0")/.."

# Copier la configuration Klipper
echo " copie de la configuration..."
cp firmware/klipper.config klipper/.config

# Nettoyer et compiler
echo " compilation du firmware..."
cd klipper
make clean
make

echo " compilation terminée. Le firmware se trouve dans klipper/out/klipper.bin"

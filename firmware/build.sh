#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGO_FILE="${SCRIPT_DIR}/../logo/banner.txt"

if [[ -f "${LOGO_FILE}" ]]; then
    cat "${LOGO_FILE}"
    echo
fi

# Script pour compiler le firmware Klipper pour le BMCU-C

# Se déplacer à la racine du projet
cd "${SCRIPT_DIR}/.."

# Copier la configuration Klipper
echo " copie de la configuration..."
cp firmware/klipper.config klipper/.config

# Nettoyer et compiler
echo " compilation du firmware..."
cd klipper
make clean
make

echo " compilation terminée. Le firmware se trouve dans klipper/out/klipper.bin"

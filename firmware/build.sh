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

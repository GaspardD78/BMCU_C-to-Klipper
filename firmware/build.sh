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

# Appliquer les correctifs spécifiques CH32V20X
OVERRIDES_DIR="${SCRIPT_DIR}/klipper_overrides"
KLIPPER_DIR="${SCRIPT_DIR}/../klipper"

apply_patch() {
    local patch_file="$1"
    if [[ -f "${patch_file}" ]]; then
        echo " application du patch $(basename "${patch_file}")..."
        if ! patch -d "${KLIPPER_DIR}" -p1 -N --silent < "${patch_file}"; then
            echo " échec lors de l'application de ${patch_file}" >&2
            exit 1
        fi
    fi
}

copy_tree() {
    local src="$1"
    local dest="$2"
    if [[ -d "${src}" ]]; then
        echo " synchronisation de $(basename "${src}")..."
        mkdir -p "${dest}"
        cp -a "${src}"/. "${dest}/"
    fi
}

apply_patch "${OVERRIDES_DIR}/src/Kconfig.patch"
copy_tree "${OVERRIDES_DIR}/src/ch32v20x" "${KLIPPER_DIR}/src/ch32v20x"
copy_tree "${OVERRIDES_DIR}/src/generic" "${KLIPPER_DIR}/src/generic"
copy_tree "${OVERRIDES_DIR}/config/boards" "${KLIPPER_DIR}/config/boards"

# Nettoyer et compiler
echo " compilation du firmware..."
cd klipper
make clean
make

echo " compilation terminée. Le firmware se trouve dans klipper/out/klipper.bin"

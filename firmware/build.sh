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
REPO_ROOT="${SCRIPT_DIR}/.."
KLIPPER_DIR="${REPO_ROOT}/klipper"
LOGO_FILE="${REPO_ROOT}/logo/banner.txt"
OVERRIDES_DIR="${SCRIPT_DIR}/klipper_overrides"
TOOLCHAIN_PREFIX="${CROSS_PREFIX:-riscv64-unknown-elf-}"

if [[ -t 1 ]]; then
    readonly COLOR_INFO="\e[34m"
    readonly COLOR_SUCCESS="\e[32m"
    readonly COLOR_ERROR="\e[31m"
    readonly COLOR_RESET="\e[0m"
else
    readonly COLOR_INFO=""
    readonly COLOR_SUCCESS=""
    readonly COLOR_ERROR=""
    readonly COLOR_RESET=""
fi

print_info() {
    printf "%s[INFO]%s %s\n" "${COLOR_INFO}" "${COLOR_RESET}" "$1"
}

print_success() {
    printf "%s[OK]%s %s\n" "${COLOR_SUCCESS}" "${COLOR_RESET}" "$1"
}

print_error() {
    printf "%s[ERREUR]%s %s\n" "${COLOR_ERROR}" "${COLOR_RESET}" "$1" >&2
}

require_command() {
    local cmd="$1"
    local message="$2"

    if ! command -v "${cmd}" >/dev/null 2>&1; then
        print_error "${message}"
        exit 1
    fi
}

if [[ -f "${LOGO_FILE}" ]]; then
    cat "${LOGO_FILE}"
    echo
fi

print_info "Vérification des dépendances..."

declare -A REQUIRED_COMMANDS=(
    [git]="git est requis. Assurez-vous qu'il est installé."
    [patch]="patch est requis. Installez le paquet patch."
    [make]="make est requis. Installez les outils de compilation (build-essential)."
)
REQUIRED_COMMANDS["${TOOLCHAIN_PREFIX}gcc"]="la chaîne d'outils ${TOOLCHAIN_PREFIX}gcc est absente. Installez 'gcc-riscv64-unknown-elf' ou définissez CROSS_PREFIX pour pointer vers un préfixe valide."

ordered_commands=(git patch make "${TOOLCHAIN_PREFIX}gcc")
for cmd in "${ordered_commands[@]}"; do
    require_command "${cmd}" "${REQUIRED_COMMANDS[${cmd}]}"
    print_info "  • ${cmd} ✅"
done

print_info "Positionnement à la racine du dépôt"
cd "${REPO_ROOT}"

if [[ ! -d "${KLIPPER_DIR}/.git" ]]; then
    print_info "Initialisation du sous-module Klipper..."
    git submodule update --init --recursive klipper
else
    print_info "Synchronisation du sous-module Klipper..."
    git submodule update --recursive klipper
fi

print_info "Copie de la configuration Klipper..."
cp "${SCRIPT_DIR}/klipper.config" "${KLIPPER_DIR}/.config"

apply_patch() {
    local patch_file="$1"

    if [[ ! -f "${patch_file}" ]]; then
        return
    fi

    local patch_name
    patch_name="$(basename "${patch_file}")"

    if patch -d "${KLIPPER_DIR}" -p1 -R --dry-run --silent < "${patch_file}" 2>/dev/null; then
        print_info "Patch ${patch_name} déjà appliqué, passage."
        return
    fi

    print_info "Application du patch ${patch_name}..."
    if ! patch -d "${KLIPPER_DIR}" -p1 -N --silent < "${patch_file}"; then
        print_error "Échec lors de l'application de ${patch_name}"
        exit 1
    fi
}

copy_tree() {
    local src="$1"
    local dest="$2"

    if [[ -d "${src}" ]]; then
        print_info "Synchronisation de $(basename "${src}")..."
        mkdir -p "${dest}"
        cp -a "${src}"/. "${dest}/"
    fi
}

apply_patch "${OVERRIDES_DIR}/src/Kconfig.patch"
copy_tree "${OVERRIDES_DIR}/src/ch32v20x" "${KLIPPER_DIR}/src/ch32v20x"
copy_tree "${OVERRIDES_DIR}/src/generic" "${KLIPPER_DIR}/src/generic"
copy_tree "${OVERRIDES_DIR}/config/boards" "${KLIPPER_DIR}/config/boards"

print_info "Compilation du firmware Klipper..."
cd "${KLIPPER_DIR}"
make clean
make

print_success "Compilation terminée. Le firmware se trouve dans klipper/out/klipper.bin"

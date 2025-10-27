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
FLASH_ROOT="${SCRIPT_DIR}"
CACHE_ROOT="${FLASH_ROOT}/.cache"
KLIPPER_DIR="${CACHE_ROOT}/klipper"
LOGO_FILE="${FLASH_ROOT}/banner.txt"
OVERRIDES_DIR="${FLASH_ROOT}/klipper_overrides"
TOOLCHAIN_PREFIX="${CROSS_PREFIX:-riscv32-unknown-elf-}"
TOOLCHAIN_CACHE_DIR="${CACHE_ROOT}/toolchains"
TOOLCHAIN_RELEASE="2025.10.18"
TOOLCHAIN_ARCHIVE="riscv32-elf-ubuntu-22.04-gcc.tar.xz"
TOOLCHAIN_URL="https://github.com/riscv-collab/riscv-gnu-toolchain/releases/download/${TOOLCHAIN_RELEASE}/${TOOLCHAIN_ARCHIVE}"
TOOLCHAIN_INSTALL_DIR="${TOOLCHAIN_CACHE_DIR}/riscv32-elf-${TOOLCHAIN_RELEASE}"
TOOLCHAIN_BIN_DIR="${TOOLCHAIN_INSTALL_DIR}/riscv/bin"
KLIPPER_REPO_URL="${KLIPPER_REPO_URL:-https://github.com/Klipper3d/klipper.git}"
KLIPPER_REF="${KLIPPER_REF:-master}"
KLIPPER_CLONE_DEPTH="${KLIPPER_CLONE_DEPTH:-1}"

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

bootstrap_toolchain() {
    if [[ -n "${CROSS_PREFIX:-}" ]]; then
        print_error "${TOOLCHAIN_PREFIX}gcc est introuvable et CROSS_PREFIX est défini. Veuillez installer la toolchain correspondante ou corriger CROSS_PREFIX."
        exit 1
    fi

    local toolchain_gcc="${TOOLCHAIN_BIN_DIR}/${TOOLCHAIN_PREFIX}gcc"

    if [[ -x "${toolchain_gcc}" ]]; then
        export PATH="${TOOLCHAIN_BIN_DIR}:${PATH}"
        print_info "Utilisation de la toolchain locale : ${toolchain_gcc}"
        return
    fi

    if ! command -v curl >/dev/null 2>&1; then
        print_error "curl est requis pour télécharger automatiquement la toolchain RISC-V. Installez curl ou la toolchain manuellement."
        exit 1
    fi

    if ! command -v tar >/dev/null 2>&1; then
        print_error "tar est requis pour extraire la toolchain RISC-V. Installez tar ou la toolchain manuellement."
        exit 1
    fi

    mkdir -p "${TOOLCHAIN_CACHE_DIR}"
    local archive_path="${TOOLCHAIN_CACHE_DIR}/${TOOLCHAIN_ARCHIVE}"

    if [[ ! -f "${archive_path}" ]]; then
        print_info "Téléchargement de la toolchain RISC-V (${TOOLCHAIN_RELEASE})..."
        if ! curl --fail --location --progress-bar "${TOOLCHAIN_URL}" -o "${archive_path}"; then
            print_error "Échec du téléchargement de la toolchain depuis ${TOOLCHAIN_URL}"
            rm -f "${archive_path}"
            exit 1
        fi
    else
        print_info "Archive toolchain déjà présente, réutilisation de ${archive_path}"
    fi

    local temp_dir
    temp_dir="$(mktemp -d)"
    print_info "Extraction de la toolchain dans ${TOOLCHAIN_INSTALL_DIR}"
    if ! tar -xf "${archive_path}" -C "${temp_dir}"; then
        rm -rf "${temp_dir}"
        print_error "Échec lors de l'extraction de la toolchain"
        exit 1
    fi

    rm -rf "${TOOLCHAIN_INSTALL_DIR}"
    mkdir -p "${TOOLCHAIN_INSTALL_DIR}"
    mv "${temp_dir}/riscv" "${TOOLCHAIN_INSTALL_DIR}/"
    rm -rf "${temp_dir}"

    export PATH="${TOOLCHAIN_BIN_DIR}:${PATH}"

    if [[ ! -x "${toolchain_gcc}" ]]; then
        print_error "La toolchain téléchargée ne contient pas ${TOOLCHAIN_PREFIX}gcc. Vérifiez l'archive (${TOOLCHAIN_URL})."
        exit 1
    fi

    print_info "Toolchain RISC-V installée localement dans ${TOOLCHAIN_INSTALL_DIR}"
}

ensure_toolchain() {
    local toolchain_cmd="${TOOLCHAIN_PREFIX}gcc"

    if command -v "${toolchain_cmd}" >/dev/null 2>&1; then
        return
    fi

    bootstrap_toolchain

    if ! command -v "${toolchain_cmd}" >/dev/null 2>&1; then
        print_error "${toolchain_cmd} reste introuvable malgré l'installation automatique."
        exit 1
    fi
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

ensure_toolchain

declare -A REQUIRED_COMMANDS=(
    [git]="git est requis. Assurez-vous qu'il est installé."
    [make]="make est requis. Installez les outils de compilation (build-essential)."
)
REQUIRED_COMMANDS["${TOOLCHAIN_PREFIX}gcc"]="la chaîne d'outils ${TOOLCHAIN_PREFIX}gcc est absente. Installez 'gcc-riscv32-unknown-elf', définissez CROSS_PREFIX ou laissez le script télécharger la toolchain officielle."

ordered_commands=(git make "${TOOLCHAIN_PREFIX}gcc")
for cmd in "${ordered_commands[@]}"; do
    require_command "${cmd}" "${REQUIRED_COMMANDS[${cmd}]}"
    print_info "  • ${cmd} ✅"
done

ensure_klipper_repo() {
    mkdir -p "${CACHE_ROOT}"

    if [[ ! -d "${KLIPPER_DIR}/.git" ]]; then
        print_info "Clonage du dépôt Klipper (${KLIPPER_REPO_URL})..."
        if ! git clone \
            --depth "${KLIPPER_CLONE_DEPTH}" \
            --branch "${KLIPPER_REF}" \
            "${KLIPPER_REPO_URL}" "${KLIPPER_DIR}"; then
            print_error "Échec du clonage de ${KLIPPER_REPO_URL}"
            exit 1
        fi
        return
    fi

    print_info "Mise à jour du dépôt Klipper (${KLIPPER_REF})..."
    if ! git -C "${KLIPPER_DIR}" fetch --tags --prune origin; then
        print_error "Impossible de récupérer les mises à jour depuis origin"
        exit 1
    fi

    if ! git -C "${KLIPPER_DIR}" checkout "${KLIPPER_REF}"; then
        print_error "Impossible de se positionner sur ${KLIPPER_REF}"
        exit 1
    fi

    if ! git -C "${KLIPPER_DIR}" pull --ff-only origin "${KLIPPER_REF}"; then
        print_error "Impossible de mettre à jour ${KLIPPER_REF}"
        exit 1
    fi
}

ensure_klipper_repo

print_info "Copie de la configuration Klipper..."
cp "${SCRIPT_DIR}/klipper.config" "${KLIPPER_DIR}/.config"

apply_patch() {
    local patch_file="$1"

    if [[ ! -f "${patch_file}" ]]; then
        return
    fi

    local patch_name
    patch_name="$(basename "${patch_file}")"

    if git -C "${KLIPPER_DIR}" apply --reverse --check "${patch_file}" >/dev/null 2>&1; then
        print_info "Patch ${patch_name} déjà appliqué, passage."
        return
    fi

    print_info "Application du patch ${patch_name}..."
    if ! git -C "${KLIPPER_DIR}" apply "${patch_file}"; then
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

apply_patch "${OVERRIDES_DIR}/Makefile.patch"
apply_patch "${OVERRIDES_DIR}/src/Kconfig.patch"
copy_tree "${OVERRIDES_DIR}/src/ch32v20x" "${KLIPPER_DIR}/src/ch32v20x"
copy_tree "${OVERRIDES_DIR}/src/generic" "${KLIPPER_DIR}/src/generic"
copy_tree "${OVERRIDES_DIR}/config/boards" "${KLIPPER_DIR}/config/boards"

print_info "Compilation du firmware Klipper..."
cd "${KLIPPER_DIR}"
make clean
make

print_success "Compilation terminée. Le firmware se trouve dans ${KLIPPER_DIR}/out/klipper.bin"

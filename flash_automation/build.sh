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
DEFAULT_KLIPPER_DIR="${CACHE_ROOT}/klipper"
KLIPPER_DIR="${KLIPPER_SRC_DIR:-${DEFAULT_KLIPPER_DIR}}"
USE_EXISTING_KLIPPER="false"
if [[ -n "${KLIPPER_SRC_DIR:-}" ]]; then
    USE_EXISTING_KLIPPER="true"
fi
LOGO_FILE="${FLASH_ROOT}/banner.txt"
OVERRIDES_DIR="${FLASH_ROOT}/klipper_overrides"
TOOLCHAIN_PREFIX="${CROSS_PREFIX:-riscv32-unknown-elf-}"
TOOLCHAIN_CACHE_DIR="${CACHE_ROOT}/toolchains"
TOOLCHAIN_RELEASE="2025.10.18"
TOOLCHAIN_ARCHIVE_X86_64="riscv32-elf-ubuntu-22.04-gcc.tar.xz"
TOOLCHAIN_BASE_URL="https://github.com/riscv-collab/riscv-gnu-toolchain/releases/download/${TOOLCHAIN_RELEASE}"
HOST_ARCH="$(uname -m)"
SUPPORTED_AUTO_TOOLCHAIN_ARCHS=("x86_64" "amd64")
AUTO_TOOLCHAIN_SUPPORTED="false"
for arch in "${SUPPORTED_AUTO_TOOLCHAIN_ARCHS[@]}"; do
    if [[ "${HOST_ARCH}" == "${arch}" ]]; then
        AUTO_TOOLCHAIN_SUPPORTED="true"
        break
    fi
done

if [[ "${AUTO_TOOLCHAIN_SUPPORTED}" == "true" ]]; then
    TOOLCHAIN_ARCHIVE="${TOOLCHAIN_ARCHIVE_X86_64}"
    TOOLCHAIN_URL="${TOOLCHAIN_BASE_URL}/${TOOLCHAIN_ARCHIVE}"
else
    TOOLCHAIN_ARCHIVE=""
    TOOLCHAIN_URL=""
fi

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
        print_error "${TOOLCHAIN_PREFIX}gcc est introuvable alors que CROSS_PREFIX est défini. Installez la toolchain pointée par CROSS_PREFIX ou ajustez sa valeur (voir README pour les options ARM)."
        exit 1
    fi

    local toolchain_gcc="${TOOLCHAIN_BIN_DIR}/${TOOLCHAIN_PREFIX}gcc"

    if [[ "${AUTO_TOOLCHAIN_SUPPORTED}" != "true" ]]; then
        print_error "Téléchargement automatique indisponible sur l'architecture ${HOST_ARCH}. Installez une toolchain RISC-V compatible puis relancez en exportant CROSS_PREFIX vers son préfixe binaire (ex. /opt/riscv/bin/riscv-none-elf-)."
        exit 1
    fi

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

    if [[ "${USE_EXISTING_KLIPPER}" == "true" ]]; then
        local resolved="${KLIPPER_DIR/#\~/${HOME}}"

        if [[ "${resolved}" != /* ]]; then
            if ! resolved="$(cd "${PWD}" && cd "${resolved}" 2>/dev/null && pwd)"; then
                print_error "Le répertoire Klipper spécifié (${KLIPPER_DIR}) est introuvable. Vérifiez KLIPPER_SRC_DIR."
                exit 1
            fi
        else
            if ! resolved="$(cd "${resolved}" 2>/dev/null && pwd)"; then
                print_error "Le répertoire Klipper spécifié (${KLIPPER_DIR}) est introuvable."
                exit 1
            fi
        fi

        KLIPPER_DIR="${resolved}"
        print_info "Utilisation du dépôt Klipper existant : ${KLIPPER_DIR}"

        if [[ ! -d "${KLIPPER_DIR}/.git" ]]; then
            print_error "${KLIPPER_DIR} n'est pas un dépôt Git. Impossible d'appliquer automatiquement les correctifs."
            exit 1
        fi

        return
    fi

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

if [[ "${USE_EXISTING_KLIPPER}" == "true" && -f "${KLIPPER_DIR}/.config" ]]; then
    if [[ ! -f "${KLIPPER_DIR}/.config.bmcuc_backup" ]]; then
        print_info "Sauvegarde de la configuration existante (${KLIPPER_DIR}/.config.bmcuc_backup)..."
        cp "${KLIPPER_DIR}/.config" "${KLIPPER_DIR}/.config.bmcuc_backup"
    else
        print_info "Configuration existante déjà sauvegardée (${KLIPPER_DIR}/.config.bmcuc_backup)."
    fi
fi

print_info "Copie de la configuration Klipper..."
cp "${SCRIPT_DIR}/klipper.config" "${KLIPPER_DIR}/.config"

update_cross_prefix() {
    local config_file="${KLIPPER_DIR}/.config"
    local normalized_prefix="${TOOLCHAIN_PREFIX}"

    if [[ -z "${normalized_prefix}" ]]; then
        return
    fi

    if [[ "${normalized_prefix}" != *- ]]; then
        normalized_prefix="${normalized_prefix}-"
    fi

    TOOLCHAIN_PREFIX="${normalized_prefix}"

    if command -v python3 >/dev/null 2>&1; then
        CONFIG_PATH="${config_file}" \
        CONFIG_PREFIX="${normalized_prefix}" \
        python3 - <<'PY'
import os
from pathlib import Path

config_path = Path(os.environ["CONFIG_PATH"])
prefix = os.environ["CONFIG_PREFIX"]

lines = config_path.read_text(encoding="utf-8").splitlines()
updated = []
found = False

for line in lines:
    if line.startswith("CONFIG_CROSS_PREFIX="):
        if line != f'CONFIG_CROSS_PREFIX="{prefix}"':
            found = True
        updated.append(f'CONFIG_CROSS_PREFIX="{prefix}"')
    else:
        updated.append(line)

if not any(l.startswith("CONFIG_CROSS_PREFIX=") for l in updated):
    updated.append(f'CONFIG_CROSS_PREFIX="{prefix}"')
    found = True

if found:
    config_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY
    else
        print_error "python3 est requis pour ajuster CONFIG_CROSS_PREFIX. Veuillez l'installer ou mettre à jour ${config_file} manuellement."
        exit 1
    fi
}

update_cross_prefix

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
make CROSS_PREFIX="${TOOLCHAIN_PREFIX}"

print_success "Compilation terminée. Le firmware se trouve dans ${KLIPPER_DIR}/out/klipper.bin"

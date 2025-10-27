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

# Script d'automatisation pour le flashage du firmware Klipper sur un BMCU-C.
# Ce script fusionne l'expérience utilisateur simple de l'ancien flash.sh
# avec les garde-fous et la journalisation avancés de flash_automation.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLASH_ROOT="${SCRIPT_DIR}"
CACHE_ROOT="${FLASH_ROOT}/.cache"
LOGO_FILE="${FLASH_ROOT}/banner.txt"

resolve_path_relative_to_flash_root() {
    local raw_path="$1"
    local expanded="${raw_path/#~/${HOME}}"

    if [[ "${expanded}" != /* ]]; then
        expanded="${FLASH_ROOT}/${expanded}"
    fi

    printf '%s\n' "${expanded}"
}

if [[ -f "${LOGO_FILE}" ]]; then
    cat "${LOGO_FILE}"
    echo
fi

readonly LOG_BASE_DIR="${FLASH_ROOT}/logs"
readonly LOG_DIR="${LOG_BASE_DIR}/flash_$(date +%Y-%m-%d_%H-%M-%S)"
readonly LOG_FILE="${LOG_DIR}/flash.log"
readonly FAILURE_REPORT="${LOG_DIR}/FAILURE_REPORT.txt"
readonly DEFAULT_FIRMWARE_RELATIVE_PATH=".cache/klipper/out/klipper.bin"
FIRMWARE_DISPLAY_PATH="${KLIPPER_FIRMWARE_PATH:-${DEFAULT_FIRMWARE_RELATIVE_PATH}}"
readonly FIRMWARE_DISPLAY_PATH
readonly FIRMWARE_FILE="$(resolve_path_relative_to_flash_root "${FIRMWARE_DISPLAY_PATH}")"
readonly TOOLS_ROOT="${CACHE_ROOT}/tools"
readonly WCHISP_CACHE_DIR="${TOOLS_ROOT}/wchisp"
readonly WCHISP_RELEASE="${WCHISP_RELEASE:-v0.3.0}"
readonly WCHISP_AUTO_INSTALL="${WCHISP_AUTO_INSTALL:-true}"
readonly WCHISP_BASE_URL="${WCHISP_BASE_URL:-https://github.com/ch32-rs/wchisp/releases/download}"
WCHISP_COMMAND="${WCHISP_BIN:-wchisp}"
readonly WCHISP_TARGET="${WCHISP_TARGET:-ch32v20x}"
readonly WCHISP_DELAY="${WCHISP_DELAY:-30}"

CURRENT_STEP="Initialisation"
FIRMWARE_SIZE=""
FIRMWARE_SHA=""

mkdir -p "${LOG_DIR}"
touch "${LOG_FILE}"

function log_message() {
    local level="$1"
    local message="$2"
    local timestamp
    timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    echo "[$timestamp] [$level] - $message" >> "${LOG_FILE}"
}

function handle_error() {
    local exit_code=$?
    local line_number=$1
    local command="$2"

    log_message "ERROR" "Échec à l'étape '${CURRENT_STEP}'"
    log_message "ERROR" "Commande: ${command} (ligne ${line_number}) - code ${exit_code}"

    {
        echo "Rapport d'échec - Flash BMCU-C"
        echo "================================"
        echo "Date: $(date)"
        echo "Étape échouée: ${CURRENT_STEP}"
        echo "Commande: ${command}"
        echo "Ligne: ${line_number}"
        echo "Code de sortie: ${exit_code}"
        echo
        echo "Contexte (50 dernières lignes du log):"
        echo "---------------------------------------"
        tail -n 50 "${LOG_FILE}" 2>/dev/null || echo "Aucun log disponible."
    } > "${FAILURE_REPORT}"

    echo "### ÉCHEC CRITIQUE ###"
    echo "Une erreur est survenue pendant '${CURRENT_STEP}'."
    echo "Consultez ${FAILURE_REPORT} pour plus de détails."

    exit "${exit_code}"
}

trap 'handle_error $LINENO "$BASH_COMMAND"' ERR

function command_exists() {
    local cmd="$1"
    if [[ "${cmd}" == */* ]]; then
        [[ -x "${cmd}" ]]
    else
        command -v "${cmd}" >/dev/null 2>&1
    fi
}

ensure_wchisp() {
    if command_exists "${WCHISP_COMMAND}"; then
        return
    fi

    if [[ "${WCHISP_AUTO_INSTALL}" != "true" ]]; then
        log_message "ERROR" "wchisp est introuvable et l'installation automatique est désactivée."
        echo "La dépendance 'wchisp' est introuvable. Exportez WCHISP_BIN ou activez WCHISP_AUTO_INSTALL=true pour autoriser le téléchargement automatique."
        exit 1
    fi

    if ! command_exists curl; then
        log_message "ERROR" "Impossible d'installer wchisp automatiquement: curl est absent."
        echo "curl est requis pour installer automatiquement wchisp. Installez curl ou wchisp manuellement."
        exit 1
    fi

    if ! command_exists tar; then
        log_message "ERROR" "Impossible d'installer wchisp automatiquement: tar est absent."
        echo "tar est requis pour installer automatiquement wchisp. Installez tar ou wchisp manuellement."
        exit 1
    fi

    local arch asset url
    arch="$(uname -m)"

    case "${arch}" in
        x86_64|amd64)
            asset="wchisp-${WCHISP_RELEASE}-linux-x64.tar.gz"
            ;;
        aarch64|arm64)
            asset="wchisp-${WCHISP_RELEASE}-linux-aarch64.tar.gz"
            ;;
        *)
            log_message "ERROR" "Aucun binaire wchisp pré-compilé disponible pour ${arch}."
            echo "Aucun binaire wchisp pré-compilé n'est disponible pour l'architecture ${arch}. Installez l'outil manuellement et re-lancez."
            exit 1
            ;;
    esac

    url="${WCHISP_BASE_URL}/${WCHISP_RELEASE}/${asset}"
    mkdir -p "${WCHISP_CACHE_DIR}"
    local archive_path="${WCHISP_CACHE_DIR}/${asset}"

    if [[ ! -f "${archive_path}" ]]; then
        log_message "INFO" "Téléchargement de wchisp (${url})."
        if ! curl --fail --location --progress-bar "${url}" -o "${archive_path}"; then
            rm -f "${archive_path}"
            log_message "ERROR" "Échec du téléchargement de wchisp depuis ${url}."
            echo "Échec du téléchargement de wchisp (${url}). Installez wchisp manuellement."
            exit 1
        fi
    else
        log_message "INFO" "Archive wchisp déjà présente (${archive_path})."
    fi

    local install_dir="${WCHISP_CACHE_DIR}/${WCHISP_RELEASE}-${arch}"
    rm -rf "${install_dir}"
    mkdir -p "${install_dir}"

    log_message "INFO" "Extraction de wchisp dans ${install_dir}."
    if ! tar -xf "${archive_path}" --strip-components=1 -C "${install_dir}"; then
        rm -rf "${install_dir}"
        log_message "ERROR" "Échec de l'extraction de wchisp depuis ${archive_path}."
        echo "Impossible d'extraire wchisp. Vérifiez l'archive ou installez l'outil manuellement."
        exit 1
    fi

    local candidate="${install_dir}/wchisp"
    if [[ ! -x "${candidate}" ]]; then
        log_message "ERROR" "Le binaire wchisp est introuvable après extraction (${candidate})."
        echo "Le binaire wchisp est manquant après extraction. Installez l'outil manuellement."
        exit 1
    fi

    WCHISP_COMMAND="${candidate}"
    log_message "INFO" "wchisp disponible localement via ${WCHISP_COMMAND}."
    echo "wchisp installé automatiquement dans ${install_dir}."
}

function verify_dependencies() {
    CURRENT_STEP="Étape 0: Initialisation"
    echo "=== ${CURRENT_STEP} ==="
    log_message "INFO" "Vérification des dépendances."

    ensure_wchisp

    local dependencies=("${WCHISP_COMMAND}" "sha256sum" "stat")
    for dep in "${dependencies[@]}"; do
        if ! command_exists "${dep}"; then
            log_message "ERROR" "Dépendance manquante: ${dep}"
            echo "La dépendance '${dep}' est introuvable."
            echo "Installez-la puis relancez le script."
            exit 1
        fi
    done

    log_message "INFO" "Toutes les dépendances requises sont présentes."
    echo "Dépendances... OK"
}

function prepare_firmware() {
    CURRENT_STEP="Étape 1: Vérification du firmware"
    echo "=== ${CURRENT_STEP} ==="
    log_message "INFO" "Vérification de la présence du firmware (${FIRMWARE_DISPLAY_PATH})."

    if [[ ! -f "${FIRMWARE_FILE}" ]]; then
        log_message "ERROR" "Firmware introuvable: ${FIRMWARE_FILE}"
        echo "Le firmware n'a pas été trouvé (${FIRMWARE_DISPLAY_PATH})."
        echo "Veuillez lancer './build.sh' depuis le répertoire flash_automation avant de continuer ou ajuster KLIPPER_FIRMWARE_PATH."
        exit 1
    fi

    FIRMWARE_SIZE=$(stat --printf="%s" "${FIRMWARE_FILE}")
    FIRMWARE_SHA=$(sha256sum "${FIRMWARE_FILE}" | awk '{print $1}')

    log_message "INFO" "Taille du firmware: ${FIRMWARE_SIZE} octets"
    log_message "INFO" "SHA256 du firmware: ${FIRMWARE_SHA}"

    echo "Firmware détecté: ${FIRMWARE_DISPLAY_PATH}"
    echo "Taille: ${FIRMWARE_SIZE} octets"
    echo "SHA256: ${FIRMWARE_SHA}"
}

function prompt_bootloader() {
    CURRENT_STEP="Étape 2: Passage en mode bootloader"
    echo "=== ${CURRENT_STEP} ==="
    log_message "INFO" "Instructions pour passage en mode bootloader affichées."

    cat <<'INSTRUCTIONS'
Pour flasher le BMCU-C, procédez comme suit :
  1. Maintenez le bouton BOOT0 enfoncé.
  2. Appuyez puis relâchez le bouton RESET.
  3. Relâchez le bouton BOOT0.
INSTRUCTIONS

    read -rp "Appuyez sur Entrée lorsque le BMCU-C est en mode bootloader..." _
    log_message "INFO" "Confirmation utilisateur reçue : passage en mode bootloader effectué."
}

function flash_firmware() {
    CURRENT_STEP="Étape 3: Flashage du firmware"
    echo "=== ${CURRENT_STEP} ==="
    log_message "INFO" "Début de la commande de flashage via ${WCHISP_COMMAND}."

    local cmd=("${WCHISP_COMMAND}" -d "${WCHISP_DELAY}" -c "${WCHISP_TARGET}" flash "${FIRMWARE_FILE}")
    log_message "DEBUG" "Commande exécutée: ${cmd[*]}"

    echo "Flashage du firmware..."
    "${cmd[@]}" 2>&1 | tee -a "${LOG_FILE}"

    log_message "INFO" "Flashage terminé avec succès."
    echo "Flashage... OK"
}

function post_flash() {
    CURRENT_STEP="Étape 4: Vérifications post-flash"
    echo "=== ${CURRENT_STEP} ==="
    log_message "INFO" "Processus de flashage terminé."

    echo "Résumé :"
    echo "  - Firmware : ${FIRMWARE_DISPLAY_PATH}"
    echo "  - Taille   : ${FIRMWARE_SIZE} octets"
    echo "  - SHA256   : ${FIRMWARE_SHA}"
    echo
    echo ">>> Le flashage s'est terminé avec SUCCÈS. <<<"
    echo "Les logs détaillés sont disponibles ici : ${LOG_FILE}"
    log_message "INFO" "Procédure complète terminée avec succès."
}

function main() {
    verify_dependencies
    prepare_firmware
    prompt_bootloader
    flash_firmware
    post_flash
}

main

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
readonly DEFAULT_FIRMWARE_RELATIVE_PATH=".cache/klipper/out"
FIRMWARE_DISPLAY_PATH="${KLIPPER_FIRMWARE_PATH:-}" 
FIRMWARE_FILE=""
FIRMWARE_FORMAT=""
readonly TOOLS_ROOT="${CACHE_ROOT}/tools"
readonly WCHISP_CACHE_DIR="${TOOLS_ROOT}/wchisp"
readonly WCHISP_RELEASE="${WCHISP_RELEASE:-v0.3.0}"
readonly WCHISP_AUTO_INSTALL="${WCHISP_AUTO_INSTALL:-true}"
readonly WCHISP_BASE_URL="${WCHISP_BASE_URL:-https://github.com/ch32-rs/wchisp/releases/download}"
WCHISP_COMMAND="${WCHISP_BIN:-wchisp}"
readonly WCHISP_TARGET="${WCHISP_TARGET:-ch32v20x}"
readonly WCHISP_DELAY="${WCHISP_DELAY:-30}"

if [[ -t 1 ]]; then
    COLOR_RESET="\033[0m"
    COLOR_INFO="\033[38;5;39m"
    COLOR_WARN="\033[38;5;214m"
    COLOR_ERROR="\033[38;5;203m"
    COLOR_SUCCESS="\033[38;5;40m"
    COLOR_SECTION="\033[1;97m"
    COLOR_BORDER="\033[38;5;60m"
else
    COLOR_RESET=""
    COLOR_INFO=""
    COLOR_WARN=""
    COLOR_ERROR=""
    COLOR_SUCCESS=""
    COLOR_SECTION=""
    COLOR_BORDER=""
fi

CURRENT_STEP="Initialisation"
FIRMWARE_SIZE=""
FIRMWARE_SHA=""
SELECTED_METHOD=""
SELECTED_DEVICE=""
SDCARD_MOUNTPOINT=""
declare -a ACTIVE_KLIPPER_SERVICES=()
SERVICES_STOPPED="false"
SERVICES_RESTORED="false"

mkdir -p "${LOG_DIR}"
touch "${LOG_FILE}"

function log_message() {
    local level="$1"
    local message="$2"
    local timestamp
    timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    echo "[$timestamp] [$level] - $message" >> "${LOG_FILE}"
}

function render_box() {
    local title="$1"
    local border="========================================"
    printf "%b%s%b\n" "${COLOR_BORDER}" "${border}" "${COLOR_RESET}"
    printf "%b%s%b\n" "${COLOR_SECTION}" "${title}" "${COLOR_RESET}"
    printf "%b%s%b\n" "${COLOR_BORDER}" "${border}" "${COLOR_RESET}"
}

function info() {
    local message="$1"
    log_message "INFO" "${message}"
    printf "%b[INFO]%b %s\n" "${COLOR_INFO}" "${COLOR_RESET}" "${message}"
}

function warn() {
    local message="$1"
    log_message "WARN" "${message}"
    printf "%b[WARN]%b %s\n" "${COLOR_WARN}" "${COLOR_RESET}" "${message}"
}

function error_msg() {
    local message="$1"
    log_message "ERROR" "${message}"
    printf "%b[ERROR]%b %s\n" "${COLOR_ERROR}" "${COLOR_RESET}" "${message}" >&2
}

function success() {
    local message="$1"
    log_message "INFO" "${message}"
    printf "%b[OK]%b %s\n" "${COLOR_SUCCESS}" "${COLOR_RESET}" "${message}"
}

function handle_error() {
    local exit_code=$?
    local line_number=$1
    local command="$2"

    error_msg "Échec à l'étape '${CURRENT_STEP}'"
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

    printf "%b### ÉCHEC CRITIQUE ###%b\n" "${COLOR_ERROR}" "${COLOR_RESET}"
    printf "%bUne erreur est survenue pendant '%s'.%b\n" "${COLOR_ERROR}" "${CURRENT_STEP}" "${COLOR_RESET}"
    printf "%bConsultez %s pour plus de détails.%b\n" "${COLOR_ERROR}" "${FAILURE_REPORT}" "${COLOR_RESET}"

    exit "${exit_code}"
}

trap 'handle_error $LINENO "$BASH_COMMAND"' ERR

function on_exit() {
    local exit_code=$?

    if [[ "${SERVICES_STOPPED}" == "true" && "${SERVICES_RESTORED}" != "true" ]]; then
        warn "Redémarrage automatique des services Klipper arrêtés suite à un incident."
        restart_klipper_services || true
    fi

    return "${exit_code}"
}

trap 'on_exit' EXIT

function detect_klipper_services() {
    ACTIVE_KLIPPER_SERVICES=()

    if ! command_exists systemctl; then
        info "systemctl est indisponible : aucun service Klipper géré automatiquement."
        return
    fi

    local candidates=("klipper.service" "klipper-mcu.service")
    for service in "${candidates[@]}"; do
        if systemctl status "${service}" >/dev/null 2>&1; then
            if systemctl is-active --quiet "${service}"; then
                ACTIVE_KLIPPER_SERVICES+=("${service}")
            fi
        fi
    done

    if [[ ${#ACTIVE_KLIPPER_SERVICES[@]} -gt 0 ]]; then
        info "Services Klipper actifs détectés: ${ACTIVE_KLIPPER_SERVICES[*]}"
    else
        info "Aucun service Klipper actif détecté."
    fi
}

function stop_klipper_services() {
    if [[ ${#ACTIVE_KLIPPER_SERVICES[@]} -eq 0 ]]; then
        return
    fi

    for service in "${ACTIVE_KLIPPER_SERVICES[@]}"; do
        info "Arrêt du service ${service}."
        if systemctl stop "${service}" >/dev/null 2>&1; then
            success "Service ${service} arrêté."
        else
            warn "Impossible d'arrêter ${service}. Vérifiez les permissions."
        fi
    done

    SERVICES_STOPPED="true"
}

function restart_klipper_services() {
    if [[ ${#ACTIVE_KLIPPER_SERVICES[@]} -eq 0 ]]; then
        SERVICES_RESTORED="true"
        return
    fi

    for service in "${ACTIVE_KLIPPER_SERVICES[@]}"; do
        info "Redémarrage du service ${service}."
        if systemctl start "${service}" >/dev/null 2>&1; then
            success "Service ${service} relancé."
        else
            warn "Impossible de relancer ${service}. Lancez 'systemctl start ${service}' manuellement."
        fi
    done

    SERVICES_RESTORED="true"
}

function command_exists() {
    local cmd="$1"
    if [[ "${cmd}" == */* ]]; then
        [[ -x "${cmd}" ]]
    else
        command -v "${cmd}" >/dev/null 2>&1
    fi
}

function check_command() {
    local cmd="$1"
    local mandatory="$2"

    if command_exists "${cmd}"; then
        success "${cmd} disponible."
        return 0
    fi

    if [[ "${mandatory}" == "true" ]]; then
        error_msg "La dépendance obligatoire '${cmd}' est introuvable."
        exit 1
    else
        warn "La dépendance optionnelle '${cmd}' est absente. Certaines fonctionnalités peuvent être limitées."
        return 1
    fi
}

function check_group_membership() {
    local group="$1"
    if id -nG "${USER}" 2>/dev/null | tr ' ' '\n' | grep -qx "${group}"; then
        success "Utilisateur membre du groupe '${group}'."
        return 0
    else
        warn "L'utilisateur courant n'appartient pas au groupe '${group}'. L'accès aux ports série peut être restreint."
        return 1
    fi
}

function check_device_write_access() {
    local device="$1"

    if [[ -z "${device}" ]]; then
        return 0
    fi

    if [[ -w "${device}" ]]; then
        success "Permissions d'écriture confirmées sur ${device}."
        return 0
    fi

    warn "Permissions insuffisantes pour écrire sur ${device}. Ajoutez l'utilisateur au groupe adéquat ou ajustez les règles udev."
    return 1
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

function detect_serial_devices() {
    local -n result=$1
    result=()

    if compgen -G "/dev/serial/by-id/*" >/dev/null 2>&1; then
        for path in /dev/serial/by-id/*; do
            [[ -e "${path}" ]] && result+=("${path}")
        done
    fi

    local patterns=(/dev/ttyUSB* /dev/ttyACM* /dev/ttyAMA* /dev/ttyS* /dev/ttyCH*)
    for pattern in "${patterns[@]}"; do
        for dev in ${pattern}; do
            [[ -e "${dev}" ]] && result+=("${dev}")
        done
    done

    if [[ ${#result[@]} -gt 0 ]]; then
        mapfile -t result < <(printf '%s\n' "${result[@]}" | awk '!seen[$0]++')
    fi
}

function detect_dfu_devices() {
    local -n result=$1
    result=()

    if ! command_exists dfu-util; then
        return
    fi

    while IFS= read -r line; do
        [[ -z "${line}" ]] && continue
        result+=("${line}")
    done < <(dfu-util -l 2>/dev/null | awk -F':' '/Found DFU:/{gsub(/^\s+|\s+$/, "", $2); print $2}' )
}

function display_available_devices() {
    local -a serial_devices
    local -a dfu_devices

    detect_serial_devices serial_devices
    detect_dfu_devices dfu_devices

    if [[ ${#serial_devices[@]} -eq 0 && ${#dfu_devices[@]} -eq 0 ]]; then
        warn "Aucun périphérique série ou DFU détecté pour le moment."
        return
    fi

    if [[ ${#serial_devices[@]} -gt 0 ]]; then
        info "Ports série détectés :"
        local index=1
        for dev in "${serial_devices[@]}"; do
            printf "    [%d] %s\n" "${index}" "${dev}"
            ((index++))
        done
    fi

    if [[ ${#dfu_devices[@]} -gt 0 ]]; then
        info "Périphériques DFU détectés (dfu-util) :"
        local index=1
        for dev in "${dfu_devices[@]}"; do
            printf "    [%d] %s\n" "${index}" "${dev}"
            ((index++))
        done
    fi
}

function format_path_for_display() {
    local path="$1"
    if [[ "${path}" == "${FLASH_ROOT}"* ]]; then
        printf "%s" "${path#${FLASH_ROOT}/}"
    else
        printf "%s" "${path}"
    fi
}

function verify_environment() {
    CURRENT_STEP="Étape 0: Diagnostic de l'environnement"
    render_box "${CURRENT_STEP}"
    info "Vérification des dépendances et des permissions."

    check_command "sha256sum" true
    check_command "stat" true
    check_command "find" true
    check_command "python3" false
    check_command "make" false

    check_group_membership "dialout" || true

    info "Analyse des périphériques série disponibles."
    display_available_devices
}

function collect_firmware_candidates() {
    local -n result=$1
    result=()

    declare -A seen
    local resolved_hint=""

    if [[ -n "${FIRMWARE_DISPLAY_PATH}" ]]; then
        resolved_hint="$(resolve_path_relative_to_flash_root "${FIRMWARE_DISPLAY_PATH}")"
        if [[ -f "${resolved_hint}" ]]; then
            seen["${resolved_hint}"]=1
            result+=("${resolved_hint}")
        elif [[ -d "${resolved_hint}" ]]; then
            local dir="${resolved_hint}"
            while IFS= read -r -d '' file; do
                [[ -n "${seen["${file}"]}" ]] && continue
                seen["${file}"]=1
                result+=("${file}")
            done < <(find "${dir}" -maxdepth 3 -type f \( -name '*.bin' -o -name '*.uf2' -o -name '*.elf' \) -print0 2>/dev/null)
        fi
    fi

    local default_dir="${FLASH_ROOT}/${DEFAULT_FIRMWARE_RELATIVE_PATH}"
    if [[ -d "${default_dir}" ]]; then
        while IFS= read -r -d '' file; do
            [[ -n "${seen["${file}"]}" ]] && continue
            seen["${file}"]=1
            result+=("${file}")
        done < <(find "${default_dir}" -maxdepth 2 -type f \( -name '*.bin' -o -name '*.uf2' -o -name '*.elf' \) -print0 2>/dev/null)
    fi

    local -a extra_search=("${FLASH_ROOT}")
    for dir in "${extra_search[@]}"; do
        [[ -d "${dir}" ]] || continue
        while IFS= read -r -d '' file; do
            [[ -n "${seen["${file}"]}" ]] && continue
            seen["${file}"]=1
            result+=("${file}")
        done < <(find "${dir}" -maxdepth 4 -type f \( -name '*.bin' -o -name '*.uf2' -o -name '*.elf' \) -print0 2>/dev/null)
    done

    if [[ ${#result[@]} -gt 0 ]]; then
        mapfile -t result < <(printf '%s\n' "${result[@]}" | awk '!seen[$0]++')
    fi
}

function prompt_firmware_selection() {
    local -n candidates=$1
    local choice=""

    while true; do
        echo
        echo "Sélectionnez le firmware à utiliser :"
        local index=1
        for file in "${candidates[@]}"; do
            local display
            display="$(format_path_for_display "${file}")"
            local extension="${file##*.}"
            printf "  [%d] %s (%s)\n" "${index}" "${display}" "${extension}";
            ((index++))
        done
        printf "  [%d] Saisir un chemin personnalisé\n" "${index}"

        read -rp "Votre choix : " answer

        if [[ "${answer}" =~ ^[0-9]+$ ]]; then
            local numeric=$((answer))
            if (( numeric >= 1 && numeric <= ${#candidates[@]} )); then
                choice="${candidates[$((numeric-1))]}"
                break
            elif (( numeric == index )); then
                read -rp "Chemin complet du firmware : " custom_path
                local resolved="$(resolve_path_relative_to_flash_root "${custom_path}")"
                if [[ -f "${resolved}" ]]; then
                    choice="${resolved}"
                    break
                fi
                error_msg "Le fichier spécifié est introuvable (${custom_path})."
            fi
        else
            local resolved="$(resolve_path_relative_to_flash_root "${answer}")"
            if [[ -f "${resolved}" ]]; then
                choice="${resolved}"
                break
            fi
            error_msg "Sélection invalide : ${answer}"
        fi
    done

    FIRMWARE_FILE="${choice}"
    FIRMWARE_DISPLAY_PATH="$(format_path_for_display "${FIRMWARE_FILE}")"
    FIRMWARE_FORMAT="${FIRMWARE_FILE##*.}"
}

function prepare_firmware() {
    CURRENT_STEP="Étape 1: Sélection du firmware"
    render_box "${CURRENT_STEP}"
    info "Recherche des artefacts firmware (.bin, .elf, .uf2)."

    local -a candidates
    collect_firmware_candidates candidates

    if [[ ${#candidates[@]} -eq 0 ]]; then
        error_msg "Aucun firmware compatible détecté dans ${DEFAULT_FIRMWARE_RELATIVE_PATH}. Lancer './build.sh' ou fournir KLIPPER_FIRMWARE_PATH."
        exit 1
    fi

    prompt_firmware_selection candidates

    FIRMWARE_SIZE=$(stat --printf="%s" "${FIRMWARE_FILE}")
    FIRMWARE_SHA=$(sha256sum "${FIRMWARE_FILE}" | awk '{print $1}')

    success "Firmware sélectionné : ${FIRMWARE_DISPLAY_PATH} (${FIRMWARE_FORMAT})"
    info "Taille : ${FIRMWARE_SIZE} octets"
    info "SHA256 : ${FIRMWARE_SHA}"
}

function select_flash_method() {
    CURRENT_STEP="Étape 2: Sélection de la méthode de flash"
    render_box "${CURRENT_STEP}"
    info "Choisissez la méthode adaptée à votre configuration."

    local options=(
        "Flash direct via wchisp (mode bootloader USB)"
        "Flash série via flash_usb.py (port /dev/tty*)"
        "Copie du firmware sur carte SD / stockage"
    )

    while true; do
        local index=1
        for option in "${options[@]}"; do
            printf "  [%d] %s\n" "${index}" "${option}"
            ((index++))
        done

        read -rp "Méthode choisie : " answer

        case "${answer}" in
            1)
                SELECTED_METHOD="wchisp"
                success "Méthode sélectionnée : flash direct via wchisp."
                ensure_wchisp
                break
                ;;
            2)
                SELECTED_METHOD="serial"
                success "Méthode sélectionnée : flash série."
                prompt_serial_device
                break
                ;;
            3)
                SELECTED_METHOD="sdcard"
                success "Méthode sélectionnée : copie sur carte SD."
                prompt_sdcard_mountpoint
                break
                ;;
            *)
                error_msg "Choix invalide (${answer})."
                ;;
        esac
    done
}

function prompt_serial_device() {
    local -a devices

    while true; do
        detect_serial_devices devices

        if [[ ${#devices[@]} -gt 0 ]]; then
            echo "Ports série détectés :"
            local index=1
            for dev in "${devices[@]}"; do
                printf "  [%d] %s\n" "${index}" "${dev}"
                ((index++))
            done
        else
            warn "Aucun port série détecté pour le moment."
        fi

        read -rp "Sélectionnez un port (numéro, chemin, 'r' pour rafraîchir) : " answer

        case "${answer}" in
            r|R)
                continue
                ;;
            "")
                warn "Veuillez sélectionner un port valide."
                ;;
            *)
                if [[ "${answer}" =~ ^[0-9]+$ && ${#devices[@]} -gt 0 ]]; then
                    local idx=$((answer))
                    if (( idx >= 1 && idx <= ${#devices[@]} )); then
                        SELECTED_DEVICE="${devices[$((idx-1))]}"
                        break
                    fi
                fi

                local candidate="${answer}"
                if [[ "${candidate}" != /* ]]; then
                    candidate="/dev/${candidate}"
                fi

                if [[ -e "${candidate}" ]]; then
                    SELECTED_DEVICE="${candidate}"
                    break
                fi

                error_msg "Port série invalide (${answer})."
                ;;
        esac
    done

    success "Port série sélectionné : ${SELECTED_DEVICE}"
    check_device_write_access "${SELECTED_DEVICE}" || true
}

function prompt_sdcard_mountpoint() {
    while true; do
        read -rp "Point de montage de la carte SD : " mountpoint
        [[ -z "${mountpoint}" ]] && { warn "Le chemin ne peut pas être vide."; continue; }

        local resolved="${mountpoint}"
        if [[ "${resolved}" != /* ]]; then
            resolved="$(resolve_path_relative_to_flash_root "${resolved}")"
        fi

        if [[ -d "${resolved}" && -w "${resolved}" ]]; then
            SDCARD_MOUNTPOINT="${resolved}"
            success "Carte SD détectée sur ${SDCARD_MOUNTPOINT}."
            break
        fi

        error_msg "Le chemin ${resolved} est introuvable ou non accessible en écriture."
    done
}

function prepare_target() {
    CURRENT_STEP="Étape 3: Préparation de la cible"
    render_box "${CURRENT_STEP}"

    case "${SELECTED_METHOD}" in
        wchisp)
            info "Mettre le BMCU-C en mode bootloader (BOOT0 + RESET)."
            display_available_devices
            cat <<'INSTRUCTIONS'
Actions recommandées :
  1. Maintenir BOOT0 enfoncé.
  2. Appuyer brièvement sur RESET.
  3. Relâcher BOOT0 puis attendre la détection USB.
INSTRUCTIONS
            read -rp "Appuyez sur Entrée après le passage en bootloader pour rescanner les périphériques..." _
            display_available_devices
            ;;
        serial)
            info "Validation du port série ${SELECTED_DEVICE}."
            if [[ ! -e "${SELECTED_DEVICE}" ]]; then
                warn "Le port sélectionné est introuvable."
                prompt_serial_device
            fi
            display_available_devices
            ;;
        sdcard)
            info "Préparez la carte SD montée sur ${SDCARD_MOUNTPOINT}."
            ;;
    esac
}

function flash_with_wchisp() {
    ensure_wchisp
    info "Début du flash via ${WCHISP_COMMAND} (cible ${WCHISP_TARGET})."
    local cmd=("${WCHISP_COMMAND}" -d "${WCHISP_DELAY}" -c "${WCHISP_TARGET}" flash "${FIRMWARE_FILE}")
    log_message "DEBUG" "Commande exécutée: ${cmd[*]}"
    "${cmd[@]}" 2>&1 | tee -a "${LOG_FILE}"
    success "wchisp a terminé le flash sans erreur."
}

function flash_with_serial() {
    if ! command_exists python3; then
        error_msg "python3 est requis pour la méthode de flash série."
        exit 1
    fi

    local flash_script="${FLASH_ROOT}/.cache/klipper/scripts/flash_usb.py"
    if [[ ! -f "${flash_script}" ]]; then
        error_msg "Le script ${flash_script} est introuvable. Lancez './build.sh' pour récupérer Klipper et recompiler le firmware."
        exit 1
    fi

    info "Flash USB via ${flash_script} sur ${SELECTED_DEVICE}."
    local cmd=(python3 "${flash_script}" -d "${SELECTED_DEVICE}" -f "${FIRMWARE_FILE}")
    log_message "DEBUG" "Commande exécutée: ${cmd[*]}"
    "${cmd[@]}" 2>&1 | tee -a "${LOG_FILE}"
    success "flash_usb.py a terminé sans erreur."
}

function flash_with_sdcard() {
    local destination="${SDCARD_MOUNTPOINT}/$(basename "${FIRMWARE_FILE}")"
    info "Copie de ${FIRMWARE_DISPLAY_PATH} vers ${destination}."
    if ! cp "${FIRMWARE_FILE}" "${destination}"; then
        error_msg "Échec de la copie du firmware vers ${destination}."
        exit 1
    fi
    sync
    success "Firmware copié sur la carte SD (${destination})."
}

function execute_flash() {
    CURRENT_STEP="Étape 4: Flashage (${SELECTED_METHOD})"
    render_box "${CURRENT_STEP}"

    case "${SELECTED_METHOD}" in
        wchisp)
            flash_with_wchisp
            ;;
        serial)
            flash_with_serial
            ;;
        sdcard)
            flash_with_sdcard
            ;;
        *)
            error_msg "Méthode de flash inconnue: ${SELECTED_METHOD}"
            exit 1
            ;;
    esac
}

function post_flash() {
    CURRENT_STEP="Étape 5: Résumé"
    render_box "${CURRENT_STEP}"

    restart_klipper_services

    cat <<EOF
Résumé :
  - Firmware : ${FIRMWARE_DISPLAY_PATH}
  - Format   : ${FIRMWARE_FORMAT}
  - Taille   : ${FIRMWARE_SIZE} octets
  - SHA256   : ${FIRMWARE_SHA}
  - Méthode  : ${SELECTED_METHOD}
EOF

    if [[ "${SELECTED_METHOD}" == "serial" ]]; then
        echo "  - Port     : ${SELECTED_DEVICE}"
    elif [[ "${SELECTED_METHOD}" == "sdcard" ]]; then
        echo "  - Cible    : ${SDCARD_MOUNTPOINT}"
    fi

    echo
    success ">>> Procédure terminée avec succès. <<<"
    info "Les logs détaillés sont disponibles ici : ${LOG_FILE}"
    log_message "INFO" "Procédure complète terminée avec succès."
}

function main() {
    verify_environment
    prepare_firmware
    select_flash_method
    detect_klipper_services
    prepare_target
    stop_klipper_services
    execute_flash
    post_flash
}

main

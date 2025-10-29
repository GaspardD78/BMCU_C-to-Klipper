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

resolve_serial_port_path() {
    local raw_path="$1"
    if [[ -z "${raw_path}" ]]; then
        return
    fi

    local cleaned="${raw_path}"
    cleaned="${cleaned#/dev/}"

    if [[ "${raw_path}" == /* ]]; then
        printf '%s\n' "${raw_path}"
    else
        printf '/dev/%s\n' "${cleaned}"
    fi
}

if [[ -f "${LOGO_FILE}" ]]; then
    cat "${LOGO_FILE}"
    echo
fi

readonly LOG_BASE_DIR="${FLASH_ROOT}/logs"
readonly LOG_DIR="${LOG_BASE_DIR}/flash_$(date +%Y-%m-%d_%H-%M-%S)"
readonly LOG_FILE="${LOG_DIR}/flash.log"
readonly FAILURE_REPORT="${LOG_DIR}/FAILURE_REPORT.txt"
readonly DEFAULT_FIRMWARE_RELATIVE_PATHS=(".cache/klipper/out" ".cache/firmware")
readonly DEFAULT_FIRMWARE_RELATIVE_PATH="${DEFAULT_FIRMWARE_RELATIVE_PATHS[0]}"
readonly DEFAULT_FIRMWARE_EXCLUDE_RELATIVE_PATHS=("logs" "tests" ".cache/tools")
DEEP_SCAN_ENABLED="false"
declare -a FIRMWARE_SCAN_EXCLUDES=()
declare -a CLI_FIRMWARE_SCAN_EXCLUDES=()
FIRMWARE_DISPLAY_PATH="${KLIPPER_FIRMWARE_PATH:-}"
FIRMWARE_FILE=""
FIRMWARE_FORMAT=""
PRESELECTED_FIRMWARE_FILE=""
FIRMWARE_SELECTION_SOURCE=""
readonly TOOLS_ROOT="${CACHE_ROOT}/tools"
readonly WCHISP_CACHE_DIR="${TOOLS_ROOT}/wchisp"
readonly WCHISP_RELEASE="${WCHISP_RELEASE:-v0.3.0}"
readonly WCHISP_AUTO_INSTALL="${WCHISP_AUTO_INSTALL:-true}"
readonly WCHISP_BASE_URL="${WCHISP_BASE_URL:-https://github.com/ch32-rs/wchisp/releases/download}"
readonly WCHISP_CHECKSUM_FILE="${FLASH_ROOT}/wchisp_sha256sums.txt"
readonly WCHISP_ARCH_OVERRIDE="${WCHISP_ARCH_OVERRIDE:-}"
readonly WCHISP_FALLBACK_ARCHIVE_URL="${WCHISP_FALLBACK_ARCHIVE_URL:-}"
readonly WCHISP_FALLBACK_CHECKSUM="${WCHISP_FALLBACK_CHECKSUM:-}"
readonly WCHISP_FALLBACK_ARCHIVE_NAME="${WCHISP_FALLBACK_ARCHIVE_NAME:-}"
readonly WCHISP_MANUAL_DOC="${FLASH_ROOT}/docs/wchisp_manual_install.md"

WCHISP_ARCHIVE_CHECKSUM_OVERRIDE_DEFAULT="${WCHISP_ARCHIVE_CHECKSUM_OVERRIDE:-}"
ALLOW_UNVERIFIED_WCHISP_DEFAULT="${ALLOW_UNVERIFIED_WCHISP:-false}"
WCHISP_ARCHIVE_CHECKSUM_OVERRIDE=""
ALLOW_UNVERIFIED_WCHISP=""

WCHISP_COMMAND="${WCHISP_BIN:-wchisp}"
readonly WCHISP_TRANSPORT="${WCHISP_TRANSPORT:-usb}"
readonly WCHISP_USB_INDEX="${WCHISP_USB_INDEX:-}"
readonly WCHISP_SERIAL_PORT="${WCHISP_SERIAL_PORT:-}"
readonly WCHISP_SERIAL_BAUDRATE="${WCHISP_SERIAL_BAUDRATE:-}"
readonly DFU_ALT_SETTING="${DFU_ALT_SETTING:-0}"
readonly DFU_SERIAL_NUMBER="${DFU_SERIAL_NUMBER:-}"
readonly DFU_EXTRA_ARGS="${DFU_EXTRA_ARGS:-}"

CLI_METHOD_OVERRIDE=""
ENV_METHOD_OVERRIDE="${FLASH_AUTOMATION_METHOD:-}"
CLI_FIRMWARE_OVERRIDE=""
CLI_SERIAL_PORT_OVERRIDE=""
CLI_SDCARD_PATH_OVERRIDE=""
CLI_AUTO_CONFIRM_REQUESTED="false"
CLI_DRY_RUN_REQUESTED="false"

CLI_NO_COLOR_REQUESTED="false"
CLI_QUIET_REQUESTED="false"
QUIET_MODE="false"

DEFAULT_CACHE_HOME="${XDG_CACHE_HOME:-${HOME}/.cache}"
PERMISSIONS_CACHE_FILE="${BMCU_PERMISSION_CACHE_FILE:-${DEFAULT_CACHE_HOME}/bmcu_permissions.json}"
PERMISSIONS_CACHE_TTL_RAW="${BMCU_PERMISSION_CACHE_TTL:-3600}"
# Permet de forcer un backend spécifique pour la gestion du cache de permissions.
# Utilisé principalement pour les tests automatisés afin de simuler l'absence de python3.
PERMISSIONS_CACHE_BACKEND_OVERRIDE="${BMCU_PERMISSION_CACHE_BACKEND:-}"
if [[ "${PERMISSIONS_CACHE_TTL_RAW}" =~ ^[0-9]+$ ]]; then
    PERMISSIONS_CACHE_TTL="${PERMISSIONS_CACHE_TTL_RAW}"
else
    PERMISSIONS_CACHE_TTL=0
fi
PERMISSIONS_CACHE_MESSAGE=""

COLOR_RESET=""
COLOR_INFO=""
COLOR_WARN=""
COLOR_ERROR=""
COLOR_SUCCESS=""
COLOR_SECTION=""
COLOR_BORDER=""

CURRENT_STEP="Initialisation"
FIRMWARE_SIZE=""
FIRMWARE_SHA=""
SELECTED_METHOD=""
SELECTED_DEVICE=""
SDCARD_MOUNTPOINT=""
DEFAULT_METHOD=""
RESOLVED_METHOD=""
METHOD_SOURCE_LABEL=""
FORCED_METHOD="false"
AUTO_METHOD_REASON=""
DEPENDENCIES_VERIFIED_FOR_METHOD=""
AUTO_CONFIRM_MODE="false"
AUTO_CONFIRM_SOURCE=""
DRY_RUN_MODE="false"
DRY_RUN_SOURCE=""
SERIAL_SELECTION_SOURCE=""
SDCARD_SELECTION_SOURCE=""
declare -a ACTIVE_KLIPPER_SERVICES=()
SERVICES_STOPPED="false"
SERVICES_RESTORED="false"

readonly HOST_UNAME="$(uname -s 2>/dev/null || echo unknown)"
readonly HOST_OS="${FLASH_AUTOMATION_OS_OVERRIDE:-${HOST_UNAME}}"

STAT_COMMAND=""
STAT_COMMAND_FLAVOR=""
SHA256_COMMAND=""
SHA256_COMMAND_FLAVOR=""
DFU_UTIL_COMMAND="${DFU_UTIL_BIN:-}"

if [[ -n "${FLASH_AUTOMATION_SHA256_SKIP:-}" ]]; then
    IFS=',' read -r -a SHA256_SKIP_DEFAULT <<< "${FLASH_AUTOMATION_SHA256_SKIP}"
else
    SHA256_SKIP_DEFAULT=()
fi

mkdir -p "${LOG_DIR}"
touch "${LOG_FILE}"

normalize_boolean() {
    local raw_value="${1:-}"
    case "${raw_value}" in
        1|true|TRUE|True|yes|YES|on|ON)
            printf '%s\n' "true"
            ;;
        0|false|FALSE|False|no|NO|off|OFF|'')
            printf '%s\n' "false"
            ;;
        *)
            printf '%s\n' "false"
            ;;
    esac
}

configure_color_palette() {
    local enable_colors="false"

    if [[ "${CLI_NO_COLOR_REQUESTED}" == "true" ]]; then
        enable_colors="false"
    else
        local env_no_color
        env_no_color="$(normalize_boolean "${FLASH_AUTOMATION_NO_COLOR:-false}")"
        if [[ "${env_no_color}" != "true" && -t 1 ]]; then
            enable_colors="true"
        fi
    fi

    if [[ "${enable_colors}" == "true" ]]; then
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
}

dedupe_array_in_place() {
    local -n array_ref=$1
    if [[ ${#array_ref[@]} -eq 0 ]]; then
        return
    fi

    declare -A seen_paths=()
    local -a unique=()
    for element in "${array_ref[@]}"; do
        [[ -n "${element}" ]] || continue
        if [[ -z "${seen_paths["${element}"]-}" ]]; then
            seen_paths["${element}"]=1
            unique+=("${element}")
        fi
    done

    array_ref=("${unique[@]}")
}

normalize_flash_method() {
    local raw="${1:-}"
    local lowered="${raw,,}"
    lowered="${lowered// /}"

    case "${lowered}" in
        ""|auto)
            printf '%s\n' "auto"
            ;;
        wchisp|usb|bootloader)
            printf '%s\n' "wchisp"
            ;;
        serial|uart|usb-serial|usbserial)
            printf '%s\n' "serial"
            ;;
        sd|sdcard|storage)
            printf '%s\n' "sdcard"
            ;;
        dfu|dfu-util|dfuutil)
            printf '%s\n' "dfu"
            ;;
        *)
            return 1
            ;;
    esac
}

print_usage() {
    local script_name
    script_name="$(basename "${BASH_SOURCE[0]}")"
    cat <<EOF
Usage: ${script_name} [options]

Options:
  --wchisp-checksum <sha256>   Remplace la somme de contrôle attendue pour l'archive wchisp.
  --allow-unsigned-wchisp      Active le mode dégradé : conserve l'archive même si la vérification échoue.
  --firmware <chemin>          Sélectionne directement le firmware à flasher.
  --method <mode>              Force la méthode (wchisp, serial, sdcard, dfu, auto).
  --serial-port <chemin>       Fixe le port série à utiliser pour flash_usb.py.
  --sdcard-path <chemin>       Fixe le point de montage cible pour la copie sur carte SD.
  --deep-scan                  Étend la recherche de firmwares à l'ensemble du dépôt.
  --exclude-path <chemin>      Ajoute un chemin à exclure de la découverte automatique.
  --auto-confirm               Accepte automatiquement les choix suggérés (mode non interactif).
  --no-confirm                 Alias de --auto-confirm.
  --dry-run                    Valide l'enchaînement des étapes sans appliquer les actions destructrices.
  --quiet                      Réduit les sorties console aux avertissements et erreurs.
  --no-color                   Désactive les couleurs ANSI, même sur un terminal interactif.
  -h, --help                   Affiche cette aide et quitte.

Variables d'environnement associées :
  FLASH_AUTOMATION_METHOD            Définit la méthode par défaut (wchisp|serial|sdcard|dfu|auto).
  FLASH_AUTOMATION_AUTO_CONFIRM      "true"/"1" pour activer le mode non interactif.
  FLASH_AUTOMATION_DRY_RUN           Active le mode simulation sans flash réel.
  FLASH_AUTOMATION_SERIAL_PORT       Port série forcé (équivalent --serial-port).
  FLASH_AUTOMATION_SDCARD_PATH       Point de montage forcé pour la méthode sdcard.
  FLASH_AUTOMATION_QUIET             "true"/"1" pour réduire les sorties console.
  FLASH_AUTOMATION_NO_COLOR          "true"/"1" pour forcer la sortie sans couleurs.
  WCHISP_ARCHIVE_CHECKSUM_OVERRIDE  Injecte une somme de contrôle SHA-256 personnalisée.
  ALLOW_UNVERIFIED_WCHISP           "true"/"1" pour autoriser le mode dégradé.
  KLIPPER_FIRMWARE_SCAN_EXCLUDES    Liste (séparée par ':') de chemins à ignorer durant la découverte.
  DFU_ALT_SETTING                   Sélectionne l'interface DFU (par défaut : 0).
  DFU_SERIAL_NUMBER                 Filtre dfu-util sur un numéro de série spécifique.
  DFU_EXTRA_ARGS                    Arguments supplémentaires passés à dfu-util.

Scénarios & dépendances clés :
  wchisp (auto-install)        curl, tar, sha256sum (pour vérifier et extraire l'archive).
  wchisp (local)              wchisp déjà présent dans le PATH ou via WCHISP_BIN.
  serial (flash_usb.py)       python3, build Klipper préalable pour obtenir flash_usb.py.
  dfu                         dfu-util.
  sdcard                      Aucun outil supplémentaire : simple copie du firmware.
EOF
}

parse_cli_arguments() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --wchisp-checksum)
                if [[ $# -lt 2 ]]; then
                    echo "L'option --wchisp-checksum requiert une valeur." >&2
                    print_usage >&2
                    exit 1
                fi
                WCHISP_ARCHIVE_CHECKSUM_OVERRIDE="$2"
                shift 2
                ;;
            --wchisp-checksum=*)
                WCHISP_ARCHIVE_CHECKSUM_OVERRIDE="${1#*=}"
                shift
                ;;
            --allow-unsigned-wchisp)
                ALLOW_UNVERIFIED_WCHISP="true"
                shift
                ;;
            --firmware)
                if [[ $# -lt 2 ]]; then
                    echo "L'option --firmware requiert un chemin." >&2
                    print_usage >&2
                    exit 1
                fi
                CLI_FIRMWARE_OVERRIDE="$(resolve_path_relative_to_flash_root "$2")"
                shift 2
                ;;
            --firmware=*)
                local raw_firmware="${1#*=}"
                if [[ -z "${raw_firmware}" ]]; then
                    echo "L'option --firmware nécessite un chemin non vide." >&2
                    print_usage >&2
                    exit 1
                fi
                CLI_FIRMWARE_OVERRIDE="$(resolve_path_relative_to_flash_root "${raw_firmware}")"
                shift
                ;;
            --method)
                if [[ $# -lt 2 ]]; then
                    echo "L'option --method requiert une valeur." >&2
                    print_usage >&2
                    exit 1
                fi
                if ! CLI_METHOD_OVERRIDE=$(normalize_flash_method "$2"); then
                    echo "Méthode inconnue : $2" >&2
                    print_usage >&2
                    exit 1
                fi
                shift 2
                ;;
            --method=*)
                local raw_method="${1#*=}"
                if ! CLI_METHOD_OVERRIDE=$(normalize_flash_method "${raw_method}"); then
                    echo "Méthode inconnue : ${raw_method}" >&2
                    print_usage >&2
                    exit 1
                fi
                shift
                ;;
            --serial-port)
                if [[ $# -lt 2 ]]; then
                    echo "L'option --serial-port requiert une valeur." >&2
                    print_usage >&2
                    exit 1
                fi
                CLI_SERIAL_PORT_OVERRIDE="$2"
                shift 2
                ;;
            --serial-port=*)
                CLI_SERIAL_PORT_OVERRIDE="${1#*=}"
                shift
                ;;
            --sdcard-path)
                if [[ $# -lt 2 ]]; then
                    echo "L'option --sdcard-path requiert une valeur." >&2
                    print_usage >&2
                    exit 1
                fi
                CLI_SDCARD_PATH_OVERRIDE="$(resolve_path_relative_to_flash_root "$2")"
                shift 2
                ;;
            --sdcard-path=*)
                local raw_mount="${1#*=}"
                if [[ -z "${raw_mount}" ]]; then
                    echo "L'option --sdcard-path nécessite un chemin non vide." >&2
                    print_usage >&2
                    exit 1
                fi
                CLI_SDCARD_PATH_OVERRIDE="$(resolve_path_relative_to_flash_root "${raw_mount}")"
                shift
                ;;
            --auto-confirm|--no-confirm)
                CLI_AUTO_CONFIRM_REQUESTED="true"
                shift
                ;;
            --dry-run)
                CLI_DRY_RUN_REQUESTED="true"
                shift
                ;;
            --quiet)
                CLI_QUIET_REQUESTED="true"
                shift
                ;;
            --no-color)
                CLI_NO_COLOR_REQUESTED="true"
                shift
                ;;
            --deep-scan)
                DEEP_SCAN_ENABLED="true"
                shift
                ;;
            --exclude-path)
                if [[ $# -lt 2 ]]; then
                    echo "L'option --exclude-path requiert une valeur." >&2
                    print_usage >&2
                    exit 1
                fi
                CLI_FIRMWARE_SCAN_EXCLUDES+=("$(resolve_path_relative_to_flash_root "$2")")
                shift 2
                ;;
            --exclude-path=*)
                local raw_path="${1#*=}"
                if [[ -z "${raw_path}" ]]; then
                    echo "L'option --exclude-path nécessite un chemin non vide." >&2
                    print_usage >&2
                    exit 1
                fi
                CLI_FIRMWARE_SCAN_EXCLUDES+=("$(resolve_path_relative_to_flash_root "${raw_path}")")
                shift
                ;;
            -h|--help)
                print_usage
                exit 0
                ;;
            --)
                shift
                break
                ;;
            -*|+*)
                echo "Option inconnue : $1" >&2
                print_usage >&2
                exit 1
                ;;
            *)
                echo "Argument inattendu : $1" >&2
                print_usage >&2
                exit 1
                ;;
        esac
    done

    if [[ $# -gt 0 ]]; then
        echo "Arguments supplémentaires non pris en charge : $*" >&2
        print_usage >&2
        exit 1
    fi
}

apply_configuration_defaults() {
    if [[ -z "${ALLOW_UNVERIFIED_WCHISP}" ]]; then
        ALLOW_UNVERIFIED_WCHISP="${ALLOW_UNVERIFIED_WCHISP_DEFAULT}"
    fi
    ALLOW_UNVERIFIED_WCHISP="$(normalize_boolean "${ALLOW_UNVERIFIED_WCHISP}")"

    if [[ -z "${WCHISP_ARCHIVE_CHECKSUM_OVERRIDE}" ]]; then
        WCHISP_ARCHIVE_CHECKSUM_OVERRIDE="${WCHISP_ARCHIVE_CHECKSUM_OVERRIDE_DEFAULT}"
    fi

    local -a excludes=()
    for rel_path in "${DEFAULT_FIRMWARE_EXCLUDE_RELATIVE_PATHS[@]}"; do
        excludes+=("$(resolve_path_relative_to_flash_root "${rel_path}")")
    done

    if [[ -n "${KLIPPER_FIRMWARE_SCAN_EXCLUDES:-}" ]]; then
        local old_ifs="${IFS}"
        IFS=':'
        read -r -a env_excludes <<< "${KLIPPER_FIRMWARE_SCAN_EXCLUDES}"
        IFS="${old_ifs}"
        for raw in "${env_excludes[@]}"; do
            [[ -n "${raw}" ]] || continue
            excludes+=("$(resolve_path_relative_to_flash_root "${raw}")")
        done
    fi

    if [[ ${#CLI_FIRMWARE_SCAN_EXCLUDES[@]} -gt 0 ]]; then
        excludes+=("${CLI_FIRMWARE_SCAN_EXCLUDES[@]}")
    fi

    FIRMWARE_SCAN_EXCLUDES=("${excludes[@]}")
    dedupe_array_in_place FIRMWARE_SCAN_EXCLUDES

    PRESELECTED_FIRMWARE_FILE=""
    FIRMWARE_SELECTION_SOURCE=""
    SERIAL_SELECTION_SOURCE=""
    SDCARD_SELECTION_SOURCE=""

    if [[ "${CLI_AUTO_CONFIRM_REQUESTED}" == "true" ]]; then
        AUTO_CONFIRM_MODE="true"
        AUTO_CONFIRM_SOURCE="option CLI (--auto-confirm)"
    else
        AUTO_CONFIRM_MODE="$(normalize_boolean "${FLASH_AUTOMATION_AUTO_CONFIRM:-false}")"
        if [[ "${AUTO_CONFIRM_MODE}" == "true" ]]; then
            AUTO_CONFIRM_SOURCE="variable d'environnement FLASH_AUTOMATION_AUTO_CONFIRM"
        fi
    fi

    if [[ "${CLI_DRY_RUN_REQUESTED}" == "true" ]]; then
        DRY_RUN_MODE="true"
        DRY_RUN_SOURCE="option CLI (--dry-run)"
    else
        DRY_RUN_MODE="$(normalize_boolean "${FLASH_AUTOMATION_DRY_RUN:-false}")"
        if [[ "${DRY_RUN_MODE}" == "true" ]]; then
            DRY_RUN_SOURCE="variable d'environnement FLASH_AUTOMATION_DRY_RUN"
        fi
    fi

    if [[ "${CLI_QUIET_REQUESTED}" == "true" ]]; then
        QUIET_MODE="true"
    else
        QUIET_MODE="$(normalize_boolean "${FLASH_AUTOMATION_QUIET:-false}")"
    fi

    if [[ "${DRY_RUN_MODE}" == "true" ]]; then
        AUTO_CONFIRM_MODE="true"
        if [[ -z "${AUTO_CONFIRM_SOURCE}" ]]; then
            AUTO_CONFIRM_SOURCE="mode --dry-run"
        fi
    fi

    if [[ -n "${CLI_FIRMWARE_OVERRIDE}" ]]; then
        if [[ ! -f "${CLI_FIRMWARE_OVERRIDE}" ]]; then
            error_msg "Le firmware spécifié (--firmware) est introuvable : ${CLI_FIRMWARE_OVERRIDE}"
            exit 1
        fi
        PRESELECTED_FIRMWARE_FILE="${CLI_FIRMWARE_OVERRIDE}"
        FIRMWARE_SELECTION_SOURCE="option CLI (--firmware)"
        FIRMWARE_DISPLAY_PATH="$(format_path_for_display "${PRESELECTED_FIRMWARE_FILE}")"
    elif [[ -n "${KLIPPER_FIRMWARE_PATH:-}" ]]; then
        local resolved_hint
        resolved_hint="$(resolve_path_relative_to_flash_root "${KLIPPER_FIRMWARE_PATH}")"
        if [[ -f "${resolved_hint}" ]]; then
            PRESELECTED_FIRMWARE_FILE="${resolved_hint}"
            FIRMWARE_SELECTION_SOURCE="variable d'environnement KLIPPER_FIRMWARE_PATH"
            FIRMWARE_DISPLAY_PATH="$(format_path_for_display "${PRESELECTED_FIRMWARE_FILE}")"
        else
            FIRMWARE_DISPLAY_PATH="${KLIPPER_FIRMWARE_PATH}"
        fi
    fi

    local serial_candidate=""
    local serial_source=""
    if [[ -n "${CLI_SERIAL_PORT_OVERRIDE}" ]]; then
        serial_candidate="$(resolve_serial_port_path "${CLI_SERIAL_PORT_OVERRIDE}")"
        serial_source="option CLI (--serial-port)"
    elif [[ -n "${FLASH_AUTOMATION_SERIAL_PORT:-}" ]]; then
        serial_candidate="$(resolve_serial_port_path "${FLASH_AUTOMATION_SERIAL_PORT}")"
        serial_source="variable d'environnement FLASH_AUTOMATION_SERIAL_PORT"
    fi

    SELECTED_DEVICE="${serial_candidate}"
    SERIAL_SELECTION_SOURCE="${serial_source}"

    local sdcard_candidate=""
    local sdcard_source=""
    if [[ -n "${CLI_SDCARD_PATH_OVERRIDE}" ]]; then
        sdcard_candidate="${CLI_SDCARD_PATH_OVERRIDE}"
        sdcard_source="option CLI (--sdcard-path)"
    elif [[ -n "${FLASH_AUTOMATION_SDCARD_PATH:-}" ]]; then
        sdcard_candidate="$(resolve_path_relative_to_flash_root "${FLASH_AUTOMATION_SDCARD_PATH}")"
        sdcard_source="variable d'environnement FLASH_AUTOMATION_SDCARD_PATH"
    fi

    if [[ -n "${sdcard_candidate}" ]]; then
        if [[ ! -d "${sdcard_candidate}" ]]; then
            if [[ "${DRY_RUN_MODE}" == "true" ]]; then
                warn "Point de montage fourni introuvable (${sdcard_candidate}); poursuite en mode --dry-run."
            else
                error_msg "Le point de montage spécifié est introuvable : ${sdcard_candidate}"
                exit 1
            fi
        fi
    fi

    SDCARD_MOUNTPOINT="${sdcard_candidate}"
    SDCARD_SELECTION_SOURCE="${sdcard_source}"

    configure_color_palette
}

function log_message() {
    local level="$1"
    local message="$2"
    local timestamp
    timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    echo "[$timestamp] [$level] - $message" >> "${LOG_FILE}"
}

detect_wchisp_machine() {
    if [[ -n "${WCHISP_ARCH_OVERRIDE}" ]]; then
        printf '%s\n' "${WCHISP_ARCH_OVERRIDE}"
        return
    fi

    uname -m
}

normalize_wchisp_machine() {
    local raw="$1"

    case "${raw}" in
        amd64)
            printf '%s\n' "x86_64"
            ;;
        arm64)
            printf '%s\n' "aarch64"
            ;;
        armv8l|armv7|armv7l|armhf)
            printf '%s\n' "armv7l"
            ;;
        armv6|armv6l|armel)
            printf '%s\n' "armv6l"
            ;;
        i386|i486|i586|i686)
            printf '%s\n' "i686"
            ;;
        *)
            printf '%s\n' "${raw}"
            ;;
    esac
}

wchisp_architecture_not_supported() {
    local arch="$1"

    log_message "ERROR" "Aucun binaire wchisp pré-compilé disponible pour ${arch}."
    cat <<EOF >&2
Aucun binaire wchisp pré-compilé n'est disponible pour l'architecture '${arch}'.
Vous pouvez :
  1. Compiler wchisp depuis les sources (voir ${WCHISP_MANUAL_DOC}).
  2. Fournir une archive compatible via WCHISP_FALLBACK_ARCHIVE_URL et, si possible, WCHISP_FALLBACK_CHECKSUM
     (ajoutez WCHISP_FALLBACK_ARCHIVE_NAME si l'URL comporte des paramètres).
  3. Exporter WCHISP_BIN vers un binaire wchisp déjà installé sur votre système.

Pour simuler une architecture différente (tests ou CI), exportez WCHISP_ARCH_OVERRIDE.
EOF
    return 1
}

resolve_wchisp_download() {
    local raw_arch normalized_arch asset url mode checksum

    raw_arch="$(detect_wchisp_machine)"
    normalized_arch="$(normalize_wchisp_machine "${raw_arch}")"
    mode="official"
    checksum=""

    case "${normalized_arch}" in
        x86_64)
            asset="wchisp-${WCHISP_RELEASE}-linux-x64.tar.gz"
            url="${WCHISP_BASE_URL}/${WCHISP_RELEASE}/${asset}"
            ;;
        aarch64)
            asset="wchisp-${WCHISP_RELEASE}-linux-aarch64.tar.gz"
            url="${WCHISP_BASE_URL}/${WCHISP_RELEASE}/${asset}"
            ;;
        armv7l|armv6l|i686)
            if [[ -n "${WCHISP_FALLBACK_ARCHIVE_URL}" ]]; then
                asset="${WCHISP_FALLBACK_ARCHIVE_NAME:-${WCHISP_FALLBACK_ARCHIVE_URL##*/}}"
                asset="${asset%%\?*}"
                url="${WCHISP_FALLBACK_ARCHIVE_URL}"
                mode="fallback"
                checksum="${WCHISP_FALLBACK_CHECKSUM}"
                log_message "WARN" "Utilisation de l'archive de secours pour ${raw_arch} (${asset})."
            else
                wchisp_architecture_not_supported "${raw_arch}" || true
                return 1
            fi
            ;;
        *)
            if [[ -n "${WCHISP_FALLBACK_ARCHIVE_URL}" ]]; then
                asset="${WCHISP_FALLBACK_ARCHIVE_NAME:-${WCHISP_FALLBACK_ARCHIVE_URL##*/}}"
                asset="${asset%%\?*}"
                url="${WCHISP_FALLBACK_ARCHIVE_URL}"
                mode="fallback"
                checksum="${WCHISP_FALLBACK_CHECKSUM}"
                log_message "WARN" "Architecture ${raw_arch} non prise en charge officiellement; utilisation de l'archive de secours (${asset})."
            else
                wchisp_architecture_not_supported "${raw_arch}" || true
                return 1
            fi
            ;;
    esac

    if [[ -z "${asset}" ]]; then
        error_msg "Impossible de déterminer le nom de l'archive wchisp pour ${raw_arch}."
        printf "Définissez WCHISP_FALLBACK_ARCHIVE_URL avec une URL complète vers une archive wchisp valide.\n" >&2
        return 1
    fi

    printf '%s|%s|%s|%s|%s|%s\n' "${raw_arch}" "${normalized_arch}" "${asset}" "${url}" "${mode}" "${checksum}"
}

function format_duration_seconds() {
    local total_seconds="$1"
    if ! [[ "${total_seconds}" =~ ^[0-9]+$ ]]; then
        printf '%s' "0s"
        return
    fi

    local hours=$(( total_seconds / 3600 ))
    local minutes=$(( (total_seconds % 3600) / 60 ))
    local seconds=$(( total_seconds % 60 ))
    local -a parts=()

    if (( hours > 0 )); then
        parts+=("${hours}h")
    fi
    if (( minutes > 0 )); then
        parts+=("${minutes}m")
    fi
    if (( seconds > 0 )) || (( ${#parts[@]} == 0 )); then
        parts+=("${seconds}s")
    fi

    local IFS=' '
    printf '%s' "${parts[*]}"
}

function permissions_cache_enabled() {
    [[ "${PERMISSIONS_CACHE_TTL}" -gt 0 ]] && [[ -n "${PERMISSIONS_CACHE_FILE}" ]]
}

# Lorsque python3 est absent (ou explicitement désactivé via BMCU_PERMISSION_CACHE_BACKEND=bash),
# le cache de permissions est lu/écrit au format TSV à l'aide des fonctions Bash ci-dessous.
# Ce mode dégradé conserve uniquement les informations essentielles : statut, timestamp, TTL, origine et message.
permissions_cache_use_python() {
    case "${PERMISSIONS_CACHE_BACKEND_OVERRIDE}" in
        python)
            return 0
            ;;
        bash)
            return 1
            ;;
    esac

    if command -v python3 >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

permissions_cache_epoch_seconds() {
    local now
    if now=$(date -u +%s 2>/dev/null); then
        printf '%s\n' "${now}"
    elif now=$(date +%s 2>/dev/null); then
        printf '%s\n' "${now}"
    else
        return 1
    fi
}

permissions_cache_sanitize_field() {
    local value="$1"
    value="${value//$'\n'/ }"
    value="${value//$'\r'/ }"
    value="${value//$'\t'/ }"
    printf '%s' "${value}"
}

permissions_cache_read_bash() {
    local path="${PERMISSIONS_CACHE_FILE}"
    local status checked_epoch stored_ttl origin extra

    if [[ ! -s "${path}" ]]; then
        return 1
    fi

    IFS=$'\t' read -r status checked_epoch stored_ttl origin extra < "${path}" || return 1

    if [[ "${status}" != "ok" ]]; then
        return 1
    fi

    if [[ -z "${checked_epoch}" ]] || [[ ! "${checked_epoch}" =~ ^[0-9]+$ ]]; then
        return 1
    fi

    local ttl="${PERMISSIONS_CACHE_TTL}"
    if [[ -n "${stored_ttl}" ]] && [[ "${stored_ttl}" =~ ^[0-9]+$ ]]; then
        ttl="${stored_ttl}"
    fi

    if [[ "${ttl}" -le 0 ]]; then
        return 1
    fi

    local now
    if ! now="$(permissions_cache_epoch_seconds)"; then
        return 1
    fi

    local age=$(( now - checked_epoch ))
    if (( age < 0 )); then
        age=0
    fi

    if (( age >= ttl )); then
        return 1
    fi

    local remaining=$(( ttl - age ))
    local origin_note=""
    if [[ -n "${origin}" ]]; then
        origin_note=" — source ${origin}"
    fi

    if [[ -n "${extra}" ]]; then
        origin_note+=" — ${extra}"
    fi

    PERMISSIONS_CACHE_MESSAGE="cache valide (vérifié il y a $(format_duration_seconds "${age}"); expiration dans $(format_duration_seconds "${remaining}"))${origin_note}"
    return 0
}

permissions_cache_write_bash() {
    local status="$1"
    local message="$2"
    local origin_override="${3:-}"
    local ttl="${PERMISSIONS_CACHE_TTL}"
    local origin="${origin_override:-${PERMISSIONS_ORIGIN:-flash_automation.sh}}"

    if [[ "${ttl}" -le 0 ]]; then
        return 0
    fi

    local now
    if ! now="$(permissions_cache_epoch_seconds)"; then
        return 1
    fi

    local sanitized_message
    sanitized_message="$(permissions_cache_sanitize_field "${message}")"
    origin="$(permissions_cache_sanitize_field "${origin}")"

    local cache_dir
    cache_dir="$(dirname "${PERMISSIONS_CACHE_FILE}")"
    if [[ -n "${cache_dir}" ]] && [[ "${cache_dir}" != "." ]]; then
        mkdir -p "${cache_dir}" || return 1
    fi

    if ! printf '%s\t%s\t%s\t%s\t%s\n' "${status}" "${now}" "${ttl}" "${origin}" "${sanitized_message}" > "${PERMISSIONS_CACHE_FILE}"; then
        return 1
    fi
}

function should_skip_permission_checks() {
    PERMISSIONS_CACHE_MESSAGE=""
    if ! permissions_cache_enabled; then
        return 1
    fi
    if [[ ! -f "${PERMISSIONS_CACHE_FILE}" ]]; then
        return 1
    fi

    if ! permissions_cache_use_python; then
        if permissions_cache_read_bash; then
            return 0
        fi
        return 1
    fi

    local output
    if ! output=$(PERMISSIONS_CACHE_FILE="${PERMISSIONS_CACHE_FILE}" PERMISSIONS_CACHE_TTL="${PERMISSIONS_CACHE_TTL}" python3 - <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

path = os.environ["PERMISSIONS_CACHE_FILE"]
try:
    ttl = int(os.environ["PERMISSIONS_CACHE_TTL"])
except (KeyError, ValueError):
    sys.exit(1)

if ttl <= 0:
    sys.exit(1)

try:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
except Exception:
    sys.exit(1)

if data.get("status") != "ok":
    sys.exit(1)

checked_raw = data.get("checked_at")
if not isinstance(checked_raw, str):
    sys.exit(1)

try:
    checked = datetime.fromisoformat(checked_raw)
except ValueError:
    sys.exit(1)

if checked.tzinfo is None:
    checked = checked.replace(tzinfo=timezone.utc)

now = datetime.now(timezone.utc)
age = (now - checked).total_seconds()
if age < 0:
    age = 0

if age >= ttl:
    sys.exit(1)

remaining = ttl - age

def format_duration(value: float) -> str:
    total = max(int(round(value)), 0)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)

print(
    f"cache valide (vérifié il y a {format_duration(age)}; "
    f"expiration dans {format_duration(remaining)})"
)
PY
    ); then
        return 1
    fi
    PERMISSIONS_CACHE_MESSAGE="${output}"
    return 0
}

function update_permissions_cache() {
    local status="$1"
    local message="$2"

    if ! permissions_cache_enabled; then
        return
    fi

    if ! permissions_cache_use_python; then
        if ! permissions_cache_write_bash "${status}" "${message}" "flash_automation.verify_environment"; then
            warn "Impossible de mettre à jour le cache de permissions (${PERMISSIONS_CACHE_FILE})."
            return 1
        fi
        return 0
    fi

    if ! PERMISSIONS_STATUS="${status}" \
        PERMISSIONS_MESSAGE="${message}" \
        PERMISSIONS_ORIGIN="flash_automation.verify_environment" \
        PERMISSIONS_CACHE_FILE="${PERMISSIONS_CACHE_FILE}" \
        PERMISSIONS_CACHE_TTL="${PERMISSIONS_CACHE_TTL}" python3 - <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

path = os.environ["PERMISSIONS_CACHE_FILE"]
try:
    ttl = int(os.environ["PERMISSIONS_CACHE_TTL"])
except (KeyError, ValueError):
    sys.exit(0)

if ttl <= 0:
    sys.exit(0)

payload = {
    "status": os.environ.get("PERMISSIONS_STATUS", "ok"),
    "checked_at": datetime.now(timezone.utc).isoformat(),
    "origin": os.environ.get("PERMISSIONS_ORIGIN", "flash_automation.sh"),
    "ttl_seconds": ttl,
}

message = os.environ.get("PERMISSIONS_MESSAGE", "")
if message:
    payload["message"] = message

cache_dir = os.path.dirname(path) or "."
try:
    os.makedirs(cache_dir, exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)
except Exception:
    sys.exit(1)
else:
    sys.exit(0)
PY
    then
        warn "Impossible de mettre à jour le cache de permissions (${PERMISSIONS_CACHE_FILE})."
        return 1
    fi
    return 0
}

function invalidate_permissions_cache() {
    if permissions_cache_enabled && [[ -f "${PERMISSIONS_CACHE_FILE}" ]]; then
        rm -f "${PERMISSIONS_CACHE_FILE}" || true
    fi
}

function render_box() {
    local title="$1"
    local border="========================================"
    if [[ "${QUIET_MODE}" == "true" ]]; then
        return
    fi
    printf "%b%s%b\n" "${COLOR_BORDER}" "${border}" "${COLOR_RESET}"
    printf "%b%s%b\n" "${COLOR_SECTION}" "${title}" "${COLOR_RESET}"
    printf "%b%s%b\n" "${COLOR_BORDER}" "${border}" "${COLOR_RESET}"
}

function info() {
    local message="$1"
    log_message "INFO" "${message}"
    if [[ "${QUIET_MODE}" != "true" ]]; then
        printf "%b[INFO]%b %s\n" "${COLOR_INFO}" "${COLOR_RESET}" "${message}"
    fi
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
    if [[ "${QUIET_MODE}" != "true" ]]; then
        printf "%b[OK]%b %s\n" "${COLOR_SUCCESS}" "${COLOR_RESET}" "${message}"
    fi
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

    if [[ "${DRY_RUN_MODE}" == "true" ]]; then
        for service in "${ACTIVE_KLIPPER_SERVICES[@]}"; do
            info "[DRY-RUN] Service ${service} serait arrêté."
        done
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

    if [[ "${DRY_RUN_MODE}" == "true" ]]; then
        for service in "${ACTIVE_KLIPPER_SERVICES[@]}"; do
            info "[DRY-RUN] Service ${service} serait relancé."
        done
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

function command_install_hint() {
    local cmd="$1"

    local os_hint="${HOST_OS}"

    case "${cmd}" in
        sha256sum|gsha256sum|stat|gstat)
            if [[ "${os_hint}" == "Darwin" ]]; then
                printf "Installez coreutils via Homebrew : brew install coreutils."
            else
                printf "Installez le paquet fournissant '%s' (ex: sudo apt install coreutils)." "${cmd}"
            fi
            ;;
        find)
            if [[ "${os_hint}" == "Darwin" ]]; then
                printf "Installez GNU findutils via Homebrew : brew install findutils."
            else
                printf "Installez le paquet fournissant 'find' (ex: sudo apt install findutils)."
            fi
            ;;
        dfu-util|dfu-util-static)
            if [[ "${os_hint}" == "Darwin" ]]; then
                printf "Installez dfu-util via Homebrew : brew install dfu-util."
            else
                printf "Installez dfu-util (ex: sudo apt install dfu-util)."
            fi
            ;;
        make)
            printf "Installez les outils de compilation (ex: sudo apt install build-essential)."
            ;;
        python3)
            if [[ "${os_hint}" == "Darwin" ]]; then
                printf "Installez Python 3 via Homebrew : brew install python@3."
            else
                printf "Installez 'python3' via votre gestionnaire de paquets (ex: sudo apt install python3)."
            fi
            ;;
        curl)
            if [[ "${os_hint}" == "Darwin" ]]; then
                printf "Installez curl via Homebrew : brew install curl."
            else
                printf "Installez 'curl' via votre gestionnaire de paquets (ex: sudo apt install curl)."
            fi
            ;;
        tar)
            if [[ "${os_hint}" == "Darwin" ]]; then
                printf "Installez GNU tar via Homebrew : brew install gnu-tar."
            else
                printf "Installez 'tar' via votre gestionnaire de paquets (ex: sudo apt install tar)."
            fi
            ;;
        shasum)
            if [[ "${os_hint}" == "Darwin" ]]; then
                printf "Installez les outils Perl (inclus via Xcode Command Line Tools ou Homebrew)."
            else
                printf "Installez le paquet fournissant 'shasum' (ex: sudo apt install perl)."
            fi
            ;;
        *)
            if [[ "${os_hint}" == "Darwin" ]]; then
                printf "Installez '%s' via Homebrew : brew install %s." "${cmd}" "${cmd}"
            else
                printf "Installez '%s' via votre gestionnaire de paquets (ex: sudo apt install %s)." "${cmd}" "${cmd}"
            fi
            ;;
    esac
}

function missing_command_error() {
    local cmd="$1"
    local message="La dépendance obligatoire '${cmd}' est introuvable."
    local hint
    hint="$(command_install_hint "${cmd}")"
    if [[ -n "${hint}" ]]; then
        message+=" ${hint}"
    fi
    error_msg "${message}"
}

resolve_stat_command() {
    if [[ -n "${STAT_COMMAND}" ]] && command_exists "${STAT_COMMAND}"; then
        return 0
    fi

    if [[ "${HOST_OS}" == "Darwin" ]]; then
        if command_exists gstat; then
            STAT_COMMAND="gstat"
            STAT_COMMAND_FLAVOR="gnu"
            return 0
        fi
        if command_exists stat; then
            STAT_COMMAND="stat"
            STAT_COMMAND_FLAVOR="bsd"
            return 0
        fi
    else
        if command_exists stat; then
            STAT_COMMAND="stat"
            STAT_COMMAND_FLAVOR="gnu"
            return 0
        fi
    fi

    STAT_COMMAND=""
    STAT_COMMAND_FLAVOR=""
    return 1
}

ensure_portable_stat_available() {
    if resolve_stat_command; then
        if [[ "${STAT_COMMAND_FLAVOR}" == "bsd" ]]; then
            success "stat disponible (mode BSD)."
        else
            success "${STAT_COMMAND} disponible."
        fi
        return 0
    fi

    missing_command_error "stat"
    exit 1
}

portable_stat() {
    local format="$1"
    shift || true
    local target="$1"

    if ! resolve_stat_command; then
        missing_command_error "stat"
        return 1
    fi

    local output=""
    case "${STAT_COMMAND_FLAVOR}" in
        bsd)
            if [[ "${format}" == "--printf=%s" ]]; then
                output=$(stat -f "%z" "${target}") || return 1
            else
                output=$(stat "${format}" "${target}") || return 1
            fi
            ;;
        *)
            output=$("${STAT_COMMAND}" "${format}" "${target}") || return 1
            ;;
    esac

    printf '%s\n' "${output}"
}

resolve_sha256_command() {
    local -a skip_candidates=("$@")
    if [[ ${#SHA256_SKIP_DEFAULT[@]} -gt 0 ]]; then
        skip_candidates+=("${SHA256_SKIP_DEFAULT[@]}")
    fi

    if [[ -n "${SHA256_COMMAND}" ]]; then
        local skip_current="false"
        for skipped in "${skip_candidates[@]}"; do
            if [[ "${skipped}" == "${SHA256_COMMAND}" ]]; then
                skip_current="true"
                break
            fi
        done
        if [[ "${skip_current}" == "false" ]] && command_exists "${SHA256_COMMAND}"; then
            return 0
        fi
        SHA256_COMMAND=""
        SHA256_COMMAND_FLAVOR=""
    fi

    local candidate
    for candidate in sha256sum gsha256sum; do
        local should_skip="false"
        for skipped in "${skip_candidates[@]}"; do
            if [[ "${skipped}" == "${candidate}" ]]; then
                should_skip="true"
                break
            fi
        done
        if [[ "${should_skip}" == "true" ]]; then
            continue
        fi
        if command_exists "${candidate}"; then
            SHA256_COMMAND="${candidate}"
            SHA256_COMMAND_FLAVOR="gnu"
            return 0
        fi
    done

    local darwin_skip="false"
    for skipped in "${skip_candidates[@]}"; do
        if [[ "${skipped}" == "shasum" ]]; then
            darwin_skip="true"
            break
        fi
    done

    if [[ "${HOST_OS}" == "Darwin" && "${darwin_skip}" == "false" ]] && command_exists shasum; then
        SHA256_COMMAND="shasum"
        SHA256_COMMAND_FLAVOR="bsd"
        return 0
    fi

    SHA256_COMMAND=""
    SHA256_COMMAND_FLAVOR=""
    return 1
}

ensure_portable_sha256_available() {
    if resolve_sha256_command; then
        if [[ "${SHA256_COMMAND_FLAVOR}" == "bsd" ]]; then
            success "shasum disponible (fallback macOS)."
        else
            success "${SHA256_COMMAND} disponible."
        fi
        return 0
    fi

    missing_command_error "sha256sum"
    exit 1
}

portable_sha256() {
    local file="$1"
    local -a tried=()

    while true; do
        if ! resolve_sha256_command "${tried[@]}"; then
            missing_command_error "sha256sum"
            return 1
        fi

        local output=""
        local status=0
        case "${SHA256_COMMAND_FLAVOR}" in
            bsd)
                output=$("${SHA256_COMMAND}" -a 256 "${file}" 2>/dev/null) || status=$?
                ;;
            *)
                output=$("${SHA256_COMMAND}" "${file}" 2>/dev/null) || status=$?
                ;;
        esac

        if [[ ${status} -eq 0 && -n "${output}" ]]; then
            output="${output%% *}"
            printf '%s\n' "${output}"
            return 0
        fi

        tried+=("${SHA256_COMMAND}")
        SHA256_COMMAND=""
        SHA256_COMMAND_FLAVOR=""
    done
}

resolve_dfu_util_command() {
    if [[ -n "${DFU_UTIL_COMMAND}" ]] && command_exists "${DFU_UTIL_COMMAND}"; then
        return 0
    fi

    if [[ -n "${DFU_UTIL_BIN:-}" ]] && command_exists "${DFU_UTIL_BIN}"; then
        DFU_UTIL_COMMAND="${DFU_UTIL_BIN}"
        return 0
    fi

    for candidate in dfu-util dfu-util-static; do
        if command_exists "${candidate}"; then
            DFU_UTIL_COMMAND="${candidate}"
            return 0
        fi
    done

    DFU_UTIL_COMMAND=""
    return 1
}

ensure_dfu_util_available() {
    if resolve_dfu_util_command; then
        success "dfu-util disponible (${DFU_UTIL_COMMAND})."
        return 0
    fi

    missing_command_error "dfu-util"
    exit 1
}

portable_dfu_util() {
    if ! resolve_dfu_util_command; then
        return 127
    fi

    "${DFU_UTIL_COMMAND}" "$@"
}

dfu_command_display() {
    if [[ -n "${DFU_UTIL_COMMAND}" ]]; then
        printf '%s\n' "${DFU_UTIL_COMMAND}"
    else
        printf '%s\n' "dfu-util"
    fi
}

function check_command() {
    local cmd="$1"
    local mandatory="$2"
    local hint=""

    if command_exists "${cmd}"; then
        success "${cmd} disponible."
        return 0
    fi

    hint="$(command_install_hint "${cmd}")"

    if [[ "${mandatory}" == "true" ]]; then
        local message="La dépendance obligatoire '${cmd}' est introuvable."
        if [[ -n "${hint}" ]]; then
            message+=" ${hint}"
        fi
        error_msg "${message}"
        exit 1
    else
        local message="La dépendance optionnelle '${cmd}' est absente. Certaines fonctionnalités peuvent être limitées."
        if [[ -n "${hint}" ]]; then
            message+=" ${hint}"
        fi
        warn "${message}"
        return 1
    fi
}

function check_group_membership() {
    local group="$1"
    local username=""
    local candidate=""

    if command_exists id; then
        if candidate=$(id -un 2>/dev/null) && [[ -n "${candidate}" ]]; then
            username="${candidate}"
        fi
    fi

    if [[ -z "${username}" ]] && command_exists logname; then
        if candidate=$(logname 2>/dev/null) && [[ -n "${candidate}" ]]; then
            username="${candidate}"
        fi
    fi

    if [[ -z "${username}" ]] && command_exists whoami; then
        if candidate=$(whoami 2>/dev/null) && [[ -n "${candidate}" ]]; then
            username="${candidate}"
        fi
    fi

    if [[ -z "${username}" ]]; then
        warn "Impossible de déterminer l'utilisateur courant ; vérification du groupe '${group}' ignorée."
        return 1
    fi

    if ! command_exists id; then
        warn "La commande 'id' est indisponible : impossible de vérifier l'appartenance au groupe '${group}'."
        return 1
    fi

    if id -nG "${username}" 2>/dev/null | tr ' ' '\n' | grep -qx "${group}"; then
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

lookup_wchisp_checksum() {
    local asset="$1"

    if [[ ! -f "${WCHISP_CHECKSUM_FILE}" ]]; then
        error_msg "Fichier de sommes de contrôle wchisp introuvable (${WCHISP_CHECKSUM_FILE})."
        printf "Assurez-vous que le dépôt contient les sommes SHA-256 de wchisp avant de poursuivre.\n" >&2
        return 1
    fi

    local checksum
    checksum=$(awk -v target="${asset}" '
        /^[[:space:]]*#/ {next}
        NF >= 2 && $NF == target {print $1; exit}
    ' "${WCHISP_CHECKSUM_FILE}")

    if [[ -z "${checksum}" ]]; then
        error_msg "Somme de contrôle attendue introuvable pour ${asset}."
        printf "Mettez à jour %s avec l'empreinte SHA-256 officielle correspondant à cette archive.\n" "${WCHISP_CHECKSUM_FILE}" >&2
        return 1
    fi

    printf '%s\n' "${checksum}"
}

verify_wchisp_archive() {
    local asset="$1"
    local archive_path="$2"
    local expected="${3:-__auto__}"
    local degraded="${ALLOW_UNVERIFIED_WCHISP}"

    if [[ "${degraded}" == "true" ]]; then
        warn "Mode dégradé actif : la vérification SHA-256 de ${asset} sera tolérée en cas d'échec."
        log_message "WARN" "Mode dégradé actif pour ${asset} : les écarts de checksum seront ignorés."
    fi

    if [[ "${expected}" == "__auto__" ]]; then
        if ! expected=$(lookup_wchisp_checksum "${asset}"); then
            if [[ "${degraded}" == "true" ]]; then
                warn "Impossible de récupérer la somme de contrôle officielle pour ${asset}. Le mode dégradé permet de continuer."
                log_message "WARN" "Checksum officiel introuvable pour ${asset}, poursuite en mode dégradé."
                return 0
            fi
            return 1
        fi
    fi

    if [[ -n "${WCHISP_ARCHIVE_CHECKSUM_OVERRIDE}" ]]; then
        if [[ "${expected}" != "${WCHISP_ARCHIVE_CHECKSUM_OVERRIDE}" ]]; then
            warn "Somme de contrôle wchisp remplacée par la valeur fournie par l'utilisateur."
            log_message "WARN" "Checksum de ${asset} remplacé par l'override utilisateur."
        fi
        expected="${WCHISP_ARCHIVE_CHECKSUM_OVERRIDE}"
    fi

    if [[ -z "${expected}" ]]; then
        log_message "WARN" "Somme de contrôle inconnue pour ${asset}; vérification ignorée."
        echo "AVERTISSEMENT : aucune somme de contrôle n'est disponible pour ${asset}. Vérifiez manuellement l'origine de l'archive ou fournissez WCHISP_FALLBACK_CHECKSUM." >&2
        return 0
    fi

    local actual
    if ! actual=$(portable_sha256 "${archive_path}" 2>/dev/null); then
        error_msg "Impossible de calculer l'empreinte SHA-256 de ${archive_path}."
        printf "Vérifiez les permissions de lecture sur l'archive avant de relancer.\n" >&2
        return 1
    fi

    if [[ "${actual}" != "${expected}" ]]; then
        if [[ "${degraded}" == "true" ]]; then
            warn "Empreinte SHA-256 inattendue pour ${asset} (${actual}). L'archive est conservée car le mode dégradé est actif."
            log_message "WARN" "Checksum inattendu pour ${asset} (attendu=${expected}; obtenu=${actual}) mais conservation de l'archive (mode dégradé)."
            return 0
        fi
        rm -f "${archive_path}" || true
        error_msg "La vérification d'intégrité de l'archive ${asset} a échoué."
        printf "Empreinte attendue : %s\nEmpreinte calculée : %s\n" "${expected}" "${actual}" >&2
        printf "L'archive téléchargée a été supprimée. Relancez le script après avoir vérifié votre connexion ou la source du fichier.\n" >&2
        return 1
    fi

    log_message "INFO" "Somme de contrôle SHA-256 validée pour ${asset}."
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

    local resolution
    if ! resolution=$(resolve_wchisp_download); then
        exit 1
    fi

    local arch_raw arch asset url checksum_mode checksum_value expected_checksum
    IFS='|' read -r arch_raw arch asset url checksum_mode checksum_value <<< "${resolution}"

    if [[ "${checksum_mode}" == "official" ]]; then
        if ! expected_checksum=$(lookup_wchisp_checksum "${asset}"); then
            exit 1
        fi
    else
        expected_checksum="${checksum_value}"
        if [[ -z "${expected_checksum}" ]]; then
            log_message "WARN" "Aucune somme de contrôle fournie pour l'archive de secours ${asset}."
        fi
    fi

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

    ensure_portable_sha256_available

    if ! verify_wchisp_archive "${asset}" "${archive_path}" "${expected_checksum}"; then
        exit 1
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
    log_message "INFO" "wchisp disponible localement via ${WCHISP_COMMAND} (architecture détectée : ${arch_raw} -> ${arch})."
    echo "wchisp installé automatiquement dans ${install_dir}."
}

function detect_serial_devices() {
    local -n serial_devices_ref=$1
    serial_devices_ref=()

    if compgen -G "/dev/serial/by-id/*" >/dev/null 2>&1; then
        for path in /dev/serial/by-id/*; do
            [[ -e "${path}" ]] && serial_devices_ref+=("${path}")
        done
    fi

    local patterns=(/dev/ttyUSB* /dev/ttyACM* /dev/ttyAMA* /dev/ttyS* /dev/ttyCH*)
    for pattern in "${patterns[@]}"; do
        for dev in ${pattern}; do
            [[ -e "${dev}" ]] && serial_devices_ref+=("${dev}")
        done
    done

    if [[ ${#serial_devices_ref[@]} -gt 0 ]]; then
        mapfile -t serial_devices_ref < <(printf '%s\n' "${serial_devices_ref[@]}" | awk '!seen[$0]++')
    fi
}

function detect_dfu_devices() {
    local -n dfu_devices_ref=$1
    dfu_devices_ref=()

    if ! resolve_dfu_util_command; then
        return
    fi

    while IFS= read -r line; do
        [[ -z "${line}" ]] && continue
        dfu_devices_ref+=("${line}")
    done < <("${DFU_UTIL_COMMAND}" -l 2>/dev/null | awk -F':' '/Found DFU:/{gsub(/^\s+|\s+$/, "", $2); print $2}' )
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
        if [[ -n "${DFU_UTIL_COMMAND}" ]]; then
            info "Périphériques DFU détectés (${DFU_UTIL_COMMAND}) :"
        else
            info "Périphériques DFU détectés (dfu-util) :"
        fi
        local index=1
        for dev in "${dfu_devices[@]}"; do
            printf "    [%d] %s\n" "${index}" "${dev}"
            ((index++))
        done
    fi
}

flash_method_to_human() {
    local method="$1"

    case "${method}" in
        wchisp)
            printf '%s\n' "flash direct via wchisp"
            ;;
        serial)
            printf '%s\n' "flash série via flash_usb.py"
            ;;
        sdcard)
            printf '%s\n' "copie sur carte SD / stockage"
            ;;
        dfu)
            printf '%s\n' "flash DFU via $(dfu_command_display)"
            ;;
        *)
            printf '%s\n' "méthode inconnue"
            ;;
    esac
}

auto_detect_flash_method() {
    AUTO_METHOD_REASON=""

    if command_exists "${WCHISP_COMMAND}"; then
        AUTO_METHOD_REASON="wchisp détecté : ${WCHISP_COMMAND} est disponible."
        printf '%s\n' "wchisp"
        return
    fi

    if [[ "${WCHISP_AUTO_INSTALL}" == "true" ]]; then
        AUTO_METHOD_REASON="wchisp sélectionné : installation automatique autorisée."
        printf '%s\n' "wchisp"
        return
    fi

    local -a dfu_devices=()
    detect_dfu_devices dfu_devices
    if [[ ${#dfu_devices[@]} -gt 0 ]]; then
        AUTO_METHOD_REASON="Mode DFU détecté via $(dfu_command_display) (${dfu_devices[0]})."
        printf '%s\n' "dfu"
        return
    fi

    local -a serial_devices=()
    detect_serial_devices serial_devices
    if [[ ${#serial_devices[@]} -gt 0 ]]; then
        AUTO_METHOD_REASON="Ports série détectés (${serial_devices[0]})."
        printf '%s\n' "serial"
        return
    fi

    AUTO_METHOD_REASON="Aucune interface dédiée détectée : bascule sur carte SD."
    printf '%s\n' "sdcard"
}

resolve_flash_method() {
    local candidate=""
    local source_label="détection automatique"
    local forced="false"

    AUTO_METHOD_REASON=""

    if [[ -n "${CLI_METHOD_OVERRIDE}" ]]; then
        if [[ "${CLI_METHOD_OVERRIDE}" == "auto" ]]; then
            candidate="$(auto_detect_flash_method)"
            source_label="détection automatique (--method auto)"
        else
            candidate="${CLI_METHOD_OVERRIDE}"
            source_label="option CLI (--method)"
            forced="true"
        fi
    elif [[ -n "${ENV_METHOD_OVERRIDE}" ]]; then
        local normalized
        if ! normalized=$(normalize_flash_method "${ENV_METHOD_OVERRIDE}"); then
            warn "Valeur FLASH_AUTOMATION_METHOD invalide (${ENV_METHOD_OVERRIDE}). Retour à la détection automatique."
            candidate="$(auto_detect_flash_method)"
            source_label="détection automatique"
        elif [[ "${normalized}" == "auto" ]]; then
            candidate="$(auto_detect_flash_method)"
            source_label="détection automatique (FLASH_AUTOMATION_METHOD=auto)"
        else
            candidate="${normalized}"
            source_label="variable d'environnement FLASH_AUTOMATION_METHOD"
            forced="true"
        fi
        ENV_METHOD_OVERRIDE="${normalized:-}"
    else
        candidate="$(auto_detect_flash_method)"
        source_label="détection automatique"
    fi

    if [[ -z "${candidate}" ]]; then
        candidate="wchisp"
    fi

    RESOLVED_METHOD="${candidate}"
    METHOD_SOURCE_LABEL="${source_label}"
    FORCED_METHOD="${forced}"

    if [[ "${FORCED_METHOD}" == "true" ]]; then
        SELECTED_METHOD="${RESOLVED_METHOD}"
        DEFAULT_METHOD=""
    else
        DEFAULT_METHOD="${RESOLVED_METHOD}"
        SELECTED_METHOD=""
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

run_find_firmware_files() {
    local search_dir="$1"
    local max_depth="${2:-}"
    local respect_excludes="${3:-true}"

    local -a find_cmd=(find "${search_dir}")
    if [[ -n "${max_depth}" ]]; then
        find_cmd+=(-maxdepth "${max_depth}")
    fi

    if [[ "${respect_excludes}" == "true" && ${#FIRMWARE_SCAN_EXCLUDES[@]} -gt 0 ]]; then
        find_cmd+=(\()
        local first_pattern=true
        for exclude in "${FIRMWARE_SCAN_EXCLUDES[@]}"; do
            local sanitized="${exclude%/}"
            [[ -n "${sanitized}" ]] || continue
            for pattern in "${sanitized}" "${sanitized}/*"; do
                if [[ "${first_pattern}" == "true" ]]; then
                    first_pattern=false
                else
                    find_cmd+=(-o)
                fi
                find_cmd+=(-path "${pattern}")
            done
        done
        find_cmd+=(\))
        find_cmd+=(-prune)
        find_cmd+=(-o)
    fi

    find_cmd+=(-type)
    find_cmd+=(f)
    find_cmd+=(\()
    find_cmd+=(-name "*.bin")
    find_cmd+=(-o)
    find_cmd+=(-name "*.uf2")
    find_cmd+=(-o)
    find_cmd+=(-name "*.elf")
    find_cmd+=(\))
    find_cmd+=(-print0)

    "${find_cmd[@]}"
}

verify_common_dependencies() {
    ensure_portable_stat_available
    check_command "find" true
    ensure_portable_sha256_available
    check_command "python3" false
}

verify_method_dependencies() {
    local method="$1"
    local context="$2"
    local human
    human="$(flash_method_to_human "${method}")"

    if [[ "${context}" == "selection" ]]; then
        info "Validation des dépendances pour ${human} (méthode ajustée)."
    else
        info "Validation des dépendances spécifiques à ${human}."
    fi

    case "${method}" in
        wchisp)
            if command_exists "${WCHISP_COMMAND}"; then
                success "wchisp disponible (${WCHISP_COMMAND})."
            else
                if [[ "${WCHISP_AUTO_INSTALL}" == "true" ]]; then
                    info "wchisp sera installé automatiquement : vérification de curl/tar."
                    check_command "curl" true
                    check_command "tar" true
                else
                    error_msg "wchisp est requis pour la méthode sélectionnée. Exportez WCHISP_BIN ou installez l'outil."
                    exit 1
                fi
            fi
            ;;
        serial)
            check_command "python3" true
            check_command "make" false
            ;;
        dfu)
            ensure_dfu_util_available
            ;;
        sdcard)
            :
            ;;
        *)
            warn "Aucune règle de vérification spécifique pour '${method}'."
            ;;
    esac
}

finalize_method_selection() {
    if [[ -z "${SELECTED_METHOD}" ]]; then
        return
    fi

    if [[ -n "${DEPENDENCIES_VERIFIED_FOR_METHOD}" && "${SELECTED_METHOD}" != "${DEPENDENCIES_VERIFIED_FOR_METHOD}" ]]; then
        verify_method_dependencies "${SELECTED_METHOD}" "selection"
        DEPENDENCIES_VERIFIED_FOR_METHOD="${SELECTED_METHOD}"
    fi

    local human
    human="$(flash_method_to_human "${SELECTED_METHOD}")"

    case "${SELECTED_METHOD}" in
        wchisp)
            success "Méthode sélectionnée : ${human}."
            if [[ "${DRY_RUN_MODE}" == "true" ]]; then
                info "Mode --dry-run : vérification wchisp ignorée (aucun téléchargement)."
            else
                ensure_wchisp
            fi
            ;;
        serial)
            success "Méthode sélectionnée : ${human}."
            if [[ -z "${SELECTED_DEVICE}" ]]; then
                prompt_serial_device
            else
                if [[ -n "${SERIAL_SELECTION_SOURCE}" ]]; then
                    success "Port série imposé (${SERIAL_SELECTION_SOURCE}) : ${SELECTED_DEVICE}."
                else
                    success "Port série imposé : ${SELECTED_DEVICE}."
                fi
            fi
            ;;
        sdcard)
            success "Méthode sélectionnée : ${human}."
            if [[ -z "${SDCARD_MOUNTPOINT}" ]]; then
                prompt_sdcard_mountpoint
            else
                if [[ -n "${SDCARD_SELECTION_SOURCE}" ]]; then
                    success "Point de montage imposé (${SDCARD_SELECTION_SOURCE}) : ${SDCARD_MOUNTPOINT}."
                else
                    success "Point de montage imposé : ${SDCARD_MOUNTPOINT}."
                fi
            fi
            ;;
        dfu)
            success "Méthode sélectionnée : ${human}."
            ;;
        *)
            error_msg "Méthode de flash inconnue: ${SELECTED_METHOD}"
            exit 1
            ;;
    esac
}

function verify_environment() {
    CURRENT_STEP="Étape 0: Diagnostic de l'environnement"
    render_box "${CURRENT_STEP}"

    local planned_method="${RESOLVED_METHOD:-wchisp}"
    local method_label
    method_label="$(flash_method_to_human "${planned_method}")"

    info "Méthode anticipée : ${method_label} (${METHOD_SOURCE_LABEL:-détection automatique})."
    if [[ -n "${AUTO_METHOD_REASON}" && "${METHOD_SOURCE_LABEL}" == *"détection automatique"* ]]; then
        info "Indice auto-détection : ${AUTO_METHOD_REASON}"
    fi

    info "Vérification des dépendances communes."
    verify_common_dependencies
    verify_method_dependencies "${planned_method}" "initial"
    DEPENDENCIES_VERIFIED_FOR_METHOD="${planned_method}"

    if should_skip_permission_checks; then
        info "Vérification des permissions sautée : ${PERMISSIONS_CACHE_MESSAGE}."
    else
        if check_group_membership "dialout"; then
            if update_permissions_cache "ok" "Appartenance au groupe 'dialout' confirmée"; then
                if permissions_cache_enabled; then
                    info "Cache des permissions mis à jour (expiration dans $(format_duration_seconds "${PERMISSIONS_CACHE_TTL}"))"
                fi
            fi
        else
            invalidate_permissions_cache
        fi
    fi

    info "Analyse des périphériques série et DFU disponibles."
    display_available_devices
}

function collect_firmware_candidates() {
    local -n firmware_candidates_ref=$1
    firmware_candidates_ref=()

    declare -A seen
    local resolved_hint=""

    if [[ -n "${FIRMWARE_DISPLAY_PATH}" ]]; then
        resolved_hint="$(resolve_path_relative_to_flash_root "${FIRMWARE_DISPLAY_PATH}")"
        if [[ -f "${resolved_hint}" ]]; then
            seen["${resolved_hint}"]=1
            firmware_candidates_ref+=("${resolved_hint}")
        elif [[ -d "${resolved_hint}" ]]; then
            local dir="${resolved_hint}"
            while IFS= read -r -d '' file; do
                [[ -n "${seen["${file}"]-}" ]] && continue
                seen["${file}"]=1
                firmware_candidates_ref+=("${file}")
            done < <(run_find_firmware_files "${dir}" 3 false 2>/dev/null)
        fi
    fi

    for rel_path in "${DEFAULT_FIRMWARE_RELATIVE_PATHS[@]}"; do
        local default_dir="${FLASH_ROOT}/${rel_path}"
        [[ -d "${default_dir}" ]] || continue
        while IFS= read -r -d '' file; do
            [[ -n "${seen["${file}"]-}" ]] && continue
            seen["${file}"]=1
            firmware_candidates_ref+=("${file}")
        done < <(run_find_firmware_files "${default_dir}" 2 true 2>/dev/null)
    done

    if [[ "${DEEP_SCAN_ENABLED}" == "true" ]]; then
        local -a extra_search=("${FLASH_ROOT}")
        for dir in "${extra_search[@]}"; do
            [[ -d "${dir}" ]] || continue
            while IFS= read -r -d '' file; do
                [[ -n "${seen["${file}"]-}" ]] && continue
                seen["${file}"]=1
                firmware_candidates_ref+=("${file}")
            done < <(run_find_firmware_files "${dir}" 4 true 2>/dev/null)
        done
    fi

    if [[ ${#firmware_candidates_ref[@]} -gt 0 ]]; then
        mapfile -t firmware_candidates_ref < <(printf '%s\n' "${firmware_candidates_ref[@]}" | awk '!seen[$0]++')
    fi
}

function prompt_firmware_selection() {
    local -n candidates_ref=$1
    local choice=""
    local default_choice=""
    local default_display=""

    if (( ${#candidates_ref[@]} > 0 )); then
        default_choice="${candidates_ref[0]}"
        default_display="$(format_path_for_display "${default_choice}")"
    fi

    if [[ ${#DEFAULT_FIRMWARE_RELATIVE_PATHS[@]} -gt 0 ]]; then
        local joined_paths
        joined_paths="${DEFAULT_FIRMWARE_RELATIVE_PATHS[*]}"
        echo "Chemins valides (relatifs au dépôt) : ${joined_paths}"
    fi
    echo "Saisissez le numéro correspondant, un chemin absolu ou relatif, ou 'q' pour quitter rapidement."

    while true; do
        echo
        echo "Sélectionnez le firmware à utiliser :"
        local index=1
        for file in "${candidates_ref[@]}"; do
            local display
            display="$(format_path_for_display "${file}")"
            local extension="${file##*.}"
            printf "  [%d] %s (%s)\n" "${index}" "${display}" "${extension}";
            ((index++))
        done
        printf "  [%d] Saisir un chemin personnalisé\n" "${index}"
        printf "  [q] Quitter et annuler la procédure\n"

        local prompt_hint=""
        if [[ -n "${default_display}" ]]; then
            prompt_hint=" (Entrée = ${default_display})"
        fi

        read -rp "Votre choix${prompt_hint} ('q' pour quitter) : " answer

        if [[ -z "${answer}" ]]; then
            if [[ -n "${default_choice}" ]]; then
                choice="${default_choice}"
                break
            fi
            warn "Veuillez sélectionner une option ou fournir un chemin valide."
            continue
        fi

        if [[ "${answer,,}" == "q" ]]; then
            info "Arrêt demandé par l'utilisateur lors de la sélection du firmware."
            exit 0
        fi

        if [[ "${answer}" =~ ^[0-9]+$ ]]; then
            local numeric=$((answer))
            if (( numeric >= 1 && numeric <= ${#candidates_ref[@]} )); then
                choice="${candidates_ref[$((numeric-1))]}"
                break
            elif (( numeric == index )); then
                read -rp "Chemin complet du firmware (relatif à ${FLASH_ROOT} accepté) : " custom_path
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

    local search_roots_display=""
    for rel_path in "${DEFAULT_FIRMWARE_RELATIVE_PATHS[@]}"; do
        if [[ -n "${search_roots_display}" ]]; then
            search_roots_display+=", "
        fi
        search_roots_display+="${rel_path}"
    done
    info "Répertoires analysés par défaut : ${search_roots_display}"

    if [[ "${DEEP_SCAN_ENABLED}" == "true" ]]; then
        local exclude_display=""
        if [[ ${#FIRMWARE_SCAN_EXCLUDES[@]} -gt 0 ]]; then
            for exclude in "${FIRMWARE_SCAN_EXCLUDES[@]}"; do
                local formatted
                formatted="$(format_path_for_display "${exclude}")"
                if [[ -n "${exclude_display}" ]]; then
                    exclude_display+=", "
                fi
                exclude_display+="${formatted}"
            done
        fi
        info "Mode --deep-scan actif : recherche étendue dans ${FLASH_ROOT}."
        if [[ -n "${exclude_display}" ]]; then
            info "Chemins ignorés : ${exclude_display}"
        fi
    else
        info "Utilisez --deep-scan pour élargir la recherche à l'ensemble du dépôt."
    fi

    if [[ -n "${PRESELECTED_FIRMWARE_FILE}" ]]; then
        if [[ -n "${FIRMWARE_SELECTION_SOURCE}" ]]; then
            info "Firmware imposé par ${FIRMWARE_SELECTION_SOURCE}."
        fi
        FIRMWARE_FILE="${PRESELECTED_FIRMWARE_FILE}"
        FIRMWARE_DISPLAY_PATH="$(format_path_for_display "${FIRMWARE_FILE}")"
        FIRMWARE_FORMAT="${FIRMWARE_FILE##*.}"
    else
        local -a candidates
        collect_firmware_candidates candidates

        if [[ ${#candidates[@]} -eq 0 ]]; then
            local message="Aucun firmware compatible détecté (recherché dans ${search_roots_display})."
            if [[ "${DEEP_SCAN_ENABLED}" != "true" ]]; then
                message+=" Utilisez --deep-scan pour élargir la recherche."
            fi
            error_msg "${message} Lancer './build.sh' ou fournir KLIPPER_FIRMWARE_PATH."
            exit 1
        fi

        if [[ "${AUTO_CONFIRM_MODE}" == "true" ]]; then
            if [[ ${#candidates[@]} -eq 1 ]]; then
                FIRMWARE_FILE="${candidates[0]}"
                FIRMWARE_DISPLAY_PATH="$(format_path_for_display "${FIRMWARE_FILE}")"
                FIRMWARE_FORMAT="${FIRMWARE_FILE##*.}"
                info "Mode auto-confirm : sélection automatique du firmware ${FIRMWARE_DISPLAY_PATH}."
            else
                error_msg "Plusieurs firmwares détectés mais --auto-confirm actif. Précisez --firmware pour lever l'ambiguïté."
                exit 1
            fi
        else
            prompt_firmware_selection candidates
        fi
    fi

    FIRMWARE_SIZE=$(portable_stat "--printf=%s" "${FIRMWARE_FILE}")
    FIRMWARE_SHA=$(portable_sha256 "${FIRMWARE_FILE}")

    success "Firmware sélectionné : ${FIRMWARE_DISPLAY_PATH} (${FIRMWARE_FORMAT})"
    info "Taille : ${FIRMWARE_SIZE} octets"
    info "SHA256 : ${FIRMWARE_SHA}"
}

function select_flash_method() {
    CURRENT_STEP="Étape 2: Sélection de la méthode de flash"
    render_box "${CURRENT_STEP}"
    info "Choisissez la méthode adaptée à votre configuration."

    if [[ "${FORCED_METHOD}" == "true" ]]; then
        info "Méthode imposée par ${METHOD_SOURCE_LABEL}."
        finalize_method_selection
        return
    fi

    local suggestion="${DEFAULT_METHOD}"
    if [[ -n "${suggestion}" ]]; then
        local suggestion_label
        suggestion_label="$(flash_method_to_human "${suggestion}")"
        info "Suggestion détectée : ${suggestion_label}."
        if [[ -n "${AUTO_METHOD_REASON}" ]]; then
            info "Raison : ${AUTO_METHOD_REASON}"
        fi
    fi

    if [[ "${AUTO_CONFIRM_MODE}" == "true" ]]; then
        local chosen_method="${suggestion}"
        if [[ -z "${chosen_method}" ]]; then
            chosen_method="${RESOLVED_METHOD:-wchisp}"
        fi
        local auto_label
        auto_label="$(flash_method_to_human "${chosen_method}")"
        info "Mode auto-confirm : sélection automatique de ${auto_label}."
        SELECTED_METHOD="${chosen_method}"
        finalize_method_selection
        return
    fi

    local options=(
        "Flash direct via wchisp (mode bootloader USB)"
        "Flash série via flash_usb.py (port /dev/tty*)"
        "Copie du firmware sur carte SD / stockage"
        "Flash DFU via $(dfu_command_display)"
    )

    local prompt_hint=""
    if [[ -n "${suggestion}" ]]; then
        local human_hint
        human_hint="$(flash_method_to_human "${suggestion}")"
        prompt_hint=" (Entrée = ${human_hint})"
    fi

    echo "Saisissez le numéro correspondant ou 'q' pour quitter rapidement."

    while true; do
        local index=1
        for option in "${options[@]}"; do
            printf "  [%d] %s\n" "${index}" "${option}"
            ((index++))
        done
        printf "  [q] Quitter et annuler la procédure\n"

        read -rp "Méthode choisie${prompt_hint} ('q' pour quitter) : " answer

        if [[ -z "${answer}" ]]; then
            if [[ -n "${suggestion}" ]]; then
                SELECTED_DEVICE=""
                SDCARD_MOUNTPOINT=""
                SELECTED_METHOD="${suggestion}"
                finalize_method_selection
                break
            fi
            warn "Veuillez sélectionner une option ou saisir 'q' pour quitter."
            continue
        fi

        if [[ "${answer,,}" == "q" ]]; then
            info "Arrêt demandé par l'utilisateur lors de la sélection de la méthode."
            exit 0
        fi

        case "${answer}" in
            1|wchisp|WCHISP|usb|USB)
                SELECTED_DEVICE=""
                SDCARD_MOUNTPOINT=""
                SELECTED_METHOD="wchisp"
                finalize_method_selection
                break
                ;;
            2|serial|SERIAL)
                SDCARD_MOUNTPOINT=""
                SELECTED_METHOD="serial"
                SELECTED_DEVICE=""
                finalize_method_selection
                break
                ;;
            3|sd|sdcard|SD|SDCARD)
                SELECTED_DEVICE=""
                SELECTED_METHOD="sdcard"
                SDCARD_MOUNTPOINT=""
                finalize_method_selection
                break
                ;;
            dfu|DFU|4)
                SELECTED_DEVICE=""
                SDCARD_MOUNTPOINT=""
                SELECTED_METHOD="dfu"
                finalize_method_selection
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
        local default_device=""

        if [[ ${#devices[@]} -gt 0 ]]; then
            echo "Ports série détectés :"
            local index=1
            for dev in "${devices[@]}"; do
                printf "  [%d] %s\n" "${index}" "${dev}"
                ((index++))
            done
            default_device="${devices[0]}"
        else
            warn "Aucun port série détecté pour le moment."
        fi

        echo "Astuce : saisissez un numéro, un chemin /dev/tty* ou 'q' pour quitter rapidement."
        local prompt_hint=""
        if [[ -n "${default_device}" ]]; then
            prompt_hint=" (Entrée = ${default_device})"
        fi

        read -rp "Sélectionnez un port${prompt_hint} ('r' pour rafraîchir, 'q' pour quitter) : " answer

        case "${answer}" in
            r|R)
                continue
                ;;
            q|Q)
                info "Arrêt demandé par l'utilisateur lors de la sélection du port série."
                exit 0
                ;;
            "")
                if [[ -n "${default_device}" ]]; then
                    SELECTED_DEVICE="${default_device}"
                    break
                fi
                warn "Veuillez sélectionner un port valide ou saisir 'q' pour quitter."
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
    local default_mount=""
    local nullglob_was_set=0
    if shopt -q nullglob; then
        nullglob_was_set=1
    fi
    shopt -s nullglob

    local -a mount_candidates=()
    if [[ -n "${USER:-}" ]]; then
        mount_candidates+=(/media/"${USER}"/* /run/media/"${USER}"/*)
    else
        mount_candidates+=(/media/* /run/media/*)
    fi
    mount_candidates+=(/mnt/*)

    for candidate in "${mount_candidates[@]}"; do
        if [[ -d "${candidate}" ]]; then
            default_mount="${candidate}"
            break
        fi
    done

    if [[ ${nullglob_was_set} -eq 0 ]]; then
        shopt -u nullglob
    fi

    if [[ -n "${default_mount}" ]]; then
        echo "Chemin détecté : ${default_mount} (Entrée pour utiliser ce chemin)."
    fi
    echo "Astuce : saisissez un dossier monté accessible en écriture (ex: /media/${USER:-<utilisateur>}/<volume>) ou 'q' pour quitter."

    while true; do
        local prompt_hint=""
        if [[ -n "${default_mount}" ]]; then
            prompt_hint=" (Entrée = ${default_mount})"
        fi

        read -rp "Point de montage de la carte SD${prompt_hint} ('q' pour quitter) : " mountpoint

        if [[ -z "${mountpoint}" ]]; then
            if [[ -n "${default_mount}" ]]; then
                mountpoint="${default_mount}"
            else
                warn "Le chemin ne peut pas être vide."
                continue
            fi
        fi

        if [[ "${mountpoint,,}" == "q" ]]; then
            info "Arrêt demandé par l'utilisateur lors de la sélection de la carte SD."
            exit 0
        fi

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
            if [[ "${AUTO_CONFIRM_MODE}" != "true" ]]; then
                read -rp "Appuyez sur Entrée après le passage en bootloader pour rescanner les périphériques..." _
                display_available_devices
            else
                info "Mode auto-confirm : saut du prompt de rescan (affichage automatique des périphériques)."
                display_available_devices
            fi
            ;;
        serial)
            info "Validation du port série ${SELECTED_DEVICE}."
            if [[ ! -e "${SELECTED_DEVICE}" ]]; then
                if [[ "${AUTO_CONFIRM_MODE}" == "true" ]]; then
                    warn "Le port sélectionné est introuvable. Mode auto-confirm : aucun nouveau port ne sera proposé."
                else
                    warn "Le port sélectionné est introuvable."
                    prompt_serial_device
                fi
            fi
            display_available_devices
            ;;
        sdcard)
            info "Préparez la carte SD montée sur ${SDCARD_MOUNTPOINT}."
            ;;
        dfu)
            info "Basculez la carte en mode DFU (BOOT0 maintenu puis RESET)."
            local dfu_label
            dfu_label="$(dfu_command_display)"
            info "Assurez-vous que ${dfu_label} détecte la cible (${dfu_label} -l)."
            display_available_devices
            ;;
    esac
}

function flash_with_wchisp() {
    if [[ "${DRY_RUN_MODE}" == "true" ]]; then
        info "[DRY-RUN] wchisp flasherait ${FIRMWARE_DISPLAY_PATH}."
        return
    fi

    ensure_wchisp

    local transport="${WCHISP_TRANSPORT,,}"
    if [[ -z "${transport}" ]]; then
        transport="usb"
    fi

    info "Début du flash via ${WCHISP_COMMAND} (transport ${transport})."

    local cmd=("${WCHISP_COMMAND}")

    case "${transport}" in
        usb)
            cmd+=("--usb")
            if [[ -n "${WCHISP_USB_INDEX}" ]]; then
                if [[ "${WCHISP_USB_INDEX}" =~ ^[0-9]+$ ]]; then
                    cmd+=("--device" "${WCHISP_USB_INDEX}")
                else
                    warn "Valeur WCHISP_USB_INDEX invalide (${WCHISP_USB_INDEX}). Utilisation de la détection automatique."
                fi
            fi
            ;;
        serial)
            cmd+=("--serial")
            if [[ -n "${WCHISP_SERIAL_PORT}" ]]; then
                cmd+=("--port" "${WCHISP_SERIAL_PORT}")
            else
                error_msg "WCHISP_SERIAL_PORT doit être défini pour utiliser le transport série de wchisp."
                exit 1
            fi
            if [[ -n "${WCHISP_SERIAL_BAUDRATE}" ]]; then
                cmd+=("--baudrate" "${WCHISP_SERIAL_BAUDRATE}")
            fi
            ;;
        *)
            warn "Transport WCHISP_TRANSPORT=${WCHISP_TRANSPORT} non reconnu. Retour au mode USB."
            cmd+=("--usb")
            ;;
    esac

    cmd+=(flash "${FIRMWARE_FILE}")

    log_message "DEBUG" "Commande exécutée: ${cmd[*]}"
    "${cmd[@]}" 2>&1 | tee -a "${LOG_FILE}"
    success "wchisp a terminé le flash sans erreur."
}

function flash_with_dfu() {
    local dfu_label
    dfu_label="$(dfu_command_display)"

    if [[ "${DRY_RUN_MODE}" == "true" ]]; then
        info "[DRY-RUN] ${dfu_label} flasherait ${FIRMWARE_DISPLAY_PATH} (alt=${DFU_ALT_SETTING:-0})."
        return
    fi

    if ! resolve_dfu_util_command; then
        missing_command_error "dfu-util"
        exit 1
    fi

    local alt="${DFU_ALT_SETTING}"
    if [[ -z "${alt}" ]]; then
        alt=0
    fi

    dfu_label="$(dfu_command_display)"
    info "Flash DFU via ${dfu_label} (alt=${alt})."

    local cmd=("${DFU_UTIL_COMMAND}" -a "${alt}" -D "${FIRMWARE_FILE}")

    if [[ -n "${DFU_SERIAL_NUMBER}" ]]; then
        cmd+=(-S "${DFU_SERIAL_NUMBER}")
    fi

    if [[ -n "${DFU_EXTRA_ARGS}" ]]; then
        # shellcheck disable=SC2206
        local extra=( ${DFU_EXTRA_ARGS} )
        cmd+=("${extra[@]}")
    fi

    log_message "DEBUG" "Commande exécutée: ${cmd[*]}"
    "${cmd[@]}" 2>&1 | tee -a "${LOG_FILE}"
    success "${dfu_label} a terminé sans erreur."
}

function flash_with_serial() {
    if [[ "${DRY_RUN_MODE}" == "true" ]]; then
        info "[DRY-RUN] flash_usb.py programmerait ${FIRMWARE_DISPLAY_PATH} sur ${SELECTED_DEVICE}."
        return
    fi

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
    if [[ "${DRY_RUN_MODE}" == "true" ]]; then
        info "[DRY-RUN] Copie simulée de ${FIRMWARE_DISPLAY_PATH} vers ${SDCARD_MOUNTPOINT}."
        return
    fi

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
        dfu)
            flash_with_dfu
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
    elif [[ "${SELECTED_METHOD}" == "dfu" ]]; then
        local dfu_label
        dfu_label="$(dfu_command_display)"
        local alt_summary="${DFU_ALT_SETTING:-0}"
        printf '  - %s : alt=%s' "${dfu_label}" "${alt_summary}"
        if [[ -n "${DFU_SERIAL_NUMBER}" ]]; then
            printf ', serial=%s' "${DFU_SERIAL_NUMBER}"
        fi
        printf '\n'
    fi

    echo
    success ">>> Procédure terminée avec succès. <<<"
    info "Les logs détaillés sont disponibles ici : ${LOG_FILE}"
    if [[ "${DRY_RUN_MODE}" == "true" ]]; then
        info "Mode --dry-run : aucune opération de flash n'a été appliquée à la cible."
    fi
    if [[ "${QUIET_MODE}" == "true" ]]; then
        echo "Procédure terminée. Consultez ${LOG_FILE} pour le détail."
        if [[ "${DRY_RUN_MODE}" == "true" ]]; then
            echo "Mode --dry-run : aucune opération de flash n'a été appliquée à la cible."
        fi
    fi
    log_message "INFO" "Procédure complète terminée avec succès."
}

function main() {
    if [[ "${DRY_RUN_MODE}" == "true" ]]; then
        info "Mode --dry-run actif : le script valide le déroulé sans effectuer d'actions destructrices."
    fi
    resolve_flash_method
    verify_environment
    prepare_firmware
    select_flash_method
    detect_klipper_services
    prepare_target
    stop_klipper_services
    execute_flash
    post_flash
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    parse_cli_arguments "$@"
    apply_configuration_defaults
    main
else
    apply_configuration_defaults
fi

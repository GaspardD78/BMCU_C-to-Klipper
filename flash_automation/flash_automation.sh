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
readonly DEFAULT_FIRMWARE_RELATIVE_PATHS=(".cache/klipper/out" ".cache/firmware")
readonly DEFAULT_FIRMWARE_RELATIVE_PATH="${DEFAULT_FIRMWARE_RELATIVE_PATHS[0]}"
FIRMWARE_DISPLAY_PATH="${KLIPPER_FIRMWARE_PATH:-}"
FIRMWARE_FILE=""
FIRMWARE_FORMAT=""
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

DEFAULT_CACHE_HOME="${XDG_CACHE_HOME:-${HOME}/.cache}"
PERMISSIONS_CACHE_FILE="${BMCU_PERMISSION_CACHE_FILE:-${DEFAULT_CACHE_HOME}/bmcu_permissions.json}"
PERMISSIONS_CACHE_TTL_RAW="${BMCU_PERMISSION_CACHE_TTL:-3600}"
if [[ "${PERMISSIONS_CACHE_TTL_RAW}" =~ ^[0-9]+$ ]]; then
    PERMISSIONS_CACHE_TTL="${PERMISSIONS_CACHE_TTL_RAW}"
else
    PERMISSIONS_CACHE_TTL=0
fi
PERMISSIONS_CACHE_MESSAGE=""

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

print_usage() {
    local script_name
    script_name="$(basename "${BASH_SOURCE[0]}")"
    cat <<EOF
Usage: ${script_name} [options]

Options:
  --wchisp-checksum <sha256>   Remplace la somme de contrôle attendue pour l'archive wchisp.
  --allow-unsigned-wchisp      Active le mode dégradé : conserve l'archive même si la vérification échoue.
  -h, --help                   Affiche cette aide et quitte.

Variables d'environnement associées :
  WCHISP_ARCHIVE_CHECKSUM_OVERRIDE  Injecte une somme de contrôle SHA-256 personnalisée.
  ALLOW_UNVERIFIED_WCHISP           "true"/"1" pour autoriser le mode dégradé.
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

function should_skip_permission_checks() {
    PERMISSIONS_CACHE_MESSAGE=""
    if ! permissions_cache_enabled; then
        return 1
    fi
    if [[ ! -f "${PERMISSIONS_CACHE_FILE}" ]]; then
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
    if ! actual=$(sha256sum "${archive_path}" 2>/dev/null | awk '{print $1}'); then
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

    if ! command_exists sha256sum; then
        error_msg "sha256sum est requis pour vérifier l'intégrité de l'archive wchisp."
        echo "Installez coreutils ou fournissez sha256sum dans votre PATH avant de relancer." >&2
        exit 1
    fi

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

    if ! command_exists dfu-util; then
        return
    fi

    while IFS= read -r line; do
        [[ -z "${line}" ]] && continue
        dfu_devices_ref+=("${line}")
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

    info "Analyse des périphériques série disponibles."
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
            done < <(find "${dir}" -maxdepth 3 -type f \( -name '*.bin' -o -name '*.uf2' -o -name '*.elf' \) -print0 2>/dev/null)
        fi
    fi

    for rel_path in "${DEFAULT_FIRMWARE_RELATIVE_PATHS[@]}"; do
        local default_dir="${FLASH_ROOT}/${rel_path}"
        [[ -d "${default_dir}" ]] || continue
        while IFS= read -r -d '' file; do
            [[ -n "${seen["${file}"]-}" ]] && continue
            seen["${file}"]=1
            firmware_candidates_ref+=("${file}")
        done < <(find "${default_dir}" -maxdepth 2 -type f \( -name '*.bin' -o -name '*.uf2' -o -name '*.elf' \) -print0 2>/dev/null)
    done

    local -a extra_search=("${FLASH_ROOT}")
    for dir in "${extra_search[@]}"; do
        [[ -d "${dir}" ]] || continue
        while IFS= read -r -d '' file; do
            [[ -n "${seen["${file}"]-}" ]] && continue
            seen["${file}"]=1
            firmware_candidates_ref+=("${file}")
        done < <(find "${dir}" -maxdepth 4 -type f \( -name '*.bin' -o -name '*.uf2' -o -name '*.elf' \) -print0 2>/dev/null)
    done

    if [[ ${#firmware_candidates_ref[@]} -gt 0 ]]; then
        mapfile -t firmware_candidates_ref < <(printf '%s\n' "${firmware_candidates_ref[@]}" | awk '!seen[$0]++')
    fi
}

function prompt_firmware_selection() {
    local -n candidates_ref=$1
    local choice=""

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

        read -rp "Votre choix : " answer

        if [[ "${answer}" =~ ^[0-9]+$ ]]; then
            local numeric=$((answer))
            if (( numeric >= 1 && numeric <= ${#candidates_ref[@]} )); then
                choice="${candidates_ref[$((numeric-1))]}"
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
        local search_roots
        search_roots=$(printf '%s' "${DEFAULT_FIRMWARE_RELATIVE_PATHS[*]}")
        error_msg "Aucun firmware compatible détecté (recherché dans ${search_roots}). Lancer './build.sh' ou fournir KLIPPER_FIRMWARE_PATH."
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

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    parse_cli_arguments "$@"
    apply_configuration_defaults
    main
else
    apply_configuration_defaults
fi

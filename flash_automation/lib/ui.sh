# shellcheck shell=bash

if [[ -n "${FLASH_AUTOMATION_LIB_UI_SH:-}" ]]; then
    return 0
fi
FLASH_AUTOMATION_LIB_UI_SH=1

format_duration_seconds() {
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

log_message() {
    local level="$1"
    local message="$2"
    local timestamp
    timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    if [[ -n "${LOG_FILE:-}" ]]; then
        local log_dir
        log_dir="$(dirname "${LOG_FILE}")"
        mkdir -p "${log_dir}" 2>/dev/null || true
        touch "${LOG_FILE}" 2>/dev/null || true
        echo "[$timestamp] [$level] - $message" >> "${LOG_FILE}" 2>/dev/null || true
    fi
}

render_box() {
    local title="$1"
    local border="========================================"
    if [[ "${QUIET_MODE}" == "true" ]]; then
        return
    fi
    printf "%b%s%b\n" "${COLOR_BORDER}" "${border}" "${COLOR_RESET}"
    printf "%b%s%b\n" "${COLOR_SECTION}" "${title}" "${COLOR_RESET}"
    printf "%b%s%b\n" "${COLOR_BORDER}" "${border}" "${COLOR_RESET}"
}

info() {
    local message="$1"
    log_message "INFO" "${message}"
    if [[ "${QUIET_MODE}" != "true" ]]; then
        printf "%b[INFO]%b %s\n" "${COLOR_INFO}" "${COLOR_RESET}" "${message}"
    fi
}

warn() {
    local message="$1"
    log_message "WARN" "${message}"
    printf "%b[WARN]%b %s\n" "${COLOR_WARN}" "${COLOR_RESET}" "${message}"
}

error_msg() {
    local message="$1"
    log_message "ERROR" "${message}"
    printf "%b[ERROR]%b %s\n" "${COLOR_ERROR}" "${COLOR_RESET}" "${message}" >&2
}

success() {
    local message="$1"
    log_message "INFO" "${message}"
    if [[ "${QUIET_MODE}" != "true" ]]; then
        printf "%b[OK]%b %s\n" "${COLOR_SUCCESS}" "${COLOR_RESET}" "${message}"
    fi
}

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

note() {
    local message="$1"
    log_message "INFO" "${message}"
    if [[ "${QUIET_MODE}" != "true" ]]; then
        printf "%b[NOTE]%b %s\n" "${COLOR_INFO}" "${COLOR_RESET}" "${message}"
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

declare -a CHECK_COMMAND_TRACKED_COMMANDS=()
declare -a CHECK_COMMAND_TRACKED_REQUIRED=()
declare -a CHECK_COMMAND_TRACKED_STATUS=()
declare -A CHECK_COMMAND_TRACKED_INDEX=()

reset_check_command_results() {
    CHECK_COMMAND_TRACKED_COMMANDS=()
    CHECK_COMMAND_TRACKED_REQUIRED=()
    CHECK_COMMAND_TRACKED_STATUS=()
    CHECK_COMMAND_TRACKED_INDEX=()
}

_check_command_status_severity() {
    local status="$1"
    local required="$2"
    if [[ "${status}" == "success" ]]; then
        printf '%s' "0"
    elif [[ "${required}" == "true" ]]; then
        printf '%s' "2"
    else
        printf '%s' "1"
    fi
}

register_check_command_result() {
    local command="$1"
    local required="$2"
    local status="$3"

    local index="${CHECK_COMMAND_TRACKED_INDEX["${command}"]-}"
    if [[ -n "${index}" ]]; then
        local current_status="${CHECK_COMMAND_TRACKED_STATUS[${index}]}"
        local current_required="${CHECK_COMMAND_TRACKED_REQUIRED[${index}]}"
        local new_severity
        local current_severity
        new_severity=$(_check_command_status_severity "${status}" "${required}")
        current_severity=$(_check_command_status_severity "${current_status}" "${current_required}")
        if (( new_severity > current_severity )); then
            CHECK_COMMAND_TRACKED_STATUS[${index}]="${status}"
            CHECK_COMMAND_TRACKED_REQUIRED[${index}]="${required}"
        fi
        return
    fi

    index=${#CHECK_COMMAND_TRACKED_COMMANDS[@]}
    CHECK_COMMAND_TRACKED_INDEX["${command}"]=${index}
    CHECK_COMMAND_TRACKED_COMMANDS+=("${command}")
    CHECK_COMMAND_TRACKED_REQUIRED+=("${required}")
    CHECK_COMMAND_TRACKED_STATUS+=("${status}")
}

display_check_command_summary() {
    if (( ${#CHECK_COMMAND_TRACKED_COMMANDS[@]} == 0 )); then
        return
    fi
    if [[ "${QUIET_MODE}" == "true" ]]; then
        return
    fi

    local header_command="Commande"
    local header_status="Statut"
    local width_command=${#header_command}
    local width_status=${#header_status}
    local -a labels=()
    local -a symbols=()
    local -a colors=()

    local i
    for i in "${!CHECK_COMMAND_TRACKED_COMMANDS[@]}"; do
        local command="${CHECK_COMMAND_TRACKED_COMMANDS[$i]}"
        local required="${CHECK_COMMAND_TRACKED_REQUIRED[$i]}"
        local status="${CHECK_COMMAND_TRACKED_STATUS[$i]}"
        local label=""
        local symbol=""
        local color="${COLOR_INFO}"

        if [[ "${status}" == "success" ]]; then
            label="Disponible"
            symbol="✔"
            color="${COLOR_SUCCESS}"
        else
            symbol="✖"
            if [[ "${required}" == "true" ]]; then
                label="Manquante (obligatoire)"
                color="${COLOR_ERROR}"
            else
                label="Absente (optionnelle)"
                color="${COLOR_WARN}"
            fi
        fi

        labels+=("${label}")
        symbols+=("${symbol}")
        colors+=("${color}")

        local command_len=${#command}
        local label_len=${#label}
        if (( command_len > width_command )); then
            width_command=${command_len}
        fi
        if (( label_len > width_status )); then
            width_status=${label_len}
        fi
    done

    local border_command=$(( width_command + 2 ))
    local border_status=$(( width_status + 2 ))
    local border_line
    border_line="+$(printf '%*s' "${border_command}" '' | tr ' ' '-')+$(printf '%*s' "${border_status}" '' | tr ' ' '-')+"

    printf "%s\n" "Résumé des dépendances :"
    printf "%b%s%b\n" "${COLOR_BORDER}" "${border_line}" "${COLOR_RESET}"
    printf "| %-*s | %-*s |\n" "${width_command}" "${header_command}" "${width_status}" "${header_status}"
    printf "%b%s%b\n" "${COLOR_BORDER}" "${border_line}" "${COLOR_RESET}"

    for i in "${!CHECK_COMMAND_TRACKED_COMMANDS[@]}"; do
        local command="${CHECK_COMMAND_TRACKED_COMMANDS[$i]}"
        local label="${labels[$i]}"
        local symbol="${symbols[$i]}"
        local color="${colors[$i]}"
        printf "| %b%s%b %-*s | %-*s |\n" "${color}" "${symbol}" "${COLOR_RESET}" "${width_command}" "${command}" "${width_status}" "${label}"
    done

    printf "%b%s%b\n" "${COLOR_BORDER}" "${border_line}" "${COLOR_RESET}"
}

SPINNER_PID=""

_spinner_chars="⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

_spinner() {
    # Hide cursor
    if command -v tput >/dev/null; then
        tput civis
    fi
    while true; do
        for (( i=0; i<${#_spinner_chars}; i++ )); do
            char="${_spinner_chars:$i:1}"
            printf "\r%b[ %s ]%b %s" "${COLOR_INFO}" "${char}" "${COLOR_RESET}" "${1}"
            sleep 0.1
        done
    done
}

spinner_start() {
    local message="${1:-}"
    if [[ "${QUIET_MODE}" == "true" || -n "${SPINNER_PID}" ]]; then
        return
    fi
    if [[ ! -t 1 && "${FLASH_AUTOMATION_FORCE_SPINNER:-}" != "true" ]]; then
        # Affichage statique si non interactif et non forcé
        printf "%b[INFO]%b %s\n" "${COLOR_INFO}" "${COLOR_RESET}" "${message}"
        return
    fi
    _spinner "${message}" &
    SPINNER_PID=$!
    # Ensure spinner is killed on exit
    trap 'spinner_stop >/dev/null 2>&1' EXIT SIGHUP SIGINT SIGQUIT SIGTERM
}

spinner_stop() {
    if [[ -z "${SPINNER_PID}" ]]; then
        return
    fi
    if kill -0 "$SPINNER_PID" >/dev/null 2>&1; then
        kill "$SPINNER_PID" >/dev/null 2>&1
        wait "$SPINNER_PID" 2>/dev/null
    fi
    # Clear the line and show cursor
    printf "\r\033[K"
    if command -v tput >/dev/null; then
        tput cnorm
    fi
    SPINNER_PID=""
    trap - EXIT SIGHUP SIGINT SIGQUIT SIGTERM
}

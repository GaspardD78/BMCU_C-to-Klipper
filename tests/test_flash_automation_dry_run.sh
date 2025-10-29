#!/bin/bash
# Tests d'intégration rapides pour le mode --dry-run de flash_automation.sh.
#
# Ces scénarios couvrent les principaux chemins "automatisés" (wchisp, serial,
# sdcard) en validant que les nouvelles options CLI permettent d'exécuter le
# script sans interaction utilisateur.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLASH_ROOT="${REPO_ROOT}/flash_automation"
FLASH_SCRIPT="${FLASH_ROOT}/flash_automation.sh"

TMP_DIR="$(mktemp -d)"
LOG_DIR="${FLASH_ROOT}/logs"

cleanup() {
    rm -rf "${TMP_DIR}"
    rm -rf "${LOG_DIR}"
}

trap cleanup EXIT

rm -rf "${LOG_DIR}"

FIRMWARE_FILE="${TMP_DIR}/klipper.bin"
printf 'dummy firmware' > "${FIRMWARE_FILE}"

SERIAL_STUB="${TMP_DIR}/ttyUSB_FAKE"
SDCARD_DIR="${TMP_DIR}/sdcard"
mkdir -p "${SDCARD_DIR}"
:
> "${SERIAL_STUB}"

run_flash() {
    local -r label="$1"
    shift

    local -a env_args=()
    local -a cli_args=()
    local parsing_env="true"

    for arg in "$@"; do
        if [[ "${parsing_env}" == "true" && "${arg}" == "--" ]]; then
            parsing_env="false"
            continue
        fi
        if [[ "${parsing_env}" == "true" ]]; then
            env_args+=("${arg}")
        else
            cli_args+=("${arg}")
        fi
    done

    echo "[TEST] ${label}" >&2
    local output
    if [[ ${#env_args[@]} -gt 0 ]]; then
        output=$(cd "${FLASH_ROOT}" && env "${env_args[@]}" "${FLASH_SCRIPT}" \
            --firmware "${FIRMWARE_FILE}" --dry-run --auto-confirm "${cli_args[@]}")
    else
        output=$(cd "${FLASH_ROOT}" && "${FLASH_SCRIPT}" \
            --firmware "${FIRMWARE_FILE}" --dry-run --auto-confirm "${cli_args[@]}")
    fi

    printf '%s\n' "${output}"
}

# 1. Mode wchisp forcé par la CLI.
output=$(run_flash "dry-run wchisp (CLI)" \
    WCHISP_BIN="/bin/true" \
    HOME="${TMP_DIR}" \
    XDG_CACHE_HOME="${TMP_DIR}/xdg-cache" \
    -- --method wchisp)
if [[ "${output}" != *"[DRY-RUN] wchisp flasherait"* ]]; then
    echo "[ERREUR] Le mode --dry-run wchisp n'a pas été détecté dans la sortie." >&2
    exit 1
fi

# 2. Mode serial avec port imposé en CLI.
output=$(run_flash "dry-run serial (CLI)" \
    WCHISP_BIN="/bin/true" \
    HOME="${TMP_DIR}" \
    XDG_CACHE_HOME="${TMP_DIR}/xdg-cache" \
    -- --method serial --serial-port "${SERIAL_STUB}")
if [[ "${output}" != *"Port série imposé"* ]]; then
    echo "[ERREUR] Le port série imposé n'a pas été confirmé." >&2
    exit 1
fi

# 3. Mode sdcard imposé via variables d'environnement.
output=$(run_flash "dry-run sdcard (ENV)" \
    WCHISP_BIN="/bin/true" \
    FLASH_AUTOMATION_METHOD="sdcard" \
    FLASH_AUTOMATION_SDCARD_PATH="${SDCARD_DIR}" \
    HOME="${TMP_DIR}" \
    XDG_CACHE_HOME="${TMP_DIR}/xdg-cache")
if [[ "${output}" != *"[DRY-RUN] Copie simulée"* ]]; then
    echo "[ERREUR] La copie simulée n'a pas été détectée dans la sortie." >&2
    exit 1
fi

echo "Tests d'intégration --dry-run : OK"

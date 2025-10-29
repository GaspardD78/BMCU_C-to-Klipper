#!/bin/bash
# Tests minimaux pour la logique de cache de permissions lorsque python3 est indisponible.
# Ces tests s'exécutent entièrement en Bash et valident le comportement de secours.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLASH_SCRIPT="${REPO_ROOT}/flash_automation/flash_automation.sh"

TMP_DIR="$(mktemp -d)"
LOG_DIR="${REPO_ROOT}/flash_automation/logs"

cleanup() {
    rm -rf "${TMP_DIR}"
    rm -rf "${LOG_DIR}"
}

trap cleanup EXIT

rm -rf "${LOG_DIR}"

export XDG_CACHE_HOME="${TMP_DIR}/xdg-cache"
export BMCU_PERMISSION_CACHE_FILE="${TMP_DIR}/bmcu_permissions.tsv"
export BMCU_PERMISSION_CACHE_BACKEND="bash"

run_flash_script() {
    local -r snippet="$1"
    env \
        FLASH_SCRIPT="${FLASH_SCRIPT}" \
        BMCU_PERMISSION_CACHE_FILE="${BMCU_PERMISSION_CACHE_FILE}" \
        BMCU_PERMISSION_CACHE_TTL="${BMCU_PERMISSION_CACHE_TTL}" \
        BMCU_PERMISSION_CACHE_BACKEND="${BMCU_PERMISSION_CACHE_BACKEND}" \
        FLASH_SNIPPET="${snippet}" \
        XDG_CACHE_HOME="${XDG_CACHE_HOME}" \
        bash -c 'set -euo pipefail; source "${FLASH_SCRIPT}"; flash_automation_initialize; eval "${FLASH_SNIPPET}"'
}

# 1. Sans cache pré-existant, should_skip_permission_checks doit échouer.
BMCU_PERMISSION_CACHE_TTL=120
output=$(run_flash_script 'if should_skip_permission_checks; then echo "status=0"; else echo "status=1"; fi')
status_line=$(printf '%s\n' "${output}" | tail -n1)
if [[ "${status_line}" != "status=1" ]]; then
    echo "[ERREUR] should_skip_permission_checks devrait échouer sans cache valide." >&2
    exit 1
fi

# 2. Création d'un cache via l'écriture Bash et validation de la lecture.
run_flash_script 'update_permissions_cache "ok" "cache bash"'
IFS=$'\t' read -r status epoch ttl origin message < "${BMCU_PERMISSION_CACHE_FILE}" || {
    echo "[ERREUR] Impossible de lire le fichier de cache généré." >&2
    exit 1
}

if [[ "${status}" != "ok" ]]; then
    echo "[ERREUR] Statut inattendu dans le cache Bash: ${status}" >&2
    exit 1
fi

if [[ -z "${epoch}" ]]; then
    echo "[ERREUR] Timestamp absent dans le cache Bash." >&2
    exit 1
fi

if ! [[ "${epoch}" =~ ^[0-9]+$ ]]; then
    echo "[ERREUR] Timestamp invalide dans le cache Bash: ${epoch}" >&2
    exit 1
fi

if [[ "${ttl}" -ne "${BMCU_PERMISSION_CACHE_TTL}" ]]; then
    echo "[ERREUR] TTL inattendu dans le cache Bash: ${ttl}" >&2
    exit 1
fi

if [[ "${origin}" != "flash_automation.verify_environment" ]]; then
    echo "[ERREUR] Origine inattendue dans le cache Bash: ${origin}" >&2
    exit 1
fi

if [[ "${message}" != "cache bash" ]]; then
    echo "[ERREUR] Message inattendu dans le cache Bash: ${message}" >&2
    exit 1
fi

result=$(run_flash_script 'if should_skip_permission_checks; then echo "status=0"; else echo "status=1"; fi; echo "message=${PERMISSIONS_CACHE_MESSAGE}"')
status_line=$(printf '%s\n' "${result}" | tail -n2 | head -n1)
message_line=$(printf '%s\n' "${result}" | tail -n1)

if [[ "${status_line}" != "status=0" ]]; then
    echo "[ERREUR] Le cache Bash devrait être considéré comme valide." >&2
    exit 1
fi

if [[ "${message_line}" != message=* ]]; then
    echo "[ERREUR] Aucun message de cache n'a été renvoyé." >&2
    exit 1
fi

# 3. TTL très court : le cache doit expirer.
BMCU_PERMISSION_CACHE_TTL=1
run_flash_script 'update_permissions_cache "ok" "expirable"'
sleep 2
expired=$(run_flash_script 'if should_skip_permission_checks; then echo "status=0"; else echo "status=1"; fi')
expired_status=$(printf '%s\n' "${expired}" | tail -n1)
if [[ "${expired_status}" != "status=1" ]]; then
    echo "[ERREUR] Le cache Bash aurait dû expirer." >&2
    exit 1
fi

echo "Tests Bash du cache de permissions : OK"

#!/bin/bash
# Vérifie qu'un simple "source" du script n'initialise pas la journalisation.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLASH_ROOT="${REPO_ROOT}/flash_automation"
FLASH_SCRIPT="${FLASH_ROOT}/flash_automation.sh"
LOG_DIR="${FLASH_ROOT}/logs"

rm -rf "${LOG_DIR}"

bash -c 'set -euo pipefail; source "'"${FLASH_SCRIPT}"'" >/dev/null'

if [[ -e "${LOG_DIR}" ]]; then
    echo "[ERREUR] Un simple source a créé ${LOG_DIR}." >&2
    exit 1
fi

echo "Test source sans logs : OK"

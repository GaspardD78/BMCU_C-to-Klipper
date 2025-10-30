#!/bin/bash
# Test d'intégration pour le flash_automation.sh en mode non-interactif via la méthode sdcard.
#
# Ce scénario vérifie que le script peut copier un firmware sur un point de montage
# de carte SD simulé en utilisant les options non-interactives.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLASH_ROOT="${REPO_ROOT}/flash_automation"
FLASH_SCRIPT="${FLASH_ROOT}/flash_automation.sh"

WORK_DIR="$(mktemp -d)"

cleanup() {
    rm -rf "${WORK_DIR}"
    # Supprimer les logs pour ne pas polluer les exécutions suivantes
    rm -f "${FLASH_ROOT}"/flash_automation_*.log
}
trap cleanup EXIT

# 1. Préparer un firmware factice
FIRMWARE_DIR="${WORK_DIR}/firmware"
mkdir -p "${FIRMWARE_DIR}"
FIRMWARE_NAME="bmcu_test.bin"
FIRMWARE_PATH="${FIRMWARE_DIR}/${FIRMWARE_NAME}"
FIRMWARE_CONTENT="firmware-payload"
printf '%s' "${FIRMWARE_CONTENT}" > "${FIRMWARE_PATH}"

# 2. Préparer un point de montage SD factice
SDCARD_MOUNT="${WORK_DIR}/sdcard"
mkdir -p "${SDCARD_MOUNT}"

# 3. Exécuter le script
"${FLASH_SCRIPT}" \
    --firmware "${FIRMWARE_PATH}" \
    --method sdcard \
    --sdcard-path "${SDCARD_MOUNT}" \
    --auto-confirm

# 4. Vérifier que le firmware a bien été copié
FINAL_FIRMWARE_PATH="${SDCARD_MOUNT}/${FIRMWARE_NAME}"
if [[ ! -f "${FINAL_FIRMWARE_PATH}" ]]; then
    echo "[ERREUR] Le firmware n'a pas été copié sur ${SDCARD_MOUNT}." >&2
    exit 1
fi

# 5. Vérifier que le contenu du firmware est correct
if [[ "$(cat "${FINAL_FIRMWARE_PATH}")" != "${FIRMWARE_CONTENT}" ]]; then
    echo "[ERREUR] Le contenu du firmware copié est incorrect." >&2
    exit 1
fi

echo "Test sdcard non-interactif : OK"

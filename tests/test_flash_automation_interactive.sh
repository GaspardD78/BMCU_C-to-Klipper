#!/bin/bash
# Test d'intégration interactif (Expect) pour flash_automation.sh.
#
# Ce scénario vérifie que, sans options CLI, le script reste pilotable en
# mode interactif : sélection d'un firmware, choix de la méthode et saisie du
# point de montage SD.

set -euo pipefail

if ! command -v expect >/dev/null 2>&1; then
    echo "SKIP: expect n'est pas disponible, test interactif non exécuté." >&2
    exit 0
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLASH_ROOT="${REPO_ROOT}/flash_automation"
FLASH_SCRIPT="${FLASH_ROOT}/flash_automation.sh"

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "${WORK_DIR}"' EXIT

FIRMWARE_DIR="${WORK_DIR}/firmware"
SDCARD_MOUNT="${WORK_DIR}/sdcard"
mkdir -p "${FIRMWARE_DIR}" "${SDCARD_MOUNT}" "${WORK_DIR}/xdg-cache"

FIRMWARE_NAME="bmcu_test.bin"
printf 'firmware-interactif' > "${FIRMWARE_DIR}/${FIRMWARE_NAME}"

expect <<'EOF' "${FLASH_SCRIPT}" "${FIRMWARE_DIR}" "${FIRMWARE_NAME}" "${SDCARD_MOUNT}" "${WORK_DIR}"
set timeout 30
set script [lindex $argv 0]
set firmware_dir [lindex $argv 1]
set firmware_name [lindex $argv 2]
set mountpoint [lindex $argv 3]
set workdir [lindex $argv 4]

set env(WCHISP_BIN) "/bin/true"
set env(KLIPPER_FIRMWARE_PATH) $firmware_dir
set env(HOME) $workdir
set env(XDG_CACHE_HOME) "$workdir/xdg-cache"

spawn -noecho $script

expect -re "Sélectionnez le firmware"
send "1\r"

expect -re "Méthode choisie"
send "3\r"

expect -re "Point de montage de la carte SD"
send "$mountpoint\r"

expect -re ">>> Procédure terminée avec succès"
expect eof
EOF

if [[ ! -f "${SDCARD_MOUNT}/${FIRMWARE_NAME}" ]]; then
    echo "[ERREUR] Le firmware n'a pas été copié sur ${SDCARD_MOUNT}." >&2
    exit 1
fi

echo "Test interactif Expect : OK"

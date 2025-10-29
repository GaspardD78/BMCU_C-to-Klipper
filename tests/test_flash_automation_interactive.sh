#!/bin/bash
# Test d'intégration interactif (Expect) pour flash_automation.sh.
#
# Ce scénario vérifie que, sans options CLI, le script reste pilotable en
# mode interactif : sélection d'un firmware, choix de la méthode et saisie du
# point de montage SD.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLASH_ROOT="${REPO_ROOT}/flash_automation"
FLASH_SCRIPT="${FLASH_ROOT}/flash_automation.sh"

WORK_DIR="$(mktemp -d)"
LOG_DIR="${FLASH_ROOT}/logs"

cleanup() {
    rm -rf "${WORK_DIR}"
    rm -rf "${LOG_DIR}"
}

trap cleanup EXIT

rm -rf "${LOG_DIR}"

FIRMWARE_DIR="${WORK_DIR}/firmware"
SDCARD_MOUNT="${WORK_DIR}/sdcard"
mkdir -p "${FIRMWARE_DIR}" "${SDCARD_MOUNT}" "${WORK_DIR}/xdg-cache"

FIRMWARE_NAME="bmcu_test.bin"
printf 'firmware-interactif' > "${FIRMWARE_DIR}/${FIRMWARE_NAME}"

run_with_expect() {
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
}

run_with_python_fallback() {
    echo "INFO: 'expect' n'est pas disponible, passage sur le pilote interactif Python." >&2
    python3 - <<'PY' "${FLASH_SCRIPT}" "${FIRMWARE_DIR}" "${FIRMWARE_NAME}" "${SDCARD_MOUNT}" "${WORK_DIR}"
import os
import pty
import re
import select
import sys
import time

script, firmware_dir, firmware_name, mountpoint, workdir = sys.argv[1:6]

env = os.environ.copy()
env.update(
    {
        "WCHISP_BIN": "/bin/true",
        "KLIPPER_FIRMWARE_PATH": firmware_dir,
        "HOME": workdir,
        "XDG_CACHE_HOME": os.path.join(workdir, "xdg-cache"),
    }
)

pattern_sequence = [
    (r"Sélectionnez le firmware", "1\n"),
    (r"Méthode choisie", "3\n"),
    (r"Point de montage de la carte SD", f"{mountpoint}\n"),
]

captured = ""


def expect_pattern(master_fd: int, pattern: str, timeout: float = 30.0) -> None:
    compiled = re.compile(pattern)
    deadline = time.monotonic() + timeout
    global captured

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"Expiration en attendant {pattern!r}. Sortie:\n{captured}")

        ready, _, _ = select.select([master_fd], [], [], remaining)
        if master_fd not in ready:
            continue

        chunk = os.read(master_fd, 4096)
        if not chunk:
            raise RuntimeError(
                f"Flux fermé en attendant {pattern!r}. Sortie cumulée:\n{captured}"
            )

        text = chunk.decode("utf-8", "replace")
        sys.stdout.write(text)
        sys.stdout.flush()

        captured += text
        if compiled.search(captured):
            return


def send_line(master_fd: int, payload: str) -> None:
    os.write(master_fd, payload.encode("utf-8"))


def drain(master_fd: int) -> None:
    while True:
        try:
            chunk = os.read(master_fd, 4096)
            if not chunk:
                return
            text = chunk.decode("utf-8", "replace")
            sys.stdout.write(text)
            sys.stdout.flush()
        except OSError:
            return


pid, master_fd = pty.fork()
if pid == 0:
    os.execvpe("bash", ["bash", script], env)

try:
    for pattern, response in pattern_sequence:
        expect_pattern(master_fd, pattern)
        send_line(master_fd, response)

    expect_pattern(master_fd, r">>> Procédure terminée avec succès")
    drain(master_fd)
finally:
    os.close(master_fd)
    _, status = os.waitpid(pid, 0)

if os.WIFEXITED(status):
    exit_code = os.WEXITSTATUS(status)
    if exit_code:
        raise SystemExit(exit_code)
elif os.WIFSIGNALED(status):
    raise SystemExit(f"Processus interrompu par le signal {os.WTERMSIG(status)}")
PY
}

if command -v expect >/dev/null 2>&1; then
    run_with_expect
else
    run_with_python_fallback
fi

if [[ ! -f "${SDCARD_MOUNT}/${FIRMWARE_NAME}" ]]; then
    echo "[ERREUR] Le firmware n'a pas été copié sur ${SDCARD_MOUNT}." >&2
    exit 1
fi

echo "Test interactif : OK"

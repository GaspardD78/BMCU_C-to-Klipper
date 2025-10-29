#!/bin/bash
# Tests ciblant les wrappers portables (stat/sha256/dfu) de flash_automation.sh.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLASH_SCRIPT="${REPO_ROOT}/flash_automation/flash_automation.sh"
LOG_ROOT="${REPO_ROOT}/flash_automation/logs"
TMP_DIR="$(mktemp -d)"
cleanup() {
    rm -rf "${TMP_DIR}"
    rm -rf "${LOG_ROOT}"
}

trap cleanup EXIT

rm -rf "${LOG_ROOT}"

make_common_stubs() {
    local dir="$1"
    mkdir -p "${dir}"

    cat <<'STUB' > "${dir}/awk"
#!/bin/bash
exec /usr/bin/awk "$@"
STUB
    chmod +x "${dir}/awk"
}

assert_equals() {
    local expected="$1"
    local actual="$2"
    local message="$3"
    if [[ "${expected}" != "${actual}" ]]; then
        echo "[ERREUR] ${message} (attendu='${expected}', obtenu='${actual}')" >&2
        exit 1
    fi
}

assert_contains() {
    local needle="$1"
    local haystack="$2"
    local message="$3"
    if [[ "${haystack}" != *"${needle}"* ]]; then
        echo "[ERREUR] ${message} (texte='${haystack}')" >&2
        exit 1
    fi
}

# 1. portable_sha256 doit utiliser shasum lorsque sha256sum est absent (macOS simulé).
fake_bin_sha="${TMP_DIR}/bin-sha"
make_common_stubs "${fake_bin_sha}"
cat <<'STUB' > "${fake_bin_sha}/sha256sum"
#!/bin/bash
exit 127
STUB
chmod +x "${fake_bin_sha}/sha256sum"
cat <<'STUB' > "${fake_bin_sha}/shasum"
#!/bin/bash
if [[ "$1" == "-a" ]]; then
    shift 2
fi
for file in "$@"; do
    printf 'FAKEHASH  %s\n' "${file}"
    break
done
STUB
chmod +x "${fake_bin_sha}/shasum"

mkdir -p "${TMP_DIR}/home-sha" "${TMP_DIR}/cache-sha"
firmware_sample="${TMP_DIR}/firmware.bin"
printf 'dummy' > "${firmware_sample}"

sha_output=$(env PATH="${fake_bin_sha}:/bin" \
    FLASH_AUTOMATION_OS_OVERRIDE=Darwin \
    HOME="${TMP_DIR}/home-sha" \
    XDG_CACHE_HOME="${TMP_DIR}/cache-sha" \
    bash -c 'set -euo pipefail; source "'"${FLASH_SCRIPT}"'" >/dev/null; flash_automation_initialize; portable_sha256 "'"${firmware_sample}"'"')
assert_equals "FAKEHASH" "${sha_output}" "portable_sha256 devrait utiliser shasum sur macOS"

# 2. portable_stat doit s'appuyer sur gstat lorsque disponible sur macOS.
fake_bin_gstat="${TMP_DIR}/bin-gstat"
make_common_stubs "${fake_bin_gstat}"
cat <<'STUB' > "${fake_bin_gstat}/gstat"
#!/bin/bash
if [[ "$1" != "--printf=%s" ]]; then
    echo "unsupported" >&2
    exit 1
fi
bytes=$(/usr/bin/wc -c < "$2")
bytes="${bytes//[[:space:]]/}"
printf '%s' "${bytes}"
STUB
chmod +x "${fake_bin_gstat}/gstat"

mkdir -p "${TMP_DIR}/home-gstat" "${TMP_DIR}/cache-gstat"
file_gstat="${TMP_DIR}/sample-gstat.bin"
printf '123456' > "${file_gstat}"
expected_size="6"

stat_output=$(env PATH="${fake_bin_gstat}:/bin" \
    FLASH_AUTOMATION_OS_OVERRIDE=Darwin \
    HOME="${TMP_DIR}/home-gstat" \
    XDG_CACHE_HOME="${TMP_DIR}/cache-gstat" \
    bash -c 'set -euo pipefail; source "'"${FLASH_SCRIPT}"'" >/dev/null; flash_automation_initialize; portable_stat "--printf=%s" "'"${file_gstat}"'"')
assert_equals "${expected_size}" "${stat_output}" "portable_stat devrait utiliser gstat sur macOS"

# 3. portable_stat doit basculer sur stat BSD lorsque gstat est absent.
fake_bin_stat="${TMP_DIR}/bin-stat"
make_common_stubs "${fake_bin_stat}"
cat <<'STUB' > "${fake_bin_stat}/stat"
#!/bin/bash
if [[ "$1" == "-f" && "$2" == "%z" ]]; then
    bytes=$(/usr/bin/wc -c < "$3")
    bytes="${bytes//[[:space:]]/}"
    printf '%s\n' "${bytes}"
else
    echo "unsupported" >&2
    exit 1
fi
STUB
chmod +x "${fake_bin_stat}/stat"

mkdir -p "${TMP_DIR}/home-stat" "${TMP_DIR}/cache-stat"
file_stat="${TMP_DIR}/sample-stat.bin"
printf 'ABCD' > "${file_stat}"
expected_stat="4"

bsd_output=$(env PATH="${fake_bin_stat}:/bin" \
    FLASH_AUTOMATION_OS_OVERRIDE=Darwin \
    HOME="${TMP_DIR}/home-stat" \
    XDG_CACHE_HOME="${TMP_DIR}/cache-stat" \
    bash -c 'set -euo pipefail; source "'"${FLASH_SCRIPT}"'" >/dev/null; flash_automation_initialize; portable_stat "--printf=%s" "'"${file_stat}"'"')
assert_equals "${expected_stat}" "${bsd_output}" "portable_stat devrait supporter stat BSD"

# 4. portable_dfu_util doit utiliser DFU_UTIL_BIN lorsque fourni.
fake_bin_dfu="${TMP_DIR}/bin-dfu"
make_common_stubs "${fake_bin_dfu}"
cat <<'STUB' > "${fake_bin_dfu}/custom-dfu"
#!/bin/bash
printf 'dfu-stub %s\n' "$*"
STUB
chmod +x "${fake_bin_dfu}/custom-dfu"

mkdir -p "${TMP_DIR}/home-dfu" "${TMP_DIR}/cache-dfu"
dfu_output=$(env PATH="${fake_bin_dfu}:/bin" \
    FLASH_AUTOMATION_OS_OVERRIDE=Linux \
    DFU_UTIL_BIN="${fake_bin_dfu}/custom-dfu" \
    HOME="${TMP_DIR}/home-dfu" \
    XDG_CACHE_HOME="${TMP_DIR}/cache-dfu" \
    bash -c 'set -euo pipefail; source "'"${FLASH_SCRIPT}"'" >/dev/null; flash_automation_initialize; portable_dfu_util foo bar')
assert_equals "dfu-stub foo bar" "${dfu_output}" "portable_dfu_util devrait respecter DFU_UTIL_BIN"

# 5. ensure_portable_sha256_available doit suggérer Homebrew sur macOS lorsqu'aucun outil n'est présent.
fake_bin_err="${TMP_DIR}/bin-err"
make_common_stubs "${fake_bin_err}"
mkdir -p "${TMP_DIR}/home-err" "${TMP_DIR}/cache-err"
set +e
err_output=$(env PATH="${fake_bin_err}:/bin" \
    FLASH_AUTOMATION_OS_OVERRIDE=Darwin \
    FLASH_AUTOMATION_SHA256_SKIP="sha256sum,gsha256sum,shasum" \
    HOME="${TMP_DIR}/home-err" \
    XDG_CACHE_HOME="${TMP_DIR}/cache-err" \
    bash -c 'set -euo pipefail; source "'"${FLASH_SCRIPT}"'" >/dev/null; flash_automation_initialize; ensure_portable_sha256_available' 2>&1)
err_status=$?
set -e
if [[ ${err_status} -eq 0 ]]; then
    echo "[ERREUR] ensure_portable_sha256_available aurait dû échouer sans outil SHA." >&2
    exit 1
fi
assert_contains "brew install coreutils" "${err_output}" "Le message d'erreur SHA256 sur macOS devrait suggérer Homebrew"

echo "Tests portables : OK"

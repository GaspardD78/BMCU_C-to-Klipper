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

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLASH_ROOT="${SCRIPT_DIR}"
CACHE_ROOT="${FLASH_ROOT}/.cache"
DEFAULT_KLIPPER_DIR="${CACHE_ROOT}/klipper"
KLIPPER_DIR="${KLIPPER_SRC_DIR:-${DEFAULT_KLIPPER_DIR}}"
KLIPPER_DIR="${KLIPPER_DIR%/}"
USE_EXISTING_KLIPPER="false"
if [[ -n "${KLIPPER_SRC_DIR:-}" ]]; then
    USE_EXISTING_KLIPPER="true"
fi
LOGO_FILE="${FLASH_ROOT}/banner.txt"
OVERRIDES_DIR="${FLASH_ROOT}/klipper_overrides"
TOOLCHAIN_PREFIX="${CROSS_PREFIX:-riscv32-unknown-elf-}"
TOOLCHAIN_CACHE_DIR="${CACHE_ROOT}/toolchains"
TOOLCHAIN_RELEASE="${TOOLCHAIN_RELEASE:-2025.10.18}"
TOOLCHAIN_ARCHIVE_X86_64="${TOOLCHAIN_ARCHIVE_X86_64:-riscv32-elf-ubuntu-22.04-gcc.tar.xz}"
TOOLCHAIN_BASE_URL="${TOOLCHAIN_BASE_URL:-https://github.com/riscv-collab/riscv-gnu-toolchain/releases/download/${TOOLCHAIN_RELEASE}}"
HOST_ARCH="$(uname -m)"
SUPPORTED_AUTO_TOOLCHAIN_ARCHS=("x86_64" "amd64")
AUTO_TOOLCHAIN_SUPPORTED="false"
for arch in "${SUPPORTED_AUTO_TOOLCHAIN_ARCHS[@]}"; do
    if [[ "${HOST_ARCH}" == "${arch}" ]]; then
        AUTO_TOOLCHAIN_SUPPORTED="true"
        break
    fi
done

if [[ "${AUTO_TOOLCHAIN_SUPPORTED}" == "true" ]]; then
    TOOLCHAIN_ARCHIVE="${TOOLCHAIN_ARCHIVE_X86_64}"
    TOOLCHAIN_URL="${TOOLCHAIN_BASE_URL}/${TOOLCHAIN_ARCHIVE}"
else
    TOOLCHAIN_ARCHIVE=""
    TOOLCHAIN_URL=""
fi

TOOLCHAIN_INSTALL_DIR="${TOOLCHAIN_CACHE_DIR}/riscv32-elf-${TOOLCHAIN_RELEASE}"
TOOLCHAIN_BIN_DIR="${TOOLCHAIN_INSTALL_DIR}/riscv/bin"
KLIPPER_REPO_URL="${KLIPPER_REPO_URL:-https://github.com/Klipper3d/klipper.git}"
KLIPPER_REF="${KLIPPER_REF:-master}"
KLIPPER_CLONE_DEPTH="${KLIPPER_CLONE_DEPTH:-1}"
KLIPPER_FETCH_REFSPEC="${KLIPPER_FETCH_REFSPEC:-}"
if [[ -z "${KLIPPER_FETCH_REFSPEC}" ]]; then
    if [[ "${KLIPPER_REF}" == refs/* ]]; then
        KLIPPER_FETCH_REFSPEC="${KLIPPER_REF}"
    elif [[ "${KLIPPER_REF}" =~ ^v[0-9] ]]; then
        KLIPPER_FETCH_REFSPEC="refs/tags/${KLIPPER_REF}"
    else
        KLIPPER_FETCH_REFSPEC="refs/heads/${KLIPPER_REF}"
    fi
elif [[ "${KLIPPER_FETCH_REFSPEC}" != refs/* ]]; then
    KLIPPER_FETCH_REFSPEC="refs/heads/${KLIPPER_FETCH_REFSPEC}"
fi

case "${KLIPPER_FETCH_REFSPEC}" in
    refs/heads/*)
        KLIPPER_LOCAL_TRACKING_REF="refs/remotes/origin/${KLIPPER_FETCH_REFSPEC#refs/heads/}"
        ;;
    *)
        KLIPPER_LOCAL_TRACKING_REF="${KLIPPER_FETCH_REFSPEC}"
        ;;
esac

KLIPPER_METADATA_FILE="${CACHE_ROOT}/klipper.bin.meta"
INPUT_FINGERPRINT=""
INPUT_LATEST_MTIME="0"

if [[ -t 1 ]]; then
    readonly COLOR_INFO="\e[34m"
    readonly COLOR_SUCCESS="\e[32m"
    readonly COLOR_ERROR="\e[31m"
    readonly COLOR_RESET="\e[0m"
else
    readonly COLOR_INFO=""
    readonly COLOR_SUCCESS=""
    readonly COLOR_ERROR=""
    readonly COLOR_RESET=""
fi

print_info() {
    printf "%s[INFO]%s %s\n" "${COLOR_INFO}" "${COLOR_RESET}" "$1"
}

print_success() {
    printf "%s[OK]%s %s\n" "${COLOR_SUCCESS}" "${COLOR_RESET}" "$1"
}

print_error() {
    printf "%s[ERREUR]%s %s\n" "${COLOR_ERROR}" "${COLOR_RESET}" "$1" >&2
}

bootstrap_toolchain() {
    if [[ -n "${CROSS_PREFIX:-}" ]]; then
        print_error "${TOOLCHAIN_PREFIX}gcc est introuvable alors que CROSS_PREFIX est défini. Installez la toolchain pointée par CROSS_PREFIX ou ajustez sa valeur (voir README pour les options ARM)."
        exit 1
    fi

    local toolchain_gcc="${TOOLCHAIN_BIN_DIR}/${TOOLCHAIN_PREFIX}gcc"

    if [[ "${AUTO_TOOLCHAIN_SUPPORTED}" != "true" ]]; then
        print_error "Téléchargement automatique indisponible sur l'architecture ${HOST_ARCH}. Installez une toolchain RISC-V compatible puis relancez en exportant CROSS_PREFIX vers son préfixe binaire (ex. /opt/riscv/bin/riscv-none-elf-)."
        exit 1
    fi

    if [[ -x "${toolchain_gcc}" ]]; then
        export PATH="${TOOLCHAIN_BIN_DIR}:${PATH}"
        print_info "Utilisation de la toolchain locale : ${toolchain_gcc}"
        return
    fi

    if ! command -v curl >/dev/null 2>&1; then
        print_error "curl est requis pour télécharger automatiquement la toolchain RISC-V. Installez curl ou la toolchain manuellement."
        exit 1
    fi

    if ! command -v tar >/dev/null 2>&1; then
        print_error "tar est requis pour extraire la toolchain RISC-V. Installez tar ou la toolchain manuellement."
        exit 1
    fi

    mkdir -p "${TOOLCHAIN_CACHE_DIR}"
    local archive_path="${TOOLCHAIN_CACHE_DIR}/${TOOLCHAIN_ARCHIVE}"

    if [[ ! -f "${archive_path}" ]]; then
        print_info "Téléchargement de la toolchain RISC-V (${TOOLCHAIN_RELEASE})..."
        if ! curl --fail --location --progress-bar "${TOOLCHAIN_URL}" -o "${archive_path}"; then
            print_error "Échec du téléchargement de la toolchain depuis ${TOOLCHAIN_URL}"
            rm -f "${archive_path}"
            exit 1
        fi
    else
        print_info "Archive toolchain déjà présente, réutilisation de ${archive_path}"
    fi

    rm -rf "${TOOLCHAIN_INSTALL_DIR}"
    mkdir -p "${TOOLCHAIN_INSTALL_DIR}"

    local tar_args=(-xf "${archive_path}" --strip-components=1 -C "${TOOLCHAIN_INSTALL_DIR}")
    tar_args+=("--exclude=*/share/doc/*" "--exclude=*/share/info/*" "--exclude=*/share/man/*")

    print_info "Extraction de la toolchain dans ${TOOLCHAIN_INSTALL_DIR} (compression .xz multi-threads si disponible)"

    local extraction_status=0
    if [[ "${archive_path}" == *.tar.xz && -z "${XZ_OPT:-}" ]]; then
        if command -v xz >/dev/null 2>&1; then
            if ! XZ_OPT="--threads=0" tar "${tar_args[@]}"; then
                extraction_status=$?
            fi
        elif ! tar "${tar_args[@]}"; then
            extraction_status=$?
        fi
    elif ! tar "${tar_args[@]}"; then
        extraction_status=$?
    fi

    if (( extraction_status != 0 )); then
        rm -rf "${TOOLCHAIN_INSTALL_DIR}"
        print_error "Échec lors de l'extraction de la toolchain"
        exit 1
    fi

    if [[ ! -x "${toolchain_gcc}" ]]; then
        print_error "La toolchain téléchargée ne contient pas ${TOOLCHAIN_PREFIX}gcc. Vérifiez l'archive (${TOOLCHAIN_URL})."
        exit 1
    fi

    export PATH="${TOOLCHAIN_BIN_DIR}:${PATH}"

    print_info "Toolchain RISC-V installée localement dans ${TOOLCHAIN_INSTALL_DIR}"
}

ensure_toolchain() {
    local toolchain_cmd="${TOOLCHAIN_PREFIX}gcc"

    if command -v "${toolchain_cmd}" >/dev/null 2>&1; then
        return
    fi

    bootstrap_toolchain

    if ! command -v "${toolchain_cmd}" >/dev/null 2>&1; then
        print_error "${toolchain_cmd} reste introuvable malgré l'installation automatique."
        exit 1
    fi
}

require_command() {
    local cmd="$1"
    local message="$2"

    if ! command -v "${cmd}" >/dev/null 2>&1; then
        print_error "${message}"
        exit 1
    fi
}

file_mtime() {
    local path="$1"
    local mtime

    if mtime="$(stat -c %Y "${path}" 2>/dev/null)"; then
        printf '%s' "${mtime}"
        return 0
    fi

    if mtime="$(stat -f %m "${path}" 2>/dev/null)"; then
        printf '%s' "${mtime}"
        return 0
    fi

    return 1
}

if [[ -f "${LOGO_FILE}" ]]; then
    cat "${LOGO_FILE}"
    echo
fi

print_info "Vérification des dépendances..."

ensure_toolchain

declare -A REQUIRED_COMMANDS=(
    [git]="git est requis. Assurez-vous qu'il est installé."
    [make]="make est requis. Installez les outils de compilation (build-essential)."
    [stat]="stat est requis pour lire les horodatages (GNU coreutils ou BSD stat)."
    [sha256sum]="sha256sum est requis pour valider les binaires existants. Installez coreutils."
)
REQUIRED_COMMANDS["${TOOLCHAIN_PREFIX}gcc"]="la chaîne d'outils ${TOOLCHAIN_PREFIX}gcc est absente. Installez 'gcc-riscv32-unknown-elf', définissez CROSS_PREFIX ou laissez le script télécharger la toolchain officielle."

ordered_commands=(git make stat sha256sum "${TOOLCHAIN_PREFIX}gcc")
for cmd in "${ordered_commands[@]}"; do
    require_command "${cmd}" "${REQUIRED_COMMANDS[${cmd}]}"
    print_info "  • ${cmd} ✅"
done

configure_klipper_remote() {
    local repo="$1"
    local remote_url="$2"
    local fetch_refspec="$3"
    local local_refspec="$4"

    if ! git -C "${repo}" remote get-url origin >/dev/null 2>&1; then
        git -C "${repo}" remote add origin "${remote_url}"
    else
        git -C "${repo}" remote set-url origin "${remote_url}"
    fi

    git -C "${repo}" config --unset-all remote.origin.fetch >/dev/null 2>&1 || true
    if ! git -C "${repo}" config remote.origin.fetch "+${fetch_refspec}:${local_refspec}"; then
        print_error "Impossible de restreindre les références récupérées (${fetch_refspec})."
        exit 1
    fi
}

ensure_klipper_repo() {
    mkdir -p "${CACHE_ROOT}"

    if [[ "${USE_EXISTING_KLIPPER}" == "true" ]]; then
        local resolved="${KLIPPER_DIR/#\~/${HOME}}"

        if [[ "${resolved}" != /* ]]; then
            if ! resolved="$(cd "${PWD}" && cd "${resolved}" 2>/dev/null && pwd)"; then
                print_error "Le répertoire Klipper spécifié (${KLIPPER_DIR}) est introuvable. Vérifiez KLIPPER_SRC_DIR."
                exit 1
            fi
        else
            if ! resolved="$(cd "${resolved}" 2>/dev/null && pwd)"; then
                print_error "Le répertoire Klipper spécifié (${KLIPPER_DIR}) est introuvable."
                exit 1
            fi
        fi

        KLIPPER_DIR="${resolved}"
        print_info "Utilisation du dépôt Klipper existant : ${KLIPPER_DIR}"

        if [[ ! -d "${KLIPPER_DIR}/.git" ]]; then
            print_error "${KLIPPER_DIR} n'est pas un dépôt Git. Impossible d'appliquer automatiquement les correctifs."
            exit 1
        fi

        return
    fi

    if [[ -d "${KLIPPER_DIR}" && ! -d "${KLIPPER_DIR}/.git" ]]; then
        print_info "Répertoire ${KLIPPER_DIR} corrompu, nouvelle initialisation..."
        rm -rf "${KLIPPER_DIR}"
    fi

    if [[ ! -d "${KLIPPER_DIR}/.git" ]]; then
        print_info "Clonage du dépôt Klipper (${KLIPPER_REPO_URL})..."
        if ! git clone \
            --depth "${KLIPPER_CLONE_DEPTH}" \
            --branch "${KLIPPER_REF}" \
            --single-branch \
            "${KLIPPER_REPO_URL}" "${KLIPPER_DIR}"; then
            print_error "Échec du clonage de ${KLIPPER_REPO_URL}"
            exit 1
        fi
    fi

    print_info "Synchronisation du dépôt Klipper (${KLIPPER_REF})..."
    configure_klipper_remote "${KLIPPER_DIR}" "${KLIPPER_REPO_URL}" "${KLIPPER_FETCH_REFSPEC}" "${KLIPPER_LOCAL_TRACKING_REF}"

    if ! git -C "${KLIPPER_DIR}" reset --hard >/dev/null 2>&1; then
        print_error "Impossible de nettoyer l'état du dépôt Klipper."
        exit 1
    fi

    if ! git -C "${KLIPPER_DIR}" fetch --depth "${KLIPPER_CLONE_DEPTH}" --tags --prune origin; then
        print_error "Impossible de récupérer les mises à jour depuis origin"
        exit 1
    fi

    if [[ "${KLIPPER_FETCH_REFSPEC}" == refs/heads/* ]]; then
        if ! git -C "${KLIPPER_DIR}" checkout "${KLIPPER_REF}" >/dev/null 2>&1; then
            if ! git -C "${KLIPPER_DIR}" checkout -b "${KLIPPER_REF}" "origin/${KLIPPER_REF}" >/dev/null 2>&1; then
                print_error "Impossible de se positionner sur ${KLIPPER_REF}"
                exit 1
            fi
        fi
        if ! git -C "${KLIPPER_DIR}" reset --hard "origin/${KLIPPER_REF}"; then
            print_error "Impossible de mettre à jour ${KLIPPER_REF}"
            exit 1
        fi
    else
        if ! git -C "${KLIPPER_DIR}" checkout --force "${KLIPPER_REF}"; then
            print_error "Impossible de se positionner sur ${KLIPPER_REF}"
            exit 1
        fi
    fi
}

refresh_inputs_state() {
    if ! command -v python3 >/dev/null 2>&1; then
        print_error "python3 est requis pour calculer l'empreinte des fichiers de configuration."
        exit 1
    fi

    local inputs=("${SCRIPT_DIR}/klipper.config")
    if [[ -d "${OVERRIDES_DIR}" ]]; then
        inputs+=("${OVERRIDES_DIR}")
    fi

    local serialized_inputs
    serialized_inputs="$(printf '%s\n' "${inputs[@]}")"

    local state=()
    if ! mapfile -t state < <(FINGERPRINT_INPUTS="${serialized_inputs}" python3 - <<'PY'
import hashlib
import os
from pathlib import Path

inputs = [Path(p) for p in os.environ.get("FINGERPRINT_INPUTS", "").splitlines() if p]
files = []
for path in inputs:
    if not path.exists():
        continue
    if path.is_file():
        files.append(path)
    else:
        for child in sorted(path.rglob("*")):
            if child.is_file():
                files.append(child)

files.sort(key=lambda p: p.as_posix())
hasher = hashlib.sha256()
latest_mtime = 0

for file_path in files:
    file_id = file_path.as_posix().encode("utf-8")
    hasher.update(file_id)
    hasher.update(b"\0")
    with file_path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            hasher.update(chunk)
    mtime = int(file_path.stat().st_mtime)
    if mtime > latest_mtime:
        latest_mtime = mtime

print(hasher.hexdigest())
print(latest_mtime)
PY
); then
        print_error "Impossible de calculer l'empreinte des fichiers de configuration."
        exit 1
    fi

    if (( ${#state[@]} < 2 )); then
        print_error "État incomplet lors du calcul de l'empreinte de configuration."
        exit 1
    fi

    INPUT_FINGERPRINT="${state[0]}"
    INPUT_LATEST_MTIME="${state[1]}"
}

record_build_metadata() {
    local current_head="$1"
    local bin_sha="$2"
    local bin_mtime="$3"

    mkdir -p "${CACHE_ROOT}"
    cat > "${KLIPPER_METADATA_FILE}" <<EOF
KLIPPER_HEAD=${current_head}
CONFIG_FINGERPRINT=${INPUT_FINGERPRINT}
CONFIG_LATEST_MTIME=${INPUT_LATEST_MTIME}
BIN_SHA256=${bin_sha}
BIN_MTIME=${bin_mtime}
RECORDED_AT=$(date +%s)
EOF
}

maybe_reuse_existing_binary() {
    local existing_bin="${KLIPPER_DIR}/out/klipper.bin"
    local metadata_head=""
    local metadata_hash=""
    local metadata_sha=""
    local metadata_mtime=""

    if [[ ! -f "${existing_bin}" ]]; then
        return 1
    fi

    local bin_mtime
    if ! bin_mtime="$(file_mtime "${existing_bin}")"; then
        return 1
    fi

    local bin_sha
    if ! bin_sha="$(sha256sum "${existing_bin}" 2>/dev/null | awk '{print $1}')"; then
        return 1
    fi

    if (( bin_mtime < INPUT_LATEST_MTIME )); then
        return 1
    fi

    if [[ -f "${KLIPPER_METADATA_FILE}" ]]; then
        while IFS='=' read -r key value; do
            case "${key}" in
                KLIPPER_HEAD)
                    metadata_head="${value}"
                    ;;
                CONFIG_FINGERPRINT)
                    metadata_hash="${value}"
                    ;;
                BIN_SHA256)
                    metadata_sha="${value}"
                    ;;
                BIN_MTIME)
                    metadata_mtime="${value}"
                    ;;
            esac
        done < "${KLIPPER_METADATA_FILE}"
    fi

    local current_head
    if ! current_head="$(git -C "${KLIPPER_DIR}" rev-parse HEAD 2>/dev/null)"; then
        return 1
    fi

    if [[ "${metadata_head}" != "${current_head}" ]]; then
        return 1
    fi

    if [[ "${metadata_hash}" != "${INPUT_FINGERPRINT}" ]]; then
        return 1
    fi

    if [[ "${metadata_sha}" != "${bin_sha}" ]]; then
        return 1
    fi

    if [[ -n "${metadata_mtime}" ]] && (( bin_mtime < metadata_mtime )); then
        return 1
    fi

    if [[ ! -t 0 ]]; then
        print_info "Binaire existant détecté mais environnement non interactif : recompilation forcée."
        return 1
    fi

    print_info "Un binaire Klipper existant semble à jour (HEAD ${current_head:0:12}, SHA256 ${bin_sha:0:12})."
    read -r -p "Souhaitez-vous le réutiliser ? [o/N] " reuse_choice
    case "${reuse_choice}" in
        [oOyY])
            record_build_metadata "${current_head}" "${bin_sha}" "${bin_mtime}"
            print_success "Réutilisation de ${existing_bin}."
            return 0
            ;;
        *)
            print_info "Recompilation demandée."
            ;;
    esac

    return 1
}

ensure_klipper_repo

if [[ "${USE_EXISTING_KLIPPER}" == "true" && -f "${KLIPPER_DIR}/.config" ]]; then
    if [[ ! -f "${KLIPPER_DIR}/.config.bmcuc_backup" ]]; then
        print_info "Sauvegarde de la configuration existante (${KLIPPER_DIR}/.config.bmcuc_backup)..."
        cp "${KLIPPER_DIR}/.config" "${KLIPPER_DIR}/.config.bmcuc_backup"
    else
        print_info "Configuration existante déjà sauvegardée (${KLIPPER_DIR}/.config.bmcuc_backup)."
    fi
fi

print_info "Copie de la configuration Klipper..."
cp "${SCRIPT_DIR}/klipper.config" "${KLIPPER_DIR}/.config"

update_cross_prefix() {
    local config_file="${KLIPPER_DIR}/.config"
    local normalized_prefix="${TOOLCHAIN_PREFIX}"

    if [[ -z "${normalized_prefix}" ]]; then
        return
    fi

    if [[ "${normalized_prefix}" != *- ]]; then
        normalized_prefix="${normalized_prefix}-"
    fi

    TOOLCHAIN_PREFIX="${normalized_prefix}"

    if command -v python3 >/dev/null 2>&1; then
        CONFIG_PATH="${config_file}" \
        CONFIG_PREFIX="${normalized_prefix}" \
        python3 - <<'PY'
import os
from pathlib import Path

config_path = Path(os.environ["CONFIG_PATH"])
prefix = os.environ["CONFIG_PREFIX"]

lines = config_path.read_text(encoding="utf-8").splitlines()
updated = []
found = False

for line in lines:
    if line.startswith("CONFIG_CROSS_PREFIX="):
        if line != f'CONFIG_CROSS_PREFIX="{prefix}"':
            found = True
        updated.append(f'CONFIG_CROSS_PREFIX="{prefix}"')
    else:
        updated.append(line)

if not any(l.startswith("CONFIG_CROSS_PREFIX=") for l in updated):
    updated.append(f'CONFIG_CROSS_PREFIX="{prefix}"')
    found = True

if found:
    config_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY
    else
        print_error "python3 est requis pour ajuster CONFIG_CROSS_PREFIX. Veuillez l'installer ou mettre à jour ${config_file} manuellement."
        exit 1
    fi
}

update_cross_prefix

apply_patch() {
    local patch_file="$1"

    if [[ ! -f "${patch_file}" ]]; then
        return
    fi

    local patch_name
    patch_name="$(basename "${patch_file}")"

    if git -C "${KLIPPER_DIR}" apply --reverse --check "${patch_file}" >/dev/null 2>&1; then
        print_info "Patch ${patch_name} déjà appliqué, passage."
        return
    fi

    print_info "Application du patch ${patch_name}..."
    if ! git -C "${KLIPPER_DIR}" apply "${patch_file}"; then
        print_error "Échec lors de l'application de ${patch_name}"
        exit 1
    fi
}

copy_tree() {
    local src="$1"
    local dest="$2"

    if [[ -d "${src}" ]]; then
        print_info "Synchronisation de $(basename "${src}")..."
        mkdir -p "${dest}"
        cp -a "${src}"/. "${dest}/"
    fi
}

apply_patch "${OVERRIDES_DIR}/Makefile.patch"
apply_patch "${OVERRIDES_DIR}/src/Kconfig.patch"
copy_tree "${OVERRIDES_DIR}/src/ch32v20x" "${KLIPPER_DIR}/src/ch32v20x"
copy_tree "${OVERRIDES_DIR}/src/generic" "${KLIPPER_DIR}/src/generic"
copy_tree "${OVERRIDES_DIR}/config/boards" "${KLIPPER_DIR}/config/boards"

refresh_inputs_state

if maybe_reuse_existing_binary; then
    exit 0
fi

print_info "Compilation du firmware Klipper..."
cd "${KLIPPER_DIR}"
make clean
make CROSS_PREFIX="${TOOLCHAIN_PREFIX}"

BIN_PATH="${KLIPPER_DIR}/out/klipper.bin"
if [[ ! -f "${BIN_PATH}" ]]; then
    print_error "La compilation s'est terminée sans générer ${BIN_PATH}."
    exit 1
fi

if ! CURRENT_HEAD="$(git -C "${KLIPPER_DIR}" rev-parse HEAD 2>/dev/null)"; then
    CURRENT_HEAD="inconnu"
fi

BIN_SHA="$(sha256sum "${BIN_PATH}" | awk '{print $1}')"
if ! BIN_MTIME="$(file_mtime "${BIN_PATH}")"; then
    print_error "Impossible de déterminer l'horodatage de ${BIN_PATH}."
    exit 1
fi
record_build_metadata "${CURRENT_HEAD}" "${BIN_SHA}" "${BIN_MTIME}"

print_success "Compilation terminée. Le firmware se trouve dans ${BIN_PATH} (SHA256 ${BIN_SHA:0:12})."

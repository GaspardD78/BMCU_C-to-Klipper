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
PYTHON_CACHE_DIR="${CACHE_ROOT}/python"
PYTHON_DEPS_DIR="${PYTHON_CACHE_DIR}/site-packages"
REQUIREMENTS_FILE="${FLASH_ROOT}/requirements.txt"
REQUIREMENTS_HASH_FILE="${PYTHON_CACHE_DIR}/requirements.sha256"
FORCE_DEP_INSTALL="false"
REFRESH_CLONE="false"
PYTHON_CACHE_STATUS="not_checked"
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
TOOLCHAIN_BIN_DIR="${TOOLCHAIN_INSTALL_DIR}/bin"
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

LOG_DIR="${FLASH_ROOT}/logs"
STATE_FILE="${LOG_DIR}/state.json"
BUILD_LOG_BASENAME="build"
declare -a STEP_SEQUENCE=("dependencies" "repo_sync" "overrides" "compile" "finalize")
declare -A STEP_INDEX=(
    [dependencies]=0
    [repo_sync]=1
    [overrides]=2
    [compile]=3
    [finalize]=4
)
STATE_BINARY_INFO_JSON=""
CURRENT_STEP=""
RESUME_FROM_STEP=""
SIGNAL_CAUGHT=""
SHOULD_RESTORE_REPO="false"
FINAL_BIN_PATH=""
FINAL_BIN_SHA=""
FINAL_BIN_HEAD=""
FINAL_BIN_REUSED="false"
REUSED_BIN_SHA=""
REUSED_BIN_MTIME=""
REUSED_BIN_HEAD=""
REUSED_BIN_PATH=""
CLEANUP_DONE="false"
PREV_STEP=""
PREV_STATUS=""
PREV_UPDATED=""
PREV_BIN_PATH=""
PREV_BIN_SHA=""
PREV_BIN_HEAD=""
PREV_BIN_REUSED=""

KLIPPER_METADATA_FILE="${CACHE_ROOT}/klipper.bin.meta"
FIRMWARE_ARCHIVE_DIR="${CACHE_ROOT}/firmware"
FIRMWARE_ARCHIVE_PATH="${FIRMWARE_ARCHIVE_DIR}/klipper.bin"
ARCHIVED_FIRMWARE_STORED="false"
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

usage() {
    cat <<'EOF'
Usage: ./build.sh [options]

Options :
  --refresh        Force la suppression du cache Klipper et reclone le dépôt.
  --force          Réinstalle les dépendances Python même si le cache est à jour.
  -h, --help       Affiche cette aide et quitte.
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --refresh)
                REFRESH_CLONE="true"
                ;;
            --force)
                FORCE_DEP_INSTALL="true"
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            --)
                shift
                break
                ;;
            -*)
                print_error "Option inconnue : $1"
                usage
                exit 1
                ;;
            *)
                print_error "Argument non pris en charge : $1"
                usage
                exit 1
                ;;
        esac
        shift
    done

    if [[ $# -gt 0 ]]; then
        print_error "Arguments supplémentaires non pris en charge : $*"
        usage
        exit 1
    fi
}

ensure_logs_dir() {
    mkdir -p "${LOG_DIR}"
}

step_label() {
    local step="$1"
    case "${step}" in
        dependencies)
            printf '%s' "Vérification des dépendances"
            ;;
        repo_sync)
            printf '%s' "Préparation du dépôt Klipper"
            ;;
        overrides)
            printf '%s' "Application des correctifs"
            ;;
        compile)
            printf '%s' "Compilation du firmware"
            ;;
        finalize)
            printf '%s' "Nettoyage final"
            ;;
        *)
            printf '%s' "${step}"
            ;;
    esac
}

next_step() {
    local step="$1"
    case "${step}" in
        dependencies)
            printf '%s' "repo_sync"
            ;;
        repo_sync)
            printf '%s' "overrides"
            ;;
        overrides)
            printf '%s' "compile"
            ;;
        compile)
            printf '%s' "finalize"
            ;;
        finalize)
            printf '%s' "completed"
            ;;
        *)
            printf '%s' "completed"
            ;;
    esac
}

update_state_binary_info() {
    local path="$1"
    local sha="$2"
    local head="$3"
    local reused="$4"

    STATE_BINARY_INFO_JSON="$(STATE_BIN_PATH="${path}" STATE_BIN_SHA="${sha}" STATE_BIN_HEAD="${head}" STATE_BIN_REUSED="${reused}" python3 - <<'PY'
import json
import os

path = os.environ.get("STATE_BIN_PATH")
sha = os.environ.get("STATE_BIN_SHA")
head = os.environ.get("STATE_BIN_HEAD")
reused = os.environ.get("STATE_BIN_REUSED")

data = {}
if path:
    data["binary_path"] = path
if sha:
    data["binary_sha256"] = sha
if head:
    data["klipper_head"] = head
if reused:
    data["reused"] = reused.lower() == "true"

if data:
    print(json.dumps(data, ensure_ascii=False))
else:
    print("")
PY
)"
}

clear_state_binary_info() {
    STATE_BINARY_INFO_JSON=""
}

write_state() {
    local step="$1"
    local status="$2"
    local timestamp

    timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    ensure_logs_dir

    STATE_EXTRA_JSON="${STATE_BINARY_INFO_JSON}" python3 - "$STATE_FILE" "$step" "$status" "$timestamp" <<'PY'
import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
step = sys.argv[2]
status = sys.argv[3]
timestamp = sys.argv[4]
extra_raw = os.environ.get("STATE_EXTRA_JSON", "")

data = {
    "step": step,
    "status": status,
    "updated_at": timestamp,
}

if extra_raw:
    try:
        extra = json.loads(extra_raw)
    except json.JSONDecodeError:
        extra = {}
    if isinstance(extra, dict):
        data.update(extra)

tmp_path = path.with_suffix(path.suffix + ".tmp")
path.parent.mkdir(parents=True, exist_ok=True)

with tmp_path.open("w", encoding="utf-8") as handle:
    json.dump(data, handle, ensure_ascii=False, indent=2)
    handle.write("\n")

tmp_path.replace(path)
PY
}

read_state() {
    if [[ ! -f "${STATE_FILE}" ]]; then
        return 1
    fi

    mapfile -t __STATE_DATA < <(python3 - "$STATE_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    data = {}

print(data.get("step", ""))
print(data.get("status", ""))
print(data.get("updated_at", ""))
print(data.get("binary_path", ""))
print(data.get("binary_sha256", ""))
print(data.get("klipper_head", ""))
print(str(data.get("reused", "")))
PY
    )

    PREV_STEP="${__STATE_DATA[0]}"
    PREV_STATUS="${__STATE_DATA[1]}"
    PREV_UPDATED="${__STATE_DATA[2]}"
    PREV_BIN_PATH="${__STATE_DATA[3]}"
    PREV_BIN_SHA="${__STATE_DATA[4]}"
    PREV_BIN_HEAD="${__STATE_DATA[5]}"
    PREV_BIN_REUSED="${__STATE_DATA[6]}"

    return 0
}

should_skip_step() {
    local step="$1"

    if [[ -z "${RESUME_FROM_STEP}" ]]; then
        return 1
    fi

    if [[ "${step}" == "dependencies" ]]; then
        return 1
    fi

    local resume_index="${STEP_INDEX[${RESUME_FROM_STEP}]:--1}"
    local step_index="${STEP_INDEX[${step}]:--1}"

    if (( step_index < resume_index )); then
        return 0
    fi

    return 1
}

mark_step_skipped() {
    local step="$1"
    local label

    label="$(step_label "${step}")"
    print_info "Étape ${label} déjà réalisée, saut."

    local step_index="${STEP_INDEX[${step}]:--1}"
    local overrides_index="${STEP_INDEX[overrides]:-2}"
    if (( step_index >= overrides_index )); then
        SHOULD_RESTORE_REPO="true"
    fi

    local next
    next="$(next_step "${step}")"
    if [[ "${next}" == "completed" ]]; then
        clear_state_binary_info
        write_state "completed" "success"
    else
        write_state "${next}" "pending"
    fi
}

start_step() {
    local step="$1"

    if [[ -n "${RESUME_FROM_STEP}" ]] && [[ "${RESUME_FROM_STEP}" != "${step}" ]]; then
        if should_skip_step "${step}"; then
            mark_step_skipped "${step}"
            return 1
        fi
    fi

    local label
    label="$(step_label "${step}")"
    print_info "➜ ${label}"
    CURRENT_STEP="${step}"
    write_state "${step}" "running"
    return 0
}

finish_step() {
    local step="$1"
    local next

    if [[ "${CURRENT_STEP}" == "${step}" ]]; then
        CURRENT_STEP=""
    fi

    next="$(next_step "${step}")"
    if [[ "${next}" == "completed" ]]; then
        clear_state_binary_info
        write_state "completed" "success"
    else
        write_state "${next}" "pending"
    fi
}

initialize_state() {
    ensure_logs_dir

    PREV_STEP=""
    PREV_STATUS=""
    PREV_UPDATED=""
    PREV_BIN_PATH=""
    PREV_BIN_SHA=""
    PREV_BIN_HEAD=""
    PREV_BIN_REUSED=""

    local resume_choice="yes"

    if read_state; then
        local lower_status="${PREV_STATUS,,}"
        if [[ "${PREV_STEP}" == "completed" && "${lower_status}" == "success" ]]; then
            RESUME_FROM_STEP="${STEP_SEQUENCE[0]}"
            clear_state_binary_info
            SHOULD_RESTORE_REPO="false"
            write_state "${RESUME_FROM_STEP}" "pending"
            return
        fi

        if [[ -n "${PREV_STEP}" ]]; then
            local label="$(step_label "${PREV_STEP}")"
            local message="Une exécution précédente a été arrêtée à l'étape \"${label}\" (statut ${PREV_STATUS:-inconnu})."
            print_info "${message}"

            if [[ -t 0 ]]; then
                read -r -p "Souhaitez-vous reprendre cette étape ? [O/n] " resume_prompt || resume_prompt=""
                case "${resume_prompt}" in
                    [nN]*)
                        resume_choice="no"
                        ;;
                esac
            fi

            if [[ "${resume_choice}" == "yes" ]]; then
                RESUME_FROM_STEP="${PREV_STEP}"
                local reused_flag="false"
                if [[ "${PREV_BIN_REUSED,,}" == "true" ]]; then
                    reused_flag="true"
                fi
                if [[ -n "${PREV_BIN_PATH}" ]]; then
                    FINAL_BIN_PATH="${PREV_BIN_PATH}"
                    FINAL_BIN_SHA="${PREV_BIN_SHA}"
                    FINAL_BIN_HEAD="${PREV_BIN_HEAD}"
                    FINAL_BIN_REUSED="${reused_flag}"
                    update_state_binary_info "${FINAL_BIN_PATH}" "${FINAL_BIN_SHA}" "${FINAL_BIN_HEAD}" "${FINAL_BIN_REUSED}"
                fi
                local resume_index="${STEP_INDEX[${RESUME_FROM_STEP}]:--1}"
                local overrides_index="${STEP_INDEX[overrides]:-2}"
                if (( resume_index >= overrides_index )); then
                    SHOULD_RESTORE_REPO="true"
                fi
                write_state "${RESUME_FROM_STEP}" "pending"
                return
            fi
        fi
    fi

    RESUME_FROM_STEP="${STEP_SEQUENCE[0]}"
    clear_state_binary_info
    SHOULD_RESTORE_REPO="false"
    write_state "${RESUME_FROM_STEP}" "pending"
}

log_build_sha() {
    local bin_path="$1"
    local bin_sha="$2"
    local head="$3"
    local reused="$4"

    ensure_logs_dir

    local timestamp
    timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    local base_name
    base_name="${LOG_DIR}/${BUILD_LOG_BASENAME}-$(date +%Y%m%d-%H%M%S)"
    local log_file="${base_name}.log"
    local suffix=1

    while [[ -e "${log_file}" ]]; do
        log_file="${base_name}-${suffix}.log"
        ((suffix++))
    done

    {
        printf 'timestamp=%s\n' "${timestamp}"
        printf 'klipper_head=%s\n' "${head}"
        printf 'binary_path=%s\n' "${bin_path}"
        printf 'sha256=%s\n' "${bin_sha}"
        printf 'reused=%s\n' "${reused}"
    } >"${log_file}"

    print_info "Empreinte SHA256 enregistrée dans ${log_file}"
}

preserve_final_binary() {
    local reason="$1"
    local update_final_path="${2:-false}"

    if [[ "${ARCHIVED_FIRMWARE_STORED}" == "true" && "${update_final_path}" != "true" ]]; then
        return 0
    fi

    local source_path="${FINAL_BIN_PATH:-}"
    if [[ -z "${source_path}" || ! -f "${source_path}" ]]; then
        source_path="${KLIPPER_DIR}/out/klipper.bin"
        if [[ ! -f "${source_path}" ]]; then
            return 0
        fi
    fi

    if [[ "${source_path}" == "${FIRMWARE_ARCHIVE_PATH}" ]]; then
        ARCHIVED_FIRMWARE_STORED="true"
        if [[ "${update_final_path}" == "true" ]]; then
            FINAL_BIN_PATH="${FIRMWARE_ARCHIVE_PATH}"
            if [[ -z "${FINAL_BIN_SHA:-}" ]]; then
                FINAL_BIN_SHA="$(sha256sum "${FINAL_BIN_PATH}" | awk '{print $1}')"
            fi
            update_state_binary_info "${FINAL_BIN_PATH}" "${FINAL_BIN_SHA}" "${FINAL_BIN_HEAD}" "${FINAL_BIN_REUSED}"
        fi
        return 0
    fi

    mkdir -p "${FIRMWARE_ARCHIVE_DIR}"
    if cp -f "${source_path}" "${FIRMWARE_ARCHIVE_PATH}"; then
        ARCHIVED_FIRMWARE_STORED="true"
        if [[ -n "${reason}" ]]; then
            print_info "Firmware sauvegardé dans ${FIRMWARE_ARCHIVE_PATH} (${reason})."
        else
            print_info "Firmware sauvegardé dans ${FIRMWARE_ARCHIVE_PATH}."
        fi

        if [[ "${update_final_path}" == "true" ]]; then
            FINAL_BIN_PATH="${FIRMWARE_ARCHIVE_PATH}"
            if [[ -z "${FINAL_BIN_SHA:-}" ]]; then
                FINAL_BIN_SHA="$(sha256sum "${FINAL_BIN_PATH}" | awk '{print $1}')"
            fi
            update_state_binary_info "${FINAL_BIN_PATH}" "${FINAL_BIN_SHA}" "${FINAL_BIN_HEAD}" "${FINAL_BIN_REUSED}"
        fi
    else
        print_error "Impossible de sauvegarder ${source_path} vers ${FIRMWARE_ARCHIVE_PATH}."
        return 1
    fi

    return 0
}

restore_repo_if_dirty() {
    if [[ "${CLEANUP_DONE}" == "true" ]]; then
        return 0
    fi

    if [[ "${SHOULD_RESTORE_REPO}" != "true" ]]; then
        return 0
    fi

    if [[ ! -d "${KLIPPER_DIR}/.git" ]]; then
        CLEANUP_DONE="true"
        return 0
    fi

    local allow_reclone="true"
    if [[ "${USE_EXISTING_KLIPPER}" == "true" ]]; then
        allow_reclone="false"
    fi

    local status_output
    if ! status_output="$(git -C "${KLIPPER_DIR}" status --porcelain 2>/dev/null)"; then
        print_error "Impossible de vérifier l'état du dépôt Klipper (${KLIPPER_DIR})."
        return 1
    fi

    if [[ -z "${status_output}" ]]; then
        CLEANUP_DONE="true"
        return 0
    fi

    print_info "Nettoyage de l'arbre de travail Klipper..."

    if git -C "${KLIPPER_DIR}" restore --source=HEAD --staged --worktree . >/dev/null 2>&1; then
        if [[ -z "$(git -C "${KLIPPER_DIR}" status --porcelain 2>/dev/null)" ]]; then
            print_success "Dépôt Klipper restauré dans un état propre."
            CLEANUP_DONE="true"
            return 0
        fi
        print_info "Le dépôt reste modifié après restauration, reclonage nécessaire."
    else
        print_info "La restauration Git a échoué, reclonage nécessaire."
    fi

    if [[ "${allow_reclone}" == "true" ]]; then
        preserve_final_binary "reclone du dépôt" "true" || true
        print_info "Suppression du dépôt Klipper local (${KLIPPER_DIR})."
        rm -rf "${KLIPPER_DIR}"
        CLEANUP_DONE="true"
        return 0
    fi

    print_error "Le dépôt Klipper fourni (${KLIPPER_DIR}) reste modifié. Merci de le nettoyer manuellement."
    return 1
}

handle_signal() {
    local signal_name="$1"
    SIGNAL_CAUGHT="${signal_name}"
    print_error "Signal ${signal_name} reçu, interruption en cours..."

    if [[ -n "${CURRENT_STEP}" ]]; then
        write_state "${CURRENT_STEP}" "interrupted"
    else
        write_state "${RESUME_FROM_STEP:-${STEP_SEQUENCE[0]}}" "interrupted"
    fi

    restore_repo_if_dirty || true
    exit 128
}

handle_exit() {
    local exit_code=$?

    if [[ -n "${SIGNAL_CAUGHT}" ]]; then
        return
    fi

    if (( exit_code != 0 )); then
        if [[ -n "${CURRENT_STEP}" ]]; then
            write_state "${CURRENT_STEP}" "failed"
        fi
    fi

    restore_repo_if_dirty || true
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

ensure_python_requirements() {
    if [[ ! -f "${REQUIREMENTS_FILE}" ]]; then
        PYTHON_CACHE_STATUS="absent"
        return
    fi

    if ! python3 -m pip --version >/dev/null 2>&1; then
        print_error "pip pour python3 est requis pour installer les dépendances (${REQUIREMENTS_FILE})."
        exit 1
    fi

    mkdir -p "${PYTHON_CACHE_DIR}"

    local current_hash
    current_hash="$(sha256sum "${REQUIREMENTS_FILE}" | awk '{print $1}')"

    local previous_hash=""
    if [[ -f "${REQUIREMENTS_HASH_FILE}" ]]; then
        read -r previous_hash < "${REQUIREMENTS_HASH_FILE}"
    fi

    local install_needed="false"
    if [[ "${FORCE_DEP_INSTALL}" == "true" ]]; then
        install_needed="true"
        print_info "Installation des dépendances Python forcée (--force)."
    elif [[ ! -d "${PYTHON_DEPS_DIR}" || -z "$(ls -A "${PYTHON_DEPS_DIR}" 2>/dev/null)" ]]; then
        install_needed="true"
        print_info "Initialisation du cache de dépendances Python (${PYTHON_DEPS_DIR})."
    elif [[ "${current_hash}" != "${previous_hash}" ]]; then
        install_needed="true"
        print_info "requirements.txt a été modifié depuis la dernière installation. Mise à jour des dépendances..."
    fi

    if [[ "${install_needed}" == "true" ]]; then
        rm -rf "${PYTHON_DEPS_DIR}"
        mkdir -p "${PYTHON_DEPS_DIR}"

        if ! python3 -m pip install --upgrade --target "${PYTHON_DEPS_DIR}" -r "${REQUIREMENTS_FILE}"; then
            print_error "Échec de l'installation des dépendances Python (${REQUIREMENTS_FILE})."
            exit 1
        fi

        printf '%s\n' "${current_hash}" > "${REQUIREMENTS_HASH_FILE}"
        PYTHON_CACHE_STATUS="updated"
    else
        PYTHON_CACHE_STATUS="reused"
        print_info "Réutilisation du cache de dépendances Python (${PYTHON_DEPS_DIR})."
    fi

    if [[ -z "${PYTHONPATH:-}" ]]; then
        export PYTHONPATH="${PYTHON_DEPS_DIR}"
    else
        case ":${PYTHONPATH}:" in
            *:"${PYTHON_DEPS_DIR}":*) ;;
            *) export PYTHONPATH="${PYTHON_DEPS_DIR}:${PYTHONPATH}" ;;
        esac
    fi
}

report_python_cache_status() {
    case "${PYTHON_CACHE_STATUS}" in
        updated)
            print_success "Cache Python régénéré (${PYTHON_DEPS_DIR})."
            ;;
        reused)
            print_success "Cache Python réutilisé (${PYTHON_DEPS_DIR})."
            ;;
        absent)
            print_info "Aucun requirements.txt détecté, aucune dépendance Python n'a été installée."
            ;;
        not_checked)
            print_info "Cache Python non vérifié pendant cette exécution."
            ;;
        *)
            print_info "Statut du cache Python : ${PYTHON_CACHE_STATUS}."
            ;;
    esac
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

reset_cached_klipper_repo() {
    if [[ "${USE_EXISTING_KLIPPER}" == "true" ]]; then
        return
    fi

    local repo="${DEFAULT_KLIPPER_DIR}"

    if [[ ! -d "${repo}/.git" ]]; then
        return
    fi

    print_info "Réinitialisation du dépôt Klipper mis en cache (${repo})..."

    if ! git -C "${repo}" reset --hard HEAD; then
        print_error "Impossible d'annuler les modifications locales dans ${repo}."
        exit 1
    fi

    if ! git -C "${repo}" clean -fd; then
        print_error "Impossible de supprimer les fichiers non suivis dans ${repo}."
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

        if [[ "${REFRESH_CLONE}" == "true" ]]; then
            print_info "Option --refresh ignorée : KLIPPER_SRC_DIR pointe vers un dépôt externe."
        fi

        if [[ ! -d "${KLIPPER_DIR}/.git" ]]; then
            print_error "${KLIPPER_DIR} n'est pas un dépôt Git. Impossible d'appliquer automatiquement les correctifs."
            exit 1
        fi

        return
    fi

    if [[ "${REFRESH_CLONE}" == "true" && -d "${KLIPPER_DIR}" ]]; then
        print_info "Option --refresh détectée : suppression du cache Klipper (${KLIPPER_DIR})."
        rm -rf "${KLIPPER_DIR}"
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

    print_info "Mise à jour du dépôt Klipper mis en cache (${KLIPPER_DIR}) via git fetch --all && git reset --hard."
    configure_klipper_remote "${KLIPPER_DIR}" "${KLIPPER_REPO_URL}" "${KLIPPER_FETCH_REFSPEC}" "${KLIPPER_LOCAL_TRACKING_REF}"

    if ! git -C "${KLIPPER_DIR}" fetch --all --tags --prune; then
        print_error "Impossible de récupérer les mises à jour depuis origin"
        exit 1
    fi

    if [[ "${KLIPPER_FETCH_REFSPEC}" == refs/heads/* ]]; then
        local branch="${KLIPPER_FETCH_REFSPEC#refs/heads/}"
        if ! git -C "${KLIPPER_DIR}" checkout --force "${branch}" >/dev/null 2>&1; then
            if ! git -C "${KLIPPER_DIR}" checkout -B "${branch}" "origin/${branch}" >/dev/null 2>&1; then
                print_error "Impossible de se positionner sur ${branch}"
                exit 1
            fi
        fi
        if ! git -C "${KLIPPER_DIR}" reset --hard "origin/${branch}"; then
            print_error "Impossible de mettre à jour ${branch}"
            exit 1
        fi
    else
        if ! git -C "${KLIPPER_DIR}" checkout --force "${KLIPPER_REF}"; then
            print_error "Impossible de se positionner sur ${KLIPPER_REF}"
            exit 1
        fi
        if ! git -C "${KLIPPER_DIR}" reset --hard "${KLIPPER_REF}"; then
            print_error "Impossible de mettre à jour ${KLIPPER_REF}"
            exit 1
        fi
    fi

    if ! git -C "${KLIPPER_DIR}" clean -fd; then
        print_error "Impossible de supprimer les fichiers non suivis dans ${KLIPPER_DIR}."
        exit 1
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
            REUSED_BIN_SHA="${bin_sha}"
            REUSED_BIN_MTIME="${bin_mtime}"
            REUSED_BIN_HEAD="${current_head}"
            REUSED_BIN_PATH="${existing_bin}"
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

load_metadata_binary_info() {
    local meta_head=""
    local meta_sha=""

    if [[ -f "${KLIPPER_METADATA_FILE}" ]]; then
        while IFS='=' read -r key value; do
            case "${key}" in
                KLIPPER_HEAD)
                    meta_head="${value}"
                    ;;
                BIN_SHA256)
                    meta_sha="${value}"
                    ;;
            esac
        done < "${KLIPPER_METADATA_FILE}"
    fi

    if [[ -z "${FINAL_BIN_PATH}" ]]; then
        FINAL_BIN_PATH="${KLIPPER_DIR}/out/klipper.bin"
    fi

    if [[ -z "${FINAL_BIN_HEAD}" && -n "${meta_head}" ]]; then
        FINAL_BIN_HEAD="${meta_head}"
    fi

    if [[ -z "${FINAL_BIN_SHA}" && -n "${meta_sha}" ]]; then
        FINAL_BIN_SHA="${meta_sha}"
    fi

    if [[ -n "${FINAL_BIN_SHA}" ]]; then
        update_state_binary_info "${FINAL_BIN_PATH}" "${FINAL_BIN_SHA}" "${FINAL_BIN_HEAD}" "${FINAL_BIN_REUSED}"
    fi
}

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

parse_args "$@"

if [[ -f "${LOGO_FILE}" ]]; then
    cat "${LOGO_FILE}"
    echo
fi

if ! command -v python3 >/dev/null 2>&1; then
    print_error "python3 est requis pour exécuter ce script (gestion d'état et calculs SHA256)."
    exit 1
fi

initialize_state

trap 'handle_signal SIGINT' INT
trap 'handle_signal SIGTERM' TERM
trap 'handle_exit' EXIT

if start_step "dependencies"; then
    print_info "Vérification des dépendances..."
    ensure_toolchain

    declare -A REQUIRED_COMMANDS=(
        [git]="git est requis. Assurez-vous qu'il est installé."
        [make]="make est requis. Installez les outils de compilation (build-essential)."
        [stat]="stat est requis pour lire les horodatages (GNU coreutils ou BSD stat)."
        [sha256sum]="sha256sum est requis pour valider les binaires existants. Installez coreutils."
        [python3]="python3 est requis pour les empreintes et la gestion d'état. Installez-le puis relancez."
    )
    REQUIRED_COMMANDS["${TOOLCHAIN_PREFIX}gcc"]="la chaîne d'outils ${TOOLCHAIN_PREFIX}gcc est absente. Installez 'gcc-riscv32-unknown-elf', définissez CROSS_PREFIX ou laissez le script télécharger la toolchain officielle."

    ordered_commands=(git make stat sha256sum python3 "${TOOLCHAIN_PREFIX}gcc")
    for cmd in "${ordered_commands[@]}"; do
        require_command "${cmd}" "${REQUIRED_COMMANDS[${cmd}]}"
        print_info "  • ${cmd} ✅"
    done

    ensure_python_requirements

    finish_step "dependencies"
fi

if start_step "repo_sync"; then
    ensure_klipper_repo
    finish_step "repo_sync"
fi

if start_step "overrides"; then
    reset_cached_klipper_repo

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
    update_cross_prefix

    apply_patch "${OVERRIDES_DIR}/Makefile.patch"
    apply_patch "${OVERRIDES_DIR}/src/Kconfig.patch"
    copy_tree "${OVERRIDES_DIR}/src/ch32v20x" "${KLIPPER_DIR}/src/ch32v20x"
    copy_tree "${OVERRIDES_DIR}/src/generic" "${KLIPPER_DIR}/src/generic"
    copy_tree "${OVERRIDES_DIR}/config/boards" "${KLIPPER_DIR}/config/boards"

    refresh_inputs_state
    SHOULD_RESTORE_REPO="true"

    finish_step "overrides"
fi

if start_step "compile"; then
    bin_mtime=""

    FINAL_BIN_PATH=""
    FINAL_BIN_SHA=""
    FINAL_BIN_HEAD=""
    FINAL_BIN_REUSED="false"

    refresh_inputs_state

    if maybe_reuse_existing_binary; then
        FINAL_BIN_PATH="${REUSED_BIN_PATH}"
        FINAL_BIN_SHA="${REUSED_BIN_SHA}"
        FINAL_BIN_HEAD="${REUSED_BIN_HEAD}"
        FINAL_BIN_REUSED="true"
        update_state_binary_info "${FINAL_BIN_PATH}" "${FINAL_BIN_SHA}" "${FINAL_BIN_HEAD}" "${FINAL_BIN_REUSED}"
    else
        print_info "Compilation du firmware Klipper..."
        (
            cd "${KLIPPER_DIR}" && \
                make clean && \
                make CROSS_PREFIX="${TOOLCHAIN_PREFIX}"
        )

        FINAL_BIN_PATH="${KLIPPER_DIR}/out/klipper.bin"
        if [[ ! -f "${FINAL_BIN_PATH}" ]]; then
            print_error "La compilation s'est terminée sans générer ${FINAL_BIN_PATH}."
            exit 1
        fi

        if ! FINAL_BIN_HEAD="$(git -C "${KLIPPER_DIR}" rev-parse HEAD 2>/dev/null)"; then
            FINAL_BIN_HEAD="inconnu"
        fi

        FINAL_BIN_SHA="$(sha256sum "${FINAL_BIN_PATH}" | awk '{print $1}')"
        if ! bin_mtime="$(file_mtime "${FINAL_BIN_PATH}")"; then
            print_error "Impossible de déterminer l'horodatage de ${FINAL_BIN_PATH}."
            exit 1
        fi

        record_build_metadata "${FINAL_BIN_HEAD}" "${FINAL_BIN_SHA}" "${bin_mtime}"
        FINAL_BIN_REUSED="false"
        update_state_binary_info "${FINAL_BIN_PATH}" "${FINAL_BIN_SHA}" "${FINAL_BIN_HEAD}" "${FINAL_BIN_REUSED}"

        print_success "Compilation terminée. Le firmware se trouve dans ${FINAL_BIN_PATH} (SHA256 ${FINAL_BIN_SHA:0:12})."
    fi

    finish_step "compile"
fi

if start_step "finalize"; then
    if [[ -z "${FINAL_BIN_PATH}" && -n "${PREV_BIN_PATH}" ]]; then
        FINAL_BIN_PATH="${PREV_BIN_PATH}"
    fi
    if [[ -z "${FINAL_BIN_SHA}" && -n "${PREV_BIN_SHA}" ]]; then
        FINAL_BIN_SHA="${PREV_BIN_SHA}"
    fi
    if [[ -z "${FINAL_BIN_HEAD}" && -n "${PREV_BIN_HEAD}" ]]; then
        FINAL_BIN_HEAD="${PREV_BIN_HEAD}"
    fi

    if [[ -z "${FINAL_BIN_SHA}" ]]; then
        load_metadata_binary_info
    else
        update_state_binary_info "${FINAL_BIN_PATH}" "${FINAL_BIN_SHA}" "${FINAL_BIN_HEAD}" "${FINAL_BIN_REUSED}"
    fi

    if [[ -z "${FINAL_BIN_SHA}" && -n "${FINAL_BIN_PATH}" && -f "${FINAL_BIN_PATH}" ]]; then
        FINAL_BIN_SHA="$(sha256sum "${FINAL_BIN_PATH}" | awk '{print $1}')"
        update_state_binary_info "${FINAL_BIN_PATH}" "${FINAL_BIN_SHA}" "${FINAL_BIN_HEAD}" "${FINAL_BIN_REUSED}"
    fi

    if [[ -z "${FINAL_BIN_HEAD}" ]]; then
        if [[ -d "${KLIPPER_DIR}/.git" ]]; then
            if ! FINAL_BIN_HEAD="$(git -C "${KLIPPER_DIR}" rev-parse HEAD 2>/dev/null)"; then
                FINAL_BIN_HEAD="inconnu"
            fi
        else
            FINAL_BIN_HEAD="inconnu"
        fi
    fi

    if [[ -z "${FINAL_BIN_PATH}" ]]; then
        FINAL_BIN_PATH="${KLIPPER_DIR}/out/klipper.bin"
    fi

    if [[ -z "${FINAL_BIN_SHA}" ]]; then
        print_error "Impossible de déterminer le SHA256 du firmware généré."
        exit 1
    fi

    print_info "SHA256 (klipper.bin) : ${FINAL_BIN_SHA}"
    log_build_sha "${FINAL_BIN_PATH}" "${FINAL_BIN_SHA}" "${FINAL_BIN_HEAD}" "${FINAL_BIN_REUSED}"

    preserve_final_binary "sauvegarde post-compilation" || true
    restore_repo_if_dirty

    if [[ "${FINAL_BIN_REUSED}" == "true" ]]; then
        print_success "Binaire Klipper réutilisé : ${FINAL_BIN_PATH} (SHA256 ${FINAL_BIN_SHA:0:12})."
    else
        print_success "Firmware disponible : ${FINAL_BIN_PATH} (SHA256 ${FINAL_BIN_SHA:0:12})."
    fi

    report_python_cache_status

    finish_step "finalize"
fi


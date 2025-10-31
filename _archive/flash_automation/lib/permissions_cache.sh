# shellcheck shell=bash

if [[ -n "${FLASH_AUTOMATION_LIB_PERMISSIONS_CACHE_SH:-}" ]]; then
    return 0
fi
FLASH_AUTOMATION_LIB_PERMISSIONS_CACHE_SH=1

DEFAULT_CACHE_HOME="${XDG_CACHE_HOME:-${HOME}/.cache}"
PERMISSIONS_CACHE_FILE="${BMCU_PERMISSION_CACHE_FILE:-${DEFAULT_CACHE_HOME}/bmcu_permissions.json}"
PERMISSIONS_CACHE_TTL_RAW="${BMCU_PERMISSION_CACHE_TTL:-3600}"
PERMISSIONS_CACHE_BACKEND_OVERRIDE="${BMCU_PERMISSION_CACHE_BACKEND:-}"
if [[ "${PERMISSIONS_CACHE_TTL_RAW}" =~ ^[0-9]+$ ]]; then
    PERMISSIONS_CACHE_TTL="${PERMISSIONS_CACHE_TTL_RAW}"
else
    PERMISSIONS_CACHE_TTL=0
fi
PERMISSIONS_CACHE_MESSAGE=""

permissions_cache_enabled() {
    [[ "${PERMISSIONS_CACHE_TTL}" -gt 0 ]] && [[ -n "${PERMISSIONS_CACHE_FILE}" ]]
}

# Lorsque python3 est absent (ou explicitement désactivé via BMCU_PERMISSION_CACHE_BACKEND=bash),
# le cache de permissions est lu/écrit au format TSV à l'aide des fonctions Bash ci-dessous.
# Ce mode dégradé conserve uniquement les informations essentielles : statut, timestamp, TTL, origine et message.
permissions_cache_use_python() {
    case "${PERMISSIONS_CACHE_BACKEND_OVERRIDE}" in
        python)
            return 0
            ;;
        bash)
            return 1
            ;;
    esac

    if command -v python3 >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

permissions_cache_epoch_seconds() {
    local now
    if now=$(date -u +%s 2>/dev/null); then
        printf '%s\n' "${now}"
    elif now=$(date +%s 2>/dev/null); then
        printf '%s\n' "${now}"
    else
        return 1
    fi
}

permissions_cache_sanitize_field() {
    local value="$1"
    value="${value//$'\n'/ }"
    value="${value//$'\r'/ }"
    value="${value//$'\t'/ }"
    printf '%s' "${value}"
}

permissions_cache_read_bash() {
    local path="${PERMISSIONS_CACHE_FILE}"
    local status checked_epoch stored_ttl origin extra

    if [[ ! -s "${path}" ]]; then
        return 1
    fi

    IFS=$'\t' read -r status checked_epoch stored_ttl origin extra < "${path}" || return 1

    if [[ "${status}" != "ok" ]]; then
        return 1
    fi

    if [[ -z "${checked_epoch}" ]] || [[ ! "${checked_epoch}" =~ ^[0-9]+$ ]]; then
        return 1
    fi

    local ttl="${PERMISSIONS_CACHE_TTL}"
    if [[ -n "${stored_ttl}" ]] && [[ "${stored_ttl}" =~ ^[0-9]+$ ]]; then
        ttl="${stored_ttl}"
    fi

    if [[ "${ttl}" -le 0 ]]; then
        return 1
    fi

    local now
    if ! now="$(permissions_cache_epoch_seconds)"; then
        return 1
    fi

    local age=$(( now - checked_epoch ))
    if (( age < 0 )); then
        age=0
    fi

    if (( age >= ttl )); then
        return 1
    fi

    local remaining=$(( ttl - age ))
    local origin_note=""
    if [[ -n "${origin}" ]]; then
        origin_note=" — source ${origin}"
    fi

    if [[ -n "${extra}" ]]; then
        origin_note+=" — ${extra}"
    fi

    PERMISSIONS_CACHE_MESSAGE="cache valide (vérifié il y a $(format_duration_seconds "${age}"); expiration dans $(format_duration_seconds "${remaining}"))${origin_note}"
    return 0
}

permissions_cache_write_bash() {
    local status="$1"
    local message="$2"
    local origin_override="${3:-}"
    local ttl="${PERMISSIONS_CACHE_TTL}"
    local origin="${origin_override:-${PERMISSIONS_ORIGIN:-flash_automation.sh}}"

    if [[ "${ttl}" -le 0 ]]; then
        return 0
    fi

    local now
    if ! now="$(permissions_cache_epoch_seconds)"; then
        return 1
    fi

    local sanitized_message
    sanitized_message="$(permissions_cache_sanitize_field "${message}")"
    origin="$(permissions_cache_sanitize_field "${origin}")"

    local cache_dir
    cache_dir="$(dirname "${PERMISSIONS_CACHE_FILE}")"
    if [[ -n "${cache_dir}" ]] && [[ "${cache_dir}" != "." ]]; then
        mkdir -p "${cache_dir}" || return 1
    fi

    if ! printf '%s\t%s\t%s\t%s\t%s\n' "${status}" "${now}" "${ttl}" "${origin}" "${sanitized_message}" > "${PERMISSIONS_CACHE_FILE}"; then
        return 1
    fi
}

should_skip_permission_checks() {
    PERMISSIONS_CACHE_MESSAGE=""
    if ! permissions_cache_enabled; then
        return 1
    fi
    if [[ ! -f "${PERMISSIONS_CACHE_FILE}" ]]; then
        return 1
    fi

    if ! permissions_cache_use_python; then
        if permissions_cache_read_bash; then
            return 0
        fi
        return 1
    fi

    local output
    if ! output=$(PERMISSIONS_CACHE_FILE="${PERMISSIONS_CACHE_FILE}" PERMISSIONS_CACHE_TTL="${PERMISSIONS_CACHE_TTL}" python3 - <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

path = os.environ["PERMISSIONS_CACHE_FILE"]
try:
    ttl = int(os.environ["PERMISSIONS_CACHE_TTL"])
except (KeyError, ValueError):
    sys.exit(1)

if ttl <= 0:
    sys.exit(1)

try:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
except Exception:
    sys.exit(1)

if data.get("status") != "ok":
    sys.exit(1)

checked_raw = data.get("checked_at")
if not isinstance(checked_raw, str):
    sys.exit(1)

try:
    checked = datetime.fromisoformat(checked_raw)
except ValueError:
    sys.exit(1)

if checked.tzinfo is None:
    checked = checked.replace(tzinfo=timezone.utc)

now = datetime.now(timezone.utc)
age = (now - checked).total_seconds()
if age < 0:
    age = 0

if age >= ttl:
    sys.exit(1)

remaining = ttl - age

def format_duration(value: float) -> str:
    total = max(int(round(value)), 0)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)

print(
    f"cache valide (vérifié il y a {format_duration(age)}; "
    f"expiration dans {format_duration(remaining)})"
)
PY
    ); then
        return 1
    fi
    PERMISSIONS_CACHE_MESSAGE="${output}"
    return 0
}

update_permissions_cache() {
    local status="$1"
    local message="$2"

    if ! permissions_cache_enabled; then
        return
    fi

    if ! permissions_cache_use_python; then
        if ! permissions_cache_write_bash "${status}" "${message}" "flash_automation.verify_environment"; then
            warn "Impossible de mettre à jour le cache de permissions (${PERMISSIONS_CACHE_FILE})."
            return 1
        fi
        return 0
    fi

    if ! PERMISSIONS_STATUS="${status}" \
        PERMISSIONS_MESSAGE="${message}" \
        PERMISSIONS_ORIGIN="flash_automation.verify_environment" \
        PERMISSIONS_CACHE_FILE="${PERMISSIONS_CACHE_FILE}" \
        PERMISSIONS_CACHE_TTL="${PERMISSIONS_CACHE_TTL}" python3 - <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

path = os.environ["PERMISSIONS_CACHE_FILE"]
try:
    ttl = int(os.environ["PERMISSIONS_CACHE_TTL"])
except (KeyError, ValueError):
    sys.exit(0)

if ttl <= 0:
    sys.exit(0)

payload = {
    "status": os.environ.get("PERMISSIONS_STATUS", "ok"),
    "checked_at": datetime.now(timezone.utc).isoformat(),
    "origin": os.environ.get("PERMISSIONS_ORIGIN", "flash_automation.sh"),
    "ttl_seconds": ttl,
}

message = os.environ.get("PERMISSIONS_MESSAGE", "")
if message:
    payload["message"] = message

cache_dir = os.path.dirname(path) or "."
try:
    os.makedirs(cache_dir, exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)
except Exception:
    sys.exit(1)
else:
    sys.exit(0)
PY
    then
        warn "Impossible de mettre à jour le cache de permissions (${PERMISSIONS_CACHE_FILE})."
        return 1
    fi
    return 0
}

invalidate_permissions_cache() {
    if permissions_cache_enabled && [[ -f "${PERMISSIONS_CACHE_FILE}" ]]; then
        rm -f "${PERMISSIONS_CACHE_FILE}" || true
    fi
}

"""Tests unitaires ciblant les bibliothèques shell de flash_automation."""

from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
import time
from pathlib import Path

import pytest

FLASH_DIR = Path(__file__).resolve().parents[1]
LIB_DIR = FLASH_DIR / "lib"


def run_shell(script: str, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    wrapped = textwrap.dedent(
        f"""
        set -euo pipefail
        {script}
        """
    )
    base_env = os.environ.copy()
    if env:
        base_env.update(env)
    bash_path = base_env.get("BASH", shutil.which("bash"))
    if bash_path is None:
        bash_path = "/bin/bash"
    return subprocess.run(
        [bash_path, "-c", wrapped],
        cwd=str(FLASH_DIR),
        text=True,
        capture_output=True,
        env=base_env,
    )


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (5, "5s"),
        (65, "1m 5s"),
        (3665, "1h 1m 5s"),
    ],
)
def test_ui_format_duration_and_logging(tmp_path: Path, seconds: int, expected: str) -> None:
    log_file = tmp_path / "flash.log"
    env = {
        "LOG_FILE": str(log_file),
        "CLI_NO_COLOR_REQUESTED": "false",
        "FLASH_AUTOMATION_NO_COLOR": "false",
        "QUIET_MODE": "false",
        "COLOR_RESET": "",
        "COLOR_INFO": "",
        "COLOR_WARN": "",
        "COLOR_ERROR": "",
        "COLOR_SUCCESS": "",
        "COLOR_SECTION": "",
        "COLOR_BORDER": "",
    }
    script = f"""
    normalize_boolean() {{
        local raw_value="${{1:-}}"
        case "${{raw_value}}" in
            1|true|TRUE|True|yes|YES|on|ON) printf '%s\n' "true" ;;
            0|false|FALSE|False|no|NO|off|OFF|'') printf '%s\n' "false" ;;
            *) printf '%s\n' "false" ;;
        esac
    }}
    source "{LIB_DIR / 'ui.sh'}"
    configure_color_palette
    info "Message de test"
    printf 'duration=%s\n' "$(format_duration_seconds {seconds})"
    """
    result = run_shell(script, env=env)
    assert result.returncode == 0, result.stderr
    assert f"duration={expected}" in result.stdout
    assert "[INFO] Message de test" in result.stdout
    assert log_file.read_text().strip(), "Le log doit contenir l'entrée info."


def test_permissions_cache_bash_backend(tmp_path: Path) -> None:
    cache_file = tmp_path / "cache.tsv"
    env = {
        "LOG_FILE": str(tmp_path / "log.txt"),
        "COLOR_RESET": "",
        "COLOR_INFO": "",
        "COLOR_WARN": "",
        "COLOR_ERROR": "",
        "COLOR_SUCCESS": "",
        "COLOR_SECTION": "",
        "COLOR_BORDER": "",
        "QUIET_MODE": "false",
        "BMCU_PERMISSION_CACHE_FILE": str(cache_file),
        "BMCU_PERMISSION_CACHE_TTL": "120",
        "BMCU_PERMISSION_CACHE_BACKEND": "bash",
    }
    now = int(time.time())
    cache_content = f"ok\t{now}\t120\tflash_automation.tests\tmanual\n"
    script = f"""
    normalize_boolean() {{
        printf '%s\n' "false"
    }}
    source "{LIB_DIR / 'ui.sh'}"
    source "{LIB_DIR / 'permissions_cache.sh'}"
    if should_skip_permission_checks; then
        echo "skip_before=yes"
    else
        echo "skip_before=no"
    fi
    cat <<'CACHE' > "{cache_file}"
{cache_content}
CACHE
    if should_skip_permission_checks; then
        echo "skip_after=yes"
    else
        echo "skip_after=no"
    fi
    echo "message=${{PERMISSIONS_CACHE_MESSAGE:-}}"
    """
    result = run_shell(script, env=env)
    assert result.returncode == 0, result.stderr
    assert "skip_before=no" in result.stdout
    assert "skip_after=yes" in result.stdout
    assert "cache valide" in result.stdout


def test_wchisp_resolution_fallback(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    env = {
        "FLASH_ROOT": str(FLASH_DIR),
        "CACHE_ROOT": str(cache_root),
        "TOOLS_ROOT": str(cache_root / "tools"),
        "LOG_FILE": str(tmp_path / "wchisp.log"),
        "COLOR_RESET": "",
        "COLOR_INFO": "",
        "COLOR_WARN": "",
        "COLOR_ERROR": "",
        "COLOR_SUCCESS": "",
        "COLOR_SECTION": "",
        "COLOR_BORDER": "",
        "QUIET_MODE": "true",
        "WCHISP_ARCH_OVERRIDE": "armv7l",
        "WCHISP_FALLBACK_ARCHIVE_URL": "https://example.com/wchisp.tar.gz",
        "WCHISP_FALLBACK_ARCHIVE_NAME": "wchisp-custom.tar.gz",
        "WCHISP_FALLBACK_CHECKSUM": "deadbeef",
        "ALLOW_UNVERIFIED_WCHISP": "false",
    }
    script = f"""
    normalize_boolean() {{
        printf '%s\n' "false"
    }}
    source "{LIB_DIR / 'ui.sh'}"
    source "{LIB_DIR / 'wchisp.sh'}"
    echo "normalized=$(normalize_wchisp_machine arm64)"
    echo "resolution=$(resolve_wchisp_download)"
    """
    result = run_shell(script, env=env)
    assert result.returncode == 0, result.stderr
    assert "normalized=aarch64" in result.stdout
    assert "|fallback|" in result.stdout.split("resolution=")[1]

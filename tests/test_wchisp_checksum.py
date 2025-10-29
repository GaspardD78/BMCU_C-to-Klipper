import hashlib
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "flash_automation" / "flash_automation.sh"
LOGS_DIR = SCRIPT_PATH.parent / "logs"


def _cleanup_logs(snapshot):
    if not LOGS_DIR.exists():
        return
    current = set(LOGS_DIR.iterdir())
    for path in current - snapshot:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
    if not snapshot and LOGS_DIR.exists() and not any(LOGS_DIR.iterdir()):
        LOGS_DIR.rmdir()


def _run_bash(script_body, *, env=None):
    env_vars = os.environ.copy()
    if env:
        env_vars.update(env)
    existing_logs = set(LOGS_DIR.iterdir()) if LOGS_DIR.exists() else set()
    try:
        result = subprocess.run(
            ["bash", "-lc", script_body],
            check=False,
            capture_output=True,
            text=True,
            env=env_vars,
        )
    finally:
        _cleanup_logs(existing_logs)
    return result


@pytest.fixture()
def archive_path(tmp_path):
    archive = tmp_path / "wchisp-test.tar.gz"
    archive.write_bytes(b"dummy archive contents")
    return archive


def _parse_status_and_presence(output):
    status_line = next((line for line in output.splitlines() if line.startswith("status=")), None)
    presence_line = next((line for line in output.splitlines() if line.startswith("archive=")), None)
    assert status_line is not None, f"status line missing in output:\n{output}"
    assert presence_line is not None, f"archive presence line missing in output:\n{output}"
    status = int(status_line.split("=", 1)[1])
    present = presence_line.split("=", 1)[1].strip() == "present"
    return status, present


def test_verification_failure_removes_archive_without_degraded_mode(archive_path):
    script = textwrap.dedent(
        f"""
        export ALLOW_UNVERIFIED_WCHISP=false
        source "{SCRIPT_PATH}"
        flash_automation_initialize
        trap - ERR
        trap - EXIT
        set +e
        verify_wchisp_archive "asset.tar.gz" "{archive_path}" "deadbeef"
        status=$?
        if [[ -f "{archive_path}" ]]; then
            echo "archive=present"
        else
            echo "archive=missing"
        fi
        echo "status=$status"
        exit 0
        """
    )
    result = _run_bash(script)
    assert result.returncode == 0, result.stderr
    status, present = _parse_status_and_presence(result.stdout)
    assert status == 1
    assert present is False


def test_degraded_mode_keeps_archive_and_warns(archive_path):
    script = textwrap.dedent(
        f"""
        export ALLOW_UNVERIFIED_WCHISP=true
        source "{SCRIPT_PATH}"
        flash_automation_initialize
        trap - ERR
        trap - EXIT
        set +e
        verify_wchisp_archive "asset.tar.gz" "{archive_path}" "deadbeef"
        status=$?
        if [[ -f "{archive_path}" ]]; then
            echo "archive=present"
        else
            echo "archive=missing"
        fi
        echo "status=$status"
        exit 0
        """
    )
    result = _run_bash(script)
    assert result.returncode == 0, result.stderr
    status, present = _parse_status_and_presence(result.stdout)
    assert status == 0
    assert present is True
    combined_output = result.stdout + result.stderr
    assert "Mode dégradé actif" in combined_output


def test_checksum_override_allows_custom_value(archive_path):
    actual = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    script = textwrap.dedent(
        f"""
        export WCHISP_ARCHIVE_CHECKSUM_OVERRIDE="{actual}"
        export ALLOW_UNVERIFIED_WCHISP=false
        source "{SCRIPT_PATH}"
        flash_automation_initialize
        trap - ERR
        trap - EXIT
        set +e
        verify_wchisp_archive "asset.tar.gz" "{archive_path}" "incorrect"
        status=$?
        if [[ -f "{archive_path}" ]]; then
            echo "archive=present"
        else
            echo "archive=missing"
        fi
        echo "status=$status"
        exit 0
        """
    )
    result = _run_bash(script)
    assert result.returncode == 0, result.stderr
    status, present = _parse_status_and_presence(result.stdout)
    assert status == 0
    assert present is True

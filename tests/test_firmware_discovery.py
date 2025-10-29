import textwrap
from pathlib import Path

import pytest

from test_wchisp_checksum import _run_bash


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "flash_automation" / "flash_automation.sh"
FLASH_ROOT = SCRIPT_PATH.parent


@pytest.fixture()
def firmware_cleanup():
    created = []
    yield created
    for path in reversed(created):
        if path.is_file():
            path.unlink(missing_ok=True)


def _touch(path: Path, created):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"firmware")
    created.append(path)


def _parse_candidates(output: str):
    candidates = []
    for line in output.splitlines():
        if line.startswith("candidate="):
            candidates.append(line.split("=", 1)[1])
    return candidates


def test_default_scan_targets_primary_paths(firmware_cleanup):
    default_fw = FLASH_ROOT / ".cache" / "klipper" / "out" / "scan-default.bin"
    alt_fw = FLASH_ROOT / ".cache" / "firmware" / "scan-alt.uf2"
    logs_fw = FLASH_ROOT / "logs" / "scan-log.bin"
    deep_fw = FLASH_ROOT / "scan-deep.bin"

    for path in (default_fw, alt_fw, logs_fw, deep_fw):
        _touch(path, firmware_cleanup)

    script = textwrap.dedent(
        f"""
        source "{SCRIPT_PATH}"
        trap - ERR
        trap - EXIT
        set +e
        set +u
        collect_firmware_candidates candidates
        for item in "${{candidates[@]}}"; do
            echo "candidate=$item"
        done
        exit 0
        """
    )

    result = _run_bash(script)
    assert result.returncode == 0, result.stderr
    candidates = set(_parse_candidates(result.stdout))

    assert str(default_fw) in candidates
    assert str(alt_fw) in candidates
    assert str(logs_fw) not in candidates
    assert str(deep_fw) not in candidates


def test_deep_scan_includes_repository_root(firmware_cleanup):
    deep_fw = FLASH_ROOT / "scan-deep-mode.bin"
    _touch(deep_fw, firmware_cleanup)

    script = textwrap.dedent(
        f"""
        source "{SCRIPT_PATH}"
        trap - ERR
        trap - EXIT
        set +e
        set +u
        parse_cli_arguments --deep-scan
        apply_configuration_defaults
        collect_firmware_candidates candidates
        for item in "${{candidates[@]}}"; do
            echo "candidate=$item"
        done
        exit 0
        """
    )

    result = _run_bash(script)
    assert result.returncode == 0, result.stderr
    candidates = set(_parse_candidates(result.stdout))

    assert str(deep_fw) in candidates


def test_cli_exclude_path_removes_directory(firmware_cleanup):
    control_fw = FLASH_ROOT / ".cache" / "klipper" / "out" / "scan-control.bin"
    default_fw = FLASH_ROOT / ".cache" / "firmware" / "custom" / "scan-keep.bin"
    excluded_fw = FLASH_ROOT / ".cache" / "firmware" / "custom" / "scan-skip.bin"
    _touch(control_fw, firmware_cleanup)
    _touch(default_fw, firmware_cleanup)
    _touch(excluded_fw, firmware_cleanup)

    script = textwrap.dedent(
        f"""
        source "{SCRIPT_PATH}"
        trap - ERR
        trap - EXIT
        set +e
        set +u
        parse_cli_arguments --exclude-path ".cache/firmware/custom"
        apply_configuration_defaults
        collect_firmware_candidates candidates
        for item in "${{candidates[@]}}"; do
            echo "candidate=$item"
        done
        exit 0
        """
    )

    result = _run_bash(script)
    assert result.returncode == 0, result.stderr
    candidates = set(_parse_candidates(result.stdout))

    assert str(excluded_fw) not in candidates
    assert str(default_fw) not in candidates
    assert str(control_fw) in candidates

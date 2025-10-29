import os
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


def _touch(path: Path, created, *, mtime: int | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"firmware")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    created.append(path)


def _parse_candidates(output: str):
    values = []
    for line in output.splitlines():
        if line.startswith("candidate="):
            values.append(line.split("=", 1)[1])
    return values


def _parse_selected(output: str):
    for line in output.splitlines():
        if line.startswith("selected="):
            return line.split("=", 1)[1]
    raise AssertionError(f"selected line missing in output:\n{output}")


def test_candidates_sorted_by_mtime_descending(firmware_cleanup):
    older = FLASH_ROOT / ".cache" / "klipper" / "out" / "sorted-old.bin"
    newer = FLASH_ROOT / ".cache" / "klipper" / "out" / "sorted-new.bin"
    _touch(older, firmware_cleanup, mtime=1_700_000_000)
    _touch(newer, firmware_cleanup, mtime=1_800_000_000)

    script = textwrap.dedent(
        f"""
        source "{SCRIPT_PATH}"
        flash_automation_initialize
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
    candidates = _parse_candidates(result.stdout)

    assert candidates[0] == str(newer)
    assert candidates[1] == str(older)


def test_auto_confirm_prefers_pattern_match(firmware_cleanup):
    release = FLASH_ROOT / ".cache" / "klipper" / "out" / "release-fw.bin"
    debug = FLASH_ROOT / ".cache" / "klipper" / "out" / "debug-fw.bin"
    _touch(release, firmware_cleanup, mtime=1_700_000_100)
    _touch(debug, firmware_cleanup, mtime=1_800_000_000)

    script = textwrap.dedent(
        f"""
        source "{SCRIPT_PATH}"
        flash_automation_initialize
        trap - ERR
        trap - EXIT
        set +e
        set +u
        parse_cli_arguments --auto-confirm --firmware-pattern 'release-*.bin'
        apply_configuration_defaults
        prepare_firmware
        echo "selected=$FIRMWARE_FILE"
        exit 0
        """
    )

    result = _run_bash(script)
    assert result.returncode == 0, result.stderr
    selected = _parse_selected(result.stdout)
    assert selected == str(release)


def test_auto_confirm_defaults_to_newest_without_pattern(firmware_cleanup):
    older = FLASH_ROOT / ".cache" / "klipper" / "out" / "auto-old.bin"
    newer = FLASH_ROOT / ".cache" / "klipper" / "out" / "auto-new.bin"
    _touch(older, firmware_cleanup, mtime=1_700_000_000)
    _touch(newer, firmware_cleanup, mtime=1_900_000_000)

    script = textwrap.dedent(
        f"""
        source "{SCRIPT_PATH}"
        flash_automation_initialize
        trap - ERR
        trap - EXIT
        set +e
        set +u
        parse_cli_arguments --auto-confirm
        apply_configuration_defaults
        prepare_firmware
        echo "selected=$FIRMWARE_FILE"
        exit 0
        """
    )

    result = _run_bash(script)
    assert result.returncode == 0, result.stderr
    selected = _parse_selected(result.stdout)
    assert selected == str(newer)


def test_auto_confirm_pattern_miss_falls_back_to_newest(firmware_cleanup):
    older = FLASH_ROOT / ".cache" / "klipper" / "out" / "miss-old.bin"
    newer = FLASH_ROOT / ".cache" / "klipper" / "out" / "miss-new.bin"
    _touch(older, firmware_cleanup, mtime=1_700_000_000)
    _touch(newer, firmware_cleanup, mtime=1_900_000_000)

    script = textwrap.dedent(
        f"""
        source "{SCRIPT_PATH}"
        flash_automation_initialize
        trap - ERR
        trap - EXIT
        set +e
        set +u
        parse_cli_arguments --auto-confirm --firmware-pattern 'no-match-*.bin'
        apply_configuration_defaults
        prepare_firmware
        echo "selected=$FIRMWARE_FILE"
        exit 0
        """
    )

    result = _run_bash(script)
    assert result.returncode == 0, result.stderr
    selected = _parse_selected(result.stdout)
    assert selected == str(newer)

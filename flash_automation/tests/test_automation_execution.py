"""Tests for the execution flow of flashBMCUtoKlipper_automation.py."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Iterator

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

AUTOMATION_SCRIPT = ROOT_DIR / "flash_automation" / "flashBMCUtoKlipper_automation.py"


@pytest.fixture
def isolated_env(tmp_path: Path) -> Iterator[dict[str, str]]:
    """Creates an environment with an empty PATH."""
    env = os.environ.copy()
    env["PATH"] = str(tmp_path / "bin")
    (tmp_path / "bin").mkdir()
    yield env


def test_dry_run_succeeds_without_remote_dependencies(isolated_env: dict[str, str], tmp_path: Path) -> None:
    """
    Ensures that --dry-run completes successfully even if remote dependencies
    like 'ipmitool', 'sshpass', 'scp', and 'ping' are missing.
    """
    firmware_file = tmp_path / "klipper.bin"
    firmware_file.write_text("dummy firmware")

    args = [
        sys.executable,
        str(AUTOMATION_SCRIPT),
        "--dry-run",
        "--bmc-host", "dummy-host",
        "--bmc-user", "dummy-user",
        "--bmc-password", "dummy-password",
        "--firmware-file", str(firmware_file),
    ]

    result = subprocess.run(args, capture_output=True, text=True, env=isolated_env, check=False)

    assert result.returncode == 0, f"Le script a échoué en mode dry-run.\\nSTDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"
    assert "Flash du BMC terminé avec succès" in result.stdout

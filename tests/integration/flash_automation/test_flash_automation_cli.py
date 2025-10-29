import os
import subprocess
from pathlib import Path
from typing import Iterable

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
FLASH_DIR = REPO_ROOT / "flash_automation"
FLASH_SCRIPT = FLASH_DIR / "flash_automation.sh"


def _base_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    home_dir = tmp_path / "home"
    cache_dir = tmp_path / "xdg-cache"
    home_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    env.update(
        {
            "HOME": str(home_dir),
            "XDG_CACHE_HOME": str(cache_dir),
            "WCHISP_BIN": "/bin/true",
            "DFU_UTIL_BIN": "/bin/true",
            "FLASH_AUTOMATION_OS_OVERRIDE": "Linux",
            # Force the bash backend to avoid relying on python for the
            # permissions cache in constrained environments.
            "BMCU_PERMISSION_CACHE_BACKEND": "bash",
            "LC_ALL": "C.UTF-8",
            "LANG": "C.UTF-8",
        }
    )
    return env


def _run_flash(args: Iterable[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(FLASH_SCRIPT), *args],
        cwd=FLASH_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _create_dummy_firmware(tmp_path: Path, name: str = "klipper.bin") -> Path:
    firmware = tmp_path / name
    firmware.write_text("dummy firmware", encoding="utf-8")
    return firmware


def _build_fake_path(root: Path, *, exclude_prefixes: tuple[str, ...]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    search_roots = [
        Path("/bin"),
        Path("/usr/bin"),
        Path("/usr/local/bin"),
        Path("/usr/sbin"),
        Path("/sbin"),
    ]

    for directory in search_roots:
        if not directory.is_dir():
            continue
        for entry in directory.iterdir():
            name = entry.name
            if any(name.startswith(prefix) for prefix in exclude_prefixes):
                continue
            destination = root / name
            if destination.exists():
                continue
            try:
                destination.symlink_to(entry)
            except OSError:
                # Ignore sockets, fifos or entries requiring elevated privileges.
                continue
    return root


@pytest.fixture
def firmware(tmp_path: Path) -> Path:
    return _create_dummy_firmware(tmp_path)


@pytest.fixture
def flash_env(tmp_path: Path) -> dict[str, str]:
    env = _base_env(tmp_path)
    env["PATH"] = os.environ.get("PATH", "")
    return env


def test_wchisp_dry_run_success(firmware: Path, flash_env: dict[str, str]):
    result = _run_flash(
        [
            "--firmware",
            str(firmware),
            "--dry-run",
            "--auto-confirm",
            "--method",
            "wchisp",
        ],
        flash_env,
    )
    assert result.returncode == 0, result.stdout
    assert "Méthode    : flash direct via wchisp" in result.stdout
    assert "Mode       : Simulation (dry-run), aucune action réelle." in result.stdout


def test_serial_dry_run_with_forced_port(tmp_path: Path, firmware: Path, flash_env: dict[str, str]):
    serial_stub = tmp_path / "ttyUSB_FAKE"
    serial_stub.touch()
    result = _run_flash(
        [
            "--firmware",
            str(firmware),
            "--dry-run",
            "--auto-confirm",
            "--method",
            "serial",
            "--serial-port",
            str(serial_stub),
        ],
        flash_env,
    )
    assert result.returncode == 0, result.stdout
    assert "Méthode    : flash série via flash_usb.py" in result.stdout
    assert f"Port série : {serial_stub}" in result.stdout
    assert "Mode       : Simulation (dry-run), aucune action réelle." in result.stdout


def test_dfu_dry_run_with_stubbed_binary(firmware: Path, flash_env: dict[str, str]):
    result = _run_flash(
        [
            "--firmware",
            str(firmware),
            "--dry-run",
            "--auto-confirm",
            "--method",
            "dfu",
        ],
        flash_env,
    )
    assert result.returncode == 0, result.stdout
    assert "Méthode    : flash DFU via /bin/true" in result.stdout
    assert "Mode       : Simulation (dry-run), aucune action réelle." in result.stdout


def test_sdcard_copy_writes_to_target(tmp_path: Path, firmware: Path, flash_env: dict[str, str]):
    sd_mount = tmp_path / "sdcard"
    sd_mount.mkdir()
    result = _run_flash(
        [
            "--firmware",
            str(firmware),
            "--auto-confirm",
            "--method",
            "sdcard",
            "--sdcard-path",
            str(sd_mount),
            "--quiet",
        ],
        flash_env,
    )
    assert result.returncode == 0, result.stdout
    copied = sd_mount / firmware.name
    assert copied.exists(), result.stdout
    assert copied.read_text(encoding="utf-8") == firmware.read_text(encoding="utf-8")


def test_missing_python3_emits_warning(tmp_path: Path, firmware: Path):
    fake_path = _build_fake_path(tmp_path / "fake-path", exclude_prefixes=("python",))
    env = _base_env(tmp_path)
    env["PATH"] = str(fake_path)
    result = _run_flash(
        [
            "--firmware",
            str(firmware),
            "--dry-run",
            "--auto-confirm",
            "--method",
            "wchisp",
        ],
        env,
    )
    assert result.returncode != 0, result.stdout
    assert "La dépendance optionnelle 'python3' est absente" in result.stdout

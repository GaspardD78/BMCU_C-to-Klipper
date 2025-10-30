import hashlib
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from flash_automation.build_manager import BuildManager
from flash_automation.flash_manager import FlashManager

FLASH_ROOT = Path(__file__).resolve().parents[1]
BANNER_TEXT = (FLASH_ROOT / "banner.txt").read_text()

STUB_ARCHIVE_CONTENT = b"stub archive"
STUB_ARCHIVE_SHA256 = hashlib.sha256(STUB_ARCHIVE_CONTENT).hexdigest()

def ensure_real_command(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"The command '{name}' must be available in PATH during tests")
    return path

def create_stub_environment(
    tmp_path: Path, *, include_system_path: bool = False, set_user: bool = True
) -> tuple[dict[str, str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    base_path = env.get("PATH", "") if include_system_path else ""
    env["PATH"] = f"{bin_dir}{os.pathsep}{base_path}" if base_path else str(bin_dir)
    env["HOME"] = str(tmp_path)
    if set_user:
        env["USER"] = env.get("USER", "testuser")
    else:
        env.pop("USER", None)
    return env, bin_dir

def test_build_manager_compiles_firmware(tmp_path, monkeypatch):
    """Vérifie que BuildManager clone et compile le firmware."""
    env, bin_dir = create_stub_environment(tmp_path)
    monkeypatch.setenv("PATH", env["PATH"])

    # Stubs pour git et make
    git_stub = bin_dir / "git"
    git_stub.write_text("#!/bin/sh\necho 'git stub' >&2\n")
    git_stub.chmod(0o755)

    make_stub = bin_dir / "make"
    make_stub.write_text("#!/bin/sh\necho 'make stub' >&2\n")
    make_stub.chmod(0o755)

    # Crée un faux config.json
    (tmp_path / "config.json").write_text('{"klipper": {"repository_url": "dummy", "git_ref": "dummy"}}')

    manager = BuildManager(tmp_path)
    manager.klipper_dir = tmp_path / "klipper"
    manager.klipper_dir.mkdir()
    (manager.klipper_dir / ".git").mkdir()

    # Crée un faux klipper.config
    (tmp_path / "klipper.config").write_text("CONFIG_FOO=y")

    # Crée un faux binaire pour simuler la compilation
    out_dir = manager.klipper_dir / "out"
    out_dir.mkdir()
    (out_dir / "klipper.bin").write_text("firmware")

    firmware_path = manager.compile_firmware()
    assert firmware_path.exists()
    assert firmware_path.name == "klipper.bin"

def test_flash_manager_flashes_serial(tmp_path, monkeypatch):
    """Vérifie que FlashManager appelle flash_usb.py pour la méthode série."""
    env, bin_dir = create_stub_environment(tmp_path)
    monkeypatch.setenv("PATH", env["PATH"])

    # Stub pour python3
    python_stub = bin_dir / "python3"
    python_stub.write_text("#!/bin/sh\necho 'python3 stub' >&2\n")
    python_stub.chmod(0o755)

    manager = FlashManager(tmp_path)

    # Crée un faux script flash_usb.py au nouvel emplacement attendu
    klipper_lib_dir = tmp_path / ".cache/klipper/lib"
    klipper_lib_dir.mkdir(parents=True)
    flash_script = klipper_lib_dir / "flash_usb.py"
    flash_script.write_text("#!/bin/sh\necho 'flash_usb stub' >&2\n")

    firmware = tmp_path / "klipper.bin"
    firmware.write_text("firmware")

    manager.flash_serial(firmware, "/dev/ttyUSB0")

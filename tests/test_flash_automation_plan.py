# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
from pathlib import Path


def prepare_flash_workspace(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    source_flash_root = repo_root / "flash_automation"

    work_root = tmp_path / "workspace"
    work_root.mkdir()

    flash_root = work_root / "flash_automation"
    shutil.copytree(
        source_flash_root,
        flash_root,
        ignore=shutil.ignore_patterns(".cache", "logs"),
    )

    return flash_root


def test_dry_run_progresses_without_firmware(tmp_path):
    flash_root = prepare_flash_workspace(tmp_path)

    script_path = flash_root / "flash_automation.sh"
    fake_sd = flash_root / "fake_sd"
    fake_sd.mkdir()

    env = os.environ.copy()
    env.update(
        {
            "FLASH_AUTOMATION_NO_COLOR": "true",
            "FLASH_AUTOMATION_METHOD": "sdcard",
            "FLASH_AUTOMATION_SDCARD_PATH": str(fake_sd),
            "WCHISP_BIN": "/bin/true",
        }
    )

    result = subprocess.run(
        [str(script_path), "--dry-run"],
        cwd=flash_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Mode --dry-run : aucun firmware détecté" in result.stdout
    assert "Étape 2: Sélection de la méthode de flash" in result.stdout


def test_dry_run_stream_injection(tmp_path):
    flash_root = prepare_flash_workspace(tmp_path)
    script_path = flash_root / "flash_automation.sh"

    env = os.environ.copy()
    env.update(
        {
            "FLASH_AUTOMATION_NO_COLOR": "true",
            "FLASH_AUTOMATION_METHOD": "wchisp",
            "FLASH_AUTOMATION_DRY_RUN_STREAM": "fifo",
            "WCHISP_BIN": "/bin/true",
        }
    )

    result = subprocess.run(
        [str(script_path), "--dry-run"],
        cwd=flash_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "flux simulé" in result.stdout
    assert "N/A (flux simulé)" in result.stdout


def test_auto_confirm_sdcard_fallback_to_wchisp(tmp_path):
    flash_root = prepare_flash_workspace(tmp_path)
    script_path = flash_root / "flash_automation.sh"

    firmware_dir = flash_root / ".cache" / "klipper" / "out"
    firmware_dir.mkdir(parents=True)
    firmware_path = firmware_dir / "klipper.bin"
    firmware_path.write_bytes(b"test")

    env = os.environ.copy()
    env.update(
        {
            "FLASH_AUTOMATION_NO_COLOR": "true",
            "FLASH_AUTOMATION_METHOD": "sdcard",
            "FLASH_AUTOMATION_AUTO_CONFIRM": "true",
            "WCHISP_BIN": "/bin/true",
        }
    )

    result = subprocess.run(
        [str(script_path), "--auto-confirm"],
        cwd=flash_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Bascule automatique vers wchisp" in result.stdout
    assert "- Méthode  : wchisp" in result.stdout


def test_auto_confirm_sdcard_dry_run_uses_temp_dir(tmp_path):
    flash_root = prepare_flash_workspace(tmp_path)
    script_path = flash_root / "flash_automation.sh"

    env = os.environ.copy()
    env.update(
        {
            "FLASH_AUTOMATION_NO_COLOR": "true",
            "FLASH_AUTOMATION_METHOD": "sdcard",
            "WCHISP_BIN": "/bin/true",
        }
    )

    result = subprocess.run(
        [str(script_path), "--auto-confirm", "--dry-run"],
        cwd=flash_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Utilisation d'un répertoire temporaire" in result.stdout
    assert "mode --dry-run (répertoire simulé)" in result.stdout

    temp_dirs = list((flash_root / ".cache").glob("sdcard_dry_run_*"))
    assert not temp_dirs, "répertoire temporaire non nettoyé"

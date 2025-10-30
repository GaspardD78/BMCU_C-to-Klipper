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
    assert "Étape 3/6: Sélection de la méthode de flash" in result.stdout


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
    assert "Méthode    : flash direct via wchisp" in result.stdout


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


def test_full_dry_run_shows_steps_and_summary(tmp_path):
    flash_root = prepare_flash_workspace(tmp_path)
    script_path = flash_root / "flash_automation.sh"

    firmware_dir = flash_root / ".cache" / "klipper" / "out"
    firmware_dir.mkdir(parents=True)
    firmware_path = firmware_dir / "klipper.bin"
    firmware_path.write_bytes(b"dummy firmware content")

    dev_dir = flash_root / "dev"
    if not dev_dir.exists():
        dev_dir.mkdir()
    (dev_dir / "ttyACM0").touch()

    env = os.environ.copy()
    env.update(
        {
            "FLASH_AUTOMATION_NO_COLOR": "true",
            "WCHISP_BIN": "/bin/true",
            "DFU_UTIL_BIN": "/bin/true",
            "LC_ALL": "C.UTF-8",
        }
    )

    result = subprocess.run(
        [str(script_path), "--dry-run", "--auto-confirm"],
        cwd=flash_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        universal_newlines=True,
    )

    stdout = result.stdout
    stderr = result.stderr

    assert result.returncode == 0, f"Le script a échoué avec stderr:\\n{stderr}"

    assert "Étape 1/6: Diagnostic de l'environnement" in stdout
    assert "Étape 2/6: Sélection du firmware" in stdout
    assert "Étape 3/6: Sélection de la méthode de flash" in stdout
    assert "Étape 4/6: Préparation de la cible" in stdout
    assert "Étape 5/6: Flashage" in stdout
    assert "Étape 6/6: Rapport final" in stdout
    assert "Calcul du checksum SHA256..." in stdout
    assert "Suggestion basée sur la détection" in stdout
    assert "Rapport de flash" in stdout
    assert "Firmware   :" in stdout
    assert "SHA256     :" in stdout
    assert "Méthode    :" in stdout
    assert "Durée      :" in stdout
    assert "Journal    :" in stdout
    assert "Mode       : Simulation (dry-run), aucune action réelle." in stdout

# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
from pathlib import Path


def test_dry_run_progresses_without_firmware(tmp_path):
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

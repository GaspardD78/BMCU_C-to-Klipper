# -*- coding: utf-8 -*-

"""Tests pour l'étape 3 : Flashage du firmware."""

import subprocess
from unittest.mock import patch
import pytest

from matrix_flow.step_03_flash import FlashManager, FlashError

def test_flash_manager_initialization(tmp_path):
    """Vérifie que le FlashManager s'initialise correctement."""
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()
    klipper_dir = cache_dir / "klipper"
    klipper_dir.mkdir()
    out_dir = klipper_dir / "out"
    out_dir.mkdir()
    firmware_path = out_dir / "klipper.bin"
    firmware_path.touch()

    manager = FlashManager(base_dir=tmp_path)
    assert manager.firmware_path == firmware_path


def test_flash_success(mocker, tmp_path):
    """Vérifie le bon déroulement du flashage."""
    firmware_path = tmp_path / ".cache/klipper/out/klipper.bin"
    firmware_path.parent.mkdir(parents=True)
    firmware_path.touch()

    mocker.patch("shutil.which", return_value=True)
    mocker.patch("matrix_flow.step_03_flash.ui.ask_confirmation", return_value=True)
    mock_subprocess_run = mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(args=[], returncode=0))

    manager = FlashManager(base_dir=tmp_path)
    manager.run(serial_device="/dev/fake_port")

    # Vérifie que les commandes ont été appelées
    expected_flash_cmd = ["wchisp", "--serial", "--port", "/dev/fake_port", "flash", str(firmware_path)]
    mock_subprocess_run.assert_any_call(expected_flash_cmd, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace", env=mocker.ANY)


def test_flash_failure(mocker, tmp_path):
    """Vérifie la gestion d'un échec de la commande de flashage."""
    firmware_path = tmp_path / ".cache/klipper/out/klipper.bin"
    firmware_path.parent.mkdir(parents=True)
    firmware_path.touch()

    mocker.patch("shutil.which", return_value=True)
    mocker.patch("matrix_flow.step_03_flash.ui.ask_confirmation", return_value=True)

    def mock_run(command, **kwargs):
        if "wchisp" in command:
            raise subprocess.CalledProcessError(1, command, stderr="Flash failed!")
        return subprocess.CompletedProcess(command, 0)

    mocker.patch("subprocess.run", side_effect=mock_run)

    manager = FlashManager(base_dir=tmp_path)
    with pytest.raises(FlashError, match="Flash failed!"):
        manager.run(serial_device="/dev/fake_port")

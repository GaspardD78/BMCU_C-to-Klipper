#!/usr/bin/env python3
# Copyright (C) 2024 Gaspard Douté
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Tests pour le module orchestrator."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from flash_automation.orchestrator import Orchestrator


@pytest.fixture
def orchestrator(tmp_path: Path) -> Orchestrator:
    """Crée une instance de l'Orchestrator pour les tests."""
    return Orchestrator(tmp_path)


@patch("flash_automation.orchestrator.BuildManager")
def test_run_build_success(mock_build_manager_class, orchestrator: Orchestrator):
    """Vérifie que run_build appelle correctement le BuildManager."""
    mock_manager = MagicMock()
    mock_build_manager_class.return_value = mock_manager

    result = orchestrator.run_build()

    assert result is True
    mock_build_manager_class.assert_called_once_with(orchestrator.base_dir)
    mock_manager.compile_firmware.assert_called_once()


@patch("flash_automation.orchestrator.BuildManager")
def test_run_build_failure(mock_build_manager_class, orchestrator: Orchestrator):
    """Vérifie la gestion d'erreur si le build échoue."""
    mock_manager = MagicMock()
    mock_manager.compile_firmware.side_effect = subprocess.CalledProcessError(1, "cmd")
    mock_build_manager_class.return_value = mock_manager

    result = orchestrator.run_build()

    assert result is False


@patch("flash_automation.orchestrator.FlashManager")
def test_run_flash_success(mock_flash_manager_class, orchestrator: Orchestrator, tmp_path: Path):
    """Vérifie que run_flash appelle correctement le FlashManager."""
    firmware_path = tmp_path / "klipper.bin"
    firmware_path.touch()
    serial_device = "/dev/ttyACM0"

    mock_manager = MagicMock()
    mock_flash_manager_class.return_value = mock_manager

    result = orchestrator.run_flash(firmware_path, serial_device)

    assert result is True
    mock_flash_manager_class.assert_called_once_with(orchestrator.base_dir)
    mock_manager.flash.assert_called_once_with("serial", firmware_path, serial_device)


@patch("flash_automation.orchestrator.FlashManager")
def test_run_flash_failure(mock_flash_manager_class, orchestrator: Orchestrator, tmp_path: Path):
    """Vérifie la gestion d'erreur si le flash échoue."""
    firmware_path = tmp_path / "klipper.bin"
    firmware_path.touch()
    serial_device = "/dev/ttyACM0"

    mock_manager = MagicMock()
    mock_manager.flash.side_effect = ValueError("Flash failed")
    mock_flash_manager_class.return_value = mock_manager

    result = orchestrator.run_flash(firmware_path, serial_device)

    assert result is False


@patch("flash_automation.orchestrator.read_os_release", return_value={"ID": "debian"})
@patch("subprocess.run")
def test_get_system_dependencies(mock_subprocess_run, mock_read_os, orchestrator: Orchestrator):
    """Vérifie la détection des dépendances manquantes."""
    # Simule que 'git' est installé (code 0) et 'make' est manquant (code 1)
    def side_effect(*args, **kwargs):
        cmd = args[0]
        if "dpkg -s git" in " ".join(cmd):
            return MagicMock(returncode=0)
        return MagicMock(returncode=1)

    mock_subprocess_run.side_effect = side_effect

    _, missing = orchestrator.get_system_dependencies()

    assert "git" not in missing
    assert "make" in missing
    assert "ipmitool" in missing


@patch("subprocess.run")
def test_install_system_dependencies_success(mock_subprocess_run, orchestrator: Orchestrator):
    """Vérifie que la commande d'installation est correctement appelée."""
    mock_subprocess_run.return_value = MagicMock(returncode=0)
    packages = ["git", "make"]

    result = orchestrator.install_system_dependencies(packages)

    assert result is True
    mock_subprocess_run.assert_called_once_with(
        "sudo apt install -y git make", shell=True, check=True
    )

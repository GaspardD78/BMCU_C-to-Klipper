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
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from importlib.metadata import PackageNotFoundError

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


from flash_automation.orchestrator import Orchestrator, BuildManagerError, FlashManagerError


@pytest.fixture
def orchestrator(tmp_path: Path) -> Orchestrator:
    """Crée une instance de l'Orchestrator pour les tests."""
    (tmp_path / "config.json").write_text('{"klipper": {"repository_url": "dummy", "git_ref": "dummy"}}')
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
    mock_manager.compile_firmware.side_effect = BuildManagerError("Build failed")
    mock_build_manager_class.return_value = mock_manager

    with pytest.raises(BuildManagerError, match="Build failed"):
        orchestrator.run_build()


@patch("subprocess.run")
@patch("flash_automation.orchestrator.FlashManager")
def test_run_flash_success_manages_service(
    mock_flash_manager_class, mock_run, orchestrator: Orchestrator, tmp_path: Path
):
    """Vérifie que run_flash arrête et redémarre le service Klipper en cas de succès."""
    firmware_path = tmp_path / "klipper.bin"
    firmware_path.touch()
    serial_device = "/dev/ttyACM0"

    mock_manager = MagicMock()
    mock_flash_manager_class.return_value = mock_manager

    result = orchestrator.run_flash(firmware_path, serial_device)

    assert result is True
    mock_flash_manager_class.assert_called_once_with(orchestrator.base_dir)
    mock_manager.flash.assert_called_once_with("serial", firmware_path, serial_device)

    # Vérifie les appels à systemctl
    call_args_list = mock_run.call_args_list
    assert len(call_args_list) == 2
    assert call_args_list[0].args[0] == ["sudo", "systemctl", "stop", "klipper.service"]
    assert call_args_list[1].args[0] == ["sudo", "systemctl", "start", "klipper.service"]


@patch("subprocess.run")
@patch("flash_automation.orchestrator.FlashManager")
def test_run_flash_failure_still_restarts_service(
    mock_flash_manager_class, mock_run, orchestrator: Orchestrator, tmp_path: Path
):
    """Vérifie que le service Klipper est redémarré même si le flashage échoue."""
    firmware_path = tmp_path / "klipper.bin"
    firmware_path.touch()
    serial_device = "/dev/ttyACM0"

    mock_manager = MagicMock()
    mock_manager.flash.side_effect = FlashManagerError("Flash failed")
    mock_flash_manager_class.return_value = mock_manager

    with pytest.raises(FlashManagerError, match="Flash failed"):
        orchestrator.run_flash(firmware_path, serial_device)

    # Vérifie que les appels à systemctl ont bien eu lieu
    call_args_list = mock_run.call_args_list
    assert len(call_args_list) == 2
    assert call_args_list[0].args[0] == ["sudo", "systemctl", "stop", "klipper.service"]
    assert call_args_list[1].args[0] == ["sudo", "systemctl", "start", "klipper.service"]


@patch("flash_automation.orchestrator.read_os_release", return_value={"ID": "debian"})
@patch("subprocess.run")
def test_get_system_dependencies(mock_subprocess_run, mock_read_os, orchestrator: Orchestrator):
    """Vérifie la détection des dépendances manquantes."""
    def side_effect(cmd, **kwargs):
        # La commande est une liste, ex: ['dpkg', '-s', 'git']
        pkg = cmd[2]
        if pkg == 'git':
            # Simule que 'git' est installé
            return MagicMock(returncode=0)
        # Simule que tous les autres paquets sont manquants
        return MagicMock(returncode=1)

    mock_subprocess_run.side_effect = side_effect

    pm, _, missing = orchestrator.get_system_dependencies()

    assert pm == "apt"
    assert "git" not in missing
    assert "make" in missing
    assert "ipmitool" in missing


@patch("subprocess.run")
def test_install_system_dependencies_success(mock_subprocess_run, orchestrator: Orchestrator):
    """Vérifie que la commande d'installation est correctement appelée."""
    mock_subprocess_run.return_value = MagicMock(returncode=0)
    packages = ["git", "make"]

    result = orchestrator.install_system_dependencies("apt", packages)

    assert result is True
    mock_subprocess_run.assert_called_once_with(
        "sudo apt install -y git make", shell=True, check=True
    )


def test_get_python_dependencies(orchestrator: Orchestrator, tmp_path: Path):
    """Vérifie la détection des dépendances Python."""
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("pyserial>=3.5\n# Commentaire\ninvalid-package-name\n")

    # On simule que 'pyserial' est installé mais pas 'invalid-package-name'
    with patch("flash_automation.orchestrator.version") as mock_version:
        def side_effect(pkg):
            if pkg == "pyserial":
                return "3.5"
            raise PackageNotFoundError
        mock_version.side_effect = side_effect

        _, missing = orchestrator.get_python_dependencies()

        assert "pyserial" not in missing
        assert "invalid-package-name" in missing


@patch("subprocess.run")
def test_install_python_dependencies(mock_subprocess_run, orchestrator: Orchestrator, tmp_path: Path):
    """Vérifie que `pip install` est appelé correctement."""
    # Crée un faux fichier requirements.txt
    (tmp_path / "requirements.txt").write_text("pyserial>=3.5\n")
    mock_subprocess_run.return_value = MagicMock(returncode=0)

    orchestrator.install_python_dependencies()

    expected_cmd = [
        sys.executable, "-m", "pip", "install", "-r",
        str(orchestrator.base_dir / "requirements.txt")
    ]
    mock_subprocess_run.assert_called_once()
    called_cmd = mock_subprocess_run.call_args[0][0]
    assert called_cmd == expected_cmd


@patch("flash_automation.orchestrator.FlashManager")
def test_get_system_status(mock_flash_manager_class, orchestrator: Orchestrator, tmp_path: Path):
    """Vérifie que get_system_status collecte correctement l'état du système."""
    # Scénario 1: Tout est présent
    orchestrator.klipper_dir.mkdir(parents=True)
    (orchestrator.klipper_dir / "out").mkdir()
    orchestrator.firmware_path.touch()
    mock_flash_manager = MagicMock()
    mock_flash_manager.detect_serial_devices.return_value = ["/dev/ttyACM0"]
    mock_flash_manager_class.return_value = mock_flash_manager

    status1 = orchestrator.get_system_status()
    assert status1.klipper_repo_exists is True
    assert status1.firmware_exists is True
    assert status1.detected_devices == ["/dev/ttyACM0"]

    # Scénario 2: Firmware manquant
    orchestrator.firmware_path.unlink()
    status2 = orchestrator.get_system_status()
    assert status2.firmware_exists is False

    # Scénario 3: Dépôt manquant (implique firmware manquant)
    import shutil
    shutil.rmtree(orchestrator.klipper_dir)
    status3 = orchestrator.get_system_status()
    assert status3.klipper_repo_exists is False
    assert status3.firmware_exists is False

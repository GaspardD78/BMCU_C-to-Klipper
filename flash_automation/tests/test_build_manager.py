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

"""Tests pour le module BuildManager."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

from flash_automation.build_manager import BuildManager, BuildManagerError

@pytest.fixture
def manager(tmp_path: Path) -> BuildManager:
    """Crée une instance du BuildManager avec une configuration factice."""
    config_data = '{"klipper": {"repository_url": "dummy_url", "git_ref": "dummy_ref"}}'
    (tmp_path / "config.json").write_text(config_data)
    bm = BuildManager(tmp_path)
    # On simule l'existence du dépôt klipper
    bm.klipper_dir.mkdir(parents=True)
    return bm

@patch.object(BuildManager, "_run_interactive_command")
@patch.object(BuildManager, "ensure_klipper_repo")
def test_launch_menuconfig(mock_ensure_repo, mock_run_interactive, manager: BuildManager):
    """Vérifie que menuconfig est lancé correctement."""
    manager.launch_menuconfig()
    mock_ensure_repo.assert_called_once()
    mock_run_interactive.assert_called_once_with(["make", "menuconfig"], cwd=manager.klipper_dir)

@patch.object(BuildManager, "ensure_klipper_repo")
def test_save_config(mock_ensure_repo, manager: BuildManager):
    """Vérifie la sauvegarde d'un fichier .config."""
    # Crée un faux fichier .config
    config_content = "CONFIG_TEST=y"
    (manager.klipper_dir / ".config").write_text(config_content)

    manager.save_config("test_config")

    saved_file = manager.base_dir / "configs/test_config.config"
    assert saved_file.exists()
    assert saved_file.read_text() == config_content

@patch.object(BuildManager, "ensure_klipper_repo")
def test_load_config(mock_ensure_repo, manager: BuildManager):
    """Vérifie le chargement d'un fichier de configuration."""
    # Crée un faux fichier de config sauvegardé
    config_content = "CONFIG_LOAD=y"
    saved_dir = manager.base_dir / "configs"
    saved_dir.mkdir()
    (saved_dir / "test_config.config").write_text(config_content)

    manager.load_config("test_config")

    mock_ensure_repo.assert_called_once()
    loaded_file = manager.klipper_dir / ".config"
    assert loaded_file.exists()
    assert loaded_file.read_text() == config_content

@patch.object(BuildManager, "_run_command")
@patch.object(BuildManager, "ensure_klipper_repo")
@patch("shutil.copy")
def test_compile_firmware_with_default_config(mock_copy, mock_ensure_repo, mock_run, manager: BuildManager):
    """Vérifie la compilation avec la configuration par défaut."""
    (manager.base_dir / "klipper.config").touch()

    def fake_make(*args, **kwargs):
        (manager.klipper_dir / "out").mkdir(exist_ok=True)
        (manager.klipper_dir / "out/klipper.bin").touch()
    mock_run.side_effect = fake_make

    manager.compile_firmware(use_default_config=True)

    mock_ensure_repo.assert_called_once()
    mock_copy.assert_called_once()
    expected_calls = [
        call(["make", "olddefconfig"], cwd=manager.klipper_dir),
        call(["make"], cwd=manager.klipper_dir)
    ]
    mock_run.assert_has_calls(expected_calls)

@patch.object(BuildManager, "_run_command")
@patch.object(BuildManager, "ensure_klipper_repo")
@patch("shutil.copy")
def test_compile_firmware_without_default_config(mock_copy, mock_ensure_repo, mock_run, manager: BuildManager):
    """Vérifie que la config par défaut n'est pas copiée si demandé."""
    def fake_make(*args, **kwargs):
        (manager.klipper_dir / "out").mkdir(exist_ok=True)
        (manager.klipper_dir / "out/klipper.bin").touch()
    mock_run.side_effect = fake_make

    manager.compile_firmware(use_default_config=False)

    mock_ensure_repo.assert_called_once()
    mock_copy.assert_not_called()
    expected_calls = [
        call(["make", "olddefconfig"], cwd=manager.klipper_dir),
        call(["make"], cwd=manager.klipper_dir)
    ]
    mock_run.assert_has_calls(expected_calls)

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

"""Tests d'intégration pour l'interface utilisateur bmcu_tool.py."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest

from flash_automation import bmcu_tool


@patch("flash_automation.bmcu_tool.Orchestrator")
@patch("flash_automation.bmcu_tool.find_default_firmware")
def test_menu_build_flow(mock_find_firmware, mock_orchestrator_class, monkeypatch, capsys):
    """
    Simule un utilisateur qui choisit l'option 'Compiler',
    confirme la recompilation, puis quitte.
    """
    # Arrange
    mock_orchestrator = mock_orchestrator_class.return_value
    mock_orchestrator.run_build.return_value = True
    mock_orchestrator.get_system_dependencies.return_value = ("apt", [], [])
    mock_orchestrator.get_python_dependencies.return_value = ([], [])

    # Simule un firmware existant
    mock_firmware_path = MagicMock()
    mock_firmware_path.name = "klipper.bin"
    mock_find_firmware.return_value = mock_firmware_path

    # Simule les entrées utilisateur : '3' (Build), 'o' (oui), '5' (Quitter)
    user_input = "3\no\n5\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(user_input))

    # Act
    bmcu_tool.main([])

    # Assert
    captured = capsys.readouterr()
    assert "Compiler le firmware" in captured.out
    assert "Un firmware existe (klipper.bin)" in captured.out
    assert "Compilation du firmware Klipper..." in captured.out
    mock_orchestrator.run_build.assert_called_once()


@patch("flash_automation.bmcu_tool.FlashManager")
@patch("flash_automation.bmcu_tool.Orchestrator")
@patch("flash_automation.bmcu_tool.find_default_firmware")
def test_menu_flash_flow(mock_find_firmware, mock_orchestrator_class, mock_flash_manager_class, monkeypatch, capsys):
    """
    Simule un utilisateur qui choisit l'option 'Flasher',
    accepte le firmware détecté, sélectionne un port série et confirme.
    """
    # Arrange
    mock_orchestrator = mock_orchestrator_class.return_value
    mock_orchestrator.run_flash.return_value = True
    mock_orchestrator.get_system_dependencies.return_value = ("apt", [], [])
    mock_orchestrator.get_python_dependencies.return_value = ([], [])

    mock_flash_manager = mock_flash_manager_class.return_value
    mock_flash_manager.detect_serial_devices.return_value = ["/dev/ttyACM0"]

    mock_firmware_path = MagicMock()
    mock_firmware_path.__str__.return_value = "/path/to/klipper.bin"
    mock_find_firmware.return_value = mock_firmware_path

    # Simule les entrées : '4' (Flash), 'o' (oui), '1' (port), 'o' (confirmer), '5' (quitter)
    user_input = "4\no\n1\no\n5\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(user_input))

    # Act
    bmcu_tool.main([])

    # Assert
    captured = capsys.readouterr()
    assert "Flasher le firmware (assistant)" in captured.out
    assert "Périphériques USB détectés" in captured.out
    assert "/dev/ttyACM0" in captured.out
    assert "Flashage du firmware..." in captured.out
    mock_orchestrator.run_flash.assert_called_once()

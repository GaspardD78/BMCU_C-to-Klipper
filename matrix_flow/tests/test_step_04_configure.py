# -*- coding: utf-8 -*-

"""Tests pour l'étape 4 : Aide à la configuration."""

import re
from unittest.mock import patch
import pytest

from matrix_flow.step_04_configure import ConfigHelper

def strip_ansi(text: str) -> str:
    """Supprime les codes d'échappement ANSI d'une chaîne."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def test_configuration_generation_with_device_found(mocker, capsys):
    """Vérifie que le bloc de configuration est correct lorsqu'un port est trouvé."""
    # Simule la découverte d'un port série
    mocker.patch("glob.glob", return_value=["/dev/serial/by-id/usb-Klipper_123"])

    # Exécution
    helper = ConfigHelper()
    helper.run()

    # Vérification de la sortie nettoyée
    captured = capsys.readouterr()
    clean_output = strip_ansi(captured.out)
    assert "[mcu bmcu]" in clean_output
    assert "serial: /dev/serial/by-id/usb-Klipper_123" in clean_output


def test_configuration_generation_with_device_not_found(mocker, capsys):
    """Vérifie que le bloc de configuration contient un placeholder si aucun port n'est trouvé."""
    # Simule l'échec de la détection de port
    mocker.patch("glob.glob", return_value=[])

    # Exécution
    helper = ConfigHelper()
    helper.run()

    # Vérification de la sortie nettoyée
    captured = capsys.readouterr()
    clean_output = strip_ansi(captured.out)
    assert "[mcu bmcu]" in clean_output
    assert "serial: /dev/tty...." in clean_output

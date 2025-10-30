import sys
from pathlib import Path

import pytest

# S'assurer que le répertoire `flash_automation` est dans le path pour l'import
ROOT_DIR = Path(__file__).resolve().parents[2]
FLASH_AUTOMATION_DIR = ROOT_DIR / "flash_automation"
if str(FLASH_AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(FLASH_AUTOMATION_DIR))

# Importer les classes et fonctions nécessaires depuis bmcu_tool
from bmcu_tool import (
    SystemInfo,
    QuickProfile,
    EnvironmentDefaults,
    detect_environment_defaults,
    apply_environment_defaults,
    build_home_summary,
    find_default_firmware,
)


def test_detect_environment_defaults_raspberry_pi():
    """Vérifie la détection d'un environnement Raspberry Pi."""
    info = SystemInfo(
        model="Raspberry Pi 4 Model B Rev 1.2",
        os_release={"ID": "raspbian", "ID_LIKE": "debian"},
        machine="armv7l",
    )
    defaults = detect_environment_defaults(info)
    assert defaults.label == "Raspberry Pi"
    assert defaults.host == "localhost"
    assert defaults.user == "pi"


@pytest.mark.parametrize(
    "initial_host,expected_host",
    [("", "localhost"), ("10.0.0.2", "10.0.0.2")],
)
def test_apply_environment_defaults_respects_existing_values(initial_host, expected_host):
    """Vérifie que les valeurs existantes du profil ne sont pas écrasées."""
    profile = QuickProfile(
        gateway_host=initial_host,
        gateway_user="",
        remote_firmware_path="",
        serial_device="",
        log_root="",
    )
    defaults = EnvironmentDefaults(
        label="Bambu Lab CB2",
        host="localhost",
        user="bambu",
        remote_path="/tmp/klipper_firmware.bin",
        serial_device="/dev/serial/by-id/usb-wch",
        log_root="logs",
    )

    apply_environment_defaults(profile, defaults)

    assert profile.gateway_host == expected_host
    assert profile.gateway_user == "bambu"
    assert profile.remote_firmware_path == "/tmp/klipper_firmware.bin"
    assert profile.serial_device == "/dev/serial/by-id/usb-wch"
    assert profile.log_root == "logs"


def test_home_summary_includes_environment_snapshot(tmp_path, monkeypatch):
    """Vérifie que le résumé d'accueil affiche les bonnes informations."""
    firmware_path = tmp_path / "klipper.bin"
    firmware_path.write_text("binary")

    # Simuler la détection du firmware
    monkeypatch.setattr("bmcu_tool.find_default_firmware", lambda: firmware_path)

    profile = QuickProfile(gateway_host="localhost", gateway_user="pi")
    defaults = EnvironmentDefaults(label="Raspberry Pi", host="localhost", user="pi")

    summary = build_home_summary(profile, defaults)

    assert "Environnement détecté : Raspberry Pi" in summary
    assert str(firmware_path) in summary

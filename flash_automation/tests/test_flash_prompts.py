import io
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flash_automation import flash


def test_detect_environment_defaults_raspberry_pi():
    info = flash.SystemInfo(
        model="Raspberry Pi 4 Model B Rev 1.2",
        os_release={"ID": "raspbian", "ID_LIKE": "debian"},
        machine="armv7l",
    )

    defaults = flash.detect_environment_defaults(info)

    assert defaults.label == "Raspberry Pi"
    assert defaults.host == "localhost"
    assert defaults.user == "pi"


def test_prompt_timer_emits_help_message():
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        with flash.PromptTimer("Question : ", "Saisissez les informations requises.", interval=0.05):
            time.sleep(0.12)

    output = buffer.getvalue()
    assert "Saisissez les informations requises." in output


@pytest.mark.parametrize(
    "initial_host,expected_host",
    [("", "localhost"), ("10.0.0.2", "10.0.0.2")],
)
def test_apply_environment_defaults_respects_existing_values(initial_host, expected_host):
    profile = flash.QuickProfile(
        gateway_host=initial_host,
        gateway_user="",
        remote_firmware_path="",
        serial_device="",
        log_root="",
    )
    defaults = flash.EnvironmentDefaults(
        label="Bambu Lab CB2",
        host="localhost",
        user="bambu",
        remote_path="/tmp/klipper_firmware.bin",
        serial_device="/dev/serial/by-id/usb-wch",
        log_root="logs",
    )

    flash.apply_environment_defaults(profile, defaults)

    assert profile.gateway_host == expected_host
    assert profile.gateway_user == "bambu"
    assert profile.remote_firmware_path == "/tmp/klipper_firmware.bin"
    assert profile.serial_device == "/dev/serial/by-id/usb-wch"
    assert profile.log_root == "logs"


def test_home_summary_includes_environment_snapshot(tmp_path, monkeypatch):
    firmware_path = tmp_path / "klipper.bin"
    firmware_path.write_text("binary")

    monkeypatch.setattr(flash, "find_default_firmware", lambda: firmware_path)

    profile = flash.QuickProfile(gateway_host="localhost", gateway_user="pi")
    defaults = flash.EnvironmentDefaults(label="Raspberry Pi", host="localhost", user="pi")

    summary = flash.build_home_summary(profile, defaults)

    assert "Environnement détecté : Raspberry Pi" in summary
    assert str(firmware_path) in summary

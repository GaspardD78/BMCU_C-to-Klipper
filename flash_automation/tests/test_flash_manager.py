from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from flash_automation.flash_manager import FlashManager


@pytest.fixture
def manager(tmp_path: Path) -> FlashManager:
    """Fixture to create a FlashManager instance with a temporary base directory."""
    return FlashManager(tmp_path)


def test_detect_serial_devices(manager: FlashManager):
    """Verify that serial device detection correctly uses glob patterns."""
    with patch("glob.glob") as mock_glob:
        mock_glob.side_effect = [
            ["/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"],
            ["/dev/ttyUSB0", "/dev/ttyUSB1"],
            [], # ttyACM
            [], # ttyAMA
            [], # ttyS
            [], # ttyCH
        ]
        devices = manager.detect_serial_devices()
        assert devices == [
            "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0",
            "/dev/ttyUSB0",
            "/dev/ttyUSB1",
        ]
        assert mock_glob.call_count == 6


def test_flash_serial_success(manager: FlashManager):
    """Test the happy path for serial flashing."""
    firmware_path = manager.base_dir / "klipper.bin"
    firmware_path.touch()

    # Create the mock flash script
    flash_script_path = manager.base_dir / ".cache/scripts/flash_usb.py"
    flash_script_path.parent.mkdir(parents=True)
    flash_script_path.touch()

    device = "/dev/ttyUSB0"

    with patch("subprocess.run") as mock_run:
        manager.flash_serial(firmware_path, device)
        mock_run.assert_called_once_with(
            ["python3", str(flash_script_path), "-d", device, "-f", str(firmware_path)],
            check=True,
        )


def test_flash_serial_no_device_raises_error(manager: FlashManager):
    """Verify that flashing without a device raises a ValueError."""
    firmware_path = manager.base_dir / "klipper.bin"
    firmware_path.touch()

    with pytest.raises(ValueError, match="Un périphérique série est requis"):
        manager.flash_serial(firmware_path, None)


def test_flash_serial_missing_script_raises_error(manager: FlashManager):
    """Verify that a missing flash_usb.py script raises FileNotFoundError."""
    firmware_path = manager.base_dir / "klipper.bin"
    firmware_path.touch()
    device = "/dev/ttyUSB0"

    with pytest.raises(FileNotFoundError, match="Le script de flash .* est introuvable"):
        manager.flash_serial(firmware_path, device)


def test_flash_serial_subprocess_failure_propagates(manager: FlashManager):
    """Check that a subprocess failure is propagated."""
    firmware_path = manager.base_dir / "klipper.bin"
    firmware_path.touch()

    flash_script_path = manager.base_dir / ".cache/scripts/flash_usb.py"
    flash_script_path.parent.mkdir(parents=True)
    flash_script_path.touch()

    device = "/dev/ttyUSB0"

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")
        with pytest.raises(subprocess.CalledProcessError):
            manager.flash_serial(firmware_path, device)

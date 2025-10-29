import hashlib
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# @pytest.mark.skip(reason="These tests are for the deprecated flash.py and need to be adapted for bmcu_tool.py")
# from flash_automation import flash


@pytest.mark.skip(reason="Test for deprecated flash.py")
def test_compute_sha256_matches_python_hashlib(tmp_path):
    firmware = tmp_path / "klipper.bin"
    payload = b"KlipperFirmware"
    firmware.write_bytes(payload)

    assert flash.compute_sha256(firmware) == hashlib.sha256(payload).hexdigest()


@pytest.mark.skip(reason="Test for deprecated flash.py")
def test_read_checksum_file_accepts_sha256sum_format(tmp_path):
    checksum = "a" * 64
    checksum_file = tmp_path / "klipper.sha256"
    checksum_file.write_text(f"{checksum}  klipper.bin\n")

    assert flash.read_checksum_file(checksum_file) == checksum


@pytest.mark.skip(reason="Test for deprecated flash.py")
def test_verify_firmware_checksum_raises_on_mismatch(tmp_path):
    firmware = tmp_path / "klipper.bin"
    firmware.write_bytes(b"flash")
    checksum_file = tmp_path / "klipper.sha256"
    checksum_file.write_text("0" * 64)

    with pytest.raises(flash.ChecksumMismatchError):
        flash.verify_firmware_checksum(firmware, checksum_file=checksum_file)


@pytest.mark.skip(reason="Test for deprecated flash.py")
def test_verify_firmware_checksum_prefers_cli_value(tmp_path):
    firmware = tmp_path / "klipper.bin"
    payload = b"payload"
    firmware.write_bytes(payload)
    checksum_file = tmp_path / "klipper.sha256"
    checksum_file.write_text("0" * 64)

    explicit = hashlib.sha256(payload).hexdigest()
    computed, expected, source = flash.verify_firmware_checksum(
        firmware,
        explicit_checksum=explicit,
        checksum_file=checksum_file,
    )

    assert computed == explicit
    assert expected == explicit
    assert source == "option --firmware-sha256"

import hashlib
import sys
from pathlib import Path

import pytest

# S'assurer que le répertoire `flash_automation` est dans le path pour l'import
ROOT_DIR = Path(__file__).resolve().parents[2]
FLASH_AUTOMATION_DIR = ROOT_DIR / "flash_automation"
if str(FLASH_AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(FLASH_AUTOMATION_DIR))

# Importer les fonctions directement depuis bmcu_tool
from bmcu_tool import (
    compute_sha256,
    read_checksum_file,
    verify_firmware_checksum,
    ChecksumMismatchError,
)

def test_compute_sha256_matches_python_hashlib(tmp_path):
    """Vérifie que notre calcul SHA-256 correspond à celui de hashlib."""
    firmware = tmp_path / "klipper.bin"
    payload = b"KlipperFirmware"
    firmware.write_bytes(payload)

    assert compute_sha256(firmware) == hashlib.sha256(payload).hexdigest()


def test_read_checksum_file_accepts_sha256sum_format(tmp_path):
    """Vérifie que le parsing du fichier de checksum est correct."""
    checksum = "a" * 64
    checksum_file = tmp_path / "klipper.sha256"
    checksum_file.write_text(f"{checksum}  klipper.bin\n")

    assert read_checksum_file(checksum_file) == checksum


def test_verify_firmware_checksum_raises_on_mismatch(tmp_path):
    """Vérifie qu'une erreur est levée si les checksums ne correspondent pas."""
    firmware = tmp_path / "klipper.bin"
    firmware.write_bytes(b"flash")
    checksum_file = tmp_path / "klipper.sha256"
    checksum_file.write_text("0" * 64)

    with pytest.raises(ChecksumMismatchError):
        verify_firmware_checksum(firmware, checksum_file=checksum_file)


def test_verify_firmware_checksum_prefers_explicit_value(tmp_path):
    """Vérifie que le checksum explicite a la priorité sur celui du fichier."""
    firmware = tmp_path / "klipper.bin"
    payload = b"payload"
    firmware.write_bytes(payload)
    checksum_file = tmp_path / "klipper.sha256"
    checksum_file.write_text("0" * 64)  # Contenu invalide pour forcer la vérification

    explicit = hashlib.sha256(payload).hexdigest()
    computed, expected, source = verify_firmware_checksum(
        firmware,
        explicit_checksum=explicit,
        checksum_file=checksum_file,
    )

    assert computed == explicit
    assert expected == explicit
    assert source == "option --firmware-sha256"

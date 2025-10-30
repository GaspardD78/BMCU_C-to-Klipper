# Fichier de test unitaire pour addon/bmcu.py
# Copyright (C) 2024 Gaspard Douté
#
# Ce programme est sous licence GNU GPL v3.

import sys
from pathlib import Path
import pytest

# Ajouter la racine du projet au `sys.path` pour permettre l'import de `addon.bmcu`
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Les fonctions et classes à tester
from addon.bmcu import crc8_dvb_s2, crc16_bambu, BambuBusCodec, PREAMBLE

# --- Vecteurs de test pour les fonctions de checksum ---

# Ces valeurs sont calculées sur la base des implémentations actuelles dans
# bmcu.py. Elles servent de tests de non-régression.

def test_crc8_dvb_s2_empty_input():
    """Vérifie que le CRC8 d'une entrée vide retourne la valeur initiale."""
    assert crc8_dvb_s2(b'') == 0x66

def test_crc8_dvb_s2_simple_vector():
    """Teste le CRC8 avec un vecteur simple."""
    data = b'123456789'
    # Valeur actuelle produite par l'implémentation
    expected_crc = 0x79
    assert crc8_dvb_s2(data) == expected_crc

def test_crc8_dvb_s2_all_zeros():
    """Teste le CRC8 avec une séquence de zéros."""
    data = b'\x00' * 8
    # Valeur actuelle produite par l'implémentation
    expected_crc = 0x6F
    assert crc8_dvb_s2(data) == expected_crc


def test_crc16_bambu_empty_input():
    """Vérifie que le CRC16 d'une entrée vide retourne la valeur initiale."""
    assert crc16_bambu(b'') == 0x913D

def test_crc16_bambu_simple_vector():
    """Teste le CRC16 avec un vecteur simple."""
    data = b'123456789'
    # Valeur actuelle produite par l'implémentation
    expected_crc = 0x2614
    assert crc16_bambu(data) == expected_crc

def test_crc16_bambu_all_zeros():
    """Teste le CRC16 avec une séquence de zéros."""
    data = b'\x00' * 8
    # Valeur actuelle produite par l'implémentation
    expected_crc = 0x3461
    assert crc16_bambu(data) == expected_crc


# --- Tests pour l'encodeur/décodeur BambuBusCodec ---

@pytest.fixture
def codec():
    """Fournit une instance de base de BambuBusCodec pour les tests."""
    return BambuBusCodec(src_addr=0x01, dst_addr=0x11)

def test_build_packet_structure_short(codec):
    """Vérifie la structure de base d'un paquet court."""
    command = 0x01  # PING
    payload = b'\xAA\xBB'
    packet = codec.build_packet(command, payload)

    # 1. Vérifier le préambule
    assert packet.startswith(PREAMBLE)

    # 2. Vérifier que la longueur est correcte (paquet court)
    # Longueur du corps = 1 (longueur) + 4 (en-tête) + 1 (crc8) + 2 (payload) = 8
    assert packet[2] == 8 + len(payload)

    # 3. Vérifier que les checksums sont présents
    header_crc = packet[2 + 1 + 4]
    crc16_bytes = packet[-2:]

    # 4. Re-calculer les checksums pour valider l'intégrité
    header_part = packet[:2 + 1 + 4]
    full_frame_part = packet[:-2]

    assert crc8_dvb_s2(header_part) == header_crc
    expected_crc16 = crc16_bambu(full_frame_part)
    actual_crc16 = int.from_bytes(crc16_bytes, 'little')
    assert actual_crc16 == expected_crc16

def test_build_packet_structure_long(codec):
    """Vérifie la structure de base d'un paquet long."""
    command = 0x02  # HOME
    # Un payload suffisamment long pour forcer un paquet long
    payload = b'\xDE\xAD\xBE\xEF' * 20
    packet = codec.build_packet(command, payload)

    # 1. Vérifier le préambule et le marqueur de paquet long
    assert packet.startswith(PREAMBLE)
    assert packet[2] & 0x80  # Le bit de paquet long doit être à 1

    # 2. Vérifier que les checksums sont corrects
    header_crc_idx = 2 + 2 + 4 # 2 (préambule) + 2 (longueur) + 4 (en-tête)
    header_crc = packet[header_crc_idx]
    crc16_bytes = packet[-2:]

    header_part = packet[:header_crc_idx]
    full_frame_part = packet[:-2]

    assert crc8_dvb_s2(header_part) == header_crc
    expected_crc16 = crc16_bambu(full_frame_part)
    actual_crc16 = int.from_bytes(crc16_bytes, 'little')
    assert actual_crc16 == expected_crc16

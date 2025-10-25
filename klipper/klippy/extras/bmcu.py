"""Pilote Klipper pour le contrôleur BMCU-C sur le bus « bambubus ».

Cette implémentation reconstruit le protocole décrit par le firmware BMCU-C
v0020 : encapsulation des trames courtes/longues, CRC8/CRC16, numérotation de
séquence et lecture asynchrone des réponses RS-485.  Elle expose des commandes
G-code (`BMCU_SELECT_GATE`, `BMCU_HOME`, `BMCU_CHECK_GATE`) et publie un statut
consultable via `GET_STATUS BMCU`.
"""

from __future__ import annotations

import collections
import logging
import threading
from dataclasses import dataclass
from typing import Deque, Iterable, List, Optional

import serial
from serial import SerialException


LOG = logging.getLogger(__name__)

# En-tête commun à toutes les trames bambubus
PREAMBLE = bytes([0x3D, 0xC5])
# Limites extraites des tables de configuration du firmware (sections short/long)
SHORT_MAX_BODY = 0x3F
LONG_MAX_BODY = 0x3FFF

# Commandes identifiées dans le firmware de référence
CMD_PING = 0x01
CMD_HOME = 0x02
CMD_SELECT_GATE = 0x03
CMD_QUERY_STATUS = 0x04

# Réponses retournées par le BMCU
RSP_ACK_MASK = 0x80
RSP_STATUS = 0x90
RSP_ERROR = 0x91


# Implémentation du checksum CRC8 DVB-S2
# Référence : table utilisée dans les routines bambubus du firmware
# (polynôme 0x39, init 0x66).
def crc8_dvb_s2(data: Iterable[int]) -> int:
    crc = 0x66
    poly = 0x39
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ poly
            else:
                crc <<= 1
    return crc & 0xFF


# Implémentation du checksum CRC16 spécifique bambubus
# Référence : routine "crc16_add" du firmware (polynôme 0x1021, init 0x913D).
def crc16_bambu(data: Iterable[int]) -> int:
    crc = 0x913D
    poly = 0x1021
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ poly
            else:
                crc <<= 1
    return crc & 0xFFFF


@dataclass
class BambuPacket:
    """Représente une trame bambubus décodée."""

    sequence: int
    src: int
    dst: int
    command: int
    payload: bytes
    is_long: bool


class BambuBusCodec:
    """Encodeur/décodeur respectant le format bambubus des firmwares v0020."""

    def __init__(self, src_addr: int, dst_addr: int) -> None:
        self.src_addr = src_addr & 0xFF
        self.dst_addr = dst_addr & 0xFF
        self._sequence = 0

    @staticmethod
    def _encode_length(payload_len: int, long_frame: bool) -> bytearray:
        if long_frame:
            body_len = payload_len + 9
            if body_len > LONG_MAX_BODY:
                raise ValueError("payload trop long pour un paquet bambubus long")
            high = (body_len >> 8) & 0x3F
            return bytearray([0x80 | high, body_len & 0xFF])
        body_len = payload_len + 8
        if body_len > SHORT_MAX_BODY:
            raise ValueError("payload trop long pour un paquet bambubus court")
        return bytearray([body_len & 0xFF])

    @staticmethod
    def _decode_length(buffer: bytes, offset: int) -> tuple[int, int, bool]:
        length_byte = buffer[offset]
        if length_byte & 0x80:
            if offset + 1 >= len(buffer):
                raise ValueError("champ de longueur long tronqué")
            body_len = ((length_byte & 0x3F) << 8) | buffer[offset + 1]
            if body_len < 9:
                raise ValueError("longueur longue invalide")
            return body_len, 2, True
        body_len = length_byte
        if body_len < 8:
            raise ValueError("longueur courte invalide")
        return body_len, 1, False

    def build_packet(self, command: int, payload: bytes = b"", *, dst_addr: Optional[int] = None) -> bytes:
        payload = payload or b""
        long_frame = len(payload) + 8 > SHORT_MAX_BODY
        length_field = self._encode_length(len(payload), long_frame)

        frame = bytearray(PREAMBLE)
        frame.extend(length_field)
        sequence = self._sequence
        self._sequence = (self._sequence + 1) & 0xFF
        frame.append(sequence)
        frame.append(self.src_addr)
        frame.append((dst_addr if dst_addr is not None else self.dst_addr) & 0xFF)
        frame.append(command & 0xFF)

        header_crc = crc8_dvb_s2(frame)
        frame.append(header_crc)
        frame.extend(payload)

        crc16 = crc16_bambu(frame)
        frame.extend([crc16 & 0xFF, (crc16 >> 8) & 0xFF])
        return bytes(frame)

    @staticmethod
    def extract_packets(buffer: Deque[int]) -> List[BambuPacket]:
        packets: List[BambuPacket] = []
        temp = bytearray(buffer)
        start = 0
        while True:
            sync = temp.find(PREAMBLE, start)
            if sync == -1:
                break
            if sync + 3 > len(temp):
                break
            try:
                body_len, length_size, is_long = BambuBusCodec._decode_length(temp, sync + 2)
            except ValueError:
                start = sync + 1
                continue
            frame_len = 2 + body_len
            end = sync + frame_len
            if end > len(temp):
                break
            frame = temp[sync:end]
            header_crc_idx = 2 + length_size + 4
            header_crc = frame[header_crc_idx]
            header_without_crc = frame[:header_crc_idx]
            if crc8_dvb_s2(header_without_crc) != header_crc:
                LOG.debug("Trame rejetée (CRC8 invalide): %s", frame.hex())
                start = sync + 1
                continue
            payload_end = frame_len - 2
            payload = frame[header_crc_idx + 1 : payload_end]
            crc16_received = frame[payload_end] | (frame[payload_end + 1] << 8)
            if crc16_bambu(frame[:payload_end]) != crc16_received:
                LOG.debug("Trame rejetée (CRC16 invalide): %s", frame.hex())
                start = sync + 1
                continue
            seq_idx = 2 + length_size
            sequence = frame[seq_idx]
            src = frame[seq_idx + 1]
            dst = frame[seq_idx + 2]
            command = frame[seq_idx + 3]
            packets.append(BambuPacket(sequence, src, dst, command, bytes(payload), is_long))
            start = end
        consumed = start
        for _ in range(consumed):
            buffer.popleft()
        return packets


class BMCU:
    """Pilote haut-niveau pour le BMCU-C."""

    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')

        serial_port = config.get('serial')
        baud_rate = config.getint('baud', 1250000)
        self.src_addr = config.getint('host_address', 0x01)
        self.dst_addr = config.getint('device_address', 0x11)
        self.poll_interval = config.getfloat('poll_interval', 0.02)

        try:
            self.serial_conn = serial.Serial(
                serial_port,
                baud_rate,
                timeout=0,
                write_timeout=1,
                parity=serial.PARITY_EVEN,
                bytesize=serial.EIGHTBITS,
                stopbits=serial.STOPBITS_ONE,
            )
        except SerialException as exc:
            raise config.error("Impossible d'ouvrir le port série BMCU: %s" % (exc,))

        self.codec = BambuBusCodec(self.src_addr, self.dst_addr)
        self._rx_buffer: Deque[int] = collections.deque()
        self._write_lock = threading.Lock()
        self._read_timer = None
        self._status_timer = None
        self._running = True

        self._last_contact = 0.0
        self._state = {
            'online': False,
            'active_gate': None,
            'doors': [False, False, False, False],
            'filament_present': [False, False, False, False],
            'error_code': 0,
            'error_history': [],
        }

        self.gcode.register_command("BMCU_SELECT_GATE", self.cmd_BMCU_SELECT_GATE, desc=self.cmd_BMCU_SELECT_GATE_help)
        self.gcode.register_command("BMCU_HOME", self.cmd_BMCU_HOME, desc=self.cmd_BMCU_HOME_help)
        self.gcode.register_command("BMCU_CHECK_GATE", self.cmd_BMCU_CHECK_GATE, desc=self.cmd_BMCU_CHECK_GATE_help)

        self.printer.register_event_handler('klippy:ready', self._handle_ready)
        self.printer.register_event_handler('klippy:shutdown', self._handle_shutdown)

        LOG.info("Module BMCU-C initialisé sur %s à %d bauds", serial_port, baud_rate)

    # ------------------------------------------------------------------
    # Boucles de communication

    def _handle_ready(self):
        if not self._read_timer:
            self._read_timer = self.reactor.register_timer(self._poll_serial, self.reactor.NOW)
        if not self._status_timer:
            self._status_timer = self.reactor.register_timer(self._poll_status, self.reactor.monotonic() + 0.5)
        self._send_command(CMD_PING)

    def _handle_shutdown(self):
        self._running = False
        if self._read_timer is not None:
            self.reactor.unregister_timer(self._read_timer)
            self._read_timer = None
        if self._status_timer is not None:
            self.reactor.unregister_timer(self._status_timer)
            self._status_timer = None
        try:
            self.serial_conn.close()
        except SerialException:
            pass

    def _poll_status(self, eventtime):
        if not self._running:
            return self.reactor.NEVER
        if self._state['online']:
            self._send_command(CMD_QUERY_STATUS)
        return eventtime + 0.5

    def _poll_serial(self, eventtime):
        if not self._running:
            return self.reactor.NEVER
        try:
            waiting = getattr(self.serial_conn, 'in_waiting', 0)
            chunk = self.serial_conn.read(waiting or 64)
        except SerialException as exc:
            LOG.error("Lecture série BMCU échouée: %s", exc)
            return eventtime + 1.0
        if chunk:
            self._ingest_data(chunk)
        return eventtime + self.poll_interval

    def _ingest_data(self, data: bytes) -> None:
        self._rx_buffer.extend(data)
        for packet in BambuBusCodec.extract_packets(self._rx_buffer):
            self._handle_packet(packet)

    # ------------------------------------------------------------------
    # Gestion des trames

    def _handle_packet(self, packet: BambuPacket) -> None:
        LOG.debug(
            "Trame reçue (seq=%d src=%02x dst=%02x cmd=%02x len=%d)",
            packet.sequence,
            packet.src,
            packet.dst,
            packet.command,
            len(packet.payload),
        )
        self._last_contact = self.reactor.monotonic()
        if packet.command & RSP_ACK_MASK and (packet.command & 0x7F) in (CMD_PING, CMD_HOME, CMD_SELECT_GATE, CMD_QUERY_STATUS):
            self._state['online'] = True
            return
        if packet.command == RSP_STATUS and len(packet.payload) >= 5:
            self._state['online'] = True
            doors_bits = packet.payload[0]
            filament_bits = packet.payload[1]
            active_gate = packet.payload[3]
            self._state['doors'] = [bool(doors_bits & (1 << i)) for i in range(4)]
            self._state['filament_present'] = [bool(filament_bits & (1 << i)) for i in range(4)]
            self._state['active_gate'] = active_gate if active_gate < 4 else None
            error_code = packet.payload[2]
            if error_code:
                self._state['error_code'] = error_code
                history = self._state['error_history']
                history.append({'code': error_code, 'sequence': packet.sequence})
                del history[:-10]
            else:
                self._state['error_code'] = 0
            LOG.debug("Statut BMCU mis à jour: %s", self._state)
            return
        if packet.command == RSP_ERROR and packet.payload:
            code = packet.payload[0]
            self._state['error_code'] = code
            self._state['error_history'].append({'code': code, 'sequence': packet.sequence})
            self._state['error_history'] = self._state['error_history'][-10:]
            LOG.warning("Erreur BMCU %02x (payload=%s)", code, packet.payload.hex())
            return
        LOG.debug("Trame non gérée: cmd=%02x payload=%s", packet.command, packet.payload.hex())

    # ------------------------------------------------------------------
    # Construction des trames sortantes

    def _send_command(self, command: int, payload: bytes = b"") -> None:
        frame = self.codec.build_packet(command, payload)
        LOG.debug("Envoi trame BMCU cmd=%02x: %s", command, frame.hex())
        with self._write_lock:
            try:
                self.serial_conn.write(frame)
                self.serial_conn.flush()
            except SerialException as exc:
                LOG.error("Échec d'écriture vers le BMCU: %s", exc)

    # ------------------------------------------------------------------
    # Interface G-code

    cmd_BMCU_SELECT_GATE_help = "Sélectionne une porte sur le BMCU-C"

    def cmd_BMCU_SELECT_GATE(self, gcmd):
        gate = gcmd.get_int('GATE', minval=0, maxval=3)
        payload = bytes([0x00, gate, 0x00])
        self._send_command(CMD_SELECT_GATE, payload)
        gcmd.respond_info(f"BMCU: sélection de la porte {gate}")

    cmd_BMCU_HOME_help = "Initialise le BMCU-C"

    def cmd_BMCU_HOME(self, gcmd):
        self._send_command(CMD_HOME)
        gcmd.respond_info("BMCU: commande de homing envoyée")

    cmd_BMCU_CHECK_GATE_help = "Demande l'état d'une porte"

    def cmd_BMCU_CHECK_GATE(self, gcmd):
        gate = gcmd.get_int('GATE', minval=0, maxval=3)
        payload = bytes([gate])
        self._send_command(CMD_QUERY_STATUS, payload)
        gcmd.respond_info(f"BMCU: requête de statut pour la porte {gate}")

    # ------------------------------------------------------------------
    # Statut Klipper

    def get_status(self, eventtime):
        return dict(self._state)


def load_config(config):
    return BMCU(config)

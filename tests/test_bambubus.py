import collections
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakeSerial:

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.port = kwargs.get('port', args[0] if args else None)
        self._baudrate = kwargs.get('baudrate', 9600)
        self.timeout = kwargs.get('timeout')
        self.write_timeout = kwargs.get('write_timeout')
        self.parity = kwargs.get('parity')
        self.bytesize = kwargs.get('bytesize')
        self.stopbits = kwargs.get('stopbits')
        self.written = []
        self._read_buffer = bytearray()
        self.in_waiting = 0
        self.closed = False

    def write(self, data):
        self.written.append(bytes(data))
        return len(data)

    def flush(self):
        return None

    def close(self):
        self.closed = True
        return None

    @property
    def baudrate(self):
        return self._baudrate

    @baudrate.setter
    def baudrate(self, value):
        self._baudrate = value

    def queue_read(self, payload: bytes):
        self._read_buffer.extend(payload)
        self.in_waiting = len(self._read_buffer)

    def read(self, size: int = 1):
        if size <= 0 or not self._read_buffer:
            self.in_waiting = len(self._read_buffer)
            return b""
        size = min(size, len(self._read_buffer))
        chunk = bytes(self._read_buffer[:size])
        del self._read_buffer[:size]
        self.in_waiting = len(self._read_buffer)
        return chunk


serial_stub = types.ModuleType('serial')
serial_stub.SerialException = RuntimeError
serial_stub.PARITY_EVEN = 'E'
serial_stub.EIGHTBITS = 8
serial_stub.STOPBITS_ONE = 1
serial_stub.Serial = FakeSerial
sys.modules.setdefault('serial', serial_stub)

from klipper.klippy.extras import bmcu


class StubReactor:
    NOW = 0.0
    NEVER = float("inf")

    def __init__(self):
        self._now = 0.0
        self.registered = []

    def register_timer(self, callback, when):
        handle = {"callback": callback, "when": when}
        self.registered.append(handle)
        return handle

    def unregister_timer(self, handle):
        try:
            self.registered.remove(handle)
        except ValueError:
            pass

    def monotonic(self):
        return self._now

    def advance(self, dt):
        self._now += dt


class StubGCode:
    def __init__(self):
        self.commands = {}
        self.infos = []

    def register_command(self, name, callback, desc=None):
        self.commands[name] = (callback, desc)

    def respond_info(self, message):
        self.infos.append(message)


class StubPrinter:
    def __init__(self):
        self._reactor = StubReactor()
        self._objects = {"gcode": StubGCode()}
        self.handlers = collections.defaultdict(list)

    def get_reactor(self):
        return self._reactor

    def lookup_object(self, name):
        return self._objects[name]

    def register_event_handler(self, event, handler):
        self.handlers[event].append(handler)


class StubConfig:
    def __init__(self, printer, **overrides):
        self._printer = printer
        self._values = {
            "serial": "/dev/ttyFAKE",
            "baud": 1250000,
            "host_address": 0x01,
            "device_address": 0x11,
            "poll_interval": 0.05,
        }
        self._values.update(overrides)

    def get_printer(self):
        return self._printer

    def get(self, key, default=None):
        return self._values.get(key, default)

    def getint(self, key, default=None, minval=None):
        if key in self._values:
            return int(self._values[key])
        if default is None:
            return default
        return int(default)

    def getfloat(self, key, default=None):
        if key in self._values:
            return float(self._values[key])
        if default is None:
            return None
        return float(default)

    def getboolean(self, key, default=None):
        if key in self._values:
            return bool(self._values[key])
        if default is None:
            return None
        return bool(default)

    def error(self, message):
        raise RuntimeError(message)


@pytest.fixture(autouse=True)
def patch_serial(monkeypatch):
    fake = FakeSerial
    monkeypatch.setattr(bmcu.serial, "Serial", fake)
    return fake


def test_build_short_packet():
    codec = bmcu.BambuBusCodec(0x01, 0x11)
    payload = bytes([0xAA, 0x55])
    frame = codec.build_packet(bmcu.CMD_PING, payload)
    assert frame.startswith(bmcu.PREAMBLE)
    # Longueur courte => premier octet de longueur sans bit 7
    assert frame[2] == len(frame) - 2
    header_crc = frame[2 + 1 + 4]
    assert header_crc == bmcu.crc8_dvb_s2(frame[:2 + 1 + 4])
    body = frame[:-2]
    crc16 = frame[-2] | (frame[-1] << 8)
    assert crc16 == bmcu.crc16_bambu(body)


def test_build_long_packet():
    codec = bmcu.BambuBusCodec(0x01, 0x11)
    payload = bytes(range(70))
    frame = codec.build_packet(bmcu.CMD_SELECT_GATE, payload)
    assert frame.startswith(bmcu.PREAMBLE)
    assert frame[2] & 0x80  # indicateur trame longue
    body_len = ((frame[2] & 0x3F) << 8) | frame[3]
    assert body_len == len(frame) - 2


def test_extract_packets_with_noise():
    codec = bmcu.BambuBusCodec(0x01, 0x11)
    frame = codec.build_packet(bmcu.CMD_PING, b"\x01")
    noise = bytearray(b"\x00\xff") + bytearray(frame) + bytearray(b"\x55")
    buffer = collections.deque(noise)
    packets = bmcu.BambuBusCodec.extract_packets(buffer)
    assert len(packets) == 1
    packet = packets[0]
    assert packet.command == bmcu.CMD_PING
    assert packet.payload == b"\x01"
    assert list(buffer) == [0x55]


def test_extract_packets_rejects_bad_crc():
    codec = bmcu.BambuBusCodec(0x01, 0x11)
    frame = bytearray(codec.build_packet(bmcu.CMD_HOME, b""))
    frame[-1] ^= 0xFF
    buffer = collections.deque(frame)
    packets = bmcu.BambuBusCodec.extract_packets(buffer)
    assert packets == []
    # Aucun octet consommé tant qu'une trame valide n'est pas détectée
    assert len(buffer) == len(frame) - 1


def test_status_update_from_packet(monkeypatch):
    printer = StubPrinter()
    config = StubConfig(printer)
    bmcu_instance = bmcu.BMCU(config)
    fake_serial = bmcu_instance.serial_conn
    assert isinstance(fake_serial, FakeSerial)

    payload = bytes([0b0101, 0b0011, 0x07, 0x02, 0x01])
    packet = bmcu.BambuPacket(3, 0x11, 0x01, bmcu.RSP_STATUS, payload, False)
    bmcu_instance._handle_packet(packet)

    status = bmcu_instance.get_status(0.0)
    assert status['online'] is True
    assert status['doors'] == [True, False, True, False]
    assert status['filament_present'] == [True, True, False, False]
    assert status['active_gate'] == 2
    assert status['error_code'] == 7
    assert status['error_history'][-1]['code'] == 7


def test_send_command_emits_frame(monkeypatch):
    printer = StubPrinter()
    config = StubConfig(printer)
    bmcu_instance = bmcu.BMCU(config)
    fake_serial = bmcu_instance.serial_conn
    assert isinstance(fake_serial, FakeSerial)

    payload = bytes([0x00, 0x02, 0x00])
    # Reproduire l'état de séquence pour comparer les trames
    reference_codec = bmcu.BambuBusCodec(bmcu_instance.src_addr, bmcu_instance.dst_addr)
    reference_codec._sequence = bmcu_instance.codec._sequence
    expected = reference_codec.build_packet(bmcu.CMD_SELECT_GATE, payload)

    bmcu_instance._send_command(bmcu.CMD_SELECT_GATE, payload)
    assert fake_serial.written[-1] == expected


def test_error_packet_updates_history():
    printer = StubPrinter()
    config = StubConfig(printer)
    bmcu_instance = bmcu.BMCU(config)

    error_packet = bmcu.BambuPacket(8, 0x11, 0x01, bmcu.RSP_ERROR, b"\x2A", False)
    bmcu_instance._handle_packet(error_packet)
    status = bmcu_instance.get_status(0.0)
    assert status['error_code'] == 0x2A
    assert status['error_history'][-1]['code'] == 0x2A


def test_init_errors_when_high_speed_unavailable(monkeypatch):
    class SlowSerial(FakeSerial):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Le pilote force silencieusement un débit plus faible
            self._baudrate = 115200

    monkeypatch.setattr(bmcu.serial, "Serial", SlowSerial)
    printer = StubPrinter()
    config = StubConfig(printer)

    with pytest.raises(RuntimeError) as exc:
        bmcu.BMCU(config)
    assert "PySerial n'a pas pu appliquer" in str(exc.value)


def test_set_custom_baudrate_is_used(monkeypatch):
    class CustomSerial(FakeSerial):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._baudrate = 115200

        def set_custom_baudrate(self, value):
            self._baudrate = value

    monkeypatch.setattr(bmcu.serial, "Serial", CustomSerial)
    printer = StubPrinter()
    config = StubConfig(printer, use_custom_baudrate=True)

    bmcu_instance = bmcu.BMCU(config)
    assert bmcu_instance.baud_rate == 1250000


def test_fallback_baudrate_applied(monkeypatch):
    class SlowSerial(FakeSerial):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._baudrate = 115200

    monkeypatch.setattr(bmcu.serial, "Serial", SlowSerial)
    printer = StubPrinter()
    config = StubConfig(printer, fallback_baud=115200)

    bmcu_instance = bmcu.BMCU(config)
    assert bmcu_instance.baud_rate == 115200

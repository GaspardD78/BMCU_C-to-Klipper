#!/usr/bin/env python3
"""Simple helper to exercise the BMCU-C RS-485 link."""

import argparse
import binascii
import sys
import time

MESSAGE_SYNC = 0x18


def build_frame(payload: bytes) -> bytes:
    """Build a raw Klipper frame containing only the payload."""
    return bytes([MESSAGE_SYNC]) + payload


def parse_hex_payload(value: str) -> bytes:
    value = value.strip().replace(" ", "")
    if not value:
        return b""
    try:
        return binascii.unhexlify(value)
    except binascii.Error as exc:  # pragma: no cover - user input
        raise argparse.ArgumentTypeError(f"invalid hex payload: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send a raw frame over the RS-485 UART to exercise the transceiver"
    )
    parser.add_argument("port", help="serial device path, e.g. /dev/ttyUSB0")
    parser.add_argument(
        "--baud",
        type=int,
        default=250000,
        help="baud rate used by the MCU (default: 250000)",
    )
    parser.add_argument(
        "--payload",
        type=parse_hex_payload,
        default=b"",
        help="hex encoded payload appended after the 0x18 sync byte",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="number of frames to send (default: 1)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.100,
        help="delay in seconds between frames (default: 0.1)",
    )
    parser.add_argument(
        "--read",
        type=int,
        default=64,
        help="number of bytes to read back after the last frame (default: 64)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=0.25,
        help="serial read timeout in seconds (default: 0.25)",
    )
    args = parser.parse_args()

    try:
        import serial  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - import guard
        print("pyserial is required: pip install pyserial", file=sys.stderr)
        raise SystemExit(1) from exc

    frame = build_frame(args.payload)
    print(f"Opening {args.port} at {args.baud} baud")
    with serial.Serial(args.port, args.baud, timeout=args.timeout) as ser:
        for idx in range(args.repeat):
            ser.write(frame)
            ser.flush()
            print(f"Sent frame {idx + 1}/{args.repeat}: {frame.hex()}")
            if idx + 1 < args.repeat and args.interval > 0:
                time.sleep(args.interval)
        if args.read:
            response = ser.read(args.read)
            if response:
                print(f"Received {len(response)} bytes: {response.hex()}")
            else:
                print("No response before timeout")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

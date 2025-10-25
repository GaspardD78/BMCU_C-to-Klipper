from pathlib import Path
from types import SimpleNamespace

import subprocess
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import setup_bmcu


def test_ensure_mcu_section_uses_serial_path():
    lines = ["# existing config\n"]
    serial = "/dev/serial/by-id/usb-test-bmcu"

    updated_lines, changed = setup_bmcu._ensure_mcu_section(lines, serial)

    assert changed is True
    assert any(line.strip() == f"serial: {serial}" for line in updated_lines)


def test_ensure_mcu_section_skips_serial_when_unknown():
    lines = ["# existing config\n"]

    updated_lines, changed = setup_bmcu._ensure_mcu_section(lines, None)

    assert changed is True
    assert not any(line.strip().startswith("serial:") for line in updated_lines)


def test_cli_list_firmware_does_not_require_paths():
    script_path = Path("scripts/setup_bmcu.py")

    result = subprocess.run(
        [sys.executable, str(script_path), "--list-firmware"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Firmware disponibles" in result.stdout


def test_main_fails_when_klipper_structure_is_invalid(tmp_path, monkeypatch, capsys):
    klipper_dir = tmp_path / "fake_klipper"
    klipper_dir.mkdir()
    config_dir = tmp_path / "klipper_config"
    config_dir.mkdir()

    args = SimpleNamespace(
        list_firmware=False,
        klipper_path=klipper_dir,
        config_path=config_dir,
        printer_config=None,
        serial_path=None,
        firmware_variant=None,
        firmware_dest=None,
        flash=False,
        flash_device=None,
        flash_baud=None,
        flash_extra_opts=None,
        no_backup=False,
        dry_run=False,
    )

    monkeypatch.setattr(setup_bmcu, "parse_args", lambda: args)

    exit_code = setup_bmcu.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Makefile" in captured.err
    assert "klippy/__init__.py" in captured.err


def test_firmware_alias_is_resolved_to_actual_path(tmp_path, monkeypatch):
    klipper_dir = tmp_path / "klipper"
    klipper_dir.mkdir()
    (klipper_dir / "Makefile").write_text("")
    klippy_dir = klipper_dir / "klippy"
    klippy_dir.mkdir()
    (klippy_dir / "__init__.py").write_text("")

    config_dir = tmp_path / "klipper_config"
    config_dir.mkdir()

    firmware_dir = tmp_path / "firmware"
    firmware_dir.mkdir()
    firmware_src = firmware_dir / "bmcu_special.bin"
    firmware_src.write_text("dummy firmware")

    firmware_dest = tmp_path / "output.bin"

    captured_calls = []

    def fake_copy(src: Path, dest: Path, dry_run: bool) -> None:
        captured_calls.append((src, dest, dry_run))

    args = SimpleNamespace(
        list_firmware=False,
        klipper_path=klipper_dir,
        config_path=config_dir,
        printer_config=None,
        serial_path=None,
        firmware_variant="bmcu_special",
        firmware_dest=firmware_dest,
        firmware_aliases={"bmcu_special": firmware_src},
        flash=False,
        flash_device=None,
        flash_baud=None,
        flash_extra_opts=None,
        no_backup=False,
        dry_run=False,
    )

    monkeypatch.setattr(setup_bmcu, "parse_args", lambda: args)
    monkeypatch.setattr(setup_bmcu, "_copy_file", fake_copy)

    exit_code = setup_bmcu.main()

    assert exit_code == 0
    expected = (
        firmware_src,
        firmware_dest.expanduser().resolve(),
        False,
    )
    assert expected in captured_calls


def test_repository_firmware_aliases_are_stable():
    aliases = setup_bmcu._build_firmware_aliases()
    expected = {
        "bmcu-c-0020-a-series-printer": "BMCU-C-0020-A Series Printer.bin",
        "bmcu-c-0020-p-x-series-ext-hub-a": "BMCU-C-0020-P-X-Series-Ext-Hub-A.bin",
        "bmcu-c-0020-p-x-series-ext-hub-b": "BMCU-C-0020-P-X-Series-Ext-Hub-B.bin",
        "bmcu-c-0020-p-x-series-ext-hub-c": "BMCU-C-0020-P-X-Series-Ext-Hub-C.bin",
        "bmcu-c-0020-p-x-series-ext-hub-d": "BMCU-C-0020-P-X-Series-Ext-Hub-D.bin",
        "bmcu-c-0020-p-x-series-int-hub-a": "BMCU-C-0020-P-X-Series-Int-Hub-A.bin",
        "bmcu-c-0020-p-x-series-int-hub-b": "BMCU-C-0020-P-X-Series-Int-Hub-B.bin",
        "bmcu-c-0020-p-x-series-int-hub-c": "BMCU-C-0020-P-X-Series-Int-Hub-C.bin",
        "bmcu-c-0020-p-x-series-int-hub-d": "BMCU-C-0020-P-X-Series-Int-Hub-D.bin",
    }
    assert {alias: path.name for alias, path in aliases.items()} == expected


def test_detect_serial_symlink_handles_multiple_candidates(tmp_path):
    base = tmp_path / "serial" / "by-id"
    base.mkdir(parents=True)

    # No matching entries
    assert setup_bmcu._detect_serial_symlink(base=base) is None

    match = base / "usb-klipper_ch32v203-if00"
    match.touch()

    assert setup_bmcu._detect_serial_symlink(base=base) == str(match)

    another = base / "wch-link-bridge"
    another.touch()

    with pytest.raises(RuntimeError) as excinfo:
        setup_bmcu._detect_serial_symlink(base=base)

    assert "--serial-path" in str(excinfo.value)


def test_main_requires_manual_serial_when_detection_fails(tmp_path, monkeypatch, capsys):
    klipper_dir = tmp_path / "klipper"
    klipper_dir.mkdir()
    (klipper_dir / "Makefile").write_text("")
    klippy_dir = klipper_dir / "klippy"
    klippy_dir.mkdir()
    (klippy_dir / "__init__.py").write_text("")

    config_dir = tmp_path / "klipper_config"
    config_dir.mkdir()

    printer_cfg = config_dir / "printer.cfg"
    printer_cfg.write_text("# printer configuration\n")

    args = SimpleNamespace(
        list_firmware=False,
        klipper_path=klipper_dir,
        config_path=config_dir,
        printer_config=printer_cfg,
        serial_path=None,
        firmware_variant=None,
        firmware_dest=None,
        firmware_aliases={},
        flash=False,
        flash_device=None,
        flash_baud=None,
        flash_extra_opts=None,
        no_backup=False,
        dry_run=False,
    )

    monkeypatch.setattr(setup_bmcu, "parse_args", lambda: args)
    monkeypatch.setattr(setup_bmcu, "_copy_file", lambda *a, **k: None)
    monkeypatch.setattr(setup_bmcu, "_detect_serial_symlink", lambda: None)

    exit_code = setup_bmcu.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "--serial-path" in captured.err


def test_flash_failure_reports_command_output(monkeypatch, tmp_path, capsys):
    messages = {
        "stdout": "flash output\nline 2\n",
        "stderr": "flash error\n",
    }

    def fake_run(cmd, cwd, check, capture_output, text):
        assert cmd == [
            "make",
            "flash",
        ]
        assert check is True
        assert capture_output is True
        assert text is True
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=cmd,
            output=messages["stdout"],
            stderr=messages["stderr"],
        )

    monkeypatch.setattr(setup_bmcu.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError):
        setup_bmcu._flash_firmware(
            tmp_path,
            flash_device=None,
            flash_baud=None,
            flash_extra_opts=None,
            dry_run=False,
        )

    captured = capsys.readouterr()
    assert messages["stdout"].strip() in captured.err
    assert messages["stderr"].strip() in captured.err


def test_flash_command_includes_optional_arguments(monkeypatch, tmp_path):
    captured_cmd = None

    def fake_run(cmd, cwd, check, capture_output, text):
        nonlocal captured_cmd
        captured_cmd = cmd
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=cmd,
            output="",
            stderr="",
        )

    monkeypatch.setattr(setup_bmcu.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError):
        setup_bmcu._flash_firmware(
            tmp_path,
            flash_device="/dev/ttyUSB0",
            flash_baud=115200,
            flash_extra_opts="--reset --boot-delay=1",
            dry_run=False,
        )

    assert captured_cmd == [
        "make",
        "flash",
        "FLASH_DEVICE=/dev/ttyUSB0",
        "FLASH_BAUD=115200",
        "FLASH_EXTRA_OPTS=--reset --boot-delay=1",
    ]

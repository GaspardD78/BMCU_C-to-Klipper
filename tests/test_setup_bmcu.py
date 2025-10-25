from pathlib import Path
from types import SimpleNamespace

import pytest

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

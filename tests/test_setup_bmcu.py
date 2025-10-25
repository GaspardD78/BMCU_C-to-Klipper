from types import SimpleNamespace

from scripts import setup_bmcu


def test_ensure_mcu_section_uses_serial_path():
    lines = ["# existing config\n"]
    serial = "/dev/serial/by-id/usb-test-bmcu"

    updated_lines, changed = setup_bmcu._ensure_mcu_section(lines, serial)

    assert changed is True
    assert any(line.strip() == f"serial: {serial}" for line in updated_lines)


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

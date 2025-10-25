from scripts import setup_bmcu


def test_ensure_mcu_section_uses_serial_path():
    lines = ["# existing config\n"]
    serial = "/dev/serial/by-id/usb-test-bmcu"

    updated_lines, changed = setup_bmcu._ensure_mcu_section(lines, serial)

    assert changed is True
    assert any(line.strip() == f"serial: {serial}" for line in updated_lines)

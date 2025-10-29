import textwrap
from pathlib import Path

from test_wchisp_checksum import _run_bash


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "flash_automation" / "flash_automation.sh"


def test_serial_dependencies_fail_when_flash_usb_missing(tmp_path):
    missing_path = tmp_path / "flash_usb.py"
    script = textwrap.dedent(
        f"""
        export FLASH_AUTOMATION_FLASH_USB_SCRIPT="{missing_path}"
        source "{SCRIPT_PATH}"
        flash_automation_initialize
        trap - ERR
        trap - EXIT
        set +e
        verify_method_dependencies serial manual
        """
    )

    result = _run_bash(script)
    assert result.returncode == 1, result.stdout + result.stderr
    combined_output = result.stdout + result.stderr
    assert "flash_usb.py" in combined_output
    assert "Lancez './build.sh'" in combined_output


def test_serial_dependencies_accept_custom_flash_usb_script(tmp_path):
    custom_script = tmp_path / "custom_flash_usb.py"
    custom_script.write_text("#!/usr/bin/env python3\n")

    script = textwrap.dedent(
        f"""
        source "{SCRIPT_PATH}"
        flash_automation_initialize
        trap - ERR
        trap - EXIT
        set +e
        parse_cli_arguments --flash-usb-script "{custom_script}"
        apply_configuration_defaults
        verify_method_dependencies serial manual
        status=$?
        echo "status=$status"
        exit $status
        """
    )

    result = _run_bash(script)
    assert result.returncode == 0, result.stderr
    assert "flash_usb.py disponible" in result.stdout
    assert "status=0" in result.stdout


def test_serial_dependencies_skip_flash_usb_check_in_dry_run(tmp_path):
    missing_path = tmp_path / "flash_usb.py"

    script = textwrap.dedent(
        f"""
        export FLASH_AUTOMATION_FLASH_USB_SCRIPT="{missing_path}"
        source "{SCRIPT_PATH}"
        flash_automation_initialize
        trap - ERR
        trap - EXIT
        set +e
        parse_cli_arguments --dry-run
        apply_configuration_defaults
        verify_method_dependencies serial manual
        status=$?
        echo "status=$status"
        """
    )

    result = _run_bash(script)
    assert result.returncode == 0, result.stdout + result.stderr
    combined_output = result.stdout + result.stderr
    assert "Mode --dry-run" in combined_output
    assert "status=0" in combined_output

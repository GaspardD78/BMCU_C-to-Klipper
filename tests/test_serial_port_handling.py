from pathlib import Path
import textwrap

from test_wchisp_checksum import _run_bash

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "flash_automation" / "flash_automation.sh"


def test_auto_confirm_missing_serial_port_aborts(tmp_path):
    missing_port = tmp_path / "ttyFAKE"
    script = textwrap.dedent(
        f"""
        missing_port="{missing_port}"
        rm -f "$missing_port"
        source "{SCRIPT_PATH}"
        flash_automation_initialize
        trap - ERR
        trap - EXIT
        set +e
        set +u
        parse_cli_arguments --auto-confirm --method serial --serial-port "$missing_port"
        apply_configuration_defaults
        SELECTED_METHOD="serial"
        finalize_method_selection
        """
    )

    result = _run_bash(script)
    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert "Mode auto-confirm" in combined_output
    assert str(missing_port) in combined_output


def test_interactive_missing_serial_port_triggers_prompt(tmp_path):
    missing_port = tmp_path / "ttyMISSING"
    fallback_port = tmp_path / "ttyUSB-real"
    script = textwrap.dedent(
        f"""
        missing_port="{missing_port}"
        fallback_port="{fallback_port}"
        rm -f "$missing_port" "$fallback_port"
        source "{SCRIPT_PATH}"
        prompt_serial_device() {{
            echo "prompt_invoked=1"
            touch "$fallback_port"
            SELECTED_DEVICE="$fallback_port"
        }}
        flash_automation_initialize
        trap - ERR
        trap - EXIT
        set +e
        set +u
        parse_cli_arguments --method serial --serial-port "$missing_port"
        apply_configuration_defaults
        SELECTED_METHOD="serial"
        finalize_method_selection
        echo "selected=$SELECTED_DEVICE"
        """
    )

    result = _run_bash(script)
    assert result.returncode == 0, result.stderr
    assert "prompt_invoked=1" in result.stdout
    assert f"selected={fallback_port}" in result.stdout

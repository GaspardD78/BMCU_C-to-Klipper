import textwrap
from pathlib import Path

from test_wchisp_checksum import _run_bash

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "flash_automation" / "flash_automation.sh"


def _extract_value(output: str, key: str) -> str:
    prefix = f"{key}="
    for line in output.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :]
    raise AssertionError(f"{key} line missing in output:\n{output}")


def test_auto_detection_requires_wch_presence():
    script = textwrap.dedent(
        f"""
        export WCHISP_BIN=/bin/true
        source "{SCRIPT_PATH}"
        flash_automation_initialize
        trap - ERR
        trap - EXIT
        set +e
        detect_wch_bootloader_devices() {{
            local -n ref=$1
            ref=()
        }}
        detect_dfu_devices() {{
            local -n ref=$1
            ref=("DFU:auto")
        }}
        detect_serial_devices() {{
            local -n ref=$1
            ref=("/dev/ttyUSB-auto")
        }}
        method="$(auto_detect_flash_method)"
        echo "method=$method"
        exit 0
        """
    )

    result = _run_bash(script)
    assert result.returncode == 0, result.stderr
    method = _extract_value(result.stdout, "method")

    assert method == "dfu"


def test_auto_detection_prefers_wch_when_device_present():
    script = textwrap.dedent(
        f"""
        export WCHISP_BIN=/bin/true
        source "{SCRIPT_PATH}"
        flash_automation_initialize
        trap - ERR
        trap - EXIT
        set +e
        detect_wch_bootloader_devices() {{
            local -n ref=$1
            ref=("usb:1a86:8010")
        }}
        detect_dfu_devices() {{
            local -n ref=$1
            ref=("DFU:auto")
        }}
        method="$(auto_detect_flash_method)"
        echo "method=$method"
        exit 0
        """
    )

    result = _run_bash(script)
    assert result.returncode == 0, result.stderr
    method = _extract_value(result.stdout, "method")

    assert method == "wchisp"


def test_wchisp_failure_falls_back_to_dfu():
    script = textwrap.dedent(
        f"""
        source "{SCRIPT_PATH}"
        flash_automation_initialize
        trap - ERR
        trap - EXIT
        set +e
        detect_wch_bootloader_devices() {{
            local -n ref=$1
            ref=()
        }}
        detect_dfu_devices() {{
            local -n ref=$1
            ref=("DFU:auto")
        }}
        ensure_dfu_util_available() {{
            return 0
        }}
        detect_serial_devices() {{
            local -n ref=$1
            ref=("/dev/ttyUSB-auto")
        }}
        SELECTED_METHOD="wchisp"
        RESOLVED_METHOD="wchisp"
        DEPENDENCIES_VERIFIED_FOR_METHOD="wchisp"
        SERIAL_SELECTION_SOURCE=""
        SDCARD_SELECTION_SOURCE=""
        SELECTED_DEVICE=""
        SDCARD_MOUNTPOINT=""
        handle_wchisp_failure 2
        status=$?
        echo "status=$status"
        echo "fallback_method=$SELECTED_METHOD"
        echo "serial_device=$SELECTED_DEVICE"
        exit 0
        """
    )

    result = _run_bash(script)
    assert result.returncode == 0, result.stderr
    status = _extract_value(result.stdout, "status")
    fallback_method = _extract_value(result.stdout, "fallback_method")
    serial_device = _extract_value(result.stdout, "serial_device")

    assert status == "0"
    assert fallback_method == "dfu"
    assert serial_device == ""


def test_wchisp_failure_falls_back_to_serial_when_no_dfu():
    script = textwrap.dedent(
        f"""
        source "{SCRIPT_PATH}"
        flash_automation_initialize
        trap - ERR
        trap - EXIT
        set +e
        detect_wch_bootloader_devices() {{
            local -n ref=$1
            ref=()
        }}
        detect_dfu_devices() {{
            local -n ref=$1
            ref=()
        }}
        detect_serial_devices() {{
            local -n ref=$1
            ref=("/dev/ttyUSB-auto" "/dev/ttyUSB-alt")
        }}
        SELECTED_METHOD="wchisp"
        RESOLVED_METHOD="wchisp"
        DEPENDENCIES_VERIFIED_FOR_METHOD="wchisp"
        SERIAL_SELECTION_SOURCE=""
        SDCARD_SELECTION_SOURCE=""
        SELECTED_DEVICE=""
        SDCARD_MOUNTPOINT=""
        handle_wchisp_failure 3
        status=$?
        echo "status=$status"
        echo "fallback_method=$SELECTED_METHOD"
        echo "serial_device=$SELECTED_DEVICE"
        echo "serial_source=$SERIAL_SELECTION_SOURCE"
        exit 0
        """
    )

    result = _run_bash(script)
    assert result.returncode == 0, result.stderr
    status = _extract_value(result.stdout, "status")
    fallback_method = _extract_value(result.stdout, "fallback_method")
    serial_device = _extract_value(result.stdout, "serial_device")
    serial_source = _extract_value(result.stdout, "serial_source")

    assert status == "0"
    assert fallback_method == "serial"
    assert serial_device == "/dev/ttyUSB-auto"
    assert "fallback" in serial_source

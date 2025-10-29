from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tarfile
import textwrap
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
FLASH_DIR = REPO_ROOT / "flash_automation"
FLASH_SCRIPT = FLASH_DIR / "flash_automation.sh"
LOGS_DIR = FLASH_DIR / "logs"


def _run_bash(
    snippet: str, *, env: dict[str, str] | None = None
) -> tuple[subprocess.CompletedProcess[str], list[Path]]:
    """Execute a Bash snippet with the flash automation script sourced."""

    env_vars = os.environ.copy()
    if env:
        env_vars.update(env)

    existing_logs = set(LOGS_DIR.iterdir()) if LOGS_DIR.exists() else set()

    try:
        result = subprocess.run(
            [
                "bash",
                "-lc",
                textwrap.dedent(
                    f"""
                    set -euo pipefail
                    source "{FLASH_SCRIPT}"
                    flash_automation_initialize
                    trap - ERR
                    trap - EXIT
                    set +e
                    {snippet}
                    """
                ),
            ],
            check=False,
            text=True,
            capture_output=True,
            env=env_vars,
        )
    finally:
        pass

    if LOGS_DIR.exists():
        current = set(LOGS_DIR.iterdir())
        new_dirs = [path for path in current - existing_logs if path.is_dir()]
    else:
        new_dirs = []

    return result, new_dirs


@pytest.fixture()
def wchisp_archive(tmp_path: Path) -> tuple[Path, str]:
    archive = tmp_path / "wchisp-test.tar.gz"
    binary = tmp_path / "wchisp"
    binary.write_text("#!/bin/sh\necho stubbed\n", encoding="utf-8")
    binary.chmod(0o755)
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(binary, arcname="package/wchisp")
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    return archive, checksum


def test_auto_install_wchisp_writes_logs(tmp_path: Path, wchisp_archive: tuple[Path, str]):
    archive, checksum = wchisp_archive
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    env = {
        "HOME": str(tmp_path / "home"),
        "XDG_CACHE_HOME": str(tmp_path / "xdg-cache"),
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
        "WCHISP_ARCH_OVERRIDE": "armv7l",
        "WCHISP_FALLBACK_ARCHIVE_URL": f"file://{archive}",
        "WCHISP_FALLBACK_CHECKSUM": checksum,
        "WCHISP_AUTO_INSTALL": "true",
        "WCHISP_BIN": "wchisp-missing",
    }

    snippet = """
        ensure_wchisp
        status=$?
        echo "status=${status}"
        echo "log_dir=${LOG_DIR}"
        echo "installed=${WCHISP_COMMAND}"
    """

    result, log_dirs = _run_bash(snippet, env=env)

    assert result.returncode == 0, result.stderr
    stdout_lines = {line.split("=", 1)[0]: line.split("=", 1)[1] for line in result.stdout.splitlines() if "=" in line}

    assert stdout_lines.get("status") == "0"
    installed_path = stdout_lines.get("installed")
    assert installed_path and Path(installed_path).exists()

    log_dir = stdout_lines.get("log_dir")
    assert log_dir, result.stdout
    log_file = Path(log_dir) / "flash.log"
    assert log_file.exists()
    log_content = log_file.read_text(encoding="utf-8")
    assert "Téléchargement de wchisp" in log_content
    assert "Extraction de wchisp" in log_content
    assert "wchisp disponible localement" in log_content

    # Cache artefacts should be cleaned to avoid polluting the repository cache.
    shutil.rmtree(FLASH_DIR / ".cache", ignore_errors=True)
    for new_dir in log_dirs:
        shutil.rmtree(new_dir, ignore_errors=True)
    if LOGS_DIR.exists() and not any(LOGS_DIR.iterdir()):
        LOGS_DIR.rmdir()


def test_systemctl_wrapper_controls_services(tmp_path: Path):
    log_file = tmp_path / "systemctl.log"

    systemctl_stub = tmp_path / "systemctl"
    systemctl_stub.write_text(
        textwrap.dedent(
            f"""
            #!/bin/bash
            set -euo pipefail
            echo "$@" >> "{log_file}"
            case "$1" in
                status)
                    if [[ "$2" == "klipper.service" || "$2" == "klipper-mcu.service" ]]; then
                        exit 0
                    fi
                    ;;
                is-active)
                    if [[ "$3" == "klipper.service" || "$3" == "klipper-mcu.service" ]]; then
                        exit 0
                    fi
                    ;;
                stop|start)
                    exit 0
                    ;;
            esac
            exit 1
            """
        ),
        encoding="utf-8",
    )
    systemctl_stub.chmod(0o755)

    env = {
        "PATH": f"{systemctl_stub.parent}:{os.environ.get('PATH', '')}",
        "HOME": str(tmp_path / "home"),
        "XDG_CACHE_HOME": str(tmp_path / "xdg-cache"),
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }

    snippet = """
        detect_klipper_services
        stop_klipper_services
        restart_klipper_services
        echo "services=${ACTIVE_KLIPPER_SERVICES[*]}"
        echo "stopped=${SERVICES_STOPPED}"
        echo "restored=${SERVICES_RESTORED}"
        echo "log_dir=${LOG_DIR}"
    """

    result, log_dirs = _run_bash(snippet, env=env)

    assert result.returncode == 0, result.stderr
    stdout_lines = {line.split("=", 1)[0]: line.split("=", 1)[1] for line in result.stdout.splitlines() if "=" in line}
    services = stdout_lines.get("services", "").split()
    assert services == ["klipper.service", "klipper-mcu.service"]
    assert stdout_lines.get("stopped") == "true"
    assert stdout_lines.get("restored") == "true"

    log_dir = stdout_lines.get("log_dir")
    assert log_dir
    log_path = Path(log_dir) / "flash.log"
    assert log_path.exists()
    log_content = log_path.read_text(encoding="utf-8")
    assert "Services Klipper actifs détectés" in log_content
    assert "Service klipper.service arrêté." in log_content
    assert "Service klipper-mcu.service relancé." in log_content

    stub_calls = log_file.read_text(encoding="utf-8").splitlines()
    assert stub_calls.count("status klipper.service") == 1
    assert stub_calls.count("status klipper-mcu.service") == 1
    assert "is-active --quiet klipper.service" in stub_calls
    assert "is-active --quiet klipper-mcu.service" in stub_calls
    assert "stop klipper.service" in stub_calls
    assert "stop klipper-mcu.service" in stub_calls
    assert "start klipper.service" in stub_calls
    assert "start klipper-mcu.service" in stub_calls

    shutil.rmtree(FLASH_DIR / ".cache", ignore_errors=True)
    for new_dir in log_dirs:
        shutil.rmtree(new_dir, ignore_errors=True)
    if LOGS_DIR.exists() and not any(LOGS_DIR.iterdir()):
        LOGS_DIR.rmdir()

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
    env_vars = os.environ.copy()
    if env:
        env_vars.update(env)

    existing_logs = set(LOGS_DIR.iterdir()) if LOGS_DIR.exists() else set()

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

    if LOGS_DIR.exists():
        current = set(LOGS_DIR.iterdir())
        new_dirs = [path for path in current - existing_logs if path.is_dir()]
    else:
        new_dirs = []

    return result, new_dirs


def _cleanup_logs(paths: list[Path]) -> None:
    for path in paths:
        shutil.rmtree(path, ignore_errors=True)
    if LOGS_DIR.exists() and not any(LOGS_DIR.iterdir()):
        LOGS_DIR.rmdir()


def _create_wchisp_archive(tmp_path: Path, *, valid_tar: bool) -> Path:
    archive = tmp_path / "wchisp-test.tar.gz"
    if valid_tar:
        binary = tmp_path / "wchisp"
        binary.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
        binary.chmod(0o755)
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(binary, arcname="package/wchisp")
    else:
        archive.write_bytes(b"corrupted archive")
    return archive


def _assert_report_contains(report_path: Path, *fragments: str) -> None:
    assert report_path.exists(), f"failure report missing at {report_path}"
    content = report_path.read_text(encoding="utf-8")
    for fragment in fragments:
        assert fragment in content, f"'{fragment}' absent de {report_path}\n{content}"


@pytest.fixture()
def base_env(tmp_path: Path) -> dict[str, str]:
    env = {
        "HOME": str(tmp_path / "home"),
        "XDG_CACHE_HOME": str(tmp_path / "xdg-cache"),
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }
    return env


def test_handle_error_reports_invalid_checksum(tmp_path: Path, base_env: dict[str, str]):
    archive = _create_wchisp_archive(tmp_path, valid_tar=True)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()

    env = base_env | {
        "WCHISP_ARCH_OVERRIDE": "armv7l",
        "WCHISP_FALLBACK_ARCHIVE_URL": f"file://{archive}",
        "WCHISP_FALLBACK_CHECKSUM": checksum,
    }

    snippet = f"""
        CURRENT_STEP="Étape 3: Préparation de la cible"
        verify_wchisp_archive "wchisp-test.tar.gz" "{archive}" "deadbeef"
        status=$?
        if [[ $status -ne 0 ]]; then
            (exit "$status")
            handle_error $LINENO "verify_wchisp_archive"
        fi
    """

    result, log_dirs = _run_bash(snippet, env=env)
    try:
        assert result.returncode != 0
        assert log_dirs, "aucun répertoire de logs généré"
        report_path = sorted(log_dirs)[0] / "FAILURE_REPORT.txt"
        _assert_report_contains(
            report_path,
            "Étape échouée: Étape 3: Préparation de la cible",
            "La vérification d'intégrité de l'archive",
        )
    finally:
        _cleanup_logs(log_dirs)
        shutil.rmtree(FLASH_DIR / ".cache", ignore_errors=True)


def test_handle_error_reports_corrupted_archive(tmp_path: Path, base_env: dict[str, str]):
    archive = _create_wchisp_archive(tmp_path, valid_tar=False)

    env = base_env | {
        "WCHISP_ARCH_OVERRIDE": "armv7l",
        "WCHISP_FALLBACK_ARCHIVE_URL": f"file://{archive}",
    }

    install_dir = tmp_path / "install"

    snippet = f"""
        CURRENT_STEP="Étape 3: Préparation de la cible"
        mkdir -p "${{WCHISP_CACHE_DIR}}"
        install_dir="${{WCHISP_CACHE_DIR}}/test"
        rm -rf "${{install_dir}}"
        mkdir -p "${{install_dir}}"
        log_message "INFO" "Extraction de wchisp dans ${{install_dir}}."
        if ! tar -xf "{archive}" --strip-components=1 -C "${{install_dir}}"; then
            rm -rf "${{install_dir}}"
            log_message "ERROR" "Échec de l'extraction de wchisp depuis {archive}."
            error_msg "Impossible d'extraire wchisp. Vérifiez l'archive ou installez l'outil manuellement."
            (exit 1)
            handle_error $LINENO "tar -xf"
        fi
    """

    result, log_dirs = _run_bash(snippet, env=env)
    try:
        assert result.returncode != 0
        assert log_dirs, "aucun répertoire de logs généré"
        report_path = sorted(log_dirs)[0] / "FAILURE_REPORT.txt"
        _assert_report_contains(
            report_path,
            "Étape échouée: Étape 3: Préparation de la cible",
            "Impossible d'extraire wchisp",
        )
    finally:
        _cleanup_logs(log_dirs)


def test_handle_error_reports_permission_denied(tmp_path: Path, base_env: dict[str, str]):
    firmware = tmp_path / "klipper.bin"
    firmware.write_text("firmware", encoding="utf-8")
    target_dir = tmp_path / "sd"
    target_dir.mkdir()
    target = target_dir / firmware.name

    cp_stub = tmp_path / "cp"
    cp_stub.write_text(
        "#!/bin/sh\necho 'cp: permission denied' >&2\nexit 1\n",
        encoding="utf-8",
    )
    cp_stub.chmod(0o755)

    env = base_env | {
        "FIRMWARE_DISPLAY_PATH": str(firmware),
        "PATH": f"{cp_stub.parent}:{os.environ.get('PATH', '')}",
    }

    snippet = f"""
        CURRENT_STEP="Étape 4: Flashage (sdcard)"
        FIRMWARE_FILE="{firmware}"
        if ! cp "{firmware}" "{target}"; then
            error_msg "Échec de la copie du firmware vers {target}."
            (exit 1)
            handle_error $LINENO "cp"
        fi
    """

    result, log_dirs = _run_bash(snippet, env=env)
    try:
        assert result.returncode != 0
        assert log_dirs, "aucun répertoire de logs généré"
        report_path = sorted(log_dirs)[0] / "FAILURE_REPORT.txt"
        _assert_report_contains(
            report_path,
            "Étape échouée: Étape 4: Flashage (sdcard)",
            "Échec de la copie du firmware",
        )
    finally:
        _cleanup_logs(log_dirs)

import hashlib
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "flash_automation.sh"
FLASH_ROOT = SCRIPT_PATH.parent
BANNER_TEXT = (FLASH_ROOT / "banner.txt").read_text()

STUB_ARCHIVE_CONTENT = b"stub archive"
STUB_ARCHIVE_SHA256 = hashlib.sha256(STUB_ARCHIVE_CONTENT).hexdigest()


def ensure_real_command(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"The command '{name}' must be available in PATH during tests")
    return path


def run_flash_script(commands: str, *, env: dict[str, str] | None = None, input_text: str = ""):
    script = textwrap.dedent(
        f"""
        set -euo pipefail
        source "{SCRIPT_PATH}"
        {commands}
        """
    )
    search_path = None if env is None else env.get("PATH")
    bash_path = shutil.which("bash", path=search_path) or shutil.which("bash") or "/bin/bash"
    return subprocess.run(
        [bash_path, "-c", script],
        input=input_text,
        text=True,
        capture_output=True,
        env=env,
        cwd=str(FLASH_ROOT),
    )


def create_stub_environment(
    tmp_path: Path, *, include_system_path: bool = False, set_user: bool = True
) -> tuple[dict[str, str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    base_path = env.get("PATH", "") if include_system_path else ""
    env["PATH"] = f"{bin_dir}{os.pathsep}{base_path}" if base_path else str(bin_dir)
    env["HOME"] = str(tmp_path)
    if set_user:
        env["USER"] = env.get("USER", "testuser")
    else:
        env.pop("USER", None)
    return env, bin_dir


def add_symlink(bin_dir: Path, command: str, target: str | None = None):
    target_path = Path(target or ensure_real_command(command))
    link_path = bin_dir / command
    link_path.symlink_to(target_path)
    return link_path


def add_failing_stub(bin_dir: Path, command: str):
    path = bin_dir / command
    path.write_text("#!/bin/sh\nexit 1\n")
    path.chmod(0o755)
    return path


def add_id_stub(bin_dir: Path, groups: str, *, username: str | None = "stubuser"):
    real_id = ensure_real_command("id")
    username_case = "exit 1" if username is None else f'echo "{username}"'
    script = textwrap.dedent(
        f"""#!/bin/sh
        case "$1" in
            -nG)
                shift
                echo "{groups}"
                ;;
            -un)
                {username_case}
                ;;
            *)
                exec "{real_id}" "$@"
                ;;
        esac
        """
    )
    path = bin_dir / "id"
    path.write_text(script)
    path.chmod(0o755)
    return path


COMMON_COMMANDS = [
    "dirname",
    "cat",
    "date",
    "mkdir",
    "touch",
    "chmod",
    "tee",
    "awk",
    "grep",
    "tr",
    "sed",
    "rm",
    "cp",
    "sync",
    "ls",
    "tail",
    "basename",
]


def populate_common_commands(bin_dir: Path):
    for name in COMMON_COMMANDS:
        add_symlink(bin_dir, name)


def test_cli_help_omits_banner(tmp_path):
    env = os.environ.copy()
    env.setdefault("LC_ALL", "C.UTF-8")
    env.setdefault("LANG", "C.UTF-8")
    env["HOME"] = str(tmp_path / "home")
    env["XDG_CACHE_HOME"] = str(tmp_path / "xdg-cache")

    result = subprocess.run(
        [str(SCRIPT_PATH), "--help"],
        cwd=str(FLASH_ROOT),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0
    assert BANNER_TEXT not in result.stdout
    assert result.stdout.startswith("Usage: flash_automation.sh")
    assert result.stderr == ""


PROMPT_OVERRIDE = textwrap.dedent(
    """
    prompt_firmware_selection() {
        local target="$1"
        local -n _candidates="$target"
        local choice=""

        while true; do
            echo
            echo "Sélectionnez le firmware à utiliser :"
            local index=1
            for file in "${_candidates[@]}"; do
                local display
                display="$(format_path_for_display "${file}")"
                local extension="${file##*.}"
                printf "  [%d] %s (%s)\n" "${index}" "${display}" "${extension}";
                ((index++))
            done
            printf "  [%d] Saisir un chemin personnalisé\n" "${index}"

            read -rp "Votre choix : " answer

            if [[ "${answer}" =~ ^[0-9]+$ ]]; then
                local numeric=$((answer))
                if (( numeric >= 1 && numeric <= ${#_candidates[@]} )); then
                    choice="${_candidates[$((numeric-1))]}"
                    break
                elif (( numeric == index )); then
                    read -rp "Chemin complet du firmware : " custom_path
                    local resolved
                    resolved="$(resolve_path_relative_to_flash_root "${custom_path}")"
                    if [[ -f "${resolved}" ]]; then
                        choice="${resolved}"
                        break
                    fi
                    error_msg "Le fichier spécifié est introuvable (${custom_path})."
                fi
            else
                local resolved
                resolved="$(resolve_path_relative_to_flash_root "${answer}")"
                if [[ -f "${resolved}" ]]; then
                    choice="${resolved}"
                    break
                fi
                error_msg "Sélection invalide : ${answer}"
            fi
        done

        FIRMWARE_FILE="${choice}"
        FIRMWARE_DISPLAY_PATH="$(format_path_for_display "${FIRMWARE_FILE}")"
        FIRMWARE_FORMAT="${FIRMWARE_FILE##*.}"
    }
    """
)


@pytest.mark.parametrize(
    "missing_command,expected_messages",
    [
        (None, ["Utilisateur membre du groupe 'dialout'."]),
        (
            "sha256sum",
            [
                "La dépendance obligatoire 'sha256sum' est introuvable.",
                "Installez le paquet fournissant 'sha256sum' (ex: sudo apt install coreutils).",
            ],
        ),
    ],
)
def test_verify_environment_dependency_checks(tmp_path, missing_command, expected_messages):
    env, bin_dir = create_stub_environment(tmp_path)
    add_symlink(bin_dir, "bash")
    add_id_stub(bin_dir, "dialout")
    populate_common_commands(bin_dir)

    required_commands = ["curl", "tar", "sha256sum", "stat", "find", "python3", "make"]
    for command in required_commands:
        if command == missing_command:
            continue
        add_symlink(bin_dir, command)

    if missing_command is None:
        result = run_flash_script("verify_environment", env=env)
        assert result.returncode == 0
    else:
        result = run_flash_script("verify_environment", env=env)
        assert result.returncode != 0

    combined_output = result.stdout + result.stderr
    for expected_message in expected_messages:
        assert expected_message in combined_output


def test_verify_environment_warns_when_python_missing(tmp_path):
    env, bin_dir = create_stub_environment(tmp_path)
    add_symlink(bin_dir, "bash")
    add_id_stub(bin_dir, "dialout")
    populate_common_commands(bin_dir)
    for command in ["curl", "tar", "sha256sum", "stat", "find", "make"]:
        add_symlink(bin_dir, command)

    result = run_flash_script("verify_environment || true", env=env)
    assert result.returncode == 0
    assert "La dépendance optionnelle 'python3' est absente" in result.stdout
    assert "Installez 'python3' via votre gestionnaire de paquets" in result.stdout


def test_verify_environment_uses_permission_cache(tmp_path):
    env, bin_dir = create_stub_environment(tmp_path)
    add_symlink(bin_dir, "bash")
    add_id_stub(bin_dir, "dialout")
    populate_common_commands(bin_dir)
    for command in ["curl", "tar", "sha256sum", "stat", "find", "python3", "make"]:
        add_symlink(bin_dir, command)

    cache_file = tmp_path / "perm_cache.json"
    env["PERMISSIONS_CACHE_FILE"] = str(cache_file)
    env["PERMISSIONS_CACHE_TTL"] = "3600"

    first = run_flash_script("verify_environment", env=env)
    assert first.returncode == 0
    assert "Cache des permissions mis à jour" in first.stdout

    second = run_flash_script("verify_environment", env=env)
    assert second.returncode == 0
    assert "Vérification des permissions sautée" in second.stdout


def test_check_group_membership_warns_without_user(tmp_path):
    env, bin_dir = create_stub_environment(tmp_path, set_user=False)
    add_symlink(bin_dir, "bash")
    populate_common_commands(bin_dir)
    add_id_stub(bin_dir, "dialout", username=None)
    add_failing_stub(bin_dir, "logname")
    add_failing_stub(bin_dir, "whoami")

    result = run_flash_script('check_group_membership "dialout" || true', env=env)

    assert result.returncode == 0
    assert "Impossible de déterminer l'utilisateur courant ; vérification du groupe 'dialout' ignorée." in (
        result.stdout + result.stderr
    )


def make_stub_curl(bin_dir: Path):
    script = textwrap.dedent(
        f"""#!/bin/sh
        output=""
        while [ "$#" -gt 0 ]; do
            case "$1" in
                -o)
                    shift
                    output="$1"
                    ;;
            esac
            shift
        done
        if [ -z "$output" ]; then
            exit 1
        fi
        printf '%s' '{STUB_ARCHIVE_CONTENT.decode()}' >"$output"
        exit 0
        """
    )
    path = bin_dir / "curl"
    path.write_text(script)
    path.chmod(0o755)
    return path


def make_stub_tar(bin_dir: Path):
    script = textwrap.dedent(
        """#!/bin/sh
        target=""
        while [ "$#" -gt 0 ]; do
            if [ "$1" = "-C" ]; then
                shift
                target="$1"
            fi
            shift
        done
        [ -n "$target" ] || exit 1
        mkdir -p "$target"
        printf '#!/bin/sh\necho stub wchisp\n' >"$target/wchisp"
        chmod +x "$target/wchisp"
        exit 0
        """
    )
    path = bin_dir / "tar"
    path.write_text(script)
    path.chmod(0o755)
    return path


def make_stub_uname(bin_dir: Path, arch: str = "x86_64"):
    real_uname = ensure_real_command("uname")
    script = textwrap.dedent(
        f"""#!/bin/sh
        if [ "$#" -eq 0 ] || [ "$1" = "-m" ]; then
            echo "{arch}"
        else
            exec "{real_uname}" "$@"
        fi
        """
    )
    path = bin_dir / "uname"
    path.write_text(script)
    path.chmod(0o755)
    return path


def test_ensure_wchisp_installs_tool_when_missing(tmp_path):
    env, bin_dir = create_stub_environment(tmp_path)
    add_symlink(bin_dir, "bash")
    add_id_stub(bin_dir, "dialout")
    populate_common_commands(bin_dir)
    for command in ["sha256sum", "stat", "find", "python3", "make"]:
        add_symlink(bin_dir, command)
    make_stub_curl(bin_dir)
    make_stub_tar(bin_dir)
    make_stub_uname(bin_dir)

    env["WCHISP_BASE_URL"] = "https://example.invalid"
    env["WCHISP_AUTO_INSTALL"] = "true"
    env["WCHISP_ARCHIVE_CHECKSUM_OVERRIDE"] = STUB_ARCHIVE_SHA256

    cache_dir = FLASH_ROOT / ".cache/tools/wchisp"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)

    result = run_flash_script("flash_automation_initialize\nensure_wchisp", env=env)
    assert result.returncode == 0
    assert "wchisp installé automatiquement" in result.stdout

    install_dir = cache_dir / "v0.3.0-x86_64"
    assert (install_dir / "wchisp").exists()


def test_ensure_wchisp_respects_quiet_mode(tmp_path):
    env, bin_dir = create_stub_environment(tmp_path)
    add_symlink(bin_dir, "bash")
    add_id_stub(bin_dir, "dialout")
    populate_common_commands(bin_dir)
    for command in ["sha256sum", "stat", "find", "python3", "make"]:
        add_symlink(bin_dir, command)
    make_stub_curl(bin_dir)
    make_stub_tar(bin_dir)
    make_stub_uname(bin_dir, arch="armv7l")

    env["WCHISP_AUTO_INSTALL"] = "true"
    env["WCHISP_FALLBACK_ARCHIVE_URL"] = "https://example.invalid/wchisp-fallback.tar.gz"
    env["WCHISP_FALLBACK_CHECKSUM"] = STUB_ARCHIVE_SHA256

    cache_dir = FLASH_ROOT / ".cache/tools/wchisp"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)

    result = run_flash_script('flash_automation_initialize\nQUIET_MODE="true"\nensure_wchisp', env=env)

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_ensure_wchisp_stops_on_download_failure(tmp_path):
    env, bin_dir = create_stub_environment(tmp_path)
    add_symlink(bin_dir, "bash")
    add_id_stub(bin_dir, "dialout")
    populate_common_commands(bin_dir)
    for command in ["sha256sum", "stat", "find", "python3", "make", "tar", "uname"]:
        add_symlink(bin_dir, command)

    script = textwrap.dedent(
        """#!/bin/sh
        exit 1
        """
    )
    path = bin_dir / "curl"
    path.write_text(script)
    path.chmod(0o755)

    cache_dir = FLASH_ROOT / ".cache/tools/wchisp"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)

    result = run_flash_script("flash_automation_initialize\nensure_wchisp", env=env)
    assert result.returncode != 0
    assert "Échec du téléchargement de wchisp" in result.stderr + result.stdout


def test_prepare_firmware_errors_when_no_candidates(tmp_path):
    env, bin_dir = create_stub_environment(tmp_path, include_system_path=True)
    add_id_stub(bin_dir, "dialout")
    result = run_flash_script("prepare_firmware", env=env)
    assert result.returncode != 0
    assert "Aucun firmware compatible détecté" in result.stderr + result.stdout


def test_prepare_firmware_selects_single_candidate(tmp_path):
    firmware = tmp_path / "klipper.bin"
    firmware.write_text("payload")

    env, bin_dir = create_stub_environment(tmp_path, include_system_path=True)
    env["KLIPPER_FIRMWARE_PATH"] = str(firmware)
    add_id_stub(bin_dir, "dialout")

    result = run_flash_script(PROMPT_OVERRIDE + "\nprepare_firmware", env=env, input_text="1\n")
    assert result.returncode == 0
    assert str(firmware) in result.stdout


def test_prepare_firmware_lists_multiple_candidates(tmp_path):
    firmware_a = tmp_path / "a.bin"
    firmware_b = tmp_path / "b.elf"
    firmware_a.write_text("A")
    firmware_b.write_text("B")

    env, bin_dir = create_stub_environment(tmp_path, include_system_path=True)
    env["KLIPPER_FIRMWARE_PATH"] = str(tmp_path)
    add_id_stub(bin_dir, "dialout")

    result = run_flash_script(PROMPT_OVERRIDE + "\nprepare_firmware", env=env, input_text="2\n")
    assert result.returncode == 0
    assert "a.bin" in result.stdout
    assert "b.elf" in result.stdout
    assert "Firmware sélectionné" in result.stdout


def test_prepare_firmware_accepts_custom_path(tmp_path):
    default_fw = tmp_path / "default.bin"
    custom_fw = tmp_path / "custom.bin"
    default_fw.write_text("default")
    custom_fw.write_text("custom")

    env, bin_dir = create_stub_environment(tmp_path, include_system_path=True)
    env["KLIPPER_FIRMWARE_PATH"] = str(default_fw)
    add_id_stub(bin_dir, "dialout")

    # Option 2 corresponds to "Saisir un chemin personnalisé"
    input_sequence = f"2\n{custom_fw}\n"
    result = run_flash_script(PROMPT_OVERRIDE + "\nprepare_firmware", env=env, input_text=input_sequence)
    assert result.returncode == 0
    assert str(custom_fw) in result.stdout


def test_prepare_firmware_reprompts_on_invalid_custom_path(tmp_path):
    default_fw = tmp_path / "default.bin"
    default_fw.write_text("default")

    env, bin_dir = create_stub_environment(tmp_path, include_system_path=True)
    env["KLIPPER_FIRMWARE_PATH"] = str(default_fw)
    add_id_stub(bin_dir, "dialout")

    input_sequence = f"2\n/tmp/does-not-exist.bin\n1\n"
    result = run_flash_script(PROMPT_OVERRIDE + "\nprepare_firmware", env=env, input_text=input_sequence)
    assert result.returncode == 0
    assert "Le fichier spécifié est introuvable" in result.stderr + result.stdout
    assert "Firmware sélectionné" in result.stdout


def test_flash_with_wchisp_runs_command(tmp_path):
    env, bin_dir = create_stub_environment(tmp_path)
    add_symlink(bin_dir, "bash")
    add_id_stub(bin_dir, "dialout")
    populate_common_commands(bin_dir)
    for command in ["sha256sum", "stat", "find", "python3", "make"]:
        add_symlink(bin_dir, command)
    make_stub_curl(bin_dir)
    make_stub_tar(bin_dir)
    make_stub_uname(bin_dir)

    firmware = tmp_path / "klipper.bin"
    firmware.write_text("binary")

    wchisp_invocation = tmp_path / "wchisp_invoked"
    stub = textwrap.dedent(
        f"""#!/bin/sh
        printf '%s' "$@" >"{wchisp_invocation}"
        exit 0
        """
    )
    (tmp_path / "wchisp").write_text(stub)
    (tmp_path / "wchisp").chmod(0o755)

    env["WCHISP_BIN"] = str(tmp_path / "wchisp")
    env["WCHISP_ARCHIVE_CHECKSUM_OVERRIDE"] = STUB_ARCHIVE_SHA256

    commands = textwrap.dedent(
        f"""
        FIRMWARE_FILE="{firmware}"
        SELECTED_METHOD="wchisp"
        flash_with_wchisp
        """
    )

    result = run_flash_script(commands, env=env)
    assert result.returncode == 0
    assert "wchisp a terminé le flash" in result.stdout
    assert wchisp_invocation.read_text().startswith("--usb")


def test_select_flash_method_warns_when_no_serial_device(tmp_path):
    env, bin_dir = create_stub_environment(tmp_path, include_system_path=True)
    add_id_stub(bin_dir, "dialout")

    fake_device = tmp_path / "ttyFAKE"
    fake_device.write_text("")

    input_sequence = f"2\n{fake_device}\n"
    result = run_flash_script("select_flash_method", env=env, input_text=input_sequence)
    assert result.returncode == 0
    assert "Aucun port série détecté" in result.stdout
    assert "Port série sélectionné" in result.stdout


def test_flash_with_serial_errors_when_script_missing(tmp_path):
    env, bin_dir = create_stub_environment(tmp_path, include_system_path=True)
    add_id_stub(bin_dir, "dialout")
    firmware = tmp_path / "klipper.bin"
    firmware.write_text("binary")

    commands = textwrap.dedent(
        f"""
        FIRMWARE_FILE="{firmware}"
        SELECTED_DEVICE="{tmp_path / 'ttyUSB0'}"
        SELECTED_METHOD="serial"
        flash_with_serial
        """
    )

    result = run_flash_script(commands, env=env)
    assert result.returncode != 0
    assert "flash_usb.py est introuvable" in result.stderr + result.stdout


def test_prompt_sdcard_mountpoint_validates_paths(tmp_path):
    env, bin_dir = create_stub_environment(tmp_path, include_system_path=True)
    add_id_stub(bin_dir, "dialout")

    mountpoint = tmp_path / "mount"
    mountpoint.mkdir()

    input_sequence = f"/path/invalid\n{mountpoint}\n"
    result = run_flash_script("prompt_sdcard_mountpoint", env=env, input_text=input_sequence)
    assert result.returncode == 0
    assert "introuvable ou non accessible" in result.stderr + result.stdout
    assert str(mountpoint) in result.stdout


def test_flash_with_sdcard_copies_firmware(tmp_path):
    env, bin_dir = create_stub_environment(tmp_path, include_system_path=True)
    add_id_stub(bin_dir, "dialout")

    firmware = tmp_path / "klipper.bin"
    firmware.write_text("binary")
    mountpoint = tmp_path / "mount"
    mountpoint.mkdir()

    commands = textwrap.dedent(
        f"""
        FIRMWARE_FILE="{firmware}"
        FIRMWARE_DISPLAY_PATH="{firmware}"
        SELECTED_METHOD="sdcard"
        SDCARD_MOUNTPOINT="{mountpoint}"
        flash_with_sdcard
        """
    )

    result = run_flash_script(commands, env=env)
    assert result.returncode == 0
    copied = mountpoint / firmware.name
    assert copied.exists()
    assert copied.read_text() == "binary"


def test_flash_with_sdcard_creates_failure_report_on_error(tmp_path):
    env, bin_dir = create_stub_environment(tmp_path, include_system_path=True)
    add_id_stub(bin_dir, "dialout")

    firmware = tmp_path / "klipper.bin"
    firmware.write_text("binary")
    mountpoint = tmp_path / "mount_file"
    mountpoint.write_text("not a directory")

    commands = textwrap.dedent(
        f"""
        FIRMWARE_FILE="{firmware}"
        FIRMWARE_DISPLAY_PATH="{firmware}"
        SELECTED_METHOD="sdcard"
        SDCARD_MOUNTPOINT="{mountpoint}"
        flash_with_sdcard
        """
    )

    result = run_flash_script(commands, env=env)
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "Échec de la copie du firmware" in combined


def make_systemctl_stub(bin_dir: Path, state_file: Path):
    script = textwrap.dedent(
        """#!/bin/sh
        state_file="$SYSTEMCTL_STATE"
        [ -n "$state_file" ] || exit 1
        command="$1"
        shift
        case "$command" in
            status)
                service="$1"
                grep -q "${service}=active" "$state_file" && exit 0 || exit 3
                ;;
            is-active)
                [ "$1" = "--quiet" ] && shift
                service="$1"
                grep -q "${service}=active" "$state_file" && exit 0 || exit 3
                ;;
            stop)
                service="$1"
                if grep -q "${service}=active" "$state_file"; then
                    sed -i "s/${service}=active/${service}=inactive/" "$state_file"
                    exit 0
                fi
                exit 1
                ;;
            start)
                service="$1"
                if grep -q "${service}=inactive" "$state_file"; then
                    sed -i "s/${service}=inactive/${service}=active/" "$state_file"
                else
                    echo "${service}=active" >>"$state_file"
                fi
                exit 0
                ;;
            *)
                exit 1
                ;;
        esac
        """
    )
    path = bin_dir / "systemctl"
    path.write_text(script)
    path.chmod(0o755)
    return path


def test_detect_and_stop_services(tmp_path):
    env, bin_dir = create_stub_environment(tmp_path)
    add_symlink(bin_dir, "bash")
    add_id_stub(bin_dir, "dialout")
    populate_common_commands(bin_dir)
    for command in ["sha256sum", "stat", "find", "python3", "make"]:
        add_symlink(bin_dir, command)

    state_file = tmp_path / "systemctl_state"
    state_file.write_text("klipper.service=active\n")
    make_systemctl_stub(bin_dir, state_file)
    env["SYSTEMCTL_STATE"] = str(state_file)

    script = "\n".join(
        [
            "detect_klipper_services",
            "stop_klipper_services",
            "printf '%s' \"${ACTIVE_KLIPPER_SERVICES[*]}\"",
        ]
    )
    result = run_flash_script(script, env=env)
    assert result.returncode == 0
    assert "Services Klipper actifs détectés" in result.stdout
    assert "Service klipper.service arrêté" in result.stdout
    assert "klipper.service" in result.stdout.splitlines()[-1]


def test_detect_services_when_none_active(tmp_path):
    env, bin_dir = create_stub_environment(tmp_path)
    add_symlink(bin_dir, "bash")
    add_id_stub(bin_dir, "dialout")
    populate_common_commands(bin_dir)
    for command in ["sha256sum", "stat", "find", "python3", "make"]:
        add_symlink(bin_dir, command)

    state_file = tmp_path / "systemctl_state"
    state_file.write_text("")
    make_systemctl_stub(bin_dir, state_file)
    env["SYSTEMCTL_STATE"] = str(state_file)

    result = run_flash_script("detect_klipper_services", env=env)
    assert result.returncode == 0
    assert "Aucun service Klipper actif détecté" in result.stdout


def test_restart_services_after_success(tmp_path):
    env, bin_dir = create_stub_environment(tmp_path)
    add_symlink(bin_dir, "bash")
    add_id_stub(bin_dir, "dialout")
    populate_common_commands(bin_dir)
    for command in ["sha256sum", "stat", "find", "python3", "make"]:
        add_symlink(bin_dir, command)

    state_file = tmp_path / "systemctl_state"
    state_file.write_text("klipper.service=active\n")
    make_systemctl_stub(bin_dir, state_file)
    env["SYSTEMCTL_STATE"] = str(state_file)

    script = "\n".join(
        [
            "detect_klipper_services",
            "stop_klipper_services",
            "restart_klipper_services",
        ]
    )
    result = run_flash_script(script, env=env)
    assert result.returncode == 0
    assert "Redémarrage du service klipper.service" in result.stdout
    assert "Service klipper.service relancé" in result.stdout


def test_services_restored_after_error(tmp_path):
    env, bin_dir = create_stub_environment(tmp_path)
    add_symlink(bin_dir, "bash")
    add_id_stub(bin_dir, "dialout")
    populate_common_commands(bin_dir)
    for command in ["sha256sum", "stat", "find", "python3", "make"]:
        add_symlink(bin_dir, command)

    state_file = tmp_path / "systemctl_state"
    state_file.write_text("klipper.service=active\n")
    make_systemctl_stub(bin_dir, state_file)
    env["SYSTEMCTL_STATE"] = str(state_file)

    result = run_flash_script(
        "\n".join(
            [
                "detect_klipper_services",
                "stop_klipper_services",
                "false",
            ]
        ),
        env=env,
    )
    assert result.returncode != 0
    assert "Redémarrage du service klipper.service" in result.stdout
    assert "Service klipper.service relancé" in result.stdout


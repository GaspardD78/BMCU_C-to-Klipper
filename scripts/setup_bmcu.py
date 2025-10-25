#!/usr/bin/env python3
"""Utility to deploy BMCU-C support files into an existing Klipper installation."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]


def _available_firmware() -> List[Path]:
    firmware_dir = REPO_ROOT / "firmware"
    return sorted(firmware_dir.glob("*.bin"))


def _slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def _read_alias_overrides() -> Dict[str, str]:
    readme_path = REPO_ROOT / "firmware" / "README.md"
    if not readme_path.exists():
        return {}

    content = readme_path.read_text(encoding="utf-8")
    start_marker = "<!-- firmware-aliases:start -->"
    end_marker = "<!-- firmware-aliases:end -->"
    if start_marker not in content or end_marker not in content:
        return {}

    aliases: Dict[str, str] = {}
    between = content.split(start_marker, 1)[1].split(end_marker, 1)[0]
    for line in between.splitlines():
        match = re.search(r"\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|", line)
        if match:
            alias, filename = match.groups()
            aliases[alias.strip()] = filename.strip()
    return aliases


def _build_firmware_aliases() -> Dict[str, Path]:
    overrides = _read_alias_overrides()
    result: Dict[str, Path] = {}
    for firmware_path in _available_firmware():
        alias = next(
            (
                alias
                for alias, filename in overrides.items()
                if firmware_path.name == filename
            ),
            None,
        )
        if alias is None:
            alias = _slugify(firmware_path.stem)
        result[alias] = firmware_path
    return result


def _copy_file(src: Path, dest: Path, dry_run: bool) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dry_run:
        print(f"[dry-run] would copy {src} -> {dest}")
        return
    print(f"Copying {src} -> {dest}")
    shutil.copy2(src, dest)


def _ensure_includes(lines: List[str], includes: Iterable[str]) -> Tuple[List[str], bool]:
    updated = False
    result = list(lines)
    existing = {line.strip() for line in lines}
    for include in includes:
        if include not in existing:
            result.append(include + "\n")
            updated = True
    if updated and result and result[-1] != "\n":
        result.append("\n")
    return result, updated


def _detect_serial_symlink(base: Path | None = None) -> Optional[str]:
    base = base or Path("/dev/serial/by-id")
    if not base.exists():
        return None

    patterns = ("usb-klipper_ch32v203*", "wch-link*")
    candidates: dict[str, Path] = {}
    for pattern in patterns:
        for match in base.glob(pattern):
            candidates.setdefault(str(match), match)

    matches = [candidates[key] for key in sorted(candidates)]

    if not matches:
        return None
    if len(matches) == 1:
        return str(matches[0])

    raise RuntimeError(
        "Plusieurs périphériques Klipper détectés. "
        "Veuillez préciser --serial-path pour sélectionner le bon lien."
    )


def _ensure_mcu_section(lines: List[str], serial_path: Optional[str]) -> Tuple[List[str], bool]:
    marker = "[mcu bmcu_c]"
    for line in lines:
        if line.strip().lower() == marker:
            return lines, False

    template = [
        "\n",
        "[mcu bmcu_c]\n",
        "restart_method: command\n",
        "baud: 1250000\n",
        "# use_custom_baudrate: True  # Uncomment si PySerial expose set_custom_baudrate()\n",
        "# fallback_baud: 250000      # À déclarer si le BMCU a été recompilé avec un autre débit\n",
    ]

    if serial_path:
        template.insert(2, f"serial: {serial_path}\n")

    result = list(lines)
    result.extend(template)
    return result, True


def _update_printer_cfg(
    printer_cfg: Path,
    dry_run: bool,
    create_backup: bool,
    serial_path: Optional[str],
) -> None:
    if not printer_cfg.exists():
        raise FileNotFoundError(f"printer.cfg not found: {printer_cfg}")

    content = printer_cfg.read_text().splitlines(keepends=True)
    content, added_includes = _ensure_includes(
        content, ["[include bmcu_config.cfg]", "[include bmcu_macros.cfg]"]
    )
    content, added_mcu = _ensure_mcu_section(content, serial_path)

    if not (added_includes or added_mcu):
        print("printer.cfg already contains BMCU sections; no changes needed.")
        return

    if dry_run:
        print("[dry-run] would update printer.cfg with BMCU includes and MCU section")
        return

    if create_backup:
        backup_path = printer_cfg.with_suffix(printer_cfg.suffix + ".bak")
        shutil.copy2(printer_cfg, backup_path)
        print(f"Backup created: {backup_path}")

    printer_cfg.write_text("".join(content))
    print(f"Updated {printer_cfg}")


def _flash_firmware(klipper_path: Path, flash_device: str | None, dry_run: bool) -> None:
    cmd: List[str] = ["make", "flash"]
    if flash_device:
        cmd.append(f"FLASH_DEVICE={flash_device}")

    print("Running", " ".join(cmd), "in", klipper_path)
    if dry_run:
        print("[dry-run] skipping make flash execution")
        return

    try:
        subprocess.run(
            cmd,
            cwd=klipper_path,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        if exc.stdout:
            print("--- make flash stdout ---", file=sys.stderr)
            print(exc.stdout, file=sys.stderr, end="" if exc.stdout.endswith("\n") else "\n")
        if exc.stderr:
            print("--- make flash stderr ---", file=sys.stderr)
            print(exc.stderr, file=sys.stderr, end="" if exc.stderr.endswith("\n") else "\n")
        raise RuntimeError("make flash failed") from exc



def parse_args() -> argparse.Namespace:
    firmware_aliases = _build_firmware_aliases()
    parser = argparse.ArgumentParser(
        description=(
            "Automatise la copie des fichiers BMCU-C vers une installation Klipper "
            "et facilite le flash du microcontrôleur."
        )
    )
    parser.add_argument("--klipper-path", type=Path, required=True, help="Répertoire de l'installation Klipper hôte")
    parser.add_argument(
        "--config-path", type=Path, required=True, help="Répertoire de configuration Klipper (généralement ~/klipper_config)"
    )
    parser.add_argument(
        "--printer-config", type=Path, help="Chemin vers printer.cfg pour y injecter les includes BMCU"
    )
    parser.add_argument(
        "--serial-path",
        help=(
            "Chemin vers le lien /dev/serial/by-id/ du BMCU. Si omis, une détection automatique est tentée."
        ),
    )
    parser.add_argument(
        "--firmware-variant",
        choices=sorted(firmware_aliases),
        help="Nom du binaire firmware à copier depuis le dépôt",
    )
    parser.add_argument(
        "--firmware-dest",
        type=Path,
        help="Destination du binaire firmware sélectionné (par exemple ~/klipper/out/klipper.bin)",
    )
    parser.add_argument(
        "--flash",
        action="store_true",
        help="Lancer 'make flash' dans --klipper-path après la copie des fichiers",
    )
    parser.add_argument(
        "--flash-device",
        help="Valeur à fournir à FLASH_DEVICE lors de l'appel à make flash",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Ne pas créer de sauvegarde .bak de printer.cfg avant modification",
    )
    parser.add_argument("--dry-run", action="store_true", help="Afficher les actions sans les exécuter")
    parser.add_argument(
        "--list-firmware",
        action="store_true",
        help="Lister les binaires firmware disponibles et quitter",
    )
    args = parser.parse_args()
    setattr(args, "firmware_aliases", firmware_aliases)
    return args


def main() -> int:
    args = parse_args()
    firmware_aliases: dict[str, Path] = getattr(args, "firmware_aliases", {})

    if args.list_firmware:
        print("Firmware disponibles :")
        for alias, firmware_path in sorted(firmware_aliases.items()):
            print(f"  - {alias}: {firmware_path.name}")
        return 0

    klipper_path: Path = args.klipper_path.expanduser().resolve()
    config_path: Path = args.config_path.expanduser().resolve()

    if not klipper_path.exists():
        print(f"Erreur : le répertoire Klipper {klipper_path} n'existe pas.", file=sys.stderr)
        return 1

    required_files = {
        "Makefile": klipper_path / "Makefile",
        "klippy/__init__.py": klipper_path / "klippy" / "__init__.py",
    }
    missing = [name for name, path in required_files.items() if not path.exists()]
    if missing:
        missing_list = ", ".join(missing)
        print(
            "Erreur : les fichiers suivants sont introuvables dans"
            f" {klipper_path} : {missing_list}. Vérifiez que --klipper-path pointe"
            " vers la racine de l'installation Klipper.",
            file=sys.stderr,
        )
        return 1

    if not config_path.exists():
        print(f"Erreur : le répertoire de configuration {config_path} n'existe pas.", file=sys.stderr)
        return 1

    extras_src = REPO_ROOT / "klipper" / "klippy" / "extras" / "bmcu.py"
    extras_dest = klipper_path / "klippy" / "extras" / "bmcu.py"
    _copy_file(extras_src, extras_dest, args.dry_run)

    config_src_files = [
        (REPO_ROOT / "config" / "bmcu_config.cfg", config_path / "bmcu_config.cfg"),
        (REPO_ROOT / "config" / "bmcu_macros.cfg", config_path / "bmcu_macros.cfg"),
        (REPO_ROOT / "klipper" / "config" / "boards" / "bmcu_c.cfg", config_path / "boards" / "bmcu_c.cfg"),
    ]

    for src, dest in config_src_files:
        _copy_file(src, dest, args.dry_run)

    if args.printer_config:
        serial_path: Optional[str] = args.serial_path
        if serial_path is None:
            try:
                detected = _detect_serial_symlink()
            except RuntimeError as exc:
                print(f"Erreur : {exc}", file=sys.stderr)
                return 1
            serial_path = detected
            if serial_path:
                print(f"Lien série détecté automatiquement : {serial_path}")
        if serial_path is None:
            print(
                "Erreur : aucun lien série n'a été détecté. "
                "Veuillez fournir --serial-path pour poursuivre.",
                file=sys.stderr,
            )
            return 1
        printer_cfg = args.printer_config.expanduser().resolve()
        try:
            _update_printer_cfg(printer_cfg, args.dry_run, not args.no_backup, serial_path)
        except FileNotFoundError as exc:
            print(f"Erreur : {exc}", file=sys.stderr)
            return 1

    if args.firmware_variant and not args.firmware_dest:
        print("Erreur : --firmware-dest est requis lorsque --firmware-variant est fourni.", file=sys.stderr)
        return 1

    if args.firmware_dest:
        if not args.firmware_variant:
            print("Erreur : --firmware-variant doit être précisé pour copier un firmware.", file=sys.stderr)
            return 1
        if args.firmware_variant not in firmware_aliases:
            print(
                "Erreur : le firmware demandé n'existe pas dans le dépôt. Utilisez --list-firmware pour voir les options.",
                file=sys.stderr,
            )
            return 1
        firmware_src = firmware_aliases[args.firmware_variant]
        firmware_dest = args.firmware_dest.expanduser().resolve()
        _copy_file(firmware_src, firmware_dest, args.dry_run)

    if args.flash:
        try:
            _flash_firmware(klipper_path, args.flash_device, args.dry_run)
        except RuntimeError as exc:
            print(f"Erreur : {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

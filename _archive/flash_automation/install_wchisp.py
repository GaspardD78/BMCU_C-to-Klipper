#!/usr/bin/env python3
"""Télécharge et installe le binaire wchisp depuis les releases GitHub.

Ce script est pensé pour les environnements où ``pip install wchisp``
n'est pas disponible (cas des machines ARM 64 bits comme le CB2 sous
Armbian). Il récupère l'archive officielle correspondant à
l'architecture locale puis installe le binaire dans ``.venv/bin`` lorsqu'il
est exécuté depuis un environnement virtuel. À défaut, le binaire est
placé dans ``~/.local/bin``.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import stat
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath


SUPPORTED_SUFFIXES = {
    "x86_64": "linux-x64",
    "aarch64": "linux-aarch64",
}

ARCH_ALIASES = {
    "amd64": "x86_64",
    "arm64": "aarch64",
    "armv7": "armv7l",
    "armv7l": "armv7l",
    "armv8l": "armv7l",
    "armhf": "armv7l",
    "armv6": "armv6l",
    "armv6l": "armv6l",
    "armel": "armv6l",
    "i386": "i686",
    "i486": "i686",
    "i586": "i686",
    "i686": "i686",
}

MANUAL_DOC_PATH = Path(__file__).resolve().parent / "docs" / "wchisp_manual_install.md"

DEFAULT_RELEASE = "v0.3.0"
DEFAULT_BASE_URL = "https://github.com/ch32-rs/wchisp/releases/download"


def resolve_machine() -> str:
    """Retourne l'architecture machine en tenant compte d'un override éventuel."""

    override = os.environ.get("WCHISP_ARCH_OVERRIDE")
    if override:
        return override.lower()
    return platform.machine().lower()


def normalize_machine(machine: str) -> str:
    """Normalise les noms d'architecture connus."""

    return ARCH_ALIASES.get(machine, machine)


def ensure_linux_platform() -> None:
    if platform.system().lower() != "linux":
        raise RuntimeError(
            "Seules les plates-formes Linux sont prises en charge pour l'installation automatique."
        )


def compute_download_plan(release: str, base_url: str) -> tuple[str, str, str, str | None]:
    """Calcule l'URL de téléchargement et les métadonnées associées."""

    ensure_linux_platform()

    raw_machine = resolve_machine()
    machine = normalize_machine(raw_machine)

    suffix = SUPPORTED_SUFFIXES.get(machine)
    if suffix:
        asset = f"wchisp-{release}-{suffix}.tar.gz"
        url = f"{base_url}/{release}/{asset}"
        return url, asset, raw_machine, None

    fallback_url = os.environ.get("WCHISP_FALLBACK_ARCHIVE_URL")
    if fallback_url:
        asset = os.environ.get("WCHISP_FALLBACK_ARCHIVE_NAME") or fallback_url.rstrip("/").split("/")[-1]
        asset = asset.split("?")[0]
        if not asset:
            raise RuntimeError(
                "Impossible de déterminer le nom de fichier de l'archive fournie via WCHISP_FALLBACK_ARCHIVE_URL."
            )
        checksum = os.environ.get("WCHISP_FALLBACK_CHECKSUM")
        return fallback_url, asset, raw_machine, checksum

    manual_doc = os.environ.get("WCHISP_MANUAL_DOC", str(MANUAL_DOC_PATH))
    raise RuntimeError(
        "Aucun binaire pré-compilé n'est disponible pour l'architecture "
        f"'{raw_machine}'. Fournissez WCHISP_FALLBACK_ARCHIVE_URL (et optionnellement WCHISP_FALLBACK_CHECKSUM) "
        f"ou suivez les instructions de '{manual_doc}' pour compiler wchisp, puis exportez WCHISP_BIN."
    )


def determine_install_dir() -> Path:
    """Détermine le répertoire d'installation du binaire."""

    virtual_env = os.environ.get("VIRTUAL_ENV")
    if virtual_env:
        return Path(virtual_env).expanduser().resolve() / "bin"

    # Fallback sur ~/.local/bin comme le ferait `pip --user`
    return Path.home() / ".local" / "bin"


def download_archive(url: str, destination: Path) -> None:
    """Télécharge le fichier ``url`` dans ``destination``."""

    try:
        with urllib.request.urlopen(url) as response, destination.open("wb") as target:
            shutil.copyfileobj(response, target)
    except urllib.error.URLError as err:
        raise RuntimeError(f"Échec du téléchargement de wchisp ({err}).") from err


def verify_checksum(path: Path, expected: str | None) -> None:
    """Vérifie la somme de contrôle SHA-256 si ``expected`` est fournie."""

    if not expected:
        print(
            "WARNING: aucune somme de contrôle n'a été fournie pour l'archive wchisp. Vérifiez la provenance du fichier.",
            file=sys.stderr,
        )
        return

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)

    actual = digest.hexdigest()
    if actual.lower() != expected.lower():
        raise RuntimeError(
            "La somme de contrôle SHA-256 de l'archive wchisp ne correspond pas à la valeur attendue."
        )


def _is_safe_member(member: tarfile.TarInfo, destination_root: Path) -> bool:
    """Vérifie que le membre peut être extrait sans échapper ``destination_root``."""

    name = member.name
    if not name:
        return False

    if member.islnk() or member.issym():
        return False

    if name.startswith("/") or name.startswith("\\"):
        return False

    posix_path = PurePosixPath(name)
    if posix_path.is_absolute():
        return False

    if any(part in {"..", ""} for part in posix_path.parts):
        return False

    member_path = Path(*posix_path.parts)
    target_path = destination_root.joinpath(member_path).resolve(strict=False)
    try:
        target_path.relative_to(destination_root)
    except ValueError:
        return False

    return True


def extract_binary(archive_path: Path, workdir: Path) -> Path:
    """Extrait l'archive dans ``workdir`` et retourne le chemin du binaire wchisp."""

    try:
        with tarfile.open(archive_path, mode="r:gz") as tar:
            members = tar.getmembers()
            destination_root = workdir.resolve()
            for member in members:
                if not _is_safe_member(member, destination_root):
                    raise RuntimeError(
                        "L'archive wchisp contient un membre avec un chemin potentiellement dangereux: "
                        f"{member.name!r}."
                    )
            tar.extractall(path=workdir, members=members, filter='data')
    except (OSError, tarfile.TarError) as err:
        raise RuntimeError("Impossible d'extraire l'archive wchisp.") from err

    for candidate in workdir.rglob("wchisp"):
        if candidate.is_file():
            return candidate

    raise RuntimeError("Le binaire wchisp est introuvable dans l'archive téléchargée.")


def install_binary(source: Path, destination_dir: Path) -> Path:
    """Copie ``source`` dans ``destination_dir`` et rend le fichier exécutable."""

    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / "wchisp"

    try:
        shutil.copy2(source, destination)
    except OSError as err:
        raise RuntimeError(f"Impossible de copier wchisp vers {destination}.") from err

    mode = destination.stat().st_mode
    destination.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return destination


def main() -> int:
    release = os.environ.get("WCHISP_RELEASE", DEFAULT_RELEASE)
    base_url = os.environ.get("WCHISP_BASE_URL", DEFAULT_BASE_URL)

    try:
        url, asset, machine, checksum = compute_download_plan(release, base_url)
    except RuntimeError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    print(f"Téléchargement de wchisp ({url})…")
    print(f"Archive wchisp sélectionnée : {asset} (machine détectée : {machine})")

    with tempfile.TemporaryDirectory() as tmp_str:
        tmpdir = Path(tmp_str)
        archive_path = tmpdir / "wchisp.tar.gz"
        download_archive(url, archive_path)

        try:
            verify_checksum(archive_path, checksum)
        except RuntimeError as err:
            print(f"ERROR: {err}", file=sys.stderr)
            return 1

        extract_dir = tmpdir / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)
        try:
            binary_path = extract_binary(archive_path, extract_dir)
        except RuntimeError as err:
            print(f"ERROR: {err}", file=sys.stderr)
            return 1

        install_dir = determine_install_dir()
        try:
            installed_path = install_binary(binary_path, install_dir)
        except RuntimeError as err:
            print(f"ERROR: {err}", file=sys.stderr)
            return 1

    print(f"wchisp installé dans {installed_path} (machine détectée : {machine})")
    print("Assurez-vous que ce dossier figure dans votre PATH avant de lancer le flash.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

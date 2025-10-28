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

import os
import platform
import shutil
import stat
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_RELEASE = "v0.3.0"
DEFAULT_BASE_URL = "https://github.com/ch32-rs/wchisp/releases/download"


def detect_archive_suffix() -> str:
    """Retourne le suffixe d'archive à télécharger pour l'architecture locale."""

    system = platform.system().lower()
    if system != "linux":
        raise RuntimeError(
            "Seules les plates-formes Linux sont prises en charge pour l'installation automatique."
        )

    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return "linux-x64"
    if machine in {"aarch64", "arm64"}:
        return "linux-aarch64"

    raise RuntimeError(
        f"Aucun binaire pré-compilé n'est disponible pour l'architecture '{machine}'."
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


def extract_binary(archive_path: Path, workdir: Path) -> Path:
    """Extrait l'archive dans ``workdir`` et retourne le chemin du binaire wchisp."""

    try:
        with tarfile.open(archive_path, mode="r:gz") as tar:
            tar.extractall(path=workdir)
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
        suffix = detect_archive_suffix()
    except RuntimeError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    url = f"{base_url}/{release}/wchisp-{release}-{suffix}.tar.gz"
    print(f"Téléchargement de wchisp ({url})…")

    with tempfile.TemporaryDirectory() as tmp_str:
        tmpdir = Path(tmp_str)
        archive_path = tmpdir / "wchisp.tar.gz"
        download_archive(url, archive_path)

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

    print(f"wchisp installé dans {installed_path}")
    print("Assurez-vous que ce dossier figure dans votre PATH avant de lancer le flash.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

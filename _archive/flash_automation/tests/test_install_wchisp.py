"""Tests de sécurisation de l'extraction pour install_wchisp."""

from __future__ import annotations

import io
import sys
import tarfile
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flash_automation.install_wchisp import extract_binary


def create_archive(tmp_path: Path, members: list[tuple[str, bytes]]) -> Path:
    archive_path = tmp_path / "wchisp.tar.gz"
    with tarfile.open(archive_path, mode="w:gz") as tar:
        for name, data in members:
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return archive_path


def test_extract_binary_accepts_safe_members(tmp_path: Path) -> None:
    archive_path = create_archive(
        tmp_path,
        [("wchisp-0.3.0/wchisp", b"#!/bin/echo wchisp")],
    )

    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()

    binary_path = extract_binary(archive_path, extract_dir)

    assert binary_path == extract_dir / "wchisp-0.3.0" / "wchisp"
    assert binary_path.exists()
    assert binary_path.is_file()


def test_extract_binary_rejects_absolute_paths(tmp_path: Path) -> None:
    archive_path = create_archive(tmp_path, [("/absolute/wchisp", b"bad")])
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()

    with pytest.raises(RuntimeError, match="dangereux"):
        extract_binary(archive_path, extract_dir)


def test_extract_binary_rejects_traversal(tmp_path: Path) -> None:
    archive_path = create_archive(tmp_path, [("../evil/wchisp", b"bad")])
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()

    with pytest.raises(RuntimeError, match="dangereux"):
        extract_binary(archive_path, extract_dir)


def test_extract_binary_rejects_symlinks(tmp_path: Path) -> None:
    archive_path = tmp_path / "wchisp_symlink.tar.gz"
    with tarfile.open(archive_path, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="wchisp_link")
        info.type = tarfile.SYMTYPE
        info.linkname = "wchisp"
        tar.addfile(info)

    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()

    with pytest.raises(RuntimeError, match="dangereux"):
        extract_binary(archive_path, extract_dir)

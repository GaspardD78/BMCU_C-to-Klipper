#!/usr/bin/env python3
"""Guardrails for repository artifacts.

This script enforces repository policies by checking for oversized files and
forbidden paths. It is intended to be used locally and in CI to prevent binary
blobs or cached assets from being committed by mistake.
"""
from __future__ import annotations

import argparse
import fnmatch
import logging
from logging import handlers
import subprocess
import sys
from pathlib import Path
from typing import List, Sequence, Tuple

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
LOGGER_NAME = "artifact_guard"
DEFAULT_LOG_FILE = "artifact_guard.log"


def configure_logging(log_directory: Path) -> logging.Logger:
    """Configure console and rotating file logging."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    log_directory.mkdir(parents=True, exist_ok=True)
    file_handler = handlers.RotatingFileHandler(
        log_directory / DEFAULT_LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=4,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def get_repo_root(start_path: Path) -> Path:
    """Return the git repository root for the given path."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:  # pragma: no cover - defensive
        raise RuntimeError("Unable to determine git repository root") from exc

    return Path(result.stdout.strip())


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate repository artifacts")
    parser.add_argument(
        "--threshold-mb",
        type=float,
        default=50.0,
        help="Maximum allowed file size in megabytes (default: 50)",
    )
    parser.add_argument(
        "--forbidden-config",
        type=Path,
        default=None,
        help="Path to a file containing newline-separated forbidden path patterns",
    )
    parser.add_argument(
        "--forbidden",
        dest="forbidden_patterns",
        action="append",
        default=None,
        help="Additional forbidden path patterns (supports glob syntax)",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=Path("logs"),
        help="Directory where log files should be written",
    )
    return parser.parse_args()


def load_patterns(config_path: Path | None) -> List[str]:
    patterns: List[str] = []
    if not config_path:
        return patterns

    if not config_path.exists():
        raise FileNotFoundError(f"Forbidden paths configuration not found: {config_path}")

    for line in config_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.append(stripped)
    return patterns


def list_tracked_files(repo_root: Path) -> List[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive
        raise RuntimeError("Unable to list tracked files") from exc

    raw_files = result.stdout.split(b"\0")
    paths = [repo_root / Path(f.decode("utf-8")) for f in raw_files if f]
    return paths


def find_large_files(files: Sequence[Path], threshold_bytes: int) -> List[Tuple[Path, int]]:
    oversized: List[Tuple[Path, int]] = []
    for file_path in files:
        try:
            size = file_path.stat().st_size
        except FileNotFoundError:
            continue
        if size > threshold_bytes:
            oversized.append((file_path, size))
    return oversized


def find_forbidden_paths(files: Sequence[Path], patterns: Sequence[str], repo_root: Path) -> List[Path]:
    violations: List[Path] = []
    if not patterns:
        return violations

    for file_path in files:
        relative = file_path.relative_to(repo_root).as_posix()
        for pattern in patterns:
            if relative == pattern:
                violations.append(file_path)
                break
            if fnmatch.fnmatch(relative, pattern):
                violations.append(file_path)
                break
            if relative.startswith(pattern.rstrip("*/")):
                violations.append(file_path)
                break
    return violations


def format_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024 or unit == "GB":
            return f"{size_bytes:.2f} {unit}" if unit != "B" else f"{size_bytes} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} GB"


def main() -> int:
    args = parse_arguments()
    repo_root = get_repo_root(Path.cwd())
    logger = configure_logging(repo_root / args.log_dir)
    logger.debug("Repository root resolved to %s", repo_root)

    threshold_bytes = int(args.threshold_mb * 1024 * 1024)
    if threshold_bytes <= 0:
        logger.error("Threshold must be a positive number of bytes")
        return 2

    try:
        tracked_files = list_tracked_files(repo_root)
    except RuntimeError as exc:
        logger.error(str(exc))
        return 2

    logger.info("Checking %d tracked files with threshold %.2f MB", len(tracked_files), args.threshold_mb)

    patterns = []
    try:
        patterns.extend(load_patterns(args.forbidden_config))
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 2

    if args.forbidden_patterns:
        patterns.extend(args.forbidden_patterns)

    oversized_files = find_large_files(tracked_files, threshold_bytes)
    forbidden_files = find_forbidden_paths(tracked_files, patterns, repo_root)

    if oversized_files:
        logger.error("Detected %d file(s) exceeding %.2f MB:", len(oversized_files), args.threshold_mb)
        for path, size in oversized_files:
            rel_path = path.relative_to(repo_root).as_posix()
            logger.error("  - %s (%s)", rel_path, format_size(size))

    if forbidden_files:
        logger.error("Detected %d forbidden path violation(s):", len(forbidden_files))
        for path in forbidden_files:
            rel_path = path.relative_to(repo_root).as_posix()
            logger.error("  - %s", rel_path)

    if oversized_files or forbidden_files:
        logger.error("Repository policy checks failed")
        return 1

    logger.info("Repository policy checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

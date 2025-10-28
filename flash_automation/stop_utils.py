"""Utilities for handling manual stop requests and repository cleanup."""

from __future__ import annotations

import logging
import os
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional, Set


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXTERNAL_LOG_ROOT = Path.home() / "BMCU_C_to_Klipper_logs"


class StopRequested(Exception):
    """Raised when the user requests to stop the automation."""


class StopController:
    """Coordinates manual stop requests across the automation scripts."""

    def __init__(self, *, enable_input_listener: bool = True) -> None:
        self._stop_event = threading.Event()
        self._processes: Set[subprocess.Popen[str]] = set()
        self._lock = threading.Lock()
        self._enable_input_listener = enable_input_listener
        self._listener_thread: Optional[threading.Thread] = None
        self._signals_registered = False

    @property
    def stop_requested(self) -> bool:
        return self._stop_event.is_set()

    def start(self) -> None:
        """Starts signal handling and the optional input listener."""

        if not self._signals_registered:
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, self._signal_handler)
            self._signals_registered = True

        if self._enable_input_listener and self._listener_thread is None:
            self._listener_thread = threading.Thread(
                target=self._listen_for_stop,
                name="stop-listener",
                daemon=True,
            )
            self._listener_thread.start()

    def request_stop(self, *, reason: str | None = None) -> None:
        """Triggers the stop event and terminates registered processes."""

        if self._stop_event.is_set():
            return

        message = "Arrêt manuel demandé par l'utilisateur"
        if reason:
            message = f"{message} ({reason})"
        logging.getLogger(__name__).warning(message)
        print(message, file=sys.stderr)
        self._stop_event.set()

        with self._lock:
            for process in list(self._processes):
                try:
                    process.terminate()
                except Exception:
                    continue

        try:
            threading.interrupt_main()
        except RuntimeError:
            pass

    def register_process(self, process: subprocess.Popen[str]) -> None:
        with self._lock:
            self._processes.add(process)

    def unregister_process(self, process: subprocess.Popen[str]) -> None:
        with self._lock:
            self._processes.discard(process)

    def raise_if_requested(self) -> None:
        if self._stop_event.is_set():
            raise StopRequested()

    def wait(self, timeout: float) -> bool:
        """Waits for the stop event for a given timeout."""

        return self._stop_event.wait(timeout)

    def _signal_handler(self, signum, _frame) -> None:  # type: ignore[override]
        self.request_stop(reason=f"signal {signum}")

    def _listen_for_stop(self) -> None:
        print("Tapez 'STOP' puis Entrée pour interrompre l'automatisation.")
        while not self._stop_event.is_set():
            try:
                user_input = input()
            except EOFError:
                return
            if user_input.strip().lower() == "stop":
                self.request_stop(reason="commande utilisateur")
                return


def resolve_log_root(candidate: Path) -> tuple[Path, bool]:
    """Ensures the log directory is located outside of the repository."""

    resolved = candidate.expanduser().resolve()
    repo = REPO_ROOT.resolve()
    if resolved == repo or repo in resolved.parents:
        return DEFAULT_EXTERNAL_LOG_ROOT.resolve(), True
    return resolved, False


def cleanup_repository(repo_root: Path = REPO_ROOT) -> None:
    """Removes the repository directory from disk."""

    if not repo_root.exists():
        return

    try:
        os.chdir(repo_root.parent)
    except OSError:
        pass

    try:
        shutil.rmtree(repo_root)
    except Exception as err:  # pragma: no cover - filesystem failure
        print(f"Échec de la suppression du dépôt {repo_root}: {err}", file=sys.stderr)
    else:
        print(f"Dépôt {repo_root} supprimé", file=sys.stderr)


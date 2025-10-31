"""Outils de supervision d'exécution des commandes shell.

Ce module fournit une exécution "streamée" des commandes avec détection des
périodes d'inactivité et instrumentation de la progression. Il est pensé pour
être partagé entre les différents points d'entrée du dossier ``flash_automation``
afin d'offrir une expérience cohérente quelle que soit la commande lancée
(compilation, téléchargement des dépendances, flash, etc.).
"""

from __future__ import annotations

import codecs
import itertools
import locale
import logging
import os
import re
import select
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence


LOG = logging.getLogger(__name__)


def _default_encoding() -> str:
    encoding = locale.getpreferredencoding(False)
    if not encoding:
        encoding = sys.getdefaultencoding() or "utf-8"
    return encoding


def _progress_bar(percent: float, *, width: int = 20) -> str:
    percent = max(0.0, min(100.0, percent))
    filled = int(round(width * percent / 100.0))
    return f"[{'#' * filled}{'.' * (width - filled)}]"


@dataclass
class _StreamEvent:
    """Petite structure pour représenter un fragment de sortie."""

    text: str
    terminator: Optional[str]


class _CommandMonitor:
    """Gère l'état de la commande (spinner, progression, journalisation)."""

    def __init__(
        self,
        *,
        printable_command: str,
        logger: logging.Logger,
        inactivity_threshold: float = 2.0,
        spinner_interval: float = 0.5,
        spinner_frames: Iterable[str] | None = None,
    ) -> None:
        self.printable_command = printable_command
        self.logger = logger
        self.inactivity_threshold = max(0.1, inactivity_threshold)
        self.spinner_interval = max(0.1, spinner_interval)
        self.spinner_frames = itertools.cycle(spinner_frames or ["|", "/", "-", "\\"])
        self._last_activity = time.monotonic()
        self._next_spinner = self._last_activity + self.inactivity_threshold
        self._spinner_active = False

    def record_activity(self) -> None:
        self._last_activity = time.monotonic()
        self._next_spinner = self._last_activity + self.inactivity_threshold
        self._spinner_active = False

    def maybe_emit_spinner(self) -> None:
        now = time.monotonic()
        if now < self._next_spinner:
            return
        frame = next(self.spinner_frames)
        self.logger.info("%s Commande toujours en cours (%s)", frame, self.printable_command)
        self._spinner_active = True
        self._next_spinner = now + self.spinner_interval

    def emit_output(self, text: str) -> None:
        if text:
            self.logger.info("[sortie] %s", text)
        self.record_activity()

    def emit_progress(self, label: str, percent: float, detail: Optional[str] = None) -> None:
        bar = _progress_bar(percent)
        message = f"[progress] {label} {bar} {percent:5.1f}%"
        if detail:
            message = f"{message} {detail}"
        self.logger.info("%s", message)
        self.record_activity()

    def emit_status(self, label: str) -> None:
        self.logger.info("[progress] %s", label)
        self.record_activity()


class _ProgressHook:
    """Interface simple pour enrichir la progression."""

    def process(self, event: _StreamEvent, monitor: _CommandMonitor) -> bool:  # pragma: no cover - interface
        raise NotImplementedError


class _GitProgressHook(_ProgressHook):
    """Analyse les sorties de Git (clone/fetch)."""

    _PATTERN = re.compile(
        r"(?P<phase>(?:Counting|Compressing|Receiving|Resolving|Updating) objects):\s+(?P<percent>\d{1,3})%(?P<tail>.*)"
    )

    def __init__(self, label: str) -> None:
        self.label = label

    def process(self, event: _StreamEvent, monitor: _CommandMonitor) -> bool:
        if not event.text:
            return False
        handled = False
        segments = event.text.split("\r") if "\r" in event.text else [event.text]
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue
            match = self._PATTERN.search(segment)
            if not match:
                continue
            percent = float(match.group("percent"))
            tail = match.group("tail").strip(" ,")
            phase = match.group("phase").lower()
            detail = tail or None
            monitor.emit_progress(f"{self.label} ({phase})", percent, detail)
            handled = True
        return handled


class _BuildProgressHook(_ProgressHook):
    """Interprète les sorties type CMake/Ninja/Make."""

    _PERCENT_RE = re.compile(r"\[\s*(?P<percent>\d{1,3})%\]")
    _RATIO_RE = re.compile(r"(?P<current>\d+)\s*/\s*(?P<total>\d+)")

    def process(self, event: _StreamEvent, monitor: _CommandMonitor) -> bool:
        text = event.text.strip()
        if not text:
            return False
        match = self._PERCENT_RE.search(text)
        if match:
            percent = float(match.group("percent"))
            detail = text.replace(match.group(0), "").strip()
            monitor.emit_progress("compilation", percent, detail or None)
            return True

        match = self._RATIO_RE.search(text)
        if match:
            total = int(match.group("total"))
            current = int(match.group("current"))
            if total > 0 and current <= total:
                percent = (current / total) * 100.0
                monitor.emit_progress("compilation", percent, text)
                return True
        return False


def _split_events(buffer: str) -> tuple[list[_StreamEvent], str]:
    events: list[_StreamEvent] = []
    start = 0
    i = 0
    length = len(buffer)
    while i < length:
        char = buffer[i]
        if char == "\r":
            terminator = "\r"
            # Consommer un éventuel \n juste après pour éviter de traiter deux fois
            if i + 1 < length and buffer[i + 1] == "\n":
                terminator = "\n"
                events.append(_StreamEvent(buffer[start:i], terminator))
                i += 2
                start = i
                continue
            events.append(_StreamEvent(buffer[start:i], terminator))
            i += 1
            start = i
            continue
        if char == "\n":
            events.append(_StreamEvent(buffer[start:i], "\n"))
            i += 1
            start = i
            continue
        i += 1

    remainder = buffer[start:]
    return events, remainder


def _prepare_process(
    command: Sequence[str],
    *,
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
) -> subprocess.Popen[bytes]:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    return subprocess.Popen(
        list(command),
        cwd=str(cwd) if cwd else None,
        env=full_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
    )


def monitor_process(
    process: subprocess.Popen[bytes],
    *,
    printable_command: str,
    logger: logging.Logger,
    hooks: Sequence[_ProgressHook] | None = None,
    inactivity_threshold: float = 2.0,
    spinner_interval: float = 0.5,
    stop_check: Optional[Callable[[], None]] = None,
) -> int:
    """Lit et journalise la sortie d'un ``Popen`` jusqu'à sa terminaison."""

    stdout = process.stdout
    if stdout is None:
        raise RuntimeError("Le processus n'expose pas stdout")

    encoding = _default_encoding()
    decoder = codecs.getincrementaldecoder(encoding)(errors="replace")
    monitor = _CommandMonitor(
        printable_command=printable_command,
        logger=logger,
        inactivity_threshold=inactivity_threshold,
        spinner_interval=spinner_interval,
    )

    hooks = list(hooks or [])
    buffer = ""
    poll_timeout = min(0.2, inactivity_threshold / 2)
    if poll_timeout <= 0:
        poll_timeout = 0.1

    while True:
        if stop_check is not None:
            stop_check()

        ready, _, _ = select.select([stdout], [], [], poll_timeout)
        if ready:
            chunk = os.read(stdout.fileno(), 4096)
            if not chunk:
                break
            buffer += decoder.decode(chunk)
            events, buffer = _split_events(buffer)
            for event in events:
                text = event.text.strip("\x00")
                handled = False
                for hook in hooks:
                    try:
                        if hook.process(event, monitor):
                            handled = True
                    except Exception:  # pragma: no cover - sécurité
                        LOG.exception("Hook de progression défaillant pour %s", printable_command)
                if not handled and text:
                    monitor.emit_output(text)
                elif handled and text:
                    monitor.record_activity()
                elif not text:
                    monitor.record_activity()
            continue

        if process.poll() is not None:
            break

        monitor.maybe_emit_spinner()

    # Fin de flux : traiter le reste
    remaining = decoder.decode(b"", final=True)
    buffer += remaining
    events, buffer = _split_events(buffer)
    for event in events:
        text = event.text.strip("\x00")
        handled = False
        for hook in hooks:
            if hook.process(event, monitor):
                handled = True
        if not handled and text:
            monitor.emit_output(text)
        elif handled and text:
            monitor.record_activity()
    if buffer.strip("\x00"):
        monitor.emit_output(buffer.strip("\x00"))

    return process.wait()


def run_command(
    command: Sequence[str],
    *,
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
    logger: logging.Logger,
    inactivity_threshold: float = 2.0,
    spinner_interval: float = 0.5,
    stop_check: Optional[Callable[[], None]] = None,
    on_process_start: Optional[Callable[[subprocess.Popen[bytes]], None]] = None,
) -> int:
    """Exécute ``command`` avec suivi de progression et spinner."""

    printable = shlex.join(list(command))
    hooks: list[_ProgressHook] = []

    normalized_first = Path(command[0]).name if command else ""
    git_label = "git"
    if normalized_first == "git":
        label_parts = [normalized_first]
        if len(command) > 1:
            label_parts.append(command[1])
        git_label = " ".join(label_parts)
    hooks.append(_GitProgressHook(git_label))

    hooks.append(_BuildProgressHook())

    process = _prepare_process(command, cwd=cwd, env=env)
    if on_process_start is not None:
        on_process_start(process)
    try:
        return monitor_process(
            process,
            printable_command=printable,
            logger=logger,
            hooks=hooks,
            inactivity_threshold=inactivity_threshold,
            spinner_interval=spinner_interval,
            stop_check=stop_check,
        )
    finally:
        process.stdout and process.stdout.close()


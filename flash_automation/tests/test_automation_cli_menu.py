"""Tests ciblés sur l'interaction du menu d'automatisation."""

from __future__ import annotations

import sys
from collections import deque
from pathlib import Path
from typing import Iterator

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

FLASH_DIR = ROOT_DIR / "flash_automation"
if str(FLASH_DIR) not in sys.path:
    sys.path.insert(0, str(FLASH_DIR))

from flash_automation import automation_cli


class _DummyStopController:
    def __init__(self) -> None:
        self._stop_requested = False
        self.finalize_calls = 0

    @property
    def stop_requested(self) -> bool:
        return self._stop_requested

    def raise_if_requested(self) -> None:
        if self._stop_requested:
            raise automation_cli.StopRequested()

    def request_stop(self, *, reason: str | None = None) -> None:  # noqa: ARG002
        self._stop_requested = True

    def finalize_stop(self) -> None:
        self._stop_requested = False
        self.finalize_calls += 1

    # Hooks unused in these tests but required by AutomationContext
    def register_process(self, _process) -> None:  # pragma: no cover - unused helper
        return

    def unregister_process(self, _process) -> None:  # pragma: no cover - unused helper
        return


@pytest.fixture(name="dummy_context")
def fixture_dummy_context(tmp_path: Path) -> Iterator[automation_cli.AutomationContext]:
    stop_controller = _DummyStopController()
    context = automation_cli.AutomationContext(
        dry_run=True,
        stop_controller=stop_controller,
        log_dir=tmp_path,
        log_file=tmp_path / "automation.log",
        report=automation_cli.AutomationReport(),
    )
    yield context


def _patched_input(monkeypatch: pytest.MonkeyPatch, values: deque[object]) -> None:
    def _fake_input(_prompt: str = "") -> str:
        if not values:
            raise AssertionError("Aucune entrée restante pour le test")
        item = values.popleft()
        if isinstance(item, BaseException):
            raise item
        return str(item)

    monkeypatch.setattr("builtins.input", _fake_input)


def test_prompt_confirmation_accepts_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _patched_input(monkeypatch, deque([""]))
    assert automation_cli.prompt_confirmation("Continuer ?", default=True, reminder_interval=0.1)


def test_prompt_confirmation_handles_invalid_then_negative(monkeypatch: pytest.MonkeyPatch) -> None:
    _patched_input(monkeypatch, deque(["peut-être", "n"]))
    assert not automation_cli.prompt_confirmation("Continuer ?", default=True, reminder_interval=0.1)


def test_interactive_menu_ctrl_c_resumes(monkeypatch: pytest.MonkeyPatch, dummy_context: automation_cli.AutomationContext) -> None:
    stop_controller = dummy_context.stop_controller  # type: ignore[assignment]

    sequence: deque[object] = deque([KeyboardInterrupt(), "X"])

    def _fake_input(prompt: str = "") -> str:  # noqa: ARG001
        item = sequence.popleft()
        if isinstance(item, KeyboardInterrupt):
            stop_controller.request_stop(reason="signal 2")
            raise item
        return str(item)

    monkeypatch.setattr("builtins.input", _fake_input)
    monkeypatch.setattr(automation_cli, "display_banner", lambda: None)

    automation_cli.interactive_menu(dummy_context)

    assert not stop_controller.stop_requested
    assert stop_controller.finalize_calls >= 1


def test_interactive_menu_recovers_after_action_interrupt(
    monkeypatch: pytest.MonkeyPatch, dummy_context: automation_cli.AutomationContext
) -> None:
    stop_controller = dummy_context.stop_controller  # type: ignore[assignment]

    test_action = automation_cli.MenuAction("1", "Essai", lambda ctx: None)
    monkeypatch.setattr(automation_cli, "ACTIONS", (test_action,), raising=False)
    monkeypatch.setattr(automation_cli, "ACTION_MAP", {"1": test_action}, raising=False)

    calls = {
        "count": 0,
    }

    def _fake_execute(action, context):  # noqa: ANN001
        calls["count"] += 1
        stop_controller.request_stop(reason="signal 2")
        raise KeyboardInterrupt()

    monkeypatch.setattr(automation_cli, "execute_action", _fake_execute)
    _patched_input(monkeypatch, deque(["1", "X"]))
    monkeypatch.setattr(automation_cli, "display_banner", lambda: None)

    automation_cli.interactive_menu(dummy_context)

    assert calls["count"] == 1
    assert not stop_controller.stop_requested
    assert stop_controller.finalize_calls >= 1

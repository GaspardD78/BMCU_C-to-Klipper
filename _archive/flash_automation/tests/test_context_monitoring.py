import logging
import sys
import textwrap
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flash_automation import context


def _run_python(script: str) -> list[str]:
    logger_name = "test.context"
    logger = logging.getLogger(logger_name)
    collected: list[str] = []

    class _ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
            collected.append(record.getMessage())

    handler = _ListHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        command = [sys.executable, "-c", textwrap.dedent(script)]
        return_code = context.run_command(
            command,
            logger=logger,
            inactivity_threshold=0.05,
            spinner_interval=0.05,
        )
    finally:
        logger.removeHandler(handler)
    assert return_code == 0
    return collected


@pytest.mark.manual("Simulation d'une commande silencieuse pour observer le spinner")
def test_spinner_is_emitted_for_silent_command():
    output = _run_python(
        """
        import time

        time.sleep(0.2)
        print('done', flush=True)
        """
    )

    assert any("Commande toujours en cours" in message for message in output)
    assert any("[sortie] done" == message for message in output)


@pytest.mark.manual("Vérifie le décodage des lignes de progression git")
def test_git_progress_lines_are_translated_to_progress_messages():
    output = _run_python(
        """
        import sys
        import time

        for value in (0, 50, 100):
            sys.stdout.write(f'Receiving objects: {value}% (1/1)\\r')
            sys.stdout.flush()
            time.sleep(0.05)
        print('Receiving objects: 100% (1/1), done.')
        """
    )

    progress_messages = [msg for msg in output if msg.startswith("[progress]")]
    assert progress_messages, f"Progression attendue, logs: {output}"
    assert any("50.0%" in msg for msg in progress_messages)

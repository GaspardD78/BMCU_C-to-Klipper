import pytest
from pathlib import Path
import shutil

@pytest.fixture
def isolated_cache(tmp_path):
    """
    Fixture to isolate tests from the real .cache directory.
    It renames the real .cache directory, creates a new empty one for the test,
    and restores the original directory after the test.
    """
    base_path = Path(__file__).resolve().parents[1]
    cache_path = base_path / ".cache"
    backup_path = base_path / ".cache.bak"

    if cache_path.exists():
        cache_path.rename(backup_path)

    # Create a fresh .cache for the test
    cache_path.mkdir()

    yield cache_path

    # Teardown: restore the original .cache
    if cache_path.exists():
        shutil.rmtree(cache_path)
    if backup_path.exists():
        backup_path.rename(cache_path)

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import db as db_module  # noqa: E402


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the db module at a throwaway SQLite file for the duration of a test."""
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test_users.db")
    db_module.init_db()
    yield db_module

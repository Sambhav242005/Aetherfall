import pytest
from app.persistence import database
from app.persistence.database import init_db


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    # Redirect every test to a unique temp DB so the suite never touches the
    # developer's real backend/aetherworld.db. Code paths that call
    # get_connection()/init_db() with no path resolve DB_PATH at call time.
    test_db = tmp_path / "test_aetherworld.db"
    monkeypatch.setattr(database, "DB_PATH", test_db)
    init_db()
    yield

import pytest
from app.persistence.database import init_db, DB_PATH


@pytest.fixture(autouse=True)
def setup_db():
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_db()
    yield
    if DB_PATH.exists():
        DB_PATH.unlink()

import os
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_PATH = PROJECT_ROOT / "data" / "test.db"

# Set this before test modules import the application and database engine.
os.environ.setdefault("DATABASE_URL", f"sqlite:///{TEST_DATABASE_PATH}")


@pytest.fixture(autouse=True)
def reset_test_database():
    from models.database import Base, SessionLocal, engine
    from services.bootstrap import seed_demo_data

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)

    yield

    Base.metadata.drop_all(bind=engine)

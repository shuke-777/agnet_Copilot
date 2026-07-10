import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.database import DATABASE_URL


class TestDatabaseConfig(unittest.TestCase):
    def test_pytest_uses_dedicated_test_database(self) -> None:
        self.assertTrue(
            DATABASE_URL.endswith("/data/test.db"),
            f"pytest should use data/test.db, got {DATABASE_URL}",
        )

import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestMainEntrypoint(unittest.TestCase):
    def test_main_file_can_be_loaded_from_outside_project_root(self) -> None:
        code = (
            "import runpy; "
            f"runpy.run_path({str(PROJECT_ROOT / 'api' / 'main.py')!r}, run_name='__not_main__')"
        )

        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd="/private/tmp",
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

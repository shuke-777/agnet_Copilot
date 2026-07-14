import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.environment import load_project_environment


class TestEnvironmentLoading(unittest.TestCase):
    def test_env_file_loads_missing_values_without_overriding_process_variables(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text(
                "LLM_PROVIDER=ollama\nLLM_MODEL=qwen3:8b\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"LLM_PROVIDER": "disabled"}, clear=True):
                loaded = load_project_environment(env_path)

                self.assertTrue(loaded)
                self.assertEqual(os.environ["LLM_PROVIDER"], "disabled")
                self.assertEqual(os.environ["LLM_MODEL"], "qwen3:8b")

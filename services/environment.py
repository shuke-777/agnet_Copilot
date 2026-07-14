import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


def load_project_environment(env_path: Path | None = None) -> bool:
    """Load the local .env file without overriding explicit process settings."""
    target_path = env_path or DEFAULT_ENV_PATH
    if not target_path.is_file():
        return False
    return load_dotenv(dotenv_path=target_path, override=False)

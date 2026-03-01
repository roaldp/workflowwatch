import platform
from pathlib import Path

from pydantic_settings import BaseSettings


def _default_db_path() -> str:
    system = platform.system()
    if system == "Darwin":
        base = Path.home() / "Library" / "Application Support" / "workflowwatch"
    elif system == "Linux":
        base = Path.home() / ".local" / "share" / "workflowwatch"
    else:
        base = Path.home() / ".workflowwatch"
    return str(base / "workflowwatch.db")


class Settings(BaseSettings):
    aw_server_url: str = "http://localhost:5600"
    ww_host: str = "127.0.0.1"
    ww_port: int = 5700
    ww_db_path: str = _default_db_path()

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

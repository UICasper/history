import json
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")


@lru_cache
def load_config() -> dict:
    with open(ROOT / "config" / "config.json", "r", encoding="utf-8") as f:
        return json.load(f)


def get_env(name: str, required: bool = True) -> str:
    value = os.environ.get(name, "")
    if required and not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. Add it to .env (see .env.example)."
        )
    return value

"""
Persistent settings stored in data/settings.json inside the container.
Falls back to environment variables if no settings file exists.
"""
import json
import os
from pathlib import Path

SETTINGS_FILE = Path(__file__).parent.parent / "data" / "settings.json"


def load() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save(settings: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def get_api_key() -> str | None:
    s = load()
    return s.get("openai_api_key") or os.getenv("OPENAI_API_KEY") or None


def get_model() -> str:
    s = load()
    return s.get("model") or "gpt-4o"

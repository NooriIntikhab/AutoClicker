"""Load and save click sets on this PC."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from autoclicker.model import Settings, settings_from_dict

SETTINGS_ENV = "AUTOCLICKER_SETTINGS"


def settings_path() -> Path:
    override = os.environ.get(SETTINGS_ENV)
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "AutoClicker" / "settings.json"


def load_settings(path: Path | None = None) -> Settings:
    path = path or settings_path()
    if not path.exists():
        return Settings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return settings_from_dict(data)
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        backup = path.with_name("settings.corrupt.json")
        try:
            path.replace(backup)
        except OSError:
            pass
        return Settings()


def save_settings(settings: Settings, path: Path | None = None) -> None:
    path = path or settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(settings.to_dict(), indent=2, sort_keys=True) + "\n"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)

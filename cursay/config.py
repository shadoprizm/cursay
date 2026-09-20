from __future__ import annotations

import json
import os
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any


APP_ID = "io.github.shadoprizm.Cursay"
APP_NAME = "Cursay"
APPEARANCE_OPTIONS = ("system", "light", "dark")
PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "cursay"
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "cursay"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "cursay"
LEGACY_CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "local-flow"
LEGACY_DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "local-flow"
CONFIG_FILE = CONFIG_DIR / "config.json"
DATABASE_FILE = DATA_DIR / "history.db"
RECORDINGS_DIR = DATA_DIR / "recordings"
TEMP_DIR = CACHE_DIR / "recordings"

DEFAULT_CONFIG: dict[str, Any] = {
    "mode": "professional",
    "appearance": "system",
    "language": "en",
    "stt_endpoint": "http://127.0.0.1:8765/v1/audio/transcriptions",
    "stt_model": "whisper-base.en",
    "shortcut": "<Control>space",
    "auto_paste": True,
    "remove_fillers": True,
    "smart_polish": False,
    "polish_endpoint": "http://127.0.0.1:8082/v1/chat/completions",
    "polish_model": "Gemma 4 26B-A4B - Fast General",
    "preserve_recordings": False,
    "launch_at_login": False,
    "show_notifications": True,
}


def migrate_legacy_data(
    legacy_config_dir: Path = LEGACY_CONFIG_DIR,
    legacy_data_dir: Path = LEGACY_DATA_DIR,
    config_dir: Path = CONFIG_DIR,
    data_dir: Path = DATA_DIR,
) -> bool:
    """Copy a Local Flow profile into Cursay once, leaving the original intact."""
    migrated = False
    legacy_config = legacy_config_dir / "config.json"
    config_file = config_dir / "config.json"
    if legacy_config.is_file() and not config_file.exists():
        config_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy_config, config_file)
        config_file.chmod(0o600)
        migrated = True

    legacy_database = legacy_data_dir / "history.db"
    database_file = data_dir / "history.db"
    if legacy_database.is_file() and not database_file.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy_database, database_file)
        database_file.chmod(0o600)
        migrated = True

    legacy_recordings = legacy_data_dir / "recordings"
    recordings_dir = data_dir / "recordings"
    if legacy_recordings.is_dir() and not recordings_dir.exists():
        shutil.copytree(legacy_recordings, recordings_dir)
        migrated = True
    return migrated


def ensure_directories() -> None:
    migrate_legacy_data()
    for directory in (CONFIG_DIR, DATA_DIR, RECORDINGS_DIR, TEMP_DIR):
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(0o700)


def load_config(path: Path = CONFIG_FILE) -> dict[str, Any]:
    ensure_directories()
    config = deepcopy(DEFAULT_CONFIG)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            config.update({key: value for key, value in data.items() if key in DEFAULT_CONFIG})
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    if config["appearance"] not in APPEARANCE_OPTIONS:
        config["appearance"] = "system"
    return config


def save_config(config: dict[str, Any], path: Path = CONFIG_FILE) -> None:
    ensure_directories()
    clean = deepcopy(DEFAULT_CONFIG)
    clean.update({key: value for key, value in config.items() if key in DEFAULT_CONFIG})
    handle, temporary_name = tempfile.mkstemp(prefix="config-", suffix=".json", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(clean, stream, indent=2, sort_keys=True)
            stream.write("\n")
        temporary.chmod(0o600)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)

"""
Configuration management for Noodle.

Uses XDG base directories:
- Config: ~/.config/noodle/config.toml
- Data: ~/noodle/ (the brain itself)
"""

from pathlib import Path
from typing import Any
import os

# XDG defaults
DEFAULT_CONFIG_HOME = Path.home() / ".config"
DEFAULT_DATA_HOME = Path.home() / "noodle"


def get_config_dir() -> Path:
    """Get the config directory (XDG_CONFIG_HOME/noodle)."""
    base = Path(os.environ.get("XDG_CONFIG_HOME", DEFAULT_CONFIG_HOME))
    return base / "noodle"


def get_noodle_home() -> Path:
    """Get the noodle data directory (~/noodle or NOODLE_HOME)."""
    if env_home := os.environ.get("NOODLE_HOME"):
        return Path(env_home)
    return DEFAULT_DATA_HOME


def get_config_path() -> Path:
    """Get the path to config.toml."""
    return get_config_dir() / "config.toml"


def get_inbox_path() -> Path:
    """Get the path to inbox.log."""
    return get_noodle_home() / "inbox.log"


def get_db_path() -> Path:
    """Get the path to noodle.db."""
    return get_noodle_home() / "noodle.db"


def ensure_dirs() -> None:
    """Ensure all required directories exist."""
    get_config_dir().mkdir(parents=True, exist_ok=True)
    get_noodle_home().mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    """
    Load configuration from config.toml.

    Returns default config if file doesn't exist.
    """
    config_path = get_config_path()

    if not config_path.exists():
        return get_default_config()

    # Lazy import tomli only when needed
    import tomli

    with open(config_path, "rb") as f:
        return tomli.load(f)


def get_default_config() -> dict[str, Any]:
    """Return default configuration."""
    return {
        "noodle": {
            "home": str(get_noodle_home()),
        },
        "classifier": {
            "confidence_threshold": 0.75,
        },
        "llm": {
            "provider": "anthropic",  # or "openai"
            "model": "claude-haiku-4-5-20251001",  # Fast and cheap for classification
        },
    }

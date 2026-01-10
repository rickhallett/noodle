"""
Health check module for Noodle.

Reports system status across all components.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

from noodle.config import get_db_path, get_inbox_path, get_noodle_home, load_config


def check_database() -> tuple[str, str]:
    """Check database status."""
    db_path = get_db_path()
    if not db_path.exists():
        return "✗", "Not found"

    try:
        from noodle.db import Database
        db = Database()
        stats = db.get_stats()
        return "✓", f"OK ({stats['total_entries']} entries)"
    except Exception as e:
        return "✗", f"Error: {e}"


def check_inbox() -> tuple[str, str]:
    """Check inbox status."""
    inbox_path = get_inbox_path()
    if not inbox_path.exists():
        return "✓", "Empty (no pending)"

    try:
        # Count unprocessed entries
        processed_path = get_noodle_home() / "processed.log"
        processed_ids: set[str] = set()

        if processed_path.exists():
            with open(processed_path) as f:
                for line in f:
                    parts = line.strip().split("\t")
                    if parts:
                        processed_ids.add(parts[0])

        pending = 0
        with open(inbox_path) as f:
            for line in f:
                if line.strip():
                    entry_id = line.split("\t")[0]
                    if entry_id not in processed_ids:
                        pending += 1

        if pending == 0:
            return "✓", "OK (0 pending)"
        else:
            return "!", f"{pending} pending"
    except Exception as e:
        return "✗", f"Error: {e}"


def check_classifier() -> tuple[str, str]:
    """Check classifier (API) status."""
    config = load_config()
    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "anthropic")

    if provider == "anthropic":
        api_key = llm_config.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return "✗", "No API key"
        return "✓", f"OK (Anthropic)"
    else:
        api_key = llm_config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return "✗", "No API key"
        return "✓", f"OK (OpenAI)"


def check_telegram() -> tuple[str, str]:
    """Check Telegram bot status."""
    config = load_config()
    tg_config = config.get("telegram", {})

    token = tg_config.get("token") or os.environ.get("NOODLE_TELEGRAM_TOKEN")
    if not token:
        return "-", "Not configured"

    users = tg_config.get("authorized_users", [])
    if not users:
        env_users = os.environ.get("NOODLE_TELEGRAM_USERS", "")
        if env_users:
            users = [u.strip() for u in env_users.split(",") if u.strip()]

    if not users:
        return "!", "No authorized users"

    return "✓", f"OK ({len(users)} users)"


def check_manual_review() -> tuple[str, str]:
    """Check manual review queue."""
    try:
        from noodle.db import Database
        db = Database()
        entries = db.get_pending_reclassification()
        count = len(entries)
        if count == 0:
            return "✓", "Empty"
        else:
            return "!", f"{count} items pending"
    except Exception:
        return "-", "N/A"


def check_systemd() -> tuple[str, str]:
    """Check systemd units status."""
    import subprocess

    units = ["noodle-inbox.path", "noodle-digest.timer", "noodle-weekly.timer"]
    active = 0

    for unit in units:
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", unit],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.stdout.strip() == "active":
                active += 1
        except Exception:
            pass

    if active == len(units):
        return "✓", f"OK ({active}/{len(units)} active)"
    elif active > 0:
        return "!", f"{active}/{len(units)} active"
    else:
        return "-", "Not enabled"


def run_health_check() -> dict[str, tuple[str, str]]:
    """Run all health checks."""
    return {
        "Database": check_database(),
        "Inbox": check_inbox(),
        "Classifier": check_classifier(),
        "Telegram": check_telegram(),
        "Manual Review": check_manual_review(),
        "Systemd": check_systemd(),
    }


def format_health_report(checks: dict[str, tuple[str, str]]) -> str:
    """Format health check results."""
    lines = ["Noodle Health Check", "-" * 40]

    for name, (status, message) in checks.items():
        lines.append(f"{status} {name}: {message}")

    return "\n".join(lines)

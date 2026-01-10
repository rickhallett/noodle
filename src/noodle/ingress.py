"""
Ingress module for Noodle.

This is the critical path - must complete in < 100ms.
Every import and operation is scrutinized for speed.
"""

import fcntl
import time
from datetime import datetime, timezone
from pathlib import Path


def generate_id() -> str:
    """Generate a unique entry ID (Unix timestamp in milliseconds)."""
    return str(int(time.time() * 1000))


def append_to_inbox(text: str, inbox_path: Path) -> str:
    """
    Append raw text to inbox.log with timestamp.

    This function MUST:
    1. Complete in < 50ms (leaving headroom for CLI overhead)
    2. Never fail silently (write or raise)
    3. Use file locking for concurrent safety

    Args:
        text: The raw thought to capture
        inbox_path: Path to inbox.log

    Returns:
        The generated entry ID
    """
    entry_id = generate_id()
    timestamp = datetime.now(timezone.utc).isoformat()

    # Tab-separated: id, timestamp, text (newlines in text become \n literal)
    escaped_text = text.replace("\n", "\\n").replace("\t", "\\t")
    line = f"{entry_id}\t{timestamp}\t{escaped_text}\n"

    # Ensure parent directory exists
    inbox_path.parent.mkdir(parents=True, exist_ok=True)

    # Atomic append with file locking
    with open(inbox_path, "a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        f.write(line)
        f.flush()
        os.fsync(f.fileno())  # Ensure durability
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    return entry_id


# Import os only for fsync - done at module level for speed
import os

"""
Router module for Noodle.

Routes classified entries to appropriate storage based on confidence.
"""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from noodle.config import get_noodle_home, load_config
from noodle.db import Database


def send_notification(title: str, body: str = "") -> None:
    """Send desktop notification via notify-send."""
    try:
        cmd = ["notify-send", title]
        if body:
            cmd.append(body)
        subprocess.run(cmd, check=False, capture_output=True)
    except Exception:
        pass  # Notifications are best-effort


def append_to_manual_review(entry: dict[str, Any], noodle_home: Path) -> None:
    """Append entry to manual_review.md for human review."""
    review_path = noodle_home / "manual_review.md"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    content = f"""
## [{entry.get('id', 'unknown')}] {now}

**Raw input:** {entry.get('raw_input', '')}

**Suggested type:** {entry.get('type', 'unknown')} (confidence: {entry.get('confidence', 0):.2f})

**Title:** {entry.get('title', '')}

**Reason:** {entry.get('error', entry.get('parse_error', 'Low confidence'))}

---
"""

    with open(review_path, "a", encoding="utf-8") as f:
        f.write(content)


def append_to_processed_log(entry: dict[str, Any], status: str, noodle_home: Path) -> None:
    """Append to processed.log for audit trail."""
    log_path = noodle_home / "processed.log"
    now = datetime.now(timezone.utc).isoformat()

    line = "\t".join([
        entry.get("id", ""),
        now,
        status,
        entry.get("type", ""),
        f"{entry.get('confidence', 0):.2f}",
        entry.get("routed_to", ""),
    ])

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def write_thought_markdown(entry: dict[str, Any], noodle_home: Path) -> Path | None:
    """Write long-form thought to markdown file."""
    body = entry.get("body", "")
    if not body or len(body) < 200:
        return None

    thoughts_dir = noodle_home / "thoughts"
    thoughts_dir.mkdir(parents=True, exist_ok=True)

    # Create slug from title
    title = entry.get("title", "untitled")
    slug = "".join(c if c.isalnum() else "-" for c in title.lower())[:50]
    slug = "-".join(filter(None, slug.split("-")))  # Remove consecutive dashes

    filename = f"{entry['id']}-{slug}.md"
    filepath = thoughts_dir / filename

    # YAML frontmatter
    frontmatter = {
        "id": entry["id"],
        "type": entry["type"],
        "title": entry["title"],
        "created": entry.get("created_at", datetime.now(timezone.utc).isoformat()),
        "tags": entry.get("tags", []),
        "project": entry.get("project"),
        "people": entry.get("people", []),
    }

    content = "---\n"
    for key, value in frontmatter.items():
        if value is not None:
            if isinstance(value, list):
                if value:
                    content += f"{key}:\n"
                    for item in value:
                        content += f"  - {item}\n"
            else:
                content += f"{key}: {value}\n"
    content += "---\n\n"
    content += body

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath


def update_person_file(entry: dict[str, Any], noodle_home: Path) -> Path:
    """Update or create a person markdown file."""
    people_dir = noodle_home / "people"
    people_dir.mkdir(parents=True, exist_ok=True)

    # Extract person slug from title or first person reference
    people = entry.get("people", [])
    if people:
        slug = people[0]
    else:
        # Create slug from title
        title = entry.get("title", "unknown")
        slug = "".join(c if c.isalnum() else "-" for c in title.lower())[:50]
        slug = "-".join(filter(None, slug.split("-")))

    filepath = people_dir / f"{slug}.md"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Append to existing file or create new
    if filepath.exists():
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(f"\n## {now}\n\n{entry.get('body') or entry.get('title', '')}\n")
    else:
        content = f"""---
id: {slug}
name: {entry.get('title', slug.replace('-', ' ').title())}
created: {now}
---

## {now}

{entry.get('body') or entry.get('raw_input', '')}
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    return filepath


class Router:
    """Routes classified entries to appropriate storage."""

    def __init__(self, config: dict[str, Any] | None = None, db: Database | None = None):
        self.config = config or load_config()
        self.db = db or Database()
        self.noodle_home = get_noodle_home()
        self.confidence_threshold = self.config.get("classifier", {}).get(
            "confidence_threshold", 0.75
        )

    def route(self, entry: dict[str, Any]) -> dict[str, Any]:
        """
        Route a classified entry to appropriate storage.

        Returns entry with routing metadata added.
        """
        confidence = entry.get("confidence", 0)
        status = entry.get("status", "classified")

        # Low confidence or fallback → manual review
        if confidence < self.confidence_threshold or status == "fallback":
            return self._route_to_manual_review(entry)

        # High confidence → database + appropriate storage
        return self._route_to_storage(entry)

    def _route_to_manual_review(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Route low-confidence entry to manual review."""
        append_to_manual_review(entry, self.noodle_home)
        append_to_processed_log(entry, "manual_review", self.noodle_home)

        # Still store in DB but flag for reclassification
        entry["needs_reclassification"] = 1
        self.db.insert_entry(entry)

        # Log classification attempt
        self.db.log_classification(
            entry_id=entry["id"],
            raw_input=entry.get("raw_input", ""),
            llm_output=json.dumps(entry),
            llm_model=entry.get("llm_model", "unknown"),
            confidence=entry.get("confidence", 0),
            processing_time_ms=entry.get("processing_time_ms", 0),
            status="manual_review",
            routed_to="manual_review.md",
        )

        # Notify user
        send_notification(
            "Noodle: Item needs review",
            entry.get("title", "")[:50]
        )

        entry["routed_to"] = "manual_review"
        return entry

    def _route_to_storage(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Route high-confidence entry to appropriate storage."""
        entry_type = entry.get("type", "thought")
        routed_to = "entries"

        # Insert into database
        self.db.insert_entry(entry)

        # Type-specific handling
        if entry_type == "thought":
            md_path = write_thought_markdown(entry, self.noodle_home)
            if md_path:
                routed_to = f"entries+{md_path.name}"

        elif entry_type == "person":
            person_path = update_person_file(entry, self.noodle_home)
            routed_to = f"entries+{person_path.name}"

        # Log classification
        self.db.log_classification(
            entry_id=entry["id"],
            raw_input=entry.get("raw_input", ""),
            llm_output=json.dumps(entry),
            llm_model=entry.get("llm_model", "unknown"),
            confidence=entry.get("confidence", 0),
            processing_time_ms=entry.get("processing_time_ms", 0),
            status="classified",
            routed_to=routed_to,
        )

        append_to_processed_log(entry, "classified", self.noodle_home)

        entry["routed_to"] = routed_to
        return entry


def route_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Convenience function to route a single entry."""
    router = Router()
    return router.route(entry)

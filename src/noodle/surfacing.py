"""
Surfacing module for Noodle.

Push-first architecture: proactively surface relevant information.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from noodle.config import load_config
from noodle.db import Database


# ANSI color codes
class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground colors
    BRIGHT_BLACK = "\033[90m"  # Gray
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"

    @classmethod
    def enabled(cls) -> bool:
        """Check if colors should be enabled."""
        # Disable if NO_COLOR is set or not a tty
        if os.environ.get("NO_COLOR"):
            return False
        return True


def c(text: str, *codes: str) -> str:
    """Apply color codes to text if colors are enabled."""
    if not Colors.enabled():
        return text
    return "".join(codes) + text + Colors.RESET


# Type colors
TYPE_COLORS = {
    "task": Colors.BRIGHT_YELLOW,
    "thought": Colors.BRIGHT_CYAN,
    "person": Colors.BRIGHT_MAGENTA,
    "event": Colors.BRIGHT_GREEN,
}


def format_id(entry_id: str) -> str:
    """Format entry ID with hyphens for readability (4-3-3-3 pattern)."""
    # Remove any existing hyphens first
    clean = entry_id.replace("-", "")
    # Format as 4-3-3-3 (e.g., 1768-427-187-928)
    if len(clean) >= 13:
        return f"{clean[:4]}-{clean[4:7]}-{clean[7:10]}-{clean[10:]}"
    elif len(clean) >= 10:
        return f"{clean[:4]}-{clean[4:7]}-{clean[7:]}"
    elif len(clean) >= 7:
        return f"{clean[:4]}-{clean[4:]}"
    return clean


def generate_daily_digest(db: Database | None = None) -> str:
    """
    Generate daily digest.

    Format: Maximum 5 items, actionable items first.
    Design: High signal-to-noise ratio. Trust through brevity.
    """
    db = db or Database()
    today = datetime.now(timezone.utc).date().isoformat()
    now = datetime.now(timezone.utc)

    lines = [f"# Noodle Daily Digest — {today}", ""]

    # Due today or overdue
    with db._connect() as conn:
        due_tasks = conn.execute("""
            SELECT id, title, due_date, priority FROM entries
            WHERE type = 'task'
            AND completed_at IS NULL
            AND due_date IS NOT NULL
            AND due_date <= ?
            ORDER BY due_date ASC, priority DESC
            LIMIT 3
        """, (today,)).fetchall()

    if due_tasks:
        lines.append(f"## Due Today ({len(due_tasks)})")
        for task in due_tasks:
            priority_marker = "!" if task["priority"] == "high" else ""
            lines.append(f"- [ ] {priority_marker}{task['title']}")
        lines.append("")

    # Incomplete tasks (no due date)
    with db._connect() as conn:
        open_tasks = conn.execute("""
            SELECT id, title, priority FROM entries
            WHERE type = 'task'
            AND completed_at IS NULL
            AND due_date IS NULL
            ORDER BY created_at DESC
            LIMIT 3
        """).fetchall()

    if open_tasks:
        lines.append(f"## Open Tasks ({len(open_tasks)})")
        for task in open_tasks:
            lines.append(f"- [ ] {task['title']}")
        lines.append("")

    # Recent thoughts worth revisiting (7+ days old)
    week_ago = (now - timedelta(days=7)).isoformat()
    with db._connect() as conn:
        stale_thoughts = conn.execute("""
            SELECT id, title, created_at FROM entries
            WHERE type = 'thought'
            AND created_at < ?
            ORDER BY created_at DESC
            LIMIT 2
        """, (week_ago,)).fetchall()

    if stale_thoughts:
        lines.append("## Worth Revisiting")
        for thought in stale_thoughts:
            created = thought["created_at"][:10]
            lines.append(f"- \"{thought['title']}\" ({created})")
        lines.append("")

    # Upcoming events
    tomorrow = (now + timedelta(days=1)).date().isoformat()
    with db._connect() as conn:
        upcoming = conn.execute("""
            SELECT id, title, due_date FROM entries
            WHERE type = 'event'
            AND due_date >= ?
            AND due_date <= ?
            ORDER BY due_date ASC
            LIMIT 2
        """, (today, tomorrow)).fetchall()

    if upcoming:
        lines.append("## Upcoming")
        for event in upcoming:
            lines.append(f"- {event['title']} ({event['due_date']})")
        lines.append("")

    # Manual review queue count
    with db._connect() as conn:
        pending = conn.execute("""
            SELECT COUNT(*) FROM entries WHERE needs_reclassification = 1
        """).fetchone()[0]

    if pending > 0:
        lines.append(f"---\n{pending} items in manual review queue")

    # If nothing to show
    if len(lines) <= 2:
        lines.append("Nothing urgent today. You're all caught up.")

    return "\n".join(lines)


def generate_weekly_review(db: Database | None = None) -> str:
    """
    Generate weekly review.

    Format: Rolling 7-day window. NO BACKLOG. No guilt.
    """
    db = db or Database()
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()
    today = now.date().isoformat()

    lines = [f"# Noodle Weekly Review — {today}", ""]

    # This week's stats
    with db._connect() as conn:
        # Total captured
        captured = conn.execute("""
            SELECT COUNT(*) FROM entries WHERE created_at >= ?
        """, (week_ago,)).fetchone()[0]

        # Completed tasks
        completed = conn.execute("""
            SELECT COUNT(*) FROM entries
            WHERE type = 'task' AND completed_at >= ?
        """, (week_ago,)).fetchone()[0]

        # Created tasks
        created_tasks = conn.execute("""
            SELECT COUNT(*) FROM entries
            WHERE type = 'task' AND created_at >= ?
        """, (week_ago,)).fetchone()[0]

        # By type
        by_type = dict(conn.execute("""
            SELECT type, COUNT(*) FROM entries
            WHERE created_at >= ?
            GROUP BY type
        """, (week_ago,)).fetchall())

    lines.append("## This Week")
    lines.append(f"- Captured: {captured} entries")
    lines.append(f"- Completed: {completed} tasks")
    lines.append(f"- Created: {created_tasks} tasks")

    delta = completed - created_tasks
    if delta > 0:
        lines.append(f"- Net: +{delta} (making progress!)")
    elif delta < 0:
        lines.append(f"- Net: {delta} (backlog growing)")
    else:
        lines.append("- Net: 0 (holding steady)")
    lines.append("")

    # Breakdown by type
    if by_type:
        lines.append("## By Type")
        for entry_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
            lines.append(f"- {entry_type}: {count}")
        lines.append("")

    # Top projects
    with db._connect() as conn:
        projects = conn.execute("""
            SELECT project_id, COUNT(*) as cnt FROM entries
            WHERE project_id IS NOT NULL AND created_at >= ?
            GROUP BY project_id
            ORDER BY cnt DESC
            LIMIT 3
        """, (week_ago,)).fetchall()

    if projects:
        lines.append("## Top Projects")
        for i, proj in enumerate(projects, 1):
            lines.append(f"{i}. {proj['project_id']} ({proj['cnt']} entries)")
        lines.append("")

    # Ideas worth revisiting
    with db._connect() as conn:
        thoughts = conn.execute("""
            SELECT title, created_at FROM entries
            WHERE type = 'thought' AND created_at >= ?
            ORDER BY created_at DESC
            LIMIT 3
        """, (week_ago,)).fetchall()

    if thoughts:
        lines.append("## Ideas This Week")
        for thought in thoughts:
            created = thought["created_at"][:10]
            lines.append(f"- \"{thought['title']}\" ({created})")
        lines.append("")

    # Pending review
    with db._connect() as conn:
        pending = conn.execute("""
            SELECT COUNT(*) FROM entries WHERE needs_reclassification = 1
        """).fetchone()[0]

    if pending > 0:
        lines.append(f"---\nManual review queue: {pending} items")

    return "\n".join(lines)


def get_entries_formatted(
    db: Database | None = None,
    entry_type: str | None = None,
    project: str | None = None,
    limit: int = 20,
    include_completed: bool = False,
    include_archived: bool = False,
) -> str:
    """Get entries as formatted string with colors."""
    db = db or Database()
    entries = db.get_entries(
        entry_type=entry_type,
        project=project,
        limit=limit,
        include_completed=include_completed,
        include_archived=include_archived,
    )

    if not entries:
        return c("No entries found.", Colors.DIM)

    lines = []

    # Header
    header_text = "ENTRIES"
    if entry_type:
        header_text = f"{entry_type.upper()}S"
    lines.append(c(f"━━━ {header_text} ━━━", Colors.BOLD, Colors.BLUE))
    lines.append("")

    # Column header
    lines.append(c(f"{'#':>4}  {'ID':16}  {'TYPE':8}  TITLE", Colors.DIM))
    lines.append(c("─" * 70, Colors.DIM))

    for entry in entries:
        seq = entry.get("seq", "?")
        full_id = format_id(entry["id"])
        etype = entry["type"]
        title = entry["title"][:42]
        type_color = TYPE_COLORS.get(etype, "")

        extra = ""
        if etype == "task":
            if entry["completed_at"]:
                extra = c(" [done]", Colors.GREEN)
            elif entry["due_date"]:
                extra = c(f" [due:{entry['due_date']}]", Colors.YELLOW)

        seq_str = c(f"{seq:>4}", Colors.BOLD, Colors.WHITE)
        id_str = c(full_id, Colors.DIM)
        type_str = c(f"{etype:8}", type_color)

        lines.append(f"{seq_str}  {id_str}  {type_str}  {title}{extra}")

    return "\n".join(lines)


def search_entries_formatted(query: str, db: Database | None = None, limit: int = 20) -> str:
    """Search entries and return formatted string with colors."""
    db = db or Database()
    entries = db.search(query, limit=limit)

    if not entries:
        return c(f"No entries matching '{query}'.", Colors.DIM)

    lines = []

    # Header
    lines.append(c(f"━━━ SEARCH: {query} ━━━", Colors.BOLD, Colors.BLUE))
    lines.append("")

    # Column header
    lines.append(c(f"{'#':>4}  {'ID':16}  {'TYPE':8}  TITLE", Colors.DIM))
    lines.append(c("─" * 70, Colors.DIM))

    for entry in entries:
        seq = entry.get("seq", "?")
        full_id = format_id(entry["id"])
        etype = entry["type"]
        title = entry["title"][:42]
        type_color = TYPE_COLORS.get(etype, "")

        seq_str = c(f"{seq:>4}", Colors.BOLD, Colors.WHITE)
        id_str = c(full_id, Colors.DIM)
        type_str = c(f"{etype:8}", type_color)

        lines.append(f"{seq_str}  {id_str}  {type_str}  {title}")

    return "\n".join(lines)


# LLM Analysis for Digest
DIGEST_ANALYSIS_PROMPT = """You are analyzing a daily digest from a personal knowledge management system.

## Digest Data
{digest_data}

## Your Task
Provide brief, actionable analysis (2-4 sentences max). Consider:
- Priorities: What should get attention first and why?
- Connections: Any links between items worth noting?
- Patterns: Anything notable about the workload or focus areas?
- Suggestions: One concrete suggestion to be more effective today

Be direct and practical. No fluff. No emojis. Keep it under 100 words."""


def _get_llm_config() -> dict[str, Any]:
    """Get LLM configuration from config file or environment."""
    config = load_config()
    llm_config = config.get("llm", {})

    provider = llm_config.get("provider", "anthropic")

    if provider == "anthropic":
        api_key = (
            llm_config.get("anthropic_api_key")
            or os.environ.get("ANTHROPIC_API_KEY")
        )
        model = llm_config.get("model", "claude-haiku-4-5-20251001")
        return {
            "provider": "anthropic",
            "api_key": api_key,
            "model": model,
            "base_url": "https://api.anthropic.com/v1",
        }
    else:
        api_key = (
            llm_config.get("openai_api_key")
            or os.environ.get("OPENAI_API_KEY")
        )
        model = llm_config.get("model", "gpt-4o-mini")
        base_url = llm_config.get("base_url", "https://api.openai.com/v1")
        return {
            "provider": "openai",
            "api_key": api_key,
            "model": model,
            "base_url": base_url,
        }


def _call_llm_for_analysis(prompt: str) -> str | None:
    """Call LLM for digest analysis. Returns None on failure."""
    config = _get_llm_config()

    if not config["api_key"]:
        return None

    try:
        with httpx.Client(timeout=30.0) as client:
            if config["provider"] == "anthropic":
                response = client.post(
                    f"{config['base_url']}/messages",
                    headers={
                        "x-api-key": config["api_key"],
                        "Content-Type": "application/json",
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": config["model"],
                        "max_tokens": 256,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.5,
                    },
                )
                response.raise_for_status()
                return response.json()["content"][0]["text"]
            else:
                response = client.post(
                    f"{config['base_url']}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config['api_key']}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": config["model"],
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.5,
                        "max_tokens": 256,
                    },
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
    except Exception:
        return None


def analyze_digest_with_llm(digest_data: dict[str, Any]) -> str | None:
    """
    Get LLM analysis of digest data.

    Args:
        digest_data: Dict containing tasks, thoughts, events, etc.

    Returns:
        Analysis string or None if LLM unavailable.
    """
    # Format digest data for the prompt
    data_str = json.dumps(digest_data, indent=2, default=str)
    prompt = DIGEST_ANALYSIS_PROMPT.format(digest_data=data_str)
    return _call_llm_for_analysis(prompt)


def get_entries_by_tag(
    tag: str,
    db: Database | None = None,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    """Get all entries with a specific tag."""
    db = db or Database()
    tag_lower = tag.lower().lstrip("#")

    with db._connect() as conn:
        query = """
            SELECT e.* FROM entries e
            JOIN entry_tags et ON e.id = et.entry_id
            JOIN tags t ON et.tag_id = t.id
            WHERE t.name = ?
        """
        params: list[Any] = [tag_lower]

        if not include_archived:
            query += " AND e.archived_at IS NULL"

        query += " ORDER BY e.created_at DESC"

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def generate_dev_context(
    tag: str = "dev",
    db: Database | None = None,
    format: str = "markdown",
) -> str:
    """
    Generate context from tagged entries for dev tools like Claude Code.

    Args:
        tag: Tag to filter by (default: "dev")
        db: Database instance
        format: Output format - "markdown" or "json"

    Returns:
        Formatted context string ready for AI consumption.
    """
    db = db or Database()
    entries = get_entries_by_tag(tag, db)

    if not entries:
        return f"No entries with tag #{tag} found."

    if format == "json":
        import json
        simplified = []
        for e in entries:
            simplified.append({
                "id": e["id"],
                "seq": e.get("seq"),
                "type": e["type"],
                "title": e["title"],
                "body": e.get("body"),
                "created": e["created_at"][:10],
                "project": e.get("project_id"),
            })
        return json.dumps(simplified, indent=2)

    # Markdown format (default)
    lines = [
        f"# Dev Context - #{tag}",
        f"",
        f"Captured thoughts and tasks tagged with #{tag} for development context.",
        f"",
    ]

    # Group by type
    by_type: dict[str, list] = {}
    for entry in entries:
        etype = entry["type"]
        if etype not in by_type:
            by_type[etype] = []
        by_type[etype].append(entry)

    for etype, items in sorted(by_type.items()):
        lines.append(f"## {etype.title()}s ({len(items)})")
        lines.append("")

        for entry in items:
            seq = entry.get("seq", "?")
            lines.append(f"### #{seq}: {entry['title']}")

            if entry.get("body"):
                lines.append(f"")
                lines.append(entry["body"])

            lines.append(f"")
            lines.append(f"*Created: {entry['created_at'][:10]}*")
            if entry.get("project_id"):
                lines.append(f"*Project: {entry['project_id']}*")
            lines.append("")

    return "\n".join(lines)


def generate_daily_digest_enhanced(db: Database | None = None) -> str:
    """
    Generate daily digest with optional LLM analysis.

    Same as generate_daily_digest but adds an AI analysis section.
    """
    db = db or Database()
    today = datetime.now(timezone.utc).date().isoformat()
    now = datetime.now(timezone.utc)

    lines = [f"# Noodle Daily Digest — {today}", ""]

    # Collect data for LLM analysis
    digest_data: dict[str, Any] = {"date": today}

    # Due today or overdue
    with db._connect() as conn:
        due_tasks = conn.execute("""
            SELECT id, title, due_date, priority FROM entries
            WHERE type = 'task'
            AND completed_at IS NULL
            AND due_date IS NOT NULL
            AND due_date <= ?
            ORDER BY due_date ASC, priority DESC
            LIMIT 3
        """, (today,)).fetchall()

    if due_tasks:
        lines.append(f"## Due Today ({len(due_tasks)})")
        digest_data["due_tasks"] = []
        for task in due_tasks:
            priority_marker = "!" if task["priority"] == "high" else ""
            lines.append(f"- [ ] {priority_marker}{task['title']}")
            digest_data["due_tasks"].append({
                "title": task["title"],
                "priority": task["priority"],
                "due_date": task["due_date"],
            })
        lines.append("")

    # Incomplete tasks (no due date)
    with db._connect() as conn:
        open_tasks = conn.execute("""
            SELECT id, title, priority FROM entries
            WHERE type = 'task'
            AND completed_at IS NULL
            AND due_date IS NULL
            ORDER BY created_at DESC
            LIMIT 3
        """).fetchall()

    if open_tasks:
        lines.append(f"## Open Tasks ({len(open_tasks)})")
        digest_data["open_tasks"] = []
        for task in open_tasks:
            lines.append(f"- [ ] {task['title']}")
            digest_data["open_tasks"].append({
                "title": task["title"],
                "priority": task["priority"],
            })
        lines.append("")

    # Recent thoughts worth revisiting (7+ days old)
    week_ago = (now - timedelta(days=7)).isoformat()
    with db._connect() as conn:
        stale_thoughts = conn.execute("""
            SELECT id, title, created_at FROM entries
            WHERE type = 'thought'
            AND created_at < ?
            ORDER BY created_at DESC
            LIMIT 2
        """, (week_ago,)).fetchall()

    if stale_thoughts:
        lines.append("## Worth Revisiting")
        digest_data["stale_thoughts"] = []
        for thought in stale_thoughts:
            created = thought["created_at"][:10]
            lines.append(f"- \"{thought['title']}\" ({created})")
            digest_data["stale_thoughts"].append({
                "title": thought["title"],
                "created": created,
            })
        lines.append("")

    # Upcoming events
    tomorrow = (now + timedelta(days=1)).date().isoformat()
    with db._connect() as conn:
        upcoming = conn.execute("""
            SELECT id, title, due_date FROM entries
            WHERE type = 'event'
            AND due_date >= ?
            AND due_date <= ?
            ORDER BY due_date ASC
            LIMIT 2
        """, (today, tomorrow)).fetchall()

    if upcoming:
        lines.append("## Upcoming")
        digest_data["upcoming_events"] = []
        for event in upcoming:
            lines.append(f"- {event['title']} ({event['due_date']})")
            digest_data["upcoming_events"].append({
                "title": event["title"],
                "date": event["due_date"],
            })
        lines.append("")

    # Manual review queue count
    with db._connect() as conn:
        pending = conn.execute("""
            SELECT COUNT(*) FROM entries WHERE needs_reclassification = 1
        """).fetchone()[0]

    if pending > 0:
        lines.append(f"---\n{pending} items in manual review queue")
        digest_data["pending_review"] = pending

    # If nothing to show
    if len(lines) <= 2:
        lines.append("Nothing urgent today. You're all caught up.")
        digest_data["empty"] = True

    # Add LLM analysis if we have content
    if digest_data and not digest_data.get("empty"):
        analysis = analyze_digest_with_llm(digest_data)
        if analysis:
            lines.append("")
            lines.append("---")
            lines.append("## Analysis")
            lines.append(analysis)

    return "\n".join(lines)

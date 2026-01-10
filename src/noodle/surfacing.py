"""
Surfacing module for Noodle.

Push-first architecture: proactively surface relevant information.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from noodle.db import Database


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
) -> str:
    """Get entries as formatted string."""
    db = db or Database()
    entries = db.get_entries(
        entry_type=entry_type,
        project=project,
        limit=limit,
        include_completed=include_completed,
    )

    if not entries:
        return "No entries found."

    lines = []
    for entry in entries:
        # Format: ID  TYPE  TITLE  [DUE/COMPLETED]
        entry_id = entry["id"]
        entry_type = entry["type"]
        title = entry["title"][:50]

        extra = ""
        if entry["type"] == "task":
            if entry["completed_at"]:
                extra = " [done]"
            elif entry["due_date"]:
                extra = f" [due:{entry['due_date']}]"

        lines.append(f"{entry_id}  {entry_type:8}  {title}{extra}")

    return "\n".join(lines)


def search_entries_formatted(query: str, db: Database | None = None, limit: int = 20) -> str:
    """Search entries and return formatted string."""
    db = db or Database()
    entries = db.search(query, limit=limit)

    if not entries:
        return f"No entries matching '{query}'."

    lines = []
    for entry in entries:
        entry_id = entry["id"]
        entry_type = entry["type"]
        title = entry["title"][:50]
        lines.append(f"{entry_id}  {entry_type:8}  {title}")

    return "\n".join(lines)

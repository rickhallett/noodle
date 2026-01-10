"""
CLI for Noodle.

Minimal CLI using stdlib for fast startup on the capture path.
Subcommands are imported lazily to avoid startup overhead.

Usage:
    noodle "your thought here"      # Capture (primary interface)
    noodle process-inbox            # Process pending items
    noodle --help                   # Show help
"""

import sys


def print_help() -> None:
    """Print help message."""
    print("""noodle - local-first second brain

Usage:
    noodle "your thought here"    Capture a thought (O(1) ingress)

Commands:
    noodle list [options]         List entries (--type, --project, --all)
    noodle find <query>           Full-text search
    noodle done <id>              Mark a task as completed
    noodle retype <id> <type>     Change entry type
    noodle digest                 Show daily digest
    noodle weekly                 Show weekly review
    noodle review                 Interactive review of pending items
    noodle health                 System health check
    noodle gc                     Garbage collection
    noodle process-inbox          Process inbox through classifier
    noodle stats                  Show database statistics
    noodle telegram               Run Telegram bot
    noodle install-systemd        Install systemd user units

Options:
    noodle --help, -h             Show this help
    noodle --version, -v          Show version

Examples:
    noodle "Remember to email Sarah"
    noodle list --type task
    noodle find "redis caching"
    noodle done abc123
    noodle digest

The thought is captured instantly. Classification happens async.
No decisions required at capture time.""")


def print_version() -> None:
    """Print version."""
    from noodle import __version__
    print(f"noodle {__version__}")


def capture(text: str) -> str:
    """
    Capture a thought to the inbox.

    Returns the entry ID.
    """
    from noodle.config import get_inbox_path, ensure_dirs
    from noodle.ingress import append_to_inbox

    ensure_dirs()
    inbox_path = get_inbox_path()
    entry_id = append_to_inbox(text, inbox_path)

    return entry_id


def cmd_process_inbox() -> int:
    """Process all pending items in inbox.log."""
    from pathlib import Path

    from noodle.config import get_inbox_path, get_noodle_home
    from noodle.classifier import Classifier
    from noodle.router import Router
    from noodle.ingress import generate_id

    inbox_path = get_inbox_path()
    noodle_home = get_noodle_home()

    if not inbox_path.exists():
        print("No inbox.log found. Nothing to process.")
        return 0

    # Read inbox
    with open(inbox_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if not lines:
        print("Inbox is empty. Nothing to process.")
        return 0

    # Track which entries have been processed
    processed_path = noodle_home / "processed.log"
    processed_ids: set[str] = set()

    if processed_path.exists():
        with open(processed_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("\t")
                if parts:
                    processed_ids.add(parts[0])

    # Parse inbox entries
    # Format: id\ttimestamp\tsource\ttext (4 fields)
    # Legacy format: id\ttimestamp\ttext (3 fields, source defaults to cli)
    pending = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 3)
        if len(parts) >= 4:
            entry_id, timestamp, source, text = parts
        elif len(parts) >= 3:
            # Legacy format without source
            entry_id, timestamp, text = parts
            source = "cli"
        else:
            continue

        if entry_id not in processed_ids:
            # Unescape text
            text = text.replace("\\n", "\n").replace("\\t", "\t")
            pending.append({
                "id": entry_id,
                "created_at": timestamp,
                "source": source,
                "text": text,
            })

    if not pending:
        print("All inbox items already processed.")
        return 0

    # Initialize classifier and router
    try:
        classifier = Classifier()
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    router = Router()

    print(f"Processing {len(pending)} items...")

    # Process each entry
    classified_count = 0
    manual_review_count = 0

    for item in pending:
        try:
            # Classify
            result = classifier.classify(item["text"])
            result["id"] = item["id"]
            result["created_at"] = item["created_at"]
            result["source"] = item.get("source", "cli")

            # Route
            routed = router.route(result)

            # Report
            confidence = routed.get("confidence", 0)
            entry_type = routed.get("type", "unknown")
            title = routed.get("title", "")[:40]

            if routed.get("routed_to") == "manual_review":
                manual_review_count += 1
                print(f"  {item['id']} → manual_review ({confidence:.2f}) {title}")
            else:
                classified_count += 1
                print(f"  {item['id']} → {entry_type} ({confidence:.2f}) {title}")

        except Exception as e:
            print(f"  {item['id']} → ERROR: {e}", file=sys.stderr)
            manual_review_count += 1

    print(f"\nDone. {classified_count} classified, {manual_review_count} manual review.")
    return 0


def cmd_stats() -> int:
    """Show database statistics."""
    from noodle.db import Database

    try:
        db = Database()
        stats = db.get_stats()

        print("Noodle Statistics")
        print("-" * 30)
        print(f"Total entries: {stats['total_entries']}")
        print("\nBy type:")
        for entry_type, count in stats.get("by_type", {}).items():
            print(f"  {entry_type}: {count}")
        print(f"\nPending reclassification: {stats['pending_reclassification']}")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_list(args: list[str]) -> int:
    """List entries with optional filters."""
    from noodle.surfacing import get_entries_formatted

    entry_type = None
    project = None
    include_completed = False

    # Parse arguments
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--type", "-t") and i + 1 < len(args):
            entry_type = args[i + 1]
            i += 2
        elif arg in ("--project", "-p") and i + 1 < len(args):
            project = args[i + 1]
            i += 2
        elif arg in ("--all", "-a"):
            include_completed = True
            i += 1
        else:
            i += 1

    try:
        result = get_entries_formatted(
            entry_type=entry_type,
            project=project,
            include_completed=include_completed,
        )
        print(result)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_find(args: list[str]) -> int:
    """Full-text search entries."""
    from noodle.surfacing import search_entries_formatted

    if not args:
        print("Usage: noodle find <query>", file=sys.stderr)
        return 1

    query = " ".join(args)

    try:
        result = search_entries_formatted(query)
        print(result)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_done(args: list[str]) -> int:
    """Mark a task as completed."""
    from noodle.db import Database

    if not args:
        print("Usage: noodle done <id>", file=sys.stderr)
        return 1

    entry_id = args[0]

    try:
        db = Database()
        success = db.complete_task(entry_id)
        if success:
            print(f"Completed: {entry_id}")
            return 0
        else:
            print(f"Not found or not a task: {entry_id}", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_digest() -> int:
    """Show daily digest."""
    from noodle.surfacing import generate_daily_digest

    try:
        digest = generate_daily_digest()
        print(digest)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_weekly() -> int:
    """Show weekly review."""
    from noodle.surfacing import generate_weekly_review

    try:
        review = generate_weekly_review()
        print(review)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_health() -> int:
    """Show system health."""
    from noodle.health import run_health_check, format_health_report

    checks = run_health_check()
    print(format_health_report(checks))
    return 0


def cmd_retype(args: list[str]) -> int:
    """Change entry type."""
    from noodle.db import Database

    if len(args) < 2:
        print("Usage: noodle retype <id> <type>", file=sys.stderr)
        print("Types: task, thought, person, event", file=sys.stderr)
        return 1

    entry_id = args[0]
    new_type = args[1]

    if new_type not in ("task", "thought", "person", "event"):
        print(f"Invalid type: {new_type}", file=sys.stderr)
        print("Types: task, thought, person, event", file=sys.stderr)
        return 1

    try:
        db = Database()
        success = db.update_entry_type(entry_id, new_type)
        if success:
            print(f"Retyped: {entry_id} → {new_type}")
            return 0
        else:
            print(f"Entry not found: {entry_id}", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_review() -> int:
    """Interactive review of pending items."""
    from noodle.db import Database

    db = Database()
    entries = db.get_pending_reclassification()

    if not entries:
        print("No entries pending review.")
        return 0

    print(f"Pending review: {len(entries)} items\n")

    for entry in entries:
        print(f"ID: {entry['id']}")
        print(f"Current: {entry['type']}")
        print(f"Title: {entry['title']}")
        if entry.get('body'):
            print(f"Body: {entry['body'][:100]}...")
        print()

        # Prompt for action
        action = input("[t]ask [h]ought [p]erson [e]vent [s]kip [q]uit: ").strip().lower()

        if action == 'q':
            break
        elif action == 's':
            continue
        elif action in ('t', 'task'):
            db.update_entry_type(entry['id'], 'task')
            print("→ task\n")
        elif action in ('h', 'thought'):
            db.update_entry_type(entry['id'], 'thought')
            print("→ thought\n")
        elif action in ('p', 'person'):
            db.update_entry_type(entry['id'], 'person')
            print("→ person\n")
        elif action in ('e', 'event'):
            db.update_entry_type(entry['id'], 'event')
            print("→ event\n")

    return 0


def cmd_gc() -> int:
    """Garbage collection and cleanup."""
    from noodle.db import Database
    from noodle.config import get_noodle_home

    print("Running garbage collection...")

    # Clean up processed.log entries that are in the database
    noodle_home = get_noodle_home()
    processed_path = noodle_home / "processed.log"

    if processed_path.exists():
        # Count lines before
        with open(processed_path) as f:
            before = sum(1 for _ in f)
        print(f"  Processed log: {before} entries")

    # Check for orphaned entries
    db = Database()
    stats = db.get_stats()
    pending = stats.get("pending_reclassification", 0)

    if pending > 0:
        print(f"  Pending review: {pending} items")

    print("Done.")
    return 0


def cmd_install_systemd() -> int:
    """Install systemd user units."""
    from pathlib import Path
    import shutil

    # Source directory (in package)
    src_dir = Path(__file__).parent / "systemd"
    if not src_dir.exists():
        print(f"Error: systemd units not found at {src_dir}", file=sys.stderr)
        return 1

    # Destination directory
    dest_dir = Path.home() / ".config" / "systemd" / "user"
    dest_dir.mkdir(parents=True, exist_ok=True)

    units = [
        "noodle-inbox.path",
        "noodle-inbox.service",
        "noodle-digest.timer",
        "noodle-digest.service",
        "noodle-weekly.timer",
        "noodle-weekly.service",
        "noodle-telegram.service",
    ]

    for unit in units:
        src = src_dir / unit
        dest = dest_dir / unit
        shutil.copy(src, dest)
        print(f"Installed: {dest}")

    print("\nTo enable:")
    print("  systemctl --user daemon-reload")
    print("  systemctl --user enable --now noodle-inbox.path")
    print("  systemctl --user enable --now noodle-digest.timer")
    print("  systemctl --user enable --now noodle-weekly.timer")
    print("  systemctl --user enable --now noodle-telegram.service  # requires NOODLE_TELEGRAM_TOKEN")

    return 0


def main() -> int:
    """
    Main entry point.

    Optimized for minimal startup time on the capture path.
    """
    args = sys.argv[1:]

    # No args - check for piped input
    if not args:
        if not sys.stdin.isatty():
            # Reading from pipe
            text = sys.stdin.read().strip()
            if text:
                entry_id = capture(text)
                print(entry_id)
                return 0
        print_help()
        return 0

    # Handle flags and commands
    first_arg = args[0]

    if first_arg in ("--help", "-h", "help"):
        print_help()
        return 0

    if first_arg in ("--version", "-v", "version"):
        print_version()
        return 0

    # Subcommands (lazy import to keep startup fast)
    if first_arg == "process-inbox":
        return cmd_process_inbox()

    if first_arg == "stats":
        return cmd_stats()

    if first_arg == "list":
        return cmd_list(args[1:])

    if first_arg == "find":
        return cmd_find(args[1:])

    if first_arg == "done":
        return cmd_done(args[1:])

    if first_arg == "digest":
        return cmd_digest()

    if first_arg == "weekly":
        return cmd_weekly()

    if first_arg == "health":
        return cmd_health()

    if first_arg == "retype":
        return cmd_retype(args[1:])

    if first_arg == "review":
        return cmd_review()

    if first_arg == "gc":
        return cmd_gc()

    if first_arg == "install-systemd":
        return cmd_install_systemd()

    if first_arg == "telegram":
        from noodle.telegram_bot import main as telegram_main
        return telegram_main()

    # Everything else is a thought to capture
    # Join all args (allows: noodle Remember to email Sarah)
    text = " ".join(args)

    if not text.strip():
        print("Error: Empty thought", file=sys.stderr)
        return 1

    entry_id = capture(text)
    print(entry_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())

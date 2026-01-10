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
    noodle process-inbox          Process inbox through classifier
    noodle stats                  Show database statistics

Options:
    noodle --help, -h             Show this help
    noodle --version, -v          Show version

Examples:
    noodle "Remember to email Sarah"
    noodle "What if we used Redis for caching?"
    echo "Piped thought" | noodle

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
    pending = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 2)
        if len(parts) >= 3:
            entry_id, timestamp, text = parts
            if entry_id not in processed_ids:
                # Unescape text
                text = text.replace("\\n", "\n").replace("\\t", "\t")
                pending.append({
                    "id": entry_id,
                    "created_at": timestamp,
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

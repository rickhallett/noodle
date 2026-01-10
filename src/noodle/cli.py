"""
CLI for Noodle.

Phase 0: Minimal CLI using only stdlib for fast startup.
Later phases can add rich CLI framework if needed.

Usage:
    noodle "your thought here"      # Capture (primary interface)
    noodle --help                   # Show help
    noodle --version                # Show version
"""

import sys


def print_help() -> None:
    """Print help message."""
    print("""noodle - local-first second brain

Usage:
    noodle "your thought here"    Capture a thought (O(1) ingress)
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

    # Handle flags
    first_arg = args[0]

    if first_arg in ("--help", "-h"):
        print_help()
        return 0

    if first_arg in ("--version", "-v"):
        print_version()
        return 0

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

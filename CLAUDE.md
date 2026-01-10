# CLAUDE.md

This file provides context for Claude Code when working on this project.

## Project Overview

Noodle is a local-first second brain for Arch Linux. It captures thoughts with zero friction and uses LLM classification to route them into four buckets: `task`, `thought`, `person`, `event`.

## Key Principles

### O(1) Ingress
The capture command MUST complete in under 150ms with zero user decisions. No flags, no type selection, no prompts at capture time.

```bash
# CORRECT
noodle "thought"

# WRONG - violates O(1)
noodle --type task "thought"
```

### Four Types Only
The taxonomy is FROZEN. Never add new types. Extend via tags instead.
- `task` — actionable items
- `thought` — ideas, notes, references
- `person` — contact information
- `event` — time-bound items

### Trust Guarantee
Every item in `inbox.log` MUST be processed. Graceful degradation if LLM fails.

### Push Over Pull
Proactive surfacing (digests, notifications) is primary. Search is secondary.

### No Guilt
Rolling time windows. Weekly review = last 7 days only. No cumulative backlog.

## Tech Stack

- **Language**: Python 3.13+
- **Package Manager**: uv (Astral)
- **Database**: SQLite
- **LLM**: OpenAI API (gpt-4o-mini for classification)
- **Notifications**: libnotify (notify-send)
- **Automation**: systemd user units

## Project Structure

```
src/noodle/
├── __init__.py      # Package metadata
├── cli.py           # CLI entry point (stdlib argparse, not click)
├── config.py        # XDG paths, config loading
├── ingress.py       # O(1) capture to inbox.log
├── db.py            # SQLite operations (Phase 1)
├── classifier.py    # LLM classification (Phase 1)
├── router.py        # Route entries to storage (Phase 1)
├── surfacing.py     # Digests, queries (Phase 2)
└── ...
```

## Commands

```bash
# Development
uv sync              # Install dependencies
uv run noodle "x"    # Run CLI
uv add <pkg>         # Add dependency
uv run pytest        # Run tests

# Git
/atomic-commit       # Claude command for focused commits
```

## Commit Style

Use atomic commits with conventional format:
```
<type>: <subject>

[body]
```

Types: `feat`, `fix`, `refactor`, `docs`, `style`, `test`, `chore`

NO AI attribution or co-author tags in commits.

## Implementation Phases

- **Phase 0** ✅: Foundation — CLI captures to inbox.log
- **Phase 1**: Classification — LLM routes to four buckets
- **Phase 2**: Surfacing — digests, search, systemd
- **Phase 3**: Integration — MCP server for Claude Code
- **Phase 4**: Mobile — Telegram bot
- **Phase 5**: Polish — TUI, health, gc

## Key Files

- `docs/specs/init.md` — Full design specification
- `docs/specs/roadmap.md` — Implementation phases with verification
- `~/noodle/inbox.log` — Raw captured thoughts
- `~/noodle/noodle.db` — SQLite database (Phase 1+)

## Testing

Verification checkpoints exist for each phase. See `docs/specs/roadmap.md`.

Phase 0 checkpoint:
```bash
uv run noodle "test"     # Returns ID
cat ~/noodle/inbox.log   # Shows entry
time uv run noodle "x"   # Under 150ms
```

## Common Tasks

### Adding a new CLI command
1. Add function to `cli.py`
2. Keep imports lazy for startup speed
3. Update help text
4. Add to README

### Adding a dependency
```bash
uv add <package>           # Runtime
uv add --dev <package>     # Dev only
uv add --optional <group> <package>  # Optional group
```

### Database changes
1. Update schema in `db.py`
2. Add migration if needed
3. Update `docs/specs/init.md` schema section

# Noodle

> Local-first second brain for Arch Linux.

A cognitive augmentation system that captures thoughts with zero friction and surfaces them when relevant.

## Philosophy

Noodle is not an app. It's a **hardware upgrade for an ancient processor**.

- **O(1) Ingress**: Zero decisions at capture. Just `noodle "thought"`.
- **Four Buckets**: `task`, `thought`, `person`, `event`. No more, ever.
- **Push Over Pull**: The system surfaces info to you via digests and notifications.
- **No Guilt**: Rolling time windows. Miss a week? No backlog monster.
- **Trust Guarantee**: Every captured thought WILL be processed.

## Quick Start

```bash
# Install
uv sync

# Capture a thought
uv run noodle "Remember to email Sarah about the deadline"
# => 1736512547382

# That's it. Classification happens async.
```

## Installation

### Development

```bash
git clone git@github.com:rickhallett/noodle.git
cd noodle
uv sync
uv run noodle "test thought"
```

### Global Install

```bash
uv tool install -e .
noodle "now available globally"
```

## Usage

```bash
# Capture (the only command you need daily)
noodle "your thought here"
echo "piped thought" | noodle

# That's it for Phase 0.
# More commands coming in later phases:
# noodle list, noodle find, noodle done, noodle digest, etc.
```

## Architecture

```
You → noodle "thought" → inbox.log → [Classifier] → noodle.db
                                          ↓
                                   (confidence < 0.75)
                                          ↓
                                   manual_review.md
```

### The Four Types

| Type | Purpose | Examples |
|------|---------|----------|
| `task` | Things to DO | "Email Sarah", "Review PR" |
| `thought` | Things to REMEMBER | "What if we used Redis?", "Article on X" |
| `person` | Info ABOUT someone | "Jake works at Stripe" |
| `event` | Things at a TIME | "Standup Monday 10am" |

### Data Storage

```
~/noodle/
├── inbox.log        # Raw captures (append-only)
├── noodle.db        # SQLite (structured data)
├── thoughts/        # Markdown (long-form)
├── people/          # Contact notes
└── projects/        # Project directories
```

## Development

```bash
# Setup
uv sync

# Run
uv run noodle "thought"

# Add dependency
uv add httpx

# Add dev dependency
uv add --dev pytest

# Test (Phase 5)
uv run pytest
```

## Roadmap

- [x] **Phase 0**: Foundation — `noodle "thought"` works
- [ ] **Phase 1**: Classification — LLM auto-categorizes
- [ ] **Phase 2**: Surfacing — digests, search, systemd timers
- [ ] **Phase 3**: Integration — Claude Code MCP server
- [ ] **Phase 4**: Mobile — Telegram bot
- [ ] **Phase 5**: Polish — TUI, health checks, docs

See [docs/specs/roadmap.md](docs/specs/roadmap.md) for details.

## Specs

- [Design Specification](docs/specs/init.md) — Full architecture and philosophy
- [Implementation Roadmap](docs/specs/roadmap.md) — Phased build plan

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (package manager)
- Arch Linux (designed for, but should work anywhere)

## License

MIT

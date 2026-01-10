# Noodle

Local-first second brain for Arch Linux.

## Quick Start

```bash
# Install with uv
uv sync

# Capture a thought
uv run noodle "Remember to email Sarah"

# Or install globally
uv tool install -e .
noodle "Remember to email Sarah"
```

## Development

```bash
# Setup
uv sync

# Run
uv run noodle "your thought"

# Add dependencies
uv add httpx              # Runtime dependency
uv add --dev pytest       # Dev dependency

# Run tests (Phase 5)
uv run pytest
```

## Philosophy

- **O(1) ingress**: Zero decisions at capture time
- **Push over pull**: System surfaces info to you
- **Four buckets**: task, thought, person, event
- **No guilt**: Rolling time windows, no backlog

See `docs/specs/init.md` for full specification.

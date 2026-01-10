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
# Clone and install
git clone git@github.com:rickhallett/noodle.git
cd noodle
uv sync

# Capture a thought
uv run noodle "Remember to email Sarah about the deadline"
# => 1736512547382

# Process inbox (requires API key)
export ANTHROPIC_API_KEY="sk-ant-..."
uv run noodle process-inbox

# Check system status
uv run noodle health
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
# Install globally via uv
uv tool install -e /path/to/noodle

# Now available everywhere
noodle "thought"
```

## Commands

### Capture

```bash
noodle "your thought here"        # Capture a thought
echo "piped thought" | noodle     # Pipe input
```

### Query

```bash
noodle list                       # List all entries
noodle list --type task           # Filter by type
noodle list --project myproject   # Filter by project
noodle list --all                 # Include completed tasks
noodle find "search query"        # Full-text search
```

### Actions

```bash
noodle done <id>                  # Mark task as completed
noodle retype <id> <type>         # Change entry type (task/thought/person/event)
```

### Surfacing

```bash
noodle digest                     # Daily digest
noodle weekly                     # Weekly review
```

### Maintenance

```bash
noodle process-inbox              # Process pending inbox items
noodle review                     # Interactive review of low-confidence items
noodle health                     # System health check
noodle gc                         # Garbage collection
noodle stats                      # Database statistics
```

### Services

```bash
noodle telegram                   # Run Telegram bot
noodle install-systemd            # Install systemd user units
```

## Configuration

Configuration lives in `~/.config/noodle/config.toml`:

```toml
# Noodle configuration

[noodle]
home = "/home/user/noodle"        # Data directory (default: ~/noodle)

[classifier]
confidence_threshold = 0.75       # Below this → manual review

[llm]
provider = "anthropic"            # or "openai"
model = "claude-haiku-4-5-20251001"

# For Anthropic (default)
anthropic_api_key = "sk-ant-..."  # Or use ANTHROPIC_API_KEY env var

# For OpenAI
# provider = "openai"
# model = "gpt-4o-mini"
# openai_api_key = "sk-..."       # Or use OPENAI_API_KEY env var

[telegram]
token = "123456789:ABC..."        # From @BotFather
authorized_users = [123456789]    # Your Telegram user ID(s)
```

### Environment Variables

```bash
# LLM API Keys
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."

# Telegram Bot
export NOODLE_TELEGRAM_TOKEN="123456789:ABC..."
export NOODLE_TELEGRAM_USERS="123456789,987654321"

# Custom data directory
export NOODLE_HOME="/path/to/noodle"
```

## Data Storage

```
~/noodle/
├── inbox.log        # Raw captures (append-only, TSV format)
├── processed.log    # Processed entry IDs
├── noodle.db        # SQLite database
└── manual_review.md # Low-confidence items for review
```

### The Four Types

| Type | Purpose | Examples |
|------|---------|----------|
| `task` | Things to DO | "Email Sarah", "Review PR" |
| `thought` | Things to REMEMBER | "What if we used Redis?", "Article on X" |
| `person` | Info ABOUT someone | "Jake works at Stripe" |
| `event` | Things at a TIME | "Standup Monday 10am" |

## Background Processes

Noodle uses systemd user units for automation.

### Install Units

```bash
noodle install-systemd
systemctl --user daemon-reload
```

### Available Units

| Unit | Purpose | Trigger |
|------|---------|---------|
| `noodle-inbox.path` | Auto-process inbox | When inbox.log changes |
| `noodle-inbox.service` | Process inbox | Triggered by path unit |
| `noodle-digest.timer` | Daily digest | Every day at 8:00 AM |
| `noodle-weekly.timer` | Weekly review | Every Sunday at 10:00 AM |
| `noodle-telegram.service` | Telegram bot | Manual start |

### Enable Services

```bash
# Auto-process inbox when new items arrive
systemctl --user enable --now noodle-inbox.path

# Daily digest at 8am
systemctl --user enable --now noodle-digest.timer

# Weekly review on Sundays at 10am
systemctl --user enable --now noodle-weekly.timer

# Telegram bot (requires token configured)
systemctl --user enable --now noodle-telegram.service
```

### Check Status

```bash
systemctl --user status noodle-inbox.path
systemctl --user status noodle-telegram.service
journalctl --user -u noodle-telegram.service -f  # View logs
```

## Telegram Bot Setup

### 1. Create Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot`
3. Choose a name (e.g., "Noodle Brain")
4. Choose a username ending in `bot` (e.g., `my_noodle_bot`)
5. Copy the token BotFather gives you

### 2. Configure

Add to `~/.config/noodle/config.toml`:

```toml
[telegram]
token = "123456789:ABCdefGHI..."
authorized_users = []  # Will add after step 3
```

### 3. Get Your User ID

```bash
uv run noodle telegram
```

Message your bot — it will reply with "Unauthorized. Your ID: XXXXXXX"

### 4. Authorize Yourself

Update config with your ID:

```toml
[telegram]
token = "123456789:ABCdefGHI..."
authorized_users = [XXXXXXX]
```

### 5. Run as Service

```bash
systemctl --user enable --now noodle-telegram.service
```

### Usage

Send any message to your bot:
- "Remember to buy milk" → Captured as thought
- "Email boss about deadline" → Captured, classified as task after processing

The bot replies with `Captured: <entry_id>`.

## Claude Code Integration

Noodle includes an MCP server for Claude Code integration.

### Setup

Add to `~/.config/claude-code/settings.json`:

```json
{
  "mcpServers": {
    "noodle": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/noodle", "python", "-m", "noodle_mcp.server"]
    }
  }
}
```

### Slash Commands

- `/noodle "thought"` — Capture a thought
- `/noodle-find query` — Search entries
- `/noodle-context topic` — Get related entries
- `/noodle-tasks` — Show tasks
- `/noodle-digest` — Show daily digest
- `/noodle-review` — Review low-confidence entries

### MCP Tools

| Tool | Description |
|------|-------------|
| `noodle_add` | Capture a thought |
| `noodle_search` | Full-text search |
| `noodle_tasks` | List tasks |
| `noodle_complete` | Complete a task |
| `noodle_digest` | Daily digest |
| `noodle_weekly` | Weekly review |
| `noodle_context` | Related entries |
| `noodle_pending` | Review queue |
| `noodle_retype` | Change entry type |

## Daily Workflow

### Morning

```bash
noodle digest                     # See what's due today
```

### Throughout the Day

```bash
noodle "thought as it occurs"     # Capture instantly
# Or message your Telegram bot from mobile
```

### End of Day

```bash
noodle list --type task           # Review tasks
noodle done <id>                  # Mark completed
```

### Weekly

```bash
noodle weekly                     # Review the week
noodle review                     # Handle any low-confidence items
```

## Architecture

```
You → noodle "thought" → inbox.log → [Classifier] → noodle.db
                              ↓              ↓
                         (systemd)    (confidence < 0.75)
                              ↓              ↓
                      auto-process    manual_review.md
```

### Processing Flow

1. **Capture**: Thought appended to `inbox.log` (< 50ms)
2. **Classify**: LLM determines type, extracts metadata
3. **Route**: High confidence → database, Low confidence → manual review
4. **Surface**: Digests and search make info accessible

## Health Check

```bash
$ noodle health
Noodle Health Check
----------------------------------------
✓ Database: OK (127 entries)
✓ Inbox: OK (0 pending)
✓ Classifier: OK (Anthropic)
✓ Telegram: OK (1 users)
✓ Manual Review: Empty
✓ Systemd: OK (3/3 active)
```

## Development

```bash
uv sync                           # Install dependencies
uv run noodle "thought"           # Run CLI
uv add <package>                  # Add dependency
uv run pytest                     # Run tests
```

## Specs

- [Design Specification](docs/specs/init.md) — Full architecture and philosophy
- [Implementation Roadmap](docs/specs/roadmap.md) — Phased build plan

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (package manager)
- Arch Linux (designed for, but should work anywhere)
- Anthropic or OpenAI API key (for classification)

## License

MIT

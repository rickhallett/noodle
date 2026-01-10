# Noodle Implementation Roadmap

> Verifiable phases from zero to working second brain.

## Overview

```
Phase 0: Foundation     → Can capture thoughts locally
Phase 1: Classification → Thoughts are auto-categorized
Phase 2: Surfacing      → System pushes info to you
Phase 3: Integration    → Claude Code can use your brain
Phase 4: Mobile         → Capture from anywhere
Phase 5: Polish         → Production-ready
```

Each phase ends with a **verification checkpoint** — concrete proof it works.

---

## Phase 0: Foundation

**Goal**: Minimal viable ingress. Capture thoughts to a file.

### Deliverables

- [ ] Project structure initialized
- [ ] `noodle` CLI with single command: capture
- [ ] `inbox.log` append-only storage
- [ ] Basic config loading (`~/.config/noodle/config.toml`)
- [ ] Install script / `pyproject.toml`

### Implementation

```
src/noodle/
├── __init__.py
├── cli.py          # Click CLI, just the capture command
├── config.py       # Load config from XDG paths
└── ingress.py      # append_to_inbox() function
```

### Verification Checkpoint

```bash
# Install
pip install -e .

# Capture a thought
$ noodle "Hello world"
1736512547382

# Verify it landed
$ cat ~/noodle/inbox.log
1736512547382	2025-01-10T09:15:47	Hello world

# Verify speed (must be < 100ms)
$ time noodle "Speed test"
real    0m0.047s  # ✓ Pass
```

**Phase 0 is DONE when**:
- `noodle "thought"` returns an ID in under 100ms
- The thought appears in `inbox.log`

---

## Phase 1: Classification

**Goal**: LLM automatically categorizes inbox items into the four buckets.

### Deliverables

- [ ] SQLite schema created (`noodle.db`)
- [ ] Database module (`db.py`)
- [ ] Classifier module with API call (`classifier.py`)
- [ ] Routing logic (confidence threshold, manual review)
- [ ] `process-inbox` command
- [ ] `processed.log` audit trail
- [ ] `manual_review.md` for low-confidence items

### Implementation

```
src/noodle/
├── db.py           # SQLite operations, schema init
├── classifier.py   # LLM API call, JSON parsing
├── router.py       # Route classified entries to storage
└── cli.py          # Add: process-inbox command
```

### Verification Checkpoint

```bash
# Add some test thoughts
$ noodle "Email Sarah about the deadline"
$ noodle "What if we used Redis for caching?"
$ noodle "Met Jake at KubeCon - works at Stripe"
$ noodle "Team standup Monday 10am"

# Process the inbox
$ noodle process-inbox
Processing 4 items...
  1736512547382 → task (0.94)
  1736512547383 → thought (0.91)
  1736512547384 → person (0.88)
  1736512547385 → event (0.92)
Done. 4 classified, 0 manual review.

# Verify database
$ sqlite3 ~/noodle/noodle.db "SELECT type, title FROM entries"
task|Email Sarah about the deadline
thought|Use Redis for caching
person|Jake - works at Stripe
event|Team standup Monday 10am

# Verify processed log
$ cat ~/noodle/processed.log
1736512547382	2025-01-10T09:16:01	classified	task	0.94	entries
...
```

**Phase 1 is DONE when**:
- `noodle process-inbox` classifies entries via API
- Entries appear in SQLite with correct types
- Low-confidence items go to `manual_review.md`

---

## Phase 2: Surfacing

**Goal**: System proactively shows you relevant information.

### Deliverables

- [ ] `noodle digest` command (daily summary)
- [ ] `noodle weekly` command (weekly review)
- [ ] `noodle list` command with filters
- [ ] `noodle find` command (full-text search)
- [ ] `noodle done` command (complete tasks)
- [ ] systemd user units (path watcher, timers)
- [ ] Desktop notifications via `notify-send`

### Implementation

```
src/noodle/
├── surfacing.py    # generate_daily_digest(), generate_weekly_review()
├── queries.py      # list, find, show queries
└── cli.py          # Add: digest, weekly, list, find, done, show

systemd/
├── noodle-classifier.path
├── noodle-classifier.service
├── noodle-digest.timer
├── noodle-digest.service
├── noodle-sync.timer
└── noodle-sync.service
```

### Verification Checkpoint

```bash
# Generate digest
$ noodle digest
# Noodle Daily Digest - 2025-01-10

## Due Today (1)
- [ ] Email Sarah about the deadline

## Recent Thoughts (2)
- "Use Redis for caching" (today)
- "Team standup Monday 10am" (today)

# List tasks
$ noodle list task
1736512547382  task  "Email Sarah about the deadline"  due:today

# Complete a task
$ noodle done 1736512547382
Completed: 1736512547382

# Full-text search
$ noodle find redis
1736512547383  thought  "Use Redis for caching"

# Verify systemd units
$ systemctl --user status noodle-classifier.path
● noodle-classifier.path - Watch noodle inbox
     Active: active (waiting)

# Trigger auto-classification by adding a thought
$ noodle "Test auto-classification"
$ sleep 2
$ sqlite3 ~/noodle/noodle.db "SELECT COUNT(*) FROM entries"
6  # ✓ Auto-processed
```

**Phase 2 is DONE when**:
- `noodle digest` outputs a formatted summary
- `noodle list/find/done` work correctly
- systemd path unit auto-triggers classification
- `notify-send` fires for low-confidence items

---

## Phase 3: Integration

**Goal**: Claude Code can read from and write to your brain.

### Deliverables

- [ ] MCP server (`noodle_mcp/server.py`)
- [ ] Tools: `noodle_add`, `noodle_search`, `noodle_context`, `noodle_tasks`, `noodle_complete`, `noodle_retype`, `noodle_pending`
- [ ] Slash commands in `.claude/commands/`
- [ ] MCP config for Claude Code

### Implementation

```
mcp/noodle_mcp/
├── __init__.py
└── server.py       # MCP server with tools

.claude/commands/
├── noodle.md
├── noodle-find.md
├── noodle-context.md
├── noodle-review.md
└── noodle-health.md
```

### Verification Checkpoint

```bash
# Start MCP server manually for testing
$ python -m noodle_mcp.server &

# Test via Claude Code
> /noodle "Testing MCP integration"
Captured: 1736512547390

> /noodle-find redis
Found 1 entry:
[thought] "Use Redis for caching" (Jan 10)

> /noodle-context authentication
Found 2 related entries:
...

# Verify MCP config works
$ cat ~/.config/claude-code/settings.json | jq '.mcpServers.noodle'
{
  "command": "python",
  "args": ["-m", "noodle_mcp.server"]
}
```

**Phase 3 is DONE when**:
- `/noodle "thought"` captures via MCP
- `/noodle-find` returns results
- `/noodle-context` synthesizes related entries

---

## Phase 4: Mobile

**Goal**: Capture thoughts from phone, anywhere.

### Deliverables

- [ ] Telegram bot (`telegram_bot.py`)
- [ ] Bot authentication (authorized user only)
- [ ] systemd service for bot
- [ ] Confirmation replies

### Implementation

```
src/noodle/
└── telegram_bot.py  # Bot with message handler

systemd/
└── noodle-telegram.service
```

### Verification Checkpoint

```bash
# Start bot
$ systemctl --user start noodle-telegram

# Send message to bot from phone
"Remember to buy milk"

# Bot replies
"Captured: 1736512547391"

# Verify on desktop
$ sqlite3 ~/noodle/noodle.db "SELECT title FROM entries ORDER BY created_at DESC LIMIT 1"
Buy milk

# Verify source tracking
$ sqlite3 ~/noodle/noodle.db "SELECT source FROM entries ORDER BY created_at DESC LIMIT 1"
telegram
```

**Phase 4 is DONE when**:
- Telegram message → appears in noodle
- Bot only responds to authorized user
- Source is tracked as `telegram`

---

## Phase 5: Polish

**Goal**: Production-ready for daily use.

### Deliverables

- [ ] `noodle review` TUI for manual review queue
- [ ] `noodle health` system check
- [ ] `noodle gc` garbage collection
- [ ] `noodle retype` / `noodle link` correction commands
- [ ] Git sync automation
- [ ] Error handling / retry logic
- [ ] Logging configuration
- [ ] Documentation (README, man page)

### Implementation

```
src/noodle/
├── tui.py          # Textual TUI for review
├── health.py       # System health checks
├── gc.py           # Garbage collection
└── sync.py         # Git sync logic
```

### Verification Checkpoint

```bash
# Health check
$ noodle health
Database: ✓ OK (127 entries)
Inbox: ✓ OK (0 pending)
Classifier: ✓ OK (API responding)
Telegram: ✓ OK (bot connected)
Git: ✓ OK (last sync 5m ago)
Manual review: 2 items pending

# Review TUI
$ noodle review
# Opens TUI, can retype items with single keypress

# Garbage collection
$ noodle gc
Cleaned: 0 orphaned entries
Reclassified: 2 pending items

# Retype a misclassified entry
$ noodle retype 1736512547382 thought
Retyped: 1736512547382 → thought

# Git sync
$ noodle sync
[main abc1234] Auto-sync: 2025-01-10T18:00:00
 3 files changed
Already up to date.
Pushed to origin/main
```

**Phase 5 is DONE when**:
- `noodle health` reports all systems
- `noodle review` TUI works
- Git auto-sync commits and pushes
- System runs unattended for 1 week

---

## Dependency Graph

```
Phase 0 ─────► Phase 1 ─────► Phase 2 ─────► Phase 5
   │              │              │
   │              │              └──────────► Phase 3
   │              │                              │
   │              └──────────────────────────────┤
   │                                             │
   └─────────────────────────────────────────────┴──► Phase 4
```

- **Phase 0** blocks everything (need ingress first)
- **Phase 1** blocks 2, 3, 4, 5 (need DB and classification)
- **Phase 2** blocks 3 (need queries for MCP)
- **Phases 3, 4, 5** can be done in parallel after Phase 2

---

## Estimated Effort

| Phase | Scope | Effort |
|-------|-------|--------|
| Phase 0 | Foundation | Small — few hours |
| Phase 1 | Classification | Medium — 1-2 days |
| Phase 2 | Surfacing | Medium — 1-2 days |
| Phase 3 | Integration | Medium — 1 day |
| Phase 4 | Mobile | Small — few hours |
| Phase 5 | Polish | Medium — 1-2 days |

**Total to MVP (Phases 0-2)**: ~3-5 days
**Total to full system**: ~1-2 weeks

---

## Let's Begin

**Start with Phase 0**. It's the smallest, and everything else depends on it.

```bash
# First command to run:
mkdir -p src/noodle
touch src/noodle/__init__.py
```

Ready?

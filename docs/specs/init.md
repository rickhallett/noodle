# Noodle: Implementation Specification

> A local-first, terminal-centric second brain for Arch Linux.

**Project**: `noodle`
**CLI Command**: `noodle`
**Version**: 0.1.0
**Author**: kai

---

## Table of Contents

1. [Cognitive Philosophy](#cognitive-philosophy)
2. [Overview](#overview)
3. [Directory Structure](#directory-structure)
4. [Core Components](#core-components)
5. [Data Schema](#data-schema)
6. [CLI Interface](#cli-interface)
7. [LLM Classifier](#llm-classifier)
8. [Systemd Integration](#systemd-integration)
9. [Claude Code Integration](#claude-code-integration)
10. [Mobile Ingress](#mobile-ingress)
11. [Extension Roadmap](#extension-roadmap)

---

## Cognitive Philosophy

Noodle is not an app. It is a **hardware upgrade for an ancient processor**.

### The Problem

Human cognitive architecture hasn't changed in 500,000 years. We have:
- **4-7 items** in working memory (hard limit)
- **No background processing** (thoughts consume active cycles)
- **Lossy storage** (forgetting is the default)

Every unfinished thought is an **open loop** - a memory leak that consumes energy as "low-grade anxiety" or a "background hum." The brain cannot garbage collect these loops on its own.

### The Solution

Noodle provides what the biological brain lacks:
- **Persistent storage** that never forgets
- **Background processing** that organizes while you sleep
- **Proactive surfacing** that pushes relevant context to you

The system must earn **trust** through reliability. If the user doubts that a captured thought will be processed, they won't "close the loop" mentally, defeating the purpose.

### Core Invariants

These rules are non-negotiable:

| Invariant | Rationale |
|-----------|-----------|
| **O(1) Ingress** | Zero decisions at capture. If you have to think about *where* or *what type*, you're paying a cognitive tax. |
| **Guaranteed Processing** | Every item entering the inbox WILL be processed. No silent failures. Graceful degradation if LLM is down. |
| **Push Over Pull** | Humans don't proactively search. The system must surface information at the right moment. |
| **No Guilt UI** | If you miss a week, the system summarizes the last 7 days. No backlog monster. No catch-up required. |
| **Stable Taxonomy** | Types are frozen after initial design. Complexity grows through tags, not new types. |

### The Four Buckets

Following the principle of "routing, not organizing," noodle has exactly **four entry types**:

| Type | Purpose | Jones Mapping |
|------|---------|---------------|
| `task` | Actionable items - things to DO | "Admin" |
| `thought` | Non-actionable captures - ideas, notes, references | "Ideas" |
| `person` | Information about people | "People" |
| `event` | Time-bound items - meetings, deadlines | (Calendar) |

**Projects** are a separate organizing dimension, not a type. Any entry can belong to a project.

This constraint ensures "Mental Portability" - you can hold the entire taxonomy in working memory.

---

## Overview

Noodle is a cognitive augmentation system designed for software engineers on Arch Linux. It prioritizes:

- **Zero-friction ingress**: < 100ms to capture a thought, zero decisions
- **Local-first storage**: SQLite + Markdown, Git-backed
- **LLM-powered classification**: Automatic routing to the four buckets
- **Push-first architecture**: Proactive surfacing via notifications and digests
- **Terminal-native**: CLI-first, scriptable, composable
- **Claude Code integration**: MCP server + slash commands for seamless AI assistance

### Design Principles

1. **Grep-able**: All data in flat files or queryable SQLite
2. **Stateless logic**: Scripts run on-demand, no daemons unless necessary
3. **Extensible**: Unix philosophy - small tools that compose
4. **Portable**: `~/noodle/` moves with you via Git
5. **Trust-first**: Every captured thought is guaranteed to be processed
6. **Push-primary**: Digests and notifications are the main interface; search is secondary
7. **Restart-friendly**: Rolling time windows, no cumulative backlogs

---

## Directory Structure

```
~/noodle/
├── noodle.db              # SQLite database (structured data)
├── inbox.log              # Raw ingress buffer (append-only, never deleted)
├── processed.log          # Processed entries (audit trail)
├── manual_review.md       # Low-confidence items for human review
│
├── thoughts/              # Long-form thought entries (markdown)
│   └── {id}-{slug}.md
│
├── projects/              # Project-specific directories
│   └── {project-slug}/
│       ├── README.md
│       └── notes.md
│
├── people/                # Contact notes
│   └── {person-slug}.md
│
├── logs/                  # Audit trail exports (optional)
│   └── classifier-{date}.jsonl
│
├── config/
│   ├── noodle.toml        # Main configuration
│   ├── prompts/           # LLM prompt templates
│   │   ├── classifier.md
│   │   ├── digest.md
│   │   └── weekly.md
│   └── schemas/           # JSON schemas for LLM output
│       └── entry.schema.json
│
└── .git/                  # Version control
```

### Repository Structure (Development)

```
~/code/repo/brain/
├── docs/
│   └── specs/
│       └── init.md        # This file
│
├── src/
│   └── noodle/
│       ├── __init__.py
│       ├── cli.py         # CLI entry point
│       ├── classifier.py  # LLM classification logic
│       ├── db.py          # SQLite operations
│       ├── config.py      # Configuration management
│       ├── ingress.py     # Input handling
│       └── models.py      # Data models
│
├── mcp/
│   └── noodle_mcp/
│       ├── __init__.py
│       └── server.py      # MCP server for Claude Code
│
├── systemd/
│   ├── noodle-classifier.service
│   ├── noodle-classifier.path
│   ├── noodle-digest.service
│   ├── noodle-digest.timer
│   ├── noodle-sync.service
│   └── noodle-sync.timer
│
├── .claude/
│   └── commands/
│       ├── noodle.md
│       ├── noodle-find.md
│       ├── noodle-review.md
│       └── noodle-health.md
│
├── tests/
├── pyproject.toml
└── README.md
```

---

## Core Components

### 1. Ingress (The Drop Box)

**Purpose**: Capture thoughts with zero friction, zero decisions.

**The O(1) Contract**: The only valid ingress command is:
```bash
noodle "your thought here"
```

No flags. No type selection. No project assignment. Just the thought.

```bash
# These are the ONLY ingress patterns
noodle "Remember to email Sarah about the copy deadline"
noodle "What if we used WebSockets instead of polling?"
noodle "Met Jake at the conference - works on distributed systems"

# Pipe support
echo "Quick thought" | noodle
xclip -o | noodle  # From clipboard

# Voice (future)
noodle --voice
```

**Anti-patterns** (violate O(1) ingress):
```bash
# WRONG - forces a decision at capture time
noodle --type task "..."
noodle --project foo "..."
noodle add --priority high "..."
```

Type assignment, project linking, and prioritization happen **after** classification, not at ingress. If you need to correct a misclassification, use `noodle retype <id>`.

**Implementation**:
```python
# src/noodle/ingress.py
import time
import fcntl
from pathlib import Path
from datetime import datetime

def append_to_inbox(text: str, inbox_path: Path) -> str:
    """
    Append raw text to inbox.log with timestamp. Returns entry ID.

    This function MUST:
    1. Complete in < 100ms
    2. Never fail silently (write or raise)
    3. Use file locking for concurrent safety
    """
    entry_id = f"{int(time.time() * 1000)}"
    timestamp = datetime.now().isoformat()
    line = f"{entry_id}\t{timestamp}\t{text}\n"

    with open(inbox_path, "a") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        f.write(line)
        f.flush()
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    return entry_id
```

**Performance Target**: < 100ms end-to-end.

**Trust Guarantee**: Once `append_to_inbox` returns, the thought is durably stored. The user can mentally "close the loop."

---

### 2. The Trust Guarantee

Every thought that enters `inbox.log` **WILL** be processed. This is the foundation of cognitive offloading.

**Processing States**:
```
inbox.log → [Classifier] → noodle.db + processed.log
                ↓
         (if confidence < 0.75)
                ↓
         manual_review.md + notification
```

**Graceful Degradation**:

If the LLM is unavailable, the system does NOT fail silently:

```python
# src/noodle/classifier.py
def classify_with_fallback(raw_input: str) -> dict:
    """Classify input, falling back gracefully if LLM is unavailable."""
    try:
        return call_llm(raw_input)
    except (ConnectionError, Timeout, LLMError) as e:
        # Fallback: store as unclassified thought
        return {
            "type": "thought",
            "title": raw_input[:100],
            "body": raw_input,
            "confidence": 0.0,  # Will route to manual_review
            "error": str(e),
            "needs_reclassification": True
        }
```

**Audit Trail**:

Every processing attempt is logged:
```
processed.log format:
{entry_id}\t{timestamp}\t{status}\t{type}\t{confidence}\t{destination}
```

Status values: `classified`, `fallback`, `manual_review`, `error`

---

### 3. Classifier (The Sorter)

**Purpose**: LLM-powered ETL that routes entries to the four buckets.

**Input**: Raw text from `inbox.log`
**Output**: Structured JSON matching schema, routed to SQLite/Markdown

**Classification Schema** (4 types only):
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["type", "title", "confidence"],
  "properties": {
    "type": {
      "enum": ["task", "thought", "person", "event"],
      "description": "FROZEN: These four types will never change"
    },
    "title": {
      "type": "string",
      "maxLength": 100
    },
    "body": {
      "type": "string"
    },
    "confidence": {
      "type": "number",
      "minimum": 0,
      "maximum": 1
    },
    "tags": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Extensibility through tags, not new types"
    },
    "project": {
      "type": "string",
      "description": "Project slug if applicable"
    },
    "people": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Referenced people (slugs)"
    },
    "due_date": {
      "type": "string",
      "format": "date",
      "description": "For tasks/events"
    },
    "priority": {
      "enum": ["low", "medium", "high"],
      "description": "Only for tasks. 3 levels, not 4 - simpler."
    }
  }
}
```

**Type Classification Rules**:

| Type | Trigger Signals | Examples |
|------|-----------------|----------|
| `task` | Verbs, "need to", "should", "must", deadlines, assignments | "Email Sarah", "Review PR", "Buy milk" |
| `thought` | "What if", "I think", observations, ideas, notes, URLs, references | "What if we used WebSockets?", "Interesting article on X" |
| `person` | Names with context, contact info, relationship notes | "Met Jake - works at Stripe", "Sarah's email is..." |
| `event` | Dates, times, meetings, appointments | "Team standup Monday 10am", "Conference next week" |

**Routing Logic**:
```python
# src/noodle/classifier.py
def route_entry(classified: dict, db: Database, thoughts_path: Path):
    """Route classified entry to appropriate storage."""

    # Low confidence → manual review (don't pollute main DB)
    if classified["confidence"] < 0.75:
        append_to_manual_review(classified)
        send_notification("Noodle: Item needs review", classified["title"][:50])
        log_processing(classified, status="manual_review")
        return

    entry_type = classified["type"]

    # All entries get a row in SQLite for indexing
    entry_id = db.insert_entry(classified)

    # Long-form thoughts also get a Markdown file
    if entry_type == "thought" and len(classified.get("body", "")) > 200:
        write_markdown_entry(entry_id, classified, thoughts_path)

    # People get their own markdown files
    if entry_type == "person":
        update_person_file(classified)

    log_processing(classified, status="classified")
```

---

### 4. Storage (The Filing Cabinet)

**Dual Storage Strategy**:

| Data Type | Storage | Why |
|-----------|---------|-----|
| Metadata, relationships, queries | SQLite | Fast lookups, SQL queries, ACID |
| Long-form content, human-readable | Markdown | Grep-able, editable, Git-friendly |
| Raw audit trail | JSONL logs | Append-only, debuggable |

---

### 5. Surfacing (The Tap on the Shoulder)

**Purpose**: Proactively surface relevant information. This is the PRIMARY interface.

> "Humans don't retrieve information; they respond to what is pushed in front of them."

**Design Constraint**: High signal-to-noise ratio. Trust is built through "small, frequent, actionable" outputs.

**Daily Digest** (08:00):

Format: **Maximum 5 items**, actionable items first.

```markdown
# Noodle Daily Digest - 2025-01-10

## Due Today (2)
- [ ] Email Sarah about copy deadline
- [ ] Review PR #423

## Needs Attention (1)
- Meeting notes from yesterday need review

---
3 items in manual review queue
```

Implementation:
```python
def generate_daily_digest() -> str:
    """Generate daily digest. Max 5 items, actionable first."""
    tasks_due = db.query("""
        SELECT * FROM entries
        WHERE type = 'task'
        AND completed_at IS NULL
        AND due_date <= date('now')
        ORDER BY priority DESC, due_date ASC
        LIMIT 3
    """)

    needs_attention = db.query("""
        SELECT * FROM entries
        WHERE updated_at < datetime('now', '-7 days')
        AND type IN ('task', 'thought')
        AND completed_at IS NULL
        LIMIT 2
    """)

    return format_digest(tasks_due, needs_attention)
```

**Weekly Review** (Sunday 18:00):

Format: Rolling 7-day window. **No backlog.** If you missed a week, the previous week is gone.

```markdown
# Noodle Weekly Review - Week of 2025-01-06

## This Week
- Captured: 23 thoughts
- Completed: 8 tasks
- Created: 5 tasks
- Net task delta: -3 (good!)

## Top Projects
1. noodle (12 entries)
2. work (8 entries)

## Ideas Worth Revisiting
- "What if we used WebSockets?" (Jan 7)
- "Meeting room booking system" (Jan 8)

## Manual Review Queue: 2 items
```

**Restart-Friendly Design**:
```python
def generate_weekly_review() -> str:
    """
    Generate weekly review for the LAST 7 DAYS only.
    No cumulative backlog. No guilt.
    """
    since = datetime.now() - timedelta(days=7)
    # Query only the rolling window
    entries = db.query("""
        SELECT * FROM entries
        WHERE created_at >= ?
    """, [since.isoformat()])
    # ...
```

**Implementation**: systemd timers + `notify-send` / terminal MOTD

---

### 6. Human-in-the-Loop (The Fix Button)

**Manual Review Queue**:
```bash
noodle review              # Interactive TUI for manual_review.md
noodle fix <id>            # Edit specific entry
noodle reclassify <id>     # Re-run classifier with hints
```

**Direct Editing**:
```bash
$EDITOR ~/noodle/manual_review.md
sqlite3 ~/noodle/noodle.db "UPDATE entries SET ..."
```

---

## Data Schema

### SQLite Schema

```sql
-- src/noodle/schema.sql

-- Core entries table
-- TYPE CONSTRAINT: Only 4 types, FROZEN forever. Extend via tags, not new types.
CREATE TABLE entries (
    id TEXT PRIMARY KEY,                    -- Unix timestamp ms
    created_at TEXT NOT NULL,               -- ISO 8601
    updated_at TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('task', 'thought', 'person', 'event')),
    title TEXT NOT NULL,
    body TEXT,
    confidence REAL NOT NULL,
    priority TEXT CHECK(priority IN ('low', 'medium', 'high')),  -- 3 levels, tasks only
    due_date TEXT,                          -- ISO 8601 date (tasks, events)
    completed_at TEXT,                      -- For tasks
    project_id TEXT REFERENCES projects(id),
    source TEXT DEFAULT 'cli',              -- cli, telegram, api, etc.
    raw_input TEXT NOT NULL,                -- Original unprocessed text
    markdown_path TEXT,                     -- Path to .md file if exists
    needs_reclassification INTEGER DEFAULT 0  -- Flag for LLM fallback entries
);

-- Projects
CREATE TABLE projects (
    id TEXT PRIMARY KEY,                    -- slug
    name TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'paused', 'completed', 'archived')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- People/Contacts
CREATE TABLE people (
    id TEXT PRIMARY KEY,                    -- slug
    name TEXT NOT NULL,
    email TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Tags (many-to-many)
CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE entry_tags (
    entry_id TEXT REFERENCES entries(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, tag_id)
);

-- Entry-People relationships
CREATE TABLE entry_people (
    entry_id TEXT REFERENCES entries(id) ON DELETE CASCADE,
    person_id TEXT REFERENCES people(id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, person_id)
);

-- Audit log for classifier debugging
CREATE TABLE classifier_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT REFERENCES entries(id),
    timestamp TEXT NOT NULL,
    raw_input TEXT NOT NULL,
    llm_output TEXT NOT NULL,               -- Full JSON response
    llm_model TEXT NOT NULL,
    confidence REAL NOT NULL,
    processing_time_ms INTEGER,
    routed_to TEXT                          -- Where it was stored
);

-- Full-text search
CREATE VIRTUAL TABLE entries_fts USING fts5(
    title,
    body,
    content='entries',
    content_rowid='rowid'
);

-- Triggers for FTS sync
CREATE TRIGGER entries_ai AFTER INSERT ON entries BEGIN
    INSERT INTO entries_fts(rowid, title, body) VALUES (new.rowid, new.title, new.body);
END;

CREATE TRIGGER entries_ad AFTER DELETE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, title, body) VALUES('delete', old.rowid, old.title, old.body);
END;

CREATE TRIGGER entries_au AFTER UPDATE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, title, body) VALUES('delete', old.rowid, old.title, old.body);
    INSERT INTO entries_fts(rowid, title, body) VALUES (new.rowid, new.title, new.body);
END;

-- Indexes
CREATE INDEX idx_entries_type ON entries(type);
CREATE INDEX idx_entries_project ON entries(project_id);
CREATE INDEX idx_entries_due_date ON entries(due_date);
CREATE INDEX idx_entries_created ON entries(created_at);
```

### Markdown Frontmatter Schema

```yaml
---
id: "1704067200000"
type: idea
title: "Use WebSockets for real-time sync"
created: 2024-01-01T00:00:00
updated: 2024-01-01T00:00:00
tags:
  - architecture
  - sync
project: noodle
people: []
---

Content goes here...
```

---

## CLI Interface

### Command Structure

```
noodle [THOUGHT]              # Primary: capture (O(1) ingress)
noodle <COMMAND> [ARGS]       # Secondary: query and manage
```

### Commands

```bash
# INGRESS (O(1) - no options, no decisions)
noodle "thought"              # THE primary interface. Nothing else.

# QUERY (Pull interface - secondary to push)
noodle list                   # Recent entries (all types)
noodle list tasks             # Filter by type
noodle list thoughts          # Filter by type
noodle list --project foo     # Filter by project
noodle find <query>           # Full-text search
noodle show <id>              # Show entry details

# CORRECTION (Post-classification fixes)
noodle retype <id> <type>     # Change entry type (task, thought, person, event)
noodle retag <id> <tags...>   # Add/replace tags
noodle link <id> <project>    # Link to project
noodle edit <id>              # Open in $EDITOR

# TASK MANAGEMENT
noodle done <id>              # Mark task complete
noodle undone <id>            # Reopen task
noodle defer <id> <date>      # Reschedule task

# REVIEW (Human-in-the-loop)
noodle review                 # Process manual review queue (TUI)
noodle pending                # Show items needing reclassification

# PROJECTS
noodle projects               # List projects
noodle project new <name>     # Create project
noodle project show <slug>    # Project details + entries

# MAINTENANCE
noodle health                 # System health check
noodle gc                     # Garbage collection
noodle sync                   # Git sync
noodle export                 # Export to JSON/CSV

# SURFACING (Manual trigger for push outputs)
noodle digest                 # Show today's digest
noodle weekly                 # Show weekly review

# STATS
noodle stats                  # Overview statistics
noodle stats --week           # Weekly breakdown
```

### Design Note: No Ingress Options

The following commands are **intentionally absent**:

```bash
# THESE DO NOT EXIST - they violate O(1) ingress
noodle add "..."
noodle --type task "..."
noodle --project foo "..."
noodle --priority high "..."
```

If classification is wrong, use `noodle retype`. If project is missing, use `noodle link`.
This keeps ingress at O(1) complexity.

### Options

```bash
--config <path>     # Config file path
--db <path>         # Database path
--verbose, -v       # Verbose output
--json              # JSON output format
--quiet, -q         # Suppress non-essential output
```

### Implementation

```python
# src/noodle/cli.py
import sys
import click
from pathlib import Path

TYPES = ['task', 'thought', 'person', 'event']  # FROZEN

@click.group(invoke_without_command=True)
@click.argument('thought', required=False, nargs=-1)
@click.pass_context
def cli(ctx, thought):
    """
    Noodle: Your local-first second brain.

    Usage: noodle "your thought here"

    No flags. No decisions. Just capture.
    """
    ctx.ensure_object(dict)
    ctx.obj['config'] = load_config()

    if thought:
        # O(1) ingress: capture and exit immediately
        text = ' '.join(thought)
        entry_id = quick_capture(text)
        click.echo(entry_id)  # Just the ID, minimal output
        sys.exit(0)

    # No thought provided and no subcommand = show help
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

@cli.command()
@click.argument('type_filter', required=False, type=click.Choice(TYPES))
@click.option('--project', '-p', help='Filter by project')
@click.option('--limit', '-n', default=20, help='Max results')
def list(type_filter, project, limit):
    """List recent entries, optionally filtered."""
    results = get_entries(type=type_filter, project=project, limit=limit)
    for entry in results:
        click.echo(format_entry_line(entry))

@cli.command()
@click.argument('query', nargs=-1, required=True)
def find(query):
    """Full-text search across all entries."""
    results = search_entries(' '.join(query))
    for entry in results:
        click.echo(format_entry_line(entry))

@cli.command()
@click.argument('entry_id')
@click.argument('new_type', type=click.Choice(TYPES))
def retype(entry_id, new_type):
    """Change an entry's type (post-classification correction)."""
    update_entry_type(entry_id, new_type)
    click.echo(f"Retyped {entry_id} → {new_type}")

@cli.command()
@click.argument('entry_id')
@click.argument('project_slug')
def link(entry_id, project_slug):
    """Link an entry to a project."""
    link_to_project(entry_id, project_slug)
    click.echo(f"Linked {entry_id} → {project_slug}")

@cli.command()
@click.argument('entry_id')
def done(entry_id):
    """Mark a task as complete."""
    complete_task(entry_id)
    click.echo(f"Completed: {entry_id}")

@cli.command()
def review():
    """Process manual review queue (TUI)."""
    from .tui import run_review_tui
    run_review_tui()

@cli.command()
def pending():
    """Show entries needing reclassification."""
    entries = get_pending_reclassification()
    for entry in entries:
        click.echo(format_entry_line(entry))

@cli.command()
def digest():
    """Show today's daily digest."""
    click.echo(generate_daily_digest())

@cli.command()
def weekly():
    """Show weekly review (rolling 7-day window)."""
    click.echo(generate_weekly_review())

@cli.command()
def health():
    """System health check."""
    report = run_health_check()
    click.echo(format_health_report(report))

@cli.command()
def gc():
    """Garbage collection and maintenance."""
    stats = run_gc()
    click.echo(f"Cleaned: {stats['orphaned']} orphaned entries")
    click.echo(f"Processed: {stats['reclassified']} pending items")
```

---

## LLM Classifier

### Prompt Template

```markdown
<!-- config/prompts/classifier.md -->

You are a classifier for a personal knowledge management system called Noodle.
Your job is to route raw thoughts into exactly ONE of four buckets.

## The Four Buckets (ONLY these exist)

1. **task** - Something to DO. Action items, todos, things that require action.
   - Signals: verbs ("email", "call", "review", "buy"), "need to", "should", "must", deadlines
   - Examples: "Email Sarah", "Review the PR", "Buy milk tomorrow"

2. **thought** - Something to REMEMBER. Ideas, notes, observations, references, URLs.
   - Signals: "what if", "I think", observations, URLs, book titles, interesting facts
   - Examples: "What if we used WebSockets?", "Interesting article on distributed systems"

3. **person** - Information ABOUT someone. Contact info, relationship notes.
   - Signals: Names with context, emails, phone numbers, "works at", "met at"
   - Examples: "Met Jake at the conference - he works on distributed systems at Stripe"

4. **event** - Something at a specific TIME. Meetings, appointments, deadlines.
   - Signals: dates, times, "on Monday", "next week", calendar-like items
   - Examples: "Team standup Monday 10am", "Conference in Seattle March 15-17"

## Input
```
{input}
```

## Rules
- Pick ONE type. When ambiguous, prefer: task > event > thought > person
- Extract @mentions as people references (slugify: "Sarah Chen" → "sarah-chen")
- Extract #hashtags as tags
- Parse natural dates relative to today ({today})
- Infer priority (low/medium/high) from urgency words - only for tasks
- Identify project context from keywords if obvious

## Output
Return ONLY valid JSON matching this schema:
```json
{schema}
```

## Examples

Input: "Remember to email Sarah about the copy deadline tomorrow"
```json
{"type": "task", "title": "Email Sarah about copy deadline", "confidence": 0.95, "people": ["sarah"], "due_date": "{tomorrow}", "priority": "medium", "tags": []}
```

Input: "What if we used WebSockets instead of polling for real-time updates?"
```json
{"type": "thought", "title": "Use WebSockets instead of polling", "body": "What if we used WebSockets instead of polling for real-time updates?", "confidence": 0.95, "tags": ["architecture", "real-time"]}
```

Input: "Met Jake Chen at KubeCon - works on service mesh at Stripe"
```json
{"type": "person", "title": "Jake Chen", "body": "Met at KubeCon. Works on service mesh at Stripe.", "confidence": 0.92, "tags": ["stripe", "kubecon"]}
```

Input: "Team standup every Monday at 10am starting next week"
```json
{"type": "event", "title": "Team standup", "confidence": 0.90, "due_date": "{next_monday}", "tags": ["recurring", "standup"]}
```

Now classify the input. Return ONLY the JSON object, no explanation.
```

### Classifier Implementation

```python
# src/noodle/classifier.py
import json
from pathlib import Path
from typing import Optional
import httpx

class Classifier:
    def __init__(self, config: dict):
        self.config = config
        self.prompt_template = self._load_prompt()
        self.schema = self._load_schema()

    def _load_prompt(self) -> str:
        prompt_path = Path(self.config['prompts_dir']) / 'classifier.md'
        return prompt_path.read_text()

    def _load_schema(self) -> dict:
        schema_path = Path(self.config['schemas_dir']) / 'entry.schema.json'
        return json.loads(schema_path.read_text())

    def classify(self, raw_input: str) -> dict:
        """Classify raw input text, return structured data."""
        prompt = self.prompt_template.format(
            input=raw_input,
            schema=json.dumps(self.schema, indent=2),
            tomorrow=self._get_tomorrow_date()
        )

        response = self._call_llm(prompt)
        parsed = self._parse_response(response)

        return parsed

    def _call_llm(self, prompt: str) -> str:
        """Call LLM API (Ollama or OpenAI)."""
        if self.config['llm']['provider'] == 'ollama':
            return self._call_ollama(prompt)
        else:
            return self._call_openai(prompt)

    def _call_ollama(self, prompt: str) -> str:
        response = httpx.post(
            f"{self.config['llm']['ollama_url']}/api/generate",
            json={
                "model": self.config['llm']['model'],
                "prompt": prompt,
                "stream": False,
                "format": "json"
            },
            timeout=30.0
        )
        return response.json()['response']

    def _call_openai(self, prompt: str) -> str:
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.config['llm']['openai_api_key']}"},
            json={
                "model": self.config['llm']['model'],
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"}
            },
            timeout=30.0
        )
        return response.json()['choices'][0]['message']['content']

    def _parse_response(self, response: str) -> dict:
        """Parse and validate LLM response."""
        try:
            data = json.loads(response)
            # Validate against schema here
            return data
        except json.JSONDecodeError:
            return {
                "type": "note",
                "title": "Failed to parse",
                "confidence": 0.0,
                "body": response
            }
```

---

## Systemd Integration

### Path Unit (Trigger on inbox.log change)

```ini
# systemd/noodle-classifier.path
[Unit]
Description=Watch noodle inbox for new entries

[Path]
PathModified=%h/noodle/inbox.log
Unit=noodle-classifier.service

[Install]
WantedBy=default.target
```

### Classifier Service

```ini
# systemd/noodle-classifier.service
[Unit]
Description=Process noodle inbox entries

[Service]
Type=oneshot
ExecStart=%h/.local/bin/noodle process-inbox
Environment=NOODLE_HOME=%h/noodle

[Install]
WantedBy=default.target
```

### Daily Digest Timer

```ini
# systemd/noodle-digest.timer
[Unit]
Description=Daily noodle digest

[Timer]
OnCalendar=*-*-* 08:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# systemd/noodle-digest.service
[Unit]
Description=Generate noodle daily digest

[Service]
Type=oneshot
ExecStart=%h/.local/bin/noodle digest --notify
Environment=NOODLE_HOME=%h/noodle
```

### Git Sync Timer

```ini
# systemd/noodle-sync.timer
[Unit]
Description=Sync noodle to git remote

[Timer]
OnCalendar=*:0/30
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# systemd/noodle-sync.service
[Unit]
Description=Git sync noodle repository

[Service]
Type=oneshot
ExecStart=%h/.local/bin/noodle sync
Environment=NOODLE_HOME=%h/noodle
```

### Installation

```bash
# Install systemd units
mkdir -p ~/.config/systemd/user
cp systemd/*.service systemd/*.timer systemd/*.path ~/.config/systemd/user/

# Enable and start
systemctl --user enable --now noodle-classifier.path
systemctl --user enable --now noodle-digest.timer
systemctl --user enable --now noodle-sync.timer

# Check status
systemctl --user status noodle-classifier.path
systemctl --user list-timers
```

---

## Claude Code Integration

### MCP Server

The MCP server exposes noodle as tools that Claude Code can use.

```python
# mcp/noodle_mcp/server.py
from mcp import Server, Tool
from noodle.db import Database
from noodle.classifier import Classifier

server = Server("noodle")
db = Database()

@server.tool()
def noodle_add(thought: str) -> dict:
    """
    Add a new entry to noodle. No type hint - classification is automatic.

    This is the O(1) ingress. No decisions required.

    Args:
        thought: The thought to capture

    Returns:
        The created entry with its ID
    """
    entry_id = quick_capture(thought)
    return {"id": entry_id, "status": "captured"}

TYPES = ['task', 'thought', 'person', 'event']  # FROZEN

@server.tool()
def noodle_search(query: str, entry_type: str = None, limit: int = 10) -> list[dict]:
    """
    Search noodle for entries matching the query.

    Args:
        query: Search query (supports full-text search)
        entry_type: Filter by type (task, thought, person, event)
        limit: Maximum results to return

    Returns:
        List of matching entries
    """
    if entry_type and entry_type not in TYPES:
        raise ValueError(f"Invalid type. Must be one of: {TYPES}")
    return db.search(query, type=entry_type, limit=limit)

@server.tool()
def noodle_context(topic: str) -> str:
    """
    Get relevant context about a topic from noodle.

    Args:
        topic: The topic to get context for

    Returns:
        Formatted summary of relevant entries
    """
    entries = db.search(topic, limit=20)
    return format_context_summary(entries)

@server.tool()
def noodle_tasks(project: str = None, include_completed: bool = False) -> list[dict]:
    """
    List tasks, optionally filtered by project.

    Args:
        project: Filter by project slug
        include_completed: Include completed tasks

    Returns:
        List of tasks
    """
    return db.get_tasks(project=project, include_completed=include_completed)

@server.tool()
def noodle_complete(entry_id: str) -> dict:
    """
    Mark a task as complete.

    Args:
        entry_id: The ID of the task to complete

    Returns:
        Updated entry
    """
    return db.complete_task(entry_id)

@server.tool()
def noodle_retype(entry_id: str, new_type: str) -> dict:
    """
    Change an entry's type (post-classification correction).

    Args:
        entry_id: The ID of the entry to retype
        new_type: The new type (task, thought, person, event)

    Returns:
        Updated entry
    """
    if new_type not in TYPES:
        raise ValueError(f"Invalid type. Must be one of: {TYPES}")
    return db.update_entry_type(entry_id, new_type)

@server.tool()
def noodle_pending() -> list[dict]:
    """
    Get entries that need reclassification (LLM fallback entries).

    Returns:
        List of entries with needs_reclassification flag
    """
    return db.get_pending_reclassification()

@server.tool()
def noodle_projects() -> list[dict]:
    """
    List all projects.

    Returns:
        List of projects with stats
    """
    return db.get_projects_with_stats()

@server.tool()
def noodle_daily_summary() -> str:
    """
    Get today's summary: active tasks, due items, recent entries.

    Returns:
        Formatted daily summary
    """
    return generate_daily_summary()

if __name__ == "__main__":
    server.run()
```

### MCP Configuration

```json
// ~/.config/claude-code/settings.json
{
  "mcpServers": {
    "noodle": {
      "command": "python",
      "args": ["-m", "noodle_mcp.server"],
      "env": {
        "NOODLE_HOME": "~/noodle"
      }
    }
  }
}
```

### Slash Commands

```markdown
<!-- .claude/commands/noodle.md -->
---
description: Quick capture a thought to noodle (O(1) ingress)
arguments:
  - name: thought
    description: The thought to capture
    required: true
---

Use the noodle_add MCP tool to capture this thought: "$ARGUMENTS"

Classification happens automatically. Just confirm the entry ID was returned.
Do NOT ask about type, project, or priority - that violates O(1) ingress.
```

```markdown
<!-- .claude/commands/noodle-find.md -->
---
description: Search noodle for entries
arguments:
  - name: query
    description: Search query
    required: true
---

Use the noodle_search MCP tool to find entries matching: "$ARGUMENTS"

Present the results in a clear format, grouping by type if there are multiple types.
```

```markdown
<!-- .claude/commands/noodle-context.md -->
---
description: Get context about a topic from noodle
arguments:
  - name: topic
    description: Topic to get context for
    required: true
---

Use the noodle_context MCP tool to retrieve relevant information about: "$ARGUMENTS"

Synthesize the results into a coherent summary that would help with the current task.
```

```markdown
<!-- .claude/commands/noodle-review.md -->
---
description: Review pending manual review items
---

1. Use noodle_pending MCP tool to get entries needing reclassification
2. Also read ~/noodle/manual_review.md for low-confidence items
3. For each item, suggest one of the 4 types: task, thought, person, event
4. Use noodle_retype to correct the type once user confirms
```

```markdown
<!-- .claude/commands/noodle-retype.md -->
---
description: Change an entry's type after classification
arguments:
  - name: id_and_type
    description: "Entry ID and new type, e.g., '1234567890 task'"
    required: true
---

Parse the arguments to get entry_id and new_type.
Valid types: task, thought, person, event (ONLY these four).
Use the noodle_retype MCP tool to change the entry's type.
```

```markdown
<!-- .claude/commands/noodle-health.md -->
---
description: Check noodle system health
---

Run these checks and report status:

1. Check if ~/noodle/noodle.db exists and is readable
2. Run `sqlite3 ~/noodle/noodle.db "SELECT COUNT(*) FROM entries"` to verify DB
3. Check systemd unit status: `systemctl --user status noodle-classifier.path`
4. Check for items in manual_review.md
5. Check git status of ~/noodle for uncommitted changes
6. Report any stale tasks (due date passed, not completed)

Format as a health report with pass/fail indicators.
```

---

## Mobile Ingress

### Pattern 1: Telegram Bot (Recommended)

```python
# src/noodle/telegram_bot.py
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

async def handle_message(update: Update, context):
    """Handle incoming message and pipe to noodle."""
    text = update.message.text
    user_id = update.effective_user.id

    # Verify authorized user
    if user_id != config['telegram']['authorized_user_id']:
        return

    # Append to inbox
    entry_id = append_to_inbox(text)

    await update.message.reply_text(f"Captured: {entry_id[:8]}...")

def main():
    app = Application.builder().token(config['telegram']['bot_token']).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
```

### Pattern 2: Syncthing (Local-First)

```toml
# config/noodle.toml
[mobile]
provider = "syncthing"
inbox_file = "mobile_inbox.md"
sync_folder_id = "noodle-mobile"
```

The classifier watches for changes to `mobile_inbox.md` and processes new lines.

### Pattern 3: Tailscale API (Direct)

```python
# src/noodle/api.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class Thought(BaseModel):
    text: str
    source: str = "api"

@app.post("/capture")
async def capture(thought: Thought):
    entry_id = append_to_inbox(thought.text, source=thought.source)
    return {"id": entry_id, "status": "captured"}

# Run with: uvicorn noodle.api:app --host 100.x.x.x --port 8080
# (Tailscale IP only)
```

---

## Extension Roadmap

### Phase 1: Core (MVP)
- [x] Specification document
- [ ] CLI scaffolding with Click
- [ ] SQLite schema and migrations
- [ ] Basic ingress (append to inbox)
- [ ] LLM classifier with Ollama
- [ ] systemd path unit for auto-classification
- [ ] Basic queries (list, find, show)

### Phase 2: Integration
- [ ] MCP server for Claude Code
- [ ] Slash commands
- [ ] Manual review TUI
- [ ] Daily digest notifications
- [ ] Git sync automation

### Phase 3: Mobile
- [ ] Telegram bot ingress
- [ ] Syncthing integration
- [ ] Optional Tailscale API

### Phase 4: Intelligence
- [ ] Semantic search with embeddings (sqlite-vec)
- [ ] Auto-linking related entries
- [ ] Stale item detection
- [ ] Weekly review generation

### Phase 5: Extensions
- [ ] Voice ingress (Whisper)
- [ ] Screenshot OCR capture
- [ ] Browser extension
- [ ] Graph visualization
- [ ] Spaced repetition surfacing

---

## Configuration

### Main Config File

```toml
# config/noodle.toml

[noodle]
home = "~/noodle"
editor = "$EDITOR"

[database]
path = "noodle.db"

[classifier]
confidence_threshold = 0.75
retry_on_low_confidence = false

[llm]
provider = "ollama"  # or "openai"
model = "llama3.2"
ollama_url = "http://localhost:11434"
# openai_api_key = "sk-..."  # If using OpenAI

[notifications]
enabled = true
provider = "libnotify"  # notify-send

[sync]
enabled = true
remote = "origin"
branch = "main"
auto_commit = true

[telegram]
enabled = false
# bot_token = "..."
# authorized_user_id = 123456789

[api]
enabled = false
host = "127.0.0.1"
port = 8080
```

---

## Dependencies

```toml
# pyproject.toml
[project]
name = "noodle"
version = "0.1.0"
description = "Local-first second brain for Arch Linux"
requires-python = ">=3.11"
dependencies = [
    "click>=8.1",
    "httpx>=0.27",
    "rich>=13.0",
    "textual>=0.50",  # For TUI
    "python-frontmatter>=1.0",
    "tomli>=2.0",
    "pydantic>=2.0",
]

[project.optional-dependencies]
telegram = ["python-telegram-bot>=21.0"]
api = ["fastapi>=0.110", "uvicorn>=0.27"]
mcp = ["mcp>=0.1"]

[project.scripts]
noodle = "noodle.cli:cli"
```

---

## Next Steps

1. **Initialize repository structure**
2. **Implement CLI skeleton**
3. **Create SQLite schema**
4. **Build basic ingress pipeline**
5. **Integrate LLM classifier**
6. **Set up systemd units**
7. **Build MCP server**
8. **Test end-to-end flow**

---

## Design Decisions Log

| Decision | Rationale | Date |
|----------|-----------|------|
| 4 types only (task, thought, person, event) | Mental portability - user can hold entire taxonomy in working memory | 2025-01-10 |
| No ingress options | O(1) capture - zero decisions at the moment of thought | 2025-01-10 |
| Confidence threshold 0.75 | Balance between automation and quality - too low pollutes DB, too high floods manual review | 2025-01-10 |
| Push-first architecture | Humans don't search; they respond to what's surfaced | 2025-01-10 |
| Rolling time windows | No backlog monster - restart-friendly design | 2025-01-10 |
| Graceful LLM degradation | Trust guarantee - capture MUST succeed even if classification fails | 2025-01-10 |

---

*Document version: 0.2.0*
*Last updated: 2025-01-10*
*Philosophy alignment: Verified against Nate B. Jones cognitive model*

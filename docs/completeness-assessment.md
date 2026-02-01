# Noodle Completeness Assessment

Assessment of noodle against the eight building blocks of a reliable second brain system.

## Building Blocks Status

| Building Block | Status | Implementation |
|----------------|--------|----------------|
| **1. Dropbox** | ✅ Complete | `noodle "text"` with <50ms capture, atomic writes, source tracking |
| **2. Sorter** | ✅ Complete | Dual LLM support (Anthropic/OpenAI), Pydantic-validated classification |
| **3. Form** | ✅ Complete | SQLite schema with 4 frozen types, FTS5 search, tags extension |
| **4. Filing Cabinet** | ✅ Complete | SQLite DB + type-specific markdown files for thoughts/people |
| **5. Receipt** | ✅ Complete | Three-tier audit: `inbox.log`, `processed.log`, `classifier_logs` table |
| **6. Bouncer** | ✅ Complete | Configurable confidence threshold (0.75), low-confidence → manual review |
| **7. Tap on Shoulder** | ✅ Complete | Daily digest, weekly review, systemd timers, desktop notifications |
| **8. Fix Button** | ✅ Complete | `noodle review` TUI, `noodle retype`, MCP tools for AI correction |

## Building Block Details

### 1. The Dropbox (Capture/Ingress)

**Location**: `src/noodle/ingress.py`, `src/noodle/cli.py`

- Sub-100ms capture guarantee using atomic file operations with fcntl locking
- Zero-decision ingress: `noodle "your thought"` or pipe input
- Sources tracked: CLI, Telegram, API
- Durability via `os.fsync()`
- Inbox format: Tab-separated with ID, timestamp, source, escaped text

### 2. The Sorter (AI Classification/Routing)

**Location**: `src/noodle/classifier.py`, `src/noodle/router.py`

- Dual LLM support: Anthropic (claude-haiku) and OpenAI (gpt-4o-mini)
- Pydantic-validated `ClassifiedEntry` with type, title, body, confidence, tags, project, people, due_date, priority
- Confidence threshold routing (default 0.75)
- Fallback mechanism: LLM failure → thought (confidence 0.0) → manual review
- Desktop notifications for low-confidence items

### 3. The Form (Schema/Data Contract)

**Location**: `src/noodle/db.py`, `src/noodle/classifier.py`

- Entries table with 13 columns including FTS5 full-text search
- Type constraint: `CHECK(type IN ('task', 'thought', 'person', 'event'))` - frozen forever
- Projects table with status tracking (active/paused/completed/archived)
- People table for contact stubs
- Tags via many-to-many junction table
- Classifier logs table for full audit trail

### 4. The Filing Cabinet (Storage/Database)

**Location**: `src/noodle/db.py`

- SQLite backend with normalized schema
- Context manager pattern with proper transaction handling
- Type-specific storage:
  - Thoughts: `thoughts/{id}-{slug}.md` with YAML frontmatter
  - People: `people/{slug}.md` with versioning
  - Tasks/Events: DB with due dates and completion tracking
- Full-text search via FTS5 with rank-based ordering

### 5. The Receipt (Audit Trail/Inbox Log)

**Location**: `src/noodle/router.py`

- `inbox.log`: Append-only raw captures (TSV)
- `processed.log`: Classified entries audit trail
- `manual_review.md`: Low-confidence/failed entries with context
- `classifier_logs` table: Full DB audit with LLM output, model, confidence, processing time, status, routed path

### 6. The Bouncer (Confidence Filter/Guardrails)

**Location**: `src/noodle/router.py`, `src/noodle/classifier.py`

- Configurable confidence threshold (default 0.75)
- Low-confidence entries → `manual_review.md`
- Parse errors → manual review
- LLM failures → manual review
- `needs_reclassification` flag in DB
- `noodle health` reports pending review count

### 7. The Tap on the Shoulder (Proactive Surfacing)

**Location**: `src/noodle/surfacing.py`

- **Daily digest**: Due today, open tasks, stale thoughts, upcoming events, review queue
- **Weekly review**: 7-day rolling window, completion stats, top projects, ideas
- **systemd automation**: 7 unit files for inbox watching, daily digest (8am), weekly review (Sunday 10am)
- Desktop notifications via `notify-send`

### 8. The Fix Button (Human Correction)

**Location**: `src/noodle/cli.py`

- `noodle review`: Interactive TUI with single-keypress corrections
- `noodle retype <id> <type>`: Direct type correction
- `noodle done <id>`: Task completion
- MCP tools: `noodle_retype` for AI-assisted correction
- All changes logged with updated timestamps

## Beyond the 8 Blocks

### MCP Server Integration

**Location**: `src/noodle_mcp/server.py`

9 MCP tools for Claude Code integration:
- `noodle_add`, `noodle_search`, `noodle_tasks`, `noodle_complete`
- `noodle_digest`, `noodle_weekly`, `noodle_pending`
- `noodle_retype`, `noodle_context`

### Telegram Bot

**Location**: `src/noodle/telegram_bot.py`

- Mobile capture with user authorization
- Source tracking as "telegram"

### Maintenance Commands

- `noodle health`: Multi-check system status
- `noodle gc`: Garbage collection
- `noodle stats`: Database statistics

## Architecture Alignment

The design follows key principles from second brain literature:

- **Push over pull**: Digests are primary, search is secondary
- **No guilt**: Rolling 7-day windows, no cumulative backlog
- **Trust guarantee**: Graceful degradation if LLM fails → manual review queue
- **O(1) ingress**: Zero decisions at capture time

## Implementation Phases

All phases complete:

- ✅ **Phase 0**: Foundation (capture to inbox.log)
- ✅ **Phase 1**: Classification (LLM routing)
- ✅ **Phase 2**: Surfacing (digests, systemd)
- ✅ **Phase 3**: Integration (MCP server)
- ✅ **Phase 4**: Mobile (Telegram bot)
- ✅ **Phase 5**: Polish (health, gc, TUI review)

## Verdict

**8/8 building blocks fully implemented**. The system is feature-complete and ready for production use.

"""
Telegram bot for Noodle.

Mobile ingress and remote access via Telegram.
"""

import logging
import os
from typing import Any

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from noodle.config import ensure_dirs, get_inbox_path, load_config
from noodle.ingress import append_to_inbox
from noodle.db import Database
from noodle.surfacing import format_id

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def get_bot_config() -> dict[str, Any]:
    """Get bot configuration."""
    config = load_config()
    bot_config = config.get("telegram", {})

    # Token from config or environment
    token = bot_config.get("token") or os.environ.get("NOODLE_TELEGRAM_TOKEN")
    if not token:
        raise ValueError(
            "Telegram bot token not found. "
            "Set NOODLE_TELEGRAM_TOKEN env var or add to config.toml"
        )

    # Authorized user IDs (comma-separated in env, list in config)
    authorized = bot_config.get("authorized_users", [])
    if not authorized:
        env_users = os.environ.get("NOODLE_TELEGRAM_USERS", "")
        if env_users:
            authorized = [int(uid.strip()) for uid in env_users.split(",") if uid.strip()]

    return {
        "token": token,
        "authorized_users": set(authorized),
    }


def is_authorized(user_id: int, authorized_users: set[int]) -> bool:
    """Check if user is authorized."""
    # If no users configured, deny all (secure default)
    if not authorized_users:
        return False
    return user_id in authorized_users


def format_entries_telegram(entries: list[dict], title: str, limit: int = 10) -> str:
    """Format entries for Telegram (plain text, compact)."""
    if not entries:
        return f"{title}\n\nNo entries found."

    lines = [f"{title}", ""]

    for entry in entries[:limit]:
        seq = entry.get("seq", "?")
        etype = entry["type"]
        entry_title = entry["title"][:40]

        extra = ""
        if etype == "task" and entry.get("due_date"):
            extra = f" [due:{entry['due_date']}]"

        lines.append(f"#{seq} [{etype}] {entry_title}{extra}")

    if len(entries) > limit:
        lines.append(f"\n... and {len(entries) - limit} more")

    return "\n".join(lines)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    authorized_users = context.bot_data.get("authorized_users", set())

    if is_authorized(user_id, authorized_users):
        await update.message.reply_text(
            "Noodle bot ready. Send any message to capture it.\n\n"
            "Commands:\n"
            "/tasks - List open tasks\n"
            "/thoughts - List recent thoughts\n"
            "/list [type] - List entries\n"
            "/done <id> - Complete a task\n"
            "/archive <id> - Archive an entry\n"
            "/find <query> - Search entries\n"
            "/digest - Daily digest\n"
            "/analyze - Daily digest with LLM analysis\n"
            "/weekly - Weekly review\n"
            "/id - Show your user ID"
        )
    else:
        await update.message.reply_text(
            f"Unauthorized. Your user ID: {user_id}\n"
            "Add this ID to NOODLE_TELEGRAM_USERS to authorize."
        )


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /id command - show user's Telegram ID."""
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    await update.message.reply_text(f"Your Telegram user ID: {user_id}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if not update.effective_user:
        return

    await update.message.reply_text(
        "Noodle Commands:\n\n"
        "/tasks - List open tasks\n"
        "/thoughts - List recent thoughts\n"
        "/list [type] - List entries\n"
        "/done <id> - Complete a task\n"
        "/archive <id> - Archive an entry\n"
        "/find <query> - Search entries\n"
        "/digest - Daily digest\n"
        "/analyze - Daily digest with LLM analysis\n"
        "/weekly - Weekly review\n"
        "/id - Show your user ID\n"
        "/help - Show this message\n\n"
        "Send any text to capture it."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages - capture to noodle."""
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id
    authorized_users = context.bot_data.get("authorized_users", set())

    # Security: only process messages from authorized users
    if not is_authorized(user_id, authorized_users):
        logger.warning(f"Unauthorized message attempt from user {user_id}")
        await update.message.reply_text(f"Unauthorized. Your ID: {user_id}")
        return

    # Get message text
    text = update.message.text
    if not text:
        await update.message.reply_text("Only text messages are supported.")
        return

    # Capture to inbox
    try:
        ensure_dirs()
        inbox_path = get_inbox_path()
        entry_id = append_to_inbox(text, inbox_path, source="telegram")

        await update.message.reply_text(f"Captured: {entry_id}")
        logger.info(f"Captured from Telegram user {user_id}: {entry_id}")

    except Exception as e:
        logger.error(f"Failed to capture: {e}")
        await update.message.reply_text(f"Error capturing thought: {e}")


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /tasks command - list open tasks."""
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    authorized_users = context.bot_data.get("authorized_users", set())

    if not is_authorized(user_id, authorized_users):
        await update.message.reply_text(f"Unauthorized. Your ID: {user_id}")
        return

    try:
        db = Database()
        entries = db.get_entries(entry_type="task", limit=15)
        response = format_entries_telegram(entries, "TASKS")
        await update.message.reply_text(response)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def thoughts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /thoughts command - list recent thoughts."""
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    authorized_users = context.bot_data.get("authorized_users", set())

    if not is_authorized(user_id, authorized_users):
        await update.message.reply_text(f"Unauthorized. Your ID: {user_id}")
        return

    try:
        db = Database()
        entries = db.get_entries(entry_type="thought", limit=15)
        response = format_entries_telegram(entries, "THOUGHTS")
        await update.message.reply_text(response)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /list command - list entries with optional type filter."""
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    authorized_users = context.bot_data.get("authorized_users", set())

    if not is_authorized(user_id, authorized_users):
        await update.message.reply_text(f"Unauthorized. Your ID: {user_id}")
        return

    # Parse type argument
    entry_type = None
    if context.args:
        entry_type = context.args[0].lower()
        if entry_type not in ("task", "thought", "person", "event"):
            await update.message.reply_text(
                f"Invalid type: {entry_type}\n"
                "Valid types: task, thought, person, event"
            )
            return

    try:
        db = Database()
        entries = db.get_entries(entry_type=entry_type, limit=15)
        title = f"{entry_type.upper()}S" if entry_type else "ENTRIES"
        response = format_entries_telegram(entries, title)
        await update.message.reply_text(response)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /done command - complete a task."""
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    authorized_users = context.bot_data.get("authorized_users", set())

    if not is_authorized(user_id, authorized_users):
        await update.message.reply_text(f"Unauthorized. Your ID: {user_id}")
        return

    if not context.args:
        await update.message.reply_text("Usage: /done <id>")
        return

    identifier = context.args[0]

    try:
        db = Database()
        entry_id = db.resolve_entry_id(identifier)
        if not entry_id:
            await update.message.reply_text(f"Entry not found: {identifier}")
            return

        success = db.complete_task(entry_id)
        if success:
            await update.message.reply_text(f"Completed: #{identifier}")
        else:
            await update.message.reply_text(f"Not a task or already completed: {identifier}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def archive_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /archive command - archive an entry."""
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    authorized_users = context.bot_data.get("authorized_users", set())

    if not is_authorized(user_id, authorized_users):
        await update.message.reply_text(f"Unauthorized. Your ID: {user_id}")
        return

    if not context.args:
        await update.message.reply_text("Usage: /archive <id>")
        return

    identifier = context.args[0]

    try:
        db = Database()
        entry_id = db.resolve_entry_id(identifier)
        if not entry_id:
            await update.message.reply_text(f"Entry not found: {identifier}")
            return

        success = db.archive_entry(entry_id)
        if success:
            await update.message.reply_text(f"Archived: #{identifier}")
        else:
            await update.message.reply_text(f"Already archived: {identifier}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /find command - search entries."""
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    authorized_users = context.bot_data.get("authorized_users", set())

    if not is_authorized(user_id, authorized_users):
        await update.message.reply_text(f"Unauthorized. Your ID: {user_id}")
        return

    if not context.args:
        await update.message.reply_text("Usage: /find <query>")
        return

    query = " ".join(context.args)

    try:
        db = Database()
        entries = db.search(query, limit=10)
        response = format_entries_telegram(entries, f"SEARCH: {query}")
        await update.message.reply_text(response)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /digest command - show daily digest."""
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    authorized_users = context.bot_data.get("authorized_users", set())

    if not is_authorized(user_id, authorized_users):
        await update.message.reply_text(f"Unauthorized. Your ID: {user_id}")
        return

    try:
        from noodle.surfacing import generate_daily_digest
        digest = generate_daily_digest()
        await update.message.reply_text(digest)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /analyze command - show daily digest with LLM analysis."""
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    authorized_users = context.bot_data.get("authorized_users", set())

    if not is_authorized(user_id, authorized_users):
        await update.message.reply_text(f"Unauthorized. Your ID: {user_id}")
        return

    try:
        from noodle.surfacing import generate_daily_digest_enhanced
        # Notify user this may take a moment
        await update.message.reply_text("Analyzing...")
        digest = generate_daily_digest_enhanced()
        await update.message.reply_text(digest)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def weekly_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /weekly command - show weekly review."""
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    authorized_users = context.bot_data.get("authorized_users", set())

    if not is_authorized(user_id, authorized_users):
        await update.message.reply_text(f"Unauthorized. Your ID: {user_id}")
        return

    try:
        from noodle.surfacing import generate_weekly_review
        review = generate_weekly_review()
        await update.message.reply_text(review)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


def run_bot() -> None:
    """Run the Telegram bot."""
    config = get_bot_config()

    # Create application
    app = Application.builder().token(config["token"]).build()

    # Store authorized users in bot_data
    app.bot_data["authorized_users"] = config["authorized_users"]

    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("tasks", tasks_command))
    app.add_handler(CommandHandler("thoughts", thoughts_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("done", done_command))
    app.add_handler(CommandHandler("archive", archive_command))
    app.add_handler(CommandHandler("find", find_command))
    app.add_handler(CommandHandler("digest", digest_command))
    app.add_handler(CommandHandler("analyze", analyze_command))
    app.add_handler(CommandHandler("weekly", weekly_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Log startup info
    if config["authorized_users"]:
        logger.info(f"Bot starting. Authorized users: {config['authorized_users']}")
    else:
        logger.warning("No authorized users configured! Bot will deny all messages.")

    # Run bot
    app.run_polling(allowed_updates=Update.ALL_TYPES)


def main() -> int:
    """Entry point for CLI."""
    try:
        run_bot()
        return 0
    except ValueError as e:
        print(f"Error: {e}")
        return 1
    except KeyboardInterrupt:
        print("\nBot stopped.")
        return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

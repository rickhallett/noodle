"""
Telegram bot for Noodle.

Mobile ingress: capture thoughts from anywhere via Telegram.
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


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    authorized_users = context.bot_data.get("authorized_users", set())

    if is_authorized(user_id, authorized_users):
        await update.message.reply_text(
            "Noodle bot ready. Send me any message to capture it.\n\n"
            "Commands:\n"
            "/start - Show this message\n"
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


def run_bot() -> None:
    """Run the Telegram bot."""
    config = get_bot_config()

    # Create application
    app = Application.builder().token(config["token"]).build()

    # Store authorized users in bot_data
    app.bot_data["authorized_users"] = config["authorized_users"]

    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("id", id_command))
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

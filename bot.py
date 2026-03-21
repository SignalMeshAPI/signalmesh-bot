"""
SignalMesh Telegram Bot — @SignalMeshBot
The demo + acquisition funnel for SignalMesh API.

Running modes:
  Local:          add BOT_TOKEN to .env, then: python bot.py
  GitHub Actions: add BOT_TOKEN as a repo secret — works automatically
"""

import logging
import os
import sys

# Load .env file when running locally (silently ignored in GitHub Actions)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from app.handlers.signal import handle_signal
from app.handlers.safety import handle_safety
from app.handlers.whales import handle_whales
from app.handlers.launch import handle_launch
from app.handlers.price import handle_price
from app.handlers.start import handle_start, handle_subscribe, handle_chains

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def get_token() -> str:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        logger.error("BOT_TOKEN not set!")
        logger.error("Local: add BOT_TOKEN=your_token to .env file")
        logger.error("GitHub Actions: add BOT_TOKEN in repo Settings > Secrets")
        sys.exit(1)
    return token


async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ Unknown command.\n\n"
        "Try: /signal BONK · /safety [address] · /whales solana · /launch\n"
        "Or /start to see everything."
    )


def main():
    token = get_token()
    is_ci = os.getenv("CI", "false").lower() == "true"
    logger.info(f"Starting @SignalMeshBot ({'GitHub Actions' if is_ci else 'local'})...")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start",     handle_start))
    app.add_handler(CommandHandler("signal",    handle_signal))
    app.add_handler(CommandHandler("safety",    handle_safety))
    app.add_handler(CommandHandler("whales",    handle_whales))
    app.add_handler(CommandHandler("launch",    handle_launch))
    app.add_handler(CommandHandler("price",     handle_price))
    app.add_handler(CommandHandler("subscribe", handle_subscribe))
    app.add_handler(CommandHandler("chains",    handle_chains))
    app.add_handler(MessageHandler(filters.COMMAND, handle_unknown))

    logger.info("@SignalMeshBot is live ✅")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()

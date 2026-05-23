import os
import logging
from functools import partial

from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters,
)
from pymongo import MongoClient

from keep_alive import keep_alive
import handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def validate_env():
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    MONGODB_URI = os.environ.get("MONGODB_URI")
    OWNER_ID_RAW = os.environ.get("OWNER_ID")

    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not MONGODB_URI:
        missing.append("MONGODB_URI")
    if not OWNER_ID_RAW:
        missing.append("OWNER_ID")

    if missing:
        logger.critical(
            "Startup aborted. Missing required environment variables: %s",
            ", ".join(missing),
        )
        raise SystemExit(1)

    try:
        owner_id = int(OWNER_ID_RAW)
    except ValueError:
        logger.critical("OWNER_ID must be a valid integer. Got: %s", OWNER_ID_RAW)
        raise SystemExit(1)

    return BOT_TOKEN, MONGODB_URI, owner_id


def main():
    BOT_TOKEN, MONGODB_URI, OWNER_ID = validate_env()

    client = MongoClient(MONGODB_URI)
    db = client["group_bot"]

    keep_alive()

    updater = Updater(token=BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", handlers.start))

    dp.add_handler(CallbackQueryHandler(handlers.main_menu_callback, pattern="^main_menu$"))
    dp.add_handler(CallbackQueryHandler(handlers.menu_mod_callback, pattern="^menu_mod$"))
    dp.add_handler(CallbackQueryHandler(handlers.menu_settings_callback, pattern="^menu_settings$"))
    dp.add_handler(CallbackQueryHandler(handlers.menu_stats_callback, pattern="^menu_stats$"))
    dp.add_handler(CallbackQueryHandler(handlers.menu_owner_callback, pattern="^menu_owner$"))
    dp.add_handler(CallbackQueryHandler(handlers.back_start_callback, pattern="^back_start$"))

    dp.add_handler(CommandHandler("ban", handlers.ban_handler))
    dp.add_handler(CommandHandler("unban", handlers.unban_handler))
    dp.add_handler(CommandHandler("mute", handlers.mute_handler))
    dp.add_handler(CommandHandler("unmute", handlers.unmute_handler))
    dp.add_handler(CommandHandler("warn", partial(handlers.warn_handler, db=db)))

    dp.add_handler(CommandHandler("setwelcome", partial(handlers.setwelcome_handler, db=db)))
    dp.add_handler(CommandHandler("clearwelcome", partial(handlers.clearwelcome_handler, db=db)))
    dp.add_handler(CommandHandler("stats", partial(handlers.stats_handler, db=db)))

    dp.add_handler(
        MessageHandler(
            Filters.status_update.new_chat_members,
            partial(handlers.welcome_new_member, db=db),
        )
    )

    logger.info("Bot started. Polling...")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()

import os
import logging
import sys
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

# ─── Logging setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ─── Startup validation ───────────────────────────────────────────────────────

def validate_env():
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    MONGODB_URI = os.environ.get("MONGODB_URI")
    OWNER_ID_RAW = os.environ.get("OWNER_ID")

    missing = [k for k, v in [("BOT_TOKEN", BOT_TOKEN), ("MONGODB_URI", MONGODB_URI), ("OWNER_ID", OWNER_ID_RAW)] if not v]
    if missing:
        logger.critical("STARTUP FAILED — Missing env vars: %s", ", ".join(missing))
        logger.critical("Set these in Render > Environment before deploying.")
        sys.exit(1)

    try:
        owner_id = int(OWNER_ID_RAW)
    except ValueError:
        logger.critical("OWNER_ID must be an integer. Got: '%s'", OWNER_ID_RAW)
        sys.exit(1)

    logger.info("Environment OK — BOT_TOKEN: set | MONGODB_URI: set | OWNER_ID: %s", owner_id)
    return BOT_TOKEN, MONGODB_URI, owner_id


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    BOT_TOKEN, MONGODB_URI, OWNER_ID = validate_env()

    logger.info("Connecting to MongoDB...")
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        db = client["group_bot"]
        logger.info("MongoDB connected successfully.")
    except Exception as e:
        logger.critical("MongoDB connection failed: %s", e)
        sys.exit(1)

    keep_alive()
    logger.info("Flask keep-alive server started.")

    updater = Updater(token=BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # ── /start ────────────────────────────────────────────────────────────────
    dp.add_handler(CommandHandler("start", partial(handlers.start, db=db)))

    # ── Menu navigation ───────────────────────────────────────────────────────
    dp.add_handler(CallbackQueryHandler(handlers.main_menu_callback,    pattern="^main_menu$"))
    dp.add_handler(CallbackQueryHandler(handlers.menu_mod_callback,     pattern="^menu_mod$"))
    dp.add_handler(CallbackQueryHandler(handlers.menu_settings_callback,pattern="^menu_settings$"))
    dp.add_handler(CallbackQueryHandler(handlers.menu_stats_callback,   pattern="^menu_stats$"))
    dp.add_handler(CallbackQueryHandler(handlers.menu_owner_callback,   pattern="^menu_owner$"))
    dp.add_handler(CallbackQueryHandler(handlers.back_start_callback,   pattern="^back_start$"))

    # ── Broadcast ─────────────────────────────────────────────────────────────
    dp.add_handler(CommandHandler("broadcast", handlers.broadcast_handler))
    dp.add_handler(CallbackQueryHandler(handlers.broadcast_target_callback, pattern="^bc_"))
    dp.add_handler(MessageHandler(
        Filters.user(OWNER_ID) & Filters.chat_type.private &
        ~Filters.command & Filters.update.message,
        partial(handlers.broadcast_send, db=db),
    ))

    # ── Owner tools ───────────────────────────────────────────────────────────
    dp.add_handler(CommandHandler("userlist",  partial(handlers.userlist_handler,  db=db)))
    dp.add_handler(CommandHandler("grouplist", partial(handlers.grouplist_handler, db=db)))

    # ── Moderation ────────────────────────────────────────────────────────────
    dp.add_handler(CommandHandler("ban",          handlers.ban_handler))
    dp.add_handler(CommandHandler("unban",        handlers.unban_handler))
    dp.add_handler(CommandHandler("mute",         handlers.mute_handler))
    dp.add_handler(CommandHandler("unmute",       handlers.unmute_handler))
    dp.add_handler(CommandHandler("warn",         partial(handlers.warn_handler, db=db)))

    # ── Chat settings ─────────────────────────────────────────────────────────
    dp.add_handler(CommandHandler("setwelcome",   partial(handlers.setwelcome_handler,   db=db)))
    dp.add_handler(CommandHandler("clearwelcome", partial(handlers.clearwelcome_handler, db=db)))
    dp.add_handler(CommandHandler("stats",        partial(handlers.stats_handler,        db=db)))

    # ── Auto-events ───────────────────────────────────────────────────────────
    dp.add_handler(MessageHandler(
        Filters.status_update.new_chat_members,
        partial(handlers.bot_added_to_group, db=db),
    ))
    dp.add_handler(MessageHandler(
        Filters.status_update.new_chat_members,
        partial(handlers.welcome_new_member, db=db),
    ))

    # ── Passive tracker (stores users & groups silently) ─────────────────────
    dp.add_handler(MessageHandler(
        Filters.all & ~Filters.status_update,
        partial(handlers.message_tracker, db=db),
    ), group=1)

    logger.info("All handlers registered. Starting polling...")
    updater.start_polling()
    logger.info("Bot is live and polling.")
    updater.idle()


if __name__ == "__main__":
    main()

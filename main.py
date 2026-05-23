import os
import sys
import traceback
import logging

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
logger = logging.getLogger(__name__)

logger.info("=" * 60)
logger.info("BOT STARTING UP  (python-telegram-bot v20)")
logger.info("=" * 60)

# ─── Step 1: Env vars ─────────────────────────────────────────────────────────
logger.info("STEP 1 — Checking environment variables...")
BOT_TOKEN    = os.environ.get("BOT_TOKEN")
MONGODB_URI  = os.environ.get("MONGODB_URI")
OWNER_ID_RAW = os.environ.get("OWNER_ID")

missing = [k for k, v in [("BOT_TOKEN", BOT_TOKEN), ("MONGODB_URI", MONGODB_URI), ("OWNER_ID", OWNER_ID_RAW)] if not v]
if missing:
    logger.critical("MISSING ENV VARS: %s — Add in Render > Environment then redeploy.", ", ".join(missing))
    sys.exit(1)

try:
    OWNER_ID = int(OWNER_ID_RAW)
except ValueError:
    logger.critical("OWNER_ID must be a plain integer. Got: '%s'", OWNER_ID_RAW)
    sys.exit(1)

logger.info("STEP 1 OK — BOT_TOKEN: set | MONGODB_URI: set | OWNER_ID: %s", OWNER_ID)

# ─── Step 2: Import PTB v20 ───────────────────────────────────────────────────
logger.info("STEP 2 — Importing python-telegram-bot v20...")
try:
    from telegram.ext import (
        Application,
        CommandHandler,
        CallbackQueryHandler,
        MessageHandler,
        filters,
    )
    logger.info("STEP 2 OK — PTB v20 imported successfully.")
except Exception:
    logger.critical("STEP 2 FAILED — Could not import telegram library.")
    logger.critical(traceback.format_exc())
    sys.exit(1)

# ─── Step 3: Import pymongo ───────────────────────────────────────────────────
logger.info("STEP 3 — Importing pymongo...")
try:
    from pymongo import MongoClient
    logger.info("STEP 3 OK — pymongo imported.")
except Exception:
    logger.critical("STEP 3 FAILED — Could not import pymongo.")
    logger.critical(traceback.format_exc())
    sys.exit(1)

# ─── Step 4: Import local modules ────────────────────────────────────────────
logger.info("STEP 4 — Importing keep_alive and handlers...")
try:
    from keep_alive import keep_alive
    logger.info("STEP 4a OK — keep_alive imported.")
except Exception:
    logger.critical("STEP 4a FAILED — keep_alive import error.")
    logger.critical(traceback.format_exc())
    sys.exit(1)

try:
    import handlers
    logger.info("STEP 4b OK — handlers imported.")
except Exception:
    logger.critical("STEP 4b FAILED — handlers import error.")
    logger.critical(traceback.format_exc())
    sys.exit(1)

# ─── Step 5: MongoDB ──────────────────────────────────────────────────────────
logger.info("STEP 5 — Connecting to MongoDB...")
try:
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=8000)
    client.admin.command("ping")
    db = client["group_bot"]
    logger.info("STEP 5 OK — MongoDB connected.")
except Exception:
    logger.critical("STEP 5 FAILED — MongoDB connection error.")
    logger.critical(traceback.format_exc())
    sys.exit(1)

# ─── Step 6: Flask keep-alive ─────────────────────────────────────────────────
logger.info("STEP 6 — Starting Flask keep-alive...")
try:
    keep_alive()
    logger.info("STEP 6 OK — Flask keep-alive started.")
except Exception:
    logger.critical("STEP 6 FAILED — Flask server error.")
    logger.critical(traceback.format_exc())
    sys.exit(1)

# ─── Step 7: Build application & register handlers ───────────────────────────
logger.info("STEP 7 — Building Application and registering handlers...")
try:
    app = Application.builder().token(BOT_TOKEN).build()
    app.bot_data["db"] = db

    # /start
    app.add_handler(CommandHandler("start", handlers.start))

    # Menu navigation
    app.add_handler(CallbackQueryHandler(handlers.main_menu_callback,     pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(handlers.menu_mod_callback,      pattern="^menu_mod$"))
    app.add_handler(CallbackQueryHandler(handlers.menu_settings_callback, pattern="^menu_settings$"))
    app.add_handler(CallbackQueryHandler(handlers.menu_stats_callback,    pattern="^menu_stats$"))
    app.add_handler(CallbackQueryHandler(handlers.menu_owner_callback,    pattern="^menu_owner$"))
    app.add_handler(CallbackQueryHandler(handlers.back_start_callback,    pattern="^back_start$"))

    # Broadcast
    app.add_handler(CommandHandler("broadcast", handlers.broadcast_handler))
    app.add_handler(CallbackQueryHandler(handlers.broadcast_target_callback, pattern="^bc_"))
    app.add_handler(MessageHandler(
        filters.User(OWNER_ID) & filters.ChatType.PRIVATE & ~filters.COMMAND,
        handlers.broadcast_send,
    ))

    # Owner tools
    app.add_handler(CommandHandler("userlist",    handlers.userlist_handler))
    app.add_handler(CommandHandler("grouplist",   handlers.grouplist_handler))

    # Moderation
    app.add_handler(CommandHandler("ban",         handlers.ban_handler))
    app.add_handler(CommandHandler("unban",       handlers.unban_handler))
    app.add_handler(CommandHandler("mute",        handlers.mute_handler))
    app.add_handler(CommandHandler("unmute",      handlers.unmute_handler))
    app.add_handler(CommandHandler("warn",        handlers.warn_handler))

    # Chat settings
    app.add_handler(CommandHandler("setwelcome",  handlers.setwelcome_handler))
    app.add_handler(CommandHandler("clearwelcome",handlers.clearwelcome_handler))
    app.add_handler(CommandHandler("stats",       handlers.stats_handler))

    # Auto-events (group=0 and group=1 so both run)
    app.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS, handlers.bot_added_to_group
    ))
    app.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS, handlers.welcome_new_member
    ), group=1)

    # Passive tracker
    app.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.VIDEO | filters.AUDIO,
        handlers.message_tracker,
    ), group=2)

    # Error handler — logs full traceback for every handler exception
    async def error_handler(update, context):
        logger.error(
            "HANDLER EXCEPTION — update: %s\n%s",
            update,
            "".join(traceback.format_exception(type(context.error), context.error, context.error.__traceback__)),
        )

    app.add_error_handler(error_handler)

    logger.info("STEP 7 OK — All handlers registered.")
except Exception:
    logger.critical("STEP 7 FAILED — Handler registration error.")
    logger.critical(traceback.format_exc())
    sys.exit(1)

# ─── Step 8: Start polling ────────────────────────────────────────────────────
logger.info("STEP 8 — Starting polling...")
try:
    logger.info("STEP 8 OK — Bot is live and polling. Ready to receive messages.")
    logger.info("=" * 60)
    app.run_polling()
except Exception:
    logger.critical("STEP 8 FAILED — Polling error.")
    logger.critical(traceback.format_exc())
    sys.exit(1)

import os
import sys
import traceback
import logging

# Force stdout to flush immediately so Render captures every line
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# ─── Logging (must come before any other import that might fail) ───────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
logger = logging.getLogger(__name__)

logger.info("=" * 60)
logger.info("BOT STARTING UP")
logger.info("=" * 60)

# ─── Step 1: Check env vars BEFORE importing anything heavy ──────────────────
logger.info("STEP 1 — Checking environment variables...")
BOT_TOKEN   = os.environ.get("BOT_TOKEN")
MONGODB_URI = os.environ.get("MONGODB_URI")
OWNER_ID_RAW = os.environ.get("OWNER_ID")

missing = [k for k, v in [
    ("BOT_TOKEN",   BOT_TOKEN),
    ("MONGODB_URI", MONGODB_URI),
    ("OWNER_ID",    OWNER_ID_RAW),
] if not v]

if missing:
    logger.critical("MISSING ENV VARS: %s", ", ".join(missing))
    logger.critical("Go to Render > Environment and add these variables, then redeploy.")
    sys.exit(1)

try:
    OWNER_ID = int(OWNER_ID_RAW)
except ValueError:
    logger.critical("OWNER_ID must be a plain integer. Got: '%s'", OWNER_ID_RAW)
    sys.exit(1)

logger.info("STEP 1 OK — BOT_TOKEN: set | MONGODB_URI: set | OWNER_ID: %s", OWNER_ID)

# ─── Step 2: Import telegram library ─────────────────────────────────────────
logger.info("STEP 2 — Importing python-telegram-bot...")
try:
    from functools import partial
    from telegram.ext import (
        Updater,
        CommandHandler,
        CallbackQueryHandler,
        MessageHandler,
        Filters,
    )
    logger.info("STEP 2 OK — telegram library imported successfully.")
except Exception:
    logger.critical("STEP 2 FAILED — Could not import telegram library.")
    logger.critical(traceback.format_exc())
    sys.exit(1)

# ─── Step 3: Import pymongo ───────────────────────────────────────────────────
logger.info("STEP 3 — Importing pymongo...")
try:
    from pymongo import MongoClient
    logger.info("STEP 3 OK — pymongo imported successfully.")
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
    logger.critical("STEP 4a FAILED — Could not import keep_alive.")
    logger.critical(traceback.format_exc())
    sys.exit(1)

try:
    import handlers
    logger.info("STEP 4b OK — handlers imported.")
except Exception:
    logger.critical("STEP 4b FAILED — Could not import handlers.")
    logger.critical(traceback.format_exc())
    sys.exit(1)

# ─── Step 5: Connect to MongoDB ──────────────────────────────────────────────
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

# ─── Step 6: Start Flask keep-alive ──────────────────────────────────────────
logger.info("STEP 6 — Starting Flask keep-alive server...")
try:
    keep_alive()
    logger.info("STEP 6 OK — Flask keep-alive started.")
except Exception:
    logger.critical("STEP 6 FAILED — Flask server error.")
    logger.critical(traceback.format_exc())
    sys.exit(1)

# ─── Step 7: Register Telegram handlers ──────────────────────────────────────
logger.info("STEP 7 — Creating Updater and registering handlers...")
try:
    updater = Updater(token=BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", partial(handlers.start, db=db)))

    dp.add_handler(CallbackQueryHandler(handlers.main_menu_callback,     pattern="^main_menu$"))
    dp.add_handler(CallbackQueryHandler(handlers.menu_mod_callback,      pattern="^menu_mod$"))
    dp.add_handler(CallbackQueryHandler(handlers.menu_settings_callback, pattern="^menu_settings$"))
    dp.add_handler(CallbackQueryHandler(handlers.menu_stats_callback,    pattern="^menu_stats$"))
    dp.add_handler(CallbackQueryHandler(handlers.menu_owner_callback,    pattern="^menu_owner$"))
    dp.add_handler(CallbackQueryHandler(handlers.back_start_callback,    pattern="^back_start$"))

    dp.add_handler(CommandHandler("broadcast",   handlers.broadcast_handler))
    dp.add_handler(CallbackQueryHandler(handlers.broadcast_target_callback, pattern="^bc_"))
    dp.add_handler(MessageHandler(
        Filters.user(OWNER_ID) & Filters.chat_type.private & ~Filters.command,
        partial(handlers.broadcast_send, db=db),
    ))

    dp.add_handler(CommandHandler("userlist",    partial(handlers.userlist_handler,    db=db)))
    dp.add_handler(CommandHandler("grouplist",   partial(handlers.grouplist_handler,   db=db)))
    dp.add_handler(CommandHandler("ban",         handlers.ban_handler))
    dp.add_handler(CommandHandler("unban",       handlers.unban_handler))
    dp.add_handler(CommandHandler("mute",        handlers.mute_handler))
    dp.add_handler(CommandHandler("unmute",      handlers.unmute_handler))
    dp.add_handler(CommandHandler("warn",        partial(handlers.warn_handler,        db=db)))
    dp.add_handler(CommandHandler("setwelcome",  partial(handlers.setwelcome_handler,  db=db)))
    dp.add_handler(CommandHandler("clearwelcome",partial(handlers.clearwelcome_handler,db=db)))
    dp.add_handler(CommandHandler("stats",       partial(handlers.stats_handler,       db=db)))

    dp.add_handler(MessageHandler(
        Filters.status_update.new_chat_members,
        partial(handlers.bot_added_to_group, db=db),
    ))
    dp.add_handler(MessageHandler(
        Filters.status_update.new_chat_members,
        partial(handlers.welcome_new_member, db=db),
    ), group=1)

    dp.add_handler(MessageHandler(
        Filters.text | Filters.photo | Filters.video | Filters.document | Filters.audio,
        partial(handlers.message_tracker, db=db),
    ), group=2)

    logger.info("STEP 7 OK — All handlers registered.")
except Exception:
    logger.critical("STEP 7 FAILED — Handler registration error.")
    logger.critical(traceback.format_exc())
    sys.exit(1)

# ─── Step 8: Start polling ────────────────────────────────────────────────────
logger.info("STEP 8 — Starting polling loop...")
try:
    updater.start_polling()
    logger.info("STEP 8 OK — Bot is live and polling. Ready to receive messages.")
    logger.info("=" * 60)
    updater.idle()
except Exception:
    logger.critical("STEP 8 FAILED — Polling error.")
    logger.critical(traceback.format_exc())
    sys.exit(1)

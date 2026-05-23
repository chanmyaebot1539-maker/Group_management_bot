"""
main.py — Group Management Bot entry point (PTB v20)
Startup is logged step-by-step to make Render log diagnosis easy.
"""
import logging
import os
import sys
import traceback

# ─── Step 1: Verify env vars ─────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

logger.info("BOT STARTING UP  (python-telegram-bot v20)")

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGODB_URI = os.environ.get("MONGODB_URI")
OWNER_ID_RAW = os.environ.get("OWNER_ID")

logger.info(
    "STEP 1 OK — BOT_TOKEN: %s | MONGODB_URI: %s | OWNER_ID: %s",
    "set" if BOT_TOKEN else "MISSING",
    "set" if MONGODB_URI else "MISSING",
    OWNER_ID_RAW or "MISSING",
)
if not BOT_TOKEN or not MONGODB_URI or not OWNER_ID_RAW:
    logger.critical("STEP 1 FAILED — Missing required environment variables. Exiting.")
    sys.exit(1)

# ─── Step 2: Import PTB ───────────────────────────────────────────────────────
try:
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        CallbackQueryHandler,
        filters,
    )
    logger.info("STEP 2 OK — PTB v20 imported successfully.")
except Exception:
    logger.critical("STEP 2 FAILED — PTB import error:\n%s", traceback.format_exc())
    sys.exit(1)

# ─── Step 3: Import pymongo ───────────────────────────────────────────────────
try:
    from pymongo import MongoClient
    logger.info("STEP 3 OK — pymongo imported.")
except Exception:
    logger.critical("STEP 3 FAILED — pymongo import error:\n%s", traceback.format_exc())
    sys.exit(1)

# ─── Step 4: Import local modules ─────────────────────────────────────────────
try:
    from keep_alive import keep_alive
    logger.info("STEP 4a OK — keep_alive imported.")
except Exception:
    logger.critical("STEP 4a FAILED:\n%s", traceback.format_exc())
    sys.exit(1)

try:
    import handlers
    logger.info("STEP 4b OK — handlers imported.")
except Exception:
    logger.critical("STEP 4b FAILED:\n%s", traceback.format_exc())
    sys.exit(1)

# ─── Step 5: Connect MongoDB ──────────────────────────────────────────────────
try:
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    try:
        db = client.get_default_database()
    except Exception:
        db = client["groupbot"]
    logger.info("STEP 5 OK — MongoDB connected: %s", db.name)
except Exception:
    logger.critical("STEP 5 FAILED — MongoDB connection error:\n%s", traceback.format_exc())
    sys.exit(1)

# ─── Step 6: Start Flask keep-alive ──────────────────────────────────────────
try:
    keep_alive()
    logger.info("STEP 6 OK — Flask keep-alive started.")
except Exception:
    logger.critical("STEP 6 FAILED:\n%s", traceback.format_exc())
    sys.exit(1)

# ─── Step 7: Build application & register handlers ───────────────────────────
try:
    app = Application.builder().token(BOT_TOKEN).build()
    app.bot_data["db"] = db

    # /start
    app.add_handler(CommandHandler("start", handlers.start))

    # ⚙️ Group Settings
    app.add_handler(CommandHandler("settitle", handlers.settitle_handler))
    app.add_handler(CommandHandler("setdesc", handlers.setdesc_handler))
    app.add_handler(CommandHandler("setphoto", handlers.setphoto_handler))
    app.add_handler(CommandHandler("delphoto", handlers.delphoto_handler))
    app.add_handler(CommandHandler("slowmode", handlers.slowmode_handler))
    app.add_handler(CommandHandler("invitelink", handlers.invitelink_handler))
    app.add_handler(CommandHandler("revokeinvite", handlers.revokeinvite_handler))
    app.add_handler(CommandHandler("stickers", handlers.stickers_handler))
    app.add_handler(CommandHandler("media", handlers.media_handler))
    app.add_handler(CommandHandler("polls", handlers.polls_handler))
    app.add_handler(CommandHandler("setperm", handlers.setperm_handler))

    # 🛡️ Anti-Flood
    app.add_handler(CommandHandler("antiflood", handlers.antiflood_handler))

    # ℹ️ Info
    app.add_handler(CommandHandler("id", handlers.id_handler))
    app.add_handler(CommandHandler("info", handlers.info_handler))
    app.add_handler(CommandHandler("stats", handlers.stats_handler))

    # 🧹 Cleanup
    app.add_handler(CommandHandler("cleandeleted", handlers.cleandeleted_handler))
    app.add_handler(CommandHandler("cleaninactive", handlers.cleaninactive_handler))
    app.add_handler(CommandHandler("autoclean", handlers.autoclean_handler))
    app.add_handler(CommandHandler("autokickdeleted", handlers.autokickdeleted_handler))

    # 🔒 Content Locks
    app.add_handler(CommandHandler("lock", handlers.lock_handler))
    app.add_handler(CommandHandler("unlock", handlers.unlock_handler))
    app.add_handler(CommandHandler("locklist", handlers.locklist_handler))
    app.add_handler(CommandHandler("ro", handlers.ro_handler))
    app.add_handler(CommandHandler("unro", handlers.unro_handler))

    # 👋 Welcome & Rules
    app.add_handler(CommandHandler("setwelcome", handlers.setwelcome_handler))
    app.add_handler(CommandHandler("getwelcome", handlers.getwelcome_handler))
    app.add_handler(CommandHandler("welcome", handlers.welcome_toggle_handler))
    app.add_handler(CommandHandler("rules", handlers.rules_handler))
    app.add_handler(CommandHandler("setrules", handlers.setrules_handler))
    app.add_handler(CommandHandler("clearrules", handlers.clearrules_handler))

    # 🛡️ Moderation
    app.add_handler(CommandHandler("ban", handlers.ban_handler))
    app.add_handler(CommandHandler("unban", handlers.unban_handler))
    app.add_handler(CommandHandler("kick", handlers.kick_handler))
    app.add_handler(CommandHandler("mute", handlers.mute_handler))
    app.add_handler(CommandHandler("unmute", handlers.unmute_handler))
    app.add_handler(CommandHandler("warn", handlers.warn_handler))
    app.add_handler(CommandHandler("unwarn", handlers.unwarn_handler))
    app.add_handler(CommandHandler("warns", handlers.warns_handler))
    app.add_handler(CommandHandler("resetwarn", handlers.resetwarn_handler))
    app.add_handler(CommandHandler("clearwarns", handlers.clearwarns_handler))
    app.add_handler(CommandHandler("promote", handlers.promote_handler))
    app.add_handler(CommandHandler("demote", handlers.demote_handler))
    app.add_handler(CommandHandler("title", handlers.title_handler))
    app.add_handler(CommandHandler("pin", handlers.pin_handler))
    app.add_handler(CommandHandler("unpin", handlers.unpin_handler))
    app.add_handler(CommandHandler("unpinall", handlers.unpinall_handler))
    app.add_handler(CommandHandler("del", handlers.del_handler))
    app.add_handler(CommandHandler("purge", handlers.purge_handler))
    app.add_handler(CommandHandler("report", handlers.report_handler))

    # 📢 Broadcast (owner only)
    app.add_handler(CommandHandler("broadcast", handlers.broadcast_handler))
    app.add_handler(CommandHandler("userlist", handlers.userlist_handler))
    app.add_handler(CommandHandler("grouplist", handlers.grouplist_handler))

    # Callback query routing
    app.add_handler(CallbackQueryHandler(handlers.main_menu_callback, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(handlers.back_start_callback, pattern="^back_start$"))
    app.add_handler(CallbackQueryHandler(handlers.share_bot_callback, pattern="^share_bot$"))
    app.add_handler(CallbackQueryHandler(handlers.menu_mod_callback, pattern="^menu_mod$"))
    app.add_handler(CallbackQueryHandler(handlers.menu_settings_callback, pattern="^menu_settings$"))
    app.add_handler(CallbackQueryHandler(handlers.menu_locks_callback, pattern="^menu_locks$"))
    app.add_handler(CallbackQueryHandler(handlers.menu_info_callback, pattern="^menu_info$"))
    app.add_handler(CallbackQueryHandler(handlers.menu_stats_callback, pattern="^menu_stats$"))
    app.add_handler(CallbackQueryHandler(handlers.menu_owner_callback, pattern="^menu_owner$"))
    app.add_handler(CallbackQueryHandler(handlers.broadcast_target_callback, pattern="^bc_"))

    # New members (welcome)
    app.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS, handlers.welcome_new_member
    ), group=1)

    # Content lock enforcer — group 0, fires before flood check
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & ~filters.COMMAND,
        handlers.lock_enforcer,
    ), group=0)

    # Anti-flood checker — group 1
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & ~filters.COMMAND,
        handlers.flood_check,
    ), group=1)

    # Broadcast receive (owner DMs only)
    app.add_handler(MessageHandler(
        filters.User(OWNER_ID_RAW if not OWNER_ID_RAW.isdigit() else int(OWNER_ID_RAW))
        & filters.ChatType.PRIVATE
        & ~filters.COMMAND,
        handlers.broadcast_send,
    ))

    # Passive tracker — group 2
    app.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.VIDEO | filters.AUDIO,
        handlers.message_tracker,
    ), group=2)

    # Global error handler
    async def error_handler(update, context):
        logger.error(
            "HANDLER EXCEPTION — update: %s\n%s",
            update,
            "".join(traceback.format_exception(
                type(context.error), context.error, context.error.__traceback__
            )),
        )

    app.add_error_handler(error_handler)

    logger.info("STEP 7 OK — All handlers registered.")
except Exception:
    logger.critical("STEP 7 FAILED — Handler registration error:\n%s", traceback.format_exc())
    sys.exit(1)

# ─── Step 8: Start polling ────────────────────────────────────────────────────
logger.info("STEP 8 — Starting polling...")
try:
    app.run_polling(drop_pending_updates=True)
    logger.info("STEP 8 OK — Bot is live and polling.")
except Exception:
    logger.critical("STEP 8 FAILED:\n%s", traceback.format_exc())
    sys.exit(1)

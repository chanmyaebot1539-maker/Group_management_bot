import os
import logging
from functools import partial
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
)
from telegram.ext import CallbackContext

logger = logging.getLogger(__name__)

OWNER_ID_RAW = os.environ.get("OWNER_ID")
OWNER_ID = int(OWNER_ID_RAW) if OWNER_ID_RAW else None

BROADCAST_TARGET_KEY = "broadcast_target"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _is_admin(update: Update, context: CallbackContext) -> bool:
    user_id = update.effective_user.id
    if user_id == OWNER_ID:
        return True
    chat = update.effective_chat
    if chat.type == "private":
        return False
    try:
        admins = context.bot.get_chat_administrators(chat.id)
        return any(a.user.id == user_id for a in admins)
    except Exception as e:
        logger.error("get_chat_administrators error: %s", e)
        return False


def _track_user(user, db):
    if not user or user.is_bot:
        return
    db["users"].update_one(
        {"_id": user.id},
        {"$set": {
            "uname": user.username or "",
            "fname": user.first_name or "",
        }, "$setOnInsert": {"w_cnt": 0}},
        upsert=True,
    )


def _track_group(chat, db):
    if chat.type not in ("group", "supergroup"):
        return
    db["groups"].update_one(
        {"_id": chat.id},
        {"$set": {"title": chat.title or ""}},
        upsert=True,
    )


# ─── /start ───────────────────────────────────────────────────────────────────

def start(update: Update, context: CallbackContext, db=None):
    if db:
        _track_user(update.effective_user, db)
    keyboard = [
        [InlineKeyboardButton("➕ Add me to your chat!", url="https://t.me/{}?startgroup=true".format(context.bot.username))],
        [InlineKeyboardButton("🎵 Music bot", url="https://t.me/key_client_bot")],
        [InlineKeyboardButton("📢 Share this bot", switch_inline_query="")],
        [InlineKeyboardButton("📱 Menu", callback_data="main_menu")],
    ]
    update.message.reply_text(
        "👋 *Welcome to the Group Management Bot!*\n\n"
        "I help you keep your Telegram groups safe, organized, and engaging.\n\n"
        "✅ Moderation (ban, mute, warn)\n"
        "✅ Welcome messages\n"
        "✅ Group statistics\n"
        "✅ Broadcast to users & groups\n\n"
        "Use the buttons below to get started.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ─── Menu callbacks ───────────────────────────────────────────────────────────

def main_menu_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    query.answer()
    is_owner = user_id == OWNER_ID
    keyboard = [
        [
            InlineKeyboardButton("🛡️ Moderation Guide", callback_data="menu_mod"),
            InlineKeyboardButton("⚙️ Chat Settings", callback_data="menu_settings"),
        ],
        [
            InlineKeyboardButton("📊 Group Statistics", callback_data="menu_stats"),
        ],
    ]
    if is_owner:
        keyboard.append([InlineKeyboardButton("👑 Bot Owner Panel", callback_data="menu_owner")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_start")])
    query.edit_message_text(
        "📱 *Main Menu*\n\nChoose a category below:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def menu_mod_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    text = (
        "🛡️ *Moderation Guide*\n\n"
        "*/ban* — Reply to a message to permanently ban that user.\n"
        "*/unban* `@username` — Remove ban from a user.\n"
        "*/mute* — Reply to a message to restrict messaging.\n"
        "*/unmute* — Reply to restore messaging rights.\n"
        "*/warn* — Reply to warn a user (auto-ban at 3 warnings).\n\n"
        "_All commands require admin or owner status._"
    )
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
    query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


def menu_settings_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    text = (
        "⚙️ *Chat Settings*\n\n"
        "*/setwelcome* `[message]` — Set a custom welcome message.\n"
        "  Use `{name}` to mention the new member.\n"
        "*/clearwelcome* — Remove the custom welcome message.\n\n"
        "_Restricted to group admins._"
    )
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
    query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


def menu_stats_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    text = (
        "📊 *Group Statistics*\n\n"
        "*/stats* — View member count and warnings for this group.\n\n"
        "_Run inside a group._"
    )
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
    query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


def menu_owner_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    if user_id != OWNER_ID:
        query.answer("🛑 Unauthorized Access: Owner Only.", show_alert=True)
        return
    query.answer()
    text = (
        "👑 *Bot Owner Panel*\n\n"
        "*/broadcast* — Send a message to users, groups, or everyone.\n"
        "*/userlist* — List all registered users (with @username).\n"
        "*/grouplist* — List all managed groups (name + ID).\n"
    )
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
    query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


def back_start_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    keyboard = [
        [InlineKeyboardButton("➕ Add me to your chat!", url="https://t.me/{}?startgroup=true".format(context.bot.username))],
        [InlineKeyboardButton("🎵 Music bot", url="https://t.me/key_client_bot")],
        [InlineKeyboardButton("📢 Share this bot", switch_inline_query="")],
        [InlineKeyboardButton("📱 Menu", callback_data="main_menu")],
    ]
    query.edit_message_text(
        "👋 *Welcome to the Group Management Bot!*\n\n"
        "I help you keep your Telegram groups safe, organized, and engaging.\n\n"
        "✅ Moderation (ban, mute, warn)\n"
        "✅ Welcome messages\n"
        "✅ Group statistics\n"
        "✅ Broadcast to users & groups\n\n"
        "Use the buttons below to get started.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ─── Broadcast ────────────────────────────────────────────────────────────────

def broadcast_handler(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        update.message.reply_text("🛑 Owner only.")
        return
    keyboard = [
        [
            InlineKeyboardButton("👥 All Users", callback_data="bc_users"),
            InlineKeyboardButton("🏘️ All Groups", callback_data="bc_groups"),
        ],
        [InlineKeyboardButton("🌐 Everyone (Users + Groups)", callback_data="bc_all")],
        [InlineKeyboardButton("❌ Cancel", callback_data="bc_cancel")],
    ]
    update.message.reply_text(
        "📢 *Broadcast — Choose target:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def broadcast_target_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    if query.from_user.id != OWNER_ID:
        query.answer("🛑 Owner only.", show_alert=True)
        return

    data = query.data

    if data == "bc_cancel":
        query.answer()
        query.edit_message_text("❌ Broadcast cancelled.")
        context.user_data.pop(BROADCAST_TARGET_KEY, None)
        return

    target_map = {
        "bc_users": "users",
        "bc_groups": "groups",
        "bc_all": "all",
    }
    target = target_map.get(data)
    if not target:
        query.answer()
        return

    context.user_data[BROADCAST_TARGET_KEY] = target
    query.answer()
    label = {"users": "👥 All Users", "groups": "🏘️ All Groups", "all": "🌐 Everyone"}[target]
    query.edit_message_text(
        f"📢 *Broadcast to {label}*\n\nNow send your message (text, photo, or video):",
        parse_mode="Markdown",
    )


def broadcast_send(update: Update, context: CallbackContext, db):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        return
    target = context.user_data.get(BROADCAST_TARGET_KEY)
    if not target:
        return

    context.user_data.pop(BROADCAST_TARGET_KEY, None)
    msg = update.message

    sent, failed = 0, 0
    recipients = []

    if target in ("users", "all"):
        for doc in db["users"].find({}, {"_id": 1}):
            recipients.append(("user", doc["_id"]))
    if target in ("groups", "all"):
        for doc in db["groups"].find({}, {"_id": 1}):
            recipients.append(("group", doc["_id"]))

    for _, chat_id in recipients:
        try:
            if msg.text:
                context.bot.send_message(chat_id, msg.text, parse_mode="Markdown")
            elif msg.photo:
                context.bot.send_photo(chat_id, msg.photo[-1].file_id, caption=msg.caption or "")
            elif msg.video:
                context.bot.send_video(chat_id, msg.video.file_id, caption=msg.caption or "")
            else:
                context.bot.copy_message(chat_id, from_chat_id=msg.chat_id, message_id=msg.message_id)
            sent += 1
        except Exception as e:
            logger.warning("Broadcast failed for %s: %s", chat_id, e)
            failed += 1

    update.message.reply_text(
        f"📢 *Broadcast complete*\n\n✅ Sent: {sent}\n❌ Failed: {failed}",
        parse_mode="Markdown",
    )


# ─── Userlist & Grouplist ──────────────────────────────────────────────────────

def userlist_handler(update: Update, context: CallbackContext, db):
    if update.effective_user.id != OWNER_ID:
        update.message.reply_text("🛑 Owner only.")
        return
    users = list(db["users"].find({}, {"uname": 1, "fname": 1}).limit(50))
    if not users:
        update.message.reply_text("No users registered yet.")
        return
    lines = []
    for i, u in enumerate(users, 1):
        uname = f"@{u['uname']}" if u.get("uname") else u.get("fname", "Unknown")
        lines.append(f"{i}. {uname} (`{u['_id']}`)")
    text = "👥 *Registered Users*\n\n" + "\n".join(lines)
    if len(users) == 50:
        text += "\n\n_Showing first 50 users._"
    update.message.reply_text(text, parse_mode="Markdown")


def grouplist_handler(update: Update, context: CallbackContext, db):
    if update.effective_user.id != OWNER_ID:
        update.message.reply_text("🛑 Owner only.")
        return
    groups = list(db["groups"].find({}, {"title": 1}).limit(50))
    if not groups:
        update.message.reply_text("No groups registered yet.")
        return
    lines = []
    for i, g in enumerate(groups, 1):
        title = g.get("title") or "Unnamed Group"
        lines.append(f"{i}. *{title}*\n   ID: `{g['_id']}`")
    text = "🏘️ *Managed Groups*\n\n" + "\n".join(lines)
    if len(groups) == 50:
        text += "\n\n_Showing first 50 groups._"
    update.message.reply_text(text, parse_mode="Markdown")


# ─── Moderation ───────────────────────────────────────────────────────────────

def ban_handler(update: Update, context: CallbackContext):
    if not _is_admin(update, context):
        update.message.reply_text("⛔ You must be an admin to use this command.")
        return
    if not update.message.reply_to_message:
        update.message.reply_text("↩️ Reply to a user's message to ban them.")
        return
    target = update.message.reply_to_message.from_user
    try:
        context.bot.ban_chat_member(update.effective_chat.id, target.id)
        update.message.reply_text(f"🔨 *{target.full_name}* has been banned.", parse_mode="Markdown")
        logger.info("BANNED user %s (%s) from chat %s", target.id, target.full_name, update.effective_chat.id)
    except Exception as e:
        logger.error("Ban error: %s", e)
        update.message.reply_text("❌ Could not ban user. Check my admin permissions.")


def unban_handler(update: Update, context: CallbackContext):
    if not _is_admin(update, context):
        update.message.reply_text("⛔ You must be an admin to use this command.")
        return
    if not context.args:
        update.message.reply_text("Usage: /unban @username")
        return
    username = context.args[0].lstrip("@")
    try:
        user = context.bot.get_chat(f"@{username}")
        context.bot.unban_chat_member(update.effective_chat.id, user.id)
        update.message.reply_text(f"✅ *{user.full_name}* has been unbanned.", parse_mode="Markdown")
    except Exception as e:
        logger.error("Unban error: %s", e)
        update.message.reply_text("❌ Could not unban. Make sure the username is correct.")


def mute_handler(update: Update, context: CallbackContext):
    if not _is_admin(update, context):
        update.message.reply_text("⛔ You must be an admin to use this command.")
        return
    if not update.message.reply_to_message:
        update.message.reply_text("↩️ Reply to a user's message to mute them.")
        return
    target = update.message.reply_to_message.from_user
    try:
        context.bot.restrict_chat_member(
            update.effective_chat.id, target.id, ChatPermissions(can_send_messages=False)
        )
        update.message.reply_text(f"🔇 *{target.full_name}* has been muted.", parse_mode="Markdown")
    except Exception as e:
        logger.error("Mute error: %s", e)
        update.message.reply_text("❌ Could not mute user. Check my admin permissions.")


def unmute_handler(update: Update, context: CallbackContext):
    if not _is_admin(update, context):
        update.message.reply_text("⛔ You must be an admin to use this command.")
        return
    if not update.message.reply_to_message:
        update.message.reply_text("↩️ Reply to a user's message to unmute them.")
        return
    target = update.message.reply_to_message.from_user
    try:
        context.bot.restrict_chat_member(
            update.effective_chat.id,
            target.id,
            ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            ),
        )
        update.message.reply_text(f"🔊 *{target.full_name}* has been unmuted.", parse_mode="Markdown")
    except Exception as e:
        logger.error("Unmute error: %s", e)
        update.message.reply_text("❌ Could not unmute user.")


def warn_handler(update: Update, context: CallbackContext, db):
    if not _is_admin(update, context):
        update.message.reply_text("⛔ You must be an admin to use this command.")
        return
    if not update.message.reply_to_message:
        update.message.reply_text("↩️ Reply to a user's message to warn them.")
        return
    target = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    reason = " ".join(context.args) if context.args else "No reason provided"

    doc = db["users"].find_one_and_update(
        {"_id": target.id},
        {"$inc": {"w_cnt": 1}},
        upsert=True,
        return_document=True,
    )
    warn_count = doc.get("w_cnt", 1) if doc else 1

    if warn_count >= 3:
        try:
            context.bot.ban_chat_member(chat_id, target.id)
            db["users"].update_one({"_id": target.id}, {"$set": {"w_cnt": 0}})
            update.message.reply_text(
                f"🔨 *{target.full_name}* banned after 3 warnings.", parse_mode="Markdown"
            )
            logger.info("Auto-banned %s after 3 warns in chat %s", target.id, chat_id)
        except Exception as e:
            logger.error("Auto-ban after warn error: %s", e)
    else:
        update.message.reply_text(
            f"⚠️ *{target.full_name}* warned ({warn_count}/3).\nReason: {reason}",
            parse_mode="Markdown",
        )


# ─── Welcome ──────────────────────────────────────────────────────────────────

def welcome_new_member(update: Update, context: CallbackContext, db):
    chat = update.effective_chat
    _track_group(chat, db)
    group_doc = db["groups"].find_one({"_id": chat.id})
    custom_welcome = group_doc.get("wlcm") if group_doc else None

    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        _track_user(member, db)
        text = custom_welcome or "👋 Welcome to the group, *{name}*! Please read the rules."
        update.message.reply_text(
            text.replace("{name}", member.full_name), parse_mode="Markdown"
        )


def bot_added_to_group(update: Update, context: CallbackContext, db):
    chat = update.effective_chat
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            _track_group(chat, db)
            logger.info("Bot added to group: %s (%s)", chat.title, chat.id)
            update.message.reply_text(
                f"👋 Thanks for adding me to *{chat.title}*!\n"
                "I'm ready to help manage this group.\n"
                "Give me admin rights to enable all features.",
                parse_mode="Markdown",
            )
            break


def setwelcome_handler(update: Update, context: CallbackContext, db):
    if not _is_admin(update, context):
        update.message.reply_text("⛔ Admins only.")
        return
    if not context.args:
        update.message.reply_text("Usage: /setwelcome [message] (use {name} for the member's name)")
        return
    welcome_msg = " ".join(context.args)
    db["groups"].update_one(
        {"_id": update.effective_chat.id},
        {"$set": {"wlcm": welcome_msg, "title": update.effective_chat.title or ""}},
        upsert=True,
    )
    update.message.reply_text("✅ Welcome message updated.")


def clearwelcome_handler(update: Update, context: CallbackContext, db):
    if not _is_admin(update, context):
        update.message.reply_text("⛔ Admins only.")
        return
    db["groups"].update_one({"_id": update.effective_chat.id}, {"$unset": {"wlcm": ""}})
    update.message.reply_text("✅ Welcome message cleared.")


def stats_handler(update: Update, context: CallbackContext, db):
    chat_id = update.effective_chat.id
    _track_group(update.effective_chat, db)
    try:
        member_count = context.bot.get_chat_member_count(chat_id)
    except Exception:
        member_count = "N/A"
    warned_users = db["users"].count_documents({"w_cnt": {"$gt": 0}})
    update.message.reply_text(
        f"📊 *Group Statistics*\n\n"
        f"👥 Members: {member_count}\n"
        f"⚠️ Users with active warnings: {warned_users}",
        parse_mode="Markdown",
    )


# ─── Message tracker (track users & groups passively) ─────────────────────────

def message_tracker(update: Update, context: CallbackContext, db):
    if update.effective_user:
        _track_user(update.effective_user, db)
    if update.effective_chat:
        _track_group(update.effective_chat, db)

import os
import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
)
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

OWNER_ID_RAW = os.environ.get("OWNER_ID")
OWNER_ID = int(OWNER_ID_RAW) if OWNER_ID_RAW else None
BROADCAST_TARGET_KEY = "broadcast_target"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _db(context: ContextTypes.DEFAULT_TYPE):
    return context.bot_data.get("db")


async def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if user_id == OWNER_ID:
        return True
    chat = update.effective_chat
    if chat.type == "private":
        return False
    try:
        member = await context.bot.get_chat_member(chat.id, user_id)
        return member.status in ("administrator", "creator")
    except Exception as e:
        logger.error("get_chat_member error: %s", e)
        return False


def _track_user(user, db):
    if not user or user.is_bot:
        return
    db["users"].update_one(
        {"_id": user.id},
        {
            "$set": {"uname": user.username or "", "fname": user.first_name or ""},
            "$setOnInsert": {"w_cnt": 0},
        },
        upsert=True,
    )


def _track_group(chat, db):
    if chat and chat.type in ("group", "supergroup"):
        db["groups"].update_one(
            {"_id": chat.id},
            {"$set": {"title": chat.title or ""}},
            upsert=True,
        )


def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ─── /start ───────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        db = _db(context)
        if db:
            _track_user(update.effective_user, db)
    except Exception as e:
        logger.error("start: db track error: %s", e)

    bot_username = context.bot.username or "your_bot"
    keyboard = [
        [InlineKeyboardButton("➕ Add me to your chat!", url=f"https://t.me/{bot_username}?startgroup=true")],
        [InlineKeyboardButton("🎵 Music bot", url="https://t.me/key_client_bot")],
        [InlineKeyboardButton("📢 Share this bot", url=f"https://t.me/{bot_username}")],
        [InlineKeyboardButton("📱 Menu", callback_data="main_menu")],
    ]
    await update.message.reply_text(
        "👋 <b>Welcome to the Group Management Bot!</b>\n\n"
        "I help you keep your Telegram groups safe, organized, and engaging.\n\n"
        "✅ Moderation (ban, mute, warn)\n"
        "✅ Welcome messages\n"
        "✅ Group statistics\n"
        "✅ Broadcast to users and groups\n\n"
        "Use the buttons below to get started.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ─── Menu callbacks ───────────────────────────────────────────────────────────

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    is_owner = query.from_user.id == OWNER_ID
    keyboard = [
        [
            InlineKeyboardButton("🛡️ Moderation Guide", callback_data="menu_mod"),
            InlineKeyboardButton("⚙️ Chat Settings", callback_data="menu_settings"),
        ],
        [InlineKeyboardButton("📊 Group Statistics", callback_data="menu_stats")],
    ]
    if is_owner:
        keyboard.append([InlineKeyboardButton("👑 Bot Owner Panel", callback_data="menu_owner")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_start")])
    await query.edit_message_text(
        "📱 <b>Main Menu</b>\n\nChoose a category below:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def menu_mod_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "🛡️ <b>Moderation Guide</b>\n\n"
        "/ban — Reply to a message to permanently ban that user.\n"
        "/unban @username — Remove ban from a user.\n"
        "/mute — Reply to restrict a user from messaging.\n"
        "/unmute — Reply to restore messaging rights.\n"
        "/warn — Reply to warn (auto-ban at 3 warnings).\n\n"
        "<i>All commands require admin or owner status.</i>"
    )
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]),
    )


async def menu_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "⚙️ <b>Chat Settings</b>\n\n"
        "/setwelcome [message] — Set custom welcome message.\n"
        "  Use <code>{name}</code> to mention the new member.\n"
        "/clearwelcome — Remove welcome message.\n\n"
        "<i>Restricted to group admins.</i>"
    )
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]),
    )


async def menu_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📊 <b>Group Statistics</b>\n\n/stats — View member count and warnings.\n\n<i>Run inside a group.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]),
    )


async def menu_owner_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != OWNER_ID:
        await query.answer("🛑 Unauthorized Access: Owner Only.", show_alert=True)
        return
    await query.answer()
    text = (
        "👑 <b>Bot Owner Panel</b>\n\n"
        "/broadcast — Send message to users, groups, or everyone.\n"
        "/userlist — List all registered users (@username).\n"
        "/grouplist — List all managed groups (name + ID).\n"
    )
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]),
    )


async def back_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bot_username = context.bot.username or "your_bot"
    keyboard = [
        [InlineKeyboardButton("➕ Add me to your chat!", url=f"https://t.me/{bot_username}?startgroup=true")],
        [InlineKeyboardButton("🎵 Music bot", url="https://t.me/key_client_bot")],
        [InlineKeyboardButton("📢 Share this bot", url=f"https://t.me/{bot_username}")],
        [InlineKeyboardButton("📱 Menu", callback_data="main_menu")],
    ]
    await query.edit_message_text(
        "👋 <b>Welcome to the Group Management Bot!</b>\n\n"
        "I help you keep your Telegram groups safe, organized, and engaging.\n\n"
        "✅ Moderation (ban, mute, warn)\n"
        "✅ Welcome messages\n"
        "✅ Group statistics\n"
        "✅ Broadcast to users and groups\n\n"
        "Use the buttons below to get started.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ─── Broadcast ────────────────────────────────────────────────────────────────

async def broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("🛑 Owner only.")
        return
    keyboard = [
        [
            InlineKeyboardButton("👥 All Users", callback_data="bc_users"),
            InlineKeyboardButton("🏘️ All Groups", callback_data="bc_groups"),
        ],
        [InlineKeyboardButton("🌐 Everyone (Users + Groups)", callback_data="bc_all")],
        [InlineKeyboardButton("❌ Cancel", callback_data="bc_cancel")],
    ]
    await update.message.reply_text(
        "📢 <b>Broadcast — Choose target:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def broadcast_target_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != OWNER_ID:
        await query.answer("🛑 Owner only.", show_alert=True)
        return

    if query.data == "bc_cancel":
        await query.answer()
        await query.edit_message_text("❌ Broadcast cancelled.")
        context.user_data.pop(BROADCAST_TARGET_KEY, None)
        return

    target_map = {"bc_users": "users", "bc_groups": "groups", "bc_all": "all"}
    target = target_map.get(query.data)
    if not target:
        await query.answer()
        return

    context.user_data[BROADCAST_TARGET_KEY] = target
    await query.answer()
    label = {"users": "👥 All Users", "groups": "🏘️ All Groups", "all": "🌐 Everyone"}[target]
    await query.edit_message_text(
        f"📢 <b>Broadcast to {label}</b>\n\nNow send your message (text, photo, or video):",
        parse_mode="HTML",
    )


async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    target = context.user_data.get(BROADCAST_TARGET_KEY)
    if not target:
        return

    db = _db(context)
    context.user_data.pop(BROADCAST_TARGET_KEY, None)
    msg = update.message
    sent, failed = 0, 0
    recipients = []

    if target in ("users", "all"):
        for doc in db["users"].find({}, {"_id": 1}):
            recipients.append(doc["_id"])
    if target in ("groups", "all"):
        for doc in db["groups"].find({}, {"_id": 1}):
            recipients.append(doc["_id"])

    for chat_id in recipients:
        try:
            if msg.text:
                await context.bot.send_message(chat_id, msg.text)
            elif msg.photo:
                await context.bot.send_photo(chat_id, msg.photo[-1].file_id, caption=msg.caption or "")
            elif msg.video:
                await context.bot.send_video(chat_id, msg.video.file_id, caption=msg.caption or "")
            else:
                await context.bot.copy_message(chat_id, from_chat_id=msg.chat_id, message_id=msg.message_id)
            sent += 1
        except Exception as e:
            logger.warning("Broadcast failed for %s: %s", chat_id, e)
            failed += 1

    await update.message.reply_text(
        f"📢 <b>Broadcast complete</b>\n\n✅ Sent: {sent}\n❌ Failed: {failed}",
        parse_mode="HTML",
    )


# ─── Userlist & Grouplist ──────────────────────────────────────────────────────

async def userlist_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("🛑 Owner only.")
        return
    db = _db(context)
    users = list(db["users"].find({}, {"uname": 1, "fname": 1}).limit(50))
    if not users:
        await update.message.reply_text("No users registered yet.")
        return
    lines = []
    for i, u in enumerate(users, 1):
        uname = f"@{_esc(u['uname'])}" if u.get("uname") else _esc(u.get("fname", "Unknown"))
        lines.append(f"{i}. {uname} (<code>{u['_id']}</code>)")
    text = "👥 <b>Registered Users</b>\n\n" + "\n".join(lines)
    if len(users) == 50:
        text += "\n\n<i>Showing first 50 users.</i>"
    await update.message.reply_text(text, parse_mode="HTML")


async def grouplist_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("🛑 Owner only.")
        return
    db = _db(context)
    groups = list(db["groups"].find({}, {"title": 1}).limit(50))
    if not groups:
        await update.message.reply_text("No groups registered yet.")
        return
    lines = []
    for i, g in enumerate(groups, 1):
        title = _esc(g.get("title") or "Unnamed Group")
        lines.append(f"{i}. <b>{title}</b>\n   ID: <code>{g['_id']}</code>")
    text = "🏘️ <b>Managed Groups</b>\n\n" + "\n".join(lines)
    if len(groups) == 50:
        text += "\n\n<i>Showing first 50 groups.</i>"
    await update.message.reply_text(text, parse_mode="HTML")


# ─── Moderation ───────────────────────────────────────────────────────────────

async def ban_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("⛔ You must be an admin to use this command.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("↩️ Reply to a user's message to ban them.")
        return
    target = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await update.message.reply_text(
            f"🔨 <b>{_esc(target.full_name)}</b> has been banned.", parse_mode="HTML"
        )
        logger.info("BANNED user %s (%s) from chat %s", target.id, target.full_name, update.effective_chat.id)
    except Exception as e:
        logger.error("Ban error: %s", e)
        await update.message.reply_text("❌ Could not ban user. Check my admin permissions.")


async def unban_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("⛔ You must be an admin to use this command.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /unban @username")
        return
    username = context.args[0].lstrip("@")
    try:
        user = await context.bot.get_chat(f"@{username}")
        await context.bot.unban_chat_member(update.effective_chat.id, user.id)
        await update.message.reply_text(
            f"✅ <b>{_esc(user.full_name)}</b> has been unbanned.", parse_mode="HTML"
        )
    except Exception as e:
        logger.error("Unban error: %s", e)
        await update.message.reply_text("❌ Could not unban. Make sure the username is correct.")


async def mute_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("⛔ You must be an admin to use this command.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("↩️ Reply to a user's message to mute them.")
        return
    target = update.message.reply_to_message.from_user
    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id, target.id,
            ChatPermissions(can_send_messages=False),
        )
        await update.message.reply_text(
            f"🔇 <b>{_esc(target.full_name)}</b> has been muted.", parse_mode="HTML"
        )
    except Exception as e:
        logger.error("Mute error: %s", e)
        await update.message.reply_text("❌ Could not mute user. Check my admin permissions.")


async def unmute_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("⛔ You must be an admin to use this command.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("↩️ Reply to a user's message to unmute them.")
        return
    target = update.message.reply_to_message.from_user
    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id, target.id,
            ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            ),
        )
        await update.message.reply_text(
            f"🔊 <b>{_esc(target.full_name)}</b> has been unmuted.", parse_mode="HTML"
        )
    except Exception as e:
        logger.error("Unmute error: %s", e)
        await update.message.reply_text("❌ Could not unmute user.")


async def warn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("⛔ You must be an admin to use this command.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("↩️ Reply to a user's message to warn them.")
        return
    db = _db(context)
    target = update.message.reply_to_message.from_user
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
            await context.bot.ban_chat_member(update.effective_chat.id, target.id)
            db["users"].update_one({"_id": target.id}, {"$set": {"w_cnt": 0}})
            await update.message.reply_text(
                f"🔨 <b>{_esc(target.full_name)}</b> banned after 3 warnings.", parse_mode="HTML"
            )
        except Exception as e:
            logger.error("Auto-ban after warn error: %s", e)
    else:
        await update.message.reply_text(
            f"⚠️ <b>{_esc(target.full_name)}</b> warned ({warn_count}/3).\nReason: {_esc(reason)}",
            parse_mode="HTML",
        )


# ─── Welcome ──────────────────────────────────────────────────────────────────

async def bot_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = _db(context)
    chat = update.effective_chat
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            if db:
                _track_group(chat, db)
            logger.info("Bot added to group: %s (%s)", chat.title, chat.id)
            await update.message.reply_text(
                f"👋 Thanks for adding me to <b>{_esc(chat.title)}</b>!\n"
                "Give me admin rights to enable all features.",
                parse_mode="HTML",
            )
            break


async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = _db(context)
    chat = update.effective_chat
    if db:
        _track_group(chat, db)
    group_doc = db["groups"].find_one({"_id": chat.id}) if db else None
    custom_welcome = group_doc.get("wlcm") if group_doc else None

    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        if db:
            _track_user(member, db)
        if custom_welcome:
            text = custom_welcome.replace("{name}", member.full_name)
            await update.message.reply_text(text)
        else:
            await update.message.reply_text(
                f"👋 Welcome to the group, <b>{_esc(member.full_name)}</b>! Please read the rules.",
                parse_mode="HTML",
            )


async def setwelcome_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("⛔ Admins only.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /setwelcome [message] (use {name} for the member's name)")
        return
    db = _db(context)
    welcome_msg = " ".join(context.args)
    db["groups"].update_one(
        {"_id": update.effective_chat.id},
        {"$set": {"wlcm": welcome_msg, "title": update.effective_chat.title or ""}},
        upsert=True,
    )
    await update.message.reply_text("✅ Welcome message updated.")


async def clearwelcome_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("⛔ Admins only.")
        return
    db = _db(context)
    db["groups"].update_one({"_id": update.effective_chat.id}, {"$unset": {"wlcm": ""}})
    await update.message.reply_text("✅ Welcome message cleared.")


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = _db(context)
    chat_id = update.effective_chat.id
    if db:
        _track_group(update.effective_chat, db)
    try:
        member_count = await context.bot.get_chat_member_count(chat_id)
    except Exception:
        member_count = "N/A"
    warned_users = db["users"].count_documents({"w_cnt": {"$gt": 0}}) if db else 0
    await update.message.reply_text(
        f"📊 <b>Group Statistics</b>\n\n"
        f"👥 Members: {member_count}\n"
        f"⚠️ Users with active warnings: {warned_users}",
        parse_mode="HTML",
    )


# ─── Passive message tracker ─────────────────────────────────────────────────

async def message_tracker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = _db(context)
    if not db:
        return
    if update.effective_user:
        _track_user(update.effective_user, db)
    if update.effective_chat:
        _track_group(update.effective_chat, db)

import os
import logging
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


def _is_admin(update: Update, context: CallbackContext) -> bool:
    user_id = update.effective_user.id
    if user_id == OWNER_ID:
        return True
    chat = update.effective_chat
    if chat.type == "private":
        return False
    admins = context.bot.get_chat_administrators(chat.id)
    return any(a.user.id == user_id for a in admins)


def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("➕ Add me to your chat!", url="https://github.com/tdlib/td/issues/1962")],
        [InlineKeyboardButton("🎵 Music bot", url="https://t.me/key_client_bot")],
        [InlineKeyboardButton("📢 Share your contact", switch_inline_query="")],
        [InlineKeyboardButton("📱 Menu", callback_data="main_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "👋 *Welcome to the Group Management Bot!*\n\n"
        "I help you keep your Telegram groups safe, organized, and engaging.\n\n"
        "✅ Moderation (ban, mute, warn)\n"
        "✅ Welcome messages\n"
        "✅ Group statistics\n"
        "✅ Multi-language support\n\n"
        "Use the buttons below to get started.",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


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
        "*/ban* `@user` — Permanently ban a user from the group.\n"
        "*/unban* `@user` — Remove the ban from a user.\n"
        "*/mute* `@user` `[time]` — Restrict a user from sending messages.\n"
        "  Example: `/mute @user 30m` (supports m, h, d)\n"
        "*/unmute* `@user` — Restore a user's messaging rights.\n"
        "*/warn* `@user` `[reason]` — Issue a warning. After 3 warns, user is banned.\n\n"
        "_All commands require admin or owner status._"
    )
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
    query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


def menu_settings_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    text = (
        "⚙️ *Chat Settings*\n\n"
        "*/setwelcome* `[message]` — Set a custom welcome message for new members.\n"
        "*/clearwelcome* — Remove the custom welcome message.\n"
        "*/setlang* `[code]` — Set the bot language (e.g., `en`, `es`, `de`).\n\n"
        "_These commands are restricted to group admins._"
    )
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
    query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


def menu_stats_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    text = (
        "📊 *Group Statistics*\n\n"
        "*/stats* — View member count, warnings issued, and ban history for this group.\n\n"
        "_Run this command inside a group to see live data._"
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
        "*/broadcast* `[message]` — Send a message to all registered users.\n"
        "*/grouplist* — List all groups the bot is managing.\n"
        "*/userlist* — List all registered users.\n"
        "*/ban_global* `@user` — Ban a user from all managed groups.\n"
    )
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
    query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


def back_start_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    keyboard = [
        [InlineKeyboardButton("➕ Add me to your chat!", url="https://github.com/tdlib/td/issues/1962")],
        [InlineKeyboardButton("🎵 Music bot", url="https://t.me/key_client_bot")],
        [InlineKeyboardButton("📢 Share your contact", switch_inline_query="")],
        [InlineKeyboardButton("📱 Menu", callback_data="main_menu")],
    ]
    query.edit_message_text(
        "👋 *Welcome to the Group Management Bot!*\n\n"
        "I help you keep your Telegram groups safe, organized, and engaging.\n\n"
        "✅ Moderation (ban, mute, warn)\n"
        "✅ Welcome messages\n"
        "✅ Group statistics\n"
        "✅ Multi-language support\n\n"
        "Use the buttons below to get started.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def ban_handler(update: Update, context: CallbackContext):
    if not _is_admin(update, context):
        update.message.reply_text("⛔ You must be an admin to use this command.")
        return
    if not update.message.reply_to_message:
        update.message.reply_text("↩️ Reply to a user's message to ban them.")
        return
    target = update.message.reply_to_message.from_user
    context.bot.ban_chat_member(update.effective_chat.id, target.id)
    update.message.reply_text(f"🔨 *{target.full_name}* has been banned.", parse_mode="Markdown")


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
        update.message.reply_text("❌ Could not unban user. Make sure the username is correct.")


def mute_handler(update: Update, context: CallbackContext):
    if not _is_admin(update, context):
        update.message.reply_text("⛔ You must be an admin to use this command.")
        return
    if not update.message.reply_to_message:
        update.message.reply_text("↩️ Reply to a user's message to mute them.")
        return
    target = update.message.reply_to_message.from_user
    permissions = ChatPermissions(can_send_messages=False)
    context.bot.restrict_chat_member(update.effective_chat.id, target.id, permissions)
    update.message.reply_text(f"🔇 *{target.full_name}* has been muted.", parse_mode="Markdown")


def unmute_handler(update: Update, context: CallbackContext):
    if not _is_admin(update, context):
        update.message.reply_text("⛔ You must be an admin to use this command.")
        return
    if not update.message.reply_to_message:
        update.message.reply_text("↩️ Reply to a user's message to unmute them.")
        return
    target = update.message.reply_to_message.from_user
    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
    )
    context.bot.restrict_chat_member(update.effective_chat.id, target.id, permissions)
    update.message.reply_text(f"🔊 *{target.full_name}* has been unmuted.", parse_mode="Markdown")


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

    users_col = db["users"]
    doc = users_col.find_one_and_update(
        {"_id": target.id},
        {"$inc": {"w_cnt": 1}},
        upsert=True,
        return_document=True,
    )
    warn_count = doc.get("w_cnt", 1) if doc else 1

    if warn_count >= 3:
        context.bot.ban_chat_member(chat_id, target.id)
        users_col.update_one({"_id": target.id}, {"$set": {"w_cnt": 0}})
        update.message.reply_text(
            f"🔨 *{target.full_name}* has been banned after 3 warnings.",
            parse_mode="Markdown",
        )
    else:
        update.message.reply_text(
            f"⚠️ *{target.full_name}* has been warned ({warn_count}/3).\nReason: {reason}",
            parse_mode="Markdown",
        )


def welcome_new_member(update: Update, context: CallbackContext, db):
    chat_id = update.effective_chat.id
    groups_col = db["groups"]
    group_doc = groups_col.find_one({"_id": chat_id})
    custom_welcome = group_doc.get("wlcm") if group_doc else None

    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        text = custom_welcome or f"👋 Welcome to the group, *{member.full_name}*! Please read the rules."
        update.message.reply_text(text.replace("{name}", member.full_name), parse_mode="Markdown")

        db["users"].update_one({"_id": member.id}, {"$setOnInsert": {"w_cnt": 0}}, upsert=True)


def setwelcome_handler(update: Update, context: CallbackContext, db):
    if not _is_admin(update, context):
        update.message.reply_text("⛔ You must be an admin to use this command.")
        return
    if not context.args:
        update.message.reply_text("Usage: /setwelcome [message] (use {name} for the user's name)")
        return
    welcome_msg = " ".join(context.args)
    db["groups"].update_one(
        {"_id": update.effective_chat.id},
        {"$set": {"wlcm": welcome_msg}},
        upsert=True,
    )
    update.message.reply_text("✅ Welcome message updated.")


def clearwelcome_handler(update: Update, context: CallbackContext, db):
    if not _is_admin(update, context):
        update.message.reply_text("⛔ You must be an admin to use this command.")
        return
    db["groups"].update_one({"_id": update.effective_chat.id}, {"$unset": {"wlcm": ""}})
    update.message.reply_text("✅ Welcome message cleared.")


def stats_handler(update: Update, context: CallbackContext, db):
    chat_id = update.effective_chat.id
    member_count = context.bot.get_chat_member_count(chat_id)
    warned_users = db["users"].count_documents({"w_cnt": {"$gt": 0}})
    update.message.reply_text(
        f"📊 *Group Statistics*\n\n"
        f"👥 Members: {member_count}\n"
        f"⚠️ Users with warnings: {warned_users}",
        parse_mode="Markdown",
    )

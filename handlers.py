"""
handlers.py — Group Management Bot (PTB v20)
All handlers. MongoDB short-key schema. HTML parse mode throughout.
"""
import os
import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
)
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
BROADCAST_TARGET_KEY = "broadcast_target"

# Anti-flood in-memory store: {chat_id: {user_id: [timestamps]}}
_flood_cache: dict = defaultdict(lambda: defaultdict(list))

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _db(context: ContextTypes.DEFAULT_TYPE):
    return context.bot_data.get("db")


def _esc(text: str) -> str:
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _track_user(user, db):
    if not user or user.is_bot:
        return
    db["users"].update_one(
        {"_id": user.id},
        {
            "$set": {
                "uname": user.username or "",
                "fname": user.first_name or "",
                "last": int(time.time()),
            },
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


async def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if user_id == OWNER_ID:
        return True
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return False
    try:
        member = await context.bot.get_chat_member(chat.id, user_id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception as e:
        logger.error("_is_admin error: %s", e)
        return False


async def _get_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return (user_object, error_string). Checks reply or first arg."""
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user, None
    if context.args:
        identifier = context.args[0].lstrip("@")
        try:
            user = await context.bot.get_chat(identifier)
            return user, None
        except Exception:
            return None, f"❌ User <code>{_esc(identifier)}</code> not found."
    return None, "↩️ Reply to a user's message or provide @username / user_id."


async def _require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not await _is_admin(update, context):
        await update.message.reply_text("⛔ Admin or owner only.")
        return False
    return True


# ─── /start ───────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        db = _db(context)
        if db:
            _track_user(update.effective_user, db)
    except Exception as e:
        logger.error("start db track: %s", e)

    # Check for referral start (e.g. /start ref_12345)
    if context.args and context.args[0].startswith("ref_"):
        ref_id = context.args[0][4:]
        logger.info("Referral start from ref_%s to user %s", ref_id, update.effective_user.id)

    bot_username = context.bot.username or "your_bot"
    keyboard = [
        [InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{bot_username}?startgroup=true")],
        [InlineKeyboardButton("🎵 Music bot", url="https://t.me/music100200bot?start=tg")],
        [InlineKeyboardButton("📢 Get my referral link", callback_data="share_bot")],
        [InlineKeyboardButton("📱 Menu", callback_data="main_menu")],
    ]
    await update.message.reply_text(
        "👋 <b>Welcome to the Group Management Bot!</b>\n\n"
        "I help keep Telegram groups safe, organized, and engaging.\n\n"
        "✅ Moderation (ban, mute, warn, kick)\n"
        "✅ Content locks and anti-flood\n"
        "✅ Custom welcome &amp; rules\n"
        "✅ Group settings &amp; permissions\n"
        "✅ Broadcast to users and groups\n\n"
        "Use the buttons below to get started.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ─── Share / Referral ─────────────────────────────────────────────────────────

async def share_bot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bot_username = context.bot.username or "your_bot"
    user_id = query.from_user.id
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    await query.message.reply_text(
        f"📢 <b>Your referral link:</b>\n<code>{ref_link}</code>\n\n"
        "Share this link and track who joins via you!",
        parse_mode="HTML",
    )


# ─── Menu callbacks ───────────────────────────────────────────────────────────

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    is_owner = query.from_user.id == OWNER_ID
    keyboard = [
        [
            InlineKeyboardButton("🛡️ Moderation", callback_data="menu_mod"),
            InlineKeyboardButton("⚙️ Group Settings", callback_data="menu_settings"),
        ],
        [
            InlineKeyboardButton("🔒 Content Locks", callback_data="menu_locks"),
            InlineKeyboardButton("ℹ️ Info", callback_data="menu_info"),
        ],
        [InlineKeyboardButton("📊 Group Stats", callback_data="menu_stats")],
    ]
    if is_owner:
        keyboard.append([InlineKeyboardButton("👑 Owner Panel", callback_data="menu_owner")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_start")])
    await query.edit_message_text(
        "📱 <b>Main Menu</b>\n\nChoose a category:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def menu_mod_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "🛡️ <b>Moderation Commands</b>\n\n"
        "<b>Bans &amp; Kicks:</b>\n"
        "/ban — Reply to ban a user permanently\n"
        "/unban @user — Remove a ban\n"
        "/kick — Reply to remove from group\n\n"
        "<b>Mute:</b>\n"
        "/mute [1m|1h|1d] — Reply to mute (optional duration)\n"
        "/unmute — Reply to restore messaging\n\n"
        "<b>Warnings:</b>\n"
        "/warn — Reply to warn (auto-ban at 3)\n"
        "/unwarn — Remove last warning\n"
        "/warns — View warnings\n"
        "/resetwarn / /clearwarns — Reset all warnings\n\n"
        "<b>Admin:</b>\n"
        "/promote, /demote, /title @user [title]\n\n"
        "<b>Messages:</b>\n"
        "/pin, /unpin, /unpinall, /del, /purge [N], /report\n\n"
        "<i>All commands require admin rights.</i>"
    )
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]),
    )


async def menu_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "⚙️ <b>Group Settings Commands</b>\n\n"
        "/settitle &lt;title&gt; — Change group title\n"
        "/setdesc &lt;text&gt; — Change group description\n"
        "/setphoto — Reply to image to set group photo\n"
        "/delphoto — Remove group photo\n"
        "/slowmode &lt;sec&gt; — Set slow mode (0 to disable)\n"
        "/invitelink — Get invite link\n"
        "/revokeinvite — Revoke &amp; regenerate invite link\n\n"
        "<b>Permissions:</b>\n"
        "/stickers on|off — Toggle stickers\n"
        "/media on|off — Toggle media messages\n"
        "/polls on|off — Toggle polls\n"
        "/setperm &lt;type&gt; on|off — Set any permission\n\n"
        "<b>Anti-Flood:</b>\n"
        "/antiflood on|off [limit] [window_sec] [mute_min]\n"
        "/antiflood — Show current settings\n\n"
        "<b>Cleanup:</b>\n"
        "/cleandeleted — Kick deleted accounts\n"
        "/cleaninactive [days] — Kick inactive members\n"
    )
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]),
    )


async def menu_locks_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "🔒 <b>Content Lock Commands</b>\n\n"
        "/lock &lt;type&gt; — Activate a content filter\n"
        "/unlock &lt;type&gt; — Deactivate a content filter\n"
        "/locklist — Show all active locks\n"
        "/ro — Enable read-only mode (non-admins can't send)\n"
        "/unro — Disable read-only mode\n\n"
        "<b>Lock types:</b> messages, media, stickers, gifs, polls, links\n\n"
        "<b>Welcome &amp; Rules:</b>\n"
        "/setwelcome &lt;text&gt; — Set welcome message (use {name})\n"
        "/getwelcome — View current welcome message\n"
        "/welcome on|off — Toggle welcome feature\n"
        "/rules — Show group rules\n"
        "/setrules &lt;text&gt; — Set group rules\n"
        "/clearrules — Remove rules\n"
    )
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]),
    )


async def menu_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "ℹ️ <b>Info Commands</b>\n\n"
        "/id — Show your user ID or group chat ID\n"
        "/info [@user] — Show user details\n"
        "/stats — Group statistics\n"
    )
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]),
    )


async def menu_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📊 <b>Group Statistics</b>\n\nUse /stats inside a group to see member count and active warnings.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]),
    )


async def menu_owner_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != OWNER_ID:
        await query.answer("🛑 Owner only.", show_alert=True)
        return
    await query.answer()
    text = (
        "👑 <b>Bot Owner Panel</b>\n\n"
        "/broadcast — Send message to users, groups, or everyone\n"
        "/userlist — List all registered users\n"
        "/grouplist — List all managed groups\n"
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
        [InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{bot_username}?startgroup=true")],
        [InlineKeyboardButton("🎵 Music bot", url="https://t.me/music100200bot?start=tg")],
        [InlineKeyboardButton("📢 Get my referral link", callback_data="share_bot")],
        [InlineKeyboardButton("📱 Menu", callback_data="main_menu")],
    ]
    await query.edit_message_text(
        "👋 <b>Welcome to the Group Management Bot!</b>\n\n"
        "I help keep Telegram groups safe, organized, and engaging.\n\n"
        "✅ Moderation (ban, mute, warn, kick)\n"
        "✅ Content locks and anti-flood\n"
        "✅ Custom welcome &amp; rules\n"
        "✅ Group settings &amp; permissions\n"
        "✅ Broadcast to users and groups\n\n"
        "Use the buttons below to get started.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ─── ⚙️ GROUP SETTINGS MODULE ─────────────────────────────────────────────────

async def settitle_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    if not context.args:
        await update.message.reply_text("Usage: /settitle <title>")
        return
    title = " ".join(context.args)
    try:
        await context.bot.set_chat_title(update.effective_chat.id, title)
        await update.message.reply_text(f"✅ Group title updated to: <b>{_esc(title)}</b>", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {_esc(str(e))}", parse_mode="HTML")


async def setdesc_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    if not context.args:
        await update.message.reply_text("Usage: /setdesc <description>")
        return
    desc = " ".join(context.args)
    try:
        await context.bot.set_chat_description(update.effective_chat.id, desc)
        await update.message.reply_text("✅ Group description updated.")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {_esc(str(e))}", parse_mode="HTML")


async def setphoto_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    msg = update.message
    photo = None
    if msg.reply_to_message and msg.reply_to_message.photo:
        photo = msg.reply_to_message.photo[-1]
    elif msg.reply_to_message and msg.reply_to_message.document:
        photo = msg.reply_to_message.document
    if not photo:
        await msg.reply_text("↩️ Reply to a photo to set it as the group profile picture.")
        return
    try:
        file = await context.bot.get_file(photo.file_id)
        await context.bot.set_chat_photo(update.effective_chat.id, file.file_id)
        await msg.reply_text("✅ Group photo updated.")
    except Exception as e:
        await msg.reply_text(f"❌ Failed: {_esc(str(e))}", parse_mode="HTML")


async def delphoto_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    try:
        await context.bot.delete_chat_photo(update.effective_chat.id)
        await update.message.reply_text("✅ Group photo removed.")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {_esc(str(e))}", parse_mode="HTML")


async def slowmode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /slowmode <seconds> (0 to disable)")
        return
    sec = int(context.args[0])
    try:
        await context.bot.set_chat_slow_mode_delay(update.effective_chat.id, sec)
        msg = f"⏱️ Slow mode set to <b>{sec}s</b>." if sec > 0 else "⏱️ Slow mode <b>disabled</b>."
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {_esc(str(e))}", parse_mode="HTML")


async def invitelink_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    try:
        link = await context.bot.export_chat_invite_link(update.effective_chat.id)
        await update.message.reply_text(f"🔗 <b>Invite Link:</b>\n{link}", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {_esc(str(e))}", parse_mode="HTML")


async def revokeinvite_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    try:
        await context.bot.revoke_chat_invite_link(
            update.effective_chat.id,
            await context.bot.export_chat_invite_link(update.effective_chat.id),
        )
        new_link = await context.bot.export_chat_invite_link(update.effective_chat.id)
        await update.message.reply_text(
            f"🔄 Invite link revoked.\n🔗 <b>New link:</b>\n{new_link}", parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {_esc(str(e))}", parse_mode="HTML")


async def _toggle_perm(update, context, perm_name: str, flag: bool):
    """Generic permission toggler."""
    chat_id = update.effective_chat.id
    current = await context.bot.get_chat(chat_id)
    perms = current.permissions or ChatPermissions()
    perms_dict = {
        "can_send_messages": perms.can_send_messages,
        "can_send_media_messages": perms.can_send_media_messages,
        "can_send_other_messages": perms.can_send_other_messages,
        "can_add_web_page_previews": perms.can_add_web_page_previews,
        "can_send_polls": perms.can_send_polls,
    }
    perms_dict[perm_name] = flag
    await context.bot.set_chat_permissions(chat_id, ChatPermissions(**perms_dict))


async def stickers_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    if not context.args or context.args[0] not in ("on", "off"):
        await update.message.reply_text("Usage: /stickers on|off")
        return
    flag = context.args[0] == "on"
    try:
        await _toggle_perm(update, context, "can_send_other_messages", flag)
        state = "enabled" if flag else "disabled"
        await update.message.reply_text(f"🎭 Stickers <b>{state}</b>.", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {_esc(str(e))}", parse_mode="HTML")


async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    if not context.args or context.args[0] not in ("on", "off"):
        await update.message.reply_text("Usage: /media on|off")
        return
    flag = context.args[0] == "on"
    try:
        await _toggle_perm(update, context, "can_send_media_messages", flag)
        state = "enabled" if flag else "disabled"
        await update.message.reply_text(f"🖼️ Media <b>{state}</b>.", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {_esc(str(e))}", parse_mode="HTML")


async def polls_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    if not context.args or context.args[0] not in ("on", "off"):
        await update.message.reply_text("Usage: /polls on|off")
        return
    flag = context.args[0] == "on"
    try:
        await _toggle_perm(update, context, "can_send_polls", flag)
        state = "enabled" if flag else "disabled"
        await update.message.reply_text(f"📊 Polls <b>{state}</b>.", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {_esc(str(e))}", parse_mode="HTML")


async def setperm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    perm_map = {
        "messages": "can_send_messages",
        "media": "can_send_media_messages",
        "stickers": "can_send_other_messages",
        "links": "can_add_web_page_previews",
        "polls": "can_send_polls",
    }
    if len(context.args) < 2 or context.args[0] not in perm_map or context.args[1] not in ("on", "off"):
        await update.message.reply_text(
            f"Usage: /setperm &lt;type&gt; on|off\nTypes: {', '.join(perm_map.keys())}",
            parse_mode="HTML",
        )
        return
    perm_name = perm_map[context.args[0]]
    flag = context.args[1] == "on"
    try:
        await _toggle_perm(update, context, perm_name, flag)
        state = "on" if flag else "off"
        await update.message.reply_text(
            f"✅ Permission <code>{_esc(context.args[0])}</code> set to <b>{state}</b>.",
            parse_mode="HTML",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {_esc(str(e))}", parse_mode="HTML")


# ─── 🛡️ ANTI-FLOOD MODULE ─────────────────────────────────────────────────────

async def antiflood_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    db = _db(context)
    chat_id = update.effective_chat.id
    doc = db["groups"].find_one({"_id": chat_id}) or {}

    args = context.args
    if not args:
        on = doc.get("f_on", False)
        lim = doc.get("f_lim", 5)
        win = doc.get("f_win", 8)
        mut = doc.get("f_mut", 10)
        state = "🟢 ON" if on else "🔴 OFF"
        await update.message.reply_text(
            f"🛡️ <b>Anti-Flood Settings</b>\n\n"
            f"Status: {state}\n"
            f"Limit: <b>{lim}</b> messages\n"
            f"Window: <b>{win}s</b>\n"
            f"Mute duration: <b>{mut} min</b>\n\n"
            "Change: /antiflood on|off [limit] [window_sec] [mute_min]",
            parse_mode="HTML",
        )
        return

    if args[0] not in ("on", "off"):
        await update.message.reply_text("Usage: /antiflood on|off [limit] [window_sec] [mute_min]")
        return

    update_data = {
        "f_on": args[0] == "on",
        "f_lim": int(args[1]) if len(args) > 1 and args[1].isdigit() else doc.get("f_lim", 5),
        "f_win": int(args[2]) if len(args) > 2 and args[2].isdigit() else doc.get("f_win", 8),
        "f_mut": int(args[3]) if len(args) > 3 and args[3].isdigit() else doc.get("f_mut", 10),
    }
    db["groups"].update_one({"_id": chat_id}, {"$set": update_data}, upsert=True)
    state = "🟢 ON" if update_data["f_on"] else "🔴 OFF"
    await update.message.reply_text(
        f"✅ Anti-flood {state}\n"
        f"Limit: <b>{update_data['f_lim']}</b> msgs / <b>{update_data['f_win']}s</b> → mute <b>{update_data['f_mut']} min</b>",
        parse_mode="HTML",
    )


async def flood_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Passive flood checker — runs on every message (group=1)."""
    db = _db(context)
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user or chat.type == "private" or user.is_bot:
        return
    if await _is_admin(update, context):
        return

    doc = db["groups"].find_one({"_id": chat.id}) if db else None
    if not doc or not doc.get("f_on", False):
        return

    lim = doc.get("f_lim", 5)
    win = doc.get("f_win", 8)
    mut = doc.get("f_mut", 10)

    now = time.time()
    timestamps = _flood_cache[chat.id][user.id]
    timestamps.append(now)
    # Keep only within window
    _flood_cache[chat.id][user.id] = [t for t in timestamps if now - t <= win]

    if len(_flood_cache[chat.id][user.id]) > lim:
        _flood_cache[chat.id][user.id] = []
        until = datetime.now() + timedelta(minutes=mut)
        try:
            await context.bot.restrict_chat_member(
                chat.id, user.id,
                ChatPermissions(can_send_messages=False),
                until_date=until,
            )
            await update.message.reply_text(
                f"🚫 <b>{_esc(user.full_name)}</b> muted for {mut} min (flood detected).",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning("Flood mute error: %s", e)


# ─── ℹ️ INFO MODULE ───────────────────────────────────────────────────────────

async def id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lines = [f"👤 <b>Your ID:</b> <code>{user.id}</code>"]
    if chat.type != "private":
        lines.append(f"💬 <b>Group ID:</b> <code>{chat.id}</code>")
    if update.message.reply_to_message:
        t = update.message.reply_to_message.from_user
        lines.append(f"↩️ <b>Replied user ID:</b> <code>{t.id}</code>  ({_esc(t.full_name)})")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target, err = await _get_target(update, context)
    if err and not update.message.reply_to_message and not context.args:
        target = update.effective_user
    elif err:
        await update.message.reply_text(err, parse_mode="HTML")
        return

    db = _db(context)
    doc = db["users"].find_one({"_id": target.id}) if db else {}

    uname = f"@{_esc(target.username)}" if target.username else "N/A"
    warn_count = (doc or {}).get("w_cnt", 0)
    last_seen_ts = (doc or {}).get("last")
    last_seen = datetime.fromtimestamp(last_seen_ts).strftime("%Y-%m-%d %H:%M") if last_seen_ts else "Unknown"

    lines = [
        f"ℹ️ <b>User Info</b>",
        f"Name: <b>{_esc(target.full_name)}</b>",
        f"Username: {uname}",
        f"ID: <code>{target.id}</code>",
        f"Warnings: <b>{warn_count}</b>/3",
        f"Last seen: {last_seen}",
    ]
    if target.is_bot:
        lines.append("Type: 🤖 Bot")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


# ─── 🧹 AUTO CLEANUP MODULE ───────────────────────────────────────────────────

async def cleandeleted_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    db = _db(context)
    chat_id = update.effective_chat.id
    kicked = 0
    failed = 0
    # Iterate tracked users and check if they're deleted accounts
    tracked_users = list(db["users"].find({}, {"_id": 1}))
    msg = await update.message.reply_text(
        f"🔍 Checking {len(tracked_users)} tracked users...", parse_mode="HTML"
    )
    for doc in tracked_users:
        try:
            member = await context.bot.get_chat_member(chat_id, doc["_id"])
            user = member.user
            if user.is_bot:
                continue
            # Deleted accounts have no first_name and username is None
            if not user.first_name and not user.username:
                await context.bot.ban_chat_member(chat_id, doc["_id"])
                await context.bot.unban_chat_member(chat_id, doc["_id"])  # Soft kick
                kicked += 1
        except Exception:
            failed += 1
    await msg.edit_text(
        f"🧹 <b>Clean Deleted</b>\n\n✅ Removed: {kicked}\n⚠️ Skipped/errors: {failed}",
        parse_mode="HTML",
    )


async def cleaninactive_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    days = 30
    if context.args and context.args[0].isdigit():
        days = int(context.args[0])
    db = _db(context)
    chat_id = update.effective_chat.id
    cutoff = int(time.time()) - (days * 86400)
    inactive_users = list(db["users"].find({"last": {"$lt": cutoff}}, {"_id": 1}))
    kicked = 0
    msg = await update.message.reply_text(
        f"🔍 Found {len(inactive_users)} users inactive for {days}+ days..."
    )
    for doc in inactive_users:
        try:
            await context.bot.get_chat_member(chat_id, doc["_id"])
            await context.bot.ban_chat_member(chat_id, doc["_id"])
            await context.bot.unban_chat_member(chat_id, doc["_id"])
            kicked += 1
        except Exception:
            pass
    await msg.edit_text(
        f"🧹 <b>Clean Inactive ({days}d)</b>\n\n✅ Removed: {kicked}",
        parse_mode="HTML",
    )


async def autoclean_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    if not context.args or context.args[0] not in ("on", "off"):
        await update.message.reply_text("Usage: /autoclean on|off [days]")
        return
    db = _db(context)
    flag = context.args[0] == "on"
    days = int(context.args[1]) if len(context.args) > 1 and context.args[1].isdigit() else 30
    db["groups"].update_one(
        {"_id": update.effective_chat.id},
        {"$set": {"ac_on": flag, "ac_days": days}},
        upsert=True,
    )
    state = "🟢 ON" if flag else "🔴 OFF"
    await update.message.reply_text(
        f"🧹 Auto-clean {state} (inactive for <b>{days}</b> days).",
        parse_mode="HTML",
    )


async def autokickdeleted_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    if not context.args or context.args[0] not in ("on", "off"):
        await update.message.reply_text("Usage: /autokickdeleted on|off")
        return
    db = _db(context)
    flag = context.args[0] == "on"
    db["groups"].update_one(
        {"_id": update.effective_chat.id},
        {"$set": {"akd_on": flag}},
        upsert=True,
    )
    state = "🟢 ON" if flag else "🔴 OFF"
    await update.message.reply_text(
        f"🗑️ Auto-kick deleted accounts {state}.",
        parse_mode="HTML",
    )


# ─── 🔒 CONTENT LOCK MODULE ───────────────────────────────────────────────────

_LOCK_KEYS = {
    "messages": "l_msg",
    "media": "l_med",
    "stickers": "l_stk",
    "gifs": "l_gif",
    "polls": "l_pol",
    "links": "l_lnk",
}


async def lock_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    if not context.args or context.args[0] not in _LOCK_KEYS:
        await update.message.reply_text(
            f"Usage: /lock &lt;type&gt;\nTypes: {', '.join(_LOCK_KEYS.keys())}",
            parse_mode="HTML",
        )
        return
    key = _LOCK_KEYS[context.args[0]]
    _db(context)["groups"].update_one(
        {"_id": update.effective_chat.id}, {"$set": {key: True}}, upsert=True
    )
    await update.message.reply_text(
        f"🔒 <b>{_esc(context.args[0])}</b> locked.", parse_mode="HTML"
    )


async def unlock_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    if not context.args or context.args[0] not in _LOCK_KEYS:
        await update.message.reply_text(
            f"Usage: /unlock &lt;type&gt;\nTypes: {', '.join(_LOCK_KEYS.keys())}",
            parse_mode="HTML",
        )
        return
    key = _LOCK_KEYS[context.args[0]]
    _db(context)["groups"].update_one(
        {"_id": update.effective_chat.id}, {"$set": {key: False}}, upsert=True
    )
    await update.message.reply_text(
        f"🔓 <b>{_esc(context.args[0])}</b> unlocked.", parse_mode="HTML"
    )


async def locklist_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = _db(context)
    doc = db["groups"].find_one({"_id": update.effective_chat.id}) or {}
    lines = ["🔒 <b>Content Lock Status</b>\n"]
    for lock_name, key in _LOCK_KEYS.items():
        status = "🔒 Locked" if doc.get(key) else "🔓 Unlocked"
        lines.append(f"{lock_name}: {status}")
    ro = "🔒 ON" if doc.get("ro") else "🔓 OFF"
    lines.append(f"\nRead-only mode: {ro}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def ro_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    try:
        await context.bot.set_chat_permissions(
            update.effective_chat.id, ChatPermissions(can_send_messages=False)
        )
        _db(context)["groups"].update_one(
            {"_id": update.effective_chat.id}, {"$set": {"ro": True}}, upsert=True
        )
        await update.message.reply_text("🔇 Read-only mode <b>enabled</b>. Only admins can message.", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {_esc(str(e))}", parse_mode="HTML")


async def unro_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    try:
        await context.bot.set_chat_permissions(
            update.effective_chat.id,
            ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            ),
        )
        _db(context)["groups"].update_one(
            {"_id": update.effective_chat.id}, {"$set": {"ro": False}}, upsert=True
        )
        await update.message.reply_text("🔊 Read-only mode <b>disabled</b>.", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {_esc(str(e))}", parse_mode="HTML")


async def lock_enforcer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-delete messages that violate active locks (group=0, before other handlers)."""
    db = _db(context)
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message
    if not chat or not user or chat.type == "private" or user.is_bot:
        return
    if await _is_admin(update, context):
        return

    doc = db["groups"].find_one({"_id": chat.id}) if db else None
    if not doc:
        return

    import re
    URL_RE = re.compile(r"(https?://|t\.me/|www\.)", re.IGNORECASE)

    should_delete = False
    if doc.get("l_msg") and msg.text and not msg.text.startswith("/"):
        should_delete = True
    elif doc.get("l_med") and (msg.photo or msg.video or msg.document or msg.audio or msg.voice):
        should_delete = True
    elif doc.get("l_stk") and msg.sticker:
        should_delete = True
    elif doc.get("l_gif") and msg.animation:
        should_delete = True
    elif doc.get("l_pol") and msg.poll:
        should_delete = True
    elif doc.get("l_lnk") and msg.text and URL_RE.search(msg.text):
        should_delete = True

    if should_delete:
        try:
            await msg.delete()
        except Exception as e:
            logger.warning("lock_enforcer delete error: %s", e)


# ─── 👋 WELCOME & RULES MODULE ────────────────────────────────────────────────

async def setwelcome_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    if not context.args:
        await update.message.reply_text("Usage: /setwelcome <text> (use {name} for the member's name)")
        return
    text = " ".join(context.args)
    _db(context)["groups"].update_one(
        {"_id": update.effective_chat.id},
        {"$set": {"wlcm": text, "wlcm_on": True, "title": update.effective_chat.title or ""}},
        upsert=True,
    )
    await update.message.reply_text("✅ Welcome message saved.")


async def getwelcome_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = _db(context)["groups"].find_one({"_id": update.effective_chat.id}) or {}
    msg = doc.get("wlcm")
    on = doc.get("wlcm_on", True)
    if msg:
        state = "🟢 ON" if on else "🔴 OFF"
        await update.message.reply_text(
            f"👋 <b>Current welcome message</b> [{state}]:\n\n{_esc(msg)}",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text("No custom welcome message set.")


async def welcome_toggle_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    if not context.args or context.args[0] not in ("on", "off"):
        await update.message.reply_text("Usage: /welcome on|off")
        return
    flag = context.args[0] == "on"
    _db(context)["groups"].update_one(
        {"_id": update.effective_chat.id}, {"$set": {"wlcm_on": flag}}, upsert=True
    )
    state = "🟢 ON" if flag else "🔴 OFF"
    await update.message.reply_text(f"👋 Welcome messages {state}.", parse_mode="HTML")


async def rules_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = _db(context)["groups"].find_one({"_id": update.effective_chat.id}) or {}
    rules = doc.get("rules")
    if rules:
        await update.message.reply_text(
            f"📜 <b>Group Rules</b>\n\n{_esc(rules)}", parse_mode="HTML"
        )
    else:
        await update.message.reply_text("No rules set for this group. Use /setrules to add some.")


async def setrules_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    if not context.args:
        await update.message.reply_text("Usage: /setrules <rules text>")
        return
    text = " ".join(context.args)
    _db(context)["groups"].update_one(
        {"_id": update.effective_chat.id}, {"$set": {"rules": text}}, upsert=True
    )
    await update.message.reply_text("✅ Rules saved.")


async def clearrules_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    _db(context)["groups"].update_one(
        {"_id": update.effective_chat.id}, {"$unset": {"rules": ""}}, upsert=True
    )
    await update.message.reply_text("✅ Rules cleared.")


async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = _db(context)
    chat = update.effective_chat
    if db:
        _track_group(chat, db)
    group_doc = db["groups"].find_one({"_id": chat.id}) if db else None

    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            if db:
                _track_group(chat, db)
            await update.message.reply_text(
                f"👋 Thanks for adding me to <b>{_esc(chat.title)}</b>!\n"
                "Give me admin rights to enable all features.",
                parse_mode="HTML",
            )
            continue
        if member.is_bot:
            continue
        if db:
            _track_user(member, db)

        if group_doc and group_doc.get("wlcm_on", True):
            custom = group_doc.get("wlcm")
            if custom:
                text = custom.replace("{name}", member.full_name)
                await update.message.reply_text(text)
            else:
                await update.message.reply_text(
                    f"👋 Welcome to the group, <b>{_esc(member.full_name)}</b>! Please read the /rules.",
                    parse_mode="HTML",
                )


# ─── 🛡️ MODERATION ENGINE ─────────────────────────────────────────────────────

async def ban_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    target, err = await _get_target(update, context)
    if err:
        await update.message.reply_text(err, parse_mode="HTML")
        return
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await update.message.reply_text(
            f"🔨 <b>{_esc(target.full_name)}</b> has been banned.", parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ban failed: {_esc(str(e))}", parse_mode="HTML")


async def unban_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    target, err = await _get_target(update, context)
    if err:
        await update.message.reply_text(err, parse_mode="HTML")
        return
    try:
        await context.bot.unban_chat_member(update.effective_chat.id, target.id, only_if_banned=True)
        await update.message.reply_text(
            f"✅ <b>{_esc(target.full_name)}</b> has been unbanned.", parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Unban failed: {_esc(str(e))}", parse_mode="HTML")


async def kick_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    target, err = await _get_target(update, context)
    if err:
        await update.message.reply_text(err, parse_mode="HTML")
        return
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await context.bot.unban_chat_member(update.effective_chat.id, target.id)
        await update.message.reply_text(
            f"👢 <b>{_esc(target.full_name)}</b> has been kicked.", parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Kick failed: {_esc(str(e))}", parse_mode="HTML")


def _parse_duration(raw: str) -> int | None:
    """Parse duration string like 1m, 2h, 3d into seconds."""
    if not raw:
        return None
    units = {"m": 60, "h": 3600, "d": 86400}
    unit = raw[-1].lower()
    if unit in units and raw[:-1].isdigit():
        return int(raw[:-1]) * units[unit]
    return None


async def mute_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    target, err = await _get_target(update, context)
    if err:
        await update.message.reply_text(err, parse_mode="HTML")
        return

    # Duration: last arg if it looks like 1m/1h/1d
    until = None
    duration_str = ""
    remaining_args = list(context.args or [])
    if remaining_args:
        dur_secs = _parse_duration(remaining_args[-1])
        if dur_secs:
            until = datetime.now() + timedelta(seconds=dur_secs)
            duration_str = f" for {_esc(remaining_args[-1])}"

    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id, target.id,
            ChatPermissions(can_send_messages=False),
            until_date=until,
        )
        await update.message.reply_text(
            f"🔇 <b>{_esc(target.full_name)}</b> muted{duration_str}.", parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Mute failed: {_esc(str(e))}", parse_mode="HTML")


async def unmute_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    target, err = await _get_target(update, context)
    if err:
        await update.message.reply_text(err, parse_mode="HTML")
        return
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
            f"🔊 <b>{_esc(target.full_name)}</b> unmuted.", parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Unmute failed: {_esc(str(e))}", parse_mode="HTML")


async def warn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    target, err = await _get_target(update, context)
    if err:
        await update.message.reply_text(err, parse_mode="HTML")
        return
    db = _db(context)
    reason_args = list(context.args or [])
    if update.message.reply_to_message and reason_args and reason_args[0].startswith("@"):
        reason_args = reason_args[1:]
    reason = " ".join(reason_args) if reason_args else "No reason provided"

    doc = db["users"].find_one_and_update(
        {"_id": target.id},
        {"$inc": {"w_cnt": 1}},
        upsert=True,
        return_document=True,
    )
    warn_count = (doc or {}).get("w_cnt", 1)

    if warn_count >= 3:
        try:
            await context.bot.ban_chat_member(update.effective_chat.id, target.id)
            db["users"].update_one({"_id": target.id}, {"$set": {"w_cnt": 0}})
            await update.message.reply_text(
                f"🔨 <b>{_esc(target.full_name)}</b> reached 3 warnings and has been auto-banned.",
                parse_mode="HTML",
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Auto-ban failed: {_esc(str(e))}", parse_mode="HTML")
    else:
        await update.message.reply_text(
            f"⚠️ <b>{_esc(target.full_name)}</b> — warning {warn_count}/3\nReason: {_esc(reason)}",
            parse_mode="HTML",
        )


async def unwarn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    target, err = await _get_target(update, context)
    if err:
        await update.message.reply_text(err, parse_mode="HTML")
        return
    db = _db(context)
    doc = db["users"].find_one({"_id": target.id}) or {}
    current = doc.get("w_cnt", 0)
    if current == 0:
        await update.message.reply_text(
            f"<b>{_esc(target.full_name)}</b> has no warnings.", parse_mode="HTML"
        )
        return
    db["users"].update_one({"_id": target.id}, {"$inc": {"w_cnt": -1}})
    await update.message.reply_text(
        f"✅ 1 warning removed from <b>{_esc(target.full_name)}</b>. Warnings: {current - 1}/3",
        parse_mode="HTML",
    )


async def warns_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target, err = await _get_target(update, context)
    if err:
        target = update.effective_user
    db = _db(context)
    doc = db["users"].find_one({"_id": target.id}) or {}
    count = doc.get("w_cnt", 0)
    await update.message.reply_text(
        f"⚠️ <b>{_esc(target.full_name)}</b> has <b>{count}/3</b> warnings.", parse_mode="HTML"
    )


async def resetwarn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    target, err = await _get_target(update, context)
    if err:
        await update.message.reply_text(err, parse_mode="HTML")
        return
    _db(context)["users"].update_one({"_id": target.id}, {"$set": {"w_cnt": 0}})
    await update.message.reply_text(
        f"✅ Warnings reset for <b>{_esc(target.full_name)}</b>.", parse_mode="HTML"
    )


async def clearwarns_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alias for resetwarn."""
    await resetwarn_handler(update, context)


async def promote_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    target, err = await _get_target(update, context)
    if err:
        await update.message.reply_text(err, parse_mode="HTML")
        return
    try:
        await context.bot.promote_chat_member(
            update.effective_chat.id, target.id,
            can_change_info=True,
            can_delete_messages=True,
            can_restrict_members=True,
            can_invite_users=True,
            can_pin_messages=True,
            can_manage_chat=True,
        )
        await update.message.reply_text(
            f"⬆️ <b>{_esc(target.full_name)}</b> promoted to admin.", parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Promote failed: {_esc(str(e))}", parse_mode="HTML")


async def demote_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    target, err = await _get_target(update, context)
    if err:
        await update.message.reply_text(err, parse_mode="HTML")
        return
    try:
        await context.bot.promote_chat_member(
            update.effective_chat.id, target.id,
            can_change_info=False,
            can_delete_messages=False,
            can_restrict_members=False,
            can_invite_users=False,
            can_pin_messages=False,
            can_manage_chat=False,
        )
        await update.message.reply_text(
            f"⬇️ <b>{_esc(target.full_name)}</b> demoted.", parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Demote failed: {_esc(str(e))}", parse_mode="HTML")


async def title_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    target, err = await _get_target(update, context)
    if err:
        await update.message.reply_text(err, parse_mode="HTML")
        return
    # Title is everything after the username/reply arg
    args = list(context.args or [])
    if args and (args[0].startswith("@") or args[0].isdigit()):
        args = args[1:]
    if not args:
        await update.message.reply_text("Usage: /title @user <custom title>")
        return
    custom_title = " ".join(args)[:16]  # Telegram limit: 16 chars
    try:
        await context.bot.set_chat_administrator_custom_title(
            update.effective_chat.id, target.id, custom_title
        )
        await update.message.reply_text(
            f"🏷️ <b>{_esc(target.full_name)}</b>'s title set to: <i>{_esc(custom_title)}</i>",
            parse_mode="HTML",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {_esc(str(e))}", parse_mode="HTML")


async def pin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("↩️ Reply to a message to pin it.")
        return
    try:
        await context.bot.pin_chat_message(
            update.effective_chat.id, update.message.reply_to_message.message_id
        )
        await update.message.reply_text("📌 Message pinned.")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {_esc(str(e))}", parse_mode="HTML")


async def unpin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    try:
        if update.message.reply_to_message:
            await context.bot.unpin_chat_message(
                update.effective_chat.id, update.message.reply_to_message.message_id
            )
        else:
            await context.bot.unpin_chat_message(update.effective_chat.id)
        await update.message.reply_text("📌 Message unpinned.")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {_esc(str(e))}", parse_mode="HTML")


async def unpinall_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    try:
        await context.bot.unpin_all_chat_messages(update.effective_chat.id)
        await update.message.reply_text("📌 All messages unpinned.")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {_esc(str(e))}", parse_mode="HTML")


async def del_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("↩️ Reply to a message to delete it.")
        return
    try:
        await update.message.reply_to_message.delete()
        await update.message.delete()
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {_esc(str(e))}", parse_mode="HTML")


async def purge_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_admin(update, context):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("↩️ Reply to the first message you want to purge from.")
        return
    start_id = update.message.reply_to_message.message_id
    end_id = update.message.message_id
    max_delete = int(context.args[0]) if context.args and context.args[0].isdigit() else end_id - start_id + 1
    deleted = 0
    for msg_id in range(start_id, min(end_id + 1, start_id + max_delete + 1)):
        try:
            await context.bot.delete_message(update.effective_chat.id, msg_id)
            deleted += 1
        except Exception:
            pass
    status = await update.message.reply_text(f"🗑️ Purged <b>{deleted}</b> messages.", parse_mode="HTML")
    import asyncio
    await asyncio.sleep(3)
    try:
        await status.delete()
    except Exception:
        pass


async def report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("↩️ Reply to the message you want to report.")
        return
    chat = update.effective_chat
    reporter = update.effective_user
    reported = update.message.reply_to_message.from_user
    reason = " ".join(context.args) if context.args else "No reason given"

    try:
        admins = await context.bot.get_chat_administrators(chat.id)
    except Exception:
        admins = []

    report_text = (
        f"🚨 <b>Report in {_esc(chat.title)}</b>\n\n"
        f"Reporter: <a href='tg://user?id={reporter.id}'>{_esc(reporter.full_name)}</a>\n"
        f"Reported: <a href='tg://user?id={reported.id}'>{_esc(reported.full_name)}</a>\n"
        f"Reason: {_esc(reason)}"
    )
    for admin in admins:
        if admin.user.is_bot:
            continue
        try:
            await context.bot.send_message(admin.user.id, report_text, parse_mode="HTML")
        except Exception:
            pass
    await update.message.reply_text("✅ Report sent to all admins.", parse_mode="HTML")


# ─── 📢 BROADCAST ─────────────────────────────────────────────────────────────

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
        f"📢 <b>Broadcast to {label}</b>\n\nSend your message now (text, photo, or video):",
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


# ─── 👑 OWNER TOOLS ───────────────────────────────────────────────────────────

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
        text += "\n\n<i>Showing first 50.</i>"
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
        lines.append(f"{i}. <b>{title}</b> — <code>{g['_id']}</code>")
    text = "🏘️ <b>Managed Groups</b>\n\n" + "\n".join(lines)
    if len(groups) == 50:
        text += "\n\n<i>Showing first 50.</i>"
    await update.message.reply_text(text, parse_mode="HTML")


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
    total_users = db["users"].count_documents({}) if db else 0
    total_groups = db["groups"].count_documents({}) if db else 0
    await update.message.reply_text(
        f"📊 <b>Statistics</b>\n\n"
        f"👥 Members in this group: <b>{member_count}</b>\n"
        f"📝 Total tracked users: <b>{total_users}</b>\n"
        f"🏘️ Total managed groups: <b>{total_groups}</b>\n"
        f"⚠️ Users with warnings: <b>{warned_users}</b>",
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

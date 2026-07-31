import logging
from telegram import Update
from telegram.ext import ContextTypes
from database.users_db import get_top_referrers, get_user

logger = logging.getLogger(__name__)


async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays user's referral dashboard and generates a ready-to-share invite card."""
    user_id = update.effective_user.id
    user_data = get_user(user_id)

    # Safely get bot username
    try:
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
    except Exception as e:
        logger.error(f"Error fetching bot username: {e}")
        bot_username = context.bot.username or "StoreBot"

    # Unpack user details safely based on DB Schema:
    # (telegram_id, referred_by, points, total_referrals, successful_purchases)
    points = user_data[2] if user_data and len(user_data) > 2 else 0
    total_referrals = user_data[3] if user_data and len(user_data) > 3 else 0
    successful_purchases = user_data[4] if user_data and len(user_data) > 4 else 0

    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    # 1. Main Dashboard Message for the User
    dashboard_text = (
        "🎁 REFERRAL & REWARDS DASHBOARD\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Points Balance: {points} Points\n"
        f"👥 Total Invited Users: {total_referrals}\n"
        f"🛍️ Completed Purchases: {successful_purchases}\n\n"
        "🔗 Your Unique Referral Link:\n"
        f"{referral_link}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 Copy and forward the message below to invite your friends!"
    )

    # 2. Forwardable Invite Card (Ready to share with friends)
    share_card = (
        "🛍️ Join our exclusive Store Bot!\n\n"
        "Discover amazing products and earn instant reward points on your purchases.\n\n"
        f"👇 Tap the link to start:\n{referral_link}"
    )

    # Send both messages cleanly
    await update.message.reply_text(dashboard_text)
    await update.message.reply_text(share_card)


async def show_referral_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback handler to display referral/profile info when triggered from inline buttons."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user_data = get_user(user_id)

    try:
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
    except Exception as e:
        logger.error(f"Error fetching bot username: {e}")
        bot_username = context.bot.username or "StoreBot"

    points = user_data[2] if user_data and len(user_data) > 2 else 0
    total_referrals = user_data[3] if user_data and len(user_data) > 3 else 0
    successful_purchases = user_data[4] if user_data and len(user_data) > 4 else 0

    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    dashboard_text = (
        "👤 USER PROFILE & REFERRAL INFO\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Points Balance: {points} Points\n"
        f"👥 Total Invited Users: {total_referrals}\n"
        f"🛍️ Completed Purchases: {successful_purchases}\n\n"
        "🔗 Your Referral Link:\n"
        f"{referral_link}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 Invite friends to earn more reward points!"
    )

    if query.message:
        try:
            await query.edit_message_text(dashboard_text)
        except Exception:
            await query.message.reply_text(dashboard_text)
    else:
        await context.bot.send_message(chat_id=user_id, text=dashboard_text)


async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays top 10 referrers leaderboard."""
    top_users = get_top_referrers(10)

    if not top_users:
        await update.message.reply_text("ℹ️ No referral rankings available yet.")
        return

    text = (
        "🏆 TOP REFERRERS LEADERBOARD\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    medals = ["🥇", "🥈", "🥉"]

    for idx, (name, count, points) in enumerate(top_users, start=1):
        badge = medals[idx - 1] if idx <= 3 else f"{idx}."
        display_name = name if name else "User"
        text += f"{badge} {display_name} ── {count} Invites ({points} pts)\n"

    text += (
        "\n━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 Share your referral link to reach the top 10!"
    )
    await update.message.reply_text(text)

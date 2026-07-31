import logging
from telegram import Update
from telegram.ext import ContextTypes
from database.users_db import get_user

logger = logging.getLogger(__name__)


async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays user's referral link, points balance, and referral statistics"""
    user_id = update.effective_user.id
    user_data = get_user(user_id)

    try:
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
    except Exception as e:
        logger.error(f"Error fetching bot username: {e}")
        bot_username = "YourBotUsername"

    # Unpack user details safely from the updated database schema
    # Tuple format: (telegram_id, referred_by, points, total_referrals, successful_purchases)
    points = user_data[2] if user_data else 0
    total_referrals = user_data[3] if user_data else 0
    successful_purchases = user_data[4] if user_data else 0

    ref_link = f"https://t.me/{bot_username}?start={user_id}"

    text = (
        f"🎁 Invite & Earn Program\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Points Balance: {points} Points\n"
        f"👥 Total Invited Users: {total_referrals}\n"
        f"🛍️ Completed Purchases by Invites: {successful_purchases}\n\n"
        f"🔗 Your Unique Referral Link:\n"
        f"{ref_link}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 Share this link with your friends to earn reward points!"
    )

    await update.message.reply_text(text)

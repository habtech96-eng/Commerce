import logging
from telegram import Update
from telegram.ext import ContextTypes
from database.users_db import get_user

logger = logging.getLogger(__name__)


async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays user's referral link and reward points balance"""
    user_id = update.effective_user.id
    user_data = get_user(user_id)

    try:
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
    except Exception as e:
        logger.error(f"Error fetching bot username: {e}")
        bot_username = "YourBotUsername"

    points = user_data[2] if user_data else 0
    ref_link = f"https://t.me/{bot_username}?start={user_id}"

    text = (
        f"🎁 **Invite & Earn Program!**\n\n"
        f"💰 Your Points Balance: **{points} Points**\n\n"
        f"🔗 **Your Unique Referral Link:**\n"
        f"`{ref_link}`\n\n"
        f"💡 Share this link with your friends. You will earn **+10 Points** for every user who joins!"
    )

    await update.message.reply_text(text, parse_mode="Markdown")

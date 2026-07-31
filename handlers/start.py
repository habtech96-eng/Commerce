import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_user_stats
from database.users_db import get_user, add_user, add_referral_points

logger = logging.getLogger(__name__)


# ----- Start Command with `ref_` Referral Link Support -----
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    referrer_id = None

    # Parse referral link parameters (e.g., /start ref_123456 or /start 123456)
    if context.args:
        arg = context.args[0]
        if arg.startswith("ref_"):
            try:
                possible_referrer = int(arg.split("_")[1])
                if possible_referrer != user_id:
                    referrer_id = possible_referrer
            except (ValueError, IndexError):
                referrer_id = None
        elif arg.isdigit():
            possible_referrer = int(arg)
            if possible_referrer != user_id:
                referrer_id = possible_referrer

    # Check if user exists in database
    existing_user = get_user(user_id)
    is_new_user = existing_user is None

    if is_new_user:
        # Register user in database
        add_user(user_id, referrer_id)

        # Award point to referrer if a new user joined via their link
        if referrer_id:
            add_referral_points(referrer_id, points=1)
            try:
                notify_text = (
                    "🎉 New Referral Notification!\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"User @{username} joined using your invite link!\n"
                    "⭐ You earned +1 reward point."
                )
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text=notify_text
                )
            except Exception as e:
                logger.error(f"Failed to send referral notification to {referrer_id}: {e}")

    # Main Inline Keyboard menu
    keyboard = [
        [InlineKeyboardButton("🛍️ View Products", callback_data="open_catalog")],
        [InlineKeyboardButton("🎁 Invite & Earn", callback_data="show_referral")],
        [InlineKeyboardButton("👤 Profile & Points", callback_data="show_profile")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        f"Hello {update.effective_user.first_name}! 👋\n\n"
        "Welcome to Ethio Shoe Store bot! 👟\n"
        "Browse products and place your orders easily.\n\n"
        "💡 Invite friends using your referral link to earn discount points!"
    )

    await update.message.reply_text(welcome_text, reply_markup=reply_markup)


# ----- Callback Query for Referral Info -----
async def show_referral_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    bot_info = await context.bot.get_me()

    # Generate user referral link
    referral_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    # Fetch user stats from database
    stats = get_user_stats(user_id) if callable(get_user_stats) else {}
    ref_count = stats.get("referrals_count", 0) if isinstance(stats, dict) else 0
    points = stats.get("points", 0) if isinstance(stats, dict) else 0

    text = (
        "🎁 Your Referral Program\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔗 Your Invite Link:\n"
        f"{referral_link}\n\n"
        f"👥 Total Invited Friends: {ref_count}\n"
        f"⭐ Total Points Earned: {points}\n\n"
        "Share this link with your friends to earn points when they join!"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")]
    ]

    await query.answer()
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

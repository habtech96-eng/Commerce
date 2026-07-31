from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import register_user, add_referral_points, get_user_stats

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    referrer_id = None

    # Parse referral link parameters (e.g., /start ref_123456)
    args = command.args
    if args and args.startswith("ref_"):
        try:
            possible_referrer = int(args.split("_")[1])
            if possible_referrer != user_id:  # Prevent self-referral
                referrer_id = possible_referrer
        except ValueError:
            referrer_id = None

    # Register user in database (returns True if new user)
    is_new_user = await register_user(user_id=user_id, username=username, referred_by=referrer_id)

    # Award point to referrer if a new user joined via their link
    if is_new_user and referrer_id:
        await add_referral_points(referrer_id, points=1)
        try:
            await message.bot.send_message(
                chat_id=referrer_id,
                text=f"🎉 <b>New Referral!</b>\n\nUser @{username} joined using your invite link! You earned 1 point."
            )
        except Exception as e:
            print(f"Failed to send referral notification: {e}")

    # Main keyboard menu
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍️ View Products", callback_data="view_products")],
        [InlineKeyboardButton(text="🎁 Invite & Earn", callback_data="show_referral")],
        [InlineKeyboardButton(text="👤 Profile & Points", callback_data="show_profile")]
    ])

    welcome_text = (
        f"Hello {message.from_user.first_name}! 👋\n\n"
        f"Welcome to <b>Ethio Shoe Store</b> bot! 👟\n"
        f"Browse products and place your orders easily.\n\n"
        f"💡 Invite friends using your referral link to earn discount points!"
    )

    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "show_referral")
async def show_referral_info(callback: CallbackQuery):
    user_id = callback.from_user.id
    bot_info = await callback.bot.get_me()

    # Generate user referral link
    referral_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    # Fetch user stats from database
    stats = await get_user_stats(user_id)
    ref_count = stats.get("referrals_count", 0)
    points = stats.get("points", 0)

    text = (
        f"🎁 <b>Your Referral Program</b>\n\n"
        f"🔗 <b>Your Invite Link:</b>\n<code>{referral_link}</code>\n\n"
        f"👥 Total Invited Friends: <b>{ref_count}</b>\n"
        f"⭐ Total Points Earned: <b>{points}</b>\n\n"
        f"<i>Share this link with your friends to earn points when they join!</i>"
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="back_to_main")]
        ])
    )
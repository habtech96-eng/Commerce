from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import get_user_stats, create_multi_item_order

router = Router()


@router.callback_query(F.data == "checkout")
async def process_checkout_prompt(callback: CallbackQuery):
    user_id = callback.from_user.id
    stats = await get_user_stats(user_id)
    available_points = stats.get("points", 0)

    # 1 Point = 10 ETB Discount
    discount_value = available_points * 10

    buttons = []
    if available_points > 0:
        buttons.append([
            InlineKeyboardButton(
                text=f"🎁 Apply {available_points} Points (-{discount_value} ETB)",
                callback_data="checkout_use_points"
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="💳 Pay Full Amount (No Discount)", callback_data="checkout_no_points")
    ])

    text = (
        f"🛒 <b>Checkout Confirmation</b>\n\n"
        f"⭐ Available Points: <b>{available_points}</b> (Worth {discount_value} ETB)\n"
        f"Would you like to apply your referral points to this order?"
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.in_({"checkout_use_points", "checkout_no_points"}))
async def finalize_order(callback: CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or callback.from_user.first_name
    use_points = (callback.data == "checkout_use_points")

    # Fetch user phone number from session state or db (using placeholder here)
    phone_number = "+251900000000"

    result, status = create_multi_item_order(
        user_id=user_id,
        user_name=username,
        phone_number=phone_number,
        use_points=use_points
    )

    if not result:
        await callback.answer(f"Order failed: {status}", show_alert=True)
        return

    text = (
        f"✅ <b>Order Placed Successfully!</b>\n\n"
        f"🆔 Order ID: <code>#{result['order_id']}</code>\n"
        f"🚚 Delivery Fee: <b>{result['delivery_fee']} ETB</b>\n"
        f"🎁 Discount Applied: <b>-{result['discount']} ETB</b> ({result['points_used']} points)\n"
        f"💰 <b>Total Paid: {result['grand_total']} ETB</b>\n\n"
        f"Thank you for shopping with Ethio Shoe Store!"
    )

    await callback.message.edit_text(text, parse_mode="HTML")
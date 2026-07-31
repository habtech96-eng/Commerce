import logging
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes, ConversationHandler
from database.db import get_user_cart, create_multi_item_order
from database.users_db import record_successful_purchase
from handlers.user import build_main_menu, get_category_icon

# Import ADMIN_IDS safely
try:
    from config import ADMIN_IDS
except ImportError:
    ADMIN_IDS = []

logger = logging.getLogger(__name__)

# Conversation State Constant
WAITING_FOR_PHONE = 1


async def start_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggers checkout phone number request"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    cart_items = get_user_cart(user_id)

    if not cart_items:
        await query.edit_message_text(
            "Your cart is empty. Please add items before checking out."
        )
        return ConversationHandler.END

    phone_keyboard = [
        [KeyboardButton("📱 Share Phone Number", request_contact=True)]
    ]
    reply_markup = ReplyKeyboardMarkup(
        phone_keyboard, resize_keyboard=True, one_time_keyboard=True
    )

    await query.message.reply_text(
        "📱 Checkout Process (Step 1/2):\n\n"
        "To place your order, please tap the button below to share your phone number or type it manually:",
        reply_markup=reply_markup,
    )
    return WAITING_FOR_PHONE


async def process_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finalizes order placement and notifies administrators"""
    user = update.effective_user

    phone_number = (
        update.message.contact.phone_number
        if update.message.contact
        else update.message.text
    )
    user_name = user.full_name or user.username or "Customer"

    order_result, msg = create_multi_item_order(
        user_id=user.id,
        user_name=user_name,
        phone_number=phone_number,
    )

    if not order_result:
        await update.message.reply_text(
            f"❌ Order Failed: {msg}",
            reply_markup=build_main_menu(user.id),
        )
        return ConversationHandler.END

    order_id, grand_total, items, delivery_fee = order_result

    items_summary = "\n".join(
        [
            f"• {get_category_icon(item['name'])} {item['name']} (Size {item['selected_size']}) x{item['quantity']}"
            for item in items
        ]
    )

    delivery_str = (
        "FREE 🎉" if delivery_fee == 0.0 else f"{delivery_fee:,.2f} ETB"
    )

    receipt_text = (
        f"✅ Order Placed Successfully!\n\n"
        f"📄 Order Receipt\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 Order ID: #ORD-{order_id}\n"
        f"👤 Customer: {user_name}\n"
        f"📞 Phone: {phone_number}\n\n"
        f"📦 Items Ordered:\n{items_summary}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🚚 Delivery Fee: {delivery_str}\n"
        f"💰 Total Amount: {grand_total:,.2f} ETB\n"
        f"🔄 Status: Processing\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💡 Our delivery team will contact you shortly to confirm delivery."
    )

    await update.message.reply_text(
        receipt_text, reply_markup=build_main_menu(user.id)
    )

    # Prepare notification for Admins
    admin_msg = (
        f"🚨 NEW ORDER RECEIVED!\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 Order ID: #ORD-{order_id}\n"
        f"👤 Customer: {user_name} (ID: {user.id})\n"
        f"📞 Phone: {phone_number}\n\n"
        f"📦 Items:\n{items_summary}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🚚 Delivery: {delivery_str}\n"
        f"💳 Total Amount: {grand_total:,.2f} ETB\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    admin_keyboard = [
        [
            InlineKeyboardButton(
                "✅ Approve Order", callback_data=f"approve_{order_id}_{user.id}"
            ),
            InlineKeyboardButton(
                "❌ Cancel Order", callback_data=f"cancel_{order_id}_{user.id}"
            ),
        ]
    ]
    admin_reply_markup = InlineKeyboardMarkup(admin_keyboard)

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id, text=admin_msg, reply_markup=admin_reply_markup
            )
        except Exception as e:
            logger.error(f"Error notifying admin {admin_id}: {e}")

    return ConversationHandler.END


async def cancel_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels the ongoing checkout process"""
    user_id = update.effective_user.id
    await update.message.reply_text(
        "Checkout process canceled.", reply_markup=build_main_menu(user_id)
    )
    return ConversationHandler.END


async def handle_admin_order_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes admin approval and credits referrer bonus for successful purchase"""
    query = update.callback_query
    await query.answer()

    data = query.data.split("_")
    action = data[0]
    order_id = data[1]
    buyer_id = int(data[2]) if len(data) > 2 else None

    if action == "approve":
        # Record purchase and reward referrer if applicable
        if buyer_id:
            record_successful_purchase(buyer_id=buyer_id, reward_referrer_points=20)

        await query.edit_message_text(
            f"✅ Order #ORD-{order_id} has been Approved and marked for delivery."
        )
    elif action == "cancel":
        await query.edit_message_text(f"❌ Order #ORD-{order_id} has been Cancelled.")

import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InputMediaPhoto,
)
from telegram.ext import ContextTypes, ConversationHandler
from database.db import (
    get_all_products,
    get_product_by_id,
    add_to_cart,
    get_user_cart,
    clear_user_cart,
    create_multi_item_order,
    get_user_orders,
    get_order_details,
    decrease_cart_quantity,
)
# የ Referral Database Funktionen Import ማድረጊያ
from database.users_db import get_user, add_user, add_referral_points

# Import ADMIN_IDS safely or provide default
try:
    from config import ADMIN_IDS
except ImportError:
    ADMIN_IDS = []

logger = logging.getLogger(__name__)

# Conversation States
WAITING_FOR_PHONE = 1

# Category icon helper
CATEGORY_ICONS = {
    "Shoes": "👟",
    "Clothes": "👕",
    "Bags": "🎒",
    "Accessories": "🧢",
}


def get_category_icon(name: str) -> str:
    """Dynamically detects Shoes, Clothes, Bags, Accessories icon."""
    for key, icon in CATEGORY_ICONS.items():
        if key.lower() in name.lower():
            return icon
    return "📦"


def build_main_menu(user_id: int) -> ReplyKeyboardMarkup:
    """Generates the main persistent reply keyboard with dynamic live Cart count badge."""
    cart_items = get_user_cart(user_id)
    total_qty = sum(item["quantity"] for item in cart_items)

    cart_label = f"🛒 My Cart ({total_qty})" if total_qty > 0 else "🛒 My Cart"

    # '🎁 Invite & Earn' የሚለው አዲስ Button እዚህ ተጨምሯል
    keyboard = [
        [KeyboardButton("🛍️ Browse Catalog"), KeyboardButton(cart_label)],
        [KeyboardButton("📦 My Orders"), KeyboardButton("🎁 Invite & Earn")],
        [KeyboardButton("🎧 Support / Contact")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# ----- Main Navigation & Commands -----


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome screen, Referral Link Processing & Deep Link (prod_ID) handler."""
    user_first_name = update.effective_user.first_name or "Valued Customer"
    user_id = update.effective_user.id

    # -------------------------------------------------------------
    # 1. REFERRAL SYSTEM LOGIC (የጋበዣ ሲስተም)
    # -------------------------------------------------------------
    existing_user = get_user(user_id)

    # አዲስ ተጠቃሚ ከሆነ ብቻ Referral ሎጂኩ ይሠራል
    if not existing_user:
        referrer_id = None

        # በሬፈራል ሊንክ ከተመጣ (ለምሳሌ /start 12345678)
        if context.args and context.args[0].isdigit():
            possible_ref = int(context.args[0])
            # ራሱን እንዳይጋብዝ እና የጋበዘው ሰው DB ውስጥ መኖሩን ማረጋገጥ
            if possible_ref != user_id and get_user(possible_ref):
                referrer_id = possible_ref

        # አዲሱን ተጠቃሚ በ Users DB መመዝገብ
        add_user(user_id, referrer_id)

        # የጋበዘው ሰው ካለ ነጥብ (Points) መስጠት እና Notification መላክ
        if referrer_id:
            add_referral_points(referrer_id, points=10)
            try:
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text="🎉 **አዲስ ሰው በሊንክዎ ተመዝግቧል!**\n+10 ነጥብ (Points) አግኝተዋል።",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Error notifying referrer {referrer_id}: {e}")

    # -------------------------------------------------------------
    # 2. DEEP LINKING (Direct product display from channel link)
    # -------------------------------------------------------------
    if context.args and context.args[0].startswith("prod_"):
        try:
            product_id = int(context.args[0].split("_")[1])
            product = get_product_by_id(product_id)
            if product:
                icon = get_category_icon(product["name"])
                caption = (
                    f"💎 PREMIUM ARRIVAL / አዲስ የገባ 💎\n\n"
                    f"{icon} Product: {product['name']}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📏 Available Sizes: {product['size']}\n"
                    f"📦 In Stock: {product['stock']} item(s)\n"
                    f"💵 Price: {product['price']:,.2f} ETB\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━"
                )
                reply_markup = build_product_keyboard(user_id, product)
                photo_ids = [
                    p.strip()
                    for p in product["photo_id"].split(",")
                    if p.strip()
                ]

                if photo_ids:
                    await update.message.reply_photo(
                        photo=photo_ids[0],
                        caption=caption,
                        reply_markup=reply_markup,
                    )
                else:
                    await update.message.reply_text(
                        caption, reply_markup=reply_markup
                    )
                return
        except Exception as e:
            logger.error(f"Error handling deep link: {e}")

    # -------------------------------------------------------------
    # 3. NORMAL WELCOME SCREEN
    # -------------------------------------------------------------
    welcome_text = (
        f"💎 Welcome to Ethio Shoe Store, {user_first_name}!\n"
        f"Your ultimate spot for premium shoes, clothing & accessories.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 Main Features:\n"
        f"• 🛍️ Browse latest catalog & sizes\n"
        f"• 🛒 Multi-item Shopping Cart\n"
        f"• 🎁 Invite friends & earn reward points\n"
        f"• 🚀 Fast Checkout & Order Tracking\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👇 Use the buttons below to start shopping:"
    )

    await update.message.reply_text(
        welcome_text, reply_markup=build_main_menu(user_id)
    )


async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Customer support info"""
    support_text = (
        "🎧 Customer Support\n\n"
        "Have questions or need assistance with your size?\n"
        "📞 Call/Telegram: @EthioShoeSupport / +251900000000\n"
        "🕒 Working Hours: Mon - Sat (8:30 AM - 8:00 PM)"
    )
    await update.message.reply_text(support_text)


# ----- Dynamic Keyboard Builder Helper -----


def build_product_keyboard(
    user_id: int, product: dict, selected_size: str = None
) -> InlineKeyboardMarkup:
    """Generates dynamic keyboards with Size Selection or Quantity Controllers (+ / -)"""
    user_cart = get_user_cart(user_id)

    cart_items = [
        item for item in user_cart if item["product_id"] == product["id"]
    ]

    if not selected_size and cart_items:
        selected_size = cart_items[0]["selected_size"]

    qty_in_cart = (
        sum(
            item["quantity"]
            for item in cart_items
            if str(item["selected_size"]) == str(selected_size)
        )
        if selected_size
        else 0
    )

    keyboard = []

    # 1. Size Selection Row
    available_sizes = str(product["size"]).split(",")
    size_buttons = []
    for sz in available_sizes:
        sz_str = sz.strip()
        btn_label = (
            f"✅ Size {sz_str}" if selected_size == sz_str else f"Size {sz_str}"
        )
        size_buttons.append(
            InlineKeyboardButton(
                btn_label,
                callback_data=f"selectsize_{product['id']}_{sz_str}",
            )
        )

    keyboard.append(size_buttons)

    # 2. Dynamic Quantity Control Row (+ / -)
    if selected_size and qty_in_cart > 0:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "➖",
                    callback_data=f"cartdec_{product['id']}_{selected_size}",
                ),
                InlineKeyboardButton(
                    f"🛒 In Cart: {qty_in_cart}", callback_data="ignore"
                ),
                InlineKeyboardButton(
                    "➕",
                    callback_data=f"cartinc_{product['id']}_{selected_size}",
                ),
            ]
        )
    else:
        btn_action_text = (
            f"➕ Add Size {selected_size} to Cart"
            if selected_size
            else "👇 Select a Size Above"
        )
        cb_data = (
            f"cartinc_{product['id']}_{selected_size}"
            if selected_size
            else "prompt_select_size"
        )
        keyboard.append(
            [InlineKeyboardButton(btn_action_text, callback_data=cb_data)]
        )

    return InlineKeyboardMarkup(keyboard)


# ----- Catalog & Product View -----


async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays products as Photo Albums (Media Groups) with Size & Quantity controls"""
    products = get_all_products()
    user_id = update.effective_user.id

    message_target = (
        update.message
        if update.message
        else (update.callback_query.message if update.callback_query else None)
    )

    if not products:
        if message_target:
            await message_target.reply_text(
                "🚫 No products available right now. Please check back soon!"
            )
        return

    for item in products:
        icon = get_category_icon(item["name"])
        caption = (
            f"{icon} Product: {item['name']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📏 Available Sizes: {item['size']}\n"
            f"📦 Stock Available: {item['stock']} item(s)\n"
            f"💵 Price: {item['price']:,.2f} ETB\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )

        reply_markup = build_product_keyboard(user_id, item)
        photo_ids = [
            p.strip() for p in item["photo_id"].split(",") if p.strip()
        ]

        if len(photo_ids) > 1:
            media_group = [
                InputMediaPhoto(media=photo_id) for photo_id in photo_ids
            ]
            await message_target.reply_media_group(media=media_group)
            await message_target.reply_text(caption, reply_markup=reply_markup)
        else:
            try:
                await message_target.reply_photo(
                    photo=photo_ids[0],
                    caption=caption,
                    reply_markup=reply_markup,
                )
            except Exception as e:
                logger.error(f"Error sending product photo: {e}")
                await message_target.reply_text(
                    caption, reply_markup=reply_markup
                )


# ----- Real-time Cart Handlers -----


async def handle_catalog_interactions(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Handles Size Selection, Quantity Increase (+), and Decrease (-) Buttons in Real-time"""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    if data == "prompt_select_size":
        await query.answer(
            "⚠️ Please select a size first from the top row!", show_alert=True
        )
        return
    elif data == "ignore":
        await query.answer()
        return

    action, product_id_str, size = data.split("_")
    product_id = int(product_id_str)
    product = get_product_by_id(product_id)

    if not product or product["stock"] <= 0:
        await query.answer(
            "⚠️ Sorry, this item is out of stock!", show_alert=True
        )
        return

    if action == "selectsize":
        reply_markup = build_product_keyboard(
            user_id, product, selected_size=size
        )
        await query.edit_message_reply_markup(reply_markup=reply_markup)
        await query.answer(f"Selected Size {size}")

    elif action == "cartinc":
        success, msg = add_to_cart(user_id, product_id, size, quantity=1)

        cart_items = get_user_cart(user_id)
        total_items = sum(i["quantity"] for i in cart_items)

        if success:
            reply_markup = build_product_keyboard(
                user_id, product, selected_size=size
            )
            await query.edit_message_reply_markup(reply_markup=reply_markup)
            await query.answer(f"➕ Added Size {size}! (Cart: {total_items} items)")
        else:
            await query.answer(msg, show_alert=True)

    elif action == "cartdec":
        decrease_cart_quantity(user_id, product_id, size)

        cart_items = get_user_cart(user_id)
        total_items = sum(i["quantity"] for i in cart_items)

        reply_markup = build_product_keyboard(
            user_id, product, selected_size=size
        )
        await query.edit_message_reply_markup(reply_markup=reply_markup)
        await query.answer(f"➖ Decreased Size {size}. (Cart: {total_items} items)")


# ----- Cart & Checkout System -----


async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays user's cart with dynamic icons & smart free delivery calculation"""
    user_id = update.effective_user.id
    cart_items = get_user_cart(user_id)

    if not cart_items:
        text = (
            "🛒 Your Shopping Cart is Empty!\n\n"
            "Browse our catalog and pick your favorite items."
        )
        keyboard = [
            [
                InlineKeyboardButton(
                    "🛍️ Go to Catalog", callback_data="open_catalog"
                )
            ]
        ]
        target = (
            update.callback_query.message
            if update.callback_query
            else update.message
        )
        await target.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    subtotal = 0.0
    cart_text = "🛒 Your Shopping Cart\n━━━━━━━━━━━━━━━━━━━━━━\n\n"

    for idx, item in enumerate(cart_items, 1):
        item_qty = item["quantity"]
        unit_price = item["price"]
        item_total = unit_price * item_qty
        subtotal += item_total
        icon = get_category_icon(item["name"])

        cart_text += (
            f"{idx}. {icon} {item['name']}\n"
            f"   └ 📏 Size: {item['selected_size']} | 🔢 Qty: {item_qty}\n"
            f"   └ 💰 {unit_price:,.2f} ETB × {item_qty} = {item_total:,.2f} ETB\n\n"
        )

    # Dynamic delivery fee check (Free if subtotal >= 2000 ETB)
    delivery_fee = 0.0 if subtotal >= 2000.0 else 200.0
    delivery_str = (
        "FREE 🎉" if delivery_fee == 0.0 else f"{delivery_fee:,.2f} ETB"
    )
    total = subtotal + delivery_fee

    cart_text += (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 Subtotal: {subtotal:,.2f} ETB\n"
        f"🚚 Delivery Fee: {delivery_str}\n"
        f"--------------------------------------\n"
        f"💳 TOTAL AMOUNT: {total:,.2f} ETB\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "🚀 Proceed to Checkout", callback_data="start_checkout"
            )
        ],
        [InlineKeyboardButton("🗑️ Clear Cart", callback_data="clear_cart")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    target = (
        update.callback_query.message
        if update.callback_query
        else update.message
    )
    await target.reply_text(
        cart_text, reply_markup=reply_markup
    )


async def cart_action_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Handles cart inline button triggers"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "clear_cart":
        clear_user_cart(user_id)
        await query.edit_message_text("🗑️ Your cart has been cleared.")
        await query.message.reply_text(
            "Cart reset.", reply_markup=build_main_menu(user_id)
        )
    elif query.data == "open_catalog":
        await query.message.delete()
        await show_catalog(update, context)


# ----- Checkout Flow -----


async def start_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggers checkout phone request"""
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
        [KeyboardButton("📱 Send My Phone Number", request_contact=True)]
    ]
    reply_markup = ReplyKeyboardMarkup(
        phone_keyboard, resize_keyboard=True, one_time_keyboard=True
    )

    await query.message.reply_text(
        "📱 Checkout Step 1/2:\n\n"
        "To confirm your delivery order, please tap the button below to share your phone number or type it manually:",
        reply_markup=reply_markup,
    )
    return WAITING_FOR_PHONE


async def process_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finalizes multi-item order and notifies admins"""
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
        f"🔄 Status: 🟡 Processing\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💡 Our delivery team will contact you shortly to confirm delivery details."
    )
    await update.message.reply_text(
        receipt_text, reply_markup=build_main_menu(user.id)
    )

    # Admin Notification UI
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
                "✅ Approve Order", callback_data=f"approve_{order_id}"
            ),
            InlineKeyboardButton(
                "❌ Cancel Order", callback_data=f"cancel_{order_id}"
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
    """Cancels checkout flow"""
    user_id = update.effective_user.id
    await update.message.reply_text(
        "Checkout process canceled.", reply_markup=build_main_menu(user_id)
    )
    return ConversationHandler.END


async def view_orders_history(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Displays user's recent order history"""
    user_id = update.effective_user.id
    orders = get_user_orders(user_id, limit=5)

    if not orders:
        await update.message.reply_text(
            "📦 No Order History Found\n\nYou haven't placed any orders yet."
        )
        return

    msg = "📦 Your Recent Orders History\n━━━━━━━━━━━━━━━━━━━━━━\n\n"

    status_emoji = {
        "PENDING": "🟡 Processing",
        "APPROVED": "✅ Approved / In Transit",
        "CANCELLED": "❌ Cancelled",
    }

    for order in orders:
        order_info, items = get_order_details(order["id"])
        items_str = ", ".join(
            [
                f"{get_category_icon(i['product_name'])} {i['product_name']} (x{i['quantity']})"
                for i in items
            ]
        )
        status = status_emoji.get(order["status"], order["status"])

        msg += (
            f"🆔 Order #ORD-{order['id']}\n"
            f"📅 Date: {order['created_at'][:16]}\n"
            f"📦 Items: {items_str}\n"
            f"💰 Total Amount: {order['total_price']:,.2f} ETB\n"
            f"🔄 Status: {status}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

    await update.message.reply_text(msg)

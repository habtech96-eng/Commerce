import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_IDS, CHANNEL_ID
from database.db import (
    add_product,
    update_order_status,
    get_order_details,
    get_all_products,
    delete_product_by_id,
    update_product_stock,
    get_db,
)

logger = logging.getLogger(__name__)

# Conversation States
(
    ADD_CATEGORY,
    ADD_NAME,
    ADD_SIZE,
    ADD_PRICE,
    ADD_STOCK,
    ADD_PHOTO,
) = range(6)
WAITING_FOR_STOCK_INPUT = 10

CATEGORY_ICONS = {
    "Shoes": "👟",
    "Clothes": "👕",
    "Bags": "🎒",
    "Accessories": "🧢",
}


def get_category_icon(name_or_cat: str) -> str:
    """Dynamically returns matching emoji based on product or category name."""
    for key, icon in CATEGORY_ICONS.items():
        if key.lower() in name_or_cat.lower():
            return icon
    return "📦"


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ----- Auto-Post Helper Function -----
async def post_to_channel(
        context: ContextTypes.DEFAULT_TYPE, product_data: dict
):
    """Automatically posts newly added products to the channel/group."""
    if not CHANNEL_ID:
        return

    icon = get_category_icon(product_data["name"])

    caption = (
        f"💎 PREMIUM ARRIVAL / NEW ITEM 💎\n\n"
        f"{icon} Product: {product_data['name']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📏 Available Sizes: {product_data['size']}\n"
        f"📦 In Stock: {product_data['stock']} item(s)\n"
        f"💵 Price: {product_data['price']:,.2f} ETB\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👇 Click the button below to order directly via our bot!"
    )

    bot_username = (await context.bot.get_me()).username
    buy_url = f"https://t.me/{bot_username}?start=prod_{product_data['id']}"

    keyboard = [
        [InlineKeyboardButton("🛍️ Order Now via Bot", url=buy_url)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if product_data["photos"]:
            await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=product_data["photos"][0],
                caption=caption,
                reply_markup=reply_markup,
            )
    except Exception as e:
        logger.error(f"Error auto-posting to channel/group: {e}")


# ----- Product Categories Keyboard -----
def get_category_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("👟 Shoes", callback_data="cat_Shoes"),
            InlineKeyboardButton("👕 Clothes", callback_data="cat_Clothes"),
        ],
        [
            InlineKeyboardButton("🎒 Bags", callback_data="cat_Bags"),
            InlineKeyboardButton("🧢 Accessories", callback_data="cat_Accessories"),
        ],
        [
            InlineKeyboardButton(
                "✨ Custom Category", callback_data="cat_CUSTOM"
            )
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# ----- Admin Dashboard -----
async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "🚫 Access Denied: Admin privileges required."
        )
        return

    products = get_all_products()
    total_products = len(products)
    total_stock = sum(p["stock"] for p in products)

    # Safe DB connection with Context Manager
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'PENDING'")
        pending_orders = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'APPROVED'")
        approved_orders = cursor.fetchone()[0]

    dashboard_text = (
        "💎 ADMIN DASHBOARD\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 Active Products: {total_products}\n"
        f"👟 Total Items in Stock: {total_stock}\n"
        f"🟡 Pending Orders: {pending_orders}\n"
        f"✅ Approved Orders: {approved_orders}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 Quick Admin Commands:\n"
        "• /add - Add new product\n"
        "• /products - View, Delete & Edit stock of existing items\n"
        "• /cancel - Cancel active wizard operation"
    )
    await update.message.reply_text(dashboard_text)


# ----- Product Management (/products) -----
async def list_admin_products(
        update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 Access Denied.")
        return

    products = get_all_products()
    if not products:
        await update.message.reply_text(
            "📦 No active products found in inventory."
        )
        return

    await update.message.reply_text("🛠️ Product Management List:")

    for p in products:
        icon = get_category_icon(p["name"])
        text = (
            f"🆔 ID: {p['id']} | {icon} Product Name: {p['name']}\n"
            f"📏 Sizes: {p['size']}\n"
            f"💰 Price: {p['price']:,.2f} ETB\n"
            f"📦 Current Stock: {p['stock']} item(s)"
        )
        keyboard = [
            [
                InlineKeyboardButton(
                    "✏️ Edit Stock", callback_data=f"editstock_{p['id']}"
                ),
                InlineKeyboardButton(
                    "🗑️ Delete Product", callback_data=f"delprod_{p['id']}"
                ),
            ]
        ]
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def handle_product_admin_actions(
        update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("Unauthorized.", show_alert=True)
        return

    data = query.data.split("_")
    action = data[0]
    p_id = int(data[1])

    if action == "delprod":
        delete_product_by_id(p_id)
        await query.answer("🗑️ Product deleted successfully!", show_alert=True)
        await query.edit_message_text(
            f"❌ Product ID #{p_id} has been permanently deleted."
        )

    elif action == "editstock":
        context.user_data["editing_stock_pid"] = p_id
        await query.answer()
        await query.message.reply_text(
            f"✏️ Enter new stock quantity for Product ID #{p_id}:\n\n"
            f"(Or send /cancel to stop)"
        )
        return WAITING_FOR_STOCK_INPUT


async def process_stock_update(
        update: Update, context: ContextTypes.DEFAULT_TYPE
):
    p_id = context.user_data.get("editing_stock_pid")
    if not p_id:
        return ConversationHandler.END

    try:
        new_stock = int(update.message.text.strip())
        if new_stock < 0:
            await update.message.reply_text(
                "⚠️ Stock cannot be negative. Enter a valid number:"
            )
            return WAITING_FOR_STOCK_INPUT

        update_product_stock(p_id, new_stock)
        await update.message.reply_text(
            f"✅ Stock updated successfully! Product ID #{p_id} stock set to {new_stock}."
        )
        context.user_data.pop("editing_stock_pid", None)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(
            "⚠️ Invalid number format. Enter integer quantity:"
        )
        return WAITING_FOR_STOCK_INPUT


# ----- /add Product Wizard -----
async def start_add_product(
        update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "🚫 Access Denied: Admin privileges required."
        )
        return ConversationHandler.END

    context.user_data["p_photos"] = []
    await update.message.reply_text(
        "➕ Add New Product\n\nStep 1/6: Select Product Category:",
        reply_markup=get_category_keyboard(),
    )
    return ADD_CATEGORY


async def handle_category_selection(
        update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    category = query.data.split("_")[1]

    if category == "CUSTOM":
        await query.edit_message_text(
            "✍️ Enter custom category name: (e.g., Watches, Perfumes)"
        )
        context.user_data["waiting_custom_cat"] = True
        return ADD_CATEGORY

    context.user_data["p_category"] = category
    await query.edit_message_text(f"✅ Category selected: {category}")
    await query.message.reply_text(
        "📝 Step 2/6: Enter the product name (e.g., Nike Air Force 1 or Adidas Hoodie):"
    )
    return ADD_NAME


async def get_custom_category(
        update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if context.user_data.get("waiting_custom_cat"):
        custom_cat = update.message.text.strip()
        context.user_data["p_category"] = custom_cat
        context.user_data.pop("waiting_custom_cat", None)

        await update.message.reply_text(
            f"✅ Custom category saved: {custom_cat}\n\n📝 Step 2/6: Enter the product name:"
        )
        return ADD_NAME
    else:
        await update.message.reply_text(
            "⚠️ Please select a category from the inline buttons above."
        )
        return ADD_CATEGORY


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = context.user_data.get("p_category", "")
    item_name = update.message.text.strip()

    full_product_name = (
        f"{category} {item_name}".strip() if category else item_name
    )
    context.user_data["p_name"] = full_product_name

    await update.message.reply_text(
        "📏 Step 3/6: Enter available sizes separated by commas (e.g., 40, 41, 42 or M, L, XL):"
    )
    return ADD_SIZE


async def get_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["p_size"] = update.message.text.strip()
    await update.message.reply_text(
        "💰 Step 4/6: Enter price in ETB (e.g., 3500):"
    )
    return ADD_PRICE


async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip())
        if price <= 0:
            await update.message.reply_text(
                "⚠️ Price must be greater than 0 ETB. Try again:"
            )
            return ADD_PRICE

        context.user_data["p_price"] = price
        await update.message.reply_text(
            "📦 Step 5/6: Enter stock quantity available (e.g., 10):"
        )
        return ADD_STOCK
    except ValueError:
        await update.message.reply_text(
            "⚠️ Invalid format! Enter valid price number:"
        )
        return ADD_PRICE


async def get_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        stock = int(update.message.text.strip())
        if stock < 0:
            await update.message.reply_text(
                "⚠️ Stock cannot be negative. Try again:"
            )
            return ADD_STOCK

        context.user_data["p_stock"] = stock

        keyboard = [[KeyboardButton("✅ Done Uploading Photos")]]
        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=True
        )

        await update.message.reply_text(
            "📸 Step 6/6: Send photo(s) of the product.\n\n"
            "Press '✅ Done Uploading Photos' when finished!",
            reply_markup=reply_markup,
        )
        return ADD_PHOTO
    except ValueError:
        await update.message.reply_text(
            "⚠️ Invalid format! Enter a valid integer:"
        )
        return ADD_STOCK


async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "✅ Done Uploading Photos":
        photos_list = context.user_data.get("p_photos", [])

        if not photos_list:
            await update.message.reply_text(
                "⚠️ Please send at least ONE photo before clicking Done!"
            )
            return ADD_PHOTO

        product_name = context.user_data["p_name"]
        size = context.user_data["p_size"]
        price = context.user_data["p_price"]
        stock = context.user_data["p_stock"]

        p_id = add_product(product_name, price, size, stock, photos_list)

        product_info = {
            "id": p_id,
            "name": product_name,
            "size": size,
            "price": price,
            "stock": stock,
            "photos": photos_list,
        }
        await post_to_channel(context, product_info)

        await update.message.reply_text(
            f"✅ Product Created Successfully!\n"
            f"📢 Posted to Channel/Group!\n\n"
            f"🆔 Product ID: {p_id}\n"
            f"📦 Name: {product_name}\n"
            f"📏 Sizes: {size}\n"
            f"💰 Price: {price:,.2f} ETB\n"
            f"📦 Stock: {stock} item(s)\n"
            f"🖼️ Photos Attached: {len(photos_list)}",
            reply_markup=ReplyKeyboardRemove(),
        )

        context.user_data.clear()
        return ConversationHandler.END

    if update.message.photo:
        photo_id = update.message.photo[-1].file_id
        context.user_data["p_photos"].append(photo_id)
        count = len(context.user_data["p_photos"])
        await update.message.reply_text(
            f"📸 Photo #{count} received! Send another or tap '✅ Done Uploading Photos'."
        )
        return ADD_PHOTO
    else:
        await update.message.reply_text(
            "⚠️ Please upload a valid photo or click '✅ Done Uploading Photos'."
        )
        return ADD_PHOTO


async def cancel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Wizard process canceled.", reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END


# ----- Admin Order Callbacks -----
async def admin_order_callback(
        update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not is_admin(query.from_user.id):
        await query.answer("🚫 Unauthorized action.", show_alert=True)
        return

    data = query.data.split("_")
    action = data[0]
    order_id = int(data[1])

    order, items = get_order_details(order_id)

    if not order:
        await query.answer("❌ Order record not found.", show_alert=True)
        return

    if order["status"] != "PENDING":
        await query.answer(
            f"⚠️ Order #ORD-{order_id} has already been {order['status'].lower()}!",
            show_alert=True,
        )
        return

    admin_name = query.from_user.first_name or "Admin"
    await query.answer()

    if action == "approve":
        update_order_status(order_id, "APPROVED")
        status_label = f"✅ APPROVED (by {admin_name})"
        try:
            await context.bot.send_message(
                chat_id=order["user_id"],
                text=(
                    f"🎉 Order Approved!\n\n"
                    f"Your order #ORD-{order_id} has been confirmed. "
                    f"Our delivery team is preparing your items!"
                ),
            )
        except Exception as e:
            logger.error(f"Error notifying customer: {e}")

    elif action == "cancel":
        update_order_status(order_id, "CANCELLED")
        status_label = f"❌ CANCELLED (by {admin_name})"
        try:
            await context.bot.send_message(
                chat_id=order["user_id"],
                text=(
                    f"ℹ️ Order Status Update:\n\n"
                    f"Your order #ORD-{order_id} has been cancelled. "
                    f"If you have any questions, please contact support."
                ),
            )
        except Exception as e:
            logger.error(f"Error notifying customer: {e}")

    original_text = query.message.text or query.message.caption or ""
    updated_text = f"{original_text}\n\n📌 Status: {status_label}"

    if query.message.photo:
        await query.edit_message_caption(caption=updated_text, reply_markup=None)
    else:
        await query.edit_message_text(text=updated_text, reply_markup=None)

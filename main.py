import logging

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN
from database.db import init_db, cleanup_expired_carts
from handlers.user import (
    start_command,
    support_command,
    show_catalog,
    handle_catalog_interactions,
    view_cart,
    cart_action_handler,
    start_checkout,
    process_checkout,
    cancel_checkout,
    view_orders_history,
    WAITING_FOR_PHONE,
)
from handlers.admin import (
    admin_dashboard,
    list_admin_products,
    handle_product_admin_actions,
    process_stock_update,
    start_add_product,
    handle_category_selection,
    get_custom_category,
    get_name,
    get_size,
    get_price,
    get_stock,
    get_photo,
    cancel_add,
    admin_order_callback,
    ADD_CATEGORY,
    ADD_NAME,
    ADD_SIZE,
    ADD_PRICE,
    ADD_STOCK,
    ADD_PHOTO,
    WAITING_FOR_STOCK_INPUT,
)

# Logging Setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


# Automatic Background Cart Cleanup Job
async def auto_cleanup_job(context: ContextTypes.DEFAULT_TYPE):
    """Runs every 60 seconds to clean up expired cart items automatically"""
    try:
        cleanup_expired_carts(timeout_minutes=30)
    except Exception as e:
        logging.getLogger(__name__).error(f"Error in auto_cleanup_job: {e}")


def main():
    # 1. Initialize SQLite Database Schema
    init_db()

    # 2. Build Application with HTTP Timeouts
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .build()
    )

    # Schedule JobQueue for Auto-Cleaner (Runs every 1 minute)
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(auto_cleanup_job, interval=60, first=10)

    # --- 3. CONVERSATION HANDLERS ---

    # A) Checkout Flow Conversation
    checkout_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_checkout, pattern="^start_checkout$")
        ],
        states={
            WAITING_FOR_PHONE: [
                MessageHandler(
                    filters.CONTACT | (filters.TEXT & ~filters.COMMAND),
                    process_checkout,
                )
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_checkout)],
        per_chat=True,
        per_user=True,
    )

    # B) Admin Product Creation Wizard Conversation
    admin_add_handler = ConversationHandler(
        entry_points=[CommandHandler("add", start_add_product)],
        states={
            ADD_CATEGORY: [
                CallbackQueryHandler(
                    handle_category_selection, pattern="^cat_"
                ),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, get_custom_category
                ),
            ],
            ADD_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)
            ],
            ADD_SIZE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_size)
            ],
            ADD_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_price)
            ],
            ADD_STOCK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_stock)
            ],
            ADD_PHOTO: [
                MessageHandler(
                    (filters.PHOTO | filters.TEXT) & ~filters.COMMAND,
                    get_photo,
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_add)],
    )

    # C) Admin Stock Edit Conversation
    stock_edit_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                handle_product_admin_actions, pattern="^editstock_"
            )
        ],
        states={
            WAITING_FOR_STOCK_INPUT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, process_stock_update
                )
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_add)],
    )

    # --- 4. REGISTER HANDLERS ---

    # Register Conversations first to ensure state priority
    app.add_handler(checkout_handler)
    app.add_handler(admin_add_handler)
    app.add_handler(stock_edit_handler)

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("support", support_command))
    app.add_handler(CommandHandler("admin", admin_dashboard))
    app.add_handler(CommandHandler("products", list_admin_products))

    # Reply Keyboard Triggers (UPDATED REGEX FOR CART BADGE)
    app.add_handler(
        MessageHandler(filters.Regex("^🛍️ Browse Catalog$"), show_catalog)
    )
    # `^🛒 My Cart` በማድረጋችን ቁጥር ቢኖረውም አግኝቶ ይሰራል
    app.add_handler(MessageHandler(filters.Regex("^🛒 My Cart"), view_cart))
    app.add_handler(
        MessageHandler(filters.Regex("^📦 My Orders$"), view_orders_history)
    )
    app.add_handler(
        MessageHandler(filters.Regex("^🎧 Support / Contact$"), support_command)
    )

    # Dynamic Inline Button Callbacks
    app.add_handler(
        CallbackQueryHandler(
            handle_catalog_interactions,
            pattern="^(selectsize|cartinc|cartdec|prompt_select_size|ignore)",
        )
    )

    # Product Delete Action Callback
    app.add_handler(
        CallbackQueryHandler(
            handle_product_admin_actions, pattern="^delprod_"
        )
    )

    # Cart & Admin Order Callbacks
    app.add_handler(
        CallbackQueryHandler(
            cart_action_handler, pattern="^(clear_cart|open_catalog)$"
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            admin_order_callback, pattern="^(approve|cancel)_"
        )
    )

    # 5. Launch Polling Loop
    print("🚀 Ethio Shoe Store Bot is running successfully!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
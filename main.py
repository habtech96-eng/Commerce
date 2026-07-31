import logging
from telegram.error import NetworkError, TimedOut
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
from database.users_db import init_users_db

# User Handlers
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

# Referral & Leaderboard Handlers
from handlers.referral import (
    referral_command,
    show_leaderboard,
    show_referral_info,
)

# Admin Handlers & Broadcast System
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
    start_broadcast,
    process_broadcast,
    ADD_CATEGORY,
    ADD_NAME,
    ADD_SIZE,
    ADD_PRICE,
    ADD_STOCK,
    ADD_PHOTO,
    WAITING_FOR_STOCK_INPUT,
    WAITING_FOR_BROADCAST_MSG,
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


# Global Network & General Error Handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates and handle network glitches gracefully"""
    if isinstance(context.error, (NetworkError, TimedOut)):
        logging.warning(
            f"Network glitch occurred: {context.error}. Retrying automatically..."
        )
    else:
        logging.error(f"Update {update} caused error {context.error}")


def main():
    # 1. Initialize SQLite Database Schemas
    init_db()
    init_users_db()

    # 2. Build Application with Extended HTTP Timeouts for Network Stability
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(60.0)
        .read_timeout(60.0)
        .write_timeout(60.0)
        .pool_timeout(60.0)
        .get_updates_connect_timeout(60.0)
        .get_updates_read_timeout(60.0)
        .build()
    )

    # Register Global Error Handler
    app.add_error_handler(error_handler)

    # Schedule JobQueue for Auto-Cleaner (Runs every 1 minute)
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(auto_cleanup_job, interval=60, first=10)

    # --- MENU BUTTON & COMMAND FALLBACK FILTERS ---
    menu_button_filter = filters.Regex(
        "^(🛍️ Browse Catalog|🛒 My Cart|📦 My Orders|🎁 Invite & Earn|🎧 Support / Contact)"
    )

    cancel_fallbacks = [
        CommandHandler("cancel", cancel_add),
        CommandHandler("start", cancel_add),
        CommandHandler("admin", cancel_add),
        CommandHandler("products", cancel_add),
        CommandHandler("referral", cancel_add),
        CommandHandler("leaderboard", cancel_add),
        CommandHandler("broadcast", cancel_add),
        MessageHandler(menu_button_filter, cancel_add),
    ]

    checkout_fallbacks = [
        CommandHandler("cancel", cancel_checkout),
        CommandHandler("start", cancel_checkout),
        CommandHandler("admin", cancel_checkout),
        CommandHandler("products", cancel_checkout),
        CommandHandler("referral", cancel_checkout),
        CommandHandler("leaderboard", cancel_checkout),
        CommandHandler("broadcast", cancel_checkout),
        MessageHandler(menu_button_filter, cancel_checkout),
    ]

    # --- 3. CONVERSATION HANDLERS ---

    # A) Checkout Flow Conversation
    checkout_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                start_checkout, pattern="^(start_checkout|proceed_checkout)$"
            )
        ],
        states={
            WAITING_FOR_PHONE: [
                MessageHandler(
                    filters.CONTACT
                    | (filters.TEXT & ~filters.COMMAND & ~menu_button_filter),
                    process_checkout,
                )
            ]
        },
        fallbacks=checkout_fallbacks,
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
                    filters.TEXT & ~filters.COMMAND & ~menu_button_filter,
                    get_custom_category,
                ),
            ],
            ADD_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~menu_button_filter,
                    get_name,
                )
            ],
            ADD_SIZE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~menu_button_filter,
                    get_size,
                )
            ],
            ADD_PRICE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~menu_button_filter,
                    get_price,
                )
            ],
            ADD_STOCK: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~menu_button_filter,
                    get_stock,
                )
            ],
            ADD_PHOTO: [
                MessageHandler(
                    (filters.PHOTO | filters.TEXT)
                    & ~filters.COMMAND
                    & ~menu_button_filter,
                    get_photo,
                )
            ],
        },
        fallbacks=cancel_fallbacks,
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
                    filters.TEXT & ~filters.COMMAND & ~menu_button_filter,
                    process_stock_update,
                )
            ]
        },
        fallbacks=cancel_fallbacks,
    )

    # D) Admin Broadcast System Conversation
    broadcast_handler = ConversationHandler(
        entry_points=[CommandHandler("broadcast", start_broadcast)],
        states={
            WAITING_FOR_BROADCAST_MSG: [
                MessageHandler(
                    ~filters.COMMAND & ~menu_button_filter,
                    process_broadcast,
                )
            ]
        },
        fallbacks=cancel_fallbacks,
    )

    # --- 4. REGISTER HANDLERS ---

    # Conversation Handlers First
    app.add_handler(checkout_handler)
    app.add_handler(admin_add_handler)
    app.add_handler(stock_edit_handler)
    app.add_handler(broadcast_handler)

    # User & General Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("support", support_command))
    app.add_handler(CommandHandler("referral", referral_command))
    app.add_handler(CommandHandler("leaderboard", show_leaderboard))

    # Admin Commands
    app.add_handler(CommandHandler("admin", admin_dashboard))
    app.add_handler(CommandHandler("products", list_admin_products))

    # Reply Keyboard Triggers
    app.add_handler(
        MessageHandler(filters.Regex("^🛍️ Browse Catalog$"), show_catalog)
    )
    app.add_handler(MessageHandler(filters.Regex("^🛒 My Cart"), view_cart))
    app.add_handler(
        MessageHandler(filters.Regex("^📦 My Orders$"), view_orders_history)
    )
    app.add_handler(
        MessageHandler(filters.Regex("^🎁 Invite & Earn$"), referral_command)
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^🎧 Support / Contact$"), support_command
        )
    )

    # Referral & Profile Inline Callbacks
    app.add_handler(
        CallbackQueryHandler(
            show_referral_info, pattern="^(show_referral|show_profile)$"
        )
    )
    app.add_handler(
        CallbackQueryHandler(start_command, pattern="^back_to_main$")
    )

    # Dynamic Catalog Inline Button Callbacks
    app.add_handler(
        CallbackQueryHandler(
            handle_catalog_interactions,
            pattern="^(selectsize|cartinc|cartdec|prompt_select_size|ignore)",
        )
    )

    # Admin Product Delete Callback
    app.add_handler(
        CallbackQueryHandler(
            handle_product_admin_actions, pattern="^delprod_"
        )
    )

    # Cart Actions Callback
    app.add_handler(
        CallbackQueryHandler(
            cart_action_handler, pattern="^(clear_cart|open_catalog)$"
        )
    )

    # Admin Order Approval / Cancellation Callbacks
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

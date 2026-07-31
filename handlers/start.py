from telegram import Update
from telegram.ext import ContextTypes

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # Check if user came from a referral link (args contains the payload after /start)
    referrer_id = None
    if context.args:
        try:
            possible_referrer = int(context.args[0])
            # Prevent self-referral
            if possible_referrer != user_id:
                referrer_id = possible_referrer
        except ValueError:
            pass

    # DB Logic Pseudocode:
    # 1. Check if user already exists in DB.
    # 2. If NEW user and referrer_id is present:
    #    - Save new user with referred_by = referrer_id
    #    - Increment referrer_id's referral_count by +1 (and add reward points)
    #    - Send notification to referrer_id: "Someone joined using your link!"
    # 3. If ALREADY existing user, ignore referral link to prevent exploitation.

    await update.message.reply_text(
        f"Welcome, {user.first_name}! 👋\n\nUse /referral to get your personal invite link and check your rewards."
    )
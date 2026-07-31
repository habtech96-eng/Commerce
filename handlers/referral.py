async def referral_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot_username = context.bot.username

    # Create personal link
    ref_link = f"https://t.me/{bot_username}?start={user_id}"

    # Fetch stats from DB (replace with your actual database query)
    # referral_count, points = await get_user_referral_stats(user_id)
    referral_count = 0  # Placeholder
    points = 0          # Placeholder

    message = (
        "🎁 **Referral & Rewards**\n\n"
        f"Share your referral link with friends and earn rewards for every new user who joins!\n\n"
        f"🔗 **Your Referral Link:**\n`{ref_link}`\n\n"
        f"📊 **Your Stats:**\n"
        f"• Total Referrals: `{referral_count}`\n"
        f"• Total Credits/Points: `{points}`"
    )

    await update.message.reply_text(
        message, 
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
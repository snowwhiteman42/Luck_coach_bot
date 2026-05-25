import os
import random
import logging
import getpass
import warnings
from datetime import datetime

try:
    from dotenv import load_dotenv
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.warnings import PTBUserWarning
    from telegram.ext import (
        ApplicationBuilder,
        CommandHandler,
        CallbackQueryHandler,
        ConversationHandler,
        ContextTypes,
    )
except ImportError:
    print("\n❌ CRITICAL ERROR: Missing Libraries")
    print("Run: pip install python-telegram-bot python-dotenv")
    exit(1)

warnings.filterwarnings("ignore", category=PTBUserWarning)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Max possible distance between any two values in [1, 10]
MAX_POSSIBLE_ERROR = 9

PLAYING = 1


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if update.callback_query:
        await update.callback_query.answer()

    context.user_data['round'] = 1
    context.user_data['history'] = []

    intro_text = (
        f"🍀 *Test Your Luck* 🍀\n"
        f"Player: {user.first_name}\n\n"
        "I will think of a number between 1 and 10.\n"
        "We will play 10 rounds.\n"
        "Starting Round 1..."
    )

    await update.effective_chat.send_message(intro_text, parse_mode='Markdown')
    await ask_number(update, context)
    return PLAYING


async def ask_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_round = context.user_data['round']
    secret_number = random.randint(1, 10)
    context.user_data['current_secret'] = secret_number

    keyboard = [
        [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(1, 6)],
        [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(6, 11)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"🎲 *Round {current_round}/10*\nGuess the number (1–10):"

    await update.effective_chat.send_message(text, reply_markup=reply_markup, parse_mode='Markdown')


async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not query.data.isdigit():
        return ConversationHandler.END

    if 'round' not in context.user_data:
        await query.edit_message_text("⚠️ Session expired. Type /start to play.")
        return ConversationHandler.END

    if 'current_secret' not in context.user_data:
        await query.edit_message_text("⚠️ Something went wrong. Type /start to play.")
        return ConversationHandler.END

    user_guess = int(query.data)
    secret = context.user_data['current_secret']
    current_round = context.user_data['round']

    actual_error = abs(user_guess - secret)
    round_luck = (1 - actual_error / MAX_POSSIBLE_ERROR) * 100.0

    context.user_data['history'].append({
        'guess': user_guess,
        'secret': secret,
        'round_score': round_luck,
    })

    if user_guess == secret:
        result_text = f"✅ *Round {current_round}/10:* You guessed *{user_guess}* — PERFECT MATCH! (100%)"
    else:
        result_text = (
            f"🎲 *Round {current_round}/10:* You guessed *{user_guess}*, "
            f"the number was *{secret}* — {round_luck:.0f}% close"
        )

    try:
        await query.edit_message_text(result_text, parse_mode='Markdown')
    except Exception as e:
        logging.warning("Could not edit message: %s", e)

    context.user_data['round'] += 1

    if context.user_data['round'] > 10:
        await show_results(update, context)
        return ConversationHandler.END
    else:
        await ask_number(update, context)
        return PLAYING


async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    history = context.user_data.get('history', [])
    correct_count = 0
    total_luck_score = 0.0
    details = ""

    for idx, item in enumerate(history, 1):
        guess = item['guess']
        secret = item['secret']
        score = item['round_score']
        total_luck_score += score

        if guess == secret:
            correct_count += 1
            status_text = "✅ PERFECT"
        else:
            status_text = f"{score:.0f}% close"

        details += f"R{idx}: Guess {guess} | True {secret}  {status_text}\n"

    n = len(history)
    average_luck = total_luck_score / n if n > 0 else 0.0
    today_str = datetime.now().strftime("%d.%m.%Y")

    summary = (
        f"🏁 *GAME OVER* 🏁\n"
        f"📅 Date: {today_str}\n"
        f"Exact Matches: {correct_count}/10\n"
        f"Luck Score: {average_luck:.1f}%\n\n"
        f"📝 *Game History:*\n"
        f"{details}"
    )

    keyboard = [[InlineKeyboardButton("Play Again", callback_data="start_game")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.effective_chat.send_message(summary, parse_mode='Markdown', reply_markup=reply_markup)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Game canceled. Type /start to play again.")
    return ConversationHandler.END


def main():
    load_dotenv()
    token = os.getenv("TELEGRAM_TOKEN")

    if not token:
        print("\n⚠️  TELEGRAM_TOKEN not found in .env file.")
        token = getpass.getpass("👉 Paste your Telegram Bot Token: ").strip()

    if not token:
        print("No token provided. Exiting.")
        return

    print("Bot is starting...")
    application = ApplicationBuilder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(start, pattern="^start_game$"),
        ],
        states={
            PLAYING: [CallbackQueryHandler(handle_guess)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    print("✅ Bot is running! Go to Telegram and type /start")
    application.run_polling()


if __name__ == '__main__':
    main()

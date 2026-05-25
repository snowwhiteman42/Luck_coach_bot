import os
import random
import logging
import getpass
import sqlite3
import warnings
from datetime import datetime, timedelta
from pathlib import Path

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

MAX_POSSIBLE_ERROR = 9
PLAYING = 1
DB_PATH = Path(__file__).parent / "stats.db"


# --- DATABASE ---

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                username     TEXT,
                luck_score   REAL    NOT NULL,
                exact_matches INTEGER NOT NULL,
                date         TEXT    NOT NULL,
                played_at    TEXT    NOT NULL
            )
        """)


def save_game(user_id: int, username: str, luck_score: float, exact_matches: int):
    now = datetime.now()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO games (user_id, username, luck_score, exact_matches, date, played_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, username, luck_score, exact_matches,
             now.strftime("%Y-%m-%d"), now.isoformat())
        )


def get_stats(user_id: int) -> dict:
    today     = datetime.now().strftime("%Y-%m-%d")
    week_ago  = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    with sqlite3.connect(DB_PATH) as conn:
        def q(sql, params=()):
            return conn.execute(sql, params).fetchone()

        return {
            'today': q(
                "SELECT COUNT(*), AVG(luck_score), MAX(luck_score) "
                "FROM games WHERE user_id=? AND date=?",
                (user_id, today)
            ),
            'week': q(
                "SELECT COUNT(*), AVG(luck_score), MAX(luck_score) "
                "FROM games WHERE user_id=? AND date>=?",
                (user_id, week_ago)
            ),
            'month': q(
                "SELECT COUNT(*), AVG(luck_score), MAX(luck_score) "
                "FROM games WHERE user_id=? AND date>=?",
                (user_id, month_ago)
            ),
            'all': q(
                "SELECT COUNT(*), AVG(luck_score), MAX(luck_score), MAX(exact_matches) "
                "FROM games WHERE user_id=?",
                (user_id,)
            ),
            'recent': [
                r[0] for r in conn.execute(
                    "SELECT luck_score FROM games WHERE user_id=? "
                    "ORDER BY played_at DESC LIMIT 10",
                    (user_id,)
                ).fetchall()
            ],
        }


def trend_label(scores: list) -> str:
    if len(scores) < 4:
        return "➡️ play more games to see your trend"
    recent = sum(scores[:3]) / 3
    older_slice = scores[3:3 + min(3, len(scores) - 3)]
    older = sum(older_slice) / len(older_slice)
    diff = recent - older
    if diff > 3:
        return "📈 improving"
    if diff < -3:
        return "📉 declining"
    return "➡️ stable"


# --- GAME HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if update.callback_query:
        await update.callback_query.answer()

    context.user_data['round'] = 1
    context.user_data['history'] = []

    intro_text = (
        f"🍀 *Test Your Luck* 🍀\n"
        f"Welcome, {user.first_name}!\n\n"
        "Each round I secretly pick a number (1–10).\n"
        "Tap your guess — the closer you are, the higher your score.\n\n"
        "🎯 Perfect guess = *100%*\n"
        "📏 Off by 9 = *0%*\n\n"
        "10 rounds. Let's see how lucky you really are!\n"
        "_(Type /stats anytime to check your progress)_"
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
    text = f"🎲 *Round {current_round}/10* — pick your number:"

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

    user_guess    = int(query.data)
    secret        = context.user_data['current_secret']
    current_round = context.user_data['round']
    actual_error  = abs(user_guess - secret)
    round_luck    = (1 - actual_error / MAX_POSSIBLE_ERROR) * 100.0

    context.user_data['history'].append({
        'guess': user_guess,
        'secret': secret,
        'round_score': round_luck,
    })

    if user_guess == secret:
        result_text = (
            f"✅ *Round {current_round}/10:* "
            f"You guessed *{user_guess}* — PERFECT MATCH! (100%)"
        )
    else:
        result_text = (
            f"🎲 *Round {current_round}/10:* "
            f"You guessed *{user_guess}*, the number was *{secret}* — {round_luck:.0f}% close"
        )

    try:
        await query.edit_message_text(result_text, parse_mode='Markdown')
    except Exception as e:
        logging.warning("Could not edit message: %s", e)

    context.user_data['round'] += 1

    if context.user_data['round'] > 10:
        await show_results(update, context)
        return ConversationHandler.END

    await ask_number(update, context)
    return PLAYING


async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    history = context.user_data.get('history', [])

    correct_count    = 0
    total_luck_score = 0.0
    details          = ""

    for idx, item in enumerate(history, 1):
        guess  = item['guess']
        secret = item['secret']
        score  = item['round_score']
        total_luck_score += score

        if guess == secret:
            correct_count += 1
            status_text = "✅ PERFECT"
        else:
            status_text = f"{score:.0f}% close"

        details += f"R{idx}: Guess {guess} | True {secret}  {status_text}\n"

    n            = len(history)
    average_luck = total_luck_score / n if n > 0 else 0.0
    today_str    = datetime.now().strftime("%d.%m.%Y")

    # Save result, then check if it's a personal best
    save_game(user.id, user.first_name, average_luck, correct_count)
    stats         = get_stats(user.id)
    all_time_best = stats['all'][2] or 0.0

    if average_luck >= all_time_best:
        record_line = "🎉 *NEW PERSONAL BEST!*\n"
    else:
        record_line = f"🏆 Your best ever: {all_time_best:.1f}%\n"

    summary = (
        f"🏁 *GAME OVER* 🏁\n"
        f"📅 {today_str}\n\n"
        f"🎯 Exact Matches: {correct_count}/10\n"
        f"⭐ Luck Score: *{average_luck:.1f}%*\n"
        f"{record_line}\n"
        f"📝 *Round History:*\n"
        f"{details}\n"
        f"Type /stats to see your full history."
    )

    keyboard = [[InlineKeyboardButton("🔄 Play Again", callback_data="start_game")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.effective_chat.send_message(summary, parse_mode='Markdown', reply_markup=reply_markup)


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    stats = get_stats(user.id)

    total_games = stats['all'][0] or 0

    if total_games == 0:
        await update.message.reply_text(
            "You haven't played yet\\! Type /start to begin\\.",
            parse_mode='MarkdownV2'
        )
        return

    def fmt_row(row, label: str) -> str:
        count, avg, best = row[0], row[1], row[2]
        if not count:
            return f"{label}: —"
        return f"{label}: {count} game{'s' if count != 1 else ''} | Avg: {avg:.1f}% | Best: {best:.1f}%"

    all_row      = stats['all']
    trend        = trend_label(stats['recent'])
    recent_str   = " → ".join(f"{s:.0f}%" for s in stats['recent'][:5])

    text = (
        f"📊 *Luck Stats — {user.first_name}*\n\n"
        f"{fmt_row(stats['today'], '📅 Today')}\n"
        f"{fmt_row(stats['week'],  '📆 This week')}\n"
        f"{fmt_row(stats['month'], '🗓 This month')}\n\n"
        f"🏆 *All Time*\n"
        f"   Games played: {all_row[0]}\n"
        f"   Average score: {all_row[1]:.1f}%\n"
        f"   Best game: {all_row[2]:.1f}%\n"
        f"   Most exact guesses: {all_row[3]}/10\n\n"
        f"📈 Trend: {trend}\n"
        f"Recent: {recent_str}\n\n"
        f"Type /start to play!"
    )

    await update.message.reply_text(text, parse_mode='Markdown')


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Game canceled. Type /start to play again.")
    return ConversationHandler.END


def main():
    load_dotenv()
    init_db()

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
    application.add_handler(CommandHandler('stats', show_stats))

    print("✅ Bot is running! Go to Telegram and type /start")
    application.run_polling()


if __name__ == '__main__':
    main()

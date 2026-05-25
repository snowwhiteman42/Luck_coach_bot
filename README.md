# Luck Bot

🤖 **Try it live: [t.me/Luck_coach_bot](https://t.me/Luck_coach_bot)**

A Telegram bot that tests your luck over 10 rounds. Each round the bot picks a random number between 1 and 10 — you guess, and your Luck Score reflects how close you were. Stats are saved locally so you can track your progress over time.

## How it works

- 10 rounds per game
- Each round: bot picks a secret number (1–10), you tap your guess
- After each guess: the secret is revealed and your round score shown
- Game over: exact matches, average Luck Score, and personal best comparison
- `/stats`: your full history — today, this week, this month, all-time, trend

**Scoring:** `(1 - |guess - secret| / 9) × 100%` — consistent and fair across all rounds.

## Setup

**1. Clone and install dependencies**

```bash
git clone <your-repo-url>
cd Luck_test
pip install -r requirements.txt
```

**2. Create your `.env` file**

```bash
cp .env.example .env
```

Then edit `.env` and paste your bot token:

```
TELEGRAM_TOKEN=your_bot_token_here
```

Get a token from [@BotFather](https://t.me/BotFather) on Telegram.

**3. Run the bot**

```bash
python luck-bot.py
```

Then open Telegram and send `/start` to your bot.

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Start a new 10-round game |
| `/stats` | View your stats: today / week / month / all-time + trend |
| `/cancel` | Cancel the current game |

## Stats tracking

Your game results are saved automatically to a local SQLite database (`stats.db`).  
The `/stats` command shows:

- **Today / This week / This month** — games played, average score, best score
- **All time** — total games, average, best game, most exact guesses in one game
- **Trend** — whether your recent scores are improving, declining, or stable (needs 4+ games)

`stats.db` is excluded from git — it stays on your machine only.

## Requirements

- Python 3.9+
- `python-telegram-bot >= 20.0`
- `python-dotenv`

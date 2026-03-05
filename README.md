# 🏆 SportsOracle v2 — Live Telegram Bot

Real football & basketball predictions using live APIs + booking code converter.

---

## 🚀 Setup

### Files to upload to GitHub:
- `bot.py`
- `requirements.txt`
- `Procfile`

### Environment Variables to set on Railway:

| Variable | Value | Required? |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Your token from @BotFather | ✅ Yes |
| `API_FOOTBALL_KEY` | From api-football.com | ⚠️ For football |

---

## 🔑 Getting Your Free API-Football Key

1. Go to **https://dashboard.api-football.com/register**
2. Sign up for free (no credit card needed)
3. Copy your API key from the dashboard
4. Add it as `API_FOOTBALL_KEY` on Railway

✅ Free plan gives you **100 requests/day** — enough for the bot.

---

## 📡 What Powers the Bot

| Sport | Source | Key Needed? |
|---|---|---|
| ⚽ Football (all leagues) | api-football.com | Yes (free) |
| 🏀 Basketball (all leagues) | thesportsdb.com | No (free) |

---

## 💬 Bot Commands

| Command | What it does |
|---|---|
| `/start` | Main menu |
| `/football` | Browse all football games (7 days) |
| `/basketball` | Browse all basketball games (7 days) |
| `/toppicks` | High confidence picks only |
| `/convert` | Convert a booking code |
| `/help` | List all commands |

---

## 🔄 Booking Code Converter

Supports: **Bet9ja ↔ SportyBet ↔ 1xBet ↔ BetWay ↔ BetKing**

How to use:
1. Tap 🔄 Convert Booking Code
2. Select which platform your code is FROM
3. Type your booking code in chat
4. Choose which platform to convert TO (or convert to ALL at once)

---

⚠️ For entertainment only. Bet responsibly.

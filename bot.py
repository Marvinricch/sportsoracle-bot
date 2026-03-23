import os
import logging
import asyncio
from datetime import datetime, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode
from api import FootballAPI
from predictor import MatchPredictor
from formatter import MessageFormatter

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
API_KEY = os.getenv("FOOTBALL_DATA_KEY", "YOUR_FOOTBALL_DATA_KEY_HERE")

# Conversation states
WAITING_MATCH_INPUT = 1

api = FootballAPI(API_KEY)
predictor = MatchPredictor(api)
formatter = MessageFormatter()

# ─── COMMAND HANDLERS ─────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎯 Today's 10-Odds Ticket", callback_data="daily_ticket")],
        [InlineKeyboardButton("🔍 Analyze a Match", callback_data="analyze_prompt"),
         InlineKeyboardButton("📋 Upcoming Fixtures", callback_data="fixtures")],
        [InlineKeyboardButton("➕ Add Manual Pick", callback_data="manual_pick"),
         InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome = (
        "⚽ *SPORTSORCA CLE — AI Prediction Engine*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🧠 Powered by deep statistical analysis\n"
        "🌍 Covering all football leagues worldwide\n"
        "📊 10-Odds daily ticket + deep match insights\n\n"
        "What would you like today?"
    )
    await update.message.reply_text(welcome, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)


async def daily_ticket_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_daily_ticket(update.message, context)


async def analyze_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: `/analyze Team A vs Team B`\n\nExample: `/analyze Arsenal vs Chelsea`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    query = " ".join(args)
    await _send_match_analysis(update.message, context, query)


async def fixtures_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_fixtures(update.message, context)


async def addpick_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✏️ *Add a Manual Pick*\n\nSend me the match in this format:\n"
        "`Team A vs Team B — Your Pick — Odds`\n\n"
        "Example: `Man City vs Arsenal — Over 2.5 — 1.85`",
        parse_mode=ParseMode.MARKDOWN
    )
    return WAITING_MATCH_INPUT


async def receive_manual_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        parts = [p.strip() for p in text.split("—")]
        if len(parts) != 3:
            raise ValueError("Wrong format")
        match, pick, odds = parts
        if "manual_picks" not in context.bot_data:
            context.bot_data["manual_picks"] = []
        context.bot_data["manual_picks"].append({
            "match": match, "pick": pick, "odds": float(odds)
        })
        await update.message.reply_text(
            f"✅ *Pick Added!*\n\n⚽ {match}\n📌 {pick} @ *{odds}*\n\n"
            f"Total manual picks today: {len(context.bot_data['manual_picks'])}",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        await update.message.reply_text(
            "❌ Wrong format. Use:\n`Team A vs Team B — Pick — Odds`",
            parse_mode=ParseMode.MARKDOWN
        )
    return ConversationHandler.END


# ─── CALLBACK HANDLERS ────────────────────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "daily_ticket":
        await query.message.reply_text("⏳ Building today's 10-odds ticket...", parse_mode=ParseMode.MARKDOWN)
        await _send_daily_ticket(query.message, context)

    elif data == "analyze_prompt":
        await query.message.reply_text(
            "🔍 Send me: `/analyze Team A vs Team B`",
            parse_mode=ParseMode.MARKDOWN
        )

    elif data == "fixtures":
        await query.message.reply_text("⏳ Fetching upcoming fixtures...", parse_mode=ParseMode.MARKDOWN)
        await _send_fixtures(query.message, context)

    elif data == "manual_pick":
        await query.message.reply_text(
            "✏️ Use command: `/addpick Team A vs Team B — Pick — Odds`",
            parse_mode=ParseMode.MARKDOWN
        )

    elif data.startswith("deep_"):
        fixture_id = data.replace("deep_", "")
        await query.message.reply_text("🧠 Running deep analysis...", parse_mode=ParseMode.MARKDOWN)
        await _send_deep_analysis(query.message, context, fixture_id)

    elif data == "settings":
        await _show_settings(query.message, context)

    elif data.startswith("toggle_"):
        setting = data.replace("toggle_", "")
        if "settings" not in context.bot_data:
            context.bot_data["settings"] = {"auto_daily": True, "notifications": True}
        context.bot_data["settings"][setting] = not context.bot_data["settings"].get(setting, True)
        await _show_settings(query.message, context)


# ─── CORE FUNCTIONS ───────────────────────────────────────────────────────────

async def _send_daily_ticket(message, context: ContextTypes.DEFAULT_TYPE):
    try:
        manual_picks = context.bot_data.get("manual_picks", [])
        ticket = await predictor.build_daily_ticket(manual_picks=manual_picks)

        if not ticket:
            await message.reply_text("⚠️ Not enough data to build ticket today. Try again later.")
            return

        text = formatter.format_daily_ticket(ticket)
        keyboard = [
            [InlineKeyboardButton(f"🔍 Analyze: {p['home']} vs {p['away']}", callback_data=f"deep_{p['fixture_id']}")]
            for p in ticket["picks"][:3]
        ]
        keyboard.append([InlineKeyboardButton("🔄 Regenerate Ticket", callback_data="daily_ticket")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        for chunk in _split_message(text):
            await message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
            reply_markup = None  # only attach keyboard to first chunk

    except Exception as e:
        logger.error(f"Error building ticket: {e}")
        await message.reply_text(f"❌ Error building ticket: {str(e)}\n\nCheck your API key in config.")


async def _send_match_analysis(message, context, query_text: str):
    try:
        await message.reply_text(f"🔍 Searching for: *{query_text}*...", parse_mode=ParseMode.MARKDOWN)
        fixture = await api.search_fixture(query_text)
        if not fixture:
            await message.reply_text("❌ Match not found. Try: `Arsenal vs Chelsea`", parse_mode=ParseMode.MARKDOWN)
            return
        analysis = await predictor.deep_analyze(fixture["fixture"]["id"])
        text = formatter.format_deep_analysis(analysis)
        for chunk in _split_message(text):
            await message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        await message.reply_text(f"❌ Analysis failed: {str(e)}")


async def _send_deep_analysis(message, context, fixture_id: str):
    try:
        analysis = await predictor.deep_analyze(int(fixture_id))
        text = formatter.format_deep_analysis(analysis)
        for chunk in _split_message(text):
            await message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Deep analysis error: {e}")
        await message.reply_text(f"❌ Deep analysis failed: {str(e)}")


async def _send_fixtures(message, context):
    try:
        fixtures = await api.get_todays_fixtures()
        if not fixtures:
            await message.reply_text("No fixtures found for today.")
            return
        text = formatter.format_fixtures(fixtures[:20])
        keyboard = []
        for f in fixtures[:5]:
            fid = f["fixture"]["id"]
            home = f["teams"]["home"]["name"]
            away = f["teams"]["away"]["name"]
            keyboard.append([InlineKeyboardButton(f"🔍 {home} vs {away}", callback_data=f"deep_{fid}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        for chunk in _split_message(text):
            await message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
            reply_markup = None
    except Exception as e:
        logger.error(f"Fixtures error: {e}")
        await message.reply_text(f"❌ Failed to fetch fixtures: {str(e)}")


async def _show_settings(message, context):
    settings = context.bot_data.get("settings", {"auto_daily": True, "notifications": True})
    auto = "✅ ON" if settings.get("auto_daily") else "❌ OFF"
    notif = "✅ ON" if settings.get("notifications") else "❌ OFF"
    keyboard = [
        [InlineKeyboardButton(f"🕐 Auto Daily Ticket: {auto}", callback_data="toggle_auto_daily")],
        [InlineKeyboardButton(f"🔔 Notifications: {notif}", callback_data="toggle_notifications")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text("⚙️ *Settings*", reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)


# ─── DAILY SCHEDULER ──────────────────────────────────────────────────────────

async def scheduled_daily_ticket(context: ContextTypes.DEFAULT_TYPE):
    """Sends daily ticket to a configured channel/chat every morning at 7AM"""
    chat_id = context.job.data.get("chat_id")
    if not chat_id:
        return
    try:
        ticket = await predictor.build_daily_ticket()
        text = formatter.format_daily_ticket(ticket)
        for chunk in _split_message(text):
            await context.bot.send_message(chat_id=chat_id, text=chunk, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Scheduled ticket error: {e}")


async def subscribe_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Subscribe chat to receive daily ticket at 7 AM"""
    chat_id = update.effective_chat.id
    context.job_queue.run_daily(
        scheduled_daily_ticket,
        time=time(7, 0, 0),
        data={"chat_id": chat_id},
        name=f"daily_{chat_id}"
    )
    await update.message.reply_text(
        "✅ *Subscribed!*\nYou'll receive the 10-odds ticket every day at *7:00 AM*.",
        parse_mode=ParseMode.MARKDOWN
    )


async def unsubscribe_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs_by_name(f"daily_{chat_id}")
    for job in jobs:
        job.schedule_removal()
    await update.message.reply_text("❌ Unsubscribed from daily ticket.")


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _split_message(text: str, limit: int = 4000):
    """Split long messages to stay within Telegram's 4096 char limit"""
    if len(text) <= limit:
        return [text]
    chunks = []
    while len(text) > limit:
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:]
    if text:
        chunks.append(text)
    return chunks


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("addpick", addpick_cmd)],
        states={WAITING_MATCH_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_manual_pick)]},
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ticket", daily_ticket_cmd))
    app.add_handler(CommandHandler("analyze", analyze_cmd))
    app.add_handler(CommandHandler("fixtures", fixtures_cmd))
    app.add_handler(CommandHandler("subscribe", subscribe_daily))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe_daily))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("🚀 SportsOracle Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

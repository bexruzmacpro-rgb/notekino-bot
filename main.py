
import os
import re
import sqlite3
import logging

from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DATABASE_PATH", "notekino.db")

ADMIN_USERNAME = "bekxruzdeeee"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                code TEXT PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_seen TEXT NOT NULL
            )
        """)


def register_user(update):
    user = update.effective_user
    if not user:
        return

    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            INSERT OR IGNORE INTO users
            (user_id, username, first_seen)
            VALUES (?, ?, ?)
        """, (
            user.id,
            user.username,
            datetime.now(timezone.utc).isoformat()
        ))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update)

    await update.message.reply_text(
        "🎬 Notekino botiga xush kelibsiz!\n\n"
        "🔎 Kino kodini yuboring va filmni oling."
    )


async def stat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not user or (user.username or "").lower() != ADMIN_USERNAME.lower():
        await update.message.reply_text("⛔ Siz admin emassiz!")
        return

    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    week_ago = (now - timedelta(days=7)).isoformat()

    with sqlite3.connect(DB_PATH) as db:
        total = db.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        today_count = db.execute(
            "SELECT COUNT(*) FROM users WHERE substr(first_seen, 1, 10) = ?",
            (today,)
        ).fetchone()[0]

        week_count = db.execute(
            "SELECT COUNT(*) FROM users WHERE first_seen >= ?",
            (week_ago,)
        ).fetchone()[0]

    await update.message.reply_text(
        "📊 NOTEKINO BOT STATISTIKASI\n\n"
        f"👥 Jami foydalanuvchilar: {total}\n"
        f"🆕 Bugun qo‘shilganlar: {today_count}\n"
        f"📅 Oxirgi 7 kunda: {week_count}"
    )


async def save_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.channel_post
    if not message:
        return

    caption = message.caption or message.text or ""
    match = re.search(r"(?:kod\s*:\s*|#)([A-Za-z0-9_-]+)", caption, re.I)

    if not match:
        return

    code = match.group(1).upper()

    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            "INSERT OR REPLACE INTO movies VALUES (?, ?, ?)",
            (code, message.chat_id, message.message_id)
        )

    logger.info("Kino saqlandi: %s", code)


async def find_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update)

    code = update.message.text.strip().upper()

    if not re.fullmatch(r"[A-Z0-9_-]+", code):
        await update.message.reply_text("❌ Faqat kino kodini yuboring.")
        return

    with sqlite3.connect(DB_PATH) as db:
        result = db.execute(
            "SELECT chat_id, message_id FROM movies WHERE code = ?",
            (code,)
        ).fetchone()

    if not result:
        await update.message.reply_text(
            "😕 Bu kod bo‘yicha kino topilmadi."
        )
        return

    chat_id, message_id = result

    try:
        await context.bot.copy_message(
            chat_id=update.effective_chat.id,
            from_chat_id=chat_id,
            message_id=message_id
        )
    except Exception:
        logger.exception("Kinoni yuborishda xatolik")
        await update.message.reply_text(
            "Kino yuborilmadi. Keyinroq urinib ko‘ring."
        )


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN sozlanmagan!")

    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stat", stat))

    app.add_handler(
        MessageHandler(filters.ChatType.CHANNEL, save_movie)
    )

    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
            find_movie
        )
    )

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

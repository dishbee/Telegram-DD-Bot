import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask, request

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))  # Render gives the port via env var
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Your Render web service URL (without trailing slash)

logging.basicConfig(level=logging.INFO)

app_tg = ApplicationBuilder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(f"Your Telegram ID is: {user_id}")

app_tg.add_handler(CommandHandler("start", start))

# Flask app for webhook
flask_app = Flask(__name__)

@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), app_tg.bot)
    app_tg.update_queue.put_nowait(update)
    return "OK", 200

@flask_app.route("/set_webhook", methods=["GET"])
def set_webhook():
    app_tg.bot.set_webhook(f"{WEBHOOK_URL}/{TOKEN}")
    return "Webhook set!", 200

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=PORT)

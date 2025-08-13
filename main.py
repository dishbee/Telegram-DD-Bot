import os
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import threading
import json

TOKEN = os.getenv("BOT_TOKEN")  # Make sure BOT_TOKEN is set in Render
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Your Render app URL
PORT = int(os.getenv("PORT", "10000"))  # Render's dynamic port

app = Flask(__name__)

# === TELEGRAM BOT SETUP ===
application = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your Telegram ID is: {update.effective_user.id}")

application.add_handler(CommandHandler("start", start))

# Start Telegram bot in background
def run_bot():
    asyncio.run(application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}",
        drop_pending_updates=True
    ))

threading.Thread(target=run_bot).start()

# === SHOPIFY WEBHOOK ROUTE ===
@app.route("/webhooks/shopify", methods=["POST"])
def shopify_webhook():
    try:
        data = request.get_json()
        print("Received Shopify webhook:", data)
        # Here you can forward the data to Telegram or process it
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print("Error processing webhook:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    print(f"Starting Flask app on port {PORT}...")
    app.run(host="0.0.0.0", port=PORT)

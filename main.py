import os
import hmac
import hashlib
import base64
import json
from flask import Flask, request, abort

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- Environment variables ---
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://telegram-dd-bot.onrender.com
PORT = int(os.getenv("PORT", "10000"))  # Render provides PORT
SHOPIFY_WEBHOOK_SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET", "")

# --- Flask app ---
app = Flask(__name__)

# --- Telegram bot app (python-telegram-bot) ---
tg_app = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your Telegram ID is: {update.effective_user.id}")

tg_app.add_handler

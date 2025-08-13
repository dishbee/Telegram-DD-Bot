# main.py

import os
import json
import hmac
import hashlib
from flask import Flask, request
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DISPATCH_MAIN_CHAT_ID = os.environ.get("DISPATCH_MAIN_CHAT_ID")
SHOPIFY_WEBHOOK_SECRET = os.environ.get("SHOPIFY_WEBHOOK_SECRET")
VENDOR_GROUP_MAP = json.loads(os.environ.get("VENDOR_GROUP_MAP", "{}"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

bot = Bot(token=BOT_TOKEN)
app = Flask(__name__)

def verify_shopify_webhook(data, hmac_header):
    digest = hmac.new(SHOPIFY_WEBHOOK_SECRET.encode('utf-8'), data, hashlib.sha256).digest()
    calculated_hmac = digest.hex()
    return hmac.compare_digest(calculated_hmac, hmac_header)

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = request.get_json(force=True)
    print("Telegram update:", update)
    return "ok", 200

@app.route("/webhooks/shopify", methods=["POST"])
def shopify_webhook():
    data = request.get_data()
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256")
    if not verify_shopify_webhook(data, hmac_header):
        return "Unauthorized", 401

    payload = json.loads(data)
    print("Shopify webhook received:", json.dumps(payload, indent=2))

    order_number = payload.get("order_number")
    order_key = str(order_number)[-2:]
    line_items = payload.get("line_items", [])
    vendor_items = {}
    for item in line_items:
        vendor = item.get("vendor", "Unknown")
        vendor_items.setdefault(vendor, []).append(item)

    mdg_text = f"🟥 Order #{order_number}\n"
    for vendor, items in vendor_items.items():
        mdg_text += f"- {vendor}: {len(items)} items\n"

    bot.send_message(chat_id=DISPATCH_MAIN_CHAT_ID, text=mdg_text)

    for vendor, items in vendor_items.items():
        group_id = VENDOR_GROUP_MAP.get(vendor)
        if not group_id:
            continue
        vendor_text = f"🟥 Order #{order_number} for {vendor}\n{len(items)} products"
        keyboard = [[InlineKeyboardButton("Confirm", callback_data=f"confirm:{order_key}:{vendor}")]]
        markup = InlineKeyboardMarkup(keyboard)
        bot.send_message(chat_id=group_id, text=vendor_text, reply_markup=markup)

    return "ok", 200

@app.route("/")
def index():
    return "Bot is running", 200

@app.before_first_request
def set_webhook():
    bot.delete_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")

@app.route("/callback", methods=["POST"])
def callback():
    data = request.json
    print("Callback data:", data)
    return "ok", 200

def build_restaurant_buttons(order_key, vendor):
    labels = ["Works", "Later", "Will prepare"]
    row = []
    for lbl in labels:
        row.append({"text": lbl, "callback_data": f"rest_later:{order_key}:{vendor}:{lbl}"})
    return row

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

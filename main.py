import os
import json
import hmac
import hashlib
from flask import Flask, request
import requests

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
SHOPIFY_WEBHOOK_SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET")
DISPATCH_MAIN_CHAT_ID = os.getenv("DISPATCH_MAIN_CHAT_ID")
VENDOR_GROUP_MAP = json.loads(os.getenv("VENDOR_GROUP_MAP", "{}"))

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# --- Helper functions ---

def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload)

def edit_message(chat_id, message_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(f"{TELEGRAM_API_URL}/editMessageText", json=payload)

def verify_shopify_webhook(data, hmac_header):
    digest = hmac.new(
        SHOPIFY_WEBHOOK_SECRET.encode('utf-8'),
        data,
        hashlib.sha256
    ).digest()
    calculated_hmac = digest.hex()
    return hmac.compare_digest(calculated_hmac, hmac_header.lower())

# --- Telegram Webhook Route ---

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = request.get_json()
    if "callback_query" in update:
        handle_callback_query(update["callback_query"])
    elif "message" in update:
        handle_message(update["message"])
    return "ok"

def handle_message(message):
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    if text.lower() == "/start":
        send_message(chat_id, "Welcome! You are now connected to Dishbee Dispatch Bot.")

def handle_callback_query(callback_query):
    data = callback_query["data"]
    chat_id = callback_query["message"]["chat"]["id"]
    message_id = callback_query["message"]["message_id"]

    if data.startswith("rest_confirm:"):
        edit_message(chat_id, message_id, "✅ Vendor confirmed preparation")
    elif data.startswith("rest_later:"):
        edit_message(chat_id, message_id, "⏳ Vendor will prepare later")
    elif data.startswith("rest_willprepare:"):
        edit_message(chat_id, message_id, "🟡 Vendor will prepare soon")

# --- Shopify Webhook Route ---

@app.route("/webhooks/shopify", methods=["POST"])
def shopify_webhook():
    data = request.get_data()
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "")

    if not verify_shopify_webhook(data, hmac_header):
        return "Unauthorized", 401

    order = request.get_json()
    order_number = order.get("order_number", "")
    vendors = {}
    for item in order.get("line_items", []):
        vendor = item.get("vendor", "Unknown")
        vendors.setdefault(vendor, []).append(item)

    # Send to main dispatch group
    mdg_text = f"🆕 New Order #{order_number}\n"
    for vendor, items in vendors.items():
        mdg_text += f"\n<b>{vendor}</b> — {len(items)} items"
    send_message(DISPATCH_MAIN_CHAT_ID, mdg_text)

    # Send to vendor groups
    for vendor, items in vendors.items():
        if vendor in VENDOR_GROUP_MAP:
            group_id = VENDOR_GROUP_MAP[vendor]
            vendor_text = f"Order #{order_number} for {vendor} — {len(items)} products"
            keyboard = {
                "inline_keyboard": [[
                    {"text": "✅ Works", "callback_data": f"rest_confirm:{order_number}:{vendor}"},
                    {"text": "⏳ Later", "callback_data": f"rest_later:{order_number}:{vendor}"},
                    {"text": "🟡 Will prepare", "callback_data": f"rest_willprepare:{order_number}:{vendor}"}
                ]]
            }
            send_message(group_id, vendor_text, reply_markup=keyboard)

    return "ok"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

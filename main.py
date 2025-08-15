import os
import json
import hmac
import hashlib
import base64
from flask import Flask, request
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_SECRET = os.environ.get("SHOPIFY_WEBHOOK_SECRET")
DISPATCH_MAIN_CHAT_ID = os.environ.get("DISPATCH_MAIN_CHAT_ID")
VENDOR_GROUP_MAP = json.loads(os.environ.get("VENDOR_GROUP_MAP", "{}"))

bot = Bot(token=BOT_TOKEN)

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = request.get_json()
    print("Received Telegram update:", update)
    return "OK"

@app.route("/webhooks/shopify", methods=["POST"])
def shopify_webhook():
    data = request.get_data()
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256")

    if not verify_webhook(data, hmac_header):
        return "Unauthorized", 401

    payload = request.get_json()
    print("Received Shopify order:", json.dumps(payload, indent=2))

    order_name = payload.get("name", "Unknown")
    customer = payload.get("customer", {})
    customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
    phone = customer.get("phone", "N/A")
    address = format_address(payload.get("shipping_address") or {})
    items = payload.get("line_items", [])
    note = payload.get("note", "")
    delivery_time = payload.get("delivery_method", {}).get("requested_fulfillment_time") or "ASAP"
    vendor_tags = payload.get("tags", "").split(",")

    product_lines = "\n".join([f"- {item['quantity']} x {item['name']}" for item in items])
    full_message = (
        f"🟥 NEW ORDER ({order_name})\n"
        f"👤 Customer: {customer_name}\n"
        f"📍 Address: {address}\n"
        f"📞 Phone: {phone}\n"
        f"🕒 Time: {delivery_time}\n"
        f"🛒 Items:\n{product_lines}"
    )
    if note:
        full_message += f"\n📝 Note: {note}"

    bot.send_message(chat_id=DISPATCH_MAIN_CHAT_ID, text=full_message)

    for vendor in vendor_tags:
        group_id = VENDOR_GROUP_MAP.get(vendor.strip())
        if group_id:
            vendor_msg = (
                f"🟥 NEW ORDER ({order_name})\n"
                f"🛒 Items:\n{product_lines}\n"
                f"🕒 Time: {delivery_time}"
            )
            if note:
                vendor_msg += f"\n📝 Note: {note}"

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Expand ⬇", callback_data=f"expand_{order_name}_{vendor.strip()}")]
            ])
            bot.send_message(chat_id=group_id, text=vendor_msg, reply_markup=keyboard)

    return "OK"

def format_address(address):
    return f"{address.get('address1', '')}, {address.get('city', '')}"

def verify_webhook(data, hmac_header):
    computed_hmac = hmac.new(WEBHOOK_SECRET.encode('utf-8'), data, hashlib.sha256).digest()
    computed_hmac_b64 = base64.b64encode(computed_hmac).decode('utf-8')
    return hmac.compare_digest(computed_hmac_b64, hmac_header or "")

if __name__ == "__main__":
    app.run()

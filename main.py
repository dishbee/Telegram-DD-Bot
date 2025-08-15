# telegram_dispatch_bot/main.py

from flask import Flask, request, jsonify
import telegram
import hmac
import hashlib
import os
import json

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
SHOPIFY_WEBHOOK_SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET")
DISPATCH_MAIN_CHAT_ID = int(os.getenv("DISPATCH_MAIN_CHAT_ID"))
VENDOR_GROUP_MAP = json.loads(os.getenv("VENDOR_GROUP_MAP", '{}'))  # JSON string: {"VendorName": chat_id}

bot = telegram.Bot(token=BOT_TOKEN)

# --- Helpers ---

def verify_shopify_webhook(data, hmac_header):
    hash_digest = hmac.new(
        SHOPIFY_WEBHOOK_SECRET.encode("utf-8"),
        data,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(hmac_header, hash_digest)

def format_main_dispatch_message(order):
    customer = order.get("customer", {})
    shipping_address = order.get("shipping_address", {})
    line_items = order.get("line_items", [])
    vendors = {}

    for item in line_items:
        vendor = item.get("vendor", "Unknown")
        if vendor not in vendors:
            vendors[vendor] = []
        vendors[vendor].append(f"- {item.get('quantity')}x {item.get('title')}")

    lines = [
        f"🟥 *NEW ORDER* #{order.get('order_number')}\n",
        f"👤 {customer.get('first_name', '')} {customer.get('last_name', '')}",
        f"📍 {shipping_address.get('address1', '')}, {shipping_address.get('city', '')}",
        f"📞 {shipping_address.get('phone', customer.get('phone', 'N/A'))}",
        f"🕒 {order.get('created_at')} (asap/requested time TBD)",
        "\n🍽 *VENDORS:*"
    ]

    for vendor, items in vendors.items():
        lines.append(f"\n🍴 *{vendor}*\n" + "\n".join(items))

    return "\n".join(lines), vendors

def format_vendor_message(items):
    return f"🧾 *New Order*\n\n" + "\n".join(items)

def format_vendor_hidden_detail(order):
    customer = order.get("customer", {})
    shipping_address = order.get("shipping_address", {})
    return (
        f"👤 {customer.get('first_name', '')} {customer.get('last_name', '')}\n"
        f"📍 {shipping_address.get('address1', '')}, {shipping_address.get('city', '')}\n"
        f"📞 {shipping_address.get('phone', customer.get('phone', 'N/A'))}"
    )

# --- Routes ---

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)

    if update.callback_query:
        query = update.callback_query
        data = query.data

        if data.startswith("expand:") or data.startswith("collapse:"):
            parts = data.split(":")
            if len(parts) < 3:
                return "bad data", 400
            vendor = parts[1]
            detail = parts[2]

            if data.startswith("expand:"):
                bot.edit_message_text(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    text=query.message.text + "\n\n" + detail,
                    parse_mode=telegram.ParseMode.MARKDOWN,
                    reply_markup=telegram.InlineKeyboardMarkup([
                        [telegram.InlineKeyboardButton("🔼 Hide Details", callback_data=f"collapse:{vendor}:{detail}")]
                    ])
                )
            elif data.startswith("collapse:"):
                lines = query.message.text.split("\n\n")[0]
                bot.edit_message_text(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    text=lines,
                    parse_mode=telegram.ParseMode.MARKDOWN,
                    reply_markup=telegram.InlineKeyboardMarkup([
                        [telegram.InlineKeyboardButton("🔽 Show Details", callback_data=f"expand:{vendor}:{detail}")]
                    ])
                )

    return "ok"


@app.route("/webhooks/shopify", methods=["POST"])
def shopify_webhook():
    data = request.data
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256")

    if not verify_shopify_webhook(data, hmac_header):
        return "Unauthorized", 401

    order = request.get_json()

    # Send to main dispatch group with full formatting
    mdg_message, vendors = format_main_dispatch_message(order)
    bot.send_message(chat_id=DISPATCH_MAIN_CHAT_ID, text=mdg_message, parse_mode=telegram.ParseMode.MARKDOWN)

    # Send per-vendor summaries with expand button
    for vendor, items in vendors.items():
        if vendor in VENDOR_GROUP_MAP:
            short_msg = format_vendor_message(items)
            detail = format_vendor_hidden_detail(order)
            reply_markup = telegram.InlineKeyboardMarkup([
                [telegram.InlineKeyboardButton("🔽 Show Details", callback_data=f"expand:{vendor}:{detail}")]
            ])
            bot.send_message(chat_id=VENDOR_GROUP_MAP[vendor], text=short_msg, parse_mode=telegram.ParseMode.MARKDOWN, reply_markup=reply_markup)

    return "ok"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

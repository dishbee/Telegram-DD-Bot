# telegram_dispatch_bot/main.py

from flask import Flask, request, jsonify
import telegram
import hmac
import hashlib
import os
import json
from datetime import datetime, timedelta

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
SHOPIFY_WEBHOOK_SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET")
DISPATCH_MAIN_CHAT_ID = int(os.getenv("DISPATCH_MAIN_CHAT_ID"))
VENDOR_GROUP_MAP = json.loads(os.getenv("VENDOR_GROUP_MAP", '{}'))

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

def build_mdg_buttons(order):
    order_number = order.get("order_number", "?")
    return telegram.InlineKeyboardMarkup([
        [
            telegram.InlineKeyboardButton(f"#{str(order_number)[-2:]} ASAP?", callback_data=f"mdg_asap:{order_number}"),
            telegram.InlineKeyboardButton("Request TIME", callback_data=f"mdg_time:{order_number}"),
        ],
        [
            telegram.InlineKeyboardButton("Request EXACT TIME", callback_data=f"mdg_exact:{order_number}"),
            telegram.InlineKeyboardButton("Same time as...", callback_data=f"mdg_same:{order_number}"),
        ]
    ])

def build_time_options(order_number):
    now = datetime.now()
    options = []
    for i in range(1, 5):
        future_time = now + timedelta(minutes=10 * i)
        label = future_time.strftime("%H:%M")
        options.append(telegram.InlineKeyboardButton(label, callback_data=f"mdg_time_select:{order_number}:{label}"))
    return telegram.InlineKeyboardMarkup.from_row(options)

pending_exact_time = {}
recent_orders = []

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

        elif data.startswith("mdg_asap:"):
            order_number = data.split(":")[1]
            bot.send_message(chat_id=query.message.chat.id, text=f"ASAP requested for order #{order_number}")
            query.answer()

        elif data.startswith("mdg_time:"):
            order_number = data.split(":")[1]
            reply_markup = build_time_options(order_number)
            bot.send_message(chat_id=query.message.chat.id, text=f"When should order #{order_number} be prepared?", reply_markup=reply_markup)
            query.answer()

        elif data.startswith("mdg_time_select:"):
            parts = data.split(":")
            order_number = parts[1]
            selected_time = parts[2]
            bot.send_message(chat_id=query.message.chat.id, text=f"⏰ Requested time for order #{order_number}: {selected_time}?")
            query.answer()

        elif data.startswith("mdg_exact:"):
            order_number = data.split(":")[1]
            user_id = query.from_user.id
            pending_exact_time[user_id] = order_number
            bot.send_message(chat_id=query.message.chat.id, text=f"Please send exact time (HH:MM) for order #{order_number}")
            query.answer()

        elif data.startswith("mdg_same:"):
            order_number = data.split(":")[1]
            buttons = []
            for prev in recent_orders[-3:][::-1]:
                label = f"Same as #{prev['number']} – {prev['name']}"
                cb_data = f"mdg_same_select:{order_number}:{prev['number']}"
                buttons.append([telegram.InlineKeyboardButton(label, callback_data=cb_data)])
            reply_markup = telegram.InlineKeyboardMarkup(buttons)
            bot.send_message(chat_id=query.message.chat.id, text=f"Choose an order to copy time from:", reply_markup=reply_markup)
            query.answer()

        elif data.startswith("mdg_same_select:"):
            _, current, previous = data.split(":")
            bot.send_message(chat_id=query.message.chat.id, text=f"🔁 Requested same time as order #{previous} for order #{current}")
            query.answer()

    elif update.message:
        user_id = update.message.from_user.id
        if user_id in pending_exact_time:
            order_number = pending_exact_time.pop(user_id)
            text = update.message.text.strip()
            bot.send_message(chat_id=DISPATCH_MAIN_CHAT_ID, text=f"⏰ Requested exact time for order #{order_number}: {text}")

    return "ok"


@app.route("/webhooks/shopify", methods=["POST"])
def shopify_webhook():
    data = request.data
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256")

    # DEBUG: Log all incoming webhook data
    print("--- Shopify webhook received ---")
    print("Headers:", dict(request.headers))
    print("Body:", data.decode())

    # TEMPORARILY DISABLED for local testing – re-enable before production
    # if not verify_shopify_webhook(data, hmac_header):
    #     print("❌ HMAC verification failed")
    #     return "Unauthorized", 401

    print("✅ HMAC check skipped for testing")
    order = request.get_json()
    print("Parsed Order:", order)

    mdg_message, vendors = format_main_dispatch_message(order)
    mdg_buttons = build_mdg_buttons(order)
    bot.send_message(chat_id=DISPATCH_MAIN_CHAT_ID, text=mdg_message, parse_mode=telegram.ParseMode.MARKDOWN, reply_markup=mdg_buttons)

    customer = order.get("customer", {})
    recent_orders.append({
        "number": order.get("order_number"),
        "name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
    })
    if len(recent_orders) > 10:
        recent_orders.pop(0)

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

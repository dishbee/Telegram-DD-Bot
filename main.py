import os
import json
import hmac
import hashlib
import base64
import asyncio
from flask import Flask, request
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_SECRET = os.environ.get("SHOPIFY_WEBHOOK_SECRET")
DISPATCH_MAIN_CHAT_ID = int(os.environ.get("DISPATCH_MAIN_CHAT_ID"))
VENDOR_GROUP_MAP = json.loads(os.environ.get("VENDOR_GROUP_MAP", "{}"))
DRIVERS = json.loads(os.environ.get("DRIVERS", "{}"))

bot = Bot(token=BOT_TOKEN)
application = Application.builder().token(BOT_TOKEN).build()

order_message_map = {}  # {order_id: {"dispatch_msg_id": int, "vendor_msgs": {vendor: msg_id}, "status": str, "assigned_to": str}}

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    asyncio.run(application.process_update(update))
    return "OK"

@app.route("/webhooks/shopify", methods=["POST"])
def shopify_webhook():
    data = request.get_data()
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256")
    if not verify_webhook(data, hmac_header):
        return "Unauthorized", 401

    payload = request.get_json()
    print("Received Shopify order:", json.dumps(payload, indent=2))

    order_id = str(payload.get("id"))
    order_name = payload.get("name", "Unknown")
    customer = payload.get("customer", {})
    customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
    phone = customer.get("phone", "N/A")
    address = format_address(payload.get("shipping_address") or {})
    items = payload.get("line_items", [])
    note = payload.get("note", "")
    delivery_time = payload.get("delivery_method", {}).get("requested_fulfillment_time") or "ASAP"
    vendor_tags = [v.strip() for v in payload.get("tags", "").split(",") if v.strip()]

    product_lines = "\n".join([f"- {item['quantity']} x {item['name']}" for item in items])
    short_status = "🟥 New"
    full_message = (
        f"🟥 *NEW ORDER* ({order_name})\n"
        f"👤 *Customer:* {customer_name}\n"
        f"📍 *Address:* {address}\n"
        f"📞 *Phone:* {phone}\n"
        f"🕒 *Time:* {delivery_time}\n"
        f"🛒 *Items:*\n{product_lines}"
    )
    if note:
        full_message += f"\n📝 *Note:* {note}"
    full_message += f"\n\nStatus: {short_status}"

    msg = bot.send_message(chat_id=DISPATCH_MAIN_CHAT_ID, text=full_message, parse_mode=ParseMode.MARKDOWN)
    order_message_map[order_id] = {"dispatch_msg_id": msg.message_id, "vendor_msgs": {}, "status": "🟥", "assigned_to": None}

    for vendor in vendor_tags:
        group_id = VENDOR_GROUP_MAP.get(vendor)
        if group_id:
            vendor_msg = (
                f"🟥 *NEW ORDER* ({order_name})\n"
                f"🛒 *Items:*\n{product_lines}\n"
                f"🕒 *Time:* {delivery_time}"
            )
            if note:
                vendor_msg += f"\n📝 *Note:* {note}"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Expand ⬇", callback_data=f"expand|{order_id}|{vendor}"),
                 InlineKeyboardButton("Works", callback_data=f"reply|{order_id}|{vendor}|Works")],
                [InlineKeyboardButton("Later", callback_data=f"reply|{order_id}|{vendor}|Later"),
                 InlineKeyboardButton("Will prepare", callback_data=f"reply|{order_id}|{vendor}|Will prepare")]
            ])
            msg = bot.send_message(chat_id=group_id, text=vendor_msg, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
            order_message_map[order_id]["vendor_msgs"][vendor] = msg.message_id

    return "OK"

def format_address(address):
    return f"{address.get('address1', '')}, {address.get('city', '')}"

def verify_webhook(data, hmac_header):
    computed_hmac = hmac.new(WEBHOOK_SECRET.encode('utf-8'), data, hashlib.sha256).digest()
    computed_hmac_b64 = base64.b64encode(computed_hmac).decode('utf-8')
    return hmac.compare_digest(computed_hmac_b64, hmac_header or "")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    data = query.data.split("|")
    if data[0] == "reply":
        _, order_id, vendor, reply_text = data
        text = f"🍴 *{vendor}* replied: “{reply_text}”"
        msg_id = order_message_map.get(order_id, {}).get("dispatch_msg_id")
        if msg_id:
            await bot.send_message(chat_id=DISPATCH_MAIN_CHAT_ID, text=text, parse_mode=ParseMode.MARKDOWN)
    elif data[0] == "expand":
        _, order_id, vendor = data
        # Placeholder: implement expand/hide logic later
        await query.edit_message_text(text="[Full vendor message would go here]")

application.add_handler(CallbackQueryHandler(handle_callback))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    

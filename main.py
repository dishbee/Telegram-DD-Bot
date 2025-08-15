# telegram_dispatch_bot/main.py

from flask import Flask, request
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
import hmac
import hashlib
import os
import json
import threading
import asyncio
from datetime import datetime, timedelta

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
SHOPIFY_WEBHOOK_SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET")
DISPATCH_MAIN_CHAT_ID = int(os.getenv("DISPATCH_MAIN_CHAT_ID"))
VENDOR_GROUP_MAP = json.loads(os.getenv("VENDOR_GROUP_MAP", '{}'))  # {"VendorName": chat_id}
COURIER_MAP = json.loads(os.getenv("COURIER_MAP", '{}'))  # {"Paul": user_id, "Jamil": user_id}

bot = telegram.Bot(token=BOT_TOKEN)

# track vendor replies by group chat
ORDER_STATUS_RESPONSES = {"works", "later", "will prepare"}
ORDER_VENDOR_LOOKUP = {}  # message_id -> (vendor_name, order_number)
pending_exact_time: dict[int, str] = {}
recent_orders: list[dict] = []
order_assignments: dict[str, dict] = {}  # order_number -> {'vendor_confirmed': True, 'courier_assigned': False, 'courier': 'Paul'}

# ----------- Safe asyncio thread runner -----------
async_loop = asyncio.new_event_loop()
threading.Thread(target=async_loop.run_forever, daemon=True).start()

def run_async(coro):
    asyncio.run_coroutine_threadsafe(coro, async_loop)

# ----------------- Helpers -----------------

def verify_shopify_webhook(data: bytes, hmac_header: str | None) -> bool:
    if not hmac_header or not SHOPIFY_WEBHOOK_SECRET:
        return False
    digest = hmac.new(SHOPIFY_WEBHOOK_SECRET.encode("utf-8"), data, hashlib.sha256).hexdigest()
    return hmac.compare_digest(hmac_header, digest)

def format_main_dispatch_message(order: dict):
    customer = order.get("customer", {}) or {}
    shipping = order.get("shipping_address", {}) or {}
    items = order.get("line_items", []) or []

    vendors: dict[str, list[str]] = {}
    for it in items:
        vendor = it.get("vendor") or "Unknown"
        vendors.setdefault(vendor, []).append(f"- {it.get('quantity', 1)}x {it.get('title', 'Item')}")

    lines = [
        f"🟥 *NEW ORDER* #{order.get('order_number', '?')}\n",
        f"👤 {customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
        f"📍 {shipping.get('address1', '')}, {shipping.get('city', '')}",
        f"📞 {shipping.get('phone', customer.get('phone', 'N/A'))}",
        f"🕒 {order.get('created_at', '')} (asap/requested time TBD)",
        "\n🍽 *VENDORS:*",
    ]

    for v, lst in vendors.items():
        lines.append(f"\n🍴 *{v}*\n" + "\n".join(lst))

    return "\n".join(lines), vendors

def format_vendor_message(items: list[str]) -> str:
    return "🧾 *New Order*\n\n" + "\n".join(items)

def format_vendor_hidden_detail(order: dict) -> str:
    customer = order.get("customer", {}) or {}
    shipping = order.get("shipping_address", {}) or {}
    return (
        f"👤 {customer.get('first_name', '')} {customer.get('last_name', '')}\n"
        f"📍 {shipping.get('address1', '')}, {shipping.get('city', '')}\n"
        f"📞 {shipping.get('phone', customer.get('phone', 'N/A'))}"
    )

def build_mdg_buttons(order: dict) -> InlineKeyboardMarkup:
    onum = order.get("order_number", "?")
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"#{str(onum)[-2:]} ASAP?", callback_data=f"mdg_asap:{onum}"),
            InlineKeyboardButton("Request TIME", callback_data=f"mdg_time:{onum}"),
        ],
        [
            InlineKeyboardButton("Request EXACT TIME", callback_data=f"mdg_exact:{onum}"),
            InlineKeyboardButton("Same time as...", callback_data=f"mdg_same:{onum}"),
        ],
    ])

def build_time_options(order_number: int | str) -> InlineKeyboardMarkup:
    now = datetime.now()
    buttons = []
    for i in range(1, 5):
        t = now + timedelta(minutes=10 * i)
        label = t.strftime("%H:%M")
        buttons.append(InlineKeyboardButton(label, callback_data=f"mdg_time_select:{order_number}:{label}"))
    return InlineKeyboardMarkup.from_row(buttons)

def build_courier_buttons(order_number: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(f"🛵 {name}", callback_data=f"assign:{order_number}:{name}")
        for name in COURIER_MAP.keys()
    ]
    return InlineKeyboardMarkup.from_column(buttons)

# ----------------- Flask Routes -----------------

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)

    if update.callback_query:
        data = update.callback_query.data
        if data.startswith("assign:"):
            _, order_number, courier_name = data.split(":")
            courier_id = COURIER_MAP.get(courier_name)
            if courier_id:
                run_async(bot.send_message(chat_id=courier_id, text=f"📦 You’ve been assigned order #{order_number}"))
                run_async(bot.send_message(chat_id=DISPATCH_MAIN_CHAT_ID, text=f"🟨 Assigned to {courier_name} (order #{order_number})"))
                order_assignments[order_number] = {
                    'vendor_confirmed': True,
                    'courier_assigned': True,
                    'courier': courier_name
                }

    return "ok"

@app.route("/webhooks/shopify", methods=["POST"])
def shopify_webhook():
    data = request.get_data()
    verified = verify_shopify_webhook(data, request.headers.get("X-Shopify-Hmac-Sha256"))
    if not verified:
        return "unauthorized", 401

    order = json.loads(data)
    recent_orders.append(order)
    mdg_message, vendors = format_main_dispatch_message(order)

    run_async(bot.send_message(chat_id=DISPATCH_MAIN_CHAT_ID, text=mdg_message, parse_mode=ParseMode.MARKDOWN, reply_markup=build_mdg_buttons(order)))

    for vendor, items in vendors.items():
        group_id = VENDOR_GROUP_MAP.get(vendor)
        if not group_id:
            continue
        summary = format_vendor_message(items)
        details = format_vendor_hidden_detail(order)
        full_text = summary + f"\n\n⬇️ Tap to expand\n\n||{details}||"
        run_async(bot.send_message(chat_id=group_id, text=full_text, parse_mode=ParseMode.MARKDOWN))

    return "ok"

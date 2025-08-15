# telegram_dispatch_bot/main.py

from flask import Flask, request
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
import hmac
import hashlib
import os
import json
import asyncio
from datetime import datetime, timedelta

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
SHOPIFY_WEBHOOK_SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET")
DISPATCH_MAIN_CHAT_ID = int(os.getenv("DISPATCH_MAIN_CHAT_ID"))
VENDOR_GROUP_MAP = json.loads(os.getenv("VENDOR_GROUP_MAP", '{}'))  # {"VendorName": chat_id}

bot = telegram.Bot(token=BOT_TOKEN)

# track vendor replies by group chat
ORDER_STATUS_RESPONSES = {"works", "later", "will prepare"}
ORDER_VENDOR_LOOKUP = {}  # message_id -> (vendor_name, order_number)


def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        asyncio.run(coro)

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

pending_exact_time: dict[int, str] = {}
recent_orders: list[dict] = []

# ----------------- Telegram webhook -----------------

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)

    if update.callback_query:
        q = update.callback_query
        data = q.data or ""

        if data.startswith("expand:") or data.startswith("collapse:"):
            parts = data.split(":", 2)
            if len(parts) < 3:
                return "bad data", 400
            vendor, detail = parts[1], parts[2]
            if data.startswith("expand:"):
                run_async(bot.edit_message_text(
                    chat_id=q.message.chat.id,
                    message_id=q.message.message_id,
                    text=q.message.text + "\n\n" + detail,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔼 Hide Details", callback_data=f"collapse:{vendor}:{detail}")]])
                ))
            else:
                base = q.message.text.split("\n\n")[0]
                run_async(bot.edit_message_text(
                    chat_id=q.message.chat.id,
                    message_id=q.message.message_id,
                    text=base,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔽 Show Details", callback_data=f"expand:{vendor}:{detail}")]])
                ))

        elif data.startswith("mdg_asap:"):
            onum = data.split(":")[1]
            run_async(bot.send_message(chat_id=q.message.chat.id, text=f"ASAP requested for order #{onum}"))
            q.answer()

        elif data.startswith("mdg_time:"):
            onum = data.split(":")[1]
            run_async(bot.send_message(
                chat_id=q.message.chat.id,
                text=f"When should order #{onum} be prepared?",
                reply_markup=build_time_options(onum)
            ))
            q.answer()

        elif data.startswith("mdg_time_select:"):
            _, onum, selected = data.split(":")
            run_async(bot.send_message(chat_id=q.message.chat.id, text=f"⏰ Requested time for order #{onum}: {selected}?"))
            q.answer()

        elif data.startswith("mdg_exact:"):
            onum = data.split(":")[1]
            pending_exact_time[q.from_user.id] = onum
            run_async(bot.send_message(chat_id=q.message.chat.id, text=f"Please send exact time (HH:MM) for order #{onum}"))
            q.answer()

        elif data.startswith("mdg_same:"):
            onum = data.split(":")[1]
            rows = []
            for prev in recent_orders[-3:][::-1]:
                label = f"Same as #{prev['number']} – {prev['name']}"
                rows.append([InlineKeyboardButton(label, callback_data=f"mdg_same_select:{onum}:{prev['number']}")])
            run_async(bot.send_message(chat_id=q.message.chat.id, text="Choose an order to copy time from:", reply_markup=InlineKeyboardMarkup(rows or [[InlineKeyboardButton("No previous orders", callback_data="noop")]])))
            q.answer()

        elif data.startswith("mdg_same_select:"):
            _, current_onum, prev_onum = data.split(":")
            run_async(bot.send_message(chat_id=q.message.chat.id, text=f"🔁 Requested same time as order #{prev_onum} for order #{current_onum}"))
            q.answer()

    elif update.message:
        uid = update.message.from_user.id
        chat_id = update.message.chat.id
        txt = (update.message.text or "").strip().lower()

        if uid in pending_exact_time:
            onum = pending_exact_time.pop(uid)
            run_async(bot.send_message(chat_id=DISPATCH_MAIN_CHAT_ID, text=f"⏰ Requested exact time for order #{onum}: {update.message.text}"))

        elif txt in ORDER_STATUS_RESPONSES:
            # find vendor by chat_id
            vendor = None
            for name, vid in VENDOR_GROUP_MAP.items():
                if vid == chat_id:
                    vendor = name
                    break
            # get last order number
            last_order = recent_orders[-1]['number'] if recent_orders else "?"
            if vendor:
                run_async(bot.send_message(
                    chat_id=DISPATCH_MAIN_CHAT_ID,
                    text=f"🍴 {vendor}: ✅ {txt.title()} (for order #{last_order})"
                ))

    return "ok"


# ----------------- Shopify webhook -----------------

@app.route("/webhooks/shopify", methods=["POST"])
def shopify_webhook():
    data = request.data
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256")

    print("--- Shopify webhook received ---")
    print("Headers:", dict(request.headers))
    print("Body:", data.decode(errors="ignore"))

    # if not verify_shopify_webhook(data, hmac_header):
    #     print("❌ HMAC verification failed")
    #     return "Unauthorized", 401

    print("✅ HMAC check skipped for testing")
    order = request.get_json(force=True, silent=True) or {}
    print("Parsed Order:", order)

    mdg_message, vendors = format_main_dispatch_message(order)
    run_async(bot.send_message(chat_id=DISPATCH_MAIN_CHAT_ID, text=mdg_message, parse_mode=ParseMode.MARKDOWN, reply_markup=build_mdg_buttons(order)))

    cust = order.get("customer", {}) or {}
    recent_orders.append({
        "number": order.get("order_number"),
        "name": f"{cust.get('first_name', '')} {cust.get('last_name', '')}".strip() or "Unknown"
    })
    if len(recent_orders) > 10:
        recent_orders.pop(0)

    for vendor, items in vendors.items():
        chat_id = VENDOR_GROUP_MAP.get(vendor)
        if chat_id:
            short_msg = format_vendor_message(items)
            detail = format_vendor_hidden_detail(order)
            run_async(bot.send_message(
                chat_id=chat_id,
                text=short_msg,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔽 Show Details", callback_data=f"expand:{vendor}:{detail}")]])
            ))

    return "ok"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

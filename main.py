# Telegram Dispatch Bot — Full Assignment Implementation (Webhook-only, PTB v20)
# Features:
# - Shopify → MDG dispatch message with status line (🟥/🟨/🟩/🟧)
# - Vendor group messages (items + time + optional note)
# - Vendor inline buttons: Expand ⬇/Hide ⬆, Works, Later, Will prepare
# - Vendor replies reposted to MDG as new messages
# - MDG inline buttons: Assign to <driver>, Delivered, Delay
# - Driver assignment sends DM + updates MDG status to 🟨
# - Delivered/Delayed update MDG status to 🟩/🟧
# - "Same time as" in vendor messages (lists other vendors from same order)
# - Robust HMAC verification, single-loop async execution per request
# - Avoids polling; avoids PTB Application; avoids connection-pool exhaustion

import os
import json
import hmac
import hashlib
import base64
import asyncio
from typing import Dict, Any, List
from flask import Flask, request
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest

app = Flask(__name__)

# --- ENV ---
BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_SECRET = os.environ["SHOPIFY_WEBHOOK_SECRET"]
DISPATCH_MAIN_CHAT_ID = int(os.environ["DISPATCH_MAIN_CHAT_ID"])  # e.g., -100123...
VENDOR_GROUP_MAP: Dict[str, int] = json.loads(os.environ.get("VENDOR_GROUP_MAP", "{}"))  # {"Vendor": -100...}
DRIVERS: Dict[str, int] = json.loads(os.environ.get("DRIVERS", "{}"))  # {"Anna": 123456789, "Max": 987654321}

# Configure request with larger pool to prevent pool timeout under burst
request_cfg = HTTPXRequest(
    connection_pool_size=32,
    pool_timeout=20.0,
    read_timeout=20.0,
    write_timeout=20.0,
    connect_timeout=10.0,
)
bot = Bot(token=BOT_TOKEN, request=request_cfg)

# --- STATE ---
# Keeps minimal state per order to support edits & callbacks (in-memory; reset on deploy)
STATE: Dict[str, Dict[str, Any]] = {}
# STATE[order_id] = {
#   "name": str,
#   "delivery_time": str,
#   "customer": {"name": str, "phone": str, "address": str},
#   "items_text": str,
#   "note": str or "",
#   "vendors": List[str],
#   "dispatch_msg_id": int,
#   "vendor_msgs": {vendor: msg_id},
#   "vendor_expanded": {vendor: bool},
#   "status": "🟥"|"🟨"|"🟩"|"🟧",
#   "assigned_to": str|None
# }

# --- HELPERS ---
def verify_webhook(raw: bytes, hmac_header: str) -> bool:
    computed = hmac.new(WEBHOOK_SECRET.encode("utf-8"), raw, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(computed).decode("utf-8"), hmac_header or "")

def fmt_address(addr: Dict[str, Any]) -> str:
    if not addr:
        return ""
    parts = [addr.get("address1"), addr.get("address2"), addr.get("city"), addr.get("zip"), addr.get("country")]
    return ", ".join([p for p in parts if p])

def build_dispatch_text(order: Dict[str, Any]) -> str:
    note = order.get("note")
    status_emoji = order.get("status", "🟥")
    assigned = order.get("assigned_to")
    status_line = f"Status: {status_emoji}"
    if status_emoji == "🟨" and assigned:
        status_line += f" — Assigned to {assigned}"
    text = (
        f"🟥 *NEW ORDER* ({order['name']})\n"
        f"👤 *Customer:* {order['customer']['name']}\n"
        f"📍 *Address:* {order['customer']['address']}\n"
        f"📞 *Phone:* {order['customer']['phone']}\n"
        f"🕒 *Time:* {order['delivery_time']}\n"
        f"🛒 *Items:*\n{order['items_text']}"
    )
    if note:
        text += f"\n📝 *Note:* {note}"
    text += f"\n\n{status_line}"
    return text

def build_vendor_text(order: Dict[str, Any], vendor: str, expanded: bool) -> str:
    note = order.get("note")
    other_vendors = [v for v in order["vendors"] if v != vendor]
    same_time_line = f"\n🕒 Same time as {', '.join(other_vendors)}" if other_vendors else ""
    if expanded:
        customer_block = (
            f"👤 *Customer:* {order['customer']['name']}\n"
            f"📍 *Address:* {order['customer']['address']}\n"
            f"📞 *Phone:* {order['customer']['phone']}\n"
        )
    else:
        customer_block = ""
    text = (
        f"🟥 *NEW ORDER* ({order['name']})\n"
        f"🛒 *Items:*\n{order['items_text']}\n"
        f"🕒 *Time:* {order['delivery_time']}"
        f"{same_time_line}"
    )
    if note:
        text += f"\n📝 *Note:* {note}"
    if customer_block:
        text = text + "\n\n" + customer_block
    return text

def mdg_keyboard(order_id: str) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    # Assignment row (drivers)
    if DRIVERS:
        assign_row = [InlineKeyboardButton(f"Assign: {name}", callback_data=f"assign|{order_id}|{name}|{uid}") for name, uid in DRIVERS.items()]
        rows.append(assign_row)
    # Status row
    rows.append([
        InlineKeyboardButton("Delivered ✅", callback_data=f"delivered|{order_id}"),
        InlineKeyboardButton("Delay 🕧", callback_data=f"delayed|{order_id}")
    ])
    return InlineKeyboardMarkup(rows)

def vendor_keyboard(order_id: str, vendor: str, expanded: bool) -> InlineKeyboardMarkup:
    toggle = "Hide ⬆" if expanded else "Expand ⬇"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle, callback_data=f"expand|{order_id}|{vendor}")],
        [InlineKeyboardButton("Works", callback_data=f"reply|{order_id}|{vendor}|Works"),
         InlineKeyboardButton("Later", callback_data=f"reply|{order_id}|{vendor}|Later"),
         InlineKeyboardButton("Will prepare", callback_data=f"reply|{order_id}|{vendor}|Will prepare")]
    ])

# --- TELEGRAM WEBHOOK ---
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    upd = request.get_json(force=True)
    # Only handling callback queries according to assignment
    cq = upd.get("callback_query")
    if not cq:
        return "OK"

    async def handle():
        try:
            await bot.answer_callback_query(cq["id"])  # quick ack to avoid spinner
        except Exception as e:
            print(f"answer_callback_query error: {e}")
        data = (cq.get("data") or "").split("|")
        if not data:
            return
        kind = data[0]
        try:
            if kind == "reply":
                _, order_id, vendor, reply_text = data
                # Post vendor reply to MDG
                msg = f"🍴 *{vendor}* replied: “{reply_text}”"
                await bot.send_message(DISPATCH_MAIN_CHAT_ID, msg, parse_mode=ParseMode.MARKDOWN)
            elif kind == "expand":
                _, order_id, vendor = data
                order = STATE.get(order_id)
                if not order:
                    return
                expanded = not order["vendor_expanded"].get(vendor, False)
                order["vendor_expanded"][vendor] = expanded
                chat_id = VENDOR_GROUP_MAP.get(vendor)
                msg_id = order["vendor_msgs"].get(vendor)
                if chat_id and msg_id:
                    new_text = build_vendor_text(order, vendor, expanded)
                    await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=new_text, reply_markup=vendor_keyboard(order_id, vendor, expanded), parse_mode=ParseMode.MARKDOWN)
            elif kind == "assign":
                _, order_id, driver_name, driver_id = data
                order = STATE.get(order_id)
                if not order:
                    return
                # send DM to driver
                dm_text = (
                    f"🟨 *NEW ASSIGNMENT* ({order['name']})\n"
                    f"🕒 Time: {order['delivery_time']}\n"
                    f"📍 {order['customer']['address']}\n"
                    f"👤 {order['customer']['name']} — {order['customer']['phone']}\n\n"
                    f"🛒 Items:\n{order['items_text']}"
                )
                try:
                    await bot.send_message(int(driver_id), dm_text, parse_mode=ParseMode.MARKDOWN)
                except Exception as e:
                    await bot.send_message(DISPATCH_MAIN_CHAT_ID, f"⚠️ Could not DM {driver_name} — {e}")
                # update status + edit MDG
                order["status"] = "🟨"
                order["assigned_to"] = driver_name
                try:
                    await bot.edit_message_text(chat_id=DISPATCH_MAIN_CHAT_ID, message_id=order["dispatch_msg_id"], text=build_dispatch_text(order), reply_markup=mdg_keyboard(order_id), parse_mode=ParseMode.MARKDOWN)
                except Exception as e:
                    print(f"edit dispatch after assign error: {e}")
            elif kind == "delivered":
                _, order_id = data
                order = STATE.get(order_id)
                if not order:
                    return
                order["status"] = "🟩"
                try:
                    await bot.edit_message_text(chat_id=DISPATCH_MAIN_CHAT_ID, message_id=order["dispatch_msg_id"], text=build_dispatch_text(order), reply_markup=mdg_keyboard(order_id), parse_mode=ParseMode.MARKDOWN)
                except Exception as e:
                    print(f"edit dispatch delivered error: {e}")
            elif kind == "delayed":
                _, order_id = data
                order = STATE.get(order_id)
                if not order:
                    return
                order["status"] = "🟧"
                try:
                    await bot.edit_message_text(chat_id=DISPATCH_MAIN_CHAT_ID, message_id=order["dispatch_msg_id"], text=build_dispatch_text(order), reply_markup=mdg_keyboard(order_id), parse_mode=ParseMode.MARKDOWN)
                except Exception as e:
                    print(f"edit dispatch delayed error: {e}")
        except Exception as e:
            print(f"callback handle error: {e}")
    asyncio.run(handle())
    return "OK"

# --- SHOPIFY WEBHOOK ---
@app.route("/webhooks/shopify", methods=["POST"])
def shopify_webhook():
    raw = request.get_data()
    if not verify_webhook(raw, request.headers.get("X-Shopify-Hmac-Sha256")):
        return "Unauthorized", 401

    payload = request.get_json()
    order_id = str(payload.get("id"))
    order_name = payload.get("name", "Unknown")
    customer = payload.get("customer", {})
    customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or "Unknown"
    phone = customer.get("phone") or payload.get("phone") or "N/A"
    address = fmt_address(payload.get("shipping_address") or {})
    items = payload.get("line_items", [])
    note = payload.get("note", "")
    delivery_time = (payload.get("delivery_method") or {}).get("requested_fulfillment_time") or "ASAP"
    vendors = [v.strip() for v in (payload.get("tags") or "").split(",") if v.strip()]

    items_text = "\n".join([f"- {it.get('quantity', 1)} x {it.get('name', 'Item')}" for it in items])

    # Build order object for state
    order = {
        "name": order_name,
        "delivery_time": delivery_time,
        "customer": {"name": customer_name, "phone": phone, "address": address},
        "items_text": items_text,
        "note": note,
        "vendors": vendors,
        "vendor_msgs": {},
        "vendor_expanded": {},
        "status": "🟥",
        "assigned_to": None,
    }

    async def process():
        # Send MDG message with inline controls
        mdg_text = build_dispatch_text(order)
        mdg_msg = await bot.send_message(DISPATCH_MAIN_CHAT_ID, mdg_text, reply_markup=mdg_keyboard(order_id), parse_mode=ParseMode.MARKDOWN)
        order["dispatch_msg_id"] = mdg_msg.message_id

        # Send vendor messages
        for vendor in vendors:
            group_id = VENDOR_GROUP_MAP.get(vendor)
            if not group_id:
                continue
            v_text = build_vendor_text(order, vendor, expanded=False)
            keyboard = vendor_keyboard(order_id, vendor, expanded=False)
            v_msg = await bot.send_message(group_id, v_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
            order["vendor_msgs"][vendor] = v_msg.message_id
            order["vendor_expanded"][vendor] = False

        # Save to state last, after messages are created
        STATE[order_id] = order

    try:
        asyncio.run(process())
    except Exception as e:
        print(f"shopify process error: {e}")
        return "Error", 500
    return "OK"  # 200

# --- APP ENTRY ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

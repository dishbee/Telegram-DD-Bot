import os
import json
import hmac
import hashlib
import base64
from flask import Flask, request, abort
import requests

app = Flask(__name__)

# --- Env ---
BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "").rstrip("/")
SHOPIFY_WEBHOOK_SECRET = os.environ["SHOPIFY_WEBHOOK_SECRET"]
DISPATCH_MAIN_CHAT_ID = int(os.environ["DISPATCH_MAIN_CHAT_ID"])

# Example JSONs:
# VENDOR_GROUP_MAP='{"Julis Spätzlerei": -1001234567890, "Pizza Roma": -1002233445566}'
# COURIER_MAP='{"Alex": 111111111, "Marta": 222222222}'
VENDOR_GROUP_MAP = json.loads(os.environ.get("VENDOR_GROUP_MAP", "{}"))
COURIER_MAP = json.loads(os.environ.get("COURIER_MAP", "{}"))

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# --- Ephemeral state (resets on deploy) ---
# For vendor expand/hide and minimal assignment context
STATE = {}  # key: f"{order_num}|{vendor}" -> {"items":[...], "addr":(name,phone,line1,line2,cityzip), "requested": str, "total": str}
ORDER_CACHE = {}  # key: order_num -> {"requested": str, "addr": tuple, "total": str, "vendors": dict(vendor -> count)}

# --- Telegram helpers ---
def tg_send_message(chat_id, text, reply_markup=None, parse_mode="HTML", disable_web_page_preview=True):
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": disable_web_page_preview}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    r = requests.post(f"{TELEGRAM_API}/sendMessage", data=payload, timeout=15)
    try:
        return r.json()
    except Exception:
        return {"ok": False, "status_code": r.status_code, "text": r.text}

def tg_edit_message(chat_id, message_id, text, reply_markup=None, parse_mode="HTML", disable_web_page_preview=True):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "disable_web_page_preview": disable_web_page_preview}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(f"{TELEGRAM_API}/editMessageText", data=payload, timeout=15)

def tg_answer_callback_query(cb_id, text=None, show_alert=False):
    payload = {"callback_query_id": cb_id, "show_alert": show_alert}
    if text:
        payload["text"] = text
    requests.post(f"{TELEGRAM_API}/answerCallbackQuery", data=payload, timeout=10)

# --- Shopify HMAC ---
def verify_shopify_hmac(req) -> bool:
    h = req.headers.get("X-Shopify-Hmac-Sha256")
    if not h:
        return False
    digest = hmac.new(SHOPIFY_WEBHOOK_SECRET.encode("utf-8"), msg=req.get_data(), digestmod=hashlib.sha256).digest()
    calc = base64.b64encode(digest).decode()
    return hmac.compare_digest(calc, h)

# --- Formatting helpers ---
def safe(val, default="—"):
    return val if val not in (None, "", []) else default

def parse_requested_time(payload):
    for na in payload.get("note_attributes", []):
        k = (na.get("name") or "").lower()
        v = (na.get("value") or "").strip()
        if k in ("delivery_time", "requested_time", "requested at", "lieferzeit", "time"):
            return v or "ASAP"
    return "ASAP"

def extract_address(addr):
    if not addr:
        return ("", "", "", "", "")
    name = f'{safe(addr.get("first_name",""))} {safe(addr.get("last_name",""))}'.strip()
    phone = safe(addr.get("phone",""))
    line1 = safe(addr.get("address1",""))
    line2 = safe(addr.get("address2",""))
    city_zip = f'{safe(addr.get("zip",""))} {safe(addr.get("city",""))}'.strip()
    return name, phone, line1, line2, city_zip

def euro(amount_str):
    try:
        return f"{float(amount_str):.2f}€"
    except Exception:
        return amount_str

def group_items_by_vendor(line_items):
    by_vendor = {}
    for it in line_items:
        vendor = it.get("vendor") or "Unknown"
        by_vendor.setdefault(vendor, []).append(it)
    return by_vendor

def lines_for_items(items):
    out = []
    for it in items:
        qty = it.get("quantity", 1)
        title = it.get("title") or it.get("name") or "Item"
        price = euro(it.get("price", "0"))
        out.append(f"• {qty}× {title} — {price}")
    return "\n".join(out) if out else "• (no items)"

def vendor_summary_text(vendors_grouped):
    return ", ".join([f"{v} ({len(items)})" for v, items in vendors_grouped.items()]) or "—"

def build_mdg_message(payload, requested_time, address_tuple, vendors_grouped):
    order_num = payload.get("order_number") or payload.get("name") or payload.get("id")
    total = euro(payload.get("total_price", "0"))
    currency = payload.get("currency", "EUR")
    pay_status = safe(payload.get("financial_status", ""))
    tip = euro(payload.get("total_tip_received", "0"))
    name, phone, line1, line2, city_zip = address_tuple

    lines = [
        f"🟥 <b>New order #{order_num}</b>",
        f"🕒 <b>Requested:</b> {requested_time}",
        f"💶 <b>Total:</b> {total} {currency}",
        f"💁 <b>Customer:</b> {safe(name)}",
        f"📞 {safe(phone)}",
        f"📍 {safe(line1)} {safe(line2)}",
        f"🏙️ {safe(city_zip)}",
        f"🏷️ <b>Vendors:</b> {vendor_summary_text(vendors_grouped)}",
        f"💳 <b>Payment:</b> {pay_status}",
        f"💁‍♂️ <b>Tip:</b> {tip}",
    ]
    return "\n".join(lines)

def build_vendor_card_text(order_num, vendor, items, addr_tuple, requested_time, total, expanded=False):
    name, phone, line1, line2, city_zip = addr_tuple
    header = f"🟧 <b>Order #{order_num} — {vendor}</b>\n🕒 {requested_time} • 💶 {total}"
    if not expanded:
        return header
    return (
        f"{header}\n\n"
        f"<b>Items</b>\n{lines_for_items(items)}\n\n"
        f"<b>Customer</b>\n"
        f"{safe(name)}\n{safe(phone)}\n{safe(line1)} {safe(line2)}\n{safe(city_zip)}"
    )

def vendor_keyboard(order_num, vendor, expanded):
    action = "col" if expanded else "exp"
    label = "Hide ⬆️" if expanded else "Expand ⬇️"
    return {
        "inline_keyboard": [
            [{"text": label, "callback_data": f"{action}:{order_num}:{vendor}"}],
            [
                {"text": "Works ✅", "callback_data": f"ack:{order_num}:{vendor}:Works"},
                {"text": "Later ⏳", "callback_data": f"ack:{order_num}:{vendor}:Later"},
                {"text": "Will prepare 👩‍🍳", "callback_data": f"ack:{order_num}:{vendor}:Will prepare"},
            ],
        ]
    }

def state_key(order_num, vendor):
    return f"{order_num}|{vendor}"

def assign_keyboard(order_num):
    # Build inline keyboard with one button per courier
    rows = []
    row = []
    for i, (name, uid) in enumerate(COURIER_MAP.items()):
        row.append({"text": name, "callback_data": f"assign:{order_num}:{name}"})
        if (i + 1) % 3 == 0:
            rows.append(row); row = []
    if row:
        rows.append(row)
    if not rows:
        rows = [[{"text": "No couriers configured", "callback_data": "noop"}]]
    return {"inline_keyboard": rows}

def courier_dm_text(order_num, requested, addr_tuple, total, vendors_grouped):
    name, phone, line1, line2, city_zip = addr_tuple
    vendors_line = vendor_summary_text(vendors_grouped)
    return (
        f"🟨 <b>New assignment — Order #{order_num}</b>\n"
        f"🕒 {requested} • 💶 {total}\n"
        f"🏷️ {vendors_line}\n\n"
        f"<b>Customer</b>\n"
        f"{safe(name)}\n{safe(phone)}\n{safe(line1)} {safe(line2)}\n{safe(city_zip)}"
    )

# --- Routes ---
@app.route("/")
def root():
    return "OK", 200

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_updates():
    update = request.get_json(force=True, silent=True) or {}
    cb = update.get("callback_query")
    if not cb:
        return "OK", 200

    data = cb.get("data", "")
    cb_id = cb.get("id")
    msg = cb.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    message_id = msg.get("message_id")

    try:
        parts = data.split(":", 3)
        kind = parts[0]

        if kind in ("exp", "col"):
            _, order_num, vendor = parts
            key = state_key(order_num, vendor)
            st = STATE.get(key)
            if not st:
                tg_answer_callback_query(cb_id, "No details available (state reset).", show_alert=False)
                return "OK", 200

            expanded = (kind == "exp")
            text = build_vendor_card_text(order_num, vendor, st["items"], st["addr"], st["requested"], st["total"], expanded=expanded)
            kb = vendor_keyboard(order_num, vendor, expanded=expanded)
            tg_edit_message(chat_id, message_id, text, reply_markup=kb)
            tg_answer_callback_query(cb_id)
            return "OK", 200

        if kind == "ack":
            _, order_num, vendor, status = parts
            tg_send_message(
                DISPATCH_MAIN_CHAT_ID,
                f"📣 <b>{vendor}</b> responded: <b>{status}</b> for order <b>#{order_num}</b>."
            )
            tg_answer_callback_query(cb_id, "Noted.")
            return "OK", 200

        if kind == "assign":
            _, order_num, courier_name = parts
            # Resolve courier
            courier_id = COURIER_MAP.get(courier_name)
            info = ORDER_CACHE.get(order_num)
            if not (courier_id and info):
                tg_answer_callback_query(cb_id, "Missing courier or order data.", show_alert=False)
                return "OK", 200

            # DM courier
            dm_text = courier_dm_text(order_num, info["requested"], info["addr"], info["total"], info["vendors"])
            tg_send_message(courier_id, dm_text)

            # Status line in MDG (no edits)
            tg_send_message(DISPATCH_MAIN_CHAT_ID, f"🟨 Order <b>#{order_num}</b> assigned to <b>{courier_name}</b>.")

            tg_answer_callback_query(cb_id, f"Assigned to {courier_name}.")
            return "OK", 200

        if kind == "noop":
            tg_answer_callback_query(cb_id)
            return "OK", 200

    except Exception:
        tg_answer_callback_query(cb_id)
        return "OK", 200

    return "OK", 200

@app.route("/webhooks/shopify", methods=["POST"])
def shopify_webhook():
    if not verify_shopify_hmac(request):
        abort(401)

    payload = request.get_json(force=True, silent=True) or {}
    order_num = payload.get("order_number") or payload.get("name") or payload.get("id")
    requested_time = parse_requested_time(payload)
    shipping_addr = payload.get("shipping_address") or payload.get("billing_address")
    addr_tuple = extract_address(shipping_addr)
    vendors_grouped = group_items_by_vendor(payload.get("line_items", []))
    total = euro(payload.get("total_price", "0"))

    # Cache minimal order info for assignment DMs
    ORDER_CACHE[str(order_num)] = {
        "requested": requested_time,
        "addr": addr_tuple,
        "total": total,
        "vendors": {v: len(items) for v, items in vendors_grouped.items()},
    }

    # Main MDG summary
    mdg_text = build_mdg_message(payload, requested_time, addr_tuple, vendors_grouped)
    tg_send_message(DISPATCH_MAIN_CHAT_ID, mdg_text)

    # Assignment helper message with courier buttons
    if COURIER_MAP:
        assign_text = f"🧩 Assign order <b>#{order_num}</b>:"
        tg_send_message(DISPATCH_MAIN_CHAT_ID, assign_text, reply_markup=assign_keyboard(str(order_num)))

    # Per-vendor cards to vendor groups
    for vendor, items in vendors_grouped.items():
        group_id = VENDOR_GROUP_MAP.get(vendor)
        if not group_id:
            continue

        # Store state for expand/hide
        STATE[state_key(order_num, vendor)] = {
            "items": items,
            "addr": addr_tuple,
            "requested": requested_time,
            "total": total,
        }

        text = build_vendor_card_text(order_num, vendor, items, addr_tuple, requested_time, total, expanded=False)
        kb = vendor_keyboard(order_num, vendor, expanded=False)
        tg_send_message(group_id, text, reply_markup=kb)

    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

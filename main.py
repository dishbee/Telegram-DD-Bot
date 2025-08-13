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
# COURIER_MAP='{"Bee 1": 111111111, "Bee 2": 222222222}'
VENDOR_GROUP_MAP = json.loads(os.environ.get("VENDOR_GROUP_MAP", "{}"))
COURIER_MAP = json.loads(os.environ.get("COURIER_MAP", "{}"))

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# --- Ephemeral state (resets on deploy) ---
# For vendor expand/hide and minimal assignment/time context
STATE = {}        # key: f"{order}|{vendor}" -> {"items":[...], "addr":(name,phone,line1,line2,cityzip), "requested": str, "total": str}
ORDER_CACHE = {}  # key: str(order) -> {"requested": str, "addr": tuple, "total": str, "vendors": dict(vendor->count)}

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

def fmt_total(amount_str, currency):
    try:
        val = float(amount_str)
    except Exception:
        return f"{amount_str} {currency}" if currency else str(amount_str)
    if currency == "EUR":
        return f"{val:.2f}€"
    return f"{val:.2f} {currency}"

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
    total = fmt_total(payload.get("total_price", "0"), payload.get("currency", "EUR"))
    pay_status = safe(payload.get("financial_status", ""))
    tip_raw = payload.get("total_tip_received", "0")
    name, phone, line1, line2, city_zip = address_tuple

    lines = [
        f"🟥 <b>New order #{order_num}</b>",
        f"🕒 <b>Requested:</b> {requested_time}",
        f"💶 <b>Total:</b> {total}",
        f"💁 <b>Customer:</b> {safe(name)}",
        f"📞 {safe(phone)}",
        f"📍 {safe(line1)} {safe(line2)}",
        f"🏙️ {safe(city_zip)}",
        f"🏷️ <b>Vendors:</b> {vendor_summary_text(vendors_grouped)}",
        f"💳 <b>Payment:</b> {pay_status}",
    ]
    # tip line only if > 0
    try:
        if float(tip_raw) > 0:
            lines.append(f"💁‍♂️ <b>Tip:</b> {euro(tip_raw)}")
    except Exception:
        pass
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

def assign_keyboard(order_num):
    rows, row = [], []
    for i, (name, uid) in enumerate(COURIER_MAP.items()):
        row.append({"text": name, "callback_data": f"assign:{order_num}:{name}"})
        if (i + 1) % 3 == 0:
            rows.append(row); row = []
    if row: rows.append(row)
    if not rows:
        rows = [[{"text": "No couriers configured", "callback_data": "noop"}]]
    return {"inline_keyboard": rows}

def courier_dm_text(order_num, requested, addr_tuple, total, vendors_grouped):
    name, phone, line1, line2, city_zip = addr_tuple
    vendors_line = vendor_summary_text({v: [None]*c for v, c in vendors_grouped.items()})
    return (
        f"🟨 <b>New assignment — Order #{order_num}</b>\n"
        f"🕒 {requested} • 💶 {total}\n"
        f"🏷️ {vendors_line}\n\n"
        f"<b>Customer</b>\n"
        f"{safe(name)}\n{safe(phone)}\n{safe(line1)} {safe(line2)}\n{safe(city_zip)}"
    )

def courier_dm_keyboard(order_num, courier_name):
    return {
        "inline_keyboard": [
            [{"text": "🟩 Delivered", "callback_data": f"deliv:{order_num}:{courier_name}"}],
            [
                {"text": "🟧 Delay +10m", "callback_data": f"dly:{order_num}:{courier_name}:10"},
                {"text": "🟧 Delay +20m", "callback_data": f"dly:{order_num}:{courier_name}:20"},
            ]
        ]
    }

def time_request_keyboard(order_num):
    return {
        "inline_keyboard": [
            [
                {"text": "ASAP", "callback_data": f"time:{order_num}:asap"},
                {"text": "+10", "callback_data": f"time:{order_num}:+10"},
                {"text": "+20", "callback_data": f"time:{order_num}:+20"},
                {"text": "Same time as", "callback_data": f"time:{order_num}:same"},
            ]
        ]
    }

def state_key(order_num, vendor):
    return f"{order_num}|{vendor}"

def broadcast_to_vendors(order_num, text):
    info = ORDER_CACHE.get(str(order_num)) or {}
    vendors = info.get("vendors", {})
    for vendor in vendors.keys():
        gid = VENDOR_GROUP_MAP.get(vendor)
        if gid:
            tg_send_message(gid, text)

# --- Routes ---
@app.route("/")
def root():
    return "OK", 200

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_updates():
    update = request.get_json(force=True, silent=True) or {}
    cb = update.get("callback_query")
    msg_obj = update.get("message")

    # Simple /getid for convenience
    if msg_obj and isinstance(msg_obj.get("text"), str) and msg_obj["text"].strip() == "/getid":
        chat_id = msg_obj["chat"]["id"]
        tg_send_message(chat_id, f"Your ID is: {chat_id}")
        return "OK", 200

    if not cb:
        return "OK", 200

    data = cb.get("data", "")
    cb_id = cb.get("id")
    msg = cb.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    message_id = msg.get("message_id")

    try:
        parts = data.split(":", 4)
        kind = parts[0]

        # Vendor cards expand/collapse
        if kind in ("exp", "col"):
            _, order_num, vendor = parts[:3]
            key = state_key(order_num, vendor)
            st = STATE.get(key)
            if not st:
                tg_answer_callback_query(cb_id, "No details (state reset).")
                return "OK", 200
            expanded = (kind == "exp")
            text = build_vendor_card_text(order_num, vendor, st["items"], st["addr"], st["requested"], st["total"], expanded=expanded)
            kb = vendor_keyboard(order_num, vendor, expanded=expanded)
            tg_edit_message(chat_id, message_id, text, reply_markup=kb)
            tg_answer_callback_query(cb_id)
            return "OK", 200

        # Vendor reply → post to MDG as a new message
        if kind == "ack":
            _, order_num, vendor, status = parts[:4]
            tg_send_message(DISPATCH_MAIN_CHAT_ID, f"📣 <b>{vendor}</b> responded: <b>{status}</b> for order <b>#{order_num}</b>.")
            tg_answer_callback_query(cb_id, "Noted.")
            return "OK", 200

        # Assign courier
        if kind == "assign":
            _, order_num, courier_name = parts[:3]
            courier_id = COURIER_MAP.get(courier_name)
            info = ORDER_CACHE.get(str(order_num))
            if not (courier_id and info):
                tg_answer_callback_query(cb_id, "Missing courier or order data.")
                return "OK", 200
            dm_text = courier_dm_text(order_num, info["requested"], info["addr"], info["total"], info["vendors"])
            tg_send_message(courier_id, dm_text, reply_markup=courier_dm_keyboard(order_num, courier_name))
            tg_send_message(DISPATCH_MAIN_CHAT_ID, f"🟨 Order <b>#{order_num}</b> assigned to <b>{courier_name}</b>.")
            tg_answer_callback_query(cb_id, f"Assigned to {courier_name}.")
            return "OK", 200

        # Courier marks delivered
        if kind == "deliv":
            _, order_num, courier_name = parts[:3]
            tg_send_message(DISPATCH_MAIN_CHAT_ID, f"🟩 Order <b>#{order_num}</b> delivered by <b>{courier_name}</b>.")
            tg_answer_callback_query(cb_id, "Marked delivered.")
            return "OK", 200

        # Courier declares delay
        if kind == "dly":
            _, order_num, courier_name, mins = parts[:4]
            tg_send_message(DISPATCH_MAIN_CHAT_ID, f"🟧 Order <b>#{order_num}</b> delay {mins} min — <b>{courier_name}</b>.")
            tg_answer_callback_query(cb_id, "Delay noted.")
            return "OK", 200

        # Dispatcher time requests (MDG)
        if kind == "time":
            _, order_num, which = parts[:3]
            if which == "asap":
                note = "ASAP"
            elif which in ("+10", "+20"):
                note = which
            else:
                note = "Same time as others"
            # post to vendors for this order + small echo in MDG
            broadcast_to_vendors(order_num, f"⏱ Dispatcher request for order #{order_num}: {note}.")
            tg_send_message(DISPATCH_MAIN_CHAT_ID, f"⏱ Sent time request for <b>#{order_num}</b>: {note}.")
            tg_answer_callback_query(cb_id, "Sent.")
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
    total = fmt_total(payload.get("total_price", "0"), payload.get("currency", "EUR"))

    # Cache minimal order info
    ORDER_CACHE[str(order_num)] = {
        "requested": requested_time,
        "addr": addr_tuple,
        "total": total,
        "vendors": {v: len(items) for v, items in vendors_grouped.items()},
    }

    # Main MDG summary
    mdg_text = build_mdg_message(payload, requested_time, addr_tuple, vendors_grouped)
    tg_send_message(DISPATCH_MAIN_CHAT_ID, mdg_text)

    # Assignment helper + time request buttons
    if COURIER_MAP:
        tg_send_message(DISPATCH_MAIN_CHAT_ID, f"🧩 Assign order <b>#{order_num}</b>:", reply_markup=assign_keyboard(str(order_num)))
    tg_send_message(DISPATCH_MAIN_CHAT_ID, f"⏱ Request time for <b>#{order_num}</b>:", reply_markup=time_request_keyboard(str(order_num)))

    # Per-vendor cards to vendor groups
    for vendor, items in vendors_grouped.items():
        group_id = VENDOR_GROUP_MAP.get(vendor)
        if not group_id:
            continue
        STATE[f"{order_num}|{vendor}"] = {"items": items, "addr": addr_tuple, "requested": requested_time, "total": total}
        text = build_vendor_card_text(order_num, vendor, items, addr_tuple, requested_time, total, expanded=False)
        kb = vendor_keyboard(order_num, vendor, expanded=False)
        tg_send_message(group_id, text, reply_markup=kb)

    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

import os, json, hmac, hashlib, base64
from datetime import datetime, timedelta, timezone
from flask import Flask, request, abort
import requests

app = Flask(__name__)

# ===== ENV =====
BOT_TOKEN = os.environ["BOT_TOKEN"]
DISPATCH_MAIN_CHAT_ID = int(os.environ["DISPATCH_MAIN_CHAT_ID"])
SHOPIFY_WEBHOOK_SECRET = os.environ["SHOPIFY_WEBHOOK_SECRET"]
VENDOR_GROUP_MAP = json.loads(os.environ.get("VENDOR_GROUP_MAP", "{}"))
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ===== STATE (ephemeral) =====
ORDERS = {}        # order_key -> {full,last2,vendors,addr,name,phone}
VENDOR_STATE = {}  # f"{order_key}|{vendor}" -> {"last_request": None, "agreed_time": None}

# ===== TELEGRAM HELPERS =====
def tg_send(chat_id, text, reply_markup=None, parse_mode="HTML"):
    data = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True, "parse_mode": parse_mode}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    return requests.post(f"{TELEGRAM_API}/sendMessage", data=data, timeout=15).json()

def tg_edit(chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
    data = {"chat_id": chat_id, "message_id": message_id, "text": text, "disable_web_page_preview": True, "parse_mode": parse_mode}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    requests.post(f"{TELEGRAM_API}/editMessageText", data=data, timeout=15)

def tg_answer(cb_id, text=None, alert=False):
    payload = {"callback_query_id": cb_id, "show_alert": alert}
    if text:
        payload["text"] = text
    requests.post(f"{TELEGRAM_API}/answerCallbackQuery", data=payload, timeout=10)

# ===== HEALTH =====
@app.route("/", methods=["GET", "HEAD"])
def root():
    return "OK", 200

@app.route("/health", methods=["GET", "HEAD"])
def health():
    return "healthy", 200

# ===== SHOPIFY HMAC =====
def verify_shopify_hmac(req) -> bool:
    hdr = req.headers.get("X-Shopify-Hmac-Sha256")
    if not hdr:
        return False
    digest = hmac.new(SHOPIFY_WEBHOOK_SECRET.encode(), msg=req.get_data(), digestmod=hashlib.sha256).digest()
    calc = base64.b64encode(digest).decode()
    return hmac.compare_digest(calc, hdr)

# ===== RENDERING =====
def last2(n):
    s = str(n)
    return s[-2:] if len(s) >= 2 else s

def lines_products(items):
    out = []
    for it in items:
        qty = it.get("quantity", 1)
        title = it.get("title") or it.get("name") or "Item"
        out.append(f"• {qty}× {title}")
    return "\n".join(out) if out else "• (no items)"

def mdg_actions_kb(order_key):
    return {
        "inline_keyboard": [[
            {"text": "ASAP", "callback_data": f"req_asap:{order_key}"},
            {"text": "TIME", "callback_data": f"req_time:{order_key}"},
            {"text": "EXACT TIME", "callback_data": f"req_exact:{order_key}"}
        ]]
    }

def vendor_summary_kb(order_key, vendor, expanded=False):
    return {
        "inline_keyboard": [[
            {"text": "Hide ⬆️" if expanded else "Expand ⬇️",
             "callback_data": f"toggle:{order_key}:{vendor}:{0 if expanded else 1}"}
        ]]
    }

def vendor_resp_kb(order_key, vendor, mode, base_hhmm=None):
    # mode: "asap" -> Will prepare times; "time" -> Works / Later(+5/+10/+15/+20)
    rows = []
    if mode == "asap":
        now = datetime.now().astimezone()
        opts = [now + timedelta(minutes=m) for m in (5, 10, 15, 20)]
        row = []
        for t in opts:
            hhmm = t.strftime("%H:%M")
            row.append({"text": hhmm, "callback_data": f"rest_will:{order_key}:{vendor}:{hhmm}"})
        rows.append(row)
        rows.append([{"text": "Pick time…", "callback_data": f"rest_pick:{order_key}:{vendor}:will"}])
    else:
        rows.append([{"text": "Works ✅", "callback_data": f"rest_works:{order_key}:{vendor}:{base_hhmm or ''}"}])
        if base_hhmm:
            base_dt = datetime.now().astimezone()
            incs = [5, 10, 15, 20]
            row = []
            for m in incs:
                hhmm = (base_dt + timedelta(minutes=m)).strftime("%H:%M")
                row.append({"text": hhmm, "callback_data": f"rest_later:{order_key}:{vendor}:{hhmm}"})
            rows.append(row)
        rows.append([{"text": "Pick time…", "callback_data": f"rest_pick:{order_key}:{vendor}:later"}])
    return {"inline_keyboard": rows}

def exact_hours_kb(ctx):  # ctx = f"{order_key}:{vendor}:{will|later}"
    now = datetime.now().astimezone()
    rows, row = [], []
    for h in range(now.hour, 24):
        row.append({"text": f"{h:02d}", "callback_data": f"exact_h:{ctx}:{h:02d}"})
        if len(row) == 6:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return {"inline_keyboard": rows}

def exact_minutes_kb(ctx, hour):
    rows, row = [], []
    for m in range(0, 60, 5):
        row.append({"text": f"{m:02d}", "callback_data": f"exact_m:{ctx}:{hour}:{m:02d}"})
        if len(row) == 6:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return {"inline_keyboard": rows}

# ===== TELEGRAM WEBHOOK =====
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_updates():
    upd = request.get_json(force=True, silent=True) or {}
    cb = upd.get("callback_query")
    msg = upd.get("message")

    if msg and isinstance(msg.get("text"), str) and msg["text"].strip() == "/getid":
        tg_send(msg["chat"]["id"], f"Your ID is: {msg['chat']['id']}")
        return "OK", 200

    if not cb:
        return "OK", 200

    data = cb.get("data", "")
    cb_id = cb.get("id")
    m = cb.get("message", {})
    chat_id = m.get("chat", {}).get("id")
    mid = m.get("message_id")
    parts = data.split(":")
    kind = parts[0]

    # Expand/Hide in vendor groups
    if kind == "toggle":
        _, order_key, vendor, on = parts
        od = ORDERS.get(order_key, {})
        items = od.get("vendors", {}).get(vendor, [])
        summary = f"🟧 <b>Order #{od.get('full','?')} — {vendor}</b>\n🕒 ASAP\n\n<b>Items</b>\n{lines_products(items)}"
        ship = od.get("addr", {})
        name = od.get("name", "") or "—"
        phone = od.get("phone", "") or ""
        details = f"<b>Customer</b>\n{name}\n{phone}" if (name or phone) else "(no extra details)"
        expanded = (on == "1")
        text = f"{summary}\n\n{details}" if expanded else summary
        tg_edit(chat_id, mid, text, reply_markup=vendor_summary_kb(order_key, vendor, expanded))
        tg_answer(cb_id)
        return "OK", 200

    # MDG → send ASAP/TIME/EXACT to vendor groups
    if kind == "req_asap":
        _, order_key = parts
        od = ORDERS.get(order_key, {})
        for vendor in od.get("vendors", {}).keys():
            gid = VENDOR_GROUP_MAP.get(vendor)
            if not gid:
                continue
            tg_send(gid, f"#{od['last2']} ASAP?", reply_markup=vendor_resp_kb(order_key, vendor, mode="asap"))
            VENDOR_STATE[f"{order_key}|{vendor}"] = {"last_request": "ASAP", "agreed_time": None}
        tg_answer(cb_id, "ASAP sent.")
        return "OK", 200

    if kind == "req_time":
        _, order_key = parts
        now = datetime.now().astimezone()
        base = now + timedelta(minutes=(10 - (now.minute % 10)) % 10)
        rows, row = [], []
        for i in range(6):
            t = (base + timedelta(minutes=10 * i)).strftime("%H:%M")
            row.append({"text": t, "callback_data": f"req_time_sel:{order_key}:{t}"})
            if (i + 1) % 3 == 0:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        tg_edit(chat_id, mid, m.get("text", ""), reply_markup={"inline_keyboard": rows})
        tg_answer(cb_id)
        return "OK", 200

    if kind == "req_time_sel":
        _, order_key, hhmm = parts
        od = ORDERS.get(order_key, {})
        for vendor in od.get("vendors", {}).keys():
            gid = VENDOR_GROUP_MAP.get(vendor)
            if not gid:
                continue
            tg_send(gid, f"#{od['last2']} at {hhmm}?", reply_markup=vendor_resp_kb(order_key, vendor, mode="time", base_hhmm=hhmm))
            VENDOR_STATE[f"{order_key}|{vendor}"] = {"last_request": hhmm, "agreed_time": None}
        tg_answer(cb_id, f"Requested {hhmm}.")
        return "OK", 200

    if kind == "req_exact":
        _, order_key = parts
        tg_edit(chat_id, mid, m.get("text", ""), reply_markup=exact_hours_kb(order_key))
        tg_answer(cb_id)
        return "OK", 200

    if kind == "exact_h":
        _, order_key, hour = parts
        tg_edit(chat_id, mid, m.get("text", ""), reply_markup=exact_minutes_kb(order_key, hour))
        tg_answer(cb_id)
        return "OK", 200

    if kind == "exact_m":
        _, order_key, hour, minute = parts
        hhmm = f"{hour}:{minute}"
        od = ORDERS.get(order_key, {})
        for vendor in od.get("vendors", {}).keys():
            gid = VENDOR_GROUP_MAP.get(vendor)
            if not gid:
                continue
            tg_send(gid, f"#{od['last2']} at {hhmm}?", reply_markup=vendor_resp_kb(order_key, vendor, mode="time", base_hhmm=hhmm))
            VENDOR_STATE[f"{order_key}|{vendor}"] = {"last_request": hhmm, "agreed_time": None}
        tg_answer(cb_id, f"Requested {hhmm}.")
        return "OK", 200

    # Vendor responses (appear only after MDG request)
    if kind in ("rest_works", "rest_later", "rest_will"):
        _, order_key, vendor, hhmm = (parts + [""])[:4]
        last_req = (VENDOR_STATE.get(f"{order_key}|{vendor}") or {}).get("last_request")
        if not last_req:
            tg_answer(cb_id, "No time was requested yet.", True)
            return "OK", 200
        status = {"rest_works": "Works", "rest_later": "Later", "rest_will": "Will prepare"}[kind]
        od = ORDERS.get(order_key, {})
        tg_send(DISPATCH_MAIN_CHAT_ID, f"📣 <b>{vendor}</b> responded: <b>{status}</b> for order <b>#{od.get('last2','??')}</b>.")
        tg_answer(cb_id, "Noted.")
        return "OK", 200

    tg_answer(cb_id)
    return "OK", 200

# ===== SHOPIFY WEBHOOK =====
@app.route("/webhooks/shopify", methods=["POST"])
def shopify_webhook():
    if not verify_shopify_hmac(request):
        abort(401)
    p = request.get_json(force=True, silent=True) or {}
    order_number = p.get("order_number") or p.get("name") or p.get("id")
    order_key = f"shopify:{order_number}"
    last2num = last2(order_number)

    # group by vendor
    vendors = {}
    for it in p.get("line_items", []):
        v = it.get("vendor") or "Unknown"
        vendors.setdefault(v, []).append(it)

    ship = p.get("shipping_address") or {}
    name = f"{ship.get('first_name','')} {ship.get('last_name','')}".strip()
    phone = ship.get("phone", "")

    ORDERS[order_key] = {"full": order_number, "last2": last2num, "vendors": vendors, "addr": ship, "name": name, "phone": phone}

    # MDG summary + admin actions
    mdg_lines = [f"<b>dishbee + {', '.join(vendors.keys())}</b>", f"Order: #{last2num}"]
    street = " ".join([ship.get("address1", ""), ship.get("address2", "")]).strip()
    if street:
        mdg_lines.append(f"<b>{street}</b>")
    if ship.get("zip"):
        mdg_lines.append(f"<b>{ship.get('zip')}</b>")
    for v, items in vendors.items():
        mdg_lines.append(f"<b>{v}</b>")
        mdg_lines.append(lines_products(items))
    tg_send(DISPATCH_MAIN_CHAT_ID, "\n".join(mdg_lines), reply_markup=mdg_actions_kb(order_key))

    # Vendor groups: short card with only Expand/Hide (NO action buttons yet)
    for v, items in vendors.items():
        gid = VENDOR_GROUP_MAP.get(v)
        if not gid:
            continue
        summary = f"🟧 <b>Order #{order_number} — {v}</b>\n🕒 ASAP\n\n<b>Items</b>\n{lines_products(items)}"
        tg_send(gid, summary, reply_markup=vendor_summary_kb(order_key, v, expanded=False))
        VENDOR_STATE[f"{order_key}|{v}"] = {"last_request": None, "agreed_time": None}
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

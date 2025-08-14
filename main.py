import os, json, hmac, hashlib, base64, sys, traceback
from datetime import datetime, timedelta
from flask import Flask, request, abort
import requests

app = Flask(__name__)
ORDERS = {}

# ========= ENV =========
def env(name, default=None):
    v = os.environ.get(name, default)
    if v is None:
        log(f"[ENV] Missing {name}")
    return v

BOT_TOKEN = env("BOT_TOKEN", "")
SHOPIFY_WEBHOOK_SECRET = env("SHOPIFY_WEBHOOK_SECRET", "")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

try:
    DISPATCH_MAIN_CHAT_ID = int(env("DISPATCH_MAIN_CHAT_ID", "0"))
except Exception:
    DISPATCH_MAIN_CHAT_ID = 0

try:
    VENDOR_GROUP_MAP = json.loads(env("VENDOR_GROUP_MAP", "{}"))
except Exception:
    VENDOR_GROUP_MAP = {}

# ========= LOGGING =========
def log(msg):
    ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    print(f"{ts} | {msg}", flush=True)

def log_exc(prefix="EXCEPTION"):
    etype, evalue, tb = sys.exc_info()
    print(f"{datetime.utcnow().isoformat()}Z | {prefix}: {etype.__name__}: {evalue}", flush=True)
    traceback.print_tb(tb)

# ========= TELEGRAM HELPERS =========
def tg_send(chat_id, text, reply_markup=None, parse_mode="HTML"):
    try:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
            "parse_mode": parse_mode
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)

        log(f"[TG] sendMessage -> chat_id={chat_id} text_preview={text[:80].replace(chr(10),' ')}")
        r = requests.post(f"{TELEGRAM_API}/sendMessage", data=payload, timeout=15)
        log(f"[TG] status={r.status_code} body={r.text[:300]}")
        return r.json() if r.headers.get("content-type","").startswith("application/json") else {"ok": r.ok, "text": r.text}
    except Exception:
        log_exc("[TG] sendMessage failed")
        return {"ok": False, "error": "exception"}

def tg_edit(chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
    try:
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "disable_web_page_preview": True,
            "parse_mode": parse_mode
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)

        log(f"[TG] editMessageText -> chat_id={chat_id} mid={message_id}")
        r = requests.post(f"{TELEGRAM_API}/editMessageText", data=payload, timeout=15)
        log(f"[TG] edit status={r.status_code} body={r.text[:300]}")
    except Exception:
        log_exc("[TG] editMessageText failed")

def tg_answer(cb_id, text=None, alert=False):
    try:
        payload = {"callback_query_id": cb_id, "show_alert": alert}
        if text:
            payload["text"] = text
        log(f"[TG] answerCallbackQuery -> id={cb_id} text={text or ''}")
        r = requests.post(f"{TELEGRAM_API}/answerCallbackQuery", data=payload, timeout=10)
        log(f"[TG] answer status={r.status_code} body={r.text[:300]}")
    except Exception:
        log_exc("[TG] answerCallbackQuery failed")

# ========= FORMATTER =========
def format_shopify_order_mdg(p: dict) -> str:
    order_number = p.get("order_number") or p.get("name") or p.get("id")
    last2 = str(order_number)[-2:] if order_number else "??"
    customer = p.get("customer", {})
    cust_name = " ".join(filter(None, [customer.get("first_name", ""), customer.get("last_name", "")])) or "—"
    address_info = p.get("shipping_address", {})
    address = f"{address_info.get('address1', '')} {address_info.get('zip', '')}".strip()
    note = p.get("note")
    tips = p.get("total_tip_received") or p.get("current_total_tip_received")
    payment = p.get("payment_gateway_names", [""])[0]
    paid_text = "Paid" if payment.lower() in ["sofort", "sofort_ueberweisung", "credit_card"] else "Cash"

    lines = [f"<b>dishbee + {', '.join(set(li.get('vendor') or 'Unknown' for li in p.get('line_items', [])))}</b>"]
    lines.append(f"<b>#{last2}</b>")
    lines.append(f"<b>{address}</b>")
    if note:
        lines.append(f"📝 {note}")
    if tips:
        lines.append(f"💶 Tip: {tips}")
    lines.append(f"💳 {paid_text}")
    lines.append("")  # spacer

    # group products by vendor
    vendor_items = {}
    for li in p.get("line_items", []):
        vendor = li.get("vendor", "Unknown")
        vendor_items.setdefault(vendor, []).append(f"{li.get('quantity', 1)} × {li.get('name', '')}")

    for vendor, items in vendor_items.items():
        lines.append(f"<b>{vendor}</b>")
        lines.extend(items)
        lines.append("")  # spacer

    lines.append(f"👤 {cust_name}")
    return "\n".join(lines)

# ========= HEALTH =========
@app.route("/", methods=["GET", "HEAD"])
def root():
    return "OK", 200

@app.route("/health", methods=["GET", "HEAD"])
def health():
    return "healthy", 200

# ========= HMAC =========
def verify_shopify_hmac(req) -> bool:
    header = req.headers.get("X-Shopify-Hmac-Sha256")
    if not header:
        log("[HMAC] Missing header X-Shopify-Hmac-Sha256")
        return False
    try:
        digest = hmac.new(SHOPIFY_WEBHOOK_SECRET.encode("utf-8"), msg=req.get_data(), digestmod=hashlib.sha256).digest()
        calc = base64.b64encode(digest).decode()
        ok = hmac.compare_digest(calc, header)
        log(f"[HMAC] compare -> {ok}")
        return ok
    except Exception:
        log_exc("[HMAC] verify error")
        return False

# ========= SIMPLE KEYBOARDS =========
def mdg_actions_kb(order_key):
    return {"inline_keyboard": [[
        {"text": "ASAP", "callback_data": f"req_asap:{order_key}"},
        {"text": "TIME", "callback_data": f"req_time:{order_key}"},
        {"text": "EXACT TIME", "callback_data": f"req_exact:{order_key}"},
    ]]}

def vendor_summary_kb(order_key, vendor, expanded=False):
    return {"inline_keyboard": [[
        {"text": "Hide ⬆️" if expanded else "Expand ⬇️", "callback_data": f"toggle:{order_key}:{vendor}:{0 if expanded else 1}"}
    ]]}

def vendor_resp_kb(order_key, vendor, mode, base_hhmm=None):
    rows = []
    if mode == "asap":
        now = datetime.utcnow()
        opts = [now + timedelta(minutes=m) for m in (5,10,15,20)]
        row = []
        for t in opts:
            hhmm = t.strftime("%H:%M")
            row.append({"text": hhmm, "callback_data": f"rest_will:{order_key}:{vendor}:{hhmm}"})
        rows.append(row)
    else:
        rows.append([{"text": "Works ✅", "callback_data": f"rest_works:{order_key}:{vendor}:{base_hhmm or ''}"}])
        rows.append([{"text": "Later +5/+10/+15/+20 ➡", "callback_data": f"rest_later:{order_key}:{vendor}:{base_hhmm or ''}"}])
    return {"inline_keyboard": rows}

# ========= TELEGRAM WEBHOOK =========
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_updates():
    upd = request.get_json(force=True, silent=True) or {}
    log(f"[TG] update: {json.dumps(upd)[:500]}")
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
    log(f"[TG] callback kind={kind} data={data}")

    if kind == "toggle":
        _, order_key, vendor, on = parts
        text = f"{vendor} (details {'shown' if on=='1' else 'hidden'})"
        tg_edit(chat_id, mid, text, reply_markup=vendor_summary_kb(order_key, vendor, expanded=(on=="1")))
        tg_answer(cb_id)
        return "OK", 200

    if kind == "req_asap":
        _, order_key = parts
        od = ORDERS.get(order_key, {})
        for vendor in od.get("vendors", {}).keys():
            gid = VENDOR_GROUP_MAP.get(vendor)
            if not gid:
                log(f"[FLOW] No group mapping for vendor={vendor}")
                continue
            tg_send(gid, f"#{od.get('last2','??')} ASAP?", reply_markup=vendor_resp_kb(order_key, vendor, mode="asap"))
        tg_answer(cb_id, "ASAP sent.")
        return "OK", 200

    if kind == "req_time":
        _, order_key = parts
        tg_answer(cb_id, "TIME picker would show here.")
        return "OK", 200

    if kind == "req_exact":
        _, order_key = parts
        tg_answer(cb_id, "EXACT TIME picker would show here.")
        return "OK", 200

    if kind in ("rest_works", "rest_later", "rest_will"):
        _, order_key, vendor, hhmm = (parts + [""])[:4]
        od = ORDERS.get(order_key, {})
        tg_send(DISPATCH_MAIN_CHAT_ID, f"📣 {vendor} replied {kind.replace('rest_','').upper()} for #{od.get('last2','??')} {hhmm}".strip())
        tg_answer(cb_id, "Noted.")
        return "OK", 200

    tg_answer(cb_id)
    return "OK", 200

# ========= SHOPIFY WEBHOOK =========
@app.route("/webhooks/shopify", methods=["POST"])
def shopify_webhook():
    log("[SHOPIFY] hit /webhooks/shopify")
    if not verify_shopify_hmac(request):
        log("[SHOPIFY] HMAC failed -> 401")
        abort(401)

    p = request.get_json(force=True, silent=True) or {}
    order_number = p.get("order_number") or p.get("name") or p.get("id")
    last2 = str(order_number)[-2:] if order_number is not None else "??"
    order_key = f"shopify:{order_number}"
    log(f"[SHOPIFY] order_number={order_number} last2={last2}")

    vendors = {}
    for it in p.get("line_items", []):
        v = it.get("vendor") or "Unknown"
        vendors.setdefault(v, []).append(it)
    log(f"[SHOPIFY] vendors={list(vendors.keys())}")
    ORDERS[order_key] = {"full": order_number, "last2": last2, "vendors": vendors}

    log("[FLOW] Sending formatted MDG message…")
    mdg_text = format_shopify_order_mdg(p)
    tg_send(DISPATCH_MAIN_CHAT_ID, mdg_text, reply_markup=mdg_actions_kb(order_key))

    for vendor, items in vendors.items():
        gid = VENDOR_GROUP_MAP.get(vendor)
        if not gid:
            log(f"[FLOW] Skip vendor={vendor} (no group id)")
            continue
        text = f"Order #{order_number} — {vendor}\n\n{len(items)} product(s)"
        log(f"[FLOW] Sending to vendor group {vendor} -> {gid}")
        tg_send(gid, text, reply_markup=vendor_summary_kb(order_key, vendor, expanded=False))

    return "OK", 200

# ========= TEST HOOK =========
@app.route("/ping-mdg", methods=["GET"])
def ping_mdg():
    log("[TEST] /ping-mdg called")
    tg_send(DISPATCH_MAIN_CHAT_ID, "Ping from server. If you read this, Telegram send works.")
    return "OK", 200

if __name__ == "__main__":
    log(f"[BOOT] BOT_TOKEN set={bool(BOT_TOKEN)}  DISPATCH_MAIN_CHAT_ID={DISPATCH_MAIN_CHAT_ID}")
    log(f"[BOOT] VENDOR_GROUP_MAP keys={list(VENDOR_GROUP_MAP.keys())}")
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

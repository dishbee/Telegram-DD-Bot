import os, json, hmac, hashlib, base64
from flask import Flask, request, abort
import requests

app = Flask(__name__)

# --- Env
BOT_TOKEN = os.environ["BOT_TOKEN"]
DISPATCH_MAIN_CHAT_ID = int(os.environ["DISPATCH_MAIN_CHAT_ID"])
SHOPIFY_WEBHOOK_SECRET = os.environ["SHOPIFY_WEBHOOK_SECRET"]
VENDOR_GROUP_MAP = json.loads(os.environ.get("VENDOR_GROUP_MAP", "{}"))
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# --- Telegram helpers
def tg_send(chat_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(f"{TELEGRAM_API}/sendMessage", data=payload, timeout=15)

def tg_edit(chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "disable_web_page_preview": True, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(f"{TELEGRAM_API}/editMessageText", data=payload, timeout=15)

def tg_answer(cb_id, text=None, alert=False):
    data = {"callback_query_id": cb_id, "show_alert": alert}
    if text: data["text"] = text
    requests.post(f"{TELEGRAM_API}/answerCallbackQuery", data=data, timeout=10)

# --- Health (prevents Render timeout)
@app.route("/", methods=["GET", "HEAD"])
def root():
    return "OK", 200

@app.route("/health", methods=["GET", "HEAD"])
def health():
    return "healthy", 200

# --- Shopify HMAC (base64 per Shopify spec)
def verify_shopify_hmac(req) -> bool:
    header = req.headers.get("X-Shopify-Hmac-Sha256")
    if not header:
        return False
    digest = hmac.new(SHOPIFY_WEBHOOK_SECRET.encode("utf-8"), msg=req.get_data(), digestmod=hashlib.sha256).digest()
    calc_b64 = base64.b64encode(digest).decode()
    return hmac.compare_digest(calc_b64, header)

# --- Simple state (just to demo callbacks work)
ORDER_CACHE = {}  # key: order_number -> {"vendors": {vendor:[items]}, "last2": "45"}

# --- Telegram webhook (buttons work here)
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_updates():
    upd = request.get_json(force=True, silent=True) or {}
    cb = upd.get("callback_query")
    msg = upd.get("message")

    # /getid convenience
    if msg and isinstance(msg.get("text"), str) and msg["text"].strip() == "/getid":
        tg_send(msg["chat"]["id"], f"Your ID is: {msg['chat']['id']}")
        return "OK", 200

    if not cb:
        return "OK", 200

    data = cb.get("data", "")
    cb_id = cb.get("id")
    m = cb.get("message", {})
    chat_id = m.get("chat", {}).get("id")
    message_id = m.get("message_id")

    # Minimal demo handlers so clicks DO something
    if data.startswith("rest_confirm:"):
        _, order_last2, vendor = data.split(":", 2)
        tg_edit(chat_id, message_id, f"✅ {vendor} confirmed for #{order_last2}")
        tg_answer(cb_id, "Confirmed.")
        return "OK", 200

    if data.startswith("rest_later:"):
        _, order_last2, vendor = data.split(":", 2)
        tg_edit(chat_id, message_id, f"⏳ {vendor} will prepare later for #{order_last2}")
        tg_answer(cb_id, "Noted.")
        return "OK", 200

    if data.startswith("rest_willprepare:"):
        _, order_last2, vendor = data.split(":", 2)
        tg_edit(chat_id, message_id, f"🟡 {vendor} will prepare soon for #{order_last2}")
        tg_answer(cb_id, "Noted.")
        return "OK", 200

    tg_answer(cb_id)
    return "OK", 200

# --- Shopify webhook
@app.route("/webhooks/shopify", methods=["POST"])
def shopify_webhook():
    if not verify_shopify_hmac(request):
        abort(401)

    payload = request.get_json(force=True, silent=True) or {}
    order_number = payload.get("order_number") or payload.get("name") or payload.get("id")
    last2 = str(order_number)[-2:] if order_number is not None else "??"

    # group items by vendor
    vendors = {}
    for it in payload.get("line_items", []):
        v = it.get("vendor") or "Unknown"
        vendors.setdefault(v, []).append(it)

    ORDER_CACHE[str(order_number)] = {"vendors": vendors, "last2": last2}

    # MDG summary
    mdg_lines = [f"🆕 New Order #{order_number}"]
    for v, items in vendors.items():
        mdg_lines.append(f"• {v}: {len(items)} items")
    tg_send(DISPATCH_MAIN_CHAT_ID, "\n".join(mdg_lines))

    # Vendor posts with working buttons
    for vendor, items in vendors.items():
        gid = VENDOR_GROUP_MAP.get(vendor)
        if not gid:
            continue
        text = f"Order #{order_number} for {vendor} — {len(items)} products"
        kb = {
            "inline_keyboard": [[
                {"text": "✅ Works", "callback_data": f"rest_confirm:{last2}:{vendor}"},
                {"text": "⏳ Later", "callback_data": f"rest_later:{last2}:{vendor}"},
                {"text": "🟡 Will prepare", "callback_data": f"rest_willprepare:{last2}:{vendor}"},
            ]]
        }
        tg_send(gid, text, reply_markup=kb)

    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

import os
import json
import datetime
from datetime import datetime, timedelta
from flask import Flask, request
import requests

app = Flask(__name__)

# ENV VARS
BOT_TOKEN = os.getenv("BOT_TOKEN")
DISPATCH_MAIN_CHAT_ID = int(os.getenv("DISPATCH_MAIN_CHAT_ID"))
VENDOR_GROUP_MAP = json.loads(os.getenv("VENDOR_GROUP_MAP"))

# STORE
ORDERS = {}

# UTILITIES
def tg(method, payload): return requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", json=payload)
def tg_send(chat_id, text, **kwargs): return tg("sendMessage", {"chat_id": chat_id, "text": text, **kwargs})
def tg_edit(chat_id, mid, text, **kwargs): return tg("editMessageText", {"chat_id": chat_id, "message_id": mid, "text": text, **kwargs})
def tg_answer(cb_id, text=None): return tg("answerCallbackQuery", {"callback_query_id": cb_id, **({"text": text} if text else {})})

def mdg_actions_kb(order_key):
    return {"inline_keyboard": [
        [{"text": "ASAP", "callback_data": f"req_asap:{order_key}"}],
        [{"text": "TIME", "callback_data": f"req_time:{order_key}"}],
        [{"text": "EXACT TIME", "callback_data": f"req_exact:{order_key}"}],
        [{"text": "SAME TIME AS", "callback_data": f"req_sameas:{order_key}"}]
    ]}

# ROUTES
@app.route("/webhooks/shopify", methods=["POST"])
def shopify_webhook():
    payload = request.json
    order_number = payload["name"]
    order_id = str(payload["id"])
    line_items = payload["line_items"]
    vendors = {}

    for item in line_items:
        vendor = item["vendor"]
        if vendor not in vendors:
            vendors[vendor] = []
        vendors[vendor].append(item["name"])

    last2 = order_number[-2:]
    order_key = f"{order_id[-4:]}"
    ORDERS[order_key] = {
        "full": order_number,
        "last2": last2,
        "vendors": vendors,
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z"
    }

    # MDG message
    mdg_text = f"📦 *New Order* #{last2}:\n"
    for vendor, items in vendors.items():
        mdg_text += f"\n🍽️ *{vendor}*:\n" + "\n".join(f"- {item}" for item in items)
    tg_send(DISPATCH_MAIN_CHAT_ID, mdg_text, parse_mode="Markdown", reply_markup=mdg_actions_kb(order_key))

    # Vendor messages
    for vendor, items in vendors.items():
        if vendor in VENDOR_GROUP_MAP:
            vendor_text = f"📦 New order #{last2}:\n" + "\n".join(f"- {item}" for item in items)
            tg_send(VENDOR_GROUP_MAP[vendor], vendor_text)

    return "OK", 200

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_updates():
    data = request.json
    if "callback_query" in data:
        cb = data["callback_query"]
        cb_id = cb["id"]
        cb_data = cb["data"]
        chat_id = cb["message"]["chat"]["id"]
        mid = cb["message"]["message_id"]

        if ":" not in cb_data:
            tg_answer(cb_id, "Invalid callback.")
            return "OK", 200

        kind, *parts = cb_data.split(":")

        if kind == "req_asap":
            tg_answer(cb_id, "ASAP selected.")
            return "OK", 200

        if kind == "req_time":
            tg_answer(cb_id, "TIME selected.")
            return "OK", 200

        if kind == "req_exact":
            tg_answer(cb_id, "EXACT TIME selected.")
            return "OK", 200

        if kind == "req_sameas":
            order_key = parts[0]
            now = datetime.utcnow()
            recent_orders = []

            for ok, data in ORDERS.items():
                if ok == order_key:
                    continue  # skip self
                t = data.get("timestamp")
                if not t:
                    continue
                try:
                    dt = datetime.fromisoformat(t.replace("Z", ""))
                    if now - dt <= timedelta(hours=1):
                        recent_orders.append((ok, data))
                except Exception:
                    continue

            if not recent_orders:
                tg_answer(cb_id, "No recent orders found.")
                return "OK", 200

            kb = {"inline_keyboard": []}
            for ok, data in sorted(recent_orders, key=lambda x: x[1]["timestamp"], reverse=True):
                label = f"#{data['last2']} – {', '.join(data['vendors'].keys())}"
                cbdata = f"sameas_choose:{order_key}:{ok}"
                kb["inline_keyboard"].append([{"text": label, "callback_data": cbdata}])

            tg_edit(chat_id, mid, "Select an earlier order to copy delivery time from:", reply_markup=kb)
            tg_answer(cb_id)
            return "OK", 200

    return "OK", 200

@app.route("/", methods=["GET", "HEAD"])
def healthcheck():
    return "OK", 200

if __name__ == "__main__":
    print(f"{datetime.utcnow().isoformat(timespec='seconds')}Z | [BOOT] BOT_TOKEN set={bool(BOT_TOKEN)}  DISPATCH_MAIN_CHAT_ID={DISPATCH_MAIN_CHAT_ID}")
    print(f"{datetime.utcnow().isoformat(timespec='seconds')}Z | [BOOT] VENDOR_GROUP_MAP keys={list(VENDOR_GROUP_MAP.keys())}")
    app.run(host="0.0.0.0", port=10000)

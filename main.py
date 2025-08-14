# Telegram Dispatch Bot — Phase 2b: Dispatcher requests time, vendor replies with buttons

from flask import Flask, request
import json
import os
from datetime import datetime, timedelta
import requests

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DISPATCH_MAIN_CHAT_ID = int(os.getenv("DISPATCH_MAIN_CHAT_ID"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
SHOPIFY_WEBHOOK_SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET")

VENDOR_GROUP_MAP = json.loads(os.getenv("VENDOR_GROUP_MAP"))
ORDERS = {}
VENDOR_MSGS = {}

DRIVERS = ["Driver A", "Driver B", "Driver C"]

# --- Telegram API wrappers ---
def tg_send(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload)
    if r.ok:
        return r.json().get("result", {}).get("message_id")
    return None

def tg_edit(chat_id, mid, text, reply_markup=None):
    payload = {"chat_id": chat_id, "message_id": mid, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText", json=payload)

def tg_answer(cb_id, text="OK"):
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": text})

# --- Keyboards ---
def expand_button_kb(order_key, vendor, collapsed=True):
    if collapsed:
        return {"inline_keyboard": [[{"text": "👁 View items", "callback_data": f"expand:{order_key}:{vendor}"}]]}
    else:
        return {"inline_keyboard": [[{"text": "🔽 Hide items", "callback_data": f"collapse:{order_key}:{vendor}"}]]}

def mdg_actions_kb(order_key):
    return {"inline_keyboard": [
        [{"text": "ASAP", "callback_data": f"req_asap:{order_key}"}],
        [{"text": "TIME", "callback_data": f"req_time:{order_key}"}],
        [{"text": "EXACT TIME", "callback_data": f"req_exact:{order_key}"}],
        [{"text": "SAME TIME AS", "callback_data": f"req_sameas:{order_key}"}]
    ]}

def driver_kb(order_key):
    return {"inline_keyboard": [[{"text": d, "callback_data": f"assign_driver:{order_key}:{d}"} for d in DRIVERS]]}

def vendor_time_kb(order_key):
    return {"inline_keyboard": [
        [{"text": "✅ Works 👍", "callback_data": f"vtime:works:{order_key}"}],
        [{"text": "⏱ Later", "callback_data": f"vtime:later:{order_key}"}],
        [{"text": "🕒 Will prepare", "callback_data": f"vtime:prep:{order_key}"}]
    ]}

# --- Shopify Webhook ---
@app.route("/webhooks/shopify", methods=["POST"])
def shopify_webhook():
    data = request.get_json()
    order_number = data.get("name")
    vendor_lines = {}

    for item in data.get("line_items", []):
        vendor = item.get("vendor")
        if not vendor:
            continue
        if vendor not in vendor_lines:
            vendor_lines[vendor] = []
        vendor_lines[vendor].append(f"{item['quantity']}x {item['title']}")

    last2 = order_number[-2:]
    order_key = f"order-{data['id']}"

    ORDERS[order_key] = {
        "full": order_number,
        "last2": last2,
        "vendors": vendor_lines,
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z"
    }
    VENDOR_MSGS[order_key] = {}

    mdg_text = f"🔗 New order #{last2}\n"
    for vendor, items in vendor_lines.items():
        mdg_text += f"\n🍽️ {vendor}\n" + "\n".join(items)

    tg_send(DISPATCH_MAIN_CHAT_ID, mdg_text, reply_markup=mdg_actions_kb(order_key))

    for vendor, items in vendor_lines.items():
        group_id = VENDOR_GROUP_MAP.get(vendor)
        if group_id:
            mid = tg_send(group_id, f"🍽️ New order #{last2}", reply_markup=expand_button_kb(order_key, vendor))
            VENDOR_MSGS[order_key][vendor] = {
                "group_id": group_id,
                "message_id": mid,
                "collapsed": True,
                "items": items
            }

    return "OK", 200

# --- Update Handler ---
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_updates():
    update = request.get_json()
    print(json.dumps(update, indent=2))
    if "callback_query" in update:
        cb = update["callback_query"]
        data = cb["data"]
        parts = data.split(":")
        chat_id = cb["message"]["chat"]["id"]
        mid = cb["message"]["message_id"]
        cb_id = cb["id"]

        if data.startswith("req_asap:") or data.startswith("req_time:") or data.startswith("req_exact:"):
            _, order_key = parts
            time_type = parts[0].split("_")[1]
            text_map = {
                "asap": "⏰ ASAP",
                "time": "⏱ Later",
                "exact": "⏰ Waiting for exact time"
            }
            reply_text = f"Ⅎ Dispatcher requests: {text_map[time_type]}"
            for vendor, meta in VENDOR_MSGS[order_key].items():
                tg_send(meta["group_id"], reply_text, reply_markup=vendor_time_kb(order_key))
            tg_edit(chat_id, mid, reply_text + "\nAwaiting vendor replies...")
            tg_answer(cb_id)
            return "OK", 200

        if data.startswith("vtime:"):
            _, choice, order_key = parts
            vendor_name = None
            for v, meta in VENDOR_MSGS[order_key].items():
                if meta["group_id"] == cb["message"]["chat"]["id"]:
                    vendor_name = v
                    break
            if vendor_name:
                now = datetime.utcnow().strftime("%H:%M")
                emoji_map = {
                    "works": "✅ Works 👍",
                    "later": "⏱ Later",
                    "prep": "🕒 Will prepare"
                }
                status = emoji_map.get(choice, "Responded")
                last2 = ORDERS[order_key]["last2"]
                line = f"🟢 {vendor_name} replied {status} for #{last2} at {now}"
                tg_send(DISPATCH_MAIN_CHAT_ID, line)
                tg_answer(cb_id, "Response received")
            return "OK", 200

    return "OK", 200

if __name__ == "__main__":
    print("[BOOT] Running Telegram Dispatch Bot")
    app.run(host="0.0.0.0", port=10000)

# Telegram Dispatch Bot — main.py

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
VENDOR_MSGS = {}  # order_key -> vendor -> {group_id, message_id, collapsed, items}

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

# --- Reply keyboard for vendors ---
def vendor_reply_kb():
    return {
        "keyboard": [[
            {"text": "Works"},
            {"text": "Later"},
            {"text": "Will prepare"}
        ]],
        "resize_keyboard": True,
        "one_time_keyboard": True
    }

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

    mdg_actions = mdg_actions_kb(order_key)
    tg_send(DISPATCH_MAIN_CHAT_ID, mdg_text, reply_markup=mdg_actions)

    for vendor, items in vendor_lines.items():
        group_id = VENDOR_GROUP_MAP.get(vendor)
        if group_id:
            collapsed_text = f"🍽️ New order #{last2}"
            kb = expand_button_kb(order_key, vendor, collapsed=True)
            mid = tg_send(group_id, collapsed_text, reply_markup=kb)
            VENDOR_MSGS[order_key][vendor] = {
                "group_id": group_id,
                "message_id": mid,
                "collapsed": True,
                "items": items
            }

    return "OK", 200

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
    return {"inline_keyboard": [[{"text": d, "callback_data": f"assign_driver:{order_key}:{d}"}] for d in DRIVERS]}

def parse_update(update):
    if "callback_query" in update:
        cb = update["callback_query"]
        return "cb", cb["message"]["chat"].get("id"), cb["message"]["message_id"], cb["id"], cb["data"]
    if "message" in update:
        msg = update["message"]
        return "msg", msg.get("chat", {}).get("id"), msg.get("message_id"), None, msg.get("text")
    return None, None, None, None, None

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_updates():
    update = request.get_json()
    print(json.dumps(update, indent=2))
    kind, chat_id, mid, cb_id, data = parse_update(update)

    if kind == "cb":
        parts = data.split(":")

        if data.startswith("expand:"):
            _, order_key, vendor = parts
            meta = VENDOR_MSGS.get(order_key, {}).get(vendor)
            if meta:
                text = f"🍽️ New order #{ORDERS[order_key]['last2']}\n" + "\n".join(meta["items"])
                kb = expand_button_kb(order_key, vendor, collapsed=False)
                tg_edit(meta["group_id"], meta["message_id"], text, reply_markup=kb)
                meta["collapsed"] = False
            tg_answer(cb_id)
            return "OK", 200

        if data.startswith("collapse:"):
            _, order_key, vendor = parts
            meta = VENDOR_MSGS.get(order_key, {}).get(vendor)
            if meta:
                text = f"🍽️ New order #{ORDERS[order_key]['last2']}"
                kb = expand_button_kb(order_key, vendor, collapsed=True)
                tg_edit(meta["group_id"], meta["message_id"], text, reply_markup=kb)
                meta["collapsed"] = True
            tg_answer(cb_id)
            return "OK", 200

        if data.startswith("req_asap:"):
            _, order_key = parts
            ORDERS[order_key]["delivery_time"] = "ASAP"
            tg_answer(cb_id, "Time set to ASAP.")
            for vendor in ORDERS[order_key]["vendors"]:
                group_id = VENDOR_GROUP_MAP.get(vendor)
                if group_id:
                    msg = f"⏱ Can you prepare order #{ORDERS[order_key]['last2']} for delivery ASAP?"
                    tg_send(group_id, msg, reply_markup=vendor_reply_kb())
            kb = driver_kb(order_key)
            tg_edit(chat_id, mid, "⏱ Time set to: ASAP\nAssign to:", reply_markup=kb)
            return "OK", 200

        if data.startswith("req_time:"):
            _, order_key = parts
            ORDERS[order_key]["delivery_time"] = "Later"
            tg_answer(cb_id, "Time will be sent later.")
            for vendor in ORDERS[order_key]["vendors"]:
                group_id = VENDOR_GROUP_MAP.get(vendor)
                if group_id:
                    msg = f"⏱ Can you prepare order #{ORDERS[order_key]['last2']}? Delivery time will be sent later."
                    tg_send(group_id, msg, reply_markup=vendor_reply_kb())
            kb = driver_kb(order_key)
            tg_edit(chat_id, mid, "⏱ Time will be sent later.\nAssign to:", reply_markup=kb)
            return "OK", 200

        if data.startswith("req_exact:"):
            _, order_key = parts
            ORDERS[order_key]["delivery_time"] = "Exact time (to be confirmed)"
            tg_answer(cb_id, "Please confirm exact time manually.")
            for vendor in ORDERS[order_key]["vendors"]:
                group_id = VENDOR_GROUP_MAP.get(vendor)
                if group_id:
                    msg = f"⏱ Can you prepare order #{ORDERS[order_key]['last2']} for a specific time? Please wait for exact confirmation."
                    tg_send(group_id, msg, reply_markup=vendor_reply_kb())
            kb = driver_kb(order_key)
            tg_edit(chat_id, mid, "⏱ Waiting for exact time confirmation.\nAssign to:", reply_markup=kb)
            return "OK", 200

        if data.startswith("req_sameas:"):
            _, order_key = parts
            now = datetime.utcnow()
            recent_orders = []

            for ok, odata in ORDERS.items():
                if ok == order_key:
                    continue
                t = odata.get("timestamp")
                if not t:
                    continue
                try:
                    dt = datetime.fromisoformat(t.replace("Z", ""))
                    if now - dt <= timedelta(hours=1):
                        recent_orders.append((ok, odata))
                except Exception:
                    continue

            if not recent_orders:
                tg_answer(cb_id, "No recent orders found.")
                return "OK", 200

            kb = {"inline_keyboard": []}
            for ok, odata in sorted(recent_orders, key=lambda x: x[1]["timestamp"], reverse=True):
                label = f"#{odata['last2']} – {', '.join(odata['vendors'].keys())}"
                cbdata = f"sameas_choose:{order_key}:{ok}"
                kb["inline_keyboard"].append([{"text": label, "callback_data": cbdata}])

            tg_edit(chat_id, mid, "Select an earlier order to copy delivery time from:", reply_markup=kb)
            tg_answer(cb_id)
            return "OK", 200

        if data.startswith("sameas_choose:"):
            _, current_order_key, selected_order_key = parts
            selected = ORDERS.get(selected_order_key)
            if not selected:
                tg_answer(cb_id, "Selected order not found.")
                return "OK", 200
            delivery_time = selected.get("delivery_time")
            if not delivery_time:
                tg_answer(cb_id, "Selected order has no delivery time.")
                return "OK", 200
            ORDERS[current_order_key]["delivery_time"] = delivery_time
            for vendor in ORDERS[current_order_key]["vendors"]:
                group_id = VENDOR_GROUP_MAP.get(vendor)
                if group_id:
                    tg_send(group_id, f"⏱ Can you prepare order #{ORDERS[current_order_key]['last2']}? Same time as previous order #{selected['last2']}", reply_markup=vendor_reply_kb())
            tg_answer(cb_id, "Delivery time copied.")
            tg_edit(chat_id, mid, f"✅ Time set from #{selected['last2']}: {delivery_time}\nAssign to:", reply_markup=driver_kb(current_order_key))
            return "OK", 200

        if data.startswith("assign_driver:"):
            _, order_key, driver = parts
            ORDERS[order_key]["assigned_driver"] = driver
            last2 = ORDERS[order_key]["last2"]
            text = f"🚴 Assigned to {driver} for #{last2}"
            tg_edit(chat_id, mid, text)
            tg_answer(cb_id, "Driver assigned.")
            return "OK", 200

    elif kind == "msg":
        text = data
        chat_id = chat_id
        if text in ["Works", "Later", "Will prepare"]:
            for order_key, order in ORDERS.items():
                for vendor in order["vendors"]:
                    group_id = VENDOR_GROUP_MAP.get(vendor)
                    if group_id == chat_id:
                        now = datetime.utcnow().strftime("%H:%M")
                        response_line = f"🟢 {vendor} replied ✅ {text} 👍 for #{order['last2']} at {now}"
                        tg_send(DISPATCH_MAIN_CHAT_ID, response_line)
                        return "OK", 200

    return "OK", 200

if __name__ == "__main__":
    ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    print(f"{ts} | [BOOT] BOT_TOKEN set={bool(BOT_TOKEN)}  DISPATCH_MAIN_CHAT_ID={DISPATCH_MAIN_CHAT_ID}")
    print(f"{ts} | [BOOT] VENDOR_GROUP_MAP keys={list(VENDOR_GROUP_MAP.keys())}")
    app.run(host="0.0.0.0", port=10000)

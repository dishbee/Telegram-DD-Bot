import os
import json
import hmac
import hashlib
import base64
from datetime import datetime, timedelta, timezone
from flask import Flask, request, abort
import requests

app = Flask(__name__)

# ==== ENV ====
BOT_TOKEN = os.environ["BOT_TOKEN"]
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
SHOPIFY_WEBHOOK_SECRET = os.environ["SHOPIFY_WEBHOOK_SECRET"]
DISPATCH_MAIN_CHAT_ID = int(os.environ["DISPATCH_MAIN_CHAT_ID"])
VENDOR_GROUP_MAP = json.loads(os.environ.get("VENDOR_GROUP_MAP", "{}"))
COURIER_MAP = json.loads(os.environ.get("COURIER_MAP", "{}"))  # {"Bee 1": 111..., "Bee 2": 222...}
RESTAURANT_CONTACTS = json.loads(os.environ.get("RESTAURANT_CONTACTS", "{}"))  # {"Vendor":{"telegram":"@user","phone":"+49..."}}
TIMEZONE = os.environ.get("TIMEZONE", "Europe/Prague")  # label only; timestamps carry offset

# ==== STATE (ephemeral; resets on deploy) ====
ORDERS = {}   # order_key -> parsed order dict
RECENT = []   # list of (ts_utc, order_key)
VENDOR_STATE = {}  # f"{order_key}|{vendor}" -> {"agreed_time": "HH:MM" or None, "last_request": str or None, "pickup": bool}
EXPECT_ISSUE_MSG = {}  # f"{chat_id}|{order_key}" -> {"kind": "tech"|"other"}

# ==== Telegram helpers ====
def tg_send(chat_id, text, reply_markup=None, parse_mode="HTML"):
    data = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if parse_mode:
        data["parse_mode"] = parse_mode
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    r = requests.post(f"{TELEGRAM_API}/sendMessage", data=data, timeout=15)
    try:
        return r.json()
    except Exception:
        return {"ok": False, "status": r.status_code, "text": r.text}

def tg_edit(chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
    data = {"chat_id": chat_id, "message_id": message_id, "text": text, "disable_web_page_preview": True}
    if parse_mode:
        data["parse_mode"] = parse_mode
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    requests.post(f"{TELEGRAM_API}/editMessageText", data=data, timeout=15)

def tg_answer(cb_id, text=None, alert=False):
    data = {"callback_query_id": cb_id, "show_alert": alert}
    if text:
        data["text"] = text
    requests.post(f"{TELEGRAM_API}/answerCallbackQuery", data=data, timeout=10)

# ==== Shopify HMAC ====
def verify_shopify_hmac(req) -> bool:
    hdr = req.headers.get("X-Shopify-Hmac-Sha256")
    if not hdr:
        return False
    digest = hmac.new(SHOPIFY_WEBHOOK_SECRET.encode(), msg=req.get_data(), digestmod=hashlib.sha256).digest()
    calc = base64.b64encode(digest).decode()
    return hmac.compare_digest(calc, hdr)

# ==== Utils ====
def safe(x, default=""):
    return x if x not in (None, "", []) else default

def parse_iso(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return datetime.now(timezone.utc)

def last2_digits(order_number) -> str:
    try:
        n = int(order_number)
        return f"{n % 100:02d}"
    except Exception:
        s = str(order_number)
        return s[-2:] if len(s) >= 2 else s

def fmt_total(amount_str, currency):
    try:
        val = float(amount_str)
    except Exception:
        return f"{amount_str} {currency}" if currency else str(amount_str)
    if currency == "EUR":
        return f"{val:.2f}€"
    return f"{val:.2f} {currency}"

def map_payment_shopify(fin_status, gateways: list):
    gws = [str(g).lower() for g in (gateways or [])]
    if any("cash" in g or "cod" in g for g in gws):
        return "Cash"
    if any("sofort" in g for g in gws):
        return "Paid"
    if str(fin_status).lower() in ("paid", "partially_paid", "authorized", "captured"):
        return "Paid"
    return "Paid" if gws else safe(fin_status, "Paid")

def is_pickup(payload):
    for sl in payload.get("shipping_lines", []):
        title = (sl.get("title") or "").lower()
        if "selbstabholung" in title or "abholung" in title:
            return True
    return False

def address_lines(addr):
    if not addr:
        return ("", "")
    street = " ".join([safe(addr.get("address1"), ""), safe(addr.get("address2"), "")]).strip()
    zip_only = safe(addr.get("zip"), "")
    city = safe(addr.get("city"), "")
    return (street, f"{zip_only} {city}".strip())

def vendor_from_line_item(it):
    if it.get("vendor"):
        return it["vendor"]
    props = it.get("properties") or []
    for p in props:
        k = (p.get("name") or p.get("key") or "").strip().lower()
        v = (p.get("value") or "").strip()
        if k in ("vendor", "restaurant", "vendor_name", "restaurant_name") and v:
            return v
    return "Unknown"

def group_items_by_vendor(items):
    by = {}
    for it in items or []:
        v = vendor_from_line_item(it)
        by.setdefault(v, []).append(it)
    return by

def lines_products(items):
    out = []
    for it in items:
        qty = it.get("quantity", 1)
        title = it.get("title") or it.get("name") or "Item"
        out.append(f"• {qty}× {title}")
    return "\n".join(out) if out else "• (no items)"

def per_vendor_counts(vendors_dict):
    parts = []
    for v, items in vendors_dict.items():
        parts.append(f"{v} {len(items)}")
    return " · ".join(parts) if parts else "0"

def gmaps_link(street, city_zip_full):
    q = (street + " " + city_zip_full).strip().replace(" ", "+")
    return f"https://maps.google.com/?q={q}"

def tel_link(number):
    if not number:
        return ""
    num = number.strip().replace(" ", "")
    return f"tel:{num}" if num else ""

# ==== Keyboards ====
def mdg_actions_kb(order_key):
    return {
        "inline_keyboard": [
            [
                {"text": "ASAP", "callback_data": f"req_asap:{order_key}"},
                {"text": "TIME", "callback_data": f"req_time:{order_key}"},
                {"text": "EXACT TIME", "callback_data": f"req_exact:{order_key}"},
                {"text": "SAME TIME AS", "callback_data": f"req_same:{order_key}"},
            ]
        ]
    }

def vendor_summary_kb(order_key, vendor, expanded=False):
    return {
        "inline_keyboard": [
            [
                {
                    "text": "◂ Hide" if expanded else "Details ▸",
                    "callback_data": f"toggle:{order_key}:{vendor}:{'1' if not expanded else '0'}",
                }
            ]
        ]
    }

def vendor_time_request_kb(order_key, vendor, base_time: datetime = None, requested_label=None, mode="asap"):
    rows = []
    if mode == "asap":
        now = datetime.now().astimezone()
        options = [now + timedelta(minutes=m) for m in (5, 10, 15, 20)]
        row = []
        for t in options:
            lbl = t.strftime("%H:%M")
            row.append({"text": lbl, "callback_data": f"rest_will:{order_key}:{vendor}:{lbl}"})
        rows.append(row)
        rows.append([{"text": "Pick time…", "callback_data": f"rest_will_pick:{order_key}:{vendor}"}])
    else:
        row1 = [{"text": "Works 👍", "callback_data": f"rest_works:{order_key}:{vendor}:{requested_label or ''}"}]
        rows.append(row1)
        if base_time:
            later_opts = [base_time + timedelta(minutes=m) for m in (5, 10, 15, 20)]
            row = []
            for t in later_opts:
                lbl = t.strftime("%H:%M")
                # FIXED: removed extra ']' at end of the line
                row.append({"text": lbl, "callback_data": f"rest_later:{order_key}:{vendor}:{lbl}"})
            rows.append(row)
        rows.append([{"text": "Pick time…", "callback_data": f"rest_later_pick:{order_key}:{vendor}"}])
    rows.append([{"text": "Something is wrong ⚠️", "callback_data": f"rest_wrong:{order_key}:{vendor}"}])
    return {"inline_keyboard": rows}

def wrong_menu_kb(order_key, vendor):
    return {
        "inline_keyboard": [
            [{"text": "Products not available", "callback_data": f"wrong_na:{order_key}:{vendor}"}],
            [{"text": "Order is canceled", "callback_data": f"wrong_cancel:{order_key}:{vendor}"}],
            [{"text": "Technical issue", "callback_data": f"wrong_tech:{order_key}:{vendor}"}],
            [{"text": "Something else", "callback_data": f"wrong_other:{order_key}:{vendor}"}],
        ]
    }

def delay_menu_kb(order_key, vendor, agreed_label):
    base = datetime.now().astimezone()
    opts = [base + timedelta(minutes=m) for m in (5, 10, 15, 20)]
    rows = []
    row = []
    for t in opts:
        row.append(
            {"text": t.strftime("%H:%M"), "callback_data": f"rest_delay:{order_key}:{vendor}:{t.strftime('%H:%M')}"}
        )
    if row:
        rows.append(row)
    rows.append([{"text": "Pick time…", "callback_data": f"rest_delay_pick:{order_key}:{vendor}"}])
    return {"inline_keyboard": rows}

def assign_menu_kb(order_key):
    rows = []
    rows.append([{"text": "Assign to myself", "callback_data": f"assign_self:{order_key}"}])
    names = list(COURIER_MAP.keys())
    for bee in ["Bee 1", "Bee 2", "Bee 3"]:
        if bee in names:
            names.remove(bee)
            names.insert(0, bee)
    row = []
    for i, name in enumerate(names):
        row.append({"text": name, "callback_data": f"assign_to:{order_key}:{name}"})
        if (i + 1) % 3 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return {"inline_keyboard": rows}

def time_quick_choices_kb(order_key):
    now = datetime.now().astimezone()
    base = now + timedelta(minutes=(10 - (now.minute % 10)) % 10)
    times = [base + timedelta(minutes=10 * i) for i in range(0, 6)]
    rows, row = [], []
    for i, t in enumerate(times):
        row.append({"text": t.strftime("%H:%M"), "callback_data": f"req_time_sel:{order_key}:{t.strftime('%H:%M')}"})
        if (i + 1) % 3 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return {"inline_keyboard": rows}

def exact_time_hours_kb(order_key):
    now = datetime.now().astimezone()
    rows, row = [], []
    for h in range(now.hour, 24):
        row.append({"text": f"{h:02d}", "callback_data": f"exact_h:{order_key}:{h:02d}"})
        if len(row) == 6:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return {"inline_keyboard": rows}

def exact_time_minutes_kb(order_key, hour):
    rows, row = [], []
    for m in range(0, 60, 5):
        row.append({"text": f"{m:02d}", "callback_data": f"exact_m:{order_key}:{hour}:{m:02d}"})
        if len(row) == 6:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return {"inline_keyboard": rows}

def same_time_list_kb():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    items = []
    for ts, ok in RECENT[::-1]:
        if ts < cutoff:
            break
        od = ORDERS.get(ok, {})
        if od.get("source") != "shopify":
            continue
        label = f"#{od.get('order_last2', '??')}"
        items.append({"text": label, "callback_data": f"same_pick:{ok}"})
        if len(items) >= 12:
            break
    if not items:
        return {"inline_keyboard": [[{"text": "No recent orders", "callback_data": "noop"}]]}
    rows, row = [], []
    for i, btn in enumerate(items):
        row.append(btn)
        if (i + 1) % 3 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return {"inline_keyboard": rows}

# ==== MDG/Vendor message builders ====
def mdg_message_for_shopify(od):
    title = "dishbee + " + ", ".join(od["vendors"].keys())
    lines = [f"<b>{title}</b>"]
    lines.append(f"Order: #{od['order_last2']}")
    lines.append(f"<b>{od['street']}</b>")
    lines.append(f"<b>{od['zip']}</b>")
    if od["note"]:
        lines.append(f"📝 {od['note']}")
    if od["tip_val"] > 0:
        lines.append(f"💁‍♂️ Tip: {od['tip_fmt']}")
    lines.append(f"💳 Payment: {od['payment_label']}")
    if len(od["vendors"]) > 1:
        for v, items in od["vendors"].items():
            lines.append(f"<b>{v}</b>")
            lines.append(lines_products(items))
    else:
        v = next(iter(od["vendors"]))
        lines.append(lines_products(od["vendors"][v]))
    if od["cust_name"]:
        lines.append(f"👤 {od['cust_name']}")
    return "\n".join(lines)

def vendor_summary_text(od, vendor):
    items = od["vendors"].get(vendor, [])
    parts = [f"#{od['order_last2']}"]
    prods = lines_products(items)
    if prods:
        parts.append(prods)
    if od["note"]:
        parts.append(f"📝 {od['note']}")
    if od["pickup"]:
        parts.insert(
            0,
            "<b>Order for Selbstabholung</b>\nPlease call the customer and arrange the pickup time on this number: "
            + (od["cust_phone"] or "—"),
        )
    return "\n".join(parts)

def vendor_details_text(od, vendor):
    dt = od["created_local"]
    lines = []
    lines.append(f"<b>Customer</b>\n{od['cust_name'] or '—'}")
    if od["cust_phone"]:
        lines.append(od["cust_phone"])
    lines.append(f"🕒 Placed: {dt.strftime('%H:%M')}")
    lines.append(od["street"])
    lines.append(od["zip_city"])
    return "\n".join(lines)

# ==== Order cache ====
def cache_order(payload):
    src = "shopify"
    order_number = payload.get("order_number") or payload.get("name") or payload.get("id")
    order_key = f"shopify:{order_number}"
    last2 = last2_digits(order_number)
    created = parse_iso(payload.get("created_at") or payload.get("processed_at") or datetime.now().astimezone().isoformat())
    created_local = created.astimezone()
    shipping_addr = payload.get("shipping_address") or payload.get("billing_address") or {}
    street, zip_city = address_lines(shipping_addr)
    name = (" ".join([safe(shipping_addr.get("first_name")), safe(shipping_addr.get("last_name"))])).strip()
    phone = safe(shipping_addr.get("phone"))
    vendors = group_items_by_vendor(payload.get("line_items", []))
    tip_raw = safe(payload.get("total_tip_received", "0"))
    try:
        tip_val = float(tip_raw)
    except Exception:
        tip_val = 0.0
    tip_fmt = fmt_total(tip_raw, payload.get("currency", "EUR"))
    pay_label = map_payment_shopify(payload.get("financial_status"), payload.get("payment_gateway_names"))
    pickup = is_pickup(payload)

    od = {
        "source": src,
        "order_number": order_number,
        "order_key": order_key,
        "order_last2": last2,
        "created_local": created_local,
        "street": street,
        "zip": (shipping_addr.get("zip") or ""),
        "zip_city": zip_city,
        "cust_name": name,
        "cust_phone": phone,
        "vendors": vendors,
        "note": safe(payload.get("note")),
        "tip_val": tip_val,
        "tip_fmt": tip_fmt,
        "payment_label": pay_label,
        "pickup": pickup,
        "currency": payload.get("currency", "EUR"),
        "total_fmt": fmt_total(payload.get("total_price", "0"), payload.get("currency", "EUR")),
    }
    ORDERS[order_key] = od
    RECENT.append((datetime.now(timezone.utc), order_key))
    return od

# ==== Routes ====
@app.route("/")
def root():
    return "OK", 200

@app.route("/webhooks/shopify", methods=["POST"])
def shopify_webhook():
    if not verify_shopify_hmac(request):
        abort(401)
    payload = request.get_json(force=True, silent=True) or {}
    od = cache_order(payload)

    # 1) MDG summary + actions
    mdg_text = mdg_message_for_shopify(od)
    tg_send(DISPATCH_MAIN_CHAT_ID, mdg_text, reply_markup=mdg_actions_kb(od["order_key"]))

    # 2) Vendor-scoped summaries to restaurant groups
    for vendor, _items in od["vendors"].items():
        gid = VENDOR_GROUP_MAP.get(vendor)
        if not gid:
            continue
        summary = vendor_summary_text(od, vendor)
        tg_send(gid, summary, reply_markup=vendor_summary_kb(od["order_key"], vendor, expanded=False))
        VENDOR_STATE[f"{od['order_key']}|{vendor}"] = {"agreed_time": None, "last_request": None, "pickup": od["pickup"]}
    return "OK", 200

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_updates():
    upd = request.get_json(force=True, silent=True) or {}
    msg = upd.get("message")
    cb = upd.get("callback_query")

    # /getid
    if msg and isinstance(msg.get("text"), str) and msg["text"].strip() == "/getid":
        tg_send(msg["chat"]["id"], f"Your ID is: {msg['chat']['id']}")
        return "OK", 200

    # vendor free-text for tech/other
    if msg and msg.get("reply_to_message"):
        chat_id = msg["chat"]["id"]
        for k in list(EXPECT_ISSUE_MSG.keys()):
            if k.startswith(f"{chat_id}|"):
                info = EXPECT_ISSUE_MSG.pop(k, None)
                if info:
                    order_key = k.split("|", 1)[1]
                    tg_send(
                        DISPATCH_MAIN_CHAT_ID,
                        f"⚠️ Vendor message for {order_key}:\n{msg.get('text', '(non-text)')}",
                    )
                    break
        return "OK", 200

    if not cb:
        return "OK", 200

    data = cb.get("data", "")
    cb_id = cb.get("id")
    m = cb.get("message", {})
    chat_id = m.get("chat", {}).get("id")
    message_id = m.get("message_id")
    parts = data.split(":")
    kind = parts[0]

    # --- MDG: time requests ---
    if kind == "req_asap":
        _, order_key = parts
        od = ORDERS.get(order_key)
        if not od:
            return "OK", 200
        for vendor in od["vendors"].keys():
            gid = VENDOR_GROUP_MAP.get(vendor)
            if not gid:
                continue
            txt = f"#{od['order_last2']} ASAP?"
            kb = vendor_time_request_kb(order_key, vendor, mode="asap")
            tg_send(gid, txt, reply_markup=kb)
            VENDOR_STATE[f"{order_key}|{vendor}"]["last_request"] = "ASAP"
        tg_answer(cb_id, "Sent ASAP.")
        return "OK", 200

    if kind == "req_time":
        _, order_key = parts
        tg_edit(chat_id, message_id, m.get("text", ""), reply_markup=time_quick_choices_kb(order_key))
        tg_answer(cb_id)
        return "OK", 200

    if kind == "req_time_sel":
        _, order_key, hhmm = parts
        od = ORDERS.get(order_key)
        if not od:
            return "OK", 200
        base = datetime.now().astimezone()
        for vendor in od["vendors"].keys():
            gid = VENDOR_GROUP_MAP.get(vendor)
            if not gid:
                continue
            txt = f"#{od['order_last2']} at {hhmm}?"
            kb = vendor_time_request_kb(order_key, vendor, base_time=base, requested_label=hhmm, mode="time")
            tg_send(gid, txt, reply_markup=kb)
            VENDOR_STATE[f"{order_key}|{vendor}"]["last_request"] = hhmm
        tg_answer(cb_id, f"Requested {hhmm}.")
        return "OK", 200

    if kind == "req_exact":
        _, order_key = parts
        tg_edit(chat_id, message_id, m.get("text", ""), reply_markup=exact_time_hours_kb(order_key))
        tg_answer(cb_id)
        return "OK", 200

    if kind == "exact_h":
        _, order_key, hour = parts
        tg_edit(chat_id, message_id, m.get("text", ""), reply_markup=exact_time_minutes_kb(order_key, hour))
        tg_answer(cb_id)
        return "OK", 200

    if kind == "exact_m":
        _, order_key, hour, minute = parts
        hhmm = f"{hour}:{minute}"
        od = ORDERS.get(order_key)
        if od:
            base = datetime.now().astimezone()
            for vendor in od["vendors"].keys():
                gid = VENDOR_GROUP_MAP.get(vendor)
                if not gid:
                    continue
                txt = f"#{od['order_last2']} at {hhmm}?"
                kb = vendor_time_request_kb(order_key, vendor, base_time=base, requested_label=hhmm, mode="time")
                tg_send(gid, txt, reply_markup=kb)
                VENDOR_STATE[f"{order_key}|{vendor}"]["last_request"] = hhmm
        tg_answer(cb_id, f"Requested {hhmm}.")
        return "OK", 200

    if kind == "req_same":
        tg_edit(chat_id, message_id, m.get("text", ""), reply_markup=same_time_list_kb())
        tg_answer(cb_id)
        return "OK", 200

    if kind == "same_pick":
        tg_answer(cb_id, "Will wire SAME TIME AS cross-linking in next patch.")
        return "OK", 200

    # --- Vendor: details toggle ---
    if kind == "toggle":
        _, order_key, vendor, want_expand = parts
        od = ORDERS.get(order_key)
        if not od:
            tg_answer(cb_id, "No order.")
            return "OK", 200
        expanded = want_expand == "1"
        if expanded:
            text = vendor_summary_text(od, vendor) + "\n\n" + vendor_details_text(od, vendor)
        else:
            text = vendor_summary_text(od, vendor)
        tg_edit(chat_id, message_id, text, reply_markup=vendor_summary_kb(order_key, vendor, expanded=expanded))
        tg_answer(cb_id)
        return "OK", 200

    # --- Vendor: respond to requests ---
    if kind == "rest_will":
        _, order_key, vendor, hhmm = parts
        VENDOR_STATE[f"{order_key}|{vendor}"]["agreed_time"] = hhmm
        tg_send(
            DISPATCH_MAIN_CHAT_ID,
            f"✅ {vendor} will prepare order #{ORDERS[order_key]['order_last2']} at {hhmm}.",
            reply_markup=assign_menu_kb(order_key),  # NOTE: next patch will gate until all vendors confirm
        )
        tg_answer(cb_id, "Noted.")
        return "OK", 200

    if kind == "rest_will_pick":
        _, order_key, vendor = parts
        tg_edit(chat_id, message_id, m.get("text", ""), reply_markup=exact_time_hours_kb(f"{order_key}|{vendor}|will"))
        tg_answer(cb_id)
        return "OK", 200

    if kind == "rest_works":
        _, order_key, vendor, hhmm = parts
        VENDOR_STATE[f"{order_key}|{vendor}"]["agreed_time"] = hhmm
        tg_send(
            DISPATCH_MAIN_CHAT_ID,
            f"✅ {vendor} confirmed order #{ORDERS[order_key]['order_last2']} for {hhmm}.",
            reply_markup=assign_menu_kb(order_key),
        )
        tg_send(chat_id, f"If needed: We have a delay for #{ORDERS[order_key]['order_last2']} at {hhmm}", reply_markup=delay_menu_kb(order_key, vendor, hhmm))
        tg_answer(cb_id, "Confirmed.")
        return "OK", 200

    if kind == "rest_later":
        _, order_key, vendor, hhmm = parts
        VENDOR_STATE[f"{order_key}|{vendor}"]["agreed_time"] = hhmm
        tg_send(
            DISPATCH_MAIN_CHAT_ID,
            f"✅ {vendor} proposes later time for order #{ORDERS[order_key]['order_last2']}: {hhmm}.",
            reply_markup=assign_menu_kb(order_key),
        )
        tg_send(chat_id, f"If needed: We have a delay for #{ORDERS[order_key]['order_last2']} at {hhmm}", reply_markup=delay_menu_kb(order_key, vendor, hhmm))
        tg_answer(cb_id, "Sent.")
        return "OK", 200

    if kind == "rest_later_pick":
        _, order_key, vendor = parts
        tg_edit(chat_id, message_id, m.get("text", ""), reply_markup=exact_time_hours_kb(f"{order_key}|{vendor}|later"))
        tg_answer(cb_id)
        return "OK", 200

    if kind == "exact_h" and len(parts) == 3 and "|" in parts[2]:
        _, ok_ctx, hour = parts
        tg_edit(chat_id, message_id, m.get("text", ""), reply_markup=exact_time_minutes_kb(ok_ctx, hour))
        tg_answer(cb_id)
        return "OK", 200

    if kind == "exact_m" and len(parts) == 4 and "|" in parts[2]:
        _, ok_ctx, hour, minute = parts
        order_key, vendor, mode = ok_ctx.split("|", 2)
        hhmm = f"{hour}:{minute}"
        if mode == "will":
            return telegram_updates_helper_vendor_confirm(order_key, vendor, hhmm, chat_id, cb_id, message_id, True)
        else:
            return telegram_updates_helper_vendor_confirm(order_key, vendor, hhmm, chat_id, cb_id, message_id, False)

    if kind == "rest_wrong":
        _, order_key, vendor = parts
        tg_edit(chat_id, message_id, m.get("text", ""), reply_markup=wrong_menu_kb(order_key, vendor))
        tg_answer(cb_id)
        return "OK", 200

    if kind == "wrong_na":
        _, order_key, vendor = parts
        tg_send(
            DISPATCH_MAIN_CHAT_ID,
            f"⚠️ {vendor}: Products not available for order #{ORDERS[order_key]['order_last2']}. "
            f"Please call the customer and organize a replacement. If no replacement is possible, write a message to dishbee.",
        )
        tg_answer(cb_id, "Sent.")
        return "OK", 200

    if kind == "wrong_cancel":
        _, order_key, vendor = parts
        tg_send(DISPATCH_MAIN_CHAT_ID, f"⚠️ {vendor}: Order #{ORDERS[order_key]['order_last2']} is canceled.")
        tg_answer(cb_id, "Sent.")
        return "OK", 200

    if kind == "wrong_tech":
        _, order_key, vendor = parts
        EXPECT_ISSUE_MSG[f"{chat_id}|{order_key}"] = {"kind": "tech"}
        tg_send(chat_id, "Please reply to this message with details. I will forward it to dishbee.")
        tg_answer(cb_id)
        return "OK", 200

    if kind == "wrong_other":
        _, order_key, vendor = parts
        EXPECT_ISSUE_MSG[f"{chat_id}|{order_key}"] = {"kind": "other"}
        tg_send(chat_id, "Please reply to this message with details. I will forward it to dishbee.")
        tg_answer(cb_id)
        return "OK", 200

    if kind == "rest_delay":
        _, order_key, vendor, hhmm = parts
        tg_send(DISPATCH_MAIN_CHAT_ID, f"🟧 {vendor} delay for order #{ORDERS[order_key]['order_last2']}: {hhmm}.")
        tg_answer(cb_id, "Delay sent.")
        return "OK", 200

    if kind == "rest_delay_pick":
        _, order_key, vendor = parts
        tg_edit(chat_id, message_id, m.get("text", ""), reply_markup=exact_time_hours_kb(f"{order_key}|{vendor}|delay"))
        tg_answer(cb_id)
        return "OK", 200

    # --- Assignment (temporary: appears after first vendor confirm; next patch = wait for all vendors) ---
    if kind == "assign_self":
        _, order_key = parts
        return do_assign_to(order_key, cb.get("from", {}), cb_id)

    if kind == "assign_to":
        _, order_key, name = parts
        uid = COURIER_MAP.get(name)
        if not uid:
            tg_answer(cb_id, "Courier not configured.")
            return "OK", 200
        return do_assign_to(order_key, {"id": uid, "first_name": name}, cb_id)

    if kind == "noop":
        tg_answer(cb_id)
        return "OK", 200

    tg_answer(cb_id)
    return "OK", 200

def telegram_updates_helper_vendor_confirm(order_key, vendor, hhmm, chat_id, cb_id, message_id, is_will):
    VENDOR_STATE[f"{order_key}|{vendor}"]["agreed_time"] = hhmm
    if is_will:
        tg_send(
            DISPATCH_MAIN_CHAT_ID,
            f"✅ {vendor} will prepare order #{ORDERS[order_key]['order_last2']} at {hhmm}.",
            reply_markup=assign_menu_kb(order_key),
        )
    else:
        tg_send(
            DISPATCH_MAIN_CHAT_ID,
            f"✅ {vendor} proposes {hhmm} for order #{ORDERS[order_key]['order_last2']}.",
            reply_markup=assign_menu_kb(order_key),
        )
    tg_send(
        chat_id,
        f"If needed: We have a delay for #{ORDERS[order_key]['order_last2']} at {hhmm}",
        reply_markup=delay_menu_kb(order_key, vendor, hhmm),
    )
    tg_answer(cb_id, "Noted.")
    return "OK", 200

# ==== Assignment ====
def do_assign_to(order_key, user_obj, cb_id):
    od = ORDERS.get(order_key)
    if not od:
        tg_answer(cb_id, "No order.")
        return "OK", 200
    courier_id = user_obj.get("id")
    courier_name = user_obj.get("first_name") or "Courier"
    if not courier_id:
        tg_answer(cb_id, "Cannot DM courier until they message the bot first.")
        return "OK", 200

    vendors = od["vendors"]
    per_counts = per_vendor_counts(vendors)
    cust_phone = od["cust_phone"] or "—"
    tel = tel_link(od["cust_phone"] or "")
    maps = gmaps_link(od["street"], od["zip_city"])
    title = f"dishbee #{od['order_last2']} + {', '.join(vendors.keys())}"

    dm_lines = [
        f"🟨 <b>{title}</b>",
        f"{od['street']}",
        f"{od['zip_city']}",
        f"📞 <a href=\"{tel}\">{cust_phone}</a>" if tel else f"📞 {cust_phone}",
        f"🧺 Products: {per_counts}",
        f"👤 {od['cust_name'] or '—'}",
        "",
        "<b>Actions</b>",
        f"• <a href=\"{tel}\">Call customer</a>" if tel else "• Call customer: (no number)",
        f"• <a href=\"{maps}\">Navigate</a>",
    ]
    dm_text = "\n".join(dm_lines)

    kb = {
        "inline_keyboard": [
            [
                {"text": "Postpone +5", "callback_data": f"postpone:{order_key}:5"},
                {"text": "Postpone +10", "callback_data": f"postpone:{order_key}:10"},
                {"text": "Postpone +15", "callback_data": f"postpone:{order_key}:15"},
                {"text": "Pick time…", "callback_data": f"postpone_pick:{order_key}"},
            ],
            [
                {"text": "Call restaurant (Telegram)", "callback_data": f"call_rest_tg:{order_key}"},
                {"text": "Call restaurant (Phone)", "callback_data": f"call_rest_ph:{order_key}"},
            ],
            [{"text": "Complete 🟩", "callback_data": f"complete:{order_key}"}],
        ]
    }

    tg_send(courier_id, dm_text, reply_markup=kb)
    tg_send(DISPATCH_MAIN_CHAT_ID, f"🟨 Order #{od['order_last2']} assigned to <b>{courier_name}</b>.")
    tg_answer(cb_id, f"Assigned to {courier_name}.")
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

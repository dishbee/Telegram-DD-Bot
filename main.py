from flask import Flask, request, jsonify
import telegram
import hmac
import hashlib
import os
import json
from datetime import datetime, timedelta
from telegram.constants import ParseMode  # ✅ Updated for compatibility

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
SHOPIFY_WEBHOOK_SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET")
DISPATCH_MAIN_CHAT_ID = int(os.getenv("DISPATCH_MAIN_CHAT_ID"))
VENDOR_GROUP_MAP = json.loads(os.getenv("VENDOR_GROUP_MAP", '{}'))

bot = telegram.Bot(token=BOT_TOKEN)

def verify_shopify_webhook(data, hmac_header):
    hash_digest = hmac.new(
        SHOPIFY_WEBHOOK_SECRET.encode("utf-8"),
        data,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(hmac_header, hash_digest)

# ... [rest of helper and handler functions remain unchanged] ...

@app.route("/webhooks/shopify", methods=["POST"])
def shopify_webhook():
    data = request.data
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256")
    print("--- Shopify webhook received ---")
    print("Headers:", dict(request.headers))
    print("Body:", data.decode())

    # HMAC check temporarily disabled for testing
    # if not verify_shopify_webhook(data, hmac_header):
    #     print("❌ HMAC verification failed")
    #     return "Unauthorized", 401

    print("✅ HMAC check skipped for testing")
    order = request.get_json()
    print("Parsed Order:", order)

    mdg_message, vendors = format_main_dispatch_message(order)
    mdg_buttons = build_mdg_buttons(order)
    bot.send_message(chat_id=DISPATCH_MAIN_CHAT_ID, text=mdg_message, parse_mode=ParseMode.MARKDOWN, reply_markup=mdg_buttons)

    # ... [rest of vendor handling remains unchanged] ...

    return "ok"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

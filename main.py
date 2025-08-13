import os
import hmac
import hashlib
import base64
import json
import threading
import asyncio
from flask import Flask, request, abort

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ---------- ENV ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")            # e.g. https://telegram-dd-bot.onrender.com
PORT = int(os.getenv("PORT", "10000"))            # Render provides this
SHOPIFY_WEBHOOK_SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET", "")
DISPATCH_MAIN_CHAT_ID = int(os.getenv("DISPATCH_MAIN_CHAT_ID", "0"))  # negative group id

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing")

# ---------- TELEGRAM APP (PTB) ----------
application = Application.builder().token(BOT_TOKEN).build()

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your Telegram ID is: {update.effective_user.id}")

application.add_handler(CommandHandler("start", cmd_start))

# We'll run PTB on its own asyncio loop/thread and feed updates from Flask via process_update
_loop = None

def _run_tg_app():
    """Create a dedicated event loop for PTB and keep it running."""
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    # initialize & start the app (without starting its own web server)
    _loop.run_until_complete(application.initialize())
    _loop.run_until_complete(application.start())
    try:
        _loop.run_forever()
    finally:
        _loop.run_until_complete(application.stop())
        _loop.close()

threading.Thread(target=_run_tg_app, name="ptb-loop", daemon=True).start()

# ---------- FLASK ----------
app = Flask(__name__)

def _verify_shopify(req) -> bool:
    """HMAC verify; returns True if ok or no secret set."""
    if not SHOPIFY_WEBHOOK_SECRET:
        return True
    hmac_header = req.headers.get("X-Shopify-Hmac-Sha256", "")
    digest = hmac.new(SHOPIFY_WEBHOOK_SECRET.encode("utf-8"), req.data, hashlib.sha256).digest()
    computed = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(computed, hmac_header)

@app.post("/webhooks/shopify")
def webhooks_shopify():
    # Verify HMAC (will still be True for your earlier curl test)
    if not _verify_shopify(request):
        abort(401)

    payload = request.get_json(silent=True) or {}
    print("[Shopify] webhook received")
    try:
        order_no = payload.get("order_number") or payload.get("name") or payload.get("id")
        text = f"🟥 Shopify webhook received: order {order_no}"
        # Send a quick proof-of-life message to MDG so you see it
        if DISPATCH_MAIN_CHAT_ID != 0 and _loop is not None:
            fut = asyncio.run_coroutine_threadsafe(
                application.bot.send_message(chat_id=DISPATCH_MAIN_CHAT_ID, text=text),
                _loop
            )
            fut.result(timeout=5)  # raise if fails
    except Exception as e:
        print(f"[Shopify] error sending to Telegram: {e}")

    # TODO: parse and route per your spec next
    return "", 200

# Telegram will POST updates here (set webhook to .../<BOT_TOKEN>)
@app.post(f"/{BOT_TOKEN}")
def telegram_webhook():
    data = request.get_json(force=True, silent=False)
    update = Update.de_json(data, application.bot)
    # hand off to PTB on its loop
    if _loop is None:
        abort(503)
    asyncio.run_coroutine_threadsafe(application.process_update(update), _loop)
    return "", 200

if __name__ == "__main__":
    print(f"Starting Flask on 0.0.0.0:{PORT}")
    app.run(host="0.0.0.0", port=PORT)

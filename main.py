# Telegram Dispatch Bot — Full Assignment Implementation (Webhook-only, PTB v20)
# FIXED VERSION - Addresses 500 errors and adds proper error handling

import os
import json
import hmac
import hashlib
import base64
import asyncio
import logging
from typing import Dict, Any, List, Optional
from flask import Flask, request, jsonify
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest
from telegram.error import TelegramError, TimedOut, NetworkError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- ENV ---
BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_SECRET = os.environ["SHOPIFY_WEBHOOK_SECRET"]
DISPATCH_MAIN_CHAT_ID = int(os.environ["DISPATCH_MAIN_CHAT_ID"])  # e.g., -100123...
VENDOR_GROUP_MAP: Dict[str, int] = json.loads(os.environ.get("VENDOR_GROUP_MAP", "{}"))  # {"Vendor": -100...}
DRIVERS: Dict[str, int] = json.loads(os.environ.get("DRIVERS", "{}"))  # {"Anna": 123456789, "Max": 987654321}

# Configure request with larger pool to prevent pool timeout under burst
request_cfg = HTTPXRequest(
    connection_pool_size=32,
    pool_timeout=30.0,
    read_timeout=30.0,
    write_timeout=30.0,
    connect_timeout=15.0,
)
bot = Bot(token=BOT_TOKEN, request=request_cfg)

# --- STATE ---
# Keeps minimal state per order to support edits & callbacks (in-memory; reset on deploy)
STATE: Dict[str, Dict[str, Any]] = {}

# --- HELPERS ---
def verify_webhook(raw: bytes, hmac_header: str) -> bool:
    """Verify Shopify webhook HMAC"""
    try:
        if not hmac_header:
            logger.warning("No HMAC header provided")
            return False
        
        computed = hmac.new(WEBHOOK_SECRET.encode("utf-8"), raw, hashlib.sha256).digest()
        expected = base64.b64encode(computed).decode("utf-8")
        result = hmac.compare_digest(expected, hmac_header)
        
        if not result:
            logger.warning("HMAC verification failed")
        
        return result
    except Exception as e:
        logger.error(f"HMAC verification error: {e}")
        return False

def fmt_address(addr: Dict[str, Any]) -> str:
    """Format address from Shopify data"""
    if not addr:
        return "No address provided"
    
    try:
        parts = []
        if addr.get("address1"):
            parts.append(addr["address1"])
        if addr.get("address2"):
            parts.append(addr["address2"])
        if addr.get("zip"):
            parts.append(addr["zip"])
        if addr.get("city"):
            parts.append(addr["city"])
        
        return ", ".join(parts) if parts else "Address incomplete"
    except Exception as e:
        logger.error(f"Address formatting error: {e}")
        return "Address formatting error"

def build_dispatch_text(order: Dict[str, Any]) -> str:
    """Build dispatch message text for MDG"""
    try:
        note = order.get("note", "")
        status_emoji = order.get("status", "🟥")
        assigned = order.get("assigned_to")
        
        status_line = f"Status: {status_emoji}"
        if status_emoji == "🟨" and assigned:
            status_line += f" — Assigned to {assigned}"
        
        text = (
            f"🟥 *NEW ORDER* ({order['name']})\n"
            f"👤 *Customer:* {order['customer']['name']}\n"
            f"📍 *Address:* {order['customer']['address']}\n"
            f"📞 *Phone:* {order['customer']['phone']}\n"
            f"🕒 *Time:* {order['delivery_time']}\n"
            f"🛒 *Items:*\n{order['items_text']}"
        )
        
        if note:
            text += f"\n📝 *Note:* {note}"
        text += f"\n\n{status_line}"
        
        return text
    except Exception as e:
        logger.error(f"Error building dispatch text: {e}")
        return f"Error formatting order {order.get('name', 'Unknown')}"

def build_vendor_text(order: Dict[str, Any], vendor: str, expanded: bool) -> str:
    """Build vendor message text"""
    try:
        note = order.get("note", "")
        other_vendors = [v for v in order.get("vendors", []) if v != vendor]
        same_time_line = f"\n🕒 Same time as {', '.join(other_vendors)}" if other_vendors else ""
        
        if expanded:
            customer_block = (
                f"👤 *Customer:* {order['customer']['name']}\n"
                f"📍 *Address:* {order['customer']['address']}\n"
                f"📞 *Phone:* {order['customer']['phone']}\n"
            )
        else:
            customer_block = ""
        
        text = (
            f"🟥 *NEW ORDER* ({order['name']})\n"
            f"🛒 *Items:*\n{order['items_text']}\n"
            f"🕒 *Time:* {order['delivery_time']}"
            f"{same_time_line}"
        )
        
        if note:
            text += f"\n📝 *Note:* {note}"
        if customer_block:
            text = text + "\n\n" + customer_block
        
        return text
    except Exception as e:
        logger.error(f"Error building vendor text: {e}")
        return f"Error formatting order for {vendor}"

def mdg_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build MDG inline keyboard"""
    try:
        rows: List[List[InlineKeyboardButton]] = []
        
        # Assignment row (drivers)
        if DRIVERS:
            assign_row = [
                InlineKeyboardButton(f"Assign: {name}", callback_data=f"assign|{order_id}|{name}|{uid}") 
                for name, uid in DRIVERS.items()
            ]
            rows.append(assign_row)
        
        # Status row
        rows.append([
            InlineKeyboardButton("Delivered ✅", callback_data=f"delivered|{order_id}"),
            InlineKeyboardButton("Delay 🕧", callback_data=f"delayed|{order_id}")
        ])
        
        return InlineKeyboardMarkup(rows)
    except Exception as e:
        logger.error(f"Error building MDG keyboard: {e}")
        return InlineKeyboardMarkup([])

def vendor_keyboard(order_id: str, vendor: str, expanded: bool) -> InlineKeyboardMarkup:
    """Build vendor inline keyboard"""
    try:
        toggle = "Hide ⬆" if expanded else "Expand ⬇"
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle, callback_data=f"expand|{order_id}|{vendor}")],
            [InlineKeyboardButton("Works", callback_data=f"reply|{order_id}|{vendor}|Works"),
             InlineKeyboardButton("Later", callback_data=f"reply|{order_id}|{vendor}|Later"),
             InlineKeyboardButton("Will prepare", callback_data=f"reply|{order_id}|{vendor}|Will prepare")]
        ])
    except Exception as e:
        logger.error(f"Error building vendor keyboard: {e}")
        return InlineKeyboardMarkup([])

async def safe_send_message(chat_id: int, text: str, reply_markup=None, parse_mode=ParseMode.MARKDOWN):
    """Send message with error handling and retries"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return await bot.send_message(
                chat_id=chat_id, 
                text=text, 
                reply_markup=reply_markup, 
                parse_mode=parse_mode
            )
        except TimedOut:
            if attempt < max_retries - 1:
                logger.warning(f"Timeout sending message, retrying... (attempt {attempt + 1})")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                logger.error(f"Failed to send message after {max_retries} attempts due to timeout")
                raise
        except NetworkError as e:
            if attempt < max_retries - 1:
                logger.warning(f"Network error sending message, retrying... (attempt {attempt + 1}): {e}")
                await asyncio.sleep(2 ** attempt)
                continue
            else:
                logger.error(f"Failed to send message after {max_retries} attempts due to network error: {e}")
                raise
        except TelegramError as e:
            logger.error(f"Telegram error sending message: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error sending message: {e}")
            raise

async def safe_edit_message(chat_id: int, message_id: int, text: str, reply_markup=None, parse_mode=ParseMode.MARKDOWN):
    """Edit message with error handling"""
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except TelegramError as e:
        logger.error(f"Error editing message {message_id} in chat {chat_id}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error editing message: {e}")

# --- HEALTH CHECK ---
@app.route("/", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "telegram-dispatch-bot",
        "orders_in_state": len(STATE)
    }), 200

# --- TELEGRAM WEBHOOK ---
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    """Handle Telegram webhooks (callback queries)"""
    try:
        upd = request.get_json(force=True)
        if not upd:
            logger.warning("Empty update received")
            return "OK"
        
        # Only handling callback queries according to assignment
        cq = upd.get("callback_query")
        if not cq:
            return "OK"

        async def handle():
            try:
                # Quick ack to avoid spinner
                await bot.answer_callback_query(cq["id"])
            except Exception as e:
                logger.error(f"answer_callback_query error: {e}")
            
            data = (cq.get("data") or "").split("|")
            if not data:
                logger.warning("Empty callback data")
                return
            
            kind = data[0]
            logger.info(f"Processing callback: {kind}")
            
            try:
                if kind == "reply":
                    _, order_id, vendor, reply_text = data
                    # Post vendor reply to MDG
                    msg = f"🍴 *{vendor}* replied: \"{reply_text}\""
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, msg)
                    
                elif kind == "expand":
                    _, order_id, vendor = data
                    order = STATE.get(order_id)
                    if not order:
                        logger.warning(f"Order {order_id} not found in state")
                        return
                    
                    expanded = not order["vendor_expanded"].get(vendor, False)
                    order["vendor_expanded"][vendor] = expanded
                    chat_id = VENDOR_GROUP_MAP.get(vendor)
                    msg_id = order["vendor_msgs"].get(vendor)
                    
                    if chat_id and msg_id:
                        new_text = build_vendor_text(order, vendor, expanded)
                        await safe_edit_message(
                            chat_id=chat_id, 
                            message_id=msg_id, 
                            text=new_text, 
                            reply_markup=vendor_keyboard(order_id, vendor, expanded)
                        )
                    
                elif kind == "assign":
                    _, order_id, driver_name, driver_id = data
                    order = STATE.get(order_id)
                    if not order:
                        logger.warning(f"Order {order_id} not found in state")
                        return
                    
                    # Send DM to driver
                    dm_text = (
                        f"🟨 *NEW ASSIGNMENT* ({order['name']})\n"
                        f"🕒 Time: {order['delivery_time']}\n"
                        f"📍 {order['customer']['address']}\n"
                        f"👤 {order['customer']['name']} — {order['customer']['phone']}\n\n"
                        f"🛒 Items:\n{order['items_text']}"
                    )
                    
                    try:
                        await safe_send_message(int(driver_id), dm_text)
                        logger.info(f"Assignment sent to {driver_name}")
                    except Exception as e:
                        await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"⚠️ Could not DM {driver_name} — {e}")
                    
                    # Update status + edit MDG
                    order["status"] = "🟨"
                    order["assigned_to"] = driver_name
                    await safe_edit_message(
                        chat_id=DISPATCH_MAIN_CHAT_ID, 
                        message_id=order["dispatch_msg_id"], 
                        text=build_dispatch_text(order), 
                        reply_markup=mdg_keyboard(order_id)
                    )
                    
                elif kind == "delivered":
                    _, order_id = data
                    order = STATE.get(order_id)
                    if not order:
                        logger.warning(f"Order {order_id} not found in state")
                        return
                    
                    order["status"] = "🟩"
                    await safe_edit_message(
                        chat_id=DISPATCH_MAIN_CHAT_ID, 
                        message_id=order["dispatch_msg_id"], 
                        text=build_dispatch_text(order), 
                        reply_markup=mdg_keyboard(order_id)
                    )
                    
                elif kind == "delayed":
                    _, order_id = data
                    order = STATE.get(order_id)
                    if not order:
                        logger.warning(f"Order {order_id} not found in state")
                        return
                    
                    order["status"] = "🟧"
                    await safe_edit_message(
                        chat_id=DISPATCH_MAIN_CHAT_ID, 
                        message_id=order["dispatch_msg_id"], 
                        text=build_dispatch_text(order), 
                        reply_markup=mdg_keyboard(order_id)
                    )
                    
            except Exception as e:
                logger.error(f"Callback handle error: {e}")
        
        asyncio.run(handle())
        return "OK"
        
    except Exception as e:
        logger.error(f"Telegram webhook error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# --- SHOPIFY WEBHOOK ---
@app.route("/webhooks/shopify", methods=["POST"])
def shopify_webhook():
    """Handle Shopify webhooks"""
    try:
        raw = request.get_data()
        hmac_header = request.headers.get("X-Shopify-Hmac-Sha256")
        
        if not verify_webhook(raw, hmac_header):
            logger.warning("Unauthorized Shopify webhook attempt")
            return jsonify({"error": "Unauthorized"}), 401

        try:
            payload = json.loads(raw.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in Shopify webhook: {e}")
            return jsonify({"error": "Invalid JSON"}), 400

        order_id = str(payload.get("id"))
        if not order_id:
            logger.error("No order ID in Shopify webhook")
            return jsonify({"error": "No order ID"}), 400

        logger.info(f"Processing Shopify order: {order_id}")

        # Extract order data with safe defaults
        order_name = payload.get("name", "Unknown")
        customer = payload.get("customer") or {}
        customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or "Unknown"
        phone = customer.get("phone") or payload.get("phone") or "N/A"
        address = fmt_address(payload.get("shipping_address") or {})
        items = payload.get("line_items") or []
        note = payload.get("note", "")
        
        # Handle delivery time
        delivery_method = payload.get("delivery_method") or {}
        delivery_time = delivery_method.get("requested_fulfillment_time") or "ASAP"
        
        # Extract vendors from tags
        tags = payload.get("tags", "")
        vendors = [v.strip() for v in tags.split(",") if v.strip()] if tags else []

        # Build items text
        items_text = "\n".join([
            f"- {item.get('quantity', 1)} x {item.get('name', 'Item')}" 
            for item in items
        ]) if items else "No items"

        # Build order object for state
        order = {
            "name": order_name,
            "delivery_time": delivery_time,
            "customer": {
                "name": customer_name, 
                "phone": phone, 
                "address": address
            },
            "items_text": items_text,
            "note": note,
            "vendors": vendors,
            "vendor_msgs": {},
            "vendor_expanded": {},
            "status": "🟥",
            "assigned_to": None,
        }

        async def process():
            try:
                # Send MDG message with inline controls
                mdg_text = build_dispatch_text(order)
                mdg_msg = await safe_send_message(
                    DISPATCH_MAIN_CHAT_ID, 
                    mdg_text, 
                    reply_markup=mdg_keyboard(order_id)
                )
                order["dispatch_msg_id"] = mdg_msg.message_id

                # Send vendor messages
                for vendor in vendors:
                    group_id = VENDOR_GROUP_MAP.get(vendor)
                    if not group_id:
                        logger.warning(f"No group ID found for vendor: {vendor}")
                        continue
                    
                    v_text = build_vendor_text(order, vendor, expanded=False)
                    keyboard = vendor_keyboard(order_id, vendor, expanded=False)
                    v_msg = await safe_send_message(group_id, v_text, reply_markup=keyboard)
                    order["vendor_msgs"][vendor] = v_msg.message_id
                    order["vendor_expanded"][vendor] = False

                # Save to state last, after messages are created
                STATE[order_id] = order
                logger.info(f"Order {order_id} processed successfully")
                
            except Exception as e:
                logger.error(f"Error processing order {order_id}: {e}")
                raise

        asyncio.run(process())
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        logger.error(f"Shopify webhook error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# --- APP ENTRY ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Telegram Dispatch Bot on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)

# Telegram Dispatch Bot — Complete Assignment Implementation
# All features from requirements document implemented

# =============================================================================
# MAIN WORKFLOW OVERVIEW
# =============================================================================
# Order placed → arrives in MDG and RG → user requests time from restaurants
# → restaurants confirm time → user receives info in MDG → assigns to himself
# or another user (private chat with BOT) → order delivered → user confirms
# delivery → order state changed to delivered
#
# CODE ORGANIZATION:
# 1. MDG - Main Dispatching Group: Order arrival, time requests, status updates
# 2. RG - Restaurant Groups: Vendor communications, response handling
# 3. UPC - User Private Chats: Assignment logic, DMs, completion workflows
# =============================================================================

import os
import json
import hmac
import hashlib
import base64
import asyncio
import logging
import threading
import requests  # Add this for synchronous HTTP calls
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import Flask, request, jsonify
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest
from telegram.error import TelegramError, TimedOut, NetworkError

# Import modular components
import mdg
import rg
import upc

# Import shared utilities and state
from utils import (
    STATE, RECENT_ORDERS, DISPATCH_MAIN_CHAT_ID, VENDOR_GROUP_MAP, COURIER_MAP,
    RESTAURANT_SHORTCUTS, logger, safe_send_message, safe_edit_message,
    safe_delete_message, cleanup_mdg_messages, validate_phone, verify_webhook
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- FLASK APP SETUP ---
app = Flask(__name__)

# --- ENVIRONMENT VARIABLES ---
BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_SECRET = os.environ["SHOPIFY_WEBHOOK_SECRET"]
DISPATCH_MAIN_CHAT_ID = int(os.environ["DISPATCH_MAIN_CHAT_ID"])
VENDOR_GROUP_MAP: Dict[str, int] = json.loads(os.environ.get("VENDOR_GROUP_MAP", "{}"))
DRIVERS: Dict[str, int] = json.loads(os.environ.get("DRIVERS", "{}"))

# --- CONSTANTS AND MAPPINGS ---
# Restaurant shortcut mapping (per assignment in Doc)
RESTAURANT_SHORTCUTS = {
    "Julis Spätzlerei": "JS",
    "Zweite Heimat": "ZH", 
    "Kahaani": "KA",
    "i Sapori della Toscana": "SA",
    "Leckerolls": "LR",
    "dean & david": "DD",
    "Pommes Freunde": "PF",
    "Wittelsbacher Apotheke": "AP"
}

# --- TELEGRAM BOT CONFIGURATION ---
# Configure request with larger pool to prevent pool timeout
request_cfg = HTTPXRequest(
    connection_pool_size=32,
    pool_timeout=30.0,
    read_timeout=30.0,
    write_timeout=30.0,
    connect_timeout=15.0,
)
bot = Bot(token=BOT_TOKEN, request=request_cfg)

# Create event loop for async operations
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def run_async(coro):
    """Run async function in background thread"""
    asyncio.run_coroutine_threadsafe(coro, loop)

def validate_phone(phone: str) -> Optional[str]:
    """Validate and format phone number for tel: links"""
    if not phone or phone == "N/A":
        return None
    
    # Remove non-numeric characters except + and spaces
    import re
    cleaned = re.sub(r'[^\d+\s]', '', phone).strip()
    
    # Basic validation: must have at least 7 digits
    digits_only = re.sub(r'\D', '', cleaned)
    if len(digits_only) < 7:
        return None
    
    return cleaned

# --- HELPER FUNCTIONS ---
def verify_webhook(raw: bytes, hmac_header: str) -> bool:
    """Verify Shopify webhook HMAC"""
    try:
        if not hmac_header:
            return False
        computed = hmac.new(WEBHOOK_SECRET.encode("utf-8"), raw, hashlib.sha256).digest()
        expected = base64.b64encode(computed).decode("utf-8")
        return hmac.compare_digest(expected, hmac_header)
    except Exception as e:
        logger.error(f"HMAC verification error: {e}")
        return False

# --- ASYNC UTILITY FUNCTIONS ---
async def safe_send_message(chat_id: int, text: str, reply_markup=None, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True):
    """Send message with error handling and retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Send message attempt {attempt + 1}")
            return await bot.send_message(
                chat_id=chat_id, 
                text=text, 
                reply_markup=reply_markup, 
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview
            )
        except Exception as e:
            logger.error(f"Send message attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            else:
                logger.error(f"Failed to send message after {max_retries} attempts: {e}")
                raise

async def safe_edit_message(chat_id: int, message_id: int, text: str, reply_markup=None, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True):
    """Edit message with error handling"""
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview
        )
    except Exception as e:
        logger.error(f"Error editing message: {e}")

async def safe_delete_message(chat_id: int, message_id: int):
    """Delete message with error handling"""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"Successfully deleted message {message_id}")
    except Exception as e:
        logger.error(f"Error deleting message {message_id}: {e}")

async def cleanup_mdg_messages(order_id: str):
    """Clean up additional MDG messages, keeping only the original order message"""
    order = STATE.get(order_id)
    if not order:
        return
    
    additional_messages = order.get("mdg_additional_messages", [])
    if not additional_messages:
        return
    
    logger.info(f"Cleaning up {len(additional_messages)} additional MDG messages for order {order_id}")
    
    for message_id in additional_messages:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await bot.delete_message(chat_id=DISPATCH_MAIN_CHAT_ID, message_id=message_id)
                logger.info(f"Successfully deleted MDG message {message_id} for order {order_id}")
                break
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed to delete message {message_id}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                else:
                    logger.error(f"Failed to delete message {message_id} after {max_retries} attempts")
    
    # Clear the list after cleanup
    order["mdg_additional_messages"] = []

# --- WEBHOOK ENDPOINTS ---
@app.route("/", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        "status": "healthy",
        "service": "telegram-dispatch-bot",
        "orders_in_state": len(STATE),
        "timestamp": datetime.now().isoformat()
    }), 200

# --- TELEGRAM WEBHOOK ---
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    """Handle Telegram webhooks"""
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        if not update:
            return "OK"

        # Log all incoming updates for spam detection
        logger.info(f"=== INCOMING UPDATE ===")
        logger.info(f"Update ID: {update.update_id}")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")

        # Check for regular messages (potential spam source)
        if update.message:
            msg = update.message
            from_user = msg.from_user
            chat = msg.chat
            text = msg.text or ""

            logger.info(f"MESSAGE RECEIVED:")
            logger.info(f"  Chat ID: {chat.id}")
            logger.info(f"  Chat Type: {chat.type}")
            logger.info(f"  Chat Title: {chat.title or 'N/A'}")
            logger.info(f"  From User ID: {from_user.id if from_user else 'N/A'}")
            logger.info(f"  From Username: {from_user.username if from_user else 'N/A'}")
            logger.info(f"  From First Name: {from_user.first_name if from_user else 'N/A'}")
            logger.info(f"  From Last Name: {from_user.last_name if from_user else 'N/A'}")
            logger.info(f"  Message Text: {text[:200]}{'...' if len(text) > 200 else ''}")
            logger.info(f"  Message Length: {len(text)}")

            # Flag potential spam
            if "FOXY" in text.upper() or "airdrop" in text.lower() or "t.me/" in text:
                logger.warning(f"🚨 POTENTIAL SPAM DETECTED: {text[:100]}...")

        cq = update.callback_query
        if not cq:
            logger.info("=== NO CALLBACK QUERY - END UPDATE ===")
            return "OK"

        # Answer callback query immediately (synchronously)
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery",
                json={"callback_query_id": cq.id},
                timeout=5
            )
            if not response.ok:
                logger.error(f"Failed to answer callback query: {response.text}")
        except Exception as e:
            logger.error(f"answer_callback_query error: {e}")
        
        # Process the callback in background
        async def handle():
            data = (cq.data or "").split("|")
            if not data:
                return
            
            action = data[0]
            logger.info(f"Raw callback data: {cq.data}")
            logger.info(f"Parsed callback data: {data}")
            logger.info(f"Processing callback: {action}")
            
            try:
                # DELEGATE MDG CALLBACKS TO MDG MODULE
                mdg_actions = ["req_vendor", "vendor_asap", "vendor_time", "vendor_same", "vendor_exact", "smart_time", "req_asap", "req_time", "time_plus", "req_same", "no_recent", "req_exact", "same_selected", "exact_hour", "exact_selected", "exact_back_hours", "exact_hide", "toggle"]
                if action in mdg_actions:
                    await mdg.handle_mdg_callback(action, data, cq)

                # DELEGATE RG CALLBACKS TO RG MODULE
                elif action in ["works", "later", "later_time", "prepare", "prepare_time", "wrong", "wrong_unavailable", "wrong_canceled", "wrong_technical", "wrong_other", "wrong_delay", "delay_time"]:
                    await rg.handle_rg_callback(action, data, cq)

                # DELEGATE UPC CALLBACKS TO UPC MODULE
                elif action in ["assign_user", "mark_delivered", "assign_me", "delay_order", "call_restaurant", "select_restaurant", "confirm_delivered", "delay_minutes", "delay_custom"]:
                    user_id = cq.from_user.id
                    await upc.handle_assignment_callback(action, data, user_id)

            except Exception as e:
                logger.error(f"Callback processing error: {e}")
        
        # Run the async handler in background
        run_async(handle())
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
            return jsonify({"error": "Unauthorized"}), 401

        payload = json.loads(raw.decode('utf-8'))
        order_id = str(payload.get("id"))
        
        logger.info(f"Processing Shopify order: {order_id}")

        # Extract order data
        order_name = payload.get("name", "Unknown")
        
        # Extract customer data with enhanced phone extraction
        customer = payload.get("customer") or {}
        customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or "Unknown"
        
        # Enhanced phone extraction from multiple sources
        phone = (
            customer.get("phone") or 
            payload.get("phone") or 
            payload.get("billing_address", {}).get("phone") or 
            payload.get("shipping_address", {}).get("phone") or 
            "N/A"
        )
        
        # Validate and format phone
        phone = validate_phone(phone)
        if not phone:
            logger.warning(f"Phone number missing or invalid for order {order_id}")
            phone = "N/A"
        
        address = mdg.fmt_address(payload.get("shipping_address") or {})
        
        # Store original address for clean Google Maps URL
        shipping_addr = payload.get("shipping_address", {})
        original_address = f"{shipping_addr.get('address1', '')}, {shipping_addr.get('zip', '')}".strip()
        if original_address == ", " or not original_address:
            original_address = address  # fallback to formatted address
        
        # Extract vendors from line items
        line_items = payload.get("line_items", [])
        vendors = []
        vendor_items = {}
        items_text = ""
        
        for item in line_items:
            vendor = item.get('vendor')
            if vendor and vendor in VENDOR_GROUP_MAP:
                if vendor not in vendors:
                    vendors.append(vendor)
                    vendor_items[vendor] = []
                
                item_line = f"- {item.get('quantity', 1)} x {item.get('name', 'Item')}"
                vendor_items[vendor].append(item_line)
        
        # Build items text
        if len(vendors) > 1:
            # Multi-vendor: show vendor names above items
            items_by_vendor = ""
            for vendor in vendors:
                items_by_vendor += f"\n{vendor}:\n" + "\n".join(vendor_items[vendor]) + "\n"
            items_text = items_by_vendor.strip()
        else:
            # Single vendor: just list items
            all_items = []
            for vendor_item_list in vendor_items.values():
                all_items.extend(vendor_item_list)
            items_text = "\n".join(all_items)
        
        # Check for pickup orders
        is_pickup = False
        payload_str = str(payload).lower()
        if "abholung" in payload_str:
            is_pickup = True
            logger.info("Pickup order detected (Abholung found in payload)")
        
        # Extract payment method and total from Shopify payload
        payment_method = "Paid"  # Default
        total_price = "0.00"     # Default
        
        # Check payment gateway names for CoD detection
        payment_gateways = payload.get("payment_gateway_names", [])
        if payment_gateways:
            gateway_str = " ".join(payment_gateways).lower()
            if "cash" in gateway_str and "delivery" in gateway_str:
                payment_method = "Cash on Delivery"
        
        # Check transactions for more detailed payment info
        transactions = payload.get("transactions", [])
        for transaction in transactions:
            gateway = transaction.get("gateway", "").lower()
            if "cash" in gateway and "delivery" in gateway:
                payment_method = "Cash on Delivery"
                break
        
        # Extract total price
        total_price_raw = payload.get("total_price", "0.00")
        try:
            # Format as currency with 2 decimal places
            total_price = f"{float(total_price_raw):.2f}€"
        except (ValueError, TypeError):
            total_price = "0.00€"
        
        logger.info(f"Payment method: {payment_method}, Total: {total_price}")
        
        # Extract tips from Shopify payload
        tips = 0.0
        try:
            # Check for the actual tip field used by Shopify
            if payload.get("total_tip_received"):
                tips = float(payload["total_tip_received"])
            elif payload.get("total_tip"):
                tips = float(payload["total_tip"])
            elif payload.get("tip_money") and payload["tip_money"].get("amount"):
                tips = float(payload["tip_money"]["amount"])
            elif payload.get("total_tips_set") and payload["total_tips_set"].get("shop_money", {}).get("amount"):
                tips = float(payload["total_tips_set"]["shop_money"]["amount"])
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Error extracting tips for order {order_id}: {e}")
            tips = 0.0
        
        # Build order object
        order = {
            "name": order_name,
            "order_type": "shopify",
            "vendors": vendors,
            "customer": {
                "name": customer_name,
                "phone": phone,
                "address": address,
                "original_address": original_address
            },
            "items_text": items_text,
            "vendor_items": vendor_items,
            "note": payload.get("note", ""),
            "tips": tips,
            "payment_method": payment_method,
            "total": total_price,
            "delivery_time": "ASAP",
            "is_pickup": is_pickup,
            "created_at": datetime.now(),
            "vendor_messages": {},
            "vendor_expanded": {},
            "requested_time": None,
            "confirmed_time": None,
            "vendor_confirmed_times": {},  # Track confirmed times per vendor
            "assigned_to": None,
            "assigned_at": None,
            "assigned_by": None,
            "assignment_messages": {},  # Track assignment messages per user
            "delivered_at": None,
            "delivered_by": None,
            "status": "new",
            "mdg_additional_messages": []  # Track additional MDG messages for cleanup
        }
        
        # Save order to STATE first
        STATE[order_id] = order
        
        logger.info(f"Order {order_id} has vendors: {vendors} (count: {len(vendors)})")
        if len(vendors) > 1:
            logger.info(f"MULTI-VENDOR detected: {vendors}")
        else:
            logger.info(f"SINGLE VENDOR detected: {vendors}")

        async def process():
            try:
                # Send to MDG with appropriate buttons
                mdg_text = mdg.build_mdg_dispatch_text(order)
                
                # Special formatting for pickup orders
                if is_pickup:
                    pickup_header = "**Order for Selbstabholung**\n"
                    pickup_message = f"\nPlease call the customer and arrange the pickup time on this number: {phone}"
                    mdg_text = pickup_header + mdg_text + pickup_message
                
                mdg_msg = await safe_send_message(
                    DISPATCH_MAIN_CHAT_ID,
                    mdg_text,
                    mdg.mdg_time_request_keyboard(order_id)
                )
                order["mdg_message_id"] = mdg_msg.message_id
                
                # Send to each vendor group (summary by default)
                for vendor in vendors:
                    vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                    if vendor_chat:
                        vendor_text = mdg.build_vendor_summary_text(order, vendor)
                        # Order message has only expand/collapse button
                        vendor_msg = await safe_send_message(
                            vendor_chat,
                            vendor_text,
                            mdg.vendor_keyboard(order_id, vendor, False)
                        )
                        order["vendor_messages"][vendor] = vendor_msg.message_id
                        order["vendor_expanded"][vendor] = False
                
                # Update STATE with message IDs
                STATE[order_id] = order
                
                # Keep only recent orders
                RECENT_ORDERS.append({
                    "order_id": order_id,
                    "created_at": datetime.now(),
                    "vendors": vendors
                })
                
                if len(RECENT_ORDERS) > 50:
                    RECENT_ORDERS.pop(0)
                
                logger.info(f"Order {order_id} processed successfully")
                
            except Exception as e:
                logger.error(f"Error processing order: {e}")
                raise

        run_async(process())
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        logger.error(f"Shopify webhook error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# --- APPLICATION ENTRY POINT ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Starting Complete Assignment Implementation on port {port}")
    
    # Start the event loop in a separate thread
    def run_event_loop():
        asyncio.set_event_loop(loop)
        loop.run_forever()
    
    loop_thread = threading.Thread(target=run_event_loop)
    loop_thread.daemon = True
    loop_thread.start()
    
    app.run(host="0.0.0.0", port=port, debug=False)

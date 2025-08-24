# Telegram Dispatch Bot — Complete Assignment Implementation
# All features from requirements document implemented

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
DISPATCH_MAIN_CHAT_ID = int(os.environ["DISPATCH_MAIN_CHAT_ID"])
VENDOR_GROUP_MAP: Dict[str, int] = json.loads(os.environ.get("VENDOR_GROUP_MAP", "{}"))
DRIVERS: Dict[str, int] = json.loads(os.environ.get("DRIVERS", "{}"))

# Restaurant tag mapping
TAG_TO_RESTAURANT = {
    "JS": "Julis Spätzlerei",
    "ZH": "Zweite Heimat", 
    "KA": "Kahaani",
    "SA": "i Sapori della Toscana",
    "LR": "Leckerolls",
    "DD": "dean & david",
    "PF": "Pommes Freunde",
    "AP": "Wittelsbacher Apotheke"
}

# Reverse mapping for getting shortcuts from restaurant names
RESTAURANT_TO_TAG = {v: k for k, v in TAG_TO_RESTAURANT.items()}

# Configure request with larger pool to prevent pool timeout
request_cfg = HTTPXRequest(
    connection_pool_size=32,
    pool_timeout=30.0,
    read_timeout=30.0,
    write_timeout=30.0,
    connect_timeout=15.0,
)
bot = Bot(token=BOT_TOKEN, request=request_cfg)

# --- STATE ---
STATE: Dict[str, Dict[str, Any]] = {}
RECENT_ORDERS: List[Dict[str, Any]] = []

# Global event loop for async operations
loop = None
loop_thread = None

def start_event_loop():
    """Start the event loop in a separate thread"""
    global loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_forever()

# Start event loop thread
loop_thread = threading.Thread(target=start_event_loop, daemon=True)
loop_thread.start()

# Wait for loop to be ready
import time
time.sleep(0.5)

def run_async(coro):
    """Run async function in the global event loop"""
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=30)

# --- HELPERS ---
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

def fmt_address(addr: Dict[str, Any]) -> str:
    """Format address - only street, building number and zip code (no city!)"""
    if not addr:
        return "N/A"
    street = f"{addr.get('address1', '')} {addr.get('address2', '')}".strip()
    zip_code = addr.get('zip', '')
    if street and zip_code:
        return f"{street}, {zip_code}"
    return street or zip_code or "N/A"

def build_mdg_dispatch_text(order: Dict[str, Any]) -> str:
    """Build MDG dispatch message text per assignment"""
    try:
        text = "🟥 NEW ORDER\n\n"
        
        # Order number and vendors
        text += f"#{order['name'][-2:]}\n"
        if len(order['vendors']) > 1:
            text += f"Vendors: {', '.join(order['vendors'])}\n"
        elif order['vendors']:
            text += f"Vendor: {order['vendors'][0]}\n"
        
        # Pickup order handling
        if order.get('is_pickup'):
            text += "\n**Order for Selbstabholung**\n"
            text += f"Please call the customer and arrange the pickup time on this number: {order['customer']['phone']}\n\n"
        
        # Customer details
        text += f"Customer: {order['customer']['name']}\n"
        text += f"Phone: {order['customer']['phone']}\n"
        text += f"Address: {order['customer']['address']}\n\n"
        
        # Items
        text += "Items:\n"
        text += order['items_text']
        
        # Note, tips, payment
        if order.get('note'):
            text += f"\n\nNote: {order['note']}"
        if order.get('tips'):
            text += f"\nTips: {order['tips']}"
        if order['order_type'] == 'shopify':
            text += f"\nPayment: {order.get('payment_method', 'Paid')}"
        
        return text
    except Exception as e:
        logger.error(f"Error building MDG text: {e}")
        return f"Error formatting order {order.get('name', 'Unknown')}"

def build_vendor_summary_text(order: Dict[str, Any], vendor: str) -> str:
    """Build vendor summary (collapsed state) - ONLY order number + products + note"""
    try:
        order_number = order['name'][-2:]
        
        # Get vendor-specific items or fallback to all items
        vendor_items = order.get("vendor_items", {}).get(vendor, [])
        if vendor_items:
            items_text = "\n".join(vendor_items)
        else:
            items_text = order.get("items_text", "")
        
        # Note if added (ONLY note, no other details)
        note = order.get("note", "")
        
        # Build summary: ONLY order number + products + note
        text = f"Order {order_number}\n"
        text += f"{items_text}"
        if note:
            text += f"\nNote: {note}"
        
        return text
    except Exception as e:
        logger.error(f"Error building vendor summary: {e}")
        return f"Error formatting order for {vendor}"

def build_vendor_details_text(order: Dict[str, Any], vendor: str) -> str:
    """Build vendor full details (expanded state) - FIXED per assignment"""
    try:
        # Start with summary (order number + products + note)
        summary = build_vendor_summary_text(order, vendor)
        
        # Add customer details for expanded view
        customer_name = order['customer']['name']
        phone = order['customer']['phone']
        order_time = order.get('created_at', datetime.now()).strftime('%H:%M')
        address = order['customer']['address']
        
        # Build expanded: summary + customer details
        details = f"{summary}\n\n"
        details += f"Customer: {customer_name}\n"
        details += f"Phone: {phone}\n"
        details += f"Time of order: {order_time}\n"
        details += f"Address: {address}"
        
        return details
    except Exception as e:
        logger.error(f"Error building vendor details: {e}")
        return f"Error formatting details for {vendor}"

def mdg_time_request_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build MDG time request buttons per assignment - now vendor-specific for multi-vendor"""
    try:
        order = STATE.get(order_id)
        if not order:
            # Fallback for missing order
            return InlineKeyboardMarkup([[InlineKeyboardButton("Request ASAP", callback_data=f"req_asap|{order_id}")]])
        
        vendors = order.get("vendors", [])
        
        # Multi-vendor: show ONLY restaurant selection buttons with shortcuts
        if len(vendors) > 1:
            logger.info(f"MULTI-VENDOR detected: {vendors}")
            buttons = []
            for vendor in vendors:
                # Use shortcuts for buttons
                tag = RESTAURANT_TO_TAG.get(vendor, vendor[:2].upper())
                buttons.append([InlineKeyboardButton(f"Request {tag}", callback_data=f"req_vendor|{order_id}|{vendor}")])
            return InlineKeyboardMarkup(buttons)
        
        # Single vendor: show standard buttons (NO SAME TIME AS)
        logger.info(f"SINGLE VENDOR detected: {vendors}")
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Request ASAP", callback_data=f"req_asap|{order_id}"),
                InlineKeyboardButton("Request TIME", callback_data=f"req_time|{order_id}")
            ]
        ])
        
    except Exception as e:
        logger.error(f"Error building MDG keyboard: {e}")
        return InlineKeyboardMarkup([[InlineKeyboardButton("Request ASAP", callback_data=f"req_asap|{order_id}")]])

def build_smart_time_suggestions(order_id: str, vendor: str = None) -> tuple:
    """Build smart time suggestions with new format per assignment"""
    try:
        # Get the last confirmed order for this vendor
        last_confirmed = None
        for oid, o in reversed(list(STATE.items())):
            if (o.get("confirmed_time") and 
                o.get("confirmed_by") == vendor and
                oid != order_id):
                last_confirmed = o
                break
        
        buttons = []
        message_text = ""
        
        # If we have a last confirmed order, show the new format
        if last_confirmed:
            # Get details from last confirmed order
            last_address = last_confirmed['customer']['address'].split(',')[0]  # Street only
            last_tag = RESTAURANT_TO_TAG.get(vendor, vendor[:2].upper()) if vendor else ""
            last_order_num = last_confirmed['name'][-2:]
            last_time = last_confirmed.get("confirmed_time", "")
            
            # Build title for message (not a button)
            message_text = f"{last_address} ({last_tag}, #{last_order_num}, {last_time}) +\n\n"
            
            # Add +5, +10, +15, +20 buttons
            buttons.append([
                InlineKeyboardButton("+5", callback_data=f"smart_plus|{order_id}|{vendor}|5"),
                InlineKeyboardButton("+10", callback_data=f"smart_plus|{order_id}|{vendor}|10"),
                InlineKeyboardButton("+15", callback_data=f"smart_plus|{order_id}|{vendor}|15"),
                InlineKeyboardButton("+20", callback_data=f"smart_plus|{order_id}|{vendor}|20")
            ])
            
            message_text += "Same as:\n"
        
        # Find confirmed but not delivered orders for "Same as" section
        same_as_orders = []
        for oid, o in STATE.items():
            if (o.get("confirmed_time") and 
                not o.get("delivered", False) and
                oid != order_id):
                # Build the display format for each order
                order_address = o['customer']['address'].split(',')[0]
                order_vendor = o.get("confirmed_by") or (o['vendors'][0] if o['vendors'] else "")
                order_tag = RESTAURANT_TO_TAG.get(order_vendor, order_vendor[:2].upper()) if order_vendor else ""
                order_num = o['name'][-2:]
                order_time = o['confirmed_time']
                
                button_text = f"{order_address} ({order_tag}, #{order_num}, {order_time})"
                same_as_orders.append([InlineKeyboardButton(
                    button_text,
                    callback_data=f"same_selected|{order_id}|{oid}"
                )])
        
        if same_as_orders:
            buttons.extend(same_as_orders[:5])  # Limit to 5 most recent
        
        # Always add EXACT TIME button at the bottom
        message_text += "\n\nRequest exact time:"
        buttons.append([InlineKeyboardButton("EXACT TIME", callback_data=f"req_exact|{order_id}|{vendor or ''}")])
        
        return InlineKeyboardMarkup(buttons), message_text
        
    except Exception as e:
        logger.error(f"Error building smart suggestions: {e}")
        return InlineKeyboardMarkup([[InlineKeyboardButton("EXACT TIME", callback_data=f"req_exact|{order_id}|")]]), "Select time:"

def get_recent_orders_for_same_time(current_order_id: str) -> List[Dict[str, Any]]:
    """Get recent orders from last hour for 'same time' selection"""
    try:
        recent = []
        current_time = datetime.now()
        one_hour_ago = current_time - timedelta(hours=1)
        
        for order_id, order in STATE.items():
            if order_id != current_order_id:
                created_at = order.get('created_at', current_time)
                if created_at > one_hour_ago:
                    recent.append({
                        'id': order_id,
                        'name': order['name'],
                        'vendors': order['vendors'],
                        'created_at': created_at
                    })
        
        # Sort by creation time, most recent first
        recent.sort(key=lambda x: x['created_at'], reverse=True)
        return recent[:10]  # Return max 10 recent orders
        
    except Exception as e:
        logger.error(f"Error getting recent orders: {e}")
        return []

async def safe_send_message(chat_id: int, text: str, parse_mode: str = None, reply_markup: InlineKeyboardMarkup = None, max_retries: int = 3) -> Optional[Any]:
    """Send message with retry logic"""
    for attempt in range(max_retries):
        try:
            msg = await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            return msg
        except (TimedOut, NetworkError) as e:
            logger.warning(f"Network error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
        except TelegramError as e:
            logger.error(f"Telegram error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error sending message: {e}")
            return None
    return None

async def safe_edit_message(chat_id: int, message_id: int, text: str, parse_mode: str = None, reply_markup: InlineKeyboardMarkup = None, max_retries: int = 3) -> bool:
    """Edit message with retry logic"""
    for attempt in range(max_retries):
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            return True
        except (TimedOut, NetworkError) as e:
            logger.warning(f"Network error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
        except TelegramError as e:
            logger.error(f"Telegram error editing message: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error editing message: {e}")
            return False
    return False

def answer_callback_sync(callback_query_id: str, text: str = None, show_alert: bool = False) -> bool:
    """Answer callback query synchronously using requests"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
        payload = {
            "callback_query_id": callback_query_id,
            "text": text or "",
            "show_alert": show_alert
        }
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"answer_callback_sync error: {e}")
        return False

# --- ROUTES ---
@app.route("/", methods=["GET", "HEAD"])
def health_check():
    """Health check endpoint"""
    return "OK", 200

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    """Handle Telegram webhooks"""
    try:
        update = request.get_json()
        
        # Handle callback queries
        if "callback_query" in update:
            callback_query = update["callback_query"]
            callback_query_id = callback_query["id"]
            data = callback_query["data"]
            
            # Answer callback immediately (synchronously)
            answer_callback_sync(callback_query_id)
            
            # Process callback in background
            def process_callback():
                try:
                    # Parse callback data
                    parts = data.split("|")
                    action = parts[0]
                    
                    logger.info(f"Processing callback: {action}")
                    
                    if action == "req_asap":
                        order_id = parts[1]
                        order = STATE.get(order_id)
                        if not order:
                            logger.warning(f"Order {order_id} not found in state")
                            return
                        
                        order["requested_time"] = "ASAP"
                        
                        # Send to all vendors
                        for vendor in order["vendors"]:
                            vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                            if vendor_chat:
                                msg = f"#{order['name'][-2:]} ASAP?"
                                asap_buttons = InlineKeyboardMarkup([
                                    [InlineKeyboardButton("Will prepare at", callback_data=f"prepare_time|{order_id}|{vendor}")],
                                    [InlineKeyboardButton("Something is wrong", callback_data=f"wrong|{order_id}|{vendor}")]
                                ])
                                run_async(safe_send_message(vendor_chat, msg, reply_markup=asap_buttons))
                        
                        # Update MDG with status
                        run_async(safe_send_message(DISPATCH_MAIN_CHAT_ID, f"🟨 #{order['name'][-2:]} - Requested ASAP from vendors"))
                    
                    elif action == "req_time":
                        order_id = parts[1]
                        order = STATE.get(order_id)
                        if not order:
                            logger.warning(f"Order {order_id} not found in state")
                            return
                        
                        # Single vendor - show smart suggestions
                        if len(order["vendors"]) == 1:
                            vendor = order["vendors"][0]
                            keyboard, message_text = build_smart_time_suggestions(order_id, vendor)
                            run_async(safe_send_message(DISPATCH_MAIN_CHAT_ID, message_text, reply_markup=keyboard))
                    
                    elif action == "req_vendor":
                        # Multi-vendor: after selecting restaurant, show time options
                        order_id, vendor = parts[1], parts[2]
                        order = STATE.get(order_id)
                        if not order:
                            return
                        
                        # Show ASAP/TIME options for selected vendor
                        buttons = InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton("Request ASAP", callback_data=f"vendor_asap|{order_id}|{vendor}"),
                                InlineKeyboardButton("Request TIME", callback_data=f"vendor_time|{order_id}|{vendor}")
                            ]
                        ])
                        run_async(safe_send_message(DISPATCH_MAIN_CHAT_ID, f"Time request for {vendor}:", reply_markup=buttons))
                    
                    elif action == "vendor_asap":
                        order_id, vendor = parts[1], parts[2]
                        order = STATE.get(order_id)
                        if not order:
                            return
                        
                        vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                        if vendor_chat:
                            msg = f"#{order['name'][-2:]} ASAP?"
                            asap_buttons = InlineKeyboardMarkup([
                                [InlineKeyboardButton("Will prepare at", callback_data=f"prepare_time|{order_id}|{vendor}")],
                                [InlineKeyboardButton("Something is wrong", callback_data=f"wrong|{order_id}|{vendor}")]
                            ])
                            run_async(safe_send_message(vendor_chat, msg, reply_markup=asap_buttons))
                            run_async(safe_send_message(DISPATCH_MAIN_CHAT_ID, f"🟨 Requested ASAP from {vendor}"))
                    
                    elif action == "vendor_time":
                        order_id, vendor = parts[1], parts[2]
                        keyboard, message_text = build_smart_time_suggestions(order_id, vendor)
                        msg = f"Select time for {vendor}:\n\n{message_text}"
                        run_async(safe_send_message(DISPATCH_MAIN_CHAT_ID, msg, reply_markup=keyboard))
                    
                    elif action == "smart_plus":
                        order_id, vendor, minutes = parts[1], parts[2], int(parts[3])
                        order = STATE.get(order_id)
                        if not order:
                            return
                        
                        # Find last confirmed order for this vendor to calculate time
                        last_confirmed = None
                        for oid, o in reversed(list(STATE.items())):
                            if o.get("confirmed_time") and o.get("confirmed_by") == vendor:
                                last_confirmed = o
                                break
                        
                        if last_confirmed and last_confirmed.get("confirmed_time"):
                            # Parse the time and add minutes
                            try:
                                # Assuming time format is "HH:MM"
                                time_parts = last_confirmed["confirmed_time"].split(":")
                                if len(time_parts) == 2:
                                    hours = int(time_parts[0])
                                    mins = int(time_parts[1])
                                    total_mins = hours * 60 + mins + minutes
                                    new_hours = total_mins // 60
                                    new_mins = total_mins % 60
                                    requested_time = f"{new_hours:02d}:{new_mins:02d}"
                                else:
                                    requested_time = f"+{minutes} min"
                            except:
                                requested_time = f"+{minutes} min"
                        else:
                            requested_time = f"+{minutes} min"
                        
                        order["requested_time"] = requested_time
                        
                        # Send to vendor
                        vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                        if vendor_chat:
                            msg = f"#{order['name'][-2:]} at {requested_time}?"
                            time_buttons = InlineKeyboardMarkup([
                                [InlineKeyboardButton("Works 👍", callback_data=f"works|{order_id}|{vendor}")],
                                [InlineKeyboardButton("Later at", callback_data=f"later_time|{order_id}|{vendor}")],
                                [InlineKeyboardButton("Something is wrong", callback_data=f"wrong|{order_id}|{vendor}")]
                            ])
                            run_async(safe_send_message(vendor_chat, msg, reply_markup=time_buttons))
                            run_async(safe_send_message(DISPATCH_MAIN_CHAT_ID, f"🟨 Requested {requested_time} from {vendor}"))
                    
                    elif action == "same_selected":
                        order_id, reference_order_id = parts[1], parts[2]
                        order = STATE.get(order_id)
                        reference_order = STATE.get(reference_order_id)
                        
                        if not order or not reference_order:
                            return
                        
                        # Get time from reference order
                        reference_time = reference_order.get("confirmed_time") or reference_order.get("requested_time", "ASAP")
                        
                        # Send same time request to vendors per assignment
                        for vendor in order["vendors"]:
                            vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                            if vendor_chat:
                                # Check if same restaurant as reference order
                                if vendor in reference_order.get("vendors", []):
                                    # Same restaurant - special message per assignment
                                    if order["order_type"] == "shopify":
                                        current_display = f"#{order['name'][-2:]}"
                                        ref_display = f"#{reference_order['name'][-2:]}"
                                        msg = f"Can you prepare {current_display} together with {ref_display} at the same time {reference_time}?"
                                    else:
                                        current_addr = order['customer']['address'].split(',')[0]
                                        ref_addr = reference_order['customer']['address'].split(',')[0]
                                        msg = f"Can you prepare *{current_addr}* together with *{ref_addr}* at the same time {reference_time}?"
                                else:
                                    # Different restaurant - standard message
                                    if order["order_type"] == "shopify":
                                        msg = f"#{order['name'][-2:]} at {reference_time}?"
                                    else:
                                        addr = order['customer']['address'].split(',')[0]
                                        msg = f"*{addr}* at {reference_time}?"
                                
                                # Add appropriate buttons
                                time_buttons = InlineKeyboardMarkup([
                                    [InlineKeyboardButton("Works 👍", callback_data=f"works|{order_id}|{vendor}")],
                                    [InlineKeyboardButton("Later at", callback_data=f"later_time|{order_id}|{vendor}")],
                                    [InlineKeyboardButton("Something is wrong", callback_data=f"wrong|{order_id}|{vendor}")]
                                ])
                                run_async(safe_send_message(vendor_chat, msg, reply_markup=time_buttons))
                        
                        run_async(safe_send_message(DISPATCH_MAIN_CHAT_ID, f"🟨 Requested same time as #{reference_order['name'][-2:]} ({reference_time})"))
                    
                    elif action == "req_exact":
                        order_id = parts[1]
                        vendor = parts[2] if len(parts) > 2 and parts[2] else None
                        
                        # Show exact time picker interface
                        hour_buttons = []
                        # Create hour buttons (10:00 - 22:00)
                        for hour in range(10, 23):
                            hour_buttons.append(InlineKeyboardButton(f"{hour}:00", callback_data=f"exact_hour|{order_id}|{vendor or 'all'}|{hour}:00"))
                        
                        # Arrange in rows of 3
                        keyboard = []
                        for i in range(0, len(hour_buttons), 3):
                            keyboard.append(hour_buttons[i:i+3])
                        
                        exact_keyboard = InlineKeyboardMarkup(keyboard)
                        run_async(safe_send_message(DISPATCH_MAIN_CHAT_ID, "Request exact time:", reply_markup=exact_keyboard))
                    
                    elif action == "exact_hour":
                        order_id, vendor_str, time_str = parts[1], parts[2], parts[3]
                        order = STATE.get(order_id)
                        if not order:
                            return
                        
                        order["requested_time"] = time_str
                        
                        # Send to vendor(s)
                        if vendor_str == "all":
                            vendors_to_notify = order["vendors"]
                        else:
                            vendors_to_notify = [vendor_str]
                        
                        for vendor in vendors_to_notify:
                            vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                            if vendor_chat:
                                msg = f"#{order['name'][-2:]} at {time_str}?"
                                time_buttons = InlineKeyboardMarkup([
                                    [InlineKeyboardButton("Works 👍", callback_data=f"works|{order_id}|{vendor}")],
                                    [InlineKeyboardButton("Later at", callback_data=f"later_time|{order_id}|{vendor}")],
                                    [InlineKeyboardButton("Something is wrong", callback_data=f"wrong|{order_id}|{vendor}")]
                                ])
                                run_async(safe_send_message(vendor_chat, msg, reply_markup=time_buttons))
                        
                        run_async(safe_send_message(DISPATCH_MAIN_CHAT_ID, f"🟨 Requested {time_str} from vendors"))
                    
                    elif action == "toggle":
                        # Toggle between collapsed/expanded vendor message
                        order_id, vendor = parts[1], parts[2]
                        order = STATE.get(order_id)
                        if not order:
                            return
                        
                        is_expanded = order.get("vendor_expanded", {}).get(vendor, False)
                        order.setdefault("vendor_expanded", {})[vendor] = not is_expanded
                        
                        vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                        if vendor_chat and order.get("vendor_messages", {}).get(vendor):
                            msg_id = order["vendor_messages"][vendor]
                            
                            if is_expanded:
                                # Show collapsed
                                text = build_vendor_summary_text(order, vendor)
                                button_text = "Details ▸"
                            else:
                                # Show expanded
                                text = build_vendor_details_text(order, vendor)
                                button_text = "◂ Hide"
                            
                            keyboard = InlineKeyboardMarkup([[
                                InlineKeyboardButton(button_text, callback_data=f"toggle|{order_id}|{vendor}")
                            ]])
                            
                            run_async(safe_edit_message(vendor_chat, msg_id, text, reply_markup=keyboard))
                    
                    elif action == "works":
                        order_id, vendor = parts[1], parts[2]
                        order = STATE.get(order_id)
                        if order:
                            order["confirmed_time"] = order.get("requested_time", "ASAP")
                            order["confirmed_by"] = vendor
                            order["status"] = "confirmed"
                            run_async(safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor} replied: Works 👍 — ■"))
                    
                    elif action == "later_time":
                        order_id, vendor = parts[1], parts[2]
                        # Show time picker for "Later at"
                        hour_buttons = []
                        for hour in range(10, 23):
                            hour_buttons.append(InlineKeyboardButton(f"{hour}:00", callback_data=f"later_confirm|{order_id}|{vendor}|{hour}:00"))
                        
                        keyboard = []
                        for i in range(0, len(hour_buttons), 3):
                            keyboard.append(hour_buttons[i:i+3])
                        
                        later_keyboard = InlineKeyboardMarkup(keyboard)
                        
                        # Edit the message with time picker
                        chat_id = callback_query["message"]["chat"]["id"]
                        msg_id = callback_query["message"]["message_id"]
                        run_async(safe_edit_message(chat_id, msg_id, "Select later time:", reply_markup=later_keyboard))
                    
                    elif action == "later_confirm":
                        order_id, vendor, time_str = parts[1], parts[2], parts[3]
                        order = STATE.get(order_id)
                        if order:
                            order["confirmed_time"] = time_str
                            order["confirmed_by"] = vendor
                            order["status"] = "confirmed"
                            run_async(safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor} replied: Later at {time_str} — ■"))
                    
                    elif action == "prepare_time":
                        order_id, vendor = parts[1], parts[2]
                        # Show time picker for "Will prepare at"
                        hour_buttons = []
                        for hour in range(10, 23):
                            hour_buttons.append(InlineKeyboardButton(f"{hour}:00", callback_data=f"prepare_confirm|{order_id}|{vendor}|{hour}:00"))
                        
                        keyboard = []
                        for i in range(0, len(hour_buttons), 3):
                            keyboard.append(hour_buttons[i:i+3])
                        
                        prepare_keyboard = InlineKeyboardMarkup(keyboard)
                        
                        # Edit the message with time picker
                        chat_id = callback_query["message"]["chat"]["id"]
                        msg_id = callback_query["message"]["message_id"]
                        run_async(safe_edit_message(chat_id, msg_id, "Will prepare at:", reply_markup=prepare_keyboard))
                    
                    elif action == "prepare_confirm":
                        order_id, vendor, time_str = parts[1], parts[2], parts[3]
                        order = STATE.get(order_id)
                        if order:
                            order["confirmed_time"] = time_str
                            order["confirmed_by"] = vendor
                            order["status"] = "confirmed"
                            run_async(safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor} replied: Will prepare at {time_str} — ■"))
                    
                    elif action == "wrong":
                        order_id, vendor = parts[1], parts[2]
                        wrong_buttons = InlineKeyboardMarkup([
                            [InlineKeyboardButton("Unavailable product", callback_data=f"wrong_unavailable|{order_id}|{vendor}")],
                            [InlineKeyboardButton("Order is canceled", callback_data=f"wrong_canceled|{order_id}|{vendor}")],
                            [InlineKeyboardButton("Technical issue", callback_data=f"wrong_technical|{order_id}|{vendor}")],
                            [InlineKeyboardButton("We have a delay", callback_data=f"wrong_delay|{order_id}|{vendor}")],
                            [InlineKeyboardButton("Other", callback_data=f"wrong_other|{order_id}|{vendor}")]
                        ])
                        
                        chat_id = callback_query["message"]["chat"]["id"]
                        msg_id = callback_query["message"]["message_id"]
                        run_async(safe_edit_message(chat_id, msg_id, "What's wrong?", reply_markup=wrong_buttons))
                    
                    elif action == "wrong_unavailable":
                        order_id, vendor = parts[1], parts[2]
                        order = STATE.get(order_id)
                        if order and order.get("order_type") == "shopify":
                            msg = f"■ {vendor}: Please call the customer and organize a replacement. If no replacement is possible, write a message to dishbee. ■"
                        else:
                            msg = f"■ {vendor}: Please call the customer and organize a replacement or a refund. ■"
                        run_async(safe_send_message(DISPATCH_MAIN_CHAT_ID, msg))
                    
                    elif action == "wrong_canceled":
                        order_id, vendor = parts[1], parts[2]
                        run_async(safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: Order is canceled ■"))
                    
                    elif action in ["wrong_technical", "wrong_other"]:
                        order_id, vendor = parts[1], parts[2]
                        run_async(safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: Write a message to dishbee and describe the issue ■"))
                    
                    elif action == "wrong_delay":
                        order_id, vendor = parts[1], parts[2]
                        # Show delay time picker
                        delay_buttons = []
                        for minutes in [10, 15, 20, 25, 30, 45, 60]:
                            delay_buttons.append(InlineKeyboardButton(f"{minutes} min", callback_data=f"delay_confirm|{order_id}|{vendor}|{minutes}"))
                        
                        keyboard = []
                        for i in range(0, len(delay_buttons), 3):
                            keyboard.append(delay_buttons[i:i+3])
                        
                        delay_keyboard = InlineKeyboardMarkup(keyboard)
                        
                        chat_id = callback_query["message"]["chat"]["id"]
                        msg_id = callback_query["message"]["message_id"]
                        run_async(safe_edit_message(chat_id, msg_id, "How much delay?", reply_markup=delay_keyboard))
                    
                    elif action == "delay_confirm":
                        order_id, vendor, minutes = parts[1], parts[2], parts[3]
                        run_async(safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: We have a {minutes} min delay ■"))
                        
                except Exception as e:
                    logger.error(f"Callback processing error: {e}")
            
            # Run callback processing in thread
            threading.Thread(target=process_callback, daemon=True).start()
            
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
        customer = payload.get("customer") or {}
        customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or "Unknown"
        phone = customer.get("phone") or payload.get("phone") or "N/A"
        address = fmt_address(payload.get("shipping_address") or {})
        
        # Extract vendors from product tags
        line_items = payload.get("line_items", [])
        vendors = []
        vendor_items = {}
        items_text = ""
        
        for item in line_items:
            # Get tags from the product
            product_tags = item.get('tags', '').split(',')
            vendor_tag = None
            
            vendor = None  # FIX: Initialize vendor to prevent error
            # Find restaurant tag in product tags
            for tag in product_tags:
                tag = tag.strip().upper()
                if tag in TAG_TO_RESTAURANT:
                    vendor_tag = tag
                    vendor = TAG_TO_RESTAURANT[tag]
                    break
            
            # If vendor found and in our mapping
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
        
        # Check for pickup orders - detect "Abholung" in payload
        is_pickup = False
        payload_str = str(payload).lower()
        if "abholung" in payload_str:
            is_pickup = True
            logger.info("Pickup order detected (Abholung found in payload)")
        
        # Build order object
        order = {
            "name": order_name,
            "order_type": "shopify",
            "vendors": vendors,
            "customer": {
                "name": customer_name,
                "phone": phone,
                "address": address
            },
            "items_text": items_text,
            "vendor_items": vendor_items,
            "note": payload.get("note"),
            "tips": "",  # TODO: Extract from payload
            "payment_method": "Paid",  # TODO: Extract actual payment method
            "delivery_time": None,
            "is_pickup": is_pickup,
            "created_at": datetime.now(),
            "vendor_messages": {},
            "vendor_expanded": {},
            "requested_time": None,
            "confirmed_time": None,
            "confirmed_by": None,
            "status": "new",
            "mdg_message_id": None,
            "delivered": False  # For future delivery tracking
        }
        
        # Store order
        STATE[order_id] = order
        RECENT_ORDERS.append(order)
        if len(RECENT_ORDERS) > 50:
            RECENT_ORDERS.pop(0)
        
        # Send messages
        def send_messages():
            # Send to MDG
            mdg_text = build_mdg_dispatch_text(order)
            mdg_keyboard = mdg_time_request_keyboard(order_id)
            mdg_msg = run_async(safe_send_message(DISPATCH_MAIN_CHAT_ID, mdg_text, reply_markup=mdg_keyboard))
            if mdg_msg:
                order["mdg_message_id"] = mdg_msg.message_id
            
            # Send to vendor groups
            for vendor in vendors:
                vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                if vendor_chat:
                    vendor_text = build_vendor_summary_text(order, vendor)
                    vendor_keyboard = InlineKeyboardMarkup([[
                        InlineKeyboardButton("Details ▸", callback_data=f"toggle|{order_id}|{vendor}")
                    ]])
                    vendor_msg = run_async(safe_send_message(vendor_chat, vendor_text, reply_markup=vendor_keyboard))
                    if vendor_msg:
                        order["vendor_messages"][vendor] = vendor_msg.message_id
        
        # Send messages in background thread
        threading.Thread(target=send_messages, daemon=True).start()
        
        logger.info(f"Order {order_id} processed successfully")
        return jsonify({"success": True}), 200
        
    except Exception as e:
        logger.error(f"Shopify webhook error: {e}")
        return jsonify({"error": str(e)}), 500

# --- MAIN ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Starting Telegram Dispatch Bot on port {port}")
    app.run(host="0.0.0.0", port=port)

# Telegram Dispatch Bot — Full Assignment Implementation (Webhook-only, PTB v20)
# ENHANCED VERSION - Phase 1: Core MDG Workflow Implementation

import os
import json
import hmac
import hashlib
import base64
import asyncio
import logging
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
# Enhanced state to support new features
STATE: Dict[str, Dict[str, Any]] = {}
# Added fields:
# - "order_type": "shopify"|"hubrise"|"smoothr"
# - "requested_time": str|None (time requested from restaurant)
# - "confirmed_time": str|None (time confirmed by restaurant)
# - "grouped_with": List[str] (other order IDs in same group)
# - "created_at": datetime

# Store recent orders for "same time as" functionality
RECENT_ORDERS: List[Dict[str, Any]] = []

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

def get_time_intervals(base_time: datetime, count: int = 4) -> List[str]:
    """Generate time intervals for buttons"""
    intervals = []
    for i in range(count):
        time_option = base_time + timedelta(minutes=(i + 1) * 10)
        intervals.append(time_option.strftime("%H:%M"))
    return intervals

def get_recent_orders_for_same_time(current_order_id: str) -> List[Dict[str, str]]:
    """Get recent orders (last 1 hour) for 'same time as' functionality"""
    one_hour_ago = datetime.now() - timedelta(hours=1)
    recent = []
    
    for order_id, order_data in STATE.items():
        if order_id == current_order_id:
            continue
        if order_data.get("created_at") and order_data["created_at"] > one_hour_ago:
            if order_data.get("order_type") == "shopify":
                display_name = f"#{order_data['name'][-2:]}"  # Last 2 digits
            else:
                # For HubRise/Smoothr - use street + building number
                address_parts = order_data['customer']['address'].split(',')
                street_info = address_parts[0] if address_parts else "Unknown"
                display_name = f"*{street_info}*"
            
            recent.append({
                "order_id": order_id,
                "display_name": display_name,
                "vendor": order_data.get("vendors", ["Unknown"])[0]
            })
    
    return recent[-10:]  # Return last 10 orders

def build_dispatch_text(order: Dict[str, Any]) -> str:
    """Build dispatch message text for MDG"""
    try:
        note = order.get("note", "")
        status_emoji = order.get("status", "🟥")
        assigned = order.get("assigned_to")
        requested_time = order.get("requested_time")
        confirmed_time = order.get("confirmed_time")
        
        # Enhanced status line
        status_line = f"Status: {status_emoji}"
        if status_emoji == "🟨" and assigned:
            status_line += f" — Assigned to {assigned}"
        
        # Add time information
        if requested_time:
            status_line += f"\n⏰ Requested: {requested_time}"
        if confirmed_time:
            status_line += f"\n✅ Confirmed: {confirmed_time}"
        
        # Order type prefix
        order_type = order.get("order_type", "shopify")
        if order_type == "shopify":
            title_prefix = f"🟥 *NEW ORDER* (dishbee + {', '.join(order.get('vendors', []))})"
            order_number = f"Order #{order['name'][-2:]}" if len(order['name']) >= 2 else order['name']
        else:
            title_prefix = f"🟥 *NEW ORDER* ({', '.join(order.get('vendors', []))})"
            order_number = ""
        
        text = f"{title_prefix}\n"
        if order_number:
            text += f"📋 {order_number}\n"
        
        text += (
            f"👤 *Customer:* {order['customer']['name']}\n"
            f"📍 *Address:* {order['customer']['address']}\n"
            f"📞 *Phone:* {order['customer']['phone']}\n"
            f"🕒 *Time:* {order['delivery_time']}\n"
            f"🛒 *Items:*\n{order['items_text']}"
        )
        
        if note:
            text += f"\n📝 *Note:* {note}"
        
        # Add grouping information
        grouped_with = order.get("grouped_with", [])
        if grouped_with:
            group_names = []
            for group_order_id in grouped_with:
                if group_order_id in STATE:
                    group_order = STATE[group_order_id]
                    if group_order.get("order_type") == "shopify":
                        group_names.append(f"#{group_order['name'][-2:]}")
                    else:
                        address_parts = group_order['customer']['address'].split(',')
                        street_info = address_parts[0] if address_parts else "Unknown"
                        group_names.append(f"*{street_info}*")
            if group_names:
                text += f"\n🔗 *Grouped with:* {', '.join(group_names)}"
        
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
        
        # Order number for Shopify
        order_type = order.get("order_type", "shopify")
        if order_type == "shopify":
            order_number = f"Order #{order['name'][-2:]}" if len(order['name']) >= 2 else order['name']
            title = f"🟥 *NEW ORDER* (dishbee + {vendor})"
        else:
            order_number = ""
            title = f"🟥 *NEW ORDER* ({vendor})"
        
        if expanded:
            customer_block = (
                f"👤 *Customer:* {order['customer']['name']}\n"
                f"📍 *Address:* {order['customer']['address']}\n"
                f"📞 *Phone:* {order['customer']['phone']}\n"
                f"🕒 *Order placed:* {order.get('created_at', datetime.now()).strftime('%H:%M')}\n"
            )
        else:
            customer_block = ""
        
        text = f"{title}\n"
        if order_number:
            text += f"📋 {order_number}\n"
        
        text += (
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

def mdg_time_request_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build MDG time request keyboard - NEW FEATURE"""
    try:
        current_time = datetime.now()
        time_intervals = get_time_intervals(current_time)
        
        rows: List[List[InlineKeyboardButton]] = []
        
        # Time request row 1
        rows.append([
            InlineKeyboardButton("Request ASAP", callback_data=f"request_asap|{order_id}"),
            InlineKeyboardButton("Request TIME", callback_data=f"request_time|{order_id}")
        ])
        
        # Time request row 2  
        rows.append([
            InlineKeyboardButton("Request EXACT TIME", callback_data=f"request_exact|{order_id}"),
            InlineKeyboardButton("Request SAME TIME AS", callback_data=f"request_same|{order_id}")
        ])
        
        return InlineKeyboardMarkup(rows)
    except Exception as e:
        logger.error(f"Error building MDG time request keyboard: {e}")
        return InlineKeyboardMarkup([])

def mdg_assignment_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build MDG assignment keyboard"""
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
        logger.error(f"Error building MDG assignment keyboard: {e}")
        return InlineKeyboardMarkup([])

def vendor_keyboard(order_id: str, vendor: str, expanded: bool) -> InlineKeyboardMarkup:
    """Build vendor inline keyboard"""
    try:
        toggle = "◂ Hide" if expanded else "Details ▸"
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle, callback_data=f"expand|{order_id}|{vendor}")],
            [InlineKeyboardButton("Works 👍", callback_data=f"reply|{order_id}|{vendor}|Works"),
             InlineKeyboardButton("Later at", callback_data=f"reply|{order_id}|{vendor}|Later"),
             InlineKeyboardButton("Will prepare at", callback_data=f"reply|{order_id}|{vendor}|Will prepare")]
        ])
    except Exception as e:
        logger.error(f"Error building vendor keyboard: {e}")
        return InlineKeyboardMarkup([])

def time_picker_keyboard(order_id: str, base_time: datetime, action: str) -> InlineKeyboardMarkup:
    """Build time picker keyboard"""
    try:
        intervals = get_time_intervals(base_time)
        rows = []
        
        # Time options in pairs
        for i in range(0, len(intervals), 2):
            row = [InlineKeyboardButton(intervals[i], callback_data=f"{action}_time|{order_id}|{intervals[i]}")]
            if i + 1 < len(intervals):
                row.append(InlineKeyboardButton(intervals[i + 1], callback_data=f"{action}_time|{order_id}|{intervals[i + 1]}"))
            rows.append(row)
        
        # Custom time option
        rows.append([InlineKeyboardButton("Custom Time ⏰", callback_data=f"{action}_custom|{order_id}")])
        
        return InlineKeyboardMarkup(rows)
    except Exception as e:
        logger.error(f"Error building time picker keyboard: {e}")
        return InlineKeyboardMarkup([])

def same_time_as_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build 'same time as' selection keyboard"""
    try:
        recent_orders = get_recent_orders_for_same_time(order_id)
        rows = []
        
        for order_info in recent_orders:
            button_text = f"{order_info['display_name']} ({order_info['vendor']})"
            callback_data = f"same_time|{order_id}|{order_info['order_id']}"
            rows.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        if not recent_orders:
            rows.append([InlineKeyboardButton("No recent orders found", callback_data="no_recent")])
        
        return InlineKeyboardMarkup(rows)
    except Exception as e:
        logger.error(f"Error building same time keyboard: {e}")
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
        "orders_in_state": len(STATE),
        "recent_orders": len(RECENT_ORDERS)
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
            logger.info(f"Processing callback: {kind} with data: {data}")
            
            try:
                # EXISTING CALLBACKS
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
                        reply_markup=mdg_assignment_keyboard(order_id)
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
                        reply_markup=mdg_assignment_keyboard(order_id)
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
                        reply_markup=mdg_assignment_keyboard(order_id)
                    )
                
                # NEW TIME REQUEST CALLBACKS
                elif kind == "request_asap":
                    _, order_id = data
                    order = STATE.get(order_id)
                    if not order:
                        logger.warning(f"Order {order_id} not found for request_asap")
                        return
                    
                    logger.info(f"Processing ASAP request for order {order_id}")
                    
                    # Send ASAP request to vendor
                    for vendor in order.get("vendors", []):
                        vendor_chat_id = VENDOR_GROUP_MAP.get(vendor)
                        logger.info(f"Trying to send ASAP to vendor {vendor}, chat_id: {vendor_chat_id}")
                        
                        if vendor_chat_id:
                            if order.get("order_type") == "shopify":
                                request_msg = f"#{order['name'][-2:]} ASAP?"
                            else:
                                address_parts = order['customer']['address'].split(',')
                                street_info = address_parts[0] if address_parts else "Unknown"
                                request_msg = f"*{street_info}* ASAP?"
                            
                            logger.info(f"Sending ASAP message: {request_msg}")
                            try:
                                await safe_send_message(vendor_chat_id, request_msg)
                                logger.info(f"ASAP request sent successfully to {vendor}")
                            except Exception as e:
                                logger.error(f"Failed to send ASAP to {vendor}: {e}")
                        else:
                            logger.warning(f"No chat ID found for vendor: {vendor}")
                    
                    order["requested_time"] = "ASAP"
                    # Update MDG with assignment keyboard
                    await safe_edit_message(
                        chat_id=DISPATCH_MAIN_CHAT_ID,
                        message_id=order["dispatch_msg_id"],
                        text=build_dispatch_text(order),
                        reply_markup=mdg_assignment_keyboard(order_id)
                    )
                
                elif kind == "request_time":
                    _, order_id = data
                    # Show time picker
                    current_time = datetime.now()
                    time_keyboard = time_picker_keyboard(order_id, current_time, "select")
                    await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID, 
                        "🕒 *Select time to request:*", 
                        reply_markup=time_keyboard
                    )
                
                elif kind == "select_time":
                    _, order_id, selected_time = data
                    order = STATE.get(order_id)
                    if not order:
                        return
                    
                    # Send time request to vendor
                    for vendor in order.get("vendors", []):
                        vendor_chat_id = VENDOR_GROUP_MAP.get(vendor)
                        if vendor_chat_id:
                            if order.get("order_type") == "shopify":
                                request_msg = f"#{order['name'][-2:]} at {selected_time}?"
                            else:
                                address_parts = order['customer']['address'].split(',')
                                street_info = address_parts[0] if address_parts else "Unknown"
                                request_msg = f"*{street_info}* at {selected_time}?"
                            
                            await safe_send_message(vendor_chat_id, request_msg)
                    
                    order["requested_time"] = selected_time
                    # Update MDG with assignment keyboard
                    await safe_edit_message(
                        chat_id=DISPATCH_MAIN_CHAT_ID,
                        message_id=order["dispatch_msg_id"],
                        text=build_dispatch_text(order),
                        reply_markup=mdg_assignment_keyboard(order_id)
                    )
                
                elif kind == "request_same":
                    _, order_id = data
                    # Show recent orders for selection
                    same_time_keyboard = same_time_as_keyboard(order_id)
                    await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        "🔗 *Select order to match timing with:*",
                        reply_markup=same_time_keyboard
                    )
                
                elif kind == "same_time":
                    _, order_id, reference_order_id = data
                    order = STATE.get(order_id)
                    reference_order = STATE.get(reference_order_id)
                    
                    if not order or not reference_order:
                        return
                    
                    # Group orders together
                    if "grouped_with" not in order:
                        order["grouped_with"] = []
                    if "grouped_with" not in reference_order:
                        reference_order["grouped_with"] = []
                    
                    order["grouped_with"].append(reference_order_id)
                    reference_order["grouped_with"].append(order_id)
                    
                    # Use the confirmed time from reference order, or requested time
                    reference_time = reference_order.get("confirmed_time") or reference_order.get("requested_time")
                    
                    if reference_time:
                        # Send grouped request to vendor
                        for vendor in order.get("vendors", []):
                            vendor_chat_id = VENDOR_GROUP_MAP.get(vendor)
                            if vendor_chat_id:
                                # Check if same restaurant
                                if vendor in reference_order.get("vendors", []):
                                    if order.get("order_type") == "shopify":
                                        current_display = f"#{order['name'][-2:]}"
                                        ref_display = f"#{reference_order['name'][-2:]}"
                                    else:
                                        current_addr = order['customer']['address'].split(',')[0]
                                        ref_addr = reference_order['customer']['address'].split(',')[0]
                                        current_display = f"*{current_addr}*"
                                        ref_display = f"*{ref_addr}*"
                                    
                                    request_msg = f"Can you prepare {current_display} together with {ref_display} at the same time {reference_time}?"
                                else:
                                    # Different restaurant - standard request
                                    if order.get("order_type") == "shopify":
                                        request_msg = f"#{order['name'][-2:]} at {reference_time}?"
                                    else:
                                        address_parts = order['customer']['address'].split(',')
                                        street_info = address_parts[0] if address_parts else "Unknown"
                                        request_msg = f"*{street_info}* at {reference_time}?"
                                
                                await safe_send_message(vendor_chat_id, request_msg)
                        
                        order["requested_time"] = reference_time
                    
                    # Update both MDG messages
                    for upd_order_id in [order_id, reference_order_id]:
                        upd_order = STATE[upd_order_id]
                        await safe_edit_message(
                            chat_id=DISPATCH_MAIN_CHAT_ID,
                            message_id=upd_order["dispatch_msg_id"],
                            text=build_dispatch_text(upd_order),
                            reply_markup=mdg_assignment_keyboard(upd_order_id)
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
        logger.info(f"Raw tags from Shopify: '{tags}'")
        
        vendors = [v.strip() for v in tags.split(",") if v.strip()] if tags else []
        logger.info(f"Parsed vendors: {vendors}")
        logger.info(f"Available vendor mappings: {list(VENDOR_GROUP_MAP.keys())}")
        
        # Check if vendors match our mapping
        for vendor in vendors:
            if vendor in VENDOR_GROUP_MAP:
                logger.info(f"✅ Vendor '{vendor}' found in mapping")
            else:
                logger.warning(f"❌ Vendor '{vendor}' NOT found in mapping")
                logger.warning(f"Available: {list(VENDOR_GROUP_MAP.keys())}")

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
            "order_type": "shopify",  # NEW: Track order source
            "requested_time": None,   # NEW: Track requested time
            "confirmed_time": None,   # NEW: Track confirmed time
            "grouped_with": [],       # NEW: Track grouped orders
            "created_at": datetime.now()  # NEW: Track creation time
        }

        async def process():
            try:
                # Send MDG message with TIME REQUEST controls (NEW WORKFLOW)
                mdg_text = build_dispatch_text(order)
                mdg_msg = await safe_send_message(
                    DISPATCH_MAIN_CHAT_ID, 
                    mdg_text, 
                    reply_markup=mdg_time_request_keyboard(order_id)  # Start with time request
                )
                order["dispatch_msg_id"] = mdg_msg.message_id

                # Send vendor messages (ENHANCED with better logging)
                for vendor in vendors:
                    group_id = VENDOR_GROUP_MAP.get(vendor)
                    logger.info(f"Processing vendor: {vendor}, group_id: {group_id}")
                    logger.info(f"Available vendor mappings: {VENDOR_GROUP_MAP}")
                    
                    if not group_id:
                        logger.warning(f"No group ID found for vendor: {vendor}")
                        logger.warning(f"Available vendors: {list(VENDOR_GROUP_MAP.keys())}")
                        continue
                    
                    v_text = build_vendor_text(order, vendor, expanded=False)
                    keyboard = vendor_keyboard(order_id, vendor, expanded=False)
                    
                    try:
                        v_msg = await safe_send_message(group_id, v_text, reply_markup=keyboard)
                        order["vendor_msgs"][vendor] = v_msg.message_id
                        order["vendor_expanded"][vendor] = False
                        logger.info(f"Vendor message sent successfully to {vendor}")
                    except Exception as e:
                        logger.error(f"Failed to send vendor message to {vendor}: {e}")

                # Save to state and recent orders
                STATE[order_id] = order
                RECENT_ORDERS.append({
                    "order_id": order_id,
                    "created_at": datetime.now(),
                    "vendors": vendors
                })
                
                # Keep only recent orders (last 50)
                if len(RECENT_ORDERS) > 50:
                    RECENT_ORDERS.pop(0)
                
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
    logger.info(f"Starting Enhanced Telegram Dispatch Bot on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)

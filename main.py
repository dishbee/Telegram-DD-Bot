# Telegram Dispatch Bot — Complete Assignment Implementation
# All features from requirements document implemented

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
DISPATCH_MAIN_CHAT_ID = int(os.environ["DISPATCH_MAIN_CHAT_ID"])
VENDOR_GROUP_MAP: Dict[str, int] = json.loads(os.environ.get("VENDOR_GROUP_MAP", "{}"))
DRIVERS: Dict[str, int] = json.loads(os.environ.get("DRIVERS", "{}"))

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
        return "No address provided"
    
    try:
        parts = []
        if addr.get("address1"):
            parts.append(addr["address1"])
        if addr.get("zip"):
            parts.append(addr["zip"])
        return ", ".join(parts) if parts else "Address incomplete"
    except Exception as e:
        logger.error(f"Address formatting error: {e}")
        return "Address formatting error"

def get_time_intervals(base_time: datetime, count: int = 4) -> List[str]:
    """Generate 10-minute intervals for time picker"""
    intervals = []
    for i in range(count):
        time_option = base_time + timedelta(minutes=(i + 1) * 10)
        intervals.append(time_option.strftime("%H:%M"))
    return intervals

def get_last_confirmed_order_today() -> Dict[str, Any]:
    """Get the most recent order from today where any restaurant confirmed a time"""
    try:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        confirmed_orders = []
        
        for order_id, order_data in STATE.items():
            # Check if order is from today
            if order_data.get("created_at") and order_data["created_at"] >= today:
                # Check if order has confirmed time
                confirmed_time = order_data.get("confirmed_time")
                if confirmed_time:
                    confirmed_orders.append({
                        "order_id": order_id,
                        "order_number": order_data.get("name", "")[-2:] if order_data.get("name") else "??",
                        "confirmed_time": confirmed_time,
                        "created_at": order_data["created_at"]
                    })
        
        # Return the most recent one
        if confirmed_orders:
            return max(confirmed_orders, key=lambda x: x["created_at"])
        
        return None
    except Exception as e:
        logger.error(f"Error getting last confirmed order: {e}")
        return None

def build_smart_time_suggestions(order_id: str, target_vendor: str = None) -> List[InlineKeyboardButton]:
    """Build smart time suggestion buttons based on last confirmed order"""
    try:
        timestamp = int(datetime.now().timestamp())
        last_order = get_last_confirmed_order_today()
        
        if not last_order:
            # No confirmed orders today - show message
            return [InlineKeyboardButton("There is no last order with the confirmed time", callback_data=f"no_confirmed|{order_id}|{timestamp}")]
        
        # Parse confirmed time
        confirmed_time = last_order["confirmed_time"]
        order_number = last_order["order_number"]
        
        try:
            # Parse time (format: "HH:MM")
            hour, minute = map(int, confirmed_time.split(':'))
            base_time = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # Create 4 buttons: +5, +10, +15, +20 minutes
            suggestions = []
            for offset in [5, 10, 15, 20]:
                new_time = base_time + timedelta(minutes=offset)
                time_str = new_time.strftime("%H:%M")
                button_text = f"#{order_number} {confirmed_time} + {offset}min"
                
                # Different callback data for single vs multi-vendor
                if target_vendor:
                    # Multi-vendor: include vendor in callback
                    callback_data = f"smart_time|{order_id}|{target_vendor}|{time_str}|{timestamp}"
                else:
                    # Single vendor: old format
                    callback_data = f"smart_time|{order_id}|{time_str}|{timestamp}"
                
                suggestions.append(InlineKeyboardButton(button_text, callback_data=callback_data))
            
            return suggestions
        except:
            # If time parsing fails, show fallback
            return [InlineKeyboardButton("Error parsing last confirmed time", callback_data=f"no_confirmed|{order_id}|{timestamp}")]
    
    except Exception as e:
        logger.error(f"Error building smart suggestions: {e}")
        return [InlineKeyboardButton("Error loading suggestions", callback_data=f"no_confirmed|{order_id}|{timestamp}")]
    """Get recent orders (last 1 hour) for 'same time as' functionality"""
    one_hour_ago = datetime.now() - timedelta(hours=1)
    recent = []
    
    for order_id, order_data in STATE.items():
        if order_id == current_order_id:
            continue
        if order_data.get("created_at") and order_data["created_at"] > one_hour_ago:
            if order_data.get("order_type") == "shopify":
                display_name = f"#{order_data['name'][-2:]}"
            else:
                address_parts = order_data['customer']['address'].split(',')
                street_info = address_parts[0] if address_parts else "Unknown"
                display_name = f"*{street_info}*"
            
            recent.append({
                "order_id": order_id,
                "display_name": display_name,
                "vendor": order_data.get("vendors", ["Unknown"])[0]
            })
    
    return recent[-10:]

def build_mdg_dispatch_text(order: Dict[str, Any]) -> str:
    """Build MDG dispatch message per assignment requirements"""
    try:
        order_type = order.get("order_type", "shopify")
        vendors = order.get("vendors", [])
        
        # Title: "dishbee + Name of restaurant(s)" for Shopify
        if order_type == "shopify":
            if len(vendors) > 1:
                title = f"dishbee + {', '.join(vendors)}"
            else:
                title = f"dishbee + {vendors[0] if vendors else 'Unknown'}"
        else:
            # For HubRise/Smoothr: only restaurant name
            title = vendors[0] if vendors else "Unknown"
        
        # Order number with last two digits (only for Shopify)
        order_number_line = ""
        if order_type == "shopify":
            order_name = order.get('name', '')
            if len(order_name) >= 2:
                order_number_line = f"#{order_name[-2:]}\n"
        
        # Address - only street, building number and zip code (no city!) in BOLD
        full_address = order['customer']['address']
        # Remove city from address - split by comma and take first parts (street + zip)
        address_parts = full_address.split(',')
        if len(address_parts) >= 2:
            # Take street + zip, skip city
            clean_address = f"{address_parts[0].strip()}, {address_parts[-1].strip()}"
        else:
            clean_address = address_parts[0].strip()
        
        # Delivery time (only for Smoothr/HubRise)
        delivery_time_line = ""
        if order_type in ["smoothr", "hubrise"]:
            delivery_time = order.get('delivery_time', 'ASAP')
            if delivery_time != "ASAP":
                delivery_time_line = f"Requested delivery time: {delivery_time}\n"
        
        # Note (if added)
        note_line = ""
        note = order.get("note", "")
        if note:
            note_line = f"Note: {note}\n"
        
        # Tips (if added)
        tips_line = ""
        tips = order.get("tips", "")
        if tips:
            tips_line = f"Tips: {tips}\n"
        
        # Payment method - Paid/Cash (only for Shopify)
        payment_line = ""
        if order_type == "shopify":
            payment = order.get("payment_method", "Paid")
            payment_line = f"Payment: {payment}\n"
        
        # Products with vendor names above (for multi-vendor)
        if order_type == "shopify" and len(vendors) > 1:
            # Multi-vendor: show vendor name above each vendor's products
            vendor_items = order.get("vendor_items", {})
            items_text = ""
            for vendor in vendors:
                items_text += f"\n{vendor}:\n"
                vendor_products = vendor_items.get(vendor, [])
                for item in vendor_products:
                    items_text += f"{item}\n"
        else:
            # Single vendor: just list items
            items_text = order.get("items_text", "")
        
        # Customer name
        customer_name = order['customer']['name']
        
        # Build final message
        text = f"{title}\n"
        text += order_number_line
        text += f"**{clean_address}**\n"  # Bold font for address
        text += delivery_time_line
        text += note_line
        text += tips_line
        text += payment_line
        text += f"{items_text}\n"
        text += f"{customer_name}"
        
        return text
    except Exception as e:
        logger.error(f"Error building MDG text: {e}")
        return f"Error formatting order {order.get('name', 'Unknown')}"

def build_vendor_summary_text(order: Dict[str, Any], vendor: str) -> str:
    """Build vendor short summary (default collapsed state) - FIXED per assignment"""
    try:
        order_type = order.get("order_type", "shopify")
        
        # Order number for summary
        if order_type == "shopify":
            order_number = order['name'][-2:] if len(order['name']) >= 2 else order['name']
        else:
            # For HubRise/Smoothr, use street name + building number
            address_parts = order['customer']['address'].split(',')
            order_number = address_parts[0] if address_parts else "Unknown"
        
        # ONLY ordered products for this vendor (no customer info in summary!)
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
    """Build MDG time request buttons per assignment"""
    try:
        timestamp = int(datetime.now().timestamp())
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Request ASAP", callback_data=f"req_asap|{order_id}|{timestamp}"),
                InlineKeyboardButton("Request TIME", callback_data=f"req_time|{order_id}|{timestamp}")
            ],
            [
                InlineKeyboardButton("Request SAME TIME AS", callback_data=f"req_same|{order_id}|{timestamp}")
            ]
        ])
    except Exception as e:
        logger.error(f"Error building time request keyboard: {e}")
        return InlineKeyboardMarkup([])

def mdg_assignment_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build MDG assignment buttons (shown after time confirmation)"""
    try:
        timestamp = int(datetime.now().timestamp())
        rows = []
        
        # Assignment buttons for each driver
        if DRIVERS:
            driver_buttons = []
            for name, uid in DRIVERS.items():
                driver_buttons.append(
                    InlineKeyboardButton(f"Assign to {name}", callback_data=f"assign|{order_id}|{name}|{uid}|{timestamp}")
                )
            # Split into rows of 2-3 buttons
            for i in range(0, len(driver_buttons), 2):
                rows.append(driver_buttons[i:i+2])
        
        # Status buttons
        rows.append([
            InlineKeyboardButton("Delivered ✅", callback_data=f"delivered|{order_id}|{timestamp}"),
            InlineKeyboardButton("Delay 🕧", callback_data=f"delayed|{order_id}|{timestamp}")
        ])
        
        return InlineKeyboardMarkup(rows)
    except Exception as e:
        logger.error(f"Error building assignment keyboard: {e}")
        return InlineKeyboardMarkup([])

def exact_time_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build exact time picker with 3-minute intervals in grid format"""
    try:
        timestamp = int(datetime.now().timestamp())
        current_time = datetime.now()
        current_hour = current_time.hour
        
        # Show hours from current hour to end of day (23:00)
        hour_buttons = []
        for hour in range(current_hour, 24):
            hour_buttons.append(InlineKeyboardButton(f"{hour:02d}:XX", callback_data=f"exact_hour|{order_id}|{hour}|{timestamp}"))
        
        # Split hours into rows of 4
        rows = []
        for i in range(0, len(hour_buttons), 4):
            rows.append(hour_buttons[i:i+4])
        
        rows.append([InlineKeyboardButton("← Back", callback_data=f"exact_hide|{order_id}|{timestamp}")])
        
        return InlineKeyboardMarkup(rows)
    except Exception as e:
        logger.error(f"Error building exact time keyboard: {e}")
        return InlineKeyboardMarkup([])

def exact_hour_keyboard(order_id: str, hour: int) -> InlineKeyboardMarkup:
    """Build minute picker for selected hour - 3-minute intervals in grid format"""
    try:
        timestamp = int(datetime.now().timestamp())
        current_time = datetime.now()
        
        # Generate 3-minute intervals: 00, 03, 06, 09, 12, 15, 18, 21, 24, 27, 30, 33, 36, 39, 42, 45, 48, 51, 54, 57
        minutes = []
        for minute in range(0, 60, 3):
            # Skip past times if it's the current hour
            if hour == current_time.hour and minute <= current_time.minute:
                continue
            minutes.append(f"{hour:02d}:{minute:02d}")
        
        # Create grid with 4 times per row
        rows = []
        for i in range(0, len(minutes), 4):
            row = []
            for j in range(4):
                if i + j < len(minutes):
                    time_str = minutes[i + j]
                    row.append(InlineKeyboardButton(time_str, callback_data=f"exact_selected|{order_id}|{time_str}|{timestamp}"))
            rows.append(row)
        
        rows.append([InlineKeyboardButton("← Back to hours", callback_data=f"exact_back_hours|{order_id}|{timestamp}")])
        
        return InlineKeyboardMarkup(rows)
    except Exception as e:
        logger.error(f"Error building exact hour keyboard: {e}")
        return InlineKeyboardMarkup([])

def time_picker_keyboard(order_id: str, action: str, requested_time: str = None) -> InlineKeyboardMarkup:
    """Build time picker for various actions"""
    try:
        timestamp = int(datetime.now().timestamp())
        current_time = datetime.now()
        if requested_time:
            # For vendor responses, base on requested time
            try:
                req_hour, req_min = map(int, requested_time.split(':'))
                base_time = datetime.now().replace(hour=req_hour, minute=req_min)
            except:
                base_time = current_time
        else:
            base_time = current_time
        
        intervals = get_time_intervals(base_time)
        
        rows = []
        for i in range(0, len(intervals), 2):
            row = [InlineKeyboardButton(intervals[i], callback_data=f"{action}|{order_id}|{intervals[i]}|{timestamp}")]
            if i + 1 < len(intervals):
                row.append(InlineKeyboardButton(intervals[i + 1], callback_data=f"{action}|{order_id}|{intervals[i + 1]}|{timestamp}"))
            rows.append(row)
        
        # Add custom time option
        rows.append([InlineKeyboardButton("Custom Time ⏰", callback_data=f"{action}_custom|{order_id}|{timestamp}")])
        
        return InlineKeyboardMarkup(rows)
    except Exception as e:
        logger.error(f"Error building time picker: {e}")
        return InlineKeyboardMarkup([])

def same_time_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build same time as selection keyboard"""
    try:
        timestamp = int(datetime.now().timestamp())
        recent = get_recent_orders_for_same_time(order_id)
        rows = []
        
        for order_info in recent:
            text = f"{order_info['display_name']} ({order_info['vendor']})"
            callback = f"same_as|{order_id}|{order_info['order_id']}|{timestamp}"
            rows.append([InlineKeyboardButton(text, callback_data=callback)])
        
        if not recent:
            rows.append([InlineKeyboardButton("No recent orders", callback_data=f"no_recent|{timestamp}")])
        
        return InlineKeyboardMarkup(rows)
    except Exception as e:
        logger.error(f"Error building same time keyboard: {e}")
        return InlineKeyboardMarkup([])

async def safe_send_message(chat_id: int, text: str, reply_markup=None, parse_mode=ParseMode.MARKDOWN):
    """Send message with error handling"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return await bot.send_message(
                chat_id=chat_id, 
                text=text, 
                reply_markup=reply_markup, 
                parse_mode=parse_mode
            )
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            else:
                logger.error(f"Failed to send message: {e}")
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
    except Exception as e:
        logger.error(f"Error editing message: {e}")

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
    """Handle Telegram webhooks"""
    try:
        upd = request.get_json(force=True)
        if not upd:
            return "OK"
        
        cq = upd.get("callback_query")
        if not cq:
            return "OK"

        async def handle():
            try:
                await bot.answer_callback_query(cq["id"])
            except Exception as e:
                logger.error(f"answer_callback_query error: {e}")
            
            data = (cq.get("data") or "").split("|")
            logger.info(f"Raw callback data: {cq.get('data')}")
            logger.info(f"Parsed callback data: {data}")
            
            if not data:
                logger.warning("No callback data found")
                return
            
            action = data[0]
            logger.info(f"Processing callback: {action}")
            
            try:
                # TIME REQUEST ACTIONS (MDG)
                if action == "req_asap":
                    order_id = data[1]
                    order = STATE.get(order_id)
                    if not order:
                        logger.warning(f"Order {order_id} not found in state")
                        return
                    
                    logger.info(f"Processing ASAP request for order {order_id}")
                    
                    # Send ASAP request to vendors WITH BUTTONS
                    for vendor in order["vendors"]:
                        vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                        if vendor_chat:
                            if order["order_type"] == "shopify":
                                msg = f"#{order['name'][-2:]} ASAP?"
                            else:
                                addr = order['customer']['address'].split(',')[0]
                                msg = f"*{addr}* ASAP?"
                            
                            # ASAP request buttons: "Will prepare at" + "Something is wrong"
                            timestamp = int(datetime.now().timestamp())
                            asap_buttons = InlineKeyboardMarkup([
                                [InlineKeyboardButton("Will prepare at", callback_data=f"prepare|{order_id}|{vendor}|{timestamp}")],
                                [InlineKeyboardButton("Something is wrong", callback_data=f"wrong|{order_id}|{vendor}|{timestamp}")]
                            ])
                            
                            await safe_send_message(vendor_chat, msg, asap_buttons)
                            logger.info(f"Sent ASAP request to {vendor}")
                    
                    # Update MDG - KEEP TIME REQUEST BUTTONS (don't change to assignment mode)
                    order["requested_time"] = "ASAP"
                    mdg_text = build_mdg_dispatch_text(order) + f"\n\n⏰ Requested: ASAP"
                    await safe_edit_message(
                        DISPATCH_MAIN_CHAT_ID,
                        order["mdg_message_id"],
                        mdg_text,
                        mdg_time_request_keyboard(order_id)  # Keep same buttons
                    )
                    logger.info(f"Updated MDG for order {order_id}")
                
                elif action == "req_time":
                    order_id = data[1]
                    logger.info(f"Processing TIME request for order {order_id}")
                    
                    # Check if single vendor or multi-vendor order
                    order = STATE.get(order_id)
                    if not order:
                        return
                    
                    vendors = order.get("vendors", [])
                    
                    if len(vendors) == 1:
                        # SINGLE VENDOR: Show smart suggestions directly
                        timestamp = int(datetime.now().timestamp())
                        smart_buttons = build_smart_time_suggestions(order_id)
                        
                        # If no confirmed orders, show only EXACT TIME
                        if len(smart_buttons) == 1 and "no last order" in smart_buttons[0].text.lower():
                            time_buttons = [[InlineKeyboardButton("EXACT TIME ⏰", callback_data=f"req_exact|{order_id}|{timestamp}")]]
                        else:
                            # Build keyboard with smart suggestions in rows of 2
                            time_buttons = []
                            for i in range(0, len(smart_buttons), 2):
                                row = [smart_buttons[i]]
                                if i + 1 < len(smart_buttons):
                                    row.append(smart_buttons[i + 1])
                                time_buttons.append(row)
                            
                            # Add EXACT TIME submenu
                            time_buttons.append([
                                InlineKeyboardButton("EXACT TIME ⏰", callback_data=f"req_exact|{order_id}|{timestamp}")
                            ])
                        
                        await safe_send_message(
                            DISPATCH_MAIN_CHAT_ID,
                            "🕒 Select time to request:",
                            InlineKeyboardMarkup(time_buttons)
                        )
                    else:
                        # MULTI-VENDOR: Show restaurant selection IMMEDIATELY
                        timestamp = int(datetime.now().timestamp())
                        
                        # Build restaurant selection buttons
                        vendor_buttons = []
                        for vendor in vendors:
                            vendor_buttons.append([
                                InlineKeyboardButton(f"Request {vendor}", callback_data=f"req_vendor|{order_id}|{vendor}|{timestamp}")
                            ])
                        
                        await safe_send_message(
                            DISPATCH_MAIN_CHAT_ID,
                            "🏪 Select restaurant to request time:",
                            InlineKeyboardMarkup(vendor_buttons)
                        )
                
                elif action == "req_exact":
                    order_id = data[1]
                    logger.info(f"Processing EXACT TIME request for order {order_id}")
                    # Show exact time spinner per assignment (hours + minutes up to end of current day)
                    await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        "🕒 Set exact time:",
                        exact_time_keyboard(order_id)
                    )
                
                elif action == "req_same":
                    order_id = data[1]
                    logger.info(f"Processing SAME TIME AS request for order {order_id}")
                    # Show recent orders list per assignment using existing function
                    await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        "🔗 Select order to match timing:",
                        same_time_keyboard(order_id)
                    )
                
                elif action == "time_selected":
                    order_id, selected_time = data[1], data[2]
                    order = STATE.get(order_id)
                    if not order:
                        return
                    
                    logger.info(f"Time {selected_time} selected for order {order_id}")
                    
                    # Send time request to vendors WITH BUTTONS
                    for vendor in order["vendors"]:
                        vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                        if vendor_chat:
                            if order["order_type"] == "shopify":
                                msg = f"#{order['name'][-2:]} at {selected_time}?"
                            else:
                                addr = order['customer']['address'].split(',')[0]
                                msg = f"*{addr}* at {selected_time}?"
                            
                            # Specific time request buttons: "Works 👍" + "Later at" + "Something is wrong"
                            timestamp = int(datetime.now().timestamp())
                            time_buttons = InlineKeyboardMarkup([
                                [InlineKeyboardButton("Works 👍", callback_data=f"works|{order_id}|{vendor}|{timestamp}"),
                                 InlineKeyboardButton("Later at", callback_data=f"later|{order_id}|{vendor}|{timestamp}")],
                                [InlineKeyboardButton("Something is wrong", callback_data=f"wrong|{order_id}|{vendor}|{timestamp}")]
                            ])
                            
                            await safe_send_message(vendor_chat, msg, time_buttons)
                    
                    # Update MDG - KEEP TIME REQUEST BUTTONS (don't change to assignment mode)
                    order["requested_time"] = selected_time
                    mdg_text = build_mdg_dispatch_text(order) + f"\n\n⏰ Requested: {selected_time}"
                    await safe_edit_message(
                        DISPATCH_MAIN_CHAT_ID,
                        order["mdg_message_id"],
                        mdg_text,
                        mdg_time_request_keyboard(order_id)  # Keep same buttons
                    )
                
                elif action == "exact_back_hours":
                    order_id = data[1]
                    logger.info(f"Going back to hours for order {order_id}")
                    # Edit current message to show hours again (fold minutes)
                    try:
                        chat_id = cq["message"]["chat"]["id"]
                        message_id = cq["message"]["message_id"]
                        logger.info(f"Editing message {message_id} in chat {chat_id} back to hours")
                        
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text="🕒 Select hour:",
                            reply_markup=exact_time_keyboard(order_id)
                        )
                        logger.info(f"Successfully edited message back to hours")
                    except Exception as e:
                        logger.error(f"Error going back to hours: {e}")
                        logger.error(f"Chat ID: {chat_id}, Message ID: {message_id}")
                
                elif action == "exact_hide":
                    order_id = data[1]
                    logger.info(f"Hiding exact time picker for order {order_id}")
                    # Delete the exact time picker message
                    try:
                        chat_id = cq["message"]["chat"]["id"]
                        message_id = cq["message"]["message_id"]
                        logger.info(f"Deleting message {message_id} in chat {chat_id}")
                        
                        await bot.delete_message(chat_id, message_id)
                        logger.info(f"Successfully deleted message")
                    except Exception as e:
                        logger.error(f"Could not delete message: {e}")
                        logger.error(f"Chat ID: {chat_id}, Message ID: {message_id}")
                        # If delete fails, try to edit to a minimal message
                        try:
                            await bot.edit_message_text(
                                chat_id=chat_id,
                                message_id=message_id,
                                text="🕒 Time picker closed"
                            )
                            logger.info(f"Fallback: edited message to closed state")
                        except Exception as e2:
                            logger.error(f"Fallback edit also failed: {e2}")
                
                elif action == "exact_hour":
                    order_id, hour = data[1], int(data[2])
                    logger.info(f"Processing exact hour {hour} for order {order_id}")
                    # Edit current message to show minute picker (don't send new message)
                    try:
                        chat_id = cq["message"]["chat"]["id"]
                        message_id = cq["message"]["message_id"]
                        logger.info(f"Editing message {message_id} to show minutes for hour {hour}")
                        
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=f"🕒 Select minutes for {hour:02d}:XX:",
                            reply_markup=exact_hour_keyboard(order_id, hour)
                        )
                        logger.info(f"Successfully edited message for hour {hour}")
                    except Exception as e:
                        logger.error(f"Error showing exact hour {hour}: {e}")
                
                elif action == "exact_selected":
                    order_id, selected_time = data[1], data[2]
                    order = STATE.get(order_id)
                    if not order:
                        return
                    
                    logger.info(f"Exact time {selected_time} selected for order {order_id}")
                    
                    # Send exact time request to vendors WITH BUTTONS (same as time_selected)
                    for vendor in order["vendors"]:
                        vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                        if vendor_chat:
                            if order["order_type"] == "shopify":
                                msg = f"#{order['name'][-2:]} at {selected_time}?"
                            else:
                                addr = order['customer']['address'].split(',')[0]
                                msg = f"*{addr}* at {selected_time}?"
                            
                            # Specific time request buttons: "Works 👍" + "Later at" + "Something is wrong"
                            timestamp = int(datetime.now().timestamp())
                            time_buttons = InlineKeyboardMarkup([
                                [InlineKeyboardButton("Works 👍", callback_data=f"works|{order_id}|{vendor}|{timestamp}"),
                                 InlineKeyboardButton("Later at", callback_data=f"later|{order_id}|{vendor}|{timestamp}")],
                                [InlineKeyboardButton("Something is wrong", callback_data=f"wrong|{order_id}|{vendor}|{timestamp}")]
                            ])
                            
                            await safe_send_message(vendor_chat, msg, time_buttons)
                    
                    # Update MDG - KEEP TIME REQUEST BUTTONS (don't change to assignment mode)
                    order["requested_time"] = selected_time
                    mdg_text = build_mdg_dispatch_text(order) + f"\n\n⏰ Requested: {selected_time}"
                    await safe_edit_message(
                        DISPATCH_MAIN_CHAT_ID,
                        order["mdg_message_id"],
                        mdg_text,
                        mdg_time_request_keyboard(order_id)  # Keep same buttons
                    )
                
                elif action == "smart_time":
                    order_id, selected_time = data[1], data[2]
                    order = STATE.get(order_id)
                    if not order:
                        return
                    
                    logger.info(f"Smart time {selected_time} selected for order {order_id}")
                    
                    # Send time request to vendor (single vendor only)
                    vendor = order["vendors"][0]  # Single vendor
                    vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                    if vendor_chat:
                        if order["order_type"] == "shopify":
                            msg = f"#{order['name'][-2:]} at {selected_time}?"
                        else:
                            addr = order['customer']['address'].split(',')[0]
                            msg = f"*{addr}* at {selected_time}?"
                        
                        # Specific time request buttons: "Works 👍" + "Later at" + "Something is wrong"
                        timestamp = int(datetime.now().timestamp())
                        time_buttons = InlineKeyboardMarkup([
                            [InlineKeyboardButton("Works 👍", callback_data=f"works|{order_id}|{vendor}|{timestamp}"),
                             InlineKeyboardButton("Later at", callback_data=f"later|{order_id}|{vendor}|{timestamp}")],
                            [InlineKeyboardButton("Something is wrong", callback_data=f"wrong|{order_id}|{vendor}|{timestamp}")]
                        ])
                        
                        await safe_send_message(vendor_chat, msg, time_buttons)
                    
                    # Update MDG - KEEP TIME REQUEST BUTTONS
                    order["requested_time"] = selected_time
                    mdg_text = build_mdg_dispatch_text(order) + f"\n\n⏰ Requested: {selected_time}"
                    await safe_edit_message(
                        DISPATCH_MAIN_CHAT_ID,
                        order["mdg_message_id"],
                        mdg_text,
                        mdg_time_request_keyboard(order_id)
                    )
                
                elif action == "req_vendor":
                    order_id, selected_vendor = data[1], data[2]
                    logger.info(f"Selected vendor {selected_vendor} for order {order_id}")
                    
                    # Show ASAP + TIME buttons for this specific vendor
                    timestamp = int(datetime.now().timestamp())
                    vendor_time_buttons = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("Request ASAP", callback_data=f"vendor_asap|{order_id}|{selected_vendor}|{timestamp}"),
                            InlineKeyboardButton("Request TIME", callback_data=f"vendor_time|{order_id}|{selected_vendor}|{timestamp}")
                        ]
                    ])
                    
                    await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        f"🕒 Request time from {selected_vendor}:",
                        vendor_time_buttons
                    )
                
                elif action == "vendor_asap":
                    order_id, vendor = data[1], data[2]
                    order = STATE.get(order_id)
                    if not order:
                        return
                    
                    logger.info(f"Processing ASAP request for vendor {vendor} in order {order_id}")
                    
                    # Send ASAP request to ONLY this vendor
                    vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                    if vendor_chat:
                        if order["order_type"] == "shopify":
                            msg = f"#{order['name'][-2:]} ASAP?"
                        else:
                            addr = order['customer']['address'].split(',')[0]
                            msg = f"*{addr}* ASAP?"
                        
                        # ASAP request buttons
                        timestamp = int(datetime.now().timestamp())
                        asap_buttons = InlineKeyboardMarkup([
                            [InlineKeyboardButton("Will prepare at", callback_data=f"prepare|{order_id}|{vendor}|{timestamp}")],
                            [InlineKeyboardButton("Something is wrong", callback_data=f"wrong|{order_id}|{vendor}|{timestamp}")]
                        ])
                        
                        await safe_send_message(vendor_chat, msg, asap_buttons)
                        logger.info(f"Sent ASAP request to {vendor}")
                    
                    # Post status to MDG and go back to restaurant selection
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"📤 ASAP request sent to {vendor}")
                
                elif action == "vendor_time":
                    order_id, vendor = data[1], data[2]
                    logger.info(f"Processing TIME request for vendor {vendor} in order {order_id}")
                    
                    # Check for smart suggestions
                    timestamp = int(datetime.now().timestamp())
                    smart_buttons = build_smart_time_suggestions(order_id, vendor)
                    
                    # If no confirmed orders, show only EXACT TIME
                    if len(smart_buttons) == 1 and "no last order" in smart_buttons[0].text.lower():
                        time_buttons = [[InlineKeyboardButton("EXACT TIME ⏰", callback_data=f"vendor_exact|{order_id}|{vendor}|{timestamp}")]]
                    else:
                        # Build keyboard with smart suggestions
                        time_buttons = []
                        for i in range(0, len(smart_buttons), 2):
                            row = [smart_buttons[i]]
                            if i + 1 < len(smart_buttons):
                                row.append(smart_buttons[i + 1])
                            time_buttons.append(row)
                        
                        # Add EXACT TIME submenu
                        time_buttons.append([
                            InlineKeyboardButton("EXACT TIME ⏰", callback_data=f"vendor_exact|{order_id}|{vendor}|{timestamp}")
                        ])
                    
                    await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        f"🕒 Select time for {vendor}:",
                        InlineKeyboardMarkup(time_buttons)
                    )
                    # User clicked on "no confirmed orders" message - just close it
                    try:
                        chat_id = cq["message"]["chat"]["id"]
                        message_id = cq["message"]["message_id"]
                        await bot.delete_message(chat_id, message_id)
                    except:
                        pass
                elif action == "toggle":
                    order_id, vendor = data[1], data[2]
                    order = STATE.get(order_id)
                    if not order:
                        logger.warning(f"Order {order_id} not found for toggle")
                        return
                    
                    expanded = not order["vendor_expanded"].get(vendor, False)
                    order["vendor_expanded"][vendor] = expanded
                    
                    logger.info(f"Toggling vendor message for {vendor}, expanded: {expanded}")
                    
                    # Update vendor message with only toggle button
                    if expanded:
                        text = build_vendor_details_text(order, vendor)
                        toggle_text = "◂ Hide"
                    else:
                        text = build_vendor_summary_text(order, vendor)
                        toggle_text = "Details ▸"
                    
                    timestamp = int(datetime.now().timestamp())
                    toggle_keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(toggle_text, callback_data=f"toggle|{order_id}|{vendor}|{timestamp}")]
                    ])
                    
                    await safe_edit_message(
                        VENDOR_GROUP_MAP[vendor],
                        order["vendor_messages"][vendor],
                        text,
                        toggle_keyboard
                    )
                
                elif action == "works":
                    order_id, vendor = data[1], data[2]
                    order = STATE.get(order_id)
                    if not order:
                        return
                        
                    logger.info(f"Vendor {vendor} replied Works for order {order_id}")
                    
                    # Track confirmed time
                    requested_time = order.get("requested_time", "ASAP")
                    if requested_time != "ASAP":
                        order["confirmed_time"] = requested_time
                        logger.info(f"Confirmed time {requested_time} for order {order_id}")
                    
                    # Post to MDG with status line
                    msg = f"■ {vendor} replied: Works 👍 ■"
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, msg)
                
                elif action in ["later", "prepare"]:
                    order_id, vendor = data[1], data[2]
                    order = STATE.get(order_id)
                    requested = order.get("requested_time", "ASAP") if order else "ASAP"
                    
                    logger.info(f"Vendor {vendor} requested {action} for order {order_id}")
                    
                    # Show time picker for vendor response
                    await safe_send_message(
                        VENDOR_GROUP_MAP[vendor],
                        f"Select time for {action}:",
                        time_picker_keyboard(order_id, f"{action}_time", requested)
                    )
                
                elif action == "wrong":
                    order_id, vendor = data[1], data[2]
                    logger.info(f"Vendor {vendor} reported something wrong for order {order_id}")
                    # Show "Something is wrong" submenu per assignment
                    timestamp = int(datetime.now().timestamp())
                    wrong_buttons = [
                        [InlineKeyboardButton("Ordered product(s) not available", callback_data=f"wrong_unavailable|{order_id}|{vendor}|{timestamp}")],
                        [InlineKeyboardButton("Order is canceled", callback_data=f"wrong_canceled|{order_id}|{vendor}|{timestamp}")],
                        [InlineKeyboardButton("Technical issue", callback_data=f"wrong_technical|{order_id}|{vendor}|{timestamp}")],
                        [InlineKeyboardButton("Something else", callback_data=f"wrong_other|{order_id}|{vendor}|{timestamp}")],
                        [InlineKeyboardButton("We have a delay", callback_data=f"wrong_delay|{order_id}|{vendor}|{timestamp}")]
                    ]
                    
                    await safe_send_message(
                        VENDOR_GROUP_MAP[vendor],
                        "What's wrong?",
                        InlineKeyboardMarkup(wrong_buttons)
                    )
                
                elif action == "wrong_unavailable":
                    order_id, vendor = data[1], data[2]
                    order = STATE.get(order_id)
                    if order and order.get("order_type") == "shopify":
                        msg = "Please call the customer and organize a replacement. If no replacement is possible, write a message to dishbee."
                    else:
                        msg = "Please call the customer and organize a replacement or a refund."
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: {msg} ■")
                
                elif action == "wrong_canceled":
                    order_id, vendor = data[1], data[2]
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: Order is canceled ■")
                
                elif action in ["wrong_technical", "wrong_other"]:
                    order_id, vendor = data[1], data[2]
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: Write a message to dishbee and describe the issue ■")
                
                elif action == "wrong_delay":
                    order_id, vendor = data[1], data[2]
                    order = STATE.get(order_id)
                    agreed_time = order.get("confirmed_time") or order.get("requested_time", "ASAP") if order else "ASAP"
                    
                    # Show delay time picker (agreed time + 5 min intervals)
                    try:
                        if agreed_time != "ASAP":
                            hour, minute = map(int, agreed_time.split(':'))
                            base_time = datetime.now().replace(hour=hour, minute=minute)
                        else:
                            base_time = datetime.now()
                        
                        delay_intervals = get_time_intervals(base_time, 4)
                        timestamp = int(datetime.now().timestamp())
                        delay_buttons = []
                        for i in range(0, len(delay_intervals), 2):
                            row = [InlineKeyboardButton(delay_intervals[i], callback_data=f"delay_time|{order_id}|{vendor}|{delay_intervals[i]}|{timestamp}")]
                            if i + 1 < len(delay_intervals):
                                row.append(InlineKeyboardButton(delay_intervals[i + 1], callback_data=f"delay_time|{order_id}|{vendor}|{delay_intervals[i + 1]}|{timestamp}"))
                            delay_buttons.append(row)
                        
                        await safe_send_message(
                            VENDOR_GROUP_MAP[vendor],
                            "Select delay time:",
                            InlineKeyboardMarkup(delay_buttons)
                        )
                    except:
                        await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: We have a delay ■")
                
                elif action in ["later_time", "prepare_time"]:
                    order_id, vendor, selected_time = data[1], data[2], data[3]
                    order = STATE.get(order_id)
                    if not order:
                        return
                        
                    logger.info(f"Vendor {vendor} selected time {selected_time} for {action}")
                    
                    # Track confirmed time
                    order["confirmed_time"] = selected_time
                    logger.info(f"Confirmed time {selected_time} for order {order_id}")
                    
                    # Post to MDG with status line
                    if action == "later_time":
                        msg = f"■ {vendor} replied: Later at {selected_time} ■"
                    else:  # prepare_time
                        msg = f"■ {vendor} replied: Will prepare at {selected_time} ■"
                    
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, msg)
                
                elif action == "delay_time":
                    order_id, vendor, delay_time = data[1], data[2], data[3]
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: We have a delay - new time {delay_time} ■")
                    order_id, vendor, delay_time = data[1], data[2], data[3]
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: We have a delay - new time {delay_time} ■")
                
                elif action == "same_as":
                    order_id, reference_order_id = data[1], data[2]
                    order = STATE.get(order_id)
                    reference_order = STATE.get(reference_order_id)
                    
                    if not order or not reference_order:
                        return
                    
                    logger.info(f"Setting same time as between {order_id} and {reference_order_id}")
                    
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
                            
                            await safe_send_message(vendor_chat, msg)
                    
                    # Update MDG
                    order["requested_time"] = reference_time
                    mdg_text = build_mdg_dispatch_text(order) + f"\n\n⏰ Requested: {reference_time} (same as {reference_order.get('name', 'other order')})"
                    await safe_edit_message(
                        DISPATCH_MAIN_CHAT_ID,
                        order["mdg_message_id"],
                        mdg_text,
                        mdg_assignment_keyboard(order_id)
                    )
                
                elif action == "assign":
                    order_id, driver_name, driver_id = data[1], data[2], data[3]
                    order = STATE.get(order_id)
                    if not order:
                        return
                    
                    logger.info(f"Assigning order {order_id} to {driver_name}")
                    
                    # Send DM to driver with assignment details
                    dm_text = build_assignment_dm(order)
                    try:
                        await safe_send_message(int(driver_id), dm_text)
                    except:
                        await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"⚠️ Could not DM {driver_name}")
                    
                    # Update order status
                    order["assigned_to"] = driver_name
                    order["status"] = "assigned"
                
                elif action == "delivered":
                    order_id = data[1]
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"Order {order_id} was delivered.")
                
                elif action == "delayed":
                    order_id = data[1]
                    order = STATE.get(order_id)
                    if order:
                        order["status"] = "delayed"
                
            except Exception as e:
                logger.error(f"Callback error: {e}")
        
        asyncio.run(handle())
        return "OK"
        
    except Exception as e:
        logger.error(f"Telegram webhook error: {e}")
        return jsonify({"error": "Internal server error"}), 500

def build_assignment_dm(order: Dict[str, Any]) -> str:
    """Build assignment DM text for drivers - per assignment requirements"""
    try:
        vendors = order.get("vendors", [])
        order_type = order.get("order_type", "shopify")
        
        # Order number + restaurant name
        if order_type == "shopify":
            title = f"dishbee #{order['name'][-2:]} - {', '.join(vendors)}"
        else:
            title = ', '.join(vendors)
        
        # Address - clickable for Google Maps
        address = order['customer']['address']
        
        # Phone number - clickable to call directly
        phone = order['customer']['phone']
        
        # Product count
        items_count = len(order.get("items_text", "").split('\n'))
        
        # Customer name
        customer_name = order['customer']['name']
        
        text = f"{title}\n\n"
        text += f"📍 {address}\n"
        text += f"📞 {phone}\n"
        text += f"🛍️ {items_count} items\n"
        text += f"👤 {customer_name}"
        
        return text
    except Exception as e:
        logger.error(f"Error building assignment DM: {e}")
        return f"Assignment error for order {order.get('name', 'Unknown')}"

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
            "note": payload.get("note", ""),
            "tips": "",  # Extract from payload if available
            "payment_method": "Paid",  # Determine from payload
            "delivery_time": "ASAP",
            "is_pickup": is_pickup,
            "created_at": datetime.now(),
            "vendor_messages": {},
            "vendor_expanded": {},
            "requested_time": None,
            "confirmed_time": None,
            "status": "new"
        }

        async def process():
            try:
                # Send to MDG with time request buttons
                mdg_text = build_mdg_dispatch_text(order)
                
                # Special formatting for pickup orders per assignment
                if is_pickup:
                    pickup_header = "**Order for Selbstabholung**\n"
                    pickup_message = f"\nPlease call the customer and arrange the pickup time on this number: {phone}"
                    mdg_text = pickup_header + mdg_text + pickup_message
                
                mdg_msg = await safe_send_message(
                    DISPATCH_MAIN_CHAT_ID,
                    mdg_text,
                    mdg_time_request_keyboard(order_id)
                )
                order["mdg_message_id"] = mdg_msg.message_id
                
                # Send to each vendor group (summary by default) - NO BUTTONS on order messages
                for vendor in vendors:
                    vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                    if vendor_chat:
                        vendor_text = build_vendor_summary_text(order, vendor)
                        # Order message has only expand/collapse button
                        timestamp = int(datetime.now().timestamp())
                        toggle_keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("Details ▸", callback_data=f"toggle|{order_id}|{vendor}|{timestamp}")]
                        ])
                        vendor_msg = await safe_send_message(
                            vendor_chat,
                            vendor_text,
                            toggle_keyboard
                        )
                        order["vendor_messages"][vendor] = vendor_msg.message_id
                        order["vendor_expanded"][vendor] = False
                
                # Save order
                STATE[order_id] = order
                RECENT_ORDERS.append({
                    "order_id": order_id,
                    "created_at": datetime.now(),
                    "vendors": vendors
                })
                
                # Keep only recent orders
                if len(RECENT_ORDERS) > 50:
                    RECENT_ORDERS.pop(0)
                
                logger.info(f"Order {order_id} processed successfully")
                
            except Exception as e:
                logger.error(f"Error processing order: {e}")
                raise

        asyncio.run(process())
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        logger.error(f"Shopify webhook error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# --- APP ENTRY ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Complete Assignment Implementation on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)

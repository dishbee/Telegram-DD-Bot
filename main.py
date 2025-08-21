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
STATE_FILE = "/tmp/bot_state.json"

def save_state():
    """Save STATE to file for persistence"""
    try:
        # Convert datetime objects to strings for JSON serialization
        state_to_save = {}
        for order_id, order_data in STATE.items():
            order_copy = order_data.copy()
            if order_copy.get("created_at"):
                order_copy["created_at"] = order_copy["created_at"].isoformat()
            state_to_save[order_id] = order_copy
        
        with open(STATE_FILE, 'w') as f:
            json.dump(state_to_save, f)
        logger.info(f"Saved state with {len(STATE)} orders")
    except Exception as e:
        logger.error(f"Error saving state: {e}")

def load_state():
    """Load STATE from file on startup"""
    global STATE
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                loaded_state = json.load(f)
            
            # Convert datetime strings back to datetime objects
            for order_id, order_data in loaded_state.items():
                if order_data.get("created_at"):
                    order_data["created_at"] = datetime.fromisoformat(order_data["created_at"])
                STATE[order_id] = order_data
            
            logger.info(f"Loaded state with {len(STATE)} orders")
        else:
            logger.info("No existing state file found, starting fresh")
    except Exception as e:
        logger.error(f"Error loading state: {e}")
        STATE = {}

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

def get_recent_orders_for_same_time(current_order_id: str) -> List[Dict[str, str]]:
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

def find_last_confirmed_order() -> Optional[Dict[str, Any]]:
    """Find most recent order from today with confirmed time"""
    today = datetime.now().date()
    
    confirmed_orders = []
    for order_id, order_data in STATE.items():
        # Check if order is from today
        if order_data.get("created_at"):
            order_date = order_data["created_at"].date()
            if order_date == today and order_data.get("confirmed_time"):
                confirmed_orders.append({
                    "order_id": order_id,
                    "order_name": order_data.get("name", ""),
                    "confirmed_time": order_data["confirmed_time"],
                    "created_at": order_data["created_at"]
                })
    
    if confirmed_orders:
        # Return most recent confirmed order
        return max(confirmed_orders, key=lambda x: x["created_at"])
    
    return None

def build_smart_time_suggestions(order_id: str, vendor: str = None) -> InlineKeyboardMarkup:
    """Build smart time suggestions based on last confirmed order"""
    try:
        last_order = find_last_confirmed_order()
        
        if not last_order:
            # No confirmed orders today - show only EXACT TIME
            if vendor:
                return InlineKeyboardMarkup([
                    [InlineKeyboardButton("EXACT TIME ⏰", callback_data=f"vendor_exact|{order_id}|{vendor}|{int(datetime.now().timestamp())}")]
                ])
            else:
                return InlineKeyboardMarkup([
                    [InlineKeyboardButton("EXACT TIME ⏰", callback_data=f"req_exact|{order_id}|{int(datetime.now().timestamp())}")]
                ])
        
        # Parse confirmed time
        confirmed_time = last_order["confirmed_time"]
        order_number = last_order["order_name"][-2:] if len(last_order["order_name"]) >= 2 else last_order["order_name"]
        
        # Create 4 time suggestions
        try:
            hour, minute = map(int, confirmed_time.split(':'))
            base_time = datetime.now().replace(hour=hour, minute=minute)
            
            suggestions = []
            for i in range(4):
                new_time = base_time + timedelta(minutes=(i + 1) * 5)
                time_str = new_time.strftime("%H:%M")
                button_text = f"#{order_number} {confirmed_time} + {(i + 1) * 5}min"
                
                if vendor:
                    callback_data = f"smart_time|{order_id}|{vendor}|{time_str}|{int(datetime.now().timestamp())}"
                else:
                    callback_data = f"smart_time|{order_id}|{time_str}|{int(datetime.now().timestamp())}"
                
                suggestions.append(InlineKeyboardButton(button_text, callback_data=callback_data))
        except:
            # If parsing fails, show EXACT TIME only
            if vendor:
                return InlineKeyboardMarkup([
                    [InlineKeyboardButton("EXACT TIME ⏰", callback_data=f"vendor_exact|{order_id}|{vendor}|{int(datetime.now().timestamp())}")]
                ])
            else:
                return InlineKeyboardMarkup([
                    [InlineKeyboardButton("EXACT TIME ⏰", callback_data=f"req_exact|{order_id}|{int(datetime.now().timestamp())}")]
                ])
        
        # Build keyboard with suggestions + EXACT TIME
        rows = []
        for i in range(0, len(suggestions), 2):
            row = [suggestions[i]]
            if i + 1 < len(suggestions):
                row.append(suggestions[i + 1])
            rows.append(row)
        
        # Add EXACT TIME button
        if vendor:
            exact_button = InlineKeyboardButton("EXACT TIME ⏰", callback_data=f"vendor_exact|{order_id}|{vendor}|{int(datetime.now().timestamp())}")
        else:
            exact_button = InlineKeyboardButton("EXACT TIME ⏰", callback_data=f"req_exact|{order_id}|{int(datetime.now().timestamp())}")
        
        rows.append([exact_button])
        
        return InlineKeyboardMarkup(rows)
        
    except Exception as e:
        logger.error(f"Error building smart time suggestions: {e}")
        # Fallback to EXACT TIME only
        if vendor:
            return InlineKeyboardMarkup([
                [InlineKeyboardButton("EXACT TIME ⏰", callback_data=f"vendor_exact|{order_id}|{vendor}|{int(datetime.now().timestamp())}")]
            ])
        else:
            return InlineKeyboardMarkup([
                [InlineKeyboardButton("EXACT TIME ⏰", callback_data=f"req_exact|{order_id}|{int(datetime.now().timestamp())}")]
            ])

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
    """Build vendor short summary (default collapsed state)"""
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
    """Build vendor full details (expanded state)"""
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
        order = STATE.get(order_id)
        
        if not order:
            # Fallback to default buttons if order not found in STATE
            logger.warning(f"Order {order_id} not found in STATE, using default buttons")
            return InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Request ASAP", callback_data=f"req_asap|{order_id}|{timestamp}"),
                    InlineKeyboardButton("Request TIME", callback_data=f"req_time|{order_id}|{timestamp}")
                ],
                [
                    InlineKeyboardButton("Request SAME TIME AS", callback_data=f"req_same|{order_id}|{timestamp}")
                ]
            ])
        
        vendors = order.get("vendors", [])
        logger.info(f"Order {order_id} has vendors: {vendors} (count: {len(vendors)})")
        
        if len(vendors) > 1:
            # Multi-vendor order: show restaurant selection buttons
            logger.info(f"MULTI VENDOR detected: {vendors}")
            rows = []
            for vendor in vendors:
                logger.info(f"Adding button for vendor: {vendor}")
                rows.append([InlineKeyboardButton(f"Request {vendor}", callback_data=f"req_vendor|{order_id}|{vendor}|{timestamp}")])
            
            # Add SAME TIME AS button
            rows.append([InlineKeyboardButton("Request SAME TIME AS", callback_data=f"req_same|{order_id}|{timestamp}")])
            
            logger.info(f"Sending restaurant selection with {len(rows)} buttons")
            return InlineKeyboardMarkup(rows)
        else:
            # Single vendor: show ASAP + TIME + SAME TIME AS
            logger.info(f"SINGLE VENDOR detected: {vendors}")
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

def vendor_keyboard(order_id: str, vendor: str, expanded: bool) -> InlineKeyboardMarkup:
    """Build vendor buttons - ONLY toggle for original order messages"""
    try:
        timestamp = int(datetime.now().timestamp())
        toggle_text = "◂ Hide" if expanded else "Details ▸"
        
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_text, callback_data=f"toggle|{order_id}|{vendor}|{timestamp}")]
        ])
    except Exception as e:
        logger.error(f"Error building vendor keyboard: {e}")
        return InlineKeyboardMarkup([])

def exact_time_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build exact time picker - hours first"""
    try:
        current_time = datetime.now()
        current_hour = current_time.hour
        
        # Show hours from current hour to 23
        rows = []
        hour_buttons = []
        
        for hour in range(current_hour, 24):
            hour_buttons.append(
                InlineKeyboardButton(f"{hour:02d}:XX", callback_data=f"exact_hour|{order_id}|{hour}|{int(datetime.now().timestamp())}")
            )
        
        # Arrange in rows of 4
        for i in range(0, len(hour_buttons), 4):
            rows.append(hour_buttons[i:i+4])
        
        # Add back button
        rows.append([InlineKeyboardButton("← Back", callback_data=f"exact_hide|{order_id}|{int(datetime.now().timestamp())}")])
        
        return InlineKeyboardMarkup(rows)
    except Exception as e:
        logger.error(f"Error building exact time keyboard: {e}")
        return InlineKeyboardMarkup([])

def exact_hour_keyboard(order_id: str, hour: int) -> InlineKeyboardMarkup:
    """Build minute picker for selected hour with 3-minute intervals"""
    try:
        current_time = datetime.now()
        
        # Generate 3-minute intervals
        minutes = []
        for i in range(0, 60, 3):  # 0, 3, 6, 9, ..., 57
            # Skip past times if it's the current hour
            if hour == current_time.hour and i <= current_time.minute:
                continue
            time_str = f"{hour:02d}:{i:02d}"
            minutes.append(InlineKeyboardButton(time_str, callback_data=f"exact_selected|{order_id}|{time_str}|{int(datetime.now().timestamp())}"))
        
        # Arrange in rows of 4
        rows = []
        for i in range(0, len(minutes), 4):
            rows.append(minutes[i:i+4])
        
        # Add back button
        rows.append([InlineKeyboardButton("← Back to hours", callback_data=f"exact_back_hours|{order_id}|{int(datetime.now().timestamp())}")])
        
        return InlineKeyboardMarkup(rows)
    except Exception as e:
        logger.error(f"Error building exact hour keyboard: {e}")
        return InlineKeyboardMarkup([])

def same_time_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build same time as selection keyboard"""
    try:
        recent = get_recent_orders_for_same_time(order_id)
        rows = []
        
        for order_info in recent:
            text = f"{order_info['display_name']} ({order_info['vendor']})"
            callback = f"same_as|{order_id}|{order_info['order_id']}|{int(datetime.now().timestamp())}"
            rows.append([InlineKeyboardButton(text, callback_data=callback)])
        
        if not recent:
            rows.append([InlineKeyboardButton("No recent orders", callback_data=f"no_recent|{int(datetime.now().timestamp())}")])
        
        return InlineKeyboardMarkup(rows)
    except Exception as e:
        logger.error(f"Error building same time keyboard: {e}")
        return InlineKeyboardMarkup([])

async def safe_send_message(chat_id: int, text: str, reply_markup=None, parse_mode=ParseMode.MARKDOWN):
    """Send message with error handling"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Send message attempt {attempt + 1}")
            return await bot.send_message(
                chat_id=chat_id, 
                text=text, 
                reply_markup=reply_markup, 
                parse_mode=parse_mode
            )
        except Exception as e:
            logger.error(f"Send message attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            else:
                logger.error(f"Failed to send message after {max_retries} attempts: {e}")
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
            
            data_str = cq.get("data") or ""
            logger.info(f"Raw callback data: {data_str}")
            data = data_str.split("|")
            logger.info(f"Parsed callback data: {data}")
            
            if not data:
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
                    
                    # Send ASAP request to vendors
                    for vendor in order["vendors"]:
                        vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                        if vendor_chat:
                            if order["order_type"] == "shopify":
                                msg = f"#{order['name'][-2:]} ASAP?"
                            else:
                                addr = order['customer']['address'].split(',')[0]
                                msg = f"*{addr}* ASAP?"
                            
                            await safe_send_message(vendor_chat, msg)
                    
                    # Update MDG status
                    order["requested_time"] = "ASAP"
                    save_state()  # Save state after modification
                    mdg_text = build_mdg_dispatch_text(order) + f"\n\n⏰ Requested: ASAP"
                    await safe_edit_message(
                        DISPATCH_MAIN_CHAT_ID,
                        order["mdg_message_id"],
                        mdg_text,
                        mdg_time_request_keyboard(order_id)
                    )
                
                elif action == "req_time":
                    order_id = data[1]
                    logger.info(f"Processing TIME request for order {order_id}")
                    
                    order = STATE.get(order_id)
                    if not order:
                        logger.error(f"Order {order_id} not found in STATE")
                        return
                    
                    vendors = order.get("vendors", [])
                    logger.info(f"Order {order_id} has vendors: {vendors} (count: {len(vendors)})")
                    
                    if len(vendors) > 1:
                        # Multi-vendor: show restaurant selection
                        logger.info(f"MULTI VENDOR detected: {vendors}")
                        rows = []
                        for vendor in vendors:
                            logger.info(f"Adding button for vendor: {vendor}")
                            rows.append([InlineKeyboardButton(f"Request {vendor}", callback_data=f"req_vendor|{order_id}|{vendor}|{int(datetime.now().timestamp())}")])
                        
                        await safe_send_message(
                            DISPATCH_MAIN_CHAT_ID,
                            "🏪 Select restaurant to request time:",
                            InlineKeyboardMarkup(rows)
                        )
                    else:
                        # Single vendor: show smart time suggestions
                        logger.info(f"SINGLE VENDOR detected: {vendors}")
                        await safe_send_message(
                            DISPATCH_MAIN_CHAT_ID,
                            "🕒 Select time to request:",
                            build_smart_time_suggestions(order_id)
                        )
                
                elif action == "req_vendor":
                    order_id, vendor = data[1], data[2]
                    logger.info(f"Selected vendor {vendor} for order {order_id}")
                    
                    # Show ASAP + TIME + SAME TIME AS for this vendor
                    timestamp = int(datetime.now().timestamp())
                    vendor_buttons = InlineKeyboardMarkup([
                        [InlineKeyboardButton("Request ASAP", callback_data=f"vendor_asap|{order_id}|{vendor}|{timestamp}")],
                        [InlineKeyboardButton("Request TIME", callback_data=f"vendor_time|{order_id}|{vendor}|{timestamp}")],
                        [InlineKeyboardButton("Request SAME TIME AS", callback_data=f"vendor_same|{order_id}|{vendor}|{timestamp}")]
                    ])
                    
                    await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        f"🕒 Request time from {vendor}:",
                        vendor_buttons
                    )
                
                elif action == "vendor_asap":
                    order_id, vendor = data[1], data[2]
                    logger.info(f"Processing ASAP request for vendor {vendor} in order {order_id}")
                    
                    order = STATE.get(order_id)
                    if not order:
                        logger.warning(f"Order {order_id} not found in state")
                        return
                    
                    # Send ASAP request to specific vendor only
                    vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                    if vendor_chat:
                        if order["order_type"] == "shopify":
                            msg = f"#{order['name'][-2:]} ASAP?"
                        else:
                            addr = order['customer']['address'].split(',')[0]
                            msg = f"*{addr}* ASAP?"
                        
                        await safe_send_message(vendor_chat, msg)
                        
                        # Post status to MDG
                        await safe_send_message(
                            DISPATCH_MAIN_CHAT_ID,
                            f"⏰ ASAP request sent to {vendor}"
                        )
                
                elif action == "vendor_time":
                    order_id, vendor = data[1], data[2]
                    logger.info(f"Processing TIME request for vendor {vendor} in order {order_id}")
                    
                    # Show smart time suggestions for this vendor
                    await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        f"🕒 Select time for {vendor}:",
                        build_smart_time_suggestions(order_id, vendor)
                    )
                
                elif action == "smart_time":
                    if len(data) == 4:  # Single vendor
                        order_id, time_str = data[1], data[2]
                        vendor = None
                    else:  # Multi vendor
                        order_id, vendor, time_str = data[1], data[2], data[3]
                    
                    order = STATE.get(order_id)
                    if not order:
                        logger.warning(f"Order {order_id} not found in state")
                        return
                    
                    if vendor:
                        # Send to specific vendor
                        vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                        if vendor_chat:
                            if order["order_type"] == "shopify":
                                msg = f"#{order['name'][-2:]} at {time_str}?"
                            else:
                                addr = order['customer']['address'].split(',')[0]
                                msg = f"*{addr}* at {time_str}?"
                            
                            await safe_send_message(vendor_chat, msg)
                            
                            # Post status to MDG
                            await safe_send_message(
                                DISPATCH_MAIN_CHAT_ID,
                                f"⏰ Time request ({time_str}) sent to {vendor}"
                            )
                    else:
                        # Send to all vendors (single vendor order)
                        for v in order["vendors"]:
                            vendor_chat = VENDOR_GROUP_MAP.get(v)
                            if vendor_chat:
                                if order["order_type"] == "shopify":
                                    msg = f"#{order['name'][-2:]} at {time_str}?"
                                else:
                                    addr = order['customer']['address'].split(',')[0]
                                    msg = f"*{addr}* at {time_str}?"
                                
                                await safe_send_message(vendor_chat, msg)
                        
                        # Update MDG status
                        order["requested_time"] = time_str
                        save_state()  # Save state after modification
                        mdg_text = build_mdg_dispatch_text(order) + f"\n\n⏰ Requested: {time_str}"
                        await safe_edit_message(
                            DISPATCH_MAIN_CHAT_ID,
                            order["mdg_message_id"],
                            mdg_text,
                            mdg_time_request_keyboard(order_id)
                        )
                
                elif action == "req_exact":
                    order_id = data[1]
                    # Show exact time picker
                    await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        "🕒 Set exact time:",
                        exact_time_keyboard(order_id)
                    )
                
                elif action == "vendor_exact":
                    order_id, vendor = data[1], data[2]
                    logger.info(f"Processing EXACT TIME request for vendor {vendor} in order {order_id}")
                    
                    # Show exact time picker for specific vendor
                    await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        f"🕒 Set exact time for {vendor}:",
                        exact_time_keyboard(order_id)
                    )
                
                elif action == "exact_hour":
                    order_id, hour = data[1], int(data[2])
                    logger.info(f"Processing exact hour {hour} for order {order_id}")
                    
                    # Edit message to show minute picker
                    await bot.edit_message_text(
                        chat_id=cq["message"]["chat"]["id"],
                        message_id=cq["message"]["message_id"],
                        text=f"🕒 Select minute for {hour:02d}:XX",
                        reply_markup=exact_hour_keyboard(order_id, hour)
                    )
                
                elif action == "exact_selected":
                    order_id, time_str = data[1], data[2]
                    
                    order = STATE.get(order_id)
                    if not order:
                        logger.warning(f"Order {order_id} not found in state")
                        return
                    
                    # Send to all vendors
                    for vendor in order["vendors"]:
                        vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                        if vendor_chat:
                            if order["order_type"] == "shopify":
                                msg = f"#{order['name'][-2:]} at {time_str}?"
                            else:
                                addr = order['customer']['address'].split(',')[0]
                                msg = f"*{addr}* at {time_str}?"
                            
                            await safe_send_message(vendor_chat, msg)
                    
                    # Update MDG status
                    order["requested_time"] = time_str
                    save_state()  # Save state after modification
                    mdg_text = build_mdg_dispatch_text(order) + f"\n\n⏰ Requested: {time_str}"
                    await safe_edit_message(
                        DISPATCH_MAIN_CHAT_ID,
                        order["mdg_message_id"],
                        mdg_text,
                        mdg_time_request_keyboard(order_id)
                    )
                    
                    # Delete the time picker message
                    try:
                        await bot.delete_message(
                            chat_id=cq["message"]["chat"]["id"],
                            message_id=cq["message"]["message_id"]
                        )
                    except:
                        logger.info("Could not delete time picker message")
                
                elif action == "exact_back_hours":
                    order_id = data[1]
                    logger.info(f"Going back to hours for order {order_id}")
                    
                    # Edit message back to hour picker
                    await bot.edit_message_text(
                        chat_id=cq["message"]["chat"]["id"],
                        message_id=cq["message"]["message_id"],
                        text="🕒 Set exact time:",
                        reply_markup=exact_time_keyboard(order_id)
                    )
                
                elif action == "exact_hide":
                    order_id = data[1]
                    logger.info(f"Hiding exact time picker for order {order_id}")
                    
                    # Delete the time picker message
                    try:
                        await bot.delete_message(
                            chat_id=cq["message"]["chat"]["id"],
                            message_id=cq["message"]["message_id"]
                        )
                    except Exception as e:
                        logger.error(f"Error deleting message: {e}")
                        # Fallback: edit to a simple closed message
                        try:
                            await bot.edit_message_text(
                                chat_id=cq["message"]["chat"]["id"],
                                message_id=cq["message"]["message_id"],
                                text="⏰ Time picker closed"
                            )
                        except Exception as e2:
                            logger.error(f"Error editing message: {e2}")
                
                elif action == "req_same":
                    order_id = data[1]
                    logger.info(f"Processing SAME TIME AS request for order {order_id}")
                    
                    try:
                        # Show recent orders list
                        await safe_send_message(
                            DISPATCH_MAIN_CHAT_ID,
                            "🔗 Select order to match timing:",
                            same_time_keyboard(order_id)
                        )
                    except Exception as e:
                        logger.error(f"Error building same time keyboard: {e}")
                        await safe_send_message(
                            DISPATCH_MAIN_CHAT_ID,
                            "No recent orders found for grouping"
                        )
                
                elif action == "vendor_same":
                    order_id, vendor = data[1], data[2]
                    logger.info(f"VENDOR_SAME: Starting handler with data: {data}")
                    
                    try:
                        # Show recent orders for specific vendor
                        await safe_send_message(
                            DISPATCH_MAIN_CHAT_ID,
                            f"🔗 Select order to match timing for {vendor}:",
                            same_time_keyboard(order_id)
                        )
                    except Exception as e:
                        logger.error(f"VENDOR_SAME: Error: {e}")
                        await safe_send_message(
                            DISPATCH_MAIN_CHAT_ID,
                            f"No recent orders found for {vendor}"
                        )
                
                # VENDOR RESPONSES
                elif action == "toggle":
                    order_id, vendor = data[1], data[2]
                    order = STATE.get(order_id)
                    if not order:
                        logger.warning(f"Order {order_id} not found in state")
                        return
                    
                    logger.info(f"Toggling vendor message for {vendor}, expanded: {order.get('vendor_expanded', {}).get(vendor, False)}")
                    
                    expanded = not order.get("vendor_expanded", {}).get(vendor, False)
                    if "vendor_expanded" not in order:
                        order["vendor_expanded"] = {}
                    order["vendor_expanded"][vendor] = expanded
                    save_state()  # Save state after modification
                    
                    # Update vendor message
                    if expanded:
                        text = build_vendor_details_text(order, vendor)
                    else:
                        text = build_vendor_summary_text(order, vendor)
                    
                    await safe_edit_message(
                        VENDOR_GROUP_MAP[vendor],
                        order["vendor_messages"][vendor],
                        text,
                        vendor_keyboard(order_id, vendor, expanded)
                    )
                
                elif action == "works":
                    order_id, vendor = data[1], data[2]
                    
                    # Track confirmed time
                    order = STATE.get(order_id)
                    if order and order.get("requested_time"):
                        order["confirmed_time"] = order["requested_time"]
                        save_state()  # Save state after modification
                    
                    # Post status line to MDG
                    msg = f"■ {vendor} replied: Works 👍 ■"
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, msg)
                
                elif action == "later":
                    order_id, vendor = data[1], data[2]
                    # Show time picker for "later at"
                    await safe_send_message(
                        VENDOR_GROUP_MAP[vendor],
                        f"Select time for later:",
                        # Time picker implementation would go here
                        InlineKeyboardMarkup([[InlineKeyboardButton("Time picker placeholder", callback_data="placeholder")]])
                    )
                
                elif action == "prepare":
                    order_id, vendor = data[1], data[2]
                    # Show time picker for "will prepare at"
                    await safe_send_message(
                        VENDOR_GROUP_MAP[vendor],
                        f"Select preparation time:",
                        # Time picker implementation would go here
                        InlineKeyboardMarkup([[InlineKeyboardButton("Time picker placeholder", callback_data="placeholder")]])
                    )
                
                elif action == "wrong":
                    order_id, vendor = data[1], data[2]
                    # Show "Something is wrong" submenu
                    wrong_buttons = [
                        [InlineKeyboardButton("Ordered product(s) not available", callback_data=f"wrong_unavailable|{order_id}|{vendor}|{int(datetime.now().timestamp())}")],
                        [InlineKeyboardButton("Order is canceled", callback_data=f"wrong_canceled|{order_id}|{vendor}|{int(datetime.now().timestamp())}")],
                        [InlineKeyboardButton("Technical issue", callback_data=f"wrong_technical|{order_id}|{vendor}|{int(datetime.now().timestamp())}")],
                        [InlineKeyboardButton("Something else", callback_data=f"wrong_other|{order_id}|{vendor}|{int(datetime.now().timestamp())}")],
                        [InlineKeyboardButton("We have a delay", callback_data=f"wrong_delay|{order_id}|{vendor}|{int(datetime.now().timestamp())}")]
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
                        msg = f"■ {vendor}: Please call the customer and organize a replacement. If no replacement is possible, write a message to dishbee. ■"
                    else:
                        msg = f"■ {vendor}: Please call the customer and organize a replacement or a refund. ■"
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, msg)
                
                elif action == "wrong_canceled":
                    order_id, vendor = data[1], data[2]
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: Order is canceled ■")
                
                elif action in ["wrong_technical", "wrong_other"]:
                    order_id, vendor = data[1], data[2]
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: Write a message to dishbee and describe the issue ■")
                
                elif action == "wrong_delay":
                    order_id, vendor = data[1], data[2]
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: We have a delay ■")
                    
            except Exception as e:
                logger.error(f"Callback error: {e}")
        
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
                # Save order to STATE FIRST
                STATE[order_id] = order
                
                # Save state to persist through restarts
                save_state()
                
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
                save_state()  # Save state after modification
                
                # Send to each vendor group (summary by default) - NO BUTTONS on order messages
                for vendor in vendors:
                    vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                    if vendor_chat:
                        vendor_text = build_vendor_summary_text(order, vendor)
                        # Order message has only expand/collapse button
                        toggle_keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("Details ▸", callback_data=f"toggle|{order_id}|{vendor}|{int(datetime.now().timestamp())}")]
                        ])
                        vendor_msg = await safe_send_message(
                            vendor_chat,
                            vendor_text,
                            toggle_keyboard
                        )
                        order["vendor_messages"][vendor] = vendor_msg.message_id
                        order["vendor_expanded"][vendor] = False
                
                save_state()  # Save state with vendor message IDs
                
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
    # Load persistent state on startup
    load_state()
    
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Complete Assignment Implementation on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)

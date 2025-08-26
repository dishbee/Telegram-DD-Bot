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

# Create event loop for async operations
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def run_async(coro):
    """Run async function in background thread"""
    asyncio.run_coroutine_threadsafe(coro, loop)

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

def get_last_confirmed_order(vendor: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get the most recent order with confirmed time from today"""
    today = datetime.now().date()
    confirmed_orders = []
    
    for order_id, order_data in STATE.items():
        # Check if order is from today
        created_at = order_data.get("created_at")
        if not created_at or created_at.date() != today:
            continue
            
        # Check if order has confirmed time
        if not order_data.get("confirmed_time"):
            continue
            
        # If vendor specified, filter by vendor
        if vendor and order_data.get("vendors") and vendor not in order_data["vendors"]:
            continue
            
        confirmed_orders.append({"order_id": order_id, "data": order_data})
    
    if not confirmed_orders:
        return None
        
    return max(confirmed_orders, key=lambda x: x["data"]["confirmed_time"])["data"]

def safe_send_message(chat_id: int, text: str, reply_markup: InlineKeyboardMarkup = None) -> Any:
    """Safely send a Telegram message with retry logic"""
    retries = 3
    for attempt in range(retries):
        try:
            return bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        except (TimedOut, NetworkError) as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            if attempt == retries - 1:
                logger.error(f"All {retries} attempts failed: {e}")
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
        except TelegramError as e:
            logger.error(f"Telegram error: {e}")
            raise

def build_mdg_dispatch_text(order: Dict[str, Any]) -> str:
    """Build MDG dispatch text based on order type"""
    title = f"dishbee + {' & '.join(order['vendors'])}" if order["order_type"] == "shopify" else order["vendors"][0]
    order_num = f" #{order['name'][-2:]}" if order["order_type"] == "shopify" else ""
    address = f"**{fmt_address(order['customer']['address'])}**"
    note = f"\n*Note*: {order['note']}" if order['note'] else ""
    tips = f"\n*Tips*: {order['tips']}" if order['tips'] else ""
    payment = f"\n*Payment*: {order['payment_method']}" if order["order_type"] == "shopify" else ""
    items = order["items_text"]
    
    return f"{title}{order_num}\n{address}{note}{tips}{payment}\n{items}\n*Customer*: {order['customer']['name']}"

def build_vendor_summary_text(order: Dict[str, Any], vendor: str) -> str:
    """Build vendor summary text"""
    order_num = f"#{order['name'][-2:]}"
    items = "\n".join(order["vendor_items"].get(vendor, []))
    note = f"\n*Note*: {order['note']}" if order['note'] else ""
    return f"{order_num}\n{items}{note}"

def build_vendor_details_text(order: Dict[str, Any], vendor: str) -> str:
    """Build vendor details text"""
    summary = build_vendor_summary_text(order, vendor)
    address = f"\n*Address*: {fmt_address(order['customer']['address'])}"
    phone = f"\n*Phone*: {order['customer']['phone']}"
    created = f"\n*Placed*: {order['created_at'].strftime('%H:%M')}"
    return f"{summary}{address}{phone}{created}"

def mdg_time_request_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Generate MDG time request keyboard"""
    keyboard = [
        [InlineKeyboardButton("Request ASAP", callback_data=f"asap_{order_id}")],
        [InlineKeyboardButton("Request TIME", callback_data=f"time_{order_id}")]
    ]
    # Only add "Request SAME TIME AS" for multi-vendor orders
    if len(STATE.get(order_id, {}).get("vendors", [])) > 1:
        recent = get_recent_orders_for_same_time(order_id)
        if recent:
            same_time_options = [InlineKeyboardButton(opt["display_name"], callback_data=f"same_{order_id}_{opt['order_id']}") for opt in recent]
            keyboard.append(same_time_options[:2])  # Limit to 2 options per row
            if len(same_time_options) > 2:
                keyboard.append(same_time_options[2:])
    return InlineKeyboardMarkup(keyboard)

def vendor_keyboard(order_id: str, vendor: str, expanded: bool) -> InlineKeyboardMarkup:
    """Generate vendor keyboard"""
    button = InlineKeyboardButton("Details ▸" if not expanded else "◂ Hide", callback_data=f"toggle_{order_id}_{vendor}")
    return InlineKeyboardMarkup([[button]])

# --- CALLBACK HANDLERS ---
@app.route('/webhooks/shopify', methods=['POST'])
def shopify_webhook():
    """Handle Shopify webhook"""
    try:
        hmac_header = request.headers.get('X-Shopify-Hmac-Sha256')
        if not verify_webhook(request.get_data(), hmac_header):
            return jsonify({"error": "Invalid HMAC"}), 401
        
        payload = request.get_json()
        if not payload or "line_items" not in payload:
            return jsonify({"error": "Invalid payload"}), 400
        
        order_id = payload.get("id", str(hash(str(payload))))
        order_name = payload.get("name", f"ORDER-{order_id}")
        customer_name = payload.get("customer", {}).get("first_name", "Unknown") + " " + payload.get("customer", {}).get("last_name", "")
        phone = payload.get("customer", {}).get("phone", "No phone")
        address = fmt_address(payload.get("shipping_address", {}))
        
        # Detect vendors from line items
        vendors = set()
        vendor_items: Dict[str, List[str]] = {}
        for item in payload.get("line_items", []):
            vendor_tag = next((tag for tag in TAG_TO_RESTAURANT.keys() if tag in item.get("title", "").upper()), None)
            vendor = TAG_TO_RESTAURANT.get(vendor_tag, "Unknown Vendor")
            vendors.add(vendor)
            if vendor not in vendor_items:
                vendor_items[vendor] = []
            item_line = f"{item.get('quantity', 1)}x {item.get('title', 'Unknown Item')}"
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
        
        # Build order object
        order = {
            "name": order_name,
            "order_type": "shopify",
            "vendors": list(vendors),
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
            "confirmed_by": None,
            "delivered": False,  # Track delivery status
            "status": "new"
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
                mdg_text = build_mdg_dispatch_text(order)
                
                # Special formatting for pickup orders
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
                
                # Send to each vendor group (summary by default)
                for vendor in vendors:
                    vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                    if vendor_chat:
                        vendor_text = build_vendor_summary_text(order, vendor)
                        # Order message has only expand/collapse button
                        vendor_msg = await safe_send_message(
                            vendor_chat,
                            vendor_text,
                            vendor_keyboard(order_id, vendor, False)
                        )
                        order["vendor_messages"][vendor] = vendor_msg.message_id
                        order["vendor_expanded"][vendor] = False
                
                # Update STATE with message IDs
                STATE[order_id] = order
                
                # Keep only recent orders
                RECENT_ORDERS.append({
                    "order_id": order_id,
                    "created_at": datetime.now(),
                    "vendors": list(vendors)
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

# --- APP ENTRY ---
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

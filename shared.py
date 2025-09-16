# shared.py - Shared constants, utilities, and state management

import os
import json
import hmac
import hashlib
import base64
import asyncio
import logging
import threading
import requests
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

# --- GLOBAL STATE ---
STATE: Dict[str, Dict[str, Any]] = {}
RECENT_ORDERS: List[Dict[str, Any]] = []

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
    """Generate 5-minute intervals for time picker"""
    intervals = []
    for i in range(count):
        time_option = base_time + timedelta(minutes=(i + 1) * 5)
        intervals.append(time_option.strftime("%H:%M"))
    return intervals

def get_recent_orders_for_same_time(current_order_id: str) -> List[Dict[str, str]]:
    """Get recent CONFIRMED orders (last 1 hour) for 'same time as' functionality"""
    one_hour_ago = datetime.now() - timedelta(hours=1)
    recent = []
    
    for order_id, order_data in STATE.items():
        if order_id == current_order_id:
            continue
        # Only include orders with confirmed_time
        if not order_data.get("confirmed_time"):
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
        if vendor and vendor not in order_data.get("vendors", []):
            continue
            
        confirmed_orders.append(order_data)
    
    # Sort by created_at and return most recent
    if confirmed_orders:
        confirmed_orders.sort(key=lambda x: x["created_at"], reverse=True)
        return confirmed_orders[0]
    
    return None

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

# --- ASSIGNMENT UTILITIES ---
def build_assignment_dm_text(order: Dict[str, Any]) -> str:
    """Build assignment message text for private DM"""
    vendor_shortcut = RESTAURANT_SHORTCUTS.get(order['vendors'][0], order['vendors'][0][:2].upper())
    total_products = sum(len(items) for items in order['vendor_items'].values())
    
    return (
        f"🔖 #{order['name'][-2:]} - dishbee ({vendor_shortcut})\n"
        f"👤 {order['customer']['name']}\n"
        f"📍 {order['customer']['address']}\n"
        f"\n"
        f"{order['customer']['phone']}\n"
        f"📦 Products: {total_products}"
    )

def get_assignment_cta_keyboard(order_id: str, vendor: str) -> InlineKeyboardMarkup:
    """Build CTA buttons for assignment DM"""
    vendor_shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
    buttons = [
        [InlineKeyboardButton("☎️ Call customer", callback_data=f"call_customer|{order_id}")],
        [InlineKeyboardButton("🧭 Navigate", callback_data=f"navigate|{order_id}")],
        [InlineKeyboardButton("⏰ Delay", callback_data=f"delay|{order_id}")],
        [InlineKeyboardButton(f"🍽 Call {vendor_shortcut}", callback_data=f"call_restaurant|{order_id}|{vendor}")],
        [InlineKeyboardButton("✅ Delivered", callback_data=f"delivered|{order_id}")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_delay_options_keyboard(order_id: str, agreed_time: str) -> InlineKeyboardMarkup:
    """Build delay options keyboard based on agreed time"""
    try:
        if agreed_time == "ASAP":
            base_time = datetime.now()
        else:
            hour, minute = map(int, agreed_time.split(':'))
            base_time = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        options = []
        for minutes in [5, 10, 15, 20]:
            delay_time = base_time + timedelta(minutes=minutes)
            options.append(delay_time.strftime("%H:%M"))
        
        buttons = [
            [InlineKeyboardButton(options[0], callback_data=f"delay_time|{order_id}|{options[0]}")],
            [InlineKeyboardButton(options[1], callback_data=f"delay_time|{order_id}|{options[1]}")],
            [InlineKeyboardButton(options[2], callback_data=f"delay_time|{order_id}|{options[2]}")],
            [InlineKeyboardButton(options[3], callback_data=f"delay_time|{order_id}|{options[3]}")]
        ]
        return InlineKeyboardMarkup(buttons)
    except Exception as e:
        logger.error(f"Error building delay options: {e}")
        return InlineKeyboardMarkup([])
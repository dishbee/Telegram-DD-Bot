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
from zoneinfo import ZoneInfo
from typing import Dict, Any, List, Optional
from flask import Flask, request, jsonify
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest
from telegram.error import TelegramError, TimedOut, NetworkError

# Timezone configuration for Passau, Germany (Europe/Berlin)
TIMEZONE = ZoneInfo("Europe/Berlin")

def now() -> datetime:
    """Get current time in Passau timezone (Europe/Berlin)."""
    return datetime.now(TIMEZONE)

from mdg import (
    configure as configure_mdg,
    build_mdg_dispatch_text,
    mdg_initial_keyboard,
    mdg_time_request_keyboard,
    mdg_time_submenu_keyboard,
    order_reference_options_keyboard,
    group_time_adjustment_keyboard,
    same_time_keyboard,
    time_picker_keyboard,
    exact_time_keyboard,
    exact_hour_keyboard,
    build_smart_time_suggestions,
    get_recent_orders_for_same_time,
    get_last_confirmed_order,
    shortcut_to_vendor,
)
from rg import (
    build_vendor_summary_text,
    build_vendor_details_text,
    vendor_time_keyboard,
    vendor_keyboard,
    restaurant_response_keyboard,
    vendor_exact_time_keyboard,
    vendor_exact_hour_keyboard,
    SHORTCUT_TO_VENDOR,
)
import upc
from upc import check_all_vendors_confirmed, mdg_assignment_keyboard, courier_selection_keyboard
import uc  # noqa: F401  # UC placeholder for future assignment logic
from utils import clean_product_name

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

# Placeholder for restaurant accounts (to be added later)
# Format: {"Restaurant Name": user_id} - user_id of restaurant's Telegram account
RESTAURANT_ACCOUNTS: Dict[str, int] = json.loads(os.environ.get("RESTAURANT_ACCOUNTS", "{}"))

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
    "Wittelsbacher Apotheke": "AP",
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

# --- ORDER GROUPING STATE ---
GROUPS: Dict[str, Dict[str, Any]] = {}  # {group_id: {color, order_ids[], created_at}}
GROUP_COLORS = ["🟠", "🔵", "🟣", "🟤", "⚫", "⚪"]
NEXT_GROUP_COLOR_INDEX = 0

# --- RESTAURANT COMMUNICATION TRACKING ---
# Track forwarded messages from restaurants to MDG for reply functionality
# Format: {mdg_message_id: {"vendor": "Restaurant Name", "rg_chat_id": -1234567890}}
RESTAURANT_FORWARDED_MESSAGES: Dict[int, Dict[str, Any]] = {}

configure_mdg(STATE, RESTAURANT_SHORTCUTS)
upc.configure(STATE, bot)  # Configure UPC module with STATE and bot reference

# Create event loop for async operations
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)


def run_async(coro):
    """Run async function in background thread."""
    asyncio.run_coroutine_threadsafe(coro, loop)


def validate_phone(phone: str) -> Optional[str]:
    """Validate and format phone number for tel: links."""
    if not phone or phone == "N/A":
        return None

    import re

    cleaned = re.sub(r'[^\d+\s]', '', phone).strip()
    digits_only = re.sub(r'\D', '', cleaned)
    if len(digits_only) < 7:
        return None

    return cleaned


# --- HELPER FUNCTIONS ---
def verify_webhook(raw: bytes, hmac_header: str) -> bool:
    """Verify Shopify webhook HMAC."""
    try:
        if not hmac_header:
            return False
        computed = hmac.new(WEBHOOK_SECRET.encode("utf-8"), raw, hashlib.sha256).digest()
        expected = base64.b64encode(computed).decode("utf-8")
        return hmac.compare_digest(expected, hmac_header)
    except Exception as exc:
        logger.error(f"HMAC verification error: {exc}")
        return False


def fmt_address(addr: Dict[str, Any]) -> str:
    """Format address - only street, building number and zip code (no city!)."""
    if not addr:
        return "No address provided"

    try:
        parts = []
        if addr.get("address1"):
            parts.append(addr["address1"])
        if addr.get("zip"):
            parts.append(addr["zip"])
        return ", ".join(parts) if parts else "Address incomplete"
    except Exception as exc:
        logger.error(f"Address formatting error: {exc}")
        return "Address formatting error"

def create_or_join_group(order_id: str, ref_order_id: str) -> None:
    """
    Create a new group or join an existing group when orders are grouped together.
    Called after vendor confirms time for orders grouped via BTN-SAME or BTN-GROUP.
    
    Args:
        order_id: Current order being grouped
        ref_order_id: Reference order to group with
    """
    global NEXT_GROUP_COLOR_INDEX
    
    order = STATE.get(order_id)
    ref_order = STATE.get(ref_order_id)
    
    if not order or not ref_order:
        logger.error(f"Cannot group: order {order_id} or reference {ref_order_id} not found")
        return
    
    # Check if reference order is already in a group
    if ref_order.get("group_id"):
        # Join existing group
        group_id = ref_order["group_id"]
        group = GROUPS.get(group_id)
        
        if group:
            # Add current order to existing group
            group["order_ids"].append(order_id)
            
            # Update current order's group fields
            order["group_id"] = group_id
            order["group_color"] = group["color"]
            order["group_position"] = len(group["order_ids"])
            
            logger.info(f"Order {order_id} joined existing group {group_id} at position {order['group_position']}")
        else:
            logger.error(f"Group {group_id} not found in GROUPS dict")
    else:
        # Create new group with both orders
        # Get next color
        color = GROUP_COLORS[NEXT_GROUP_COLOR_INDEX]
        NEXT_GROUP_COLOR_INDEX = (NEXT_GROUP_COLOR_INDEX + 1) % len(GROUP_COLORS)
        
        # Generate unique group ID
        timestamp = now().strftime("%Y%m%d_%H%M%S")
        group_id = f"group_{color}_{timestamp}"
        
        # Create group
        GROUPS[group_id] = {
            "color": color,
            "order_ids": [ref_order_id, order_id],
            "created_at": now()
        }
        
        # Update reference order
        ref_order["group_id"] = group_id
        ref_order["group_color"] = color
        ref_order["group_position"] = 1
        
        # Update current order
        order["group_id"] = group_id
        order["group_color"] = color
        order["group_position"] = 2
        
        logger.info(f"Created new group {group_id} with orders {ref_order_id} (1/2) and {order_id} (2/2)")

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

async def send_status_message(chat_id: int, text: str, auto_delete_after: int = 20):
    """
    Send a status message that auto-deletes after specified seconds.
    
    Used for temporary status updates like:
    - Vendor confirmations: "Vendor replied: Will prepare #90 at 14:57 👍"
    - ASAP/TIME requests sent: "✅ ASAP request sent to Vendor"
    - Delays: "Vendor: We have a delay for #90 - new time 15:00"
    
    Args:
        chat_id: Chat to send message to
        text: Message text
        auto_delete_after: Seconds to wait before deletion (default: 20)
    """
    try:
        msg = await safe_send_message(chat_id, text)
        # Schedule deletion in background
        asyncio.create_task(_delete_after_delay(chat_id, msg.message_id, auto_delete_after))
    except Exception as e:
        logger.error(f"Error in send_status_message: {e}")

async def _delete_after_delay(chat_id: int, message_id: int, delay: int):
    """Helper to delete message after delay"""
    try:
        await asyncio.sleep(delay)
        await safe_delete_message(chat_id, message_id)
    except Exception as e:
        logger.error(f"Error in _delete_after_delay: {e}")

def build_assignment_confirmation_message(order: dict) -> str:
    """
    Build assignment confirmation message showing all vendor confirmations.
    
    This message appears in MDG after all vendors have confirmed their times.
    It replaces the old "✅ All vendors confirmed" message with detailed
    vendor information including pickup times and product counts.
    
    Format for multi-vendor orders:
        🔖 #58 - dishbee (JS+LR)
        ✅ Restaurants confirmed:
        🏠 Julis Spätzlerei: 12:50 📦 1
        🏠 Leckerolls: 12:55 📦 3
    
    Format for single-vendor orders:
        🔖 #58 - dishbee (LR)
        ✅ Restaurant confirmed:
        🏠 Leckerolls: 12:55 📦 3
    
    Product count logic:
    - Parses vendor_items lines (format: "- X x Product Name")
    - Extracts quantity from each line
    - Sums total products per vendor
    
    Args:
        order: Order dict from STATE with vendors, confirmed_times, vendor_items
    
    Returns:
        Formatted message string for MDG display
    """
    vendors = order.get("vendors", [])
    confirmed_times = order.get("confirmed_times", {})
    vendor_items = order.get("vendor_items", {})
    order_num = order.get('name', '')[-2:] if len(order.get('name', '')) >= 2 else order.get('name', '')
    
    # Build vendor shortcuts string
    vendor_shortcuts = "+".join([RESTAURANT_SHORTCUTS.get(v, v[:2].upper()) for v in vendors])
    
    # Header
    message = f"🔖 #{order_num} - dishbee ({vendor_shortcuts})\n"
    
    # Title (singular/plural)
    if len(vendors) > 1:
        message += "✅ Restaurants confirmed:\n"
    else:
        message += "✅ Restaurant confirmed:\n"
    
    # Vendor details
    for vendor in vendors:
        pickup_time = confirmed_times.get(vendor, "ASAP")
        
        # Count products for this vendor
        items = vendor_items.get(vendor, [])
        product_count = 0
        for item_line in items:
            if ' x ' in item_line:
                qty_part = item_line.split(' x ')[0].strip().lstrip('-').strip()
                try:
                    product_count += int(qty_part)
                except ValueError:
                    product_count += 1
            else:
                product_count += 1
        
        message += f"🏠 {vendor}: {pickup_time} 📦 {product_count}\n"
    
    return message

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


# =============================================================================
# RESTAURANT COMMUNICATION FUNCTIONS
# =============================================================================
# Handles two-way communication between restaurants and MDG:
# 1. Restaurant → MDG: Forward manual messages from restaurant accounts
# 2. MDG → Restaurant: Forward replies to restaurant messages
# All messages auto-delete after 10 minutes
# =============================================================================

async def forward_restaurant_message_to_mdg(vendor_name: str, message_text: str, rg_chat_id: int, original_msg_id: int):
    """
    Forward a manual message from restaurant to MDG.
    
    Args:
        vendor_name: Name of the restaurant (e.g., "Zweite Heimat")
        message_text: The text message from restaurant
        rg_chat_id: Restaurant group chat ID
        original_msg_id: Original message ID in RG (for tracking)
    """
    try:
        # Format: "Vendor says: message text"
        forwarded_text = f"{vendor_name} says: {message_text}"
        
        # Send to MDG
        msg = await safe_send_message(DISPATCH_MAIN_CHAT_ID, forwarded_text)
        
        if msg:
            mdg_message_id = msg.message_id
            
            # Track this forwarded message for reply functionality
            RESTAURANT_FORWARDED_MESSAGES[mdg_message_id] = {
                "vendor": vendor_name,
                "rg_chat_id": rg_chat_id,
                "original_msg_id": original_msg_id
            }
            
            logger.info(f"Forwarded message from {vendor_name} to MDG (MDG msg_id: {mdg_message_id})")
            
            # Schedule auto-delete after 10 minutes
            await asyncio.sleep(600)  # 10 minutes = 600 seconds
            await safe_delete_message(DISPATCH_MAIN_CHAT_ID, mdg_message_id)
            
            # Clean up tracking
            if mdg_message_id in RESTAURANT_FORWARDED_MESSAGES:
                del RESTAURANT_FORWARDED_MESSAGES[mdg_message_id]
            
            logger.info(f"Auto-deleted restaurant message {mdg_message_id} from MDG after 10 minutes")
    
    except Exception as e:
        logger.error(f"Error forwarding restaurant message to MDG: {e}")


async def forward_mdg_reply_to_restaurant(from_user: Dict[str, Any], reply_text: str, replied_to_msg_id: int):
    """
    Forward a reply from MDG back to the restaurant group.
    
    Args:
        from_user: User who sent the reply in MDG
        reply_text: The reply text
        replied_to_msg_id: Message ID in MDG that was replied to
    """
    try:
        # Get the restaurant info from tracking
        restaurant_info = RESTAURANT_FORWARDED_MESSAGES.get(replied_to_msg_id)
        if not restaurant_info:
            logger.warning(f"Reply to message {replied_to_msg_id} but no restaurant tracking found")
            return
        
        vendor_name = restaurant_info["vendor"]
        rg_chat_id = restaurant_info["rg_chat_id"]
        user_id = from_user.get('id')
        
        # Get user name from COURIER_MAP (DRIVERS)
        courier_name = None
        for name, cid in DRIVERS.items():
            if cid == user_id:
                courier_name = name
                break
        
        # Fallback to first name if not in COURIER_MAP
        if not courier_name:
            courier_name = from_user.get('first_name', 'User')
        
        # Format: "Courier Name says: reply text"
        reply_message = f"{courier_name} says: {reply_text}"
        
        # Send to restaurant group
        msg = await safe_send_message(rg_chat_id, reply_message)
        
        if msg:
            rg_message_id = msg.message_id
            logger.info(f"Forwarded reply from {courier_name} to {vendor_name} (RG msg_id: {rg_message_id})")
            
            # Schedule auto-delete after 10 minutes
            await asyncio.sleep(600)  # 10 minutes = 600 seconds
            await safe_delete_message(rg_chat_id, rg_message_id)
            
            logger.info(f"Auto-deleted reply message {rg_message_id} from {vendor_name} RG after 10 minutes")
    
    except Exception as e:
        logger.error(f"Error forwarding MDG reply to restaurant: {e}")


# --- WEBHOOK ENDPOINTS ---
@app.route("/", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        "status": "healthy",
        "service": "telegram-dispatch-bot",
        "orders_in_state": len(STATE),
        "timestamp": now().isoformat()
    }), 200

# --- TELEGRAM WEBHOOK ---
# =============================================================================
# ASSIGNMENT SYSTEM ARCHITECTURE
# =============================================================================
# The assignment system handles courier assignment and delivery workflow.
# It consists of three main components working together:
#
# 1. ASSIGNMENT INITIATION (MDG → UPC):
#    - After all vendors confirm times, MDG shows assignment buttons
#    - Two options: "👈 Assign to myself" or "👉 Assign to..."
#    - "Assign to myself" directly assigns to clicking user
#    - "Assign to..." shows live courier selection menu
#
# 2. LIVE COURIER DETECTION:
#    - Queries bot.get_chat_administrators() to get MDG members
#    - Shows actual group members (no hardcoded list dependency)
#    - Filters out bots, only shows human couriers
#    - Falls back to COURIER_MAP environment variable if API fails
#    - All couriers MUST be admins in MDG for detection to work
#
# 3. PRIVATE CHAT WORKFLOW (UPC):
#    - Assigned courier receives DM with order details
#    - Action buttons: 🧭 Navigate, ⏰ Delay, ✅ Delivered
#    - MDG updated with assignment status and courier name
#    - Delay requests sent to all vendors for confirmation
#
# STATE FIELDS USED:
#    - order["status"]: "new" → "assigned" → "delivered"
#    - order["assigned_to"]: user_id of assigned courier
#    - order["confirmed_times"]: {vendor: time} mapping for multi-vendor
#
# CRITICAL PREVENTION:
#    - Duplicate assignment buttons prevented by checking order["status"]
#    - If status == "assigned", skip showing new assignment buttons
#    - Prevents confusion when courier requests delay after assignment
# =============================================================================

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    """Handle Telegram webhooks"""
    try:
        upd = request.get_json(force=True)
        if not upd:
            return "OK"

        # Log all incoming updates for spam detection
        logger.info(f"=== INCOMING UPDATE ===")
        logger.info(f"Update ID: {upd.get('update_id')}")
        logger.info(f"Timestamp: {now().isoformat()}")

        # Check for regular messages (potential spam source)
        if "message" in upd:
            msg = upd["message"]
            from_user = msg.get("from", {})
            chat = msg.get("chat", {})
            text = msg.get("text", "")

            logger.info(f"MESSAGE RECEIVED:")
            logger.info(f"  Chat ID: {chat.get('id')}")
            logger.info(f"  Chat Type: {chat.get('type')}")
            logger.info(f"  Chat Title: {chat.get('title', 'N/A')}")
            logger.info(f"  From User ID: {from_user.get('id')}")
            logger.info(f"  From Username: {from_user.get('username', 'N/A')}")
            logger.info(f"  From First Name: {from_user.get('first_name', 'N/A')}")
            logger.info(f"  From Last Name: {from_user.get('last_name', 'N/A')}")
            logger.info(f"  Message Text: {text[:200]}{'...' if len(text) > 200 else ''}")
            logger.info(f"  Message Length: {len(text)}")

            # Flag potential spam
            if "FOXY" in text.upper() or "airdrop" in text.lower() or "t.me/" in text:
                logger.warning(f"🚨 POTENTIAL SPAM DETECTED: {text[:100]}...")
            
            # Check if this is a vendor responding with issue description
            chat_id = chat.get('id')
            if text and chat_id in VENDOR_GROUP_MAP.values():
                # Find which vendor this chat belongs to
                vendor_name = None
                for vendor, group_id in VENDOR_GROUP_MAP.items():
                    if group_id == chat_id:
                        vendor_name = vendor
                        break
                
                if vendor_name:
                    # Check all orders waiting for issue description from this vendor
                    for order_id, order_data in STATE.items():
                        if order_data.get("waiting_for_issue_description") == vendor_name:
                            # Get order number
                            order_num = order_data['name'][-2:] if len(order_data['name']) >= 2 else order_data['name']
                            
                            # ST-WRITE format from CHEAT-SHEET
                            issue_msg = f"{vendor_name}: Issue with 🔖 #{order_num}: \"{text}\""
                            run_async(safe_send_message(DISPATCH_MAIN_CHAT_ID, issue_msg))
                            
                            # Clear the waiting flag
                            del order_data["waiting_for_issue_description"]
                            
                            logger.info(f"Forwarded issue description from {vendor_name} for order {order_id} to MDG")
                            break
                    
                    # RESTAURANT COMMUNICATION: Forward manual messages from restaurant to MDG
                    # Check if message is from a restaurant account (not bot-generated)
                    user_id = from_user.get('id')
                    if user_id in RESTAURANT_ACCOUNTS.values() and not from_user.get('is_bot', False):
                        logger.info(f"Restaurant message detected from {vendor_name} (user_id: {user_id})")
                        run_async(forward_restaurant_message_to_mdg(vendor_name, text, chat_id, msg.get('message_id')))
            
            # RESTAURANT COMMUNICATION: Handle replies in MDG to restaurant messages
            # Check if this is a reply to a forwarded restaurant message in MDG
            if chat_id == DISPATCH_MAIN_CHAT_ID and msg.get('reply_to_message') and text:
                replied_to_msg_id = msg['reply_to_message']['message_id']
                if replied_to_msg_id in RESTAURANT_FORWARDED_MESSAGES:
                    logger.info(f"Reply detected in MDG to restaurant message {replied_to_msg_id}")
                    run_async(forward_mdg_reply_to_restaurant(from_user, text, replied_to_msg_id))

        cq = upd.get("callback_query")
        if not cq:
            logger.info("=== NO CALLBACK QUERY - END UPDATE ===")
            return "OK"

        # Answer callback query immediately (synchronously)
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery",
                json={"callback_query_id": cq["id"]},
                timeout=5
            )
            if not response.ok:
                logger.error(f"Failed to answer callback query: {response.text}")
        except Exception as e:
            logger.error(f"answer_callback_query error: {e}")
        
        # Process the callback in background
        async def handle():
            data = (cq.get("data") or "").split("|")
            if not data:
                return
            
            action = data[0]
            logger.info(f"Raw callback data: {cq.get('data')}")
            logger.info(f"Parsed callback data: {data}")
            logger.info(f"Processing callback: {action}")
            
            try:
                # VENDOR SELECTION (for multi-vendor orders)
                if action == "req_vendor":
                    order_id, vendor = data[1], data[2]
                    logger.info(f"Selected vendor {vendor} for order {order_id}")
                    
                    # Send vendor-specific time request buttons
                    msg = await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        f"📍 Request time from {vendor}:",
                        vendor_time_keyboard(order_id, vendor)
                    )
                    
                    # Track additional message for cleanup
                    order = STATE.get(order_id)
                    if order:
                        order["mdg_additional_messages"].append(msg.message_id)
                
                # VENDOR-SPECIFIC ACTIONS
                elif action == "vendor_asap":
                    order_id, vendor = data[1], data[2]
                    order = STATE.get(order_id)
                    if not order:
                        logger.warning(f"Order {order_id} not found in state")
                        return
                    
                    # Send ASAP request only to specific vendor
                    vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                    if vendor_chat:
                        if order["order_type"] == "shopify":
                            msg = f"#{order['name'][-2:]} ASAP?"
                        else:
                            addr = order['customer']['address'].split(',')[0]
                            msg = f"*{addr}* ASAP?"
                        
                        # Send with restaurant response buttons
                        await safe_send_message(
                            vendor_chat, 
                            msg,
                            restaurant_response_keyboard("ASAP", order_id, vendor)
                        )
                    
                    # Update MDG status
                    await send_status_message(
                        DISPATCH_MAIN_CHAT_ID,
                        f"✅ ASAP request sent to {vendor}",
                        auto_delete_after=20
                    )
                    
                    # Clean up additional MDG messages
                    await cleanup_mdg_messages(order_id)
                
                elif action == "vendor_time":
                    order_id, vendor = data[1], data[2]
                    logger.info(f"Processing TIME request for {vendor}")
                    order = STATE.get(order_id)
                    if not order:
                        logger.warning(f"Order {order_id} not found in state")
                        return
                    
                    # Show TIME submenu for this vendor
                    keyboard = mdg_time_submenu_keyboard(order_id, vendor)
                    
                    # If keyboard is None, no recent orders - show hour picker directly
                    if keyboard is None:
                        logger.info(f"No recent orders found for {vendor} - showing hour picker directly")
                        msg = await safe_send_message(
                            DISPATCH_MAIN_CHAT_ID,
                            "🕒 Select hour:",
                            exact_time_keyboard(order_id, vendor)
                        )
                        # Track additional message for cleanup
                        order["mdg_additional_messages"].append(msg.message_id)
                    else:
                        # Has recent orders - show them with EXACT TIME button
                        has_recent_orders = len(keyboard.inline_keyboard) > 1  # More than just EXACT TIME button
                        message_text = "Select scheduled order:" if has_recent_orders else "Request exact time:"
                        
                        msg = await safe_send_message(
                            DISPATCH_MAIN_CHAT_ID,
                            message_text,
                            keyboard
                        )
                        
                        # Track additional message for cleanup
                        order["mdg_additional_messages"].append(msg.message_id)
                
                elif action == "vendor_same":
                    logger.info("VENDOR_SAME: Starting handler")
                    order_id, vendor = data[1], data[2]
                    logger.info(f"VENDOR_SAME: Processing for order {order_id}, vendor {vendor}")
                    
                    recent = get_recent_orders_for_same_time(order_id)
                    if recent:
                        msg = await safe_send_message(
                            DISPATCH_MAIN_CHAT_ID,
                            f"🔗 Select order to match timing for {vendor}:",
                            same_time_keyboard(order_id)
                        )
                        # Track additional message for cleanup
                        order = STATE.get(order_id)
                        if order:
                            order["mdg_additional_messages"].append(msg.message_id)
                    else:
                        msg = await safe_send_message(
                            DISPATCH_MAIN_CHAT_ID,
                            "No recent orders found (last 1 hour)"
                        )
                        # Track additional message for cleanup
                        order = STATE.get(order_id)
                        if order:
                            order["mdg_additional_messages"].append(msg.message_id)
                
                elif action == "vendor_exact":
                    logger.info("VENDOR_EXACT: Starting handler")
                    order_id, vendor = data[1], data[2]
                    logger.info(f"VENDOR_EXACT: Processing for order {order_id}, vendor {vendor}")
                    
                    # Show exact time picker
                    msg = await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        f"🕒 Set exact time for {vendor}:",
                        exact_time_keyboard(order_id)
                    )
                    
                    # Track additional message for cleanup
                    order = STATE.get(order_id)
                    if order:
                        order["mdg_additional_messages"].append(msg.message_id)
                
                elif action == "smart_time":
                    order_id, vendor, selected_time = data[1], data[2], data[3]
                    order = STATE.get(order_id)
                    if not order:
                        return
                    
                    # Send time request to specific vendor
                    vendor_chat = VENDOR_GROUP_MAP.get(vendor) if vendor != "all" else None
                    
                    if vendor == "all":
                        # Single vendor order - send to all vendors
                        for v in order["vendors"]:
                            vc = VENDOR_GROUP_MAP.get(v)
                            if vc:
                                if order["order_type"] == "shopify":
                                    msg = f"#{order['name'][-2:]} at {selected_time}?"
                                else:
                                    addr = order['customer']['address'].split(',')[0]
                                    msg = f"*{addr}* at {selected_time}?"
                                
                                await safe_send_message(
                                    vc,
                                    msg,
                                    restaurant_response_keyboard(selected_time, order_id, v)
                                )
                    else:
                        # Multi-vendor - send to specific vendor
                        if vendor_chat:
                            if order["order_type"] == "shopify":
                                msg = f"#{order['name'][-2:]} at {selected_time}?"
                            else:
                                addr = order['customer']['address'].split(',')[0]
                                msg = f"*{addr}* at {selected_time}?"
                            
                            await safe_send_message(
                                vendor_chat,
                                msg,
                                restaurant_response_keyboard(selected_time, order_id, vendor)
                            )
                    
                    # Update state and MDG
                    order["requested_time"] = selected_time
                    await send_status_message(
                        DISPATCH_MAIN_CHAT_ID,
                        f"✅ Time request ({selected_time}) sent to {vendor if vendor != 'all' else 'vendors'}",
                        auto_delete_after=20
                    )
                    
                    # Clean up additional MDG messages
                    await cleanup_mdg_messages(order_id)
                
                # MDG DETAILS TOGGLE
                elif action == "mdg_toggle":
                    order_id = data[1]
                    order = STATE.get(order_id)
                    if not order:
                        logger.warning(f"Order {order_id} not found in state")
                        return
                    
                    # Toggle expansion state
                    is_expanded = order.get("mdg_expanded", False)
                    order["mdg_expanded"] = not is_expanded
                    
                    # Rebuild message with new state
                    show_details = order["mdg_expanded"]
                    mdg_text = build_mdg_dispatch_text(order, show_details=show_details)
                    
                    # Add requested time if exists
                    if order.get("requested_time"):
                        mdg_text += f"\n\n⏰ Requested: {order['requested_time']}"
                    
                    # Update message with new keyboard
                    await safe_edit_message(
                        DISPATCH_MAIN_CHAT_ID,
                        order["mdg_message_id"],
                        mdg_text,
                        mdg_initial_keyboard(order_id)
                    )
                
                # ORIGINAL TIME REQUEST ACTIONS (MDG)
                elif action == "req_asap":
                    order_id = data[1]
                    order = STATE.get(order_id)
                    if not order:
                        logger.warning(f"Order {order_id} not found in state")
                        return
                    
                    # For single vendor, send ASAP to all vendors
                    for vendor in order["vendors"]:
                        vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                        if vendor_chat:
                            if order["order_type"] == "shopify":
                                msg = f"#{order['name'][-2:]} ASAP?"
                            else:
                                addr = order['customer']['address'].split(',')[0]
                                msg = f"*{addr}* ASAP?"
                            
                            # ASAP request buttons
                            await safe_send_message(
                                vendor_chat, 
                                msg,
                                restaurant_response_keyboard("ASAP", order_id, vendor)
                            )
                    
                    # Update MDG with ASAP status but keep time request buttons
                    order["requested_time"] = "ASAP"
                    vendors = order.get("vendors", [])
                    logger.info(f"Order {order_id} has vendors: {vendors} (count: {len(vendors)})")
                    
                    if len(vendors) > 1:
                        logger.info(f"MULTI-VENDOR detected: {vendors}")
                    else:
                        logger.info(f"SINGLE VENDOR detected: {vendors}")
                    
                    mdg_text = build_mdg_dispatch_text(order, show_details=order.get("mdg_expanded", False)) + f"\n\n⏰ Requested: ASAP"
                    await safe_edit_message(
                        DISPATCH_MAIN_CHAT_ID,
                        order["mdg_message_id"],
                        mdg_text,
                        mdg_time_request_keyboard(order_id)  # Keep same buttons
                    )
                    
                    # Clean up additional MDG messages
                    await cleanup_mdg_messages(order_id)
                
                elif action == "req_time":
                    order_id = data[1]
                    logger.info(f"Processing TIME request for order {order_id}")
                    order = STATE.get(order_id)
                    if not order:
                        logger.error(f"Order {order_id} not found in STATE")
                        return
                    
                    vendors = order.get("vendors", [])
                    logger.info(f"Order {order_id} has vendors: {vendors} (count: {len(vendors)})")
                    
                    # For single vendor, show TIME submenu per assignment
                    if len(vendors) <= 1:
                        logger.info(f"SINGLE VENDOR detected: {vendors}")
                        keyboard = mdg_time_submenu_keyboard(order_id)
                        
                        # If keyboard is None, no recent orders - show hour picker directly
                        if keyboard is None:
                            logger.info(f"No recent orders found - showing hour picker directly")
                            msg = await safe_send_message(
                                DISPATCH_MAIN_CHAT_ID,
                                "🕒 Select hour:",
                                exact_time_keyboard(order_id)
                            )
                            # Track additional message for cleanup
                            order["mdg_additional_messages"].append(msg.message_id)
                        else:
                            # Has recent orders - show them with EXACT TIME button
                            has_recent_orders = len(keyboard.inline_keyboard) > 1  # More than just EXACT TIME button
                            message_text = "Select scheduled order:" if has_recent_orders else "Request exact time:"
                            
                            msg = await safe_send_message(
                                DISPATCH_MAIN_CHAT_ID,
                                message_text,
                                keyboard
                            )
                            
                            # Track additional message for cleanup
                            order["mdg_additional_messages"].append(msg.message_id)
                    else:
                        # For multi-vendor, this shouldn't happen as they have vendor buttons
                        logger.warning(f"Unexpected req_time for multi-vendor order {order_id}")
                
                elif action == "time_plus":
                    order_id, minutes = data[1], int(data[2])
                    vendor = data[3] if len(data) > 3 else None
                    logger.info(f"Processing +{minutes} minutes for order {order_id}" + (f" (vendor: {vendor})" if vendor else ""))
                    order = STATE.get(order_id)
                    if not order:
                        return
                    
                    # Calculate new time
                    current_time = now()
                    new_time = current_time + timedelta(minutes=minutes)
                    requested_time = new_time.strftime("%H:%M")
                    
                    # Send time request to vendors
                    if vendor:
                        # Multi-vendor: send to specific vendor only
                        vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                        if vendor_chat:
                            if order["order_type"] == "shopify":
                                msg = f"#{order['name'][-2:]} at {requested_time}?"
                            else:
                                addr = order['customer']['address'].split(',')[0]
                                msg = f"*{addr}* at {requested_time}?"
                            
                            await safe_send_message(
                                vendor_chat,
                                msg,
                                restaurant_response_keyboard(requested_time, order_id, vendor)
                            )
                    else:
                        # Single vendor: send to all vendors
                        for vendor in order["vendors"]:
                            vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                            if vendor_chat:
                                if order["order_type"] == "shopify":
                                    msg = f"#{order['name'][-2:]} at {requested_time}?"
                                else:
                                    addr = order['customer']['address'].split(',')[0]
                                    msg = f"*{addr}* at {requested_time}?"
                                
                                await safe_send_message(
                                    vendor_chat,
                                    msg,
                                    restaurant_response_keyboard(requested_time, order_id, vendor)
                                )
                    
                    # Update MDG
                    order["requested_time"] = requested_time
                    mdg_text = build_mdg_dispatch_text(order, show_details=order.get("mdg_expanded", False)) + f"\n\n⏰ Requested: {requested_time}"
                    await safe_edit_message(
                        DISPATCH_MAIN_CHAT_ID,
                        order["mdg_message_id"],
                        mdg_text,
                        mdg_time_request_keyboard(order_id)
                    )
                    
                    # Clean up additional MDG messages
                    await cleanup_mdg_messages(order_id)
                
                elif action == "req_same":
                    order_id = data[1]
                    logger.info(f"Processing SAME TIME AS request for order {order_id}")
                    
                    recent = get_recent_orders_for_same_time(order_id)
                    if recent:
                        keyboard = same_time_keyboard(order_id)
                        msg = await safe_send_message(
                            DISPATCH_MAIN_CHAT_ID,
                            "🔗 Select order to match timing:",
                            keyboard
                        )
                        
                        # Track additional message for cleanup
                        order = STATE.get(order_id)
                        if order:
                            order["mdg_additional_messages"].append(msg.message_id)
                    else:
                        msg = await safe_send_message(
                            DISPATCH_MAIN_CHAT_ID,
                            "No recent orders found (last 1 hour)"
                        )
                        
                        # Track additional message for cleanup
                        order = STATE.get(order_id)
                        if order:
                            order["mdg_additional_messages"].append(msg.message_id)
                
                elif action == "order_ref":
                    # User clicked on a reference order from the list
                    order_id = data[1]
                    ref_order_id = data[2]
                    ref_time = data[3]
                    ref_vendors_str = data[4]
                    current_vendor = data[5] if len(data) > 5 else None
                    
                    logger.info(f"User selected reference order {ref_order_id} (time: {ref_time}) for order {order_id}")
                    
                    order = STATE.get(order_id)
                    ref_order = STATE.get(ref_order_id)
                    if not order or not ref_order:
                        logger.error(f"Order {order_id} or reference order {ref_order_id} not found")
                        return
                    
                    # Build Same / +5 / +10 / +15 / +20 keyboard
                    keyboard = order_reference_options_keyboard(
                        order_id, 
                        ref_order_id, 
                        ref_time, 
                        ref_vendors_str, 
                        current_vendor
                    )
                    
                    # Show the options below the selected order
                    ref_num = ref_order['name'][-2:] if len(ref_order['name']) >= 2 else ref_order['name']
                    msg = await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        f"⏰ Reference time: {ref_time} (#{ref_num})\nSelect option:",
                        keyboard
                    )
                    
                    # Track for cleanup
                    order["mdg_additional_messages"].append(msg.message_id)
                
                elif action == "time_same":
                    # User clicked "Same" - send "together with" message to current order's vendors
                    order_id = data[1]
                    ref_order_id = data[2]
                    ref_time = data[3]
                    current_vendor_shortcut = data[4] if len(data) > 4 else None
                    
                    # Convert shortcut to full vendor name if provided
                    current_vendor = shortcut_to_vendor(current_vendor_shortcut) if current_vendor_shortcut else None
                    
                    logger.info(f"Processing SAME time request for order {order_id} with reference {ref_order_id}")
                    
                    order = STATE.get(order_id)
                    ref_order = STATE.get(ref_order_id)
                    if not order or not ref_order:
                        logger.error(f"Order {order_id} or reference order {ref_order_id} not found")
                        return
                    
                    order_num = order['name'][-2:] if len(order['name']) >= 2 else order['name']
                    ref_num = ref_order['name'][-2:] if len(ref_order['name']) >= 2 else ref_order['name']
                    
                    # Determine which vendor(s) to send to - CURRENT order's vendors, not reference order's
                    if current_vendor:
                        # Multi-vendor: send only to specified vendor
                        vendors_to_notify = [current_vendor]
                    else:
                        # Single vendor: send to ALL vendors of current order
                        vendors_to_notify = order.get("vendors", [])
                    
                    # Send "together with" message to each vendor
                    for vendor in vendors_to_notify:
                        vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                        if vendor_chat:
                            msg = f"Can you also prepare 🔖 #{order_num} at {ref_time} together with 🔖 #{ref_num}?"
                            
                            await safe_send_message(
                                vendor_chat,
                                msg,
                                restaurant_response_keyboard(ref_time, order_id, vendor)
                            )
                            
                            logger.info(f"Sent 'together with' request to {vendor} for order {order_id}")
                        else:
                            logger.warning(f"Vendor {vendor} not found in VENDOR_GROUP_MAP")
                    
                    # Update MDG
                    order["requested_time"] = ref_time
                    mdg_text = build_mdg_dispatch_text(order, show_details=order.get("mdg_expanded", False)) + f"\n\n⏰ Requested: {ref_time}"
                    await safe_edit_message(
                        DISPATCH_MAIN_CHAT_ID,
                        order["mdg_message_id"],
                        mdg_text,
                        mdg_time_request_keyboard(order_id)
                    )
                    
                    # Clean up additional MDG messages
                    await cleanup_mdg_messages(order_id)
                    
                    # Send confirmation to MDG
                    vendor_names = ", ".join([RESTAURANT_SHORTCUTS.get(v, v) for v in vendors_to_notify])
                    await send_status_message(
                        DISPATCH_MAIN_CHAT_ID,
                        f"✅ Time request ({ref_time}) sent to {vendor_names}",
                        auto_delete_after=20
                    )
                    
                    # Mark order for grouping after vendor confirms
                    order["grouped_via"] = "same"
                    order["group_reference_order"] = ref_order_id
                
                elif action == "show_group_menu":
                    # User clicked "Group" button - show time adjustment menu (±3m/±5m)
                    order_id = data[1]
                    ref_order_id = data[2]
                    ref_time = data[3]
                    current_vendor = data[4] if len(data) > 4 else None
                    
                    logger.info(f"Showing group menu for order {order_id} with reference {ref_order_id}")
                    
                    order = STATE.get(order_id)
                    ref_order = STATE.get(ref_order_id)
                    if not order or not ref_order:
                        logger.error(f"Order {order_id} or reference order {ref_order_id} not found")
                        return
                    
                    # Delete the previous message (with "Group" button)
                    await safe_delete_message(DISPATCH_MAIN_CHAT_ID, cq["message"]["message_id"])
                    
                    # Show time adjustment menu
                    ref_num = ref_order['name'][-2:] if len(ref_order['name']) >= 2 else ref_order['name']
                    keyboard = group_time_adjustment_keyboard(order_id, ref_order_id, ref_time, current_vendor)
                    
                    msg = await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        f"⏰ Adjust time for grouping with #{ref_num} ({ref_time}):",
                        keyboard
                    )
                    
                    # Track for cleanup
                    order["mdg_additional_messages"].append(msg.message_id)
                
                elif action == "time_group":
                    # User selected adjusted time from group menu (±3m/±5m)
                    order_id = data[1]
                    adjusted_time = data[2]
                    ref_order_id = data[3]
                    current_vendor_shortcut = data[4] if len(data) > 4 else None
                    
                    # Convert shortcut to full vendor name if provided
                    current_vendor = shortcut_to_vendor(current_vendor_shortcut) if current_vendor_shortcut else None
                    
                    logger.info(f"Processing GROUP time request ({adjusted_time}) for order {order_id} with reference {ref_order_id}")
                    
                    order = STATE.get(order_id)
                    if not order:
                        logger.error(f"Order {order_id} not found in STATE")
                        return
                    
                    order_num = order['name'][-2:] if len(order['name']) >= 2 else order['name']
                    
                    # Determine which vendor(s) to send to - CURRENT order's vendors
                    if current_vendor:
                        vendors_to_notify = [current_vendor]
                    else:
                        vendors_to_notify = order.get("vendors", [])
                    
                    # Send time request to vendor(s)
                    for vendor in vendors_to_notify:
                        vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                        if vendor_chat:
                            msg = f"Can you prepare 🔖 #{order_num} at {adjusted_time}?"
                            
                            await safe_send_message(
                                vendor_chat,
                                msg,
                                restaurant_response_keyboard(adjusted_time, order_id, vendor)
                            )
                            
                            logger.info(f"Sent group time request ({adjusted_time}) to {vendor} for order {order_id}")
                        else:
                            logger.warning(f"Vendor {vendor} not found in VENDOR_GROUP_MAP")
                    
                    # Update MDG
                    order["requested_time"] = adjusted_time
                    mdg_text = build_mdg_dispatch_text(order, show_details=order.get("mdg_expanded", False)) + f"\n\n⏰ Requested: {adjusted_time}"
                    await safe_edit_message(
                        DISPATCH_MAIN_CHAT_ID,
                        order["mdg_message_id"],
                        mdg_text,
                        mdg_time_request_keyboard(order_id)
                    )
                    
                    # Clean up additional MDG messages
                    await cleanup_mdg_messages(order_id)
                    
                    # Send confirmation to MDG
                    vendor_names = ", ".join([RESTAURANT_SHORTCUTS.get(v, v) for v in vendors_to_notify])
                    await send_status_message(
                        DISPATCH_MAIN_CHAT_ID,
                        f"✅ Time request ({adjusted_time}) sent to {vendor_names}",
                        auto_delete_after=20
                    )
                    
                    # Mark order for grouping after vendor confirms
                    order["grouped_via"] = "group"
                    order["group_reference_order"] = ref_order_id
                
                elif action == "time_relative":
                    # User clicked +5, +10, +15, or +20
                    order_id = data[1]
                    requested_time = data[2]
                    ref_order_id = data[3]
                    current_vendor_shortcut = data[4] if len(data) > 4 else None
                    
                    # Convert shortcut to full vendor name if provided
                    current_vendor = shortcut_to_vendor(current_vendor_shortcut) if current_vendor_shortcut else None
                    
                    logger.info(f"Processing RELATIVE time request ({requested_time}) for order {order_id}")
                    
                    order = STATE.get(order_id)
                    if not order:
                        logger.error(f"Order {order_id} not found in STATE")
                        return
                    
                    order_num = order['name'][-2:] if len(order['name']) >= 2 else order['name']
                    
                    # Determine which vendor(s) to send to - CURRENT order's vendors, not reference order's
                    if current_vendor:
                        # Multi-vendor: send only to specified vendor
                        vendors_to_notify = [current_vendor]
                    else:
                        # Single vendor: send to ALL vendors of current order
                        vendors_to_notify = order.get("vendors", [])
                    
                    # Send time request to each vendor
                    for vendor in vendors_to_notify:
                        vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                        if vendor_chat:
                            msg = f"Can you prepare 🔖 #{order_num} at {requested_time}?"
                            
                            await safe_send_message(
                                vendor_chat,
                                msg,
                                restaurant_response_keyboard(requested_time, order_id, vendor)
                            )
                            
                            logger.info(f"Sent time request ({requested_time}) to {vendor} for order {order_id}")
                        else:
                            logger.warning(f"Vendor {vendor} not found in VENDOR_GROUP_MAP")
                    
                    # Update MDG
                    order["requested_time"] = requested_time
                    mdg_text = build_mdg_dispatch_text(order, show_details=order.get("mdg_expanded", False)) + f"\n\n⏰ Requested: {requested_time}"
                    await safe_edit_message(
                        DISPATCH_MAIN_CHAT_ID,
                        order["mdg_message_id"],
                        mdg_text,
                        mdg_time_request_keyboard(order_id)
                    )
                    
                    # Clean up additional MDG messages
                    await cleanup_mdg_messages(order_id)
                    
                    # Send confirmation to MDG
                    vendor_names = ", ".join([RESTAURANT_SHORTCUTS.get(v, v) for v in vendors_to_notify])
                    await send_status_message(
                        DISPATCH_MAIN_CHAT_ID,
                        f"✅ Time request ({requested_time}) sent to {vendor_names}",
                        auto_delete_after=20
                    )
                
                elif action == "no_recent":
                    # Handle click on disabled "Same as" button
                    msg = await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        "No recent confirmed orders available to match timing with"
                    )
                    
                    # Track additional message for cleanup
                    order_id = data[1] if len(data) > 1 else None
                    if order_id:
                        order = STATE.get(order_id)
                        if order:
                            order["mdg_additional_messages"].append(msg.message_id)
                
                elif action == "req_exact":
                    order_id = data[1]
                    vendor = data[2] if len(data) > 2 else None  # Extract vendor if provided
                    logger.info(f"Processing REQUEST EXACT TIME for order {order_id}, vendor: {vendor}")
                    
                    # Show hour picker for exact time
                    msg = await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        "🕒 Select hour:",
                        exact_time_keyboard(order_id, vendor)
                    )
                    
                    # Track additional message for cleanup
                    order = STATE.get(order_id)
                    if order:
                        order["mdg_additional_messages"].append(msg.message_id)
                
                elif action == "same_selected":
                    order_id, reference_order_id = data[1], data[2]
                    order = STATE.get(order_id)
                    reference_order = STATE.get(reference_order_id)
                    
                    if not order or not reference_order:
                        return
                    
                    # Get time from reference order
                    reference_time = reference_order.get("confirmed_time") or reference_order.get("requested_time", "ASAP")
                    
                    # Send same time request to vendors
                    for vendor in order["vendors"]:
                        vendor_chat = VENDOR_GROUP_MAP.get(vendor)
                        if vendor_chat:
                            # Check if same restaurant as reference order
                            if vendor in reference_order.get("vendors", []):
                                # Same restaurant - special message
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
                            
                            await safe_send_message(
                                vendor_chat,
                                msg,
                                restaurant_response_keyboard(reference_time, order_id, vendor)
                            )
                    
                    # Update MDG
                    order["requested_time"] = reference_time
                    mdg_text = build_mdg_dispatch_text(order, show_details=order.get("mdg_expanded", False)) + f"\n\n⏰ Requested: {reference_time} (same as {reference_order.get('name', 'other order')})"
                    await safe_edit_message(
                        DISPATCH_MAIN_CHAT_ID,
                        order["mdg_message_id"],
                        mdg_text,
                        mdg_time_request_keyboard(order_id)
                    )
                    
                    # Clean up additional MDG messages
                    await cleanup_mdg_messages(order_id)
                
                # EXACT TIME ACTIONS
                elif action == "exact_hour":
                    order_id, hour = data[1], data[2]
                    vendor = data[3] if len(data) > 3 else None  # Extract vendor if provided
                    logger.info(f"Processing exact hour {hour} for order {order_id}, vendor: {vendor}")
                    
                    # Edit the current message to show minute picker
                    chat_id = cq["message"]["chat"]["id"]
                    message_id = cq["message"]["message_id"]
                    
                    await safe_edit_message(
                        chat_id,
                        message_id,
                        f"🕒 Select exact time (hour {hour}):",
                        exact_hour_keyboard(order_id, int(hour), vendor)
                    )
                
                elif action == "exact_selected":
                    order_id, selected_time = data[1], data[2]
                    vendor = data[3] if len(data) > 3 else None  # Extract vendor if provided
                    order = STATE.get(order_id)
                    if not order:
                        return
                    
                    # Determine which vendors to send to
                    if vendor:
                        # Single vendor specified - send only to that vendor
                        target_vendors = [vendor]
                        logger.info(f"Sending time request to single vendor: {vendor}")
                    else:
                        # No vendor specified - send to all vendors (single-vendor orders)
                        target_vendors = order["vendors"]
                        logger.info(f"Sending time request to all vendors: {target_vendors}")
                    
                    # Send time request to target vendors
                    for v in target_vendors:
                        vendor_chat = VENDOR_GROUP_MAP.get(v)
                        if vendor_chat:
                            if order["order_type"] == "shopify":
                                msg = f"#{order['name'][-2:]} at {selected_time}?"
                            else:
                                addr = order['customer']['address'].split(',')[0]
                                msg = f"*{addr}* at {selected_time}?"
                            
                            await safe_send_message(
                                vendor_chat,
                                msg,
                                restaurant_response_keyboard(selected_time, order_id, v)
                            )
                    
                    # Update MDG
                    order["requested_time"] = selected_time
                    mdg_text = build_mdg_dispatch_text(order, show_details=order.get("mdg_expanded", False)) + f"\n\n⏰ Requested: {selected_time}"
                    await safe_edit_message(
                        DISPATCH_MAIN_CHAT_ID,
                        order["mdg_message_id"],
                        mdg_text,
                        mdg_time_request_keyboard(order_id)
                    )
                    
                    # Delete the time picker message
                    chat_id = cq["message"]["chat"]["id"]
                    message_id = cq["message"]["message_id"]
                    await safe_delete_message(chat_id, message_id)
                    
                    # Clean up additional MDG messages
                    await cleanup_mdg_messages(order_id)
                
                elif action == "exact_back_hours":
                    order_id = data[1]
                    vendor = data[2] if len(data) > 2 else None  # Extract vendor if provided
                    logger.info(f"Going back to hours for order {order_id}, vendor: {vendor}")
                    
                    # Edit current message back to hour picker
                    chat_id = cq["message"]["chat"]["id"]
                    message_id = cq["message"]["message_id"]
                    
                    await safe_edit_message(
                        chat_id,
                        message_id,
                        "🕒 Select hour:",
                        exact_time_keyboard(order_id, vendor)
                    )
                
                elif action == "exact_hide":
                    order_id = data[1]
                    logger.info(f"Hiding exact time picker for order {order_id}")
                    
                    # Delete the exact time picker message
                    chat_id = cq["message"]["chat"]["id"]
                    message_id = cq["message"]["message_id"]
                    
                    await safe_delete_message(chat_id, message_id)
                
                # VENDOR RESPONSES
                elif action == "toggle":
                    order_id, vendor = data[1], data[2]
                    order = STATE.get(order_id)
                    if not order:
                        logger.warning(f"Order {order_id} not found in state")
                        return
                    
                    expanded = not order["vendor_expanded"].get(vendor, False)
                    order["vendor_expanded"][vendor] = expanded
                    logger.info(f"Toggling vendor message for {vendor}, expanded: {expanded}")
                    
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
                    order = STATE.get(order_id)
                    if order:
                        # Track confirmed time per vendor
                        confirmed_time = order.get("requested_time", "ASAP")
                        if "confirmed_times" not in order:
                            order["confirmed_times"] = {}
                        order["confirmed_times"][vendor] = confirmed_time
                        order["confirmed_time"] = confirmed_time  # Keep for backward compatibility
                        order["confirmed_by"] = vendor
                        
                        logger.info(f"DEBUG: Updated STATE for {order_id} - confirmed_times now: {order['confirmed_times']}")
                        
                        # Get order number for display
                        order_num = order['name'][-2:] if len(order['name']) >= 2 else order['name']
                    
                    # Post status to MDG
                    status_msg = f"{vendor} replied: {confirmed_time} for 🔖 #{order_num} works 👍"
                    await send_status_message(DISPATCH_MAIN_CHAT_ID, status_msg, auto_delete_after=20)
                    
                    # Check for pending grouping - if all vendors confirmed, create/join group
                    if check_all_vendors_confirmed(order_id):
                        if order.get("grouped_via") and order.get("group_reference_order"):
                            # This order was marked for grouping via BTN-SAME or BTN-GROUP
                            ref_order_id = order["group_reference_order"]
                            logger.info(f"Auto-grouping order {order_id} with reference {ref_order_id} (via {order['grouped_via']})")
                            create_or_join_group(order_id, ref_order_id)
                            
                            # Clear grouping markers
                            order["grouped_via"] = None
                            order["group_reference_order"] = None
                    
                    # Check if all vendors confirmed - show assignment buttons
                    # CRITICAL: Only show buttons if order NOT already assigned
                    # This prevents duplicate assignment buttons appearing after delay confirmations
                    logger.info(f"DEBUG: Checking if all vendors confirmed for order {order_id}")
                    if check_all_vendors_confirmed(order_id):
                        if order.get("status") != "assigned":
                            # Order ready for assignment - show assignment buttons
                            logger.info(f"DEBUG: All vendors confirmed! Sending assignment buttons")
                            assignment_msg = await safe_send_message(
                                DISPATCH_MAIN_CHAT_ID,
                                build_assignment_confirmation_message(order),
                                mdg_assignment_keyboard(order_id)
                            )
                            # Track this message for potential cleanup
                            if "mdg_additional_messages" not in order:
                                order["mdg_additional_messages"] = []
                            order["mdg_additional_messages"].append(assignment_msg.message_id)
                        else:
                            # Order already assigned - skip duplicate buttons
                            # This happens when courier requests delay and vendor confirms new time
                            logger.info(f"DEBUG: All vendors confirmed but order already assigned - skipping assignment buttons")
                    else:
                        logger.info(f"DEBUG: Not all vendors confirmed yet for order {order_id}")
                
                elif action == "later":
                    order_id, vendor = data[1], data[2]
                    order = STATE.get(order_id)
                    requested = order.get("requested_time", "ASAP") if order else "ASAP"
                    
                    # Show time picker for vendor response
                    await safe_send_message(
                        VENDOR_GROUP_MAP[vendor],
                        f"Select later time:",
                        time_picker_keyboard(order_id, "later_time", requested, vendor)
                    )
                
                elif action == "later_time":
                    # Extract vendor SHORTCUT from callback data (format: later_time|order_id|time|vendor_shortcut)
                    order_id, selected_time, vendor_shortcut = data[1], data[2], data[3]
                    
                    # Convert shortcut back to full vendor name
                    vendor = shortcut_to_vendor(vendor_shortcut)
                    if not vendor:
                        logger.error(f"Could not convert vendor shortcut '{vendor_shortcut}' to full name")
                        return
                    
                    order = STATE.get(order_id)
                    if order:
                        # Track confirmed time per vendor
                        if "confirmed_times" not in order:
                            order["confirmed_times"] = {}
                        
                        # Store time for the correct vendor
                        order["confirmed_times"][vendor] = selected_time
                        order["confirmed_time"] = selected_time  # Keep for backward compatibility
                        
                        # Get order number for display
                        order_num = order['name'][-2:] if len(order['name']) >= 2 else order['name']
                        
                        status_msg = f"{vendor} replied: Will prepare 🔖 #{order_num} later at {selected_time} 👍"
                        await send_status_message(DISPATCH_MAIN_CHAT_ID, status_msg, auto_delete_after=20)
                        
                        logger.info(f"DEBUG: Updated STATE for {order_id} - confirmed_times now: {order['confirmed_times']}")
                        
                        # Check for pending grouping - if all vendors confirmed, create/join group
                        if check_all_vendors_confirmed(order_id):
                            if order.get("grouped_via") and order.get("group_reference_order"):
                                # This order was marked for grouping via BTN-SAME or BTN-GROUP
                                ref_order_id = order["group_reference_order"]
                                logger.info(f"Auto-grouping order {order_id} with reference {ref_order_id} (via {order['grouped_via']})")
                                create_or_join_group(order_id, ref_order_id)
                                
                                # Clear grouping markers
                                order["grouped_via"] = None
                                order["group_reference_order"] = None
                        
                        # Check if all vendors confirmed - show assignment buttons
                        logger.info(f"DEBUG: Checking if all vendors confirmed for order {order_id}")
                        if check_all_vendors_confirmed(order_id):
                            logger.info(f"DEBUG: All vendors confirmed! Sending assignment buttons")
                            assignment_msg = await safe_send_message(
                                DISPATCH_MAIN_CHAT_ID,
                                build_assignment_confirmation_message(order),
                                mdg_assignment_keyboard(order_id)
                            )
                            # Track this message for potential cleanup
                            if "mdg_additional_messages" not in order:
                                order["mdg_additional_messages"] = []
                            order["mdg_additional_messages"].append(assignment_msg.message_id)
                        else:
                            logger.info(f"DEBUG: Not all vendors confirmed yet for order {order_id}")
                    
                    # Delete the time picker message (cleanup)
                    chat_id = cq["message"]["chat"]["id"]
                    message_id = cq["message"]["message_id"]
                    await safe_delete_message(chat_id, message_id)
                
                elif action == "prepare":
                    order_id, vendor = data[1], data[2]
                    
                    # Show time picker for vendor response
                    await safe_send_message(
                        VENDOR_GROUP_MAP[vendor],
                        f"Select preparation time:",
                        time_picker_keyboard(order_id, "prepare_time", None, vendor)
                    )
                
                elif action == "prepare_time":
                    # Extract vendor SHORTCUT from callback data (format: prepare_time|order_id|time|vendor_shortcut)
                    order_id, selected_time, vendor_shortcut = data[1], data[2], data[3]
                    
                    # Convert shortcut back to full vendor name
                    vendor = shortcut_to_vendor(vendor_shortcut)
                    if not vendor:
                        logger.error(f"Could not convert vendor shortcut '{vendor_shortcut}' to full name")
                        return
                    
                    order = STATE.get(order_id)
                    if order:
                        # Track confirmed time per vendor
                        if "confirmed_times" not in order:
                            order["confirmed_times"] = {}
                        
                        # Store time for the correct vendor
                        order["confirmed_times"][vendor] = selected_time
                        order["confirmed_time"] = selected_time  # Keep for backward compatibility
                        
                        # Get order number for display
                        order_num = order['name'][-2:] if len(order['name']) >= 2 else order['name']
                        
                        status_msg = f"{vendor} replied: Will prepare 🔖 #{order_num} at {selected_time} 👍"
                        await send_status_message(DISPATCH_MAIN_CHAT_ID, status_msg, auto_delete_after=20)
                        
                        # Delete the time picker message (cleanup)
                        chat_id = cq["message"]["chat"]["id"]
                        message_id = cq["message"]["message_id"]
                        await safe_delete_message(chat_id, message_id)
                        
                        logger.info(f"DEBUG: Updated STATE for {order_id} - confirmed_times now: {order['confirmed_times']}")
                        
                        # Check for pending grouping - if all vendors confirmed, create/join group
                        if check_all_vendors_confirmed(order_id):
                            if order.get("grouped_via") and order.get("group_reference_order"):
                                # This order was marked for grouping via BTN-SAME or BTN-GROUP
                                ref_order_id = order["group_reference_order"]
                                logger.info(f"Auto-grouping order {order_id} with reference {ref_order_id} (via {order['grouped_via']})")
                                create_or_join_group(order_id, ref_order_id)
                                
                                # Clear grouping markers
                                order["grouped_via"] = None
                                order["group_reference_order"] = None
                        
                        # Check if all vendors confirmed - show assignment buttons
                        logger.info(f"DEBUG: Checking if all vendors confirmed for order {order_id}")
                        if check_all_vendors_confirmed(order_id):
                            logger.info(f"DEBUG: All vendors confirmed! Sending assignment buttons")
                            assignment_msg = await safe_send_message(
                                DISPATCH_MAIN_CHAT_ID,
                                build_assignment_confirmation_message(order),
                                mdg_assignment_keyboard(order_id)
                            )
                            # Track this message for potential cleanup
                            if "mdg_additional_messages" not in order:
                                order["mdg_additional_messages"] = []
                            order["mdg_additional_messages"].append(assignment_msg.message_id)
                        else:
                            logger.info(f"DEBUG: Not all vendors confirmed yet for order {order_id}")
                
                elif action == "wrong":
                    order_id, vendor = data[1], data[2]
                    # Show "Something is wrong" submenu
                    wrong_buttons = [
                        [InlineKeyboardButton("Ordered product(s) not available", callback_data=f"wrong_unavailable|{order_id}|{vendor}")],
                        [InlineKeyboardButton("Order is canceled", callback_data=f"wrong_canceled|{order_id}|{vendor}")],
                        [InlineKeyboardButton("Technical issue", callback_data=f"wrong_technical|{order_id}|{vendor}")],
                        [InlineKeyboardButton("Something else", callback_data=f"wrong_other|{order_id}|{vendor}")],
                        [InlineKeyboardButton("We have a delay", callback_data=f"wrong_delay|{order_id}|{vendor}")]
                    ]
                    
                    await safe_send_message(
                        VENDOR_GROUP_MAP[vendor],
                        "What's wrong?",
                        InlineKeyboardMarkup(wrong_buttons)
                    )
                
                elif action == "wrong_unavailable":
                    order_id, vendor = data[1], data[2]
                    order = STATE.get(order_id)
                    order_num = order['name'][-2:] if order and len(order.get('name', '')) >= 2 else order.get('name', '') if order else order_id
                    
                    # ST-CALL format from CHEAT-SHEET
                    msg = f"{vendor}: Please call customer for 🔖 #{order_num} (replacement/refund)"
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, msg)
                
                elif action == "wrong_canceled":
                    order_id, vendor = data[1], data[2]
                    order = STATE.get(order_id)
                    order_num = order['name'][-2:] if order and len(order.get('name', '')) >= 2 else order.get('name', '') if order else order_id
                    
                    # ST-CANCEL format from CHEAT-SHEET
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"{vendor}: Order 🔖 #{order_num} is canceled")
                
                elif action in ["wrong_technical", "wrong_other"]:
                    order_id, vendor = data[1], data[2]
                    # Set state to wait for vendor's issue description
                    order = STATE.get(order_id)
                    if order:
                        order["waiting_for_issue_description"] = vendor
                    
                    # Send instruction to vendor group (NOT to MDG)
                    await safe_send_message(
                        VENDOR_GROUP_MAP[vendor],
                        "Please write a message describing the issue and we will forward it to dishbee."
                    )
                
                elif action == "wrong_delay":
                    order_id, vendor = data[1], data[2]
                    order = STATE.get(order_id)
                    
                    if order:
                        agreed_time = order.get("confirmed_time") or order.get("requested_time")
                        
                        # Always show delay time picker - no fallback without time
                        if agreed_time and agreed_time != "ASAP":
                            try:
                                hour, minute = map(int, agreed_time.split(':'))
                                base_time = now().replace(hour=hour, minute=minute)
                            except:
                                base_time = now()
                        else:
                            base_time = now()
                        
                        delay_intervals = []
                        for minutes in [5, 10, 15, 20]:
                            time_option = base_time + timedelta(minutes=minutes)
                            delay_intervals.append(time_option.strftime("%H:%M"))
                        
                        delay_buttons = []
                        for i in range(0, len(delay_intervals), 2):
                            row = [InlineKeyboardButton(delay_intervals[i], callback_data=f"delay_time|{order_id}|{vendor}|{delay_intervals[i]}")]
                            if i + 1 < len(delay_intervals):
                                row.append(InlineKeyboardButton(delay_intervals[i + 1], callback_data=f"delay_time|{order_id}|{vendor}|{delay_intervals[i + 1]}"))
                            delay_buttons.append(row)
                        
                        await safe_send_message(
                            VENDOR_GROUP_MAP[vendor],
                            "Select delay time:",
                            InlineKeyboardMarkup(delay_buttons)
                        )
                
                elif action == "delay_time":
                    order_id, vendor, delay_time = data[1], data[2], data[3]
                    order = STATE.get(order_id)
                    order_num = order['name'][-2:] if order and len(order.get('name', '')) >= 2 else order.get('name', '') if order else order_id
                    
                    # ST-DELAY format from CHEAT-SHEET
                    await send_status_message(DISPATCH_MAIN_CHAT_ID, f"{vendor}: We have a delay for 🔖 #{order_num} - new time {delay_time}", auto_delete_after=20)
                    
                    # Delete the delay time picker message (cleanup)
                    chat_id = cq["message"]["chat"]["id"]
                    message_id = cq["message"]["message_id"]
                    await safe_delete_message(chat_id, message_id)
                
                # VENDOR EXACT TIME SELECTION
                elif action == "vendor_exact_time":
                    # Extract vendor SHORTCUT from callback (format: vendor_exact_time|order_id|vendor_shortcut|action)
                    order_id, vendor_shortcut, original_action = data[1], data[2], data[3]
                    
                    # Convert shortcut back to full vendor name
                    vendor = shortcut_to_vendor(vendor_shortcut)
                    if not vendor:
                        logger.error(f"Could not convert vendor shortcut '{vendor_shortcut}' to full name")
                        return
                    
                    logger.info(f"Vendor {vendor} requesting exact time for order {order_id} (action: {original_action})")
                    
                    # Get the message that needs to be edited (time picker message)
                    chat_id = cq["message"]["chat"]["id"]
                    message_id = cq["message"]["message_id"]
                    
                    # Show hour picker (pass vendor_shortcut to maintain consistency)
                    await safe_edit_message(
                        chat_id,
                        message_id,
                        "🕒 Select hour:",
                        vendor_exact_time_keyboard(order_id, vendor_shortcut, original_action)
                    )
                
                elif action == "vendor_exact_hour":
                    order_id, hour, vendor_short, original_action = data[1], data[2], data[3], data[4]
                    # Decode vendor shortcut
                    vendor = shortcut_to_vendor(vendor_short)
                    if not vendor:
                        logger.error(f"Could not convert vendor shortcut '{vendor_short}' to full name")
                        return
                    
                    logger.info(f"Vendor {vendor} selected hour {hour} for order {order_id}")
                    
                    # Edit message to show minute picker
                    chat_id = cq["message"]["chat"]["id"]
                    message_id = cq["message"]["message_id"]
                    
                    await safe_edit_message(
                        chat_id,
                        message_id,
                        f"🕒 Select exact time (hour {hour}):",
                        vendor_exact_hour_keyboard(order_id, int(hour), vendor, original_action)
                    )
                
                elif action == "vendor_exact_selected":
                    order_id, selected_time, vendor_short, original_action = data[1], data[2], data[3], data[4]
                    # Decode vendor shortcut
                    vendor = shortcut_to_vendor(vendor_short)
                    if not vendor:
                        logger.error(f"Could not convert vendor shortcut '{vendor_short}' to full name")
                        return
                    
                    logger.info(f"Vendor {vendor} selected exact time {selected_time} for order {order_id} (action: {original_action})")
                    
                    order = STATE.get(order_id)
                    if order:
                        # Track confirmed time per vendor
                        if "confirmed_times" not in order:
                            order["confirmed_times"] = {}
                        
                        # Store time for the correct vendor
                        order["confirmed_times"][vendor] = selected_time
                        order["confirmed_time"] = selected_time  # Keep for backward compatibility
                        
                        # Get order number for display
                        order_num = order['name'][-2:] if len(order['name']) >= 2 else order['name']
                        
                        # Send appropriate status message to MDG based on original action
                        if original_action == "later_time":
                            status_msg = f"{vendor} replied: Will prepare 🔖 #{order_num} later at {selected_time} 👍"
                        elif original_action == "prepare_time":
                            status_msg = f"{vendor} replied: Will prepare 🔖 #{order_num} at {selected_time} 👍"
                        elif original_action == "delay_time":
                            status_msg = f"{vendor}: We have a delay for 🔖 #{order_num} - new time {selected_time}"
                        else:
                            status_msg = f"{vendor} confirmed: {selected_time} for 🔖 #{order_num}"
                        
                        await send_status_message(DISPATCH_MAIN_CHAT_ID, status_msg, auto_delete_after=20)
                        
                        logger.info(f"DEBUG: Updated STATE for {order_id} - confirmed_times now: {order['confirmed_times']}")
                        
                        # Check if all vendors confirmed - show assignment buttons
                        logger.info(f"DEBUG: Checking if all vendors confirmed for order {order_id}")
                        if check_all_vendors_confirmed(order_id):
                            if order.get("status") != "assigned":
                                logger.info(f"DEBUG: All vendors confirmed! Sending assignment buttons")
                                assignment_msg = await safe_send_message(
                                    DISPATCH_MAIN_CHAT_ID,
                                    build_assignment_confirmation_message(order),
                                    mdg_assignment_keyboard(order_id)
                                )
                                # Track this message for potential cleanup
                                if "mdg_additional_messages" not in order:
                                    order["mdg_additional_messages"] = []
                                order["mdg_additional_messages"].append(assignment_msg.message_id)
                            else:
                                logger.info(f"DEBUG: All vendors confirmed but order already assigned - skipping assignment buttons")
                        else:
                            logger.info(f"DEBUG: Not all vendors confirmed yet for order {order_id}")
                    
                    # Delete the time picker message (cleanup)
                    chat_id = cq["message"]["chat"]["id"]
                    message_id = cq["message"]["message_id"]
                    await safe_delete_message(chat_id, message_id)
                
                elif action == "vendor_exact_back":
                    order_id, vendor_short, original_action = data[1], data[2], data[3]
                    # Decode vendor shortcut
                    vendor = shortcut_to_vendor(vendor_short)
                    if not vendor:
                        logger.error(f"Could not convert vendor shortcut '{vendor_short}' to full name")
                        return
                    
                    logger.info(f"Vendor {vendor} going back to hour selection for order {order_id}")
                    
                    # Edit message back to hour picker (pass vendor_shortcut to maintain consistency)
                    chat_id = cq["message"]["chat"]["id"]
                    message_id = cq["message"]["message_id"]
                    
                    await safe_edit_message(
                        chat_id,
                        message_id,
                        "🕒 Select hour:",
                        vendor_exact_time_keyboard(order_id, vendor_short, original_action)
                    )
                
                # ASSIGNMENT ACTIONS
                elif action == "assign_myself":
                    """
                    Handle "Assign to myself" button click.
                    
                    Flow:
                    1. User clicks button in MDG
                    2. Extract user_id from callback query
                    3. Send order details to user's private chat (via UPC module)
                    4. Update MDG message to show assignment status
                    5. Mark order as "assigned" in STATE
                    
                    No cleanup: Assignment confirmation message stays in MDG permanently
                    """
                    order_id = data[1]
                    user_id = cq["from"]["id"]
                    logger.info(f"User {user_id} assigning order {order_id} to themselves")
                    
                    # Send assignment to user's private chat
                    await upc.send_assignment_to_private_chat(order_id, user_id)
                    
                    # Update MDG with assignment info
                    await upc.update_mdg_with_assignment(order_id, user_id)
                
                elif action == "assign_to_menu":
                    """
                    Handle "Assign to..." button click - shows courier selection menu.
                    
                    Flow:
                    1. User clicks "Assign to..." in MDG
                    2. Query Telegram API for live MDG administrators
                    3. Build inline keyboard with one button per courier
                    4. Send "Select courier:" message with buttons
                    5. Track message for cleanup after selection
                    
                    Live detection ensures menu shows current group members.
                    Requirement: All couriers must be promoted to admin in MDG.
                    """
                    order_id = data[1]
                    logger.info(f"Showing courier selection menu for order {order_id}")
                    
                    # Show courier selection menu (async call to get live MDG members)
                    keyboard = await courier_selection_keyboard(order_id, bot)
                    menu_msg = await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        "Select courier:",
                        keyboard
                    )
                    
                    # Track this message for cleanup
                    order = STATE.get(order_id)
                    if order:
                        if "mdg_additional_messages" not in order:
                            order["mdg_additional_messages"] = []
                        order["mdg_additional_messages"].append(menu_msg.message_id)
                
                elif action == "assign_to_user":
                    """
                    Handle courier selection from "Assign to..." menu.
                    
                    Flow:
                    1. Dispatcher selects courier from menu
                    2. Extract target_user_id from callback data
                    3. Send order details to selected courier's private chat
                    4. Update MDG message to show assignment status
                    5. Mark order as "assigned" in STATE
                    """
                    order_id, target_user_id = data[1], int(data[2])
                    logger.info(f"Assigning order {order_id} to user {target_user_id}")
                    
                    # Send assignment to selected user's private chat
                    await upc.send_assignment_to_private_chat(order_id, target_user_id)
                    
                    # Update MDG with assignment info
                    await upc.update_mdg_with_assignment(order_id, target_user_id)
                
                # UPC CTA ACTIONS
                elif action == "delay_order":
                    """
                    Courier requests delay from private chat.
                    
                    Shows time picker with +5/+10/+15/+20 minute options based on
                    latest confirmed time. Courier selects new time, which triggers
                    delay request to all vendors.
                    
                    Critical: When vendors confirm new time, assignment buttons are
                    NOT shown again because order["status"] == "assigned".
                    """
                    order_id = data[1]
                    user_id = cq["from"]["id"]
                    logger.info(f"User {user_id} requesting delay for order {order_id}")
                    
                    # Show delay time options
                    await upc.show_delay_options(order_id, user_id)
                
                elif action == "delay_selected":
                    """
                    Courier selected delay time - send to restaurants.
                    
                    Sends message to all vendors asking for confirmation of new time.
                    Vendors see same response buttons as original time request.
                    """
                    order_id, new_time = data[1], data[2]
                    user_id = cq["from"]["id"]
                    logger.info(f"User {user_id} selected delay time {new_time} for order {order_id}")
                    
                    # Send delay request to restaurants
                    await upc.send_delay_request_to_restaurants(order_id, new_time, user_id)
                
                elif action == "call_restaurant":
                    """
                    Courier initiates call to restaurant (placeholder for future integration).
                    """
                    order_id, vendor = data[1], data[2]
                    user_id = cq["from"]["id"]
                    logger.info(f"User {user_id} calling restaurant {vendor} for order {order_id}")
                    
                    await upc.initiate_restaurant_call(order_id, vendor, user_id)
                
                elif action == "select_restaurant":
                    """
                    Show restaurant selection for multi-vendor call action.
                    """
                    order_id = data[1]
                    user_id = cq["from"]["id"]
                    logger.info(f"User {user_id} selecting restaurant to call for order {order_id}")
                    
                    await upc.show_restaurant_selection(order_id, user_id)
                
                elif action == "confirm_delivered":
                    """
                    Courier confirms order delivery completion.
                    
                    Final state: Order marked "delivered", MDG updated with completion status,
                    courier receives confirmation message. No further actions possible.
                    """
                    order_id = data[1]
                    user_id = cq["from"]["id"]
                    logger.info(f"User {user_id} confirming delivery for order {order_id}")
                    
                    await upc.handle_delivery_completion(order_id, user_id)
                
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
        
        address = fmt_address(payload.get("shipping_address") or {})
        
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
                
                # Clean product name using project rules
                raw_name = item.get('name', 'Item')
                logger.info(f"PRODUCT NAME DEBUG - Raw: '{raw_name}'")
                cleaned_name = clean_product_name(raw_name)
                logger.info(f"PRODUCT NAME DEBUG - Cleaned: '{cleaned_name}'")
                item_line = f"- {item.get('quantity', 1)} x {cleaned_name}"
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
            "created_at": now(),
            "vendor_messages": {},
            "vendor_expanded": {},
            "requested_time": None,
            "confirmed_times": {},  # Track confirmed time per vendor
            "confirmed_time": None,
            "status": "new",
            "mdg_additional_messages": [],  # Track additional MDG messages for cleanup
            # Order grouping fields
            "group_id": None,  # Group identifier (e.g., "group_orange_001")
            "group_color": None,  # Group color emoji (e.g., "🟠")
            "group_position": None,  # Position in group (1-indexed)
            "upc_assignment_message_id": None,  # Message ID in courier's private chat
            "grouped_via": None,  # "same" or "group" (tracking grouping method)
            "group_reference_order": None  # Reference order ID used for grouping
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
                # Send to MDG with appropriate buttons (summary by default)
                mdg_text = build_mdg_dispatch_text(order, show_details=False)
                
                # Special formatting for pickup orders
                if is_pickup:
                    pickup_header = "**Order for Selbstabholung**\n"
                    pickup_message = f"\nPlease call the customer and arrange the pickup time on this number: {phone}"
                    mdg_text = pickup_header + mdg_text + pickup_message
                
                mdg_msg = await safe_send_message(
                    DISPATCH_MAIN_CHAT_ID,
                    mdg_text,
                    mdg_initial_keyboard(order_id)
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
                    "created_at": now(),
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

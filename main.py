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

# =============================================================================
# SECTION 1: MDG - MAIN DISPATCHING GROUP
# =============================================================================
# WORKFLOW: Orders arrive here first → MDG admins see order details and time request buttons
# → Admins click buttons to request timing from restaurants → Status updates posted here
# → After restaurant confirmation, assignment buttons appear for delivery coordination
# DEPENDENCIES: Uses STATE for order data, calls RG functions for vendor communication
# =============================================================================

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

def build_smart_time_suggestions(order_id: str, vendor: Optional[str] = None) -> InlineKeyboardMarkup:
    """Build smart time suggestions based on last confirmed order"""
    last_order = get_last_confirmed_order(vendor)
    
    if not last_order:
        # No confirmed orders today - show only EXACT TIME button
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("EXACT TIME ⏰", callback_data=f"vendor_exact|{order_id}|{vendor or 'all'}")]
        ])
    
    # Build smart suggestions based on last confirmed order
    last_time_str = last_order["confirmed_time"]
    last_order_num = last_order["name"][-2:] if len(last_order["name"]) >= 2 else last_order["name"]
    
    try:
        # Parse the confirmed time
        hour, minute = map(int, last_time_str.split(':'))
        base_time = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # Generate smart suggestions
        buttons = []
        for i, minutes_to_add in enumerate([5, 10, 15, 20]):
            suggested_time = base_time + timedelta(minutes=minutes_to_add)
            button_text = f"#{last_order_num} {last_time_str} + {minutes_to_add}min"
            callback_data = f"smart_time|{order_id}|{vendor or 'all'}|{suggested_time.strftime('%H:%M')}"
            
            if i % 2 == 0:
                buttons.append([])
            buttons[-1].append(InlineKeyboardButton(button_text, callback_data=callback_data))
        
        # Add EXACT TIME button as 5th option
        buttons.append([InlineKeyboardButton("EXACT TIME ⏰", callback_data=f"vendor_exact|{order_id}|{vendor or 'all'}")])
        
        return InlineKeyboardMarkup(buttons)
        
    except Exception as e:
        logger.error(f"Error building smart suggestions: {e}")
        # Fallback to just EXACT TIME button
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("EXACT TIME ⏰", callback_data=f"vendor_exact|{order_id}|{vendor or 'all'}")]
        ])

def build_mdg_dispatch_text(order: Dict[str, Any]) -> str:
    """Build MDG dispatch message per user's exact specifications"""
    try:
        order_type = order.get("order_type", "shopify")
        vendors = order.get("vendors", [])
        
        # 1. Title with order number and shortcuts (only for Shopify) - add space after emoji
        if order_type == "shopify":
            order_num = order.get('name', '')[-2:] if len(order.get('name', '')) >= 2 else order.get('name', '')
            if len(vendors) > 1:
                # Multi-vendor: use shortcuts
                shortcuts = [RESTAURANT_SHORTCUTS.get(v, v[:2].upper()) for v in vendors]
                title = f"🔖 #{order_num} - dishbee ({'+'.join(shortcuts)})"
            else:
                # Single vendor
                shortcut = RESTAURANT_SHORTCUTS.get(vendors[0], vendors[0][:2].upper()) if vendors else ""
                title = f"🔖 #{order_num} - dishbee ({shortcut})"
        else:
            # For HubRise/Smoothr: only restaurant name
            title = vendors[0] if vendors else "Unknown"
        
        # 2. Customer name on second line with emoji
        customer_name = order['customer']['name']
        customer_line = f"🧑 {customer_name}"
        
        # 3. Address as Google Maps link with new format
        full_address = order['customer']['address']
        original_address = order['customer'].get('original_address', full_address)
        
        # Parse address: split by comma to get street and zip
        address_parts = full_address.split(',')
        if len(address_parts) >= 2:
            street_part = address_parts[0].strip()
            zip_part = address_parts[-1].strip().strip('()')  # Clean zip of any parentheses
            display_address = f"{street_part} ({zip_part})"
        else:
            # Fallback if parsing fails
            display_address = full_address.strip()
        
        # Create Google Maps link using original address (clean, no parentheses)
        maps_link = f"https://www.google.com/maps?q={original_address.replace(' ', '+')}"
        address_line = f"🗺️ [{display_address}]({maps_link})"
        
        # 4. Note (if added)
        note_line = ""
        note = order.get("note", "")
        if note:
            note_line = f"Note: {note}\n"
        
        # 5. Tips (if added)
        tips_line = ""
        tips = order.get("tips", 0.0)
        if tips and float(tips) > 0:
            tips_line = f"❕ Tip: {float(tips):.2f}€\n"
        
        # 6. Payment method - CoD with total (only for Shopify)
        payment_line = ""
        if order_type == "shopify":
            payment = order.get("payment_method", "Paid")
            total = order.get("total", "0.00€")
            
            if payment.lower() == "cash on delivery":
                payment_line = f"❕ Cash on delivery: {total}\n"
            else:
                # For paid orders, just show the total below products
                payment_line = ""
        
        # 7. Items (remove dashes)
        if order_type == "shopify" and len(vendors) > 1:
            # Multi-vendor: show vendor name above each vendor's products
            vendor_items = order.get("vendor_items", {})
            items_text = ""
            for vendor in vendors:
                items_text += f"\n{vendor}:\n"
                vendor_products = vendor_items.get(vendor, [])
                for item in vendor_products:
                    # Remove leading dash
                    clean_item = item.lstrip('- ').strip()
                    items_text += f"{clean_item}\n"
        else:
            # Single vendor: just list items
            items_text = order.get("items_text", "")
            # Remove leading dashes from all lines
            lines = items_text.split('\n')
            clean_lines = []
            for line in lines:
                if line.strip():
                    clean_line = line.lstrip('- ').strip()
                    clean_lines.append(clean_line)
            items_text = '\n'.join(clean_lines)
        
        # Add total to items_text
        total = order.get("total", "0.00€")
        if order_type == "shopify":
            payment = order.get("payment_method", "Paid")
            if payment.lower() != "cash on delivery":
                # For paid orders, show total here
                items_text += f"\n{total}"
        
        # 8. Clickable phone number (tel: link) - only if valid
        phone = order['customer']['phone']
        phone_line = ""
        if phone and phone != "N/A":
            phone_line = f"[{phone}](tel:{phone})\n"
        
        # Build final message with new structure
        text = f"{title}\n"
        text += f"{customer_line}\n"  # Customer name
        text += f"{address_line}\n\n"  # Address + empty line
        text += note_line
        text += tips_line
        text += payment_line
        if note_line or tips_line or payment_line:
            text += "\n"  # Empty line after note/tips/payment block
        text += f"{items_text}\n\n"  # Items + empty line
        text += phone_line
        
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

# --- KEYBOARD FUNCTIONS ---
def mdg_time_request_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build MDG time request buttons per assignment requirements"""
    try:
        order = STATE.get(order_id)
        if not order:
            # Fallback to standard buttons if order not found
            return InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Request ASAP", callback_data=f"req_asap|{order_id}|{int(datetime.now().timestamp())}"),
                    InlineKeyboardButton("Request TIME", callback_data=f"req_time|{order_id}|{int(datetime.now().timestamp())}")
                ]
            ])

        vendors = order.get("vendors", [])
        logger.info(f"Order {order_id} has vendors: {vendors} (count: {len(vendors)})")

        # Multi-vendor: show individual restaurant buttons (REMOVE Request SAME TIME AS)
        if len(vendors) > 1:
            logger.info(f"MULTI-VENDOR detected: {vendors}")
            buttons = []
            for vendor in vendors:
                # Use manual shortcut mapping
                shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
                logger.info(f"Adding button for vendor: {vendor} (shortcut: {shortcut})")
                buttons.append([InlineKeyboardButton(
                    f"Request {shortcut}",
                    callback_data=f"req_vendor|{order_id}|{vendor}|{int(datetime.now().timestamp())}"
                )])
            logger.info(f"Sending restaurant selection with {len(buttons)} buttons")
            return InlineKeyboardMarkup(buttons)

        # Single vendor: show Request ASAP and Request TIME
        logger.info(f"SINGLE VENDOR detected: {vendors}")
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Request ASAP", callback_data=f"req_asap|{order_id}|{int(datetime.now().timestamp())}"),
                InlineKeyboardButton("Request TIME", callback_data=f"req_time|{order_id}|{int(datetime.now().timestamp())}")
            ]
        ])

    except Exception as e:
        logger.error(f"Error building time request keyboard: {e}")
        return InlineKeyboardMarkup([])

def mdg_time_submenu_keyboard(order_id: str, vendor: Optional[str] = None) -> InlineKeyboardMarkup:
    """Build TIME submenu per assignment: title + 4 buttons + Same as + Exact time"""
    try:
        order = STATE.get(order_id)
        if not order:
            return InlineKeyboardMarkup([])

        # Get order details for title
        address = order['customer']['address'].split(',')[0]  # Street only
        if vendor:
            vendor_shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
        else:
            vendor_shortcut = RESTAURANT_SHORTCUTS.get(order['vendors'][0], order['vendors'][0][:2].upper())
        order_num = order['name'][-2:] if len(order['name']) >= 2 else order['name']
        current_time = datetime.now().strftime("%H:%M")

        # Create buttons (no title button - title is in message text)
        vendor_param = f"|{vendor}" if vendor else ""
        buttons = [
            [
                InlineKeyboardButton("+5 mins", callback_data=f"time_plus|{order_id}|5{vendor_param}"),
                InlineKeyboardButton("+10 mins", callback_data=f"time_plus|{order_id}|10{vendor_param}")
            ],
            [
                InlineKeyboardButton("+15 mins", callback_data=f"time_plus|{order_id}|15{vendor_param}"),
                InlineKeyboardButton("+20 mins", callback_data=f"time_plus|{order_id}|20{vendor_param}")
            ]
        ]

        # Check if there are confirmed orders for "Same as" button
        confirmed_orders = get_recent_orders_for_same_time(order_id)
        has_confirmed = any(order_data.get("confirmed_time") for order_data in STATE.values() 
                           if order_data.get("confirmed_time"))

        if has_confirmed:
            buttons.append([InlineKeyboardButton("Same as", callback_data=f"req_same|{order_id}")])
        else:
            # Show "Same as" as text when no confirmed orders exist
            buttons.append([InlineKeyboardButton("Same as (no recent orders)", callback_data="no_recent")])

        buttons.append([InlineKeyboardButton("Request exact time:", callback_data=f"req_exact|{order_id}")])

        return InlineKeyboardMarkup(buttons)

    except Exception as e:
        logger.error(f"Error building TIME submenu keyboard: {e}")
        return InlineKeyboardMarkup([])

def vendor_time_keyboard(order_id: str, vendor: str) -> InlineKeyboardMarkup:
    """Build time request buttons for specific vendor"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Request ASAP", callback_data=f"vendor_asap|{order_id}|{vendor}"),
            InlineKeyboardButton("Request TIME", callback_data=f"vendor_time|{order_id}|{vendor}")
        ]
    ])

def vendor_keyboard(order_id: str, vendor: str, expanded: bool) -> InlineKeyboardMarkup:
    """Build vendor buttons - only toggle button on original messages"""
    try:
        # Only toggle button on vendor order messages
        toggle_text = "◂ Hide" if expanded else "Details ▸"
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_text, callback_data=f"toggle|{order_id}|{vendor}|{int(datetime.now().timestamp())}")]
        ])
    except Exception as e:
        logger.error(f"Error building vendor keyboard: {e}")
        return InlineKeyboardMarkup([])

def restaurant_response_keyboard(request_type: str, order_id: str, vendor: str) -> InlineKeyboardMarkup:
    """Build restaurant response buttons for time request messages"""
    try:
        rows = []
        
        if request_type in ["ASAP", "delay"]:
            # ASAP or delay request: show "Will prepare at" + "Something is wrong"
            rows.append([
                InlineKeyboardButton("Will prepare at", callback_data=f"prepare|{order_id}|{vendor}")
            ])
        else:
            # Specific time request: show "Works 👍" + "Later at" + "Something is wrong"
            rows.append([
                InlineKeyboardButton("Works 👍", callback_data=f"works|{order_id}|{vendor}"),
                InlineKeyboardButton("Later at", callback_data=f"later|{order_id}|{vendor}")
            ])
        
        # "Something is wrong" always shown
        rows.append([
            InlineKeyboardButton("Something is wrong", callback_data=f"wrong|{order_id}|{vendor}")
        ])
        
        return InlineKeyboardMarkup(rows)
    except Exception as e:
        logger.error(f"Error building restaurant response keyboard: {e}")
        return InlineKeyboardMarkup([])

def same_time_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build same time as selection keyboard"""
    try:
        recent = get_recent_orders_for_same_time(order_id)
        rows = []
        
        for order_info in recent:
            text = f"{order_info['display_name']} ({order_info['vendor']})"
            callback = f"same_selected|{order_id}|{order_info['order_id']}"
            rows.append([InlineKeyboardButton(text, callback_data=callback)])
        
        if not recent:
            rows.append([InlineKeyboardButton("No recent orders", callback_data="no_recent")])
        
        return InlineKeyboardMarkup(rows)
    except Exception as e:
        logger.error(f"Error building same time keyboard: {e}")
        return InlineKeyboardMarkup([])

def time_picker_keyboard(order_id: str, action: str, requested_time: str = None) -> InlineKeyboardMarkup:
    """Build time picker for various actions"""
    try:
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
        
        # For "later" action, use requested time + 5,10,15,20
        # For "prepare" action, use current time + 5,10,15,20
        if action == "later_time":
            intervals = []
            for minutes in [5, 10, 15, 20]:
                time_option = base_time + timedelta(minutes=minutes)
                intervals.append(time_option.strftime("%H:%M"))
        else:
            intervals = []
            for minutes in [5, 10, 15, 20]:
                time_option = current_time + timedelta(minutes=minutes)
                intervals.append(time_option.strftime("%H:%M"))
        
        rows = []
        for i in range(0, len(intervals), 2):
            row = [InlineKeyboardButton(intervals[i], callback_data=f"{action}|{order_id}|{intervals[i]}")]
            if i + 1 < len(intervals):
                row.append(InlineKeyboardButton(intervals[i + 1], callback_data=f"{action}|{order_id}|{intervals[i + 1]}"))
            rows.append(row)
        
        return InlineKeyboardMarkup(rows)
    except Exception as e:
        logger.error(f"Error building time picker: {e}")
        return InlineKeyboardMarkup([])

def exact_time_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build exact time picker - shows hours"""
    try:
        current_hour = datetime.now().hour
        rows = []
        
        # Show hours from current hour to end of day (23:XX)
        hours = []
        for hour in range(current_hour, 24):
            hours.append(f"{hour:02d}:XX")
        
        # Build rows with 4 hours per row
        for i in range(0, len(hours), 4):
            row = []
            for j in range(4):
                if i + j < len(hours):
                    hour_str = hours[i + j].split(':')[0]
                    row.append(InlineKeyboardButton(
                        hours[i + j], 
                        callback_data=f"exact_hour|{order_id}|{hour_str}"
                    ))
            if row:
                rows.append(row)
        
        # Add back button
        rows.append([InlineKeyboardButton("← Back", callback_data=f"exact_hide|{order_id}")])
        
        return InlineKeyboardMarkup(rows)
    except Exception as e:
        logger.error(f"Error building exact time keyboard: {e}")
        return InlineKeyboardMarkup([])

def exact_hour_keyboard(order_id: str, hour: int) -> InlineKeyboardMarkup:
    """Build minute picker for exact time - 3 minute intervals"""
    try:
        current_time = datetime.now()
        rows = []
        minutes_options = []
        
        # Generate 3-minute intervals
        for minute in range(0, 60, 3):
            # Skip past times for current hour
            if hour == current_time.hour and minute <= current_time.minute:
                continue
            minutes_options.append(f"{hour:02d}:{minute:02d}")
        
        # Build rows with 4 times per row
        for i in range(0, len(minutes_options), 4):
            row = []
            for j in range(4):
                if i + j < len(minutes_options):
                    time_str = minutes_options[i + j]
                    row.append(InlineKeyboardButton(
                        time_str,
                        callback_data=f"exact_selected|{order_id}|{time_str}"
                    ))
            if row:
                rows.append(row)
        
        # Add back to hours button
        rows.append([InlineKeyboardButton("← Back to hours", callback_data=f"exact_back_hours|{order_id}")])
        
        return InlineKeyboardMarkup(rows)
    except Exception as e:
        logger.error(f"Error building exact hour keyboard: {e}")
        return InlineKeyboardMarkup([])

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

# =============================================================================
# SECTION 2: RG - RESTAURANT GROUPS
# =============================================================================
# WORKFLOW: Restaurants receive order notifications → Confirm or propose new time
# → Status updates posted to MDG → After confirmation, messages cleaned up
# DEPENDENCIES: Uses STATE for order data, called by MDG functions
# =============================================================================

# --- (RG) RESTAURANT GROUP LOGIC ---
def build_rg_order_message(order: Dict[str, Any], vendor: str) -> str:
    """Build order message for restaurant group"""
    try:
        order_type = order.get("order_type", "shopify")
        
        # Title: 🔖 #{order_number} - dishbee (no shortcuts)
        if order_type == "shopify":
            title = f"🔖 #{order['name'][-2:] if len(order['name']) >= 2 else order['name']} - dishbee"
        else:
            # For HubRise/Smoothr: only restaurant name
            title = vendor if vendor else "Unknown"
        
        # Customer name: 👤 {name}
        customer_name = order['customer']['name']
        customer_line = f"👤 {customer_name}"
        
        # Address: 🔺 {street} ({zip})
        full_address = order['customer']['address']
        original_address = order['customer'].get('original_address', full_address)
        
        # Parse address: split by comma to get street and zip
        address_parts = full_address.split(',')
        if len(address_parts) >= 2:
            street_part = address_parts[0].strip()
            zip_part = address_parts[-1].strip().strip('()')  # Clean zip of any parentheses
            display_address = f"{street_part} ({zip_part})"
        else:
            # Fallback if parsing fails
            display_address = full_address.strip()
        
        # Create Google Maps link using original address (clean, no parentheses)
        maps_link = f"https://www.google.com/maps?q={original_address.replace(' ', '+')}"
        address_line = f"🗺️ [{display_address}]({maps_link})"
        
        # 4. Note (if added)
        note_line = ""
        note = order.get("note", "")
        if note:
            note_line = f"Note: {note}\n"
        
        # 5. Tips (if added)
        tips_line = ""
        tips = order.get("tips", 0.0)
        if tips and float(tips) > 0:
            tips_line = f"❕ Tip: {float(tips):.2f}€\n"
        
        # 6. Payment method - CoD with total (only for Shopify)
        payment_line = ""
        if order_type == "shopify":
            payment = order.get("payment_method", "Paid")
            total = order.get("total", "0.00€")
            
            if payment.lower() == "cash on delivery":
                payment_line = f"❕ Cash on delivery: {total}\n"
            else:
                # For paid orders, just show the total below products
                payment_line = ""
        
        # 7. Items (remove dashes)
        vendor_items = order.get("vendor_items", {}).get(vendor, [])
        items_text = ""
        for item in vendor_items:
            # Remove leading dash
            clean_item = item.lstrip('- ').strip()
            items_text += f"{clean_item}\n"
        
        # Add total to items_text
        total = order.get("total", "0.00€")
        if order_type == "shopify":
            payment = order.get("payment_method", "Paid")
            if payment.lower() != "cash on delivery":
                # For paid orders, show total here
                items_text += f"\n{total}"
        
        # 8. Clickable phone number (tel: link) - only if valid
        phone = order['customer']['phone']
        phone_line = ""
        if phone and phone != "N/A":
            phone_line = f"[{phone}](tel:{phone})\n"
        
        # Build final message with new structure
        text = f"{title}\n"
        text += f"{customer_line}\n"  # Customer name
        text += f"{address_line}\n\n"  # Address + empty line
        text += note_line
        text += tips_line
        text += payment_line
        if note_line or tips_line or payment_line:
            text += "\n"  # Empty line after note/tips/payment block
        text += f"{items_text}\n\n"  # Items + empty line
        text += phone_line
        
        return text
    except Exception as e:
        logger.error(f"Error building RG order message: {e}")
        return f"Error formatting order {order.get('name', 'Unknown')} for vendor {vendor}"

def build_rg_response_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build response buttons for restaurant time requests"""
    try:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Works 👍", callback_data=f"works|{order_id}"),
                InlineKeyboardButton("Later at", callback_data=f"later|{order_id}")
            ],
            [
                InlineKeyboardButton("Something is wrong", callback_data=f"wrong|{order_id}")
            ]
        ])
    except Exception as e:
        logger.error(f"Error building RG response keyboard: {e}")
        return InlineKeyboardMarkup([])

# --- (RG) RESTAURANT GROUP HANDLERS ---
async def handle_rg_order_notification(order_id: str):
    """Handle sending order notification to restaurant group"""
    try:
        order = STATE.get(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for notification")
            return
        
        # Send order message to each vendor group
        for vendor in order.get("vendors", []):
            vendor_chat = VENDOR_GROUP_MAP.get(vendor)
            if vendor_chat:
                message_text = build_rg_order_message(order, vendor)
                await safe_send_message(
                    vendor_chat,
                    message_text
                )
        
        logger.info(f"Order notification sent to restaurant groups for order {order_id}")
    except Exception as e:
        logger.error(f"Error in handle_rg_order_notification: {e}")

async def handle_rg_time_response(order_id: str, vendor: str, response_type: str, proposed_time: str = None):
    """Handle restaurant time responses"""
    try:
        order = STATE.get(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for response handling")
            return
        
        # Update order with confirmed or proposed time
        confirmed_times = order.get("confirmed_times", {})
        if response_type == "works":
            confirmed_times[vendor] = order.get("requested_time", "ASAP")
            await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"✅ {vendor} confirmed ASAP")
        elif response_type == "later" and proposed_time:
            confirmed_times[vendor] = proposed_time
            await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"✅ {vendor} proposed new time: {proposed_time}")
        elif response_type == "wrong":
            await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"❌ {vendor} reported an issue")
        
        order["confirmed_times"] = confirmed_times
        
        # Check if all vendors have confirmed
        all_confirmed = await check_all_vendors_confirmed(order_id)
        if all_confirmed:
            # All vendors confirmed - update MDG and send assignment messages
            await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"✅ All vendors confirmed for order {order_id}")
            
            # Add assignment buttons to MDG message
            await add_assignment_buttons(order_id)
            
            # Send assignment message to each user (private chat)
            for user_id in DRIVERS.values():
                await send_assignment_message(order_id, user_id)
            
            # Clean up additional MDG messages
            await cleanup_mdg_messages(order_id)
        else:
            logger.info(f"Not all vendors confirmed yet for order {order_id}")
    
    except Exception as e:
        logger.error(f"Error in handle_rg_time_response: {e}")

# =============================================================================
# SECTION 3: UPC - USER PRIVATE CHATS
# =============================================================================
# WORKFLOW: Assignment messages sent to private chats after all vendors confirm
# → Users interact with CTA buttons for delivery coordination
# → Status updates posted to MDG, messages cleaned up after 15 seconds
# DEPENDENCIES: Called after RG confirmations, uses STATE for order data
# =============================================================================

def build_assignment_message(order: Dict[str, Any]) -> str:
    """Build assignment message for private chat"""
    try:
        # Title: 🔖 #{order_number} - dishbee (no shortcuts)
        title = f"🔖 #{order['name'][-2:] if len(order['name']) >= 2 else order['name']} - dishbee"
        
        # Vendor lines: 🏠 {vendor}: {time} 📦 {quantity}
        vendor_lines = []
        confirmed_times = order.get("confirmed_times", {})
        vendor_items = order.get("vendor_items", {})
        
        for vendor in order.get("vendors", []):
            time = confirmed_times.get(vendor, "ASAP")
            quantity = sum(int(item.split(' x ')[0].lstrip('- ')) for item in vendor_items.get(vendor, []))
            vendor_lines.append(f"🏠 {vendor}: {time} 📦 {quantity}")
        
        vendor_text = "\n".join(vendor_lines)
        
        # Customer name: 👤 {name}
        customer_line = f"👤 {order['customer']['name']}"
        
        # Address: 🔺 {street} ({zip})
        address_parts = order['customer']['address'].split(',')
        street = address_parts[0].strip() if address_parts else "Unknown"
        zip_code = address_parts[-1].strip().split()[0] if len(address_parts) > 1 else ""
        address_line = f"🔺 {street} ({zip_code})"
        
        # Tips: ❕ Tip: {amount}€
        tips_line = ""
        tips = order.get("tips", 0.0)
        if tips and float(tips) > 0:
            tips_line = f"❕ Tip: {float(tips):.2f}€\n"
        
        # Cash payment: ❕ Cash on delivery: {total}€
        payment_line = ""
        if order.get("payment_method") == "Cash on Delivery":
            payment_line = f"❕ Cash on delivery: {order.get('total', '0.00€')}\n"
        
        # Phone: 📞 {phone}
        phone_line = f"📞 {order['customer']['phone']}"
        
        # Build final message
        text = f"{title}\n{vendor_text}\n\n{customer_line}\n{address_line}\n\n{tips_line}{payment_line}{phone_line}"
        return text.strip()
    except Exception as e:
        logger.error(f"Error building assignment message: {e}")
        return f"Error formatting assignment for order {order.get('name', 'Unknown')}"

def assignment_cta_keyboard(order_id: str, is_multi_vendor: bool, phone: str = None) -> InlineKeyboardMarkup:
    """Build CTA buttons for assignment message"""
    try:
        # Call customer button - direct link if phone available
        if phone and phone != "N/A":
            call_button = InlineKeyboardButton("☎️ Call customer", url=f"tel:{phone}")
        else:
            call_button = InlineKeyboardButton("☎️ Call customer", callback_data="call_customer_error")
        
        buttons = [
            [
                call_button,
                InlineKeyboardButton("🧭 Navigate", callback_data=f"navigate|{order_id}")
            ],
            [
                InlineKeyboardButton("⏰ Delay", callback_data=f"delay|{order_id}"),
                InlineKeyboardButton("🍽 Call restaurant", callback_data=f"call_restaurant|{order_id}")
            ],
            [
                InlineKeyboardButton("✅ Delivered", callback_data=f"delivered|{order_id}")
            ]
        ]
        return InlineKeyboardMarkup(buttons)
    except Exception as e:
        logger.error(f"Error building CTA keyboard: {e}")
        return InlineKeyboardMarkup([])

def delay_vendor_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build vendor selection for delay"""
    try:
        order = STATE.get(order_id)
        if not order:
            return InlineKeyboardMarkup([])
        
        vendors = order.get("vendors", [])
        buttons = []
        
        for vendor in vendors:
            shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
            buttons.append([InlineKeyboardButton(
                f"Request {shortcut}",
                callback_data=f"delay_vendor|{order_id}|{vendor}"
            )])
        
        return InlineKeyboardMarkup(buttons)
    except Exception as e:
        logger.error(f"Error building delay vendor keyboard: {e}")
        return InlineKeyboardMarkup([])

def delay_time_keyboard(order_id: str, vendor: str) -> InlineKeyboardMarkup:
    """Build delay time selection"""
    try:
        order = STATE.get(order_id)
        if not order:
            return InlineKeyboardMarkup([])
        
        confirmed_time = order.get("confirmed_times", {}).get(vendor, "ASAP")
        
        if confirmed_time == "ASAP":
            base_time = datetime.now()
        else:
            try:
                hour, minute = map(int, confirmed_time.split(':'))
                base_time = datetime.now().replace(hour=hour, minute=minute)
            except:
                base_time = datetime.now()
        
        intervals = []
        for minutes in [5, 10, 15, 20]:
            time_option = base_time + timedelta(minutes=minutes)
            intervals.append(time_option.strftime("%H:%M"))
        
        buttons = []
        for i in range(0, len(intervals), 2):
            row = []
            for j in range(2):
                if i + j < len(intervals):
                    row.append(InlineKeyboardButton(
                        intervals[i + j],
                        callback_data=f"delay_confirm|{order_id}|{vendor}|{intervals[i + j]}"
                    ))
            if row:
                buttons.append(row)
        
        return InlineKeyboardMarkup(buttons)
    except Exception as e:
        logger.error(f"Error building delay time keyboard: {e}")
        return InlineKeyboardMarkup([])

async def send_assignment_message(order_id: str, user_id: int):
    """Send assignment message to user's private chat"""
    try:
        order = STATE.get(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for assignment")
            return
        
        # Check if user has started a private chat with the bot
        try:
            chat = await bot.get_chat(user_id)
            if chat.type != "private":
                raise Exception("Not a private chat")
        except Exception as e:
            logger.warning(f"Cannot send to user {user_id}: {e}")
            # Send error message to MDG
            await safe_send_message(
                DISPATCH_MAIN_CHAT_ID,
                f"❌ Cannot assign order {order['name'][-2:] if len(order['name']) >= 2 else order['name']} - user hasn't started a private chat with the bot"
            )
            return
        
        # Build and send assignment message
        message_text = build_assignment_message(order)
        is_multi_vendor = len(order.get("vendors", [])) > 1
        
        assignment_msg = await safe_send_message(
            user_id,
            message_text,
            assignment_cta_keyboard(order_id, is_multi_vendor, phone)
        )
        
        # Track assignment message for cleanup
        if "assignment_messages" not in order:
            order["assignment_messages"] = []
        order["assignment_messages"].append(assignment_msg.message_id)
        
        logger.info(f"Assignment message sent to user {user_id} for order {order_id}")
        
    except Exception as e:
        logger.error(f"Error sending assignment message: {e}")

async def check_all_vendors_confirmed(order_id: str) -> bool:
    """Check if all vendors have confirmed times"""
    order = STATE.get(order_id)
    if not order:
        return False
    
    vendors = order.get("vendors", [])
    confirmed_times = order.get("confirmed_times", {})
    
    return len(confirmed_times) == len(vendors) && all(vendor in confirmed_times for vendor in vendors)

async def add_assignment_buttons(order_id: str):
    """Add assignment buttons to MDG confirmation message"""
    try:
        order = STATE.get(order_id)
        if not order:
            return
        
        # Send a new message with assignment buttons
        assignment_msg = await safe_send_message(
            DISPATCH_MAIN_CHAT_ID,
            "✅ All vendors confirmed - ready for assignment",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("👈 Assign to myself", callback_data=f"assign_self|{order_id}")],
                [InlineKeyboardButton("👉 Assign to...", callback_data=f"assign_to|{order_id}")]
            ])
        )
        
        # Track the assignment message for potential cleanup (but keep it until delivered)
        if "assignment_messages" not in order:
            order["assignment_messages"] = []
        order["assignment_messages"].append(assignment_msg.message_id)
        
        logger.info(f"Assignment buttons added to MDG for order {order_id}")
        
    except Exception as e:
        logger.error(f"Error adding assignment buttons: {e}")

async def cleanup_assignment_messages(order_id: str):
    """Clean up assignment-related messages after 15 seconds"""
    try:
        await asyncio.sleep(15)
        
        order = STATE.get(order_id)
        if not order:
            return
        
        # Clean up assignment status messages
        assignment_status_messages = order.get("assignment_status_messages", [])
        for message_id in assignment_status_messages:
            try:
                await safe_delete_message(DISPATCH_MAIN_CHAT_ID, message_id)
            except Exception as e:
                logger.error(f"Error deleting assignment status message {message_id}: {e}")
        
        # Clear the list
        order["assignment_status_messages"] = []
        
    except Exception as e:
        logger.error(f"Error in cleanup_assignment_messages: {e}")

# Extend order state initialization
# ...existing code...

# In shopify_webhook, add confirmed_times initialization
# ...existing code...
            "confirmed_times": {},  # Track per-vendor confirmed times
            "all_confirmed": False,  # Track if all vendors confirmed
            "assignment_messages": [],  # Track assignment message IDs
            "assignment_status_messages": []  # Track status message IDs for cleanup
# ...existing code...
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
        upd = request.get_json(force=True)
        if not upd:
            return "OK"

        # Log all incoming updates for spam detection
        logger.info(f"=== INCOMING UPDATE ===")
        logger.info(f"Update ID: {upd.get('update_id')}")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")

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
                    status_msg = await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        f"✅ ASAP request sent to {vendor}"
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
                    
                    # Show TIME submenu for this vendor (same as single-vendor)
                    keyboard = mdg_time_submenu_keyboard(order_id, vendor)
                    title_text = f"Lederergasse 15 ({RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())}, #{order['name'][-2:] if len(order['name']) >= 2 else order['name']}, {datetime.now().strftime('%H:%M')}) +"
                    msg = await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        title_text,
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
                    status_msg = await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        f"✅ Time request ({selected_time}) sent to {vendor if vendor != 'all' else 'vendors'}"
                    )
                    
                    # Clean up additional MDG messages
                    await cleanup_mdg_messages(order_id)
                
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
                    
                    mdg_text = build_mdg_dispatch_text(order) + f"\n\n⏰ Requested: ASAP"
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
                        title_text = f"{order['customer']['address'].split(',')[0]} ({RESTAURANT_SHORTCUTS.get(vendors[0], vendors[0][:2].upper())}, #{order['name'][-2:] if len(order['name']) >= 2 else order['name']}, {datetime.now().strftime('%H:%M')}) +"
                        msg = await safe_send_message(
                            DISPATCH_MAIN_CHAT_ID,
                            title_text,
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
                    current_time = datetime.now()
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
                    mdg_text = build_mdg_dispatch_text(order) + f"\n\n⏰ Requested: {requested_time}"
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
                    logger.info(f"Processing REQUEST EXACT TIME for order {order_id}")
                    
                    # Show hour picker for exact time
                    msg = await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        "🕒 Select hour:",
                        exact_time_keyboard(order_id)
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
                    mdg_text = build_mdg_dispatch_text(order) + f"\n\n⏰ Requested: {reference_time} (same as {reference_order.get('name', 'other order')})"
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
                    logger.info(f"Processing exact hour {hour} for order {order_id}")
                    
                    # Edit the current message to show minute picker
                    chat_id = cq["message"]["chat"]["id"]
                    message_id = cq["message"]["message_id"]
                    
                    await safe_edit_message(
                        chat_id,
                        message_id,
                        f"🕒 Select exact time (hour {hour}):",
                        exact_hour_keyboard(order_id, int(hour))
                    )
                
                elif action == "exact_selected":
                    order_id, selected_time = data[1], data[2]
                    order = STATE.get(order_id)
                    if not order:
                        return
                    
                    # Send time request to vendors
                    for vendor in order["vendors"]:
                        vendor_chat = VENDOR_GROUP_MAP.get(vendor)
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
                    
                    # Update MDG
                    order["requested_time"] = selected_time
                    mdg_text = build_mdg_dispatch_text(order) + f"\n\n⏰ Requested: {selected_time}"
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
                    logger.info(f"Going back to hours for order {order_id}")
                    
                    # Edit current message back to hour picker
                    chat_id = cq["message"]["chat"]["id"]
                    message_id = cq["message"]["message_id"]
                    
                    await safe_edit_message(
                        chat_id,
                        message_id,
                        "🕒 Select hour:",
                        exact_time_keyboard(order_id)
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
                        confirmed_times = order.get("confirmed_times", {})
                        confirmed_times[vendor] = order.get("requested_time", "ASAP")
                        order["confirmed_times"] = confirmed_times
                        
                        # Check if all vendors confirmed
                        all_confirmed = await check_all_vendors_confirmed(order_id)
                        if all_confirmed:
                            order["all_confirmed"] = True
                            await add_assignment_buttons(order_id)
                    
                    # Post status to MDG
                    status_msg = f"■ {vendor} replied: Works 👍 ■"
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, status_msg)
                
                elif action == "later":
                    order_id, vendor = data[1], data[2]
                    order = STATE.get(order_id)
                    requested = order.get("requested_time", "ASAP") if order else "ASAP"
                    
                    # Show time picker for vendor response
                    await safe_send_message(
                        VENDOR_GROUP_MAP[vendor],
                        f"Select later time:",
                        time_picker_keyboard(order_id, "later_time", requested)
                    )
                
                elif action == "later_time":
                    order_id, selected_time = data[1], data[2]
                    order = STATE.get(order_id)
                    if order:
                        # Track confirmed time
                        confirmed_times = order.get("confirmed_times", {})
                        # Find which vendor this is from
                        for vendor in order["vendors"]:
                            if vendor in order.get("vendor_messages", {}):
                                confirmed_times[vendor] = selected_time
                                break
                        order["confirmed_times"] = confirmed_times
                        
                        # Check if all vendors confirmed
                        all_confirmed = await check_all_vendors_confirmed(order_id)
                        if all_confirmed:
                            order["all_confirmed"] = True
                            await add_assignment_buttons(order_id)
                        
                        # Find which vendor this is from
                        for vendor in order["vendors"]:
                            if vendor in order.get("vendor_messages", {}):
                                status_msg = f"■ {vendor} replied: Later at {selected_time} ■"
                                await safe_send_message(DISPATCH_MAIN_CHAT_ID, status_msg)
                                break
                
                elif action == "prepare":
                    order_id, vendor = data[1], data[2]
                    
                    # Show time picker for vendor response
                    await safe_send_message(
                        VENDOR_GROUP_MAP[vendor],
                        f"Select preparation time:",
                        time_picker_keyboard(order_id, "prepare_time", None)
                    )
                
                elif action == "prepare_time":
                    order_id, selected_time = data[1], data[2]
                    order = STATE.get(order_id)
                    if order:
                        # Track confirmed time
                        confirmed_times = order.get("confirmed_times", {})
                        # Find which vendor this is from
                        for vendor in order["vendors"]:
                            if vendor in order.get("vendor_messages", {}):
                                confirmed_times[vendor] = selected_time
                                break
                        order["confirmed_times"] = confirmed_times
                        
                        # Check if all vendors confirmed
                        all_confirmed = await check_all_vendors_confirmed(order_id)
                        if all_confirmed:
                            order["all_confirmed"] = True
                            await add_assignment_buttons(order_id)
                        
                        # Find which vendor this is from
                        for vendor in order["vendors"]:
                            if vendor in order.get("vendor_messages", {}):
                                status_msg = f"■ {vendor} replied: Will prepare at {selected_time} ■"
                                await safe_send_message(DISPATCH_MAIN_CHAT_ID, status_msg)
                                break
                
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
                    order = STATE.get(order_id)
                    agreed_time = order.get("confirmed_time") or order.get("requested_time", "ASAP") if order else "ASAP"
                    
                    # Show delay time picker
                    try:
                        if agreed_time != "ASAP":
                            hour, minute = map(int, agreed_time.split(':'))
                            base_time = datetime.now().replace(hour=hour, minute=minute)
                        else:
                            base_time = datetime.now()
                        
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
                    except:
                        await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: We have a delay ■")
                
                elif action == "delay_time":
                    order_id, vendor, delay_time = data[1], data[2], data[3]
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: We have a delay - new time {delay_time} ■")
                
                elif action == "navigate":
                    order_id = data[1]
                    order = STATE.get(order_id)
                    if order:
                        original_address = order['customer'].get('original_address', order['customer']['address'])
                        maps_url = f"https://www.google.com/maps/dir/?api=1&destination={original_address.replace(' ', '+')}&travelmode=bicycling"
                        await safe_send_message(
                            cq["message"]["chat"]["id"],
                            f"🧭 Navigate to delivery address:\n{maps_url}"
                        )
                
                elif action == "call_customer_error":
                    await safe_send_message(
                        cq["message"]["chat"]["id"],
                        "❌ No phone number available"
                    )
                
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
                        confirmed_times = order.get("confirmed_times", {})
                        confirmed_times[vendor] = order.get("requested_time", "ASAP")
                        order["confirmed_times"] = confirmed_times
                        
                        # Check if all vendors confirmed
                        all_confirmed = await check_all_vendors_confirmed(order_id)
                        if all_confirmed:
                            order["all_confirmed"] = True
                            await add_assignment_buttons(order_id)
                    
                    # Post status to MDG
                    status_msg = f"■ {vendor} replied: Works 👍 ■"
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, status_msg)
                
                elif action == "later":
                    order_id, vendor = data[1], data[2]
                    order = STATE.get(order_id)
                    requested = order.get("requested_time", "ASAP") if order else "ASAP"
                    
                    # Show time picker for vendor response
                    await safe_send_message(
                        VENDOR_GROUP_MAP[vendor],
                        f"Select later time:",
                        time_picker_keyboard(order_id, "later_time", requested)
                    )
                
                elif action == "later_time":
                    order_id, selected_time = data[1], data[2]
                    order = STATE.get(order_id)
                    if order:
                        # Track confirmed time
                        confirmed_times = order.get("confirmed_times", {})
                        # Find which vendor this is from
                        for vendor in order["vendors"]:
                            if vendor in order.get("vendor_messages", {}):
                                confirmed_times[vendor] = selected_time
                                break
                        order["confirmed_times"] = confirmed_times
                        
                        # Check if all vendors confirmed
                        all_confirmed = await check_all_vendors_confirmed(order_id)
                        if all_confirmed:
                            order["all_confirmed"] = True
                            await add_assignment_buttons(order_id)
                        
                        # Find which vendor this is from
                        for vendor in order["vendors"]:
                            if vendor in order.get("vendor_messages", {}):
                                status_msg = f"■ {vendor} replied: Later at {selected_time} ■"
                                await safe_send_message(DISPATCH_MAIN_CHAT_ID, status_msg)
                                break
                
                elif action == "prepare":
                    order_id, vendor = data[1], data[2]
                    
                    # Show time picker for vendor response
                    await safe_send_message(
                        VENDOR_GROUP_MAP[vendor],
                        f"Select preparation time:",
                        time_picker_keyboard(order_id, "prepare_time", None)
                    )
                
                elif action == "prepare_time":
                    order_id, selected_time = data[1], data[2]
                    order = STATE.get(order_id)
                    if order:
                        # Track confirmed time
                        confirmed_times = order.get("confirmed_times", {})
                        # Find which vendor this is from
                        for vendor in order["vendors"]:
                            if vendor in order.get("vendor_messages", {}):
                                confirmed_times[vendor] = selected_time
                                break
                        order["confirmed_times"] = confirmed_times
                        
                        # Check if all vendors confirmed
                        all_confirmed = await check_all_vendors_confirmed(order_id)
                        if all_confirmed:
                            order["all_confirmed"] = True
                            await add_assignment_buttons(order_id)
                        
                        # Find which vendor this is from
                        for vendor in order["vendors"]:
                            if vendor in order.get("vendor_messages", {}):
                                status_msg = f"■ {vendor} replied: Will prepare at {selected_time} ■"
                                await safe_send_message(DISPATCH_MAIN_CHAT_ID, status_msg)
                                break
                
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
                    order = STATE.get(order_id)
                    agreed_time = order.get("confirmed_time") or order.get("requested_time", "ASAP") if order else "ASAP"
                    
                    # Show delay time picker
                    try:
                        if agreed_time != "ASAP":
                            hour, minute = map(int, agreed_time.split(':'))
                            base_time = datetime.now().replace(hour=hour, minute=minute)
                        else:
                            base_time = datetime.now()
                        
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
                    except:
                        await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: We have a delay ■")
                
                elif action == "delay_time":
                    order_id, vendor, delay_time = data[1], data[2], data[3]
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: We have a delay - new time {delay_time} ■")
                
                elif action == "navigate":
                    order_id = data[1]
                    order = STATE.get(order_id)
                    if order:
                        original_address = order['customer'].get('original_address', order['customer']['address'])
                        maps_url = f"https://www.google.com/maps/dir/?api=1&destination={original_address.replace(' ', '+')}&travelmode=bicycling"
                        await safe_send_message(
                            cq["message"]["chat"]["id"],
                            f"🧭 Navigate to delivery address:\n{maps_url}"
                        )
                
                elif action == "call_customer_error":
                    await safe_send_message(
                        cq["message"]["chat"]["id"],
                        "❌ No phone number available"
                    )
                
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
                        confirmed_times = order.get("confirmed_times", {})
                        confirmed_times[vendor] = order.get("requested_time", "ASAP")
                        order["confirmed_times"] = confirmed_times
                        
                        # Check if all vendors confirmed
                        all_confirmed = await check_all_vendors_confirmed(order_id)
                        if all_confirmed:
                            order["all_confirmed"] = True
                            await add_assignment_buttons(order_id)
                    
                    # Post status to MDG
                    status_msg = f"■ {vendor} replied: Works 👍 ■"
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, status_msg)
                
                elif action == "later":
                    order_id, vendor = data[1], data[2]
                    order = STATE.get(order_id)
                    requested = order.get("requested_time", "ASAP") if order else "ASAP"
                    
                    # Show time picker for vendor response
                    await safe_send_message(
                        VENDOR_GROUP_MAP[vendor],
                        f"Select later time:",
                        time_picker_keyboard(order_id, "later_time", requested)
                    )
                
                elif action == "later_time":
                    order_id, selected_time = data[1], data[2]
                    order = STATE.get(order_id)
                    if order:
                        # Track confirmed time
                        confirmed_times = order.get("confirmed_times", {})
                        # Find which vendor this is from
                        for vendor in order["vendors"]:
                            if vendor in order.get("vendor_messages", {}):
                                confirmed_times[vendor] = selected_time
                                break
                        order["confirmed_times"] = confirmed_times
                        
                        # Check if all vendors confirmed
                        all_confirmed = await check_all_vendors_confirmed(order_id)
                        if all_confirmed:
                            order["all_confirmed"] = True
                            await add_assignment_buttons(order_id)
                        
                        # Find which vendor this is from
                        for vendor in order["vendors"]:
                            if vendor in order.get("vendor_messages", {}):
                                status_msg = f"■ {vendor} replied: Later at {selected_time} ■"
                                await safe_send_message(DISPATCH_MAIN_CHAT_ID, status_msg)
                                break
                
                elif action == "prepare":
                    order_id, vendor = data[1], data[2]
                    
                    # Show time picker for vendor response
                    await safe_send_message(
                        VENDOR_GROUP_MAP[vendor],
                        f"Select preparation time:",
                        time_picker_keyboard(order_id, "prepare_time", None)
                    )
                
                elif action == "prepare_time":
                    order_id, selected_time = data[1], data[2]
                    order = STATE.get(order_id)
                    if order:
                        # Track confirmed time
                        confirmed_times = order.get("confirmed_times", {})
                        # Find which vendor this is from
                        for vendor in order["vendors"]:
                            if vendor in order.get("vendor_messages", {}):
                                confirmed_times[vendor] = selected_time
                                break
                        order["confirmed_times"] = confirmed_times
                        
                        # Check if all vendors confirmed
                        all_confirmed = await check_all_vendors_confirmed(order_id)
                        if all_confirmed:
                            order["all_confirmed"] = True
                            await add_assignment_buttons(order_id)
                        
                        # Find which vendor this is from
                        for vendor in order["vendors"]:
                            if vendor in order.get("vendor_messages", {}):
                                status_msg = f"■ {vendor} replied: Will prepare at {selected_time} ■"
                                await safe_send_message(DISPATCH_MAIN_CHAT_ID, status_msg)
                                break
                
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
                    order = STATE.get(order_id)
                    agreed_time = order.get("confirmed_time") or order.get("requested_time", "ASAP") if order else "ASAP"
                    
                    # Show delay time picker
                    try:
                        if agreed_time != "ASAP":
                            hour, minute = map(int, agreed_time.split(':'))
                            base_time = datetime.now().replace(hour=hour, minute=minute)
                        else:
                            base_time = datetime.now()
                        
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
                    except:
                        await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: We have a delay ■")
                
                elif action == "delay_time":
                    order_id, vendor, delay_time = data[1], data[2], data[3]
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: We have a delay - new time {delay_time} ■")
                
                elif action == "navigate":
                    order_id = data[1]
                    order = STATE.get(order_id)
                    if order:
                        original_address = order['customer'].get('original_address', order['customer']['address'])
                        maps_url = f"https://www.google.com/maps/dir/?api=1&destination={original_address.replace(' ', '+')}&travelmode=bicycling"
                        await safe_send_message(
                            cq["message"]["chat"]["id"],
                            f"🧭 Navigate to delivery address:\n{maps_url}"
                        )
                
                elif action == "call_customer_error":
                    await safe_send_message(
                        cq["message"]["chat"]["id"],
                        "❌ No phone number available"
                    )
                
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
                        confirmed_times = order.get("confirmed_times", {})
                        confirmed_times[vendor] = order.get("requested_time", "ASAP")
                        order["confirmed_times"] = confirmed_times
                        
                        # Check if all vendors confirmed
                        all_confirmed = await check_all_vendors_confirmed(order_id)
                        if all_confirmed:
                            order["all_confirmed"] = True
                            await add_assignment_buttons(order_id)
                    
                    # Post status to MDG
                    status_msg = f"■ {vendor} replied: Works 👍 ■"
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, status_msg)
                
                elif action == "later":
                    order_id, vendor = data[1], data[2]
                    order = STATE.get(order_id)
                    requested = order.get("requested_time", "ASAP") if order else "ASAP"
                    
                    # Show time picker for vendor response
                    await safe_send_message(
                        VENDOR_GROUP_MAP[vendor],
                        f"Select later time:",
                        time_picker_keyboard(order_id, "later_time", requested)
                    )
                
                elif action == "later_time":
                    order_id, selected_time = data[1], data[2]
                    order = STATE.get(order_id)
                    if order:
                        # Track confirmed time
                        confirmed_times = order.get("confirmed_times", {})
                        # Find which vendor this is from
                        for vendor in order["vendors"]:
                            if vendor in order.get("vendor_messages", {}):
                                confirmed_times[vendor] = selected_time
                                break
                        order["confirmed_times"] = confirmed_times
                        
                        # Check if all vendors confirmed
                        all_confirmed = await check_all_vendors_confirmed(order_id)
                        if all_confirmed:
                            order["all_confirmed"] = True
                            await add_assignment_buttons(order_id)
                        
                        # Find which vendor this is from
                        for vendor in order["vendors"]:
                            if vendor in order.get("vendor_messages", {}):
                                status_msg = f"■ {vendor} replied: Later at {selected_time} ■"
                                await safe_send_message(DISPATCH_MAIN_CHAT_ID, status_msg)
                                break
                
                elif action == "prepare":
                    order_id, vendor = data[1], data[2]
                    
                    # Show time picker for vendor response
                    await safe_send_message(
                        VENDOR_GROUP_MAP[vendor],
                        f"Select preparation time:",
                        time_picker_keyboard(order_id, "prepare_time", None)
                    )
                
                elif action == "prepare_time":
                    order_id, selected_time = data[1], data[2]
                    order = STATE.get(order_id)
                    if order:
                        # Track confirmed time
                        confirmed_times = order.get("confirmed_times", {})
                        # Find which vendor this is from
                        for vendor in order["vendors"]:
                            if vendor in order.get("vendor_messages", {}):
                                confirmed_times[vendor] = selected_time
                                break
                        order["confirmed_times"] = confirmed_times
                        
                        # Check if all vendors confirmed
                        all_confirmed = await check_all_vendors_confirmed(order_id)
                        if all_confirmed:
                            order["all_confirmed"] = True
                            await add_assignment_buttons(order_id)
                        
                        # Find which vendor this is from
                        for vendor in order["vendors"]:
                            if vendor in order.get("vendor_messages", {}):
                                status_msg = f"■ {vendor} replied: Will prepare at {selected_time} ■"
                                await safe_send_message(DISPATCH_MAIN_CHAT_ID, status_msg)
                                break
                
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
                    order = STATE.get(order_id)
                    agreed_time = order.get("confirmed_time") or order.get("requested_time", "ASAP") if order else "ASAP"
                    
                    # Show delay time picker
                    try:
                        if agreed_time != "ASAP":
                            hour, minute = map(int, agreed_time.split(':'))
                            base_time = datetime.now().replace(hour=hour, minute=minute)
                        else:
                            base_time = datetime.now()
                        
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
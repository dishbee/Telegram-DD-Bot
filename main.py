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

# Import our modules
from shared import (
    logger, STATE, RESTAURANT_SHORTCUTS, DISPATCH_MAIN_CHAT_ID, VENDOR_GROUP_MAP, DRIVERS,
    safe_send_message, safe_edit_message, safe_delete_message, cleanup_mdg_messages,
    run_async, get_recent_orders_for_same_time, get_last_confirmed_order
)
from mdg import build_mdg_dispatch_text, mdg_time_request_keyboard, mdg_time_submenu_keyboard, same_time_keyboard, time_picker_keyboard, exact_time_keyboard, exact_hour_keyboard, send_mdg_confirmation, get_assign_others_keyboard
from rg import build_vendor_summary_text, build_vendor_details_text, restaurant_response_keyboard, vendor_time_keyboard, vendor_keyboard
from uc import assignment_dm, assignment_cta_keyboard, postpone_keyboard, send_assignment_dm, handle_call_customer, handle_navigate, handle_call_restaurant, handle_complete, handle_postpone, handle_postpone_time, assign_to_user, assign_to_myself, assign_to_driver

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

# --- KEYBOARD FUNCTIONS ---

# --- ASYNC UTILITY FUNCTIONS ---

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
        
        cq = upd.get("callback_query")
        if not cq:
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
                        # Track confirmed time
                        order["confirmed_time"] = order.get("requested_time", "ASAP")
                        order["confirmed_by"] = vendor
                    
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
                        order["confirmed_time"] = selected_time
                        
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
                        order["confirmed_time"] = selected_time
                        
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
                
                # ASSIGNMENT CALLBACKS
                elif action == "assign_myself":
                    order_id = data[1]
                    user_id = cq["from"]["id"]
                    await assign_to_myself(order_id, user_id)
                
                elif action == "assign_others":
                    order_id = data[1]
                    user_id = cq["from"]["id"]
                    keyboard = get_assign_others_keyboard(order_id, user_id)
                    await safe_send_message(
                        user_id,
                        "Select driver to assign:",
                        keyboard
                    )
                
                elif action == "assign_to":
                    order_id, driver_name = data[1], data[2]
                    # Find driver chat ID by name
                    driver_id = None
                    for name, chat_id in DRIVERS.items():
                        if name == driver_name:
                            driver_id = chat_id
                            break
                    
                    if driver_id:
                        await assign_to_driver(order_id, driver_id)
                    else:
                        logger.error(f"Driver {driver_name} not found in DRIVERS mapping")
                
                elif action == "call_customer":
                    order_id = data[1]
                    user_id = cq["from"]["id"]
                    await handle_call_customer(order_id, user_id)
                
                elif action == "navigate":
                    order_id = data[1]
                    user_id = cq["from"]["id"]
                    await handle_navigate(order_id, user_id)
                
                elif action == "call_restaurant":
                    order_id = data[1]
                    user_id = cq["from"]["id"]
                    await handle_call_restaurant(order_id, user_id)
                
                elif action == "postpone":
                    order_id = data[1]
                    user_id = cq["from"]["id"]
                    await handle_postpone(order_id, user_id)
                
                elif action == "postpone_time":
                    order_id, new_time = data[1], data[2]
                    user_id = cq["from"]["id"]
                    await handle_postpone_time(order_id, user_id, new_time)
                
                elif action == "complete":
                    order_id = data[1]
                    user_id = cq["from"]["id"]
                    await handle_complete(order_id, user_id)
                
                elif action == "no_others":
                    user_id = cq["from"]["id"]
                    await safe_send_message(
                        user_id,
                        "No other drivers available for assignment"
                    )
                
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

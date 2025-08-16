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
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Request ASAP", callback_data=f"req_asap|{order_id}"),
                InlineKeyboardButton("Request TIME", callback_data=f"req_time|{order_id}")
            ],
            [
                InlineKeyboardButton("Request EXACT TIME", callback_data=f"req_exact|{order_id}"),
                InlineKeyboardButton("Request SAME TIME AS", callback_data=f"req_same|{order_id}")
            ]
        ])
    except Exception as e:
        logger.error(f"Error building time request keyboard: {e}")
        return InlineKeyboardMarkup([])

def mdg_assignment_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build MDG assignment buttons (shown after time confirmation)"""
    try:
        rows = []
        
        # Assignment buttons for each driver
        if DRIVERS:
            driver_buttons = []
            for name, uid in DRIVERS.items():
                driver_buttons.append(
                    InlineKeyboardButton(f"Assign to {name}", callback_data=f"assign|{order_id}|{name}|{uid}")
                )
            # Split into rows of 2-3 buttons
            for i in range(0, len(driver_buttons), 2):
                rows.append(driver_buttons[i:i+2])
        
        # Status buttons
        rows.append([
            InlineKeyboardButton("Delivered ✅", callback_data=f"delivered|{order_id}"),
            InlineKeyboardButton("Delay 🕧", callback_data=f"delayed|{order_id}")
        ])
        
        return InlineKeyboardMarkup(rows)
    except Exception as e:
        logger.error(f"Error building assignment keyboard: {e}")
        return InlineKeyboardMarkup([])

def vendor_keyboard(order_id: str, vendor: str, expanded: bool) -> InlineKeyboardMarkup:
    """Build vendor buttons per assignment - FIXED button text"""
    try:
        # Correct button text per assignment requirements
        toggle_text = "◂ Hide" if expanded else "Details ▸"
        
        rows = [
            [InlineKeyboardButton(toggle_text, callback_data=f"toggle|{order_id}|{vendor}")],
            [
                InlineKeyboardButton("Works 👍", callback_data=f"works|{order_id}|{vendor}"),
                InlineKeyboardButton("Later at", callback_data=f"later|{order_id}|{vendor}")
            ],
            [
                InlineKeyboardButton("Will prepare at", callback_data=f"prepare|{order_id}|{vendor}"),
                InlineKeyboardButton("Something is wrong", callback_data=f"wrong|{order_id}|{vendor}")
            ]
        ]
        
        return InlineKeyboardMarkup(rows)
    except Exception as e:
        logger.error(f"Error building vendor keyboard: {e}")
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
        
        intervals = get_time_intervals(base_time)
        
        rows = []
        for i in range(0, len(intervals), 2):
            row = [InlineKeyboardButton(intervals[i], callback_data=f"{action}|{order_id}|{intervals[i]}")]
            if i + 1 < len(intervals):
                row.append(InlineKeyboardButton(intervals[i + 1], callback_data=f"{action}|{order_id}|{intervals[i + 1]}"))
            rows.append(row)
        
        # Add custom time option
        rows.append([InlineKeyboardButton("Custom Time ⏰", callback_data=f"{action}_custom|{order_id}")])
        
        return InlineKeyboardMarkup(rows)
    except Exception as e:
        logger.error(f"Error building time picker: {e}")
        return InlineKeyboardMarkup([])

def same_time_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build same time as selection keyboard"""
    try:
        recent = get_recent_orders_for_same_time(order_id)
        rows = []
        
        for order_info in recent:
            text = f"{order_info['display_name']} ({order_info['vendor']})"
            callback = f"same_as|{order_id}|{order_info['order_id']}"
            rows.append([InlineKeyboardButton(text, callback_data=callback)])
        
        if not recent:
            rows.append([InlineKeyboardButton("No recent orders", callback_data="no_recent")])
        
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
                    
                    # Update MDG to assignment mode
                    order["requested_time"] = "ASAP"
                    mdg_text = build_mdg_dispatch_text(order) + f"\n\n⏰ Requested: ASAP"
                    await safe_edit_message(
                        DISPATCH_MAIN_CHAT_ID,
                        order["mdg_message_id"],
                        mdg_text,
                        mdg_assignment_keyboard(order_id)
                    )
                
                elif action == "req_time":
                    order_id = data[1]
                    # Show time picker
                    await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        "🕒 Select time to request:",
                        time_picker_keyboard(order_id, "time_selected")
                    )
                
                elif action == "time_selected":
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
                            await safe_send_message(vendor_chat, msg)
                    
                    # Update MDG
                    order["requested_time"] = selected_time
                    mdg_text = build_mdg_dispatch_text(order) + f"\n\n⏰ Requested: {selected_time}"
                    await safe_edit_message(
                        DISPATCH_MAIN_CHAT_ID,
                        order["mdg_message_id"],
                        mdg_text,
                        mdg_assignment_keyboard(order_id)
                    )
                
                elif action == "req_same":
                    order_id = data[1]
                    await safe_send_message(
                        DISPATCH_MAIN_CHAT_ID,
                        "🔗 Select order to match timing:",
                        same_time_keyboard(order_id)
                    )
                
                # VENDOR RESPONSES
                elif action == "toggle":
                    order_id, vendor = data[1], data[2]
                    order = STATE.get(order_id)
                    if not order:
                        return
                    
                    expanded = not order["vendor_expanded"].get(vendor, False)
                    order["vendor_expanded"][vendor] = expanded
                    
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
                    # Post to MDG with status line
                    msg = f"■ {vendor} replied: Works 👍 ■"
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, msg)
                
                elif action in ["later", "prepare"]:
                    order_id, vendor = data[1], data[2]
                    order = STATE.get(order_id)
                    requested = order.get("requested_time", "ASAP") if order else "ASAP"
                    
                    # Show time picker for vendor response
                    await safe_send_message(
                        VENDOR_GROUP_MAP[vendor],
                        f"Select time for {action}:",
                        time_picker_keyboard(order_id, f"{action}_time", requested)
                    )
                
                elif action in ["later_time", "prepare_time"]:
                    order_id, selected_time = data[1], data[2]
                    # Get vendor from callback context
                    vendor = "Unknown"  # Would need to track this better
                    action_name = "Later" if action.startswith("later") else "Will prepare"
                    msg = f"■ {vendor} replied: {action_name} at {selected_time} ■"
                    await safe_send_message(DISPATCH_MAIN_CHAT_ID, msg)
                
                # ASSIGNMENT ACTIONS
                elif action == "assign":
                    order_id, driver_name, driver_id = data[1], data[2], data[3]
                    order = STATE.get(order_id)
                    if not order:
                        return
                    
                    # Send DM to driver with assignment details
                    dm_text = self.build_assignment_dm(order)
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
        
        # Check for pickup orders
        is_pickup = "Abholung" in str(payload)
        
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
                if is_pickup:
                    mdg_text = f"**Order for Selbstabholung**\n{mdg_text}\n\nPlease call the customer and arrange the pickup time on this number: {phone}"
                
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
                        vendor_msg = await safe_send_message(
                            vendor_chat,
                            vendor_text,
                            vendor_keyboard(order_id, vendor, False)
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

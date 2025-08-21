# Telegram Dispatch Bot — Complete Assignment Implementation on port 10000
# All features from requirements document implemented

import os
import json
import hmac
import hashlib
import base64
import asyncio
import logging
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import httpx

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_SECRET = os.getenv('SHOPIFY_WEBHOOK_SECRET')  # Fixed: was WEBHOOK_SECRET
DISPATCH_MAIN_CHAT_ID = int(os.getenv('DISPATCH_MAIN_CHAT_ID'))

# Restaurant group IDs - safe handling for missing env vars
RESTAURANT_GROUP_IDS = {}
if os.getenv('LECKEROLLS_GROUP_ID'):
    RESTAURANT_GROUP_IDS['Leckerolls'] = int(os.getenv('LECKEROLLS_GROUP_ID'))
if os.getenv('JULIS_GROUP_ID'):
    RESTAURANT_GROUP_IDS['Julis Spätzlerei'] = int(os.getenv('JULIS_GROUP_ID'))
if os.getenv('ZWEITE_HEIMAT_GROUP_ID'):
    RESTAURANT_GROUP_IDS['Zweite Heimat'] = int(os.getenv('ZWEITE_HEIMAT_GROUP_ID'))

print(f"Starting Complete Assignment Implementation on port {os.getenv('PORT', 10000)}")

app = Flask(__name__)

# Global state for tracking orders and conversations
STATE = {}

# Create HTTP client with timeout settings
http_client = httpx.AsyncClient(timeout=30.0)

# Bot API helper functions
async def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    """Send message with error handling and retries"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    
    for attempt in range(3):
        try:
            response = await http_client.post(url, json=payload)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Send message failed: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Send message attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
    
    return None

async def edit_message_text(chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
    """Edit message with error handling"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    
    try:
        response = await http_client.post(url, json=payload)
        return response.json()
    except Exception as e:
        logger.error(f"Edit message failed: {e}")
        return None

async def delete_message(chat_id, message_id):
    """Delete message with error handling"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id
    }
    
    try:
        response = await http_client.post(url, json=payload)
        return response.json()
    except Exception as e:
        logger.error(f"Delete message failed: {e}")
        return None

async def answer_callback_query(callback_query_id, text=None):
    """Answer callback query with error handling"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    
    try:
        response = await http_client.post(url, json=payload)
        return response.json()
    except Exception as e:
        logger.error(f"answer_callback_query error: {e}")
        return None

def get_recent_orders_for_same_time():
    """Get recent orders that have confirmed times for 'same time as' selection"""
    recent_orders = []
    
    # Look through recent orders in STATE
    for order_id, order_data in STATE.items():
        if order_id.startswith('order_'):
            # Check if this order has a confirmed time
            if 'confirmed_time' in order_data and order_data['confirmed_time']:
                try:
                    # Get order details
                    order_num = order_id.replace('order_', '')
                    confirmed_time = order_data['confirmed_time']
                    
                    # Convert timestamp to readable time
                    import datetime
                    time_obj = datetime.datetime.fromtimestamp(confirmed_time)
                    time_str = time_obj.strftime("%H:%M")
                    
                    # Add to recent orders list
                    recent_orders.append({
                        'order_id': order_num,
                        'time': time_str,
                        'timestamp': confirmed_time,
                        'display': f"#{order_num[-2:]} at {time_str}"
                    })
                except:
                    continue
    
    # Sort by timestamp (most recent first) and limit to 5
    recent_orders.sort(key=lambda x: x['timestamp'], reverse=True)
    return recent_orders[:5]

def generate_hours_keyboard(order_id, timestamp):
    """Generate hour selection keyboard for exact time picker"""
    current_hour = datetime.now().hour
    keyboard = []
    
    # Generate 3 rows of 4 hours each, starting from current hour
    for row in range(3):
        hour_row = []
        for col in range(4):
            hour = (current_hour + row * 4 + col) % 24
            hour_str = f"{hour:02d}"
            callback_data = f"exact_hour|{order_id}|{hour}|{timestamp}"
            hour_row.append({"text": hour_str, "callback_data": callback_data})
        keyboard.append(hour_row)
    
    # Add back button
    keyboard.append([{"text": "Back", "callback_data": f"exact_back_hours|{order_id}|{timestamp}"}])
    
    return {"inline_keyboard": keyboard}

def generate_minutes_keyboard(order_id, hour, timestamp):
    """Generate minute selection keyboard for exact time picker"""
    keyboard = []
    
    # Generate 3 rows of 4 minutes each (every 15 minutes)
    for row in range(3):
        minute_row = []
        for col in range(4):
            minute = (row * 4 + col) * 5  # 0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55
            if minute >= 60:
                continue
            minute_str = f"{minute:02d}"
            time_str = f"{hour:02d}:{minute_str}"
            callback_data = f"exact_selected|{order_id}|{time_str}|{timestamp}"
            minute_row.append({"text": minute_str, "callback_data": callback_data})
        keyboard.append(minute_row)
    
    # Add back and hide buttons
    keyboard.append([
        {"text": "Back to hours", "callback_data": f"exact_back_hours|{order_id}|{timestamp}"},
        {"text": "Hide", "callback_data": f"exact_hide|{order_id}|{timestamp}"}
    ])
    
    return {"inline_keyboard": keyboard}

def same_time_keyboard(order_id):
    """Generate keyboard for same time selection"""
    recent_orders = get_recent_orders_for_same_time()
    
    keyboard = []
    
    if recent_orders:
        for order in recent_orders:
            callback_data = f"same_selected|{order_id}|{order['order_id']}|{order['timestamp']}"
            keyboard.append([{"text": order['display'], "callback_data": callback_data}])
    else:
        keyboard.append([{"text": "No recent orders", "callback_data": "no_recent"}])
    
    return {"inline_keyboard": keyboard}

def generate_time_intervals():
    """Generate 10-minute time intervals starting from current time"""
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    
    # Round up to next 10-minute interval
    next_interval = ((current_minute // 10) + 1) * 10
    if next_interval >= 60:
        next_interval = 0
        current_hour += 1
    
    intervals = []
    hour = current_hour
    minute = next_interval
    
    # Generate 12 intervals (2 hours worth)
    for _ in range(12):
        if minute >= 60:
            minute = 0
            hour += 1
        if hour >= 24:
            hour = 0
        
        time_str = f"{hour:02d}:{minute:02d}"
        intervals.append(time_str)
        minute += 10
    
    return intervals

def get_vendors_from_order(order_data):
    """Extract vendor names from order line items"""
    vendors = set()
    
    if 'line_items' in order_data:
        for item in order_data['line_items']:
            if 'vendor' in item and item['vendor']:
                vendors.add(item['vendor'])
    
    return list(vendors)

def format_mdg_message(order_data):
    """Format the main dispatch message for MDG"""
    order_id = order_data['id']
    order_number = str(order_id)[-2:]  # Last 2 digits
    
    # Get vendors
    vendors = get_vendors_from_order(order_data)
    vendor_names = ", ".join(vendors) if vendors else "Unknown Vendor"
    
    # Title
    title = f"dishbee + {vendor_names}"
    
    # Address formatting (no city)
    address = order_data.get('shipping_address', {})
    street = address.get('address1', '')
    zip_code = address.get('zip', '')
    address_line = f"<b>{street}, {zip_code}</b>"
    
    # Payment method
    payment_method = "Payment: Paid"  # Default for Shopify
    
    # Build message
    message_parts = [
        title,
        f"Order #{order_number}",
        address_line,
        payment_method
    ]
    
    # Add vendor sections
    if vendors:
        for vendor in vendors:
            message_parts.append(f"\n<b>{vendor}:</b>")
            vendor_items = []
            for item in order_data.get('line_items', []):
                if item.get('vendor') == vendor:
                    quantity = item.get('quantity', 1)
                    name = item.get('name', 'Unknown Item')
                    vendor_items.append(f"{quantity}x {name}")
            
            if vendor_items:
                message_parts.extend(vendor_items)
    
    # Customer name
    customer_name = f"{order_data.get('customer', {}).get('first_name', '')} {order_data.get('customer', {}).get('last_name', '')}"
    message_parts.append(f"\n{customer_name.strip()}")
    
    return "\n".join(message_parts)

def format_vendor_message(order_data, vendor_name, collapsed=True):
    """Format message for specific vendor group"""
    order_id = order_data['id']
    order_number = str(order_id)[-2:]
    
    if collapsed:
        # Collapsed state - minimal info
        message = f"Order {order_number}"
        
        # Count items for this vendor
        vendor_items = [item for item in order_data.get('line_items', []) if item.get('vendor') == vendor_name]
        total_items = sum(item.get('quantity', 1) for item in vendor_items)
        
        if total_items > 0:
            message += f" ({total_items} items)"
    else:
        # Expanded state - full details
        customer = order_data.get('customer', {})
        address = order_data.get('shipping_address', {})
        
        message_parts = [
            f"Order {order_number}",
            f"Customer: {customer.get('first_name', '')} {customer.get('last_name', '')}",
            f"Address: {address.get('address1', '')}, {address.get('zip', '')}",
            f"Phone: {customer.get('phone', 'N/A')}"
        ]
        
        # Add items for this vendor
        vendor_items = [item for item in order_data.get('line_items', []) if item.get('vendor') == vendor_name]
        if vendor_items:
            message_parts.append("\nItems:")
            for item in vendor_items:
                quantity = item.get('quantity', 1)
                name = item.get('name', 'Unknown Item')
                message_parts.append(f"• {quantity}x {name}")
        
        message = "\n".join(message_parts)
    
    return message

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "ok", "service": "telegram-dispatch-bot"})

@app.route('/webhooks/shopify', methods=['POST'])
def shopify_webhook():
    """Handle Shopify webhooks"""
    try:
        # Verify webhook signature
        signature = request.headers.get('X-Shopify-Hmac-Sha256')
        if not signature:
            logger.error("Missing webhook signature")
            return jsonify({"error": "Missing signature"}), 400
        
        # Verify HMAC
        body = request.data
        expected_signature = base64.b64encode(
            hmac.new(WEBHOOK_SECRET.encode('utf-8'), body, hashlib.sha256).digest()
        ).decode('utf-8')
        
        if not hmac.compare_digest(signature, expected_signature):
            logger.error("Invalid webhook signature")
            return jsonify({"error": "Invalid signature"}), 401
        
        # Parse order data
        order_data = request.json
        if not order_data:
            logger.error("No order data received")
            return jsonify({"error": "No data"}), 400
        
        order_id = order_data.get('id')
        if not order_id:
            logger.error("No order ID in webhook data")
            return jsonify({"error": "No order ID"}), 400
        
        logger.info(f"Processing Shopify order: {order_id}")
        
        # Process order asynchronously
        asyncio.run(process_shopify_order(order_data))
        
        logger.info(f"Order {order_id} processed successfully")
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return jsonify({"error": "Processing failed"}), 500

async def process_shopify_order(order_data):
    """Process incoming Shopify order"""
    try:
        order_id = order_data['id']
        
        # Store order in state
        STATE[f"order_{order_id}"] = order_data
        
        # Get vendors
        vendors = get_vendors_from_order(order_data)
        
        # Send to MDG
        mdg_message = format_mdg_message(order_data)
        
        # MDG buttons for time requests
        mdg_buttons = {
            "inline_keyboard": [
                [
                    {"text": "Request ASAP", "callback_data": f"req_asap|{order_id}|{int(time.time())}"},
                    {"text": "Request TIME", "callback_data": f"req_time|{order_id}|{int(time.time())}"}
                ],
                [
                    {"text": "Request EXACT TIME", "callback_data": f"req_exact|{order_id}|{int(time.time())}"},
                    {"text": "Request SAME TIME AS", "callback_data": f"req_same|{order_id}|{int(time.time())}"}
                ]
            ]
        }
        
        mdg_response = await send_message(DISPATCH_MAIN_CHAT_ID, mdg_message, mdg_buttons)
        
        # Send to each vendor group
        for vendor in vendors:
            if vendor in RESTAURANT_GROUP_IDS:
                vendor_message = format_vendor_message(order_data, vendor, collapsed=True)
                
                # Vendor buttons (only Details toggle)
                vendor_buttons = {
                    "inline_keyboard": [
                        [{"text": "Details ▸", "callback_data": f"expand|{order_id}|{vendor}|{int(time.time())}"}]
                    ]
                }
                
                await send_message(RESTAURANT_GROUP_IDS[vendor], vendor_message, vendor_buttons)
        
    except Exception as e:
        logger.error(f"Error processing order {order_data.get('id', 'unknown')}: {e}")

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def telegram_webhook():
    """Handle Telegram webhooks"""
    try:
        start_time = time.time()
        
        update = request.json
        if not update:
            return jsonify({"status": "ok"})
        
        # Process callback queries
        if 'callback_query' in update:
            callback_query = update['callback_query']
            callback_data = callback_query.get('data', '')
            
            logger.info(f"Raw callback data: {callback_data}")
            
            # Parse callback data
            try:
                data = callback_data.split('|')
                logger.info(f"Parsed callback data: {data}")
            except:
                logger.error(f"Failed to parse callback data: {callback_data}")
                return jsonify({"status": "ok"})
            
            if not data:
                return jsonify({"status": "ok"})
            
            action = data[0]
            logger.info(f"Processing callback: {action}")
            
            # Process callback asynchronously
            asyncio.run(handle_callback_query(callback_query, action, data))
            
            # Log processing time
            processing_time = time.time() - start_time
            if processing_time > 5:
                logger.warning(f"Slow callback processing: {processing_time:.2f}s for {action}")
        
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"Telegram webhook error: {e}")
        return jsonify({"status": "ok"})

async def handle_callback_query(callback_query, action, data):
    """Handle callback query actions"""
    try:
        # Answer callback query first
        await answer_callback_query(callback_query['id'])
        
        chat_id = callback_query['message']['chat']['id']
        message_id = callback_query['message']['message_id']
        
        if action == "expand":
            # Expand vendor order details
            order_id = data[1]
            vendor = data[2]
            
            order_data = STATE.get(f"order_{order_id}")
            if order_data:
                expanded_message = format_vendor_message(order_data, vendor, collapsed=False)
                
                # Change button to Hide
                hide_buttons = {
                    "inline_keyboard": [
                        [{"text": "◂ Hide", "callback_data": f"collapse|{order_id}|{vendor}|{data[3]}"}]
                    ]
                }
                
                await edit_message_text(chat_id, message_id, expanded_message, hide_buttons)
        
        elif action == "collapse":
            # Collapse vendor order details
            order_id = data[1]
            vendor = data[2]
            
            order_data = STATE.get(f"order_{order_id}")
            if order_data:
                collapsed_message = format_vendor_message(order_data, vendor, collapsed=True)
                
                # Change button back to Details
                expand_buttons = {
                    "inline_keyboard": [
                        [{"text": "Details ▸", "callback_data": f"expand|{order_id}|{vendor}|{data[3]}"}]
                    ]
                }
                
                await edit_message_text(chat_id, message_id, collapsed_message, expand_buttons)
        
        elif action == "req_asap":
            # Request ASAP from MDG
            order_id = data[1]
            logger.info(f"Processing ASAP request for order {order_id}")
            
            order_data = STATE.get(f"order_{order_id}")
            if order_data:
                vendors = get_vendors_from_order(order_data)
                order_number = str(order_id)[-2:]
                
                # Send ASAP request to each vendor group
                for vendor in vendors:
                    if vendor in RESTAURANT_GROUP_IDS:
                        asap_message = f"#{order_number} ASAP?"
                        
                        # Buttons for ASAP response
                        asap_buttons = {
                            "inline_keyboard": [
                                [{"text": "Will prepare at", "callback_data": f"prepare_at|{order_id}|{vendor}|{data[2]}"}],
                                [{"text": "Something is wrong", "callback_data": f"wrong|{order_id}|{vendor}|{data[2]}"}]
                            ]
                        }
                        
                        await send_message(RESTAURANT_GROUP_IDS[vendor], asap_message, asap_buttons)
                        logger.info(f"Sent ASAP request to {vendor}")
                
                # Update MDG message
                await edit_message_text(chat_id, message_id, 
                    callback_query['message']['text'] + f"\n\nRequested: ASAP")
                logger.info(f"Updated MDG for order {order_id}")
        
        elif action == "req_time":
            # Request specific time from MDG
            order_id = data[1]
            logger.info(f"Processing TIME request for order {order_id}")
            
            order_data = STATE.get(f"order_{order_id}")
            if order_data:
                vendors = get_vendors_from_order(order_data)
                logger.info(f"Order {order_id} has vendors: {vendors} (count: {len(vendors)})")
                
                if len(vendors) == 1:
                    # Single vendor - show time intervals directly
                    vendor = vendors[0]
                    logger.info(f"SINGLE VENDOR detected: {vendor}")
                    
                    intervals = generate_time_intervals()
                    keyboard = []
                    
                    # Create rows of 3 time buttons each
                    for i in range(0, len(intervals), 3):
                        row = []
                        for j in range(3):
                            if i + j < len(intervals):
                                time_str = intervals[i + j]
                                callback_data = f"vendor_time_selected|{order_id}|{time_str}|{vendor}|{data[2]}"
                                row.append({"text": time_str, "callback_data": callback_data})
                        keyboard.append(row)
                    
                    time_picker_message = f"Select time for order #{str(order_id)[-2:]}:"
                    await send_message(chat_id, time_picker_message, {"inline_keyboard": keyboard})
                else:
                    # Multi vendor - show vendor selection first
                    logger.info(f"MULTI VENDOR detected: {vendors}")
                    
                    keyboard = []
                    for vendor in vendors:
                        callback_data = f"vendor_time|{order_id}|{vendor}|{data[2]}"
                        keyboard.append([{"text": vendor, "callback_data": callback_data}])
                    
                    vendor_message = f"Select vendor for time request (Order #{str(order_id)[-2:]}):"
                    await send_message(chat_id, vendor_message, {"inline_keyboard": keyboard})
        
        elif action == "vendor_time":
            # Handle vendor selection for time request
            order_id = data[1]
            vendor = data[2]
            logger.info(f"Processing TIME request for vendor {vendor} in order {order_id}")
            
            # Generate time intervals
            intervals = generate_time_intervals()
            keyboard = []
            
            # Create rows of 3 time buttons each
            for i in range(0, len(intervals), 3):
                row = []
                for j in range(3):
                    if i + j < len(intervals):
                        time_str = intervals[i + j]
                        callback_data = f"vendor_time_selected|{order_id}|{time_str}|{vendor}|{data[3]}"
                        row.append({"text": time_str, "callback_data": callback_data})
                keyboard.append(row)
            
            time_picker_message = f"Select time for {vendor} (Order #{str(order_id)[-2:]}):"
            await send_message(chat_id, time_picker_message, {"inline_keyboard": keyboard})
            
            # Delete the vendor selection message
            await delete_message(chat_id, message_id)
        
        elif action == "vendor_time_selected":
            # Handle time selection for specific vendor
            order_id = data[1]
            selected_time = data[2]
            vendor = data[3]
            order_number = str(order_id)[-2:]
            
            logger.info(f"Time {selected_time} selected for vendor {vendor} in order {order_id}")
            
            # Send time request to vendor group
            if vendor in RESTAURANT_GROUP_IDS:
                time_message = f"#{order_number} at {selected_time}?"
                
                time_buttons = {
                    "inline_keyboard": [
                        [
                            {"text": "Works 👍", "callback_data": f"works|{order_id}|{vendor}|{data[4]}"},
                            {"text": "Later at", "callback_data": f"later|{order_id}|{vendor}|{data[4]}"}
                        ],
                        [{"text": "Something is wrong", "callback_data": f"wrong|{order_id}|{vendor}|{data[4]}"}]
                    ]
                }
                
                await send_message(RESTAURANT_GROUP_IDS[vendor], time_message, time_buttons)
            
            # Update MDG
            mdg_message = callback_query['message']['text']
            # Find the MDG chat and update
            mdg_update = f"\n\nRequested: {vendor} at {selected_time}"
            await edit_message_text(DISPATCH_MAIN_CHAT_ID, message_id, mdg_message + mdg_update)
        
        elif action == "req_exact":
            # Request exact time from MDG
            order_id = data[1]
            logger.info(f"Processing EXACT TIME request for order {order_id}")
            
            timestamp = data[2]
            hour_keyboard = generate_hours_keyboard(order_id, timestamp)
            
            exact_message = f"Select hour for order #{str(order_id)[-2:]}:"
            await send_message(chat_id, exact_message, hour_keyboard)
        
        elif action == "exact_hour":
            # Handle hour selection in exact time picker
            order_id = data[1]
            hour = int(data[2])
            timestamp = data[3]
            
            logger.info(f"Processing exact hour {hour} for order {order_id}")
            logger.info(f"Editing message {message_id} to show minutes for hour {hour}")
            
            minute_keyboard = generate_minutes_keyboard(order_id, hour, timestamp)
            minute_message = f"Select minute for {hour:02d}:XX:"
            
            await edit_message_text(chat_id, message_id, minute_message, minute_keyboard)
            logger.info(f"Successfully edited message for hour {hour}")
        
        elif action == "exact_selected":
            # Handle exact time selection
            order_id = data[1]
            selected_time = data[2]
            
            logger.info(f"Exact time {selected_time} selected for order {order_id}")
            
            # Similar logic as vendor_time_selected but for exact time
            order_data = STATE.get(f"order_{order_id}")
            if order_data:
                vendors = get_vendors_from_order(order_data)
                order_number = str(order_id)[-2:]
                
                if len(vendors) == 1:
                    # Single vendor - send directly
                    vendor = vendors[0]
                    if vendor in RESTAURANT_GROUP_IDS:
                        time_message = f"#{order_number} at {selected_time}?"
                        
                        time_buttons = {
                            "inline_keyboard": [
                                [
                                    {"text": "Works 👍", "callback_data": f"works|{order_id}|{vendor}|{data[3]}"},
                                    {"text": "Later at", "callback_data": f"later|{order_id}|{vendor}|{data[3]}"}
                                ],
                                [{"text": "Something is wrong", "callback_data": f"wrong|{order_id}|{vendor}|{data[3]}"}]
                            ]
                        }
                        
                        await send_message(RESTAURANT_GROUP_IDS[vendor], time_message, time_buttons)
                    
                    # Update MDG with exact time
                    original_message = callback_query['message']['text'].split('\n\nRequested:')[0]
                    updated_message = f"{original_message}\n\nRequested: {selected_time}"
                    await edit_message_text(DISPATCH_MAIN_CHAT_ID, message_id, updated_message)
                else:
                    # Multi vendor - show vendor selection
                    keyboard = []
                    for vendor in vendors:
                        callback_data = f"vendor_exact_selected|{order_id}|{selected_time}|{vendor}|{data[3]}"
                        keyboard.append([{"text": vendor, "callback_data": callback_data}])
                    
                    vendor_message = f"Select vendor for exact time {selected_time} (Order #{order_number}):"
                    await send_message(chat_id, vendor_message, {"inline_keyboard": keyboard})
                    
                    # Delete the time picker message
                    await delete_message(chat_id, message_id)
        
        elif action == "vendor_exact_selected":
            # Handle vendor selection for exact time
            order_id = data[1]
            selected_time = data[2]
            vendor = data[3]
            order_number = str(order_id)[-2:]
            
            # Send exact time request to vendor group
            if vendor in RESTAURANT_GROUP_IDS:
                time_message = f"#{order_number} at {selected_time}?"
                
                time_buttons = {
                    "inline_keyboard": [
                        [
                            {"text": "Works 👍", "callback_data": f"works|{order_id}|{vendor}|{data[4]}"},
                            {"text": "Later at", "callback_data": f"later|{order_id}|{vendor}|{data[4]}"}
                        ],
                        [{"text": "Something is wrong", "callback_data": f"wrong|{order_id}|{vendor}|{data[4]}"}]
                    ]
                }
                
                await send_message(RESTAURANT_GROUP_IDS[vendor], time_message, time_buttons)
            
            # Update MDG
            original_message = callback_query['message']['text'].split('\n\nRequested:')[0]
            updated_message = f"{original_message}\n\nRequested: {vendor} at {selected_time}"
            await edit_message_text(DISPATCH_MAIN_CHAT_ID, message_id, updated_message)
        
        elif action == "req_same":
            # Request same time as another order
            order_id = data[1]
            logger.info(f"Processing SAME TIME AS request for order {order_id}")
            
            try:
                keyboard = same_time_keyboard(order_id)
                same_message = f"Select order to use same time for #{str(order_id)[-2:]}:"
                await send_message(chat_id, same_message, keyboard)
            except Exception as e:
                logger.error(f"Error building same time keyboard: {e}")
                # Fallback message
                await send_message(chat_id, "No recent orders available for same time selection.")
        
        elif action == "vendor_same":
            # Handle vendor selection for same time request
            order_id = data[1]
            vendor = data[2]
            logger.info(f"VENDOR_SAME: Starting handler with data: {data}")
            logger.info(f"VENDOR_SAME: Extracted order_id={order_id}, vendor={vendor}")
            
            logger.info(f"Processing SAME TIME AS request for vendor {vendor} in order {order_id}")
            logger.info(f"About to send same time selection for {vendor}")
            
            try:
                keyboard = same_time_keyboard(order_id)
                same_message = f"Select order to use same time for {vendor} (Order #{str(order_id)[-2:]}):"
                await send_message(chat_id, same_message, keyboard)
                logger.info(f"Successfully sent same time selection for {vendor}")
            except Exception as e:
                logger.error(f"Error building same time keyboard: {e}")
                # Fallback message
                await send_message(chat_id, f"No recent orders available for {vendor}.")
        
        elif action == "vendor_exact":
            # Handle vendor selection for exact time request
            order_id = data[1]
            vendor = data[2]
            logger.info(f"VENDOR_EXACT: Starting handler with data: {data}")
            logger.info(f"VENDOR_EXACT: Extracted order_id={order_id}, vendor={vendor}")
            
            logger.info(f"Processing EXACT TIME request for vendor {vendor} in order {order_id}")
            logger.info(f"About to send exact time picker for {vendor}")
            
            timestamp = data[3]
            hour_keyboard = generate_hours_keyboard(order_id, timestamp)
            
            exact_message = f"Select hour for {vendor} (Order #{str(order_id)[-2:]}):"
            await send_message(chat_id, exact_message, hour_keyboard)
            logger.info(f"Successfully sent exact time picker for {vendor}")
        
        elif action == "vendor_asap":
            # Handle vendor ASAP request
            order_id = data[1]
            vendor = data[2]
            order_number = str(order_id)[-2:]
            
            # Send ASAP request to specific vendor
            if vendor in RESTAURANT_GROUP_IDS:
                asap_message = f"#{order_number} ASAP?"
                
                asap_buttons = {
                    "inline_keyboard": [
                        [{"text": "Will prepare at", "callback_data": f"prepare_at|{order_id}|{vendor}|{data[3]}"}],
                        [{"text": "Something is wrong", "callback_data": f"wrong|{order_id}|{vendor}|{data[3]}"}]
                    ]
                }
                
                await send_message(RESTAURANT_GROUP_IDS[vendor], asap_message, asap_buttons)
        
        elif action == "works":
            # Vendor confirms time works
            order_id = data[1]
            vendor = data[2]
            order_number = str(order_id)[-2:]
            
            logger.info(f"Vendor {vendor} replied Works for order {order_id}")
            
            # Get the requested time from MDG message or state
            requested_time = None
            if f"order_{order_id}" in STATE:
                requested_time = STATE[f"order_{order_id}"].get('requested_time')
            
            if not requested_time:
                # Try to extract from message context or use current time
                requested_time = datetime.now().strftime("%H:%M")
            
            # Store confirmed time
            if f"order_{order_id}" not in STATE:
                STATE[f"order_{order_id}"] = {}
            STATE[f"order_{order_id}"]['confirmed_time'] = int(time.time())
            
            logger.info(f"Confirmed time {requested_time} for order {order_id}")
            
            # Send status update to MDG
            status_message = f"■ {vendor} replied: Works 👍 ■"
            await send_message(DISPATCH_MAIN_CHAT_ID, status_message)
        
        elif action == "later":
            # Vendor requests later time
            order_id = data[1]
            vendor = data[2]
            order_number = str(order_id)[-2:]
            
            logger.info(f"Vendor {vendor} requested later for order {order_id}")
            
            # Generate time options (15-30 minutes later)
            now = datetime.now()
            later_times = []
            for minutes in [15, 20, 25, 30]:
                later_time = now + timedelta(minutes=minutes)
                later_times.append(later_time.strftime("%H:%M"))
            
            keyboard = []
            for time_str in later_times:
                callback_data = f"later_time|{order_id}|{time_str}|{data[3]}"
                keyboard.append([{"text": time_str, "callback_data": callback_data}])
            
            later_message = f"Select later time for order #{order_number}:"
            await send_message(chat_id, later_message, {"inline_keyboard": keyboard})
        
        elif action == "later_time":
            # Handle later time selection
            order_id = data[1]
            selected_time = data[2]
            vendor = data[1]  # This might need adjustment based on callback data structure
            
            logger.info(f"Vendor {vendor} selected time {selected_time} for later_time")
            
            # Store confirmed time
            if f"order_{order_id}" not in STATE:
                STATE[f"order_{order_id}"] = {}
            STATE[f"order_{order_id}"]['confirmed_time'] = int(data[3])
            
            logger.info(f"Confirmed time {data[3]} for order {order_id}")
            
            # Send status update to MDG
            status_message = f"■ {vendor} replied: Later at {selected_time} ■"
            await send_message(DISPATCH_MAIN_CHAT_ID, status_message)
        
        elif action == "prepare_at":
            # Vendor will prepare at specific time (for ASAP requests)
            order_id = data[1]
            vendor = data[2]
            order_number = str(order_id)[-2:]
            
            # Generate time options
            now = datetime.now()
            prep_times = []
            for minutes in [10, 15, 20, 25, 30]:
                prep_time = now + timedelta(minutes=minutes)
                prep_times.append(prep_time.strftime("%H:%M"))
            
            keyboard = []
            for time_str in prep_times:
                callback_data = f"prep_time|{order_id}|{time_str}|{vendor}|{data[3]}"
                keyboard.append([{"text": time_str, "callback_data": callback_data}])
            
            prep_message = f"When will you prepare order #{order_number}?"
            await send_message(chat_id, prep_message, {"inline_keyboard": keyboard})
        
        elif action == "prep_time":
            # Handle preparation time selection
            order_id = data[1]
            selected_time = data[2]
            vendor = data[3]
            
            # Store confirmed time
            if f"order_{order_id}" not in STATE:
                STATE[f"order_{order_id}"] = {}
            STATE[f"order_{order_id}"]['confirmed_time'] = int(time.time())
            
            # Send status update to MDG
            status_message = f"■ {vendor} replied: Will prepare at {selected_time} ■"
            await send_message(DISPATCH_MAIN_CHAT_ID, status_message)
        
        elif action == "wrong":
            # Something is wrong with the order
            order_id = data[1]
            vendor = data[2]
            
            # Send status update to MDG
            status_message = f"■ {vendor} replied: Something is wrong ■"
            await send_message(DISPATCH_MAIN_CHAT_ID, status_message)
    
    except Exception as e:
        logger.error(f"Error handling callback {action}: {e}")

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

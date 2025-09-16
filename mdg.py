# mdg.py - Main Dispatching Group functionality

from shared import (
    logger, STATE, RESTAURANT_SHORTCUTS, DISPATCH_MAIN_CHAT_ID, 
    safe_send_message, safe_edit_message, safe_delete_message, cleanup_mdg_messages,
    get_recent_orders_for_same_time, get_last_confirmed_order, run_async, DRIVERS
)
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

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

# --- ASSIGNMENT FUNCTIONS ---
def send_mdg_confirmation(order_id: str):
    """Send MDG confirmation with assignment buttons after time confirmation"""
    order = STATE.get(order_id)
    if not order:
        return
    
    mdg_text = build_mdg_dispatch_text(order) + f"\n\n✅ Confirmed: {order['confirmed_time']} by {order['confirmed_by']}"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👈 Assign to myself", callback_data=f"assign_myself|{order_id}")],
        [InlineKeyboardButton("👉 Assign to...", callback_data=f"assign_others|{order_id}")]
    ])
    
    async def send():
        msg = await safe_send_message(DISPATCH_MAIN_CHAT_ID, mdg_text, keyboard)
        order["mdg_confirmation_message_id"] = msg.message_id
    
    run_async(send())

def get_assign_others_keyboard(order_id: str, current_user_id: int) -> InlineKeyboardMarkup:
    """Build keyboard for assigning to other drivers, prioritizing Bee 1,2,3"""
    drivers = []
    prioritized = ["Bee 1", "Bee 2", "Bee 3"]
    
    for username, chat_id in DRIVERS.items():
        if chat_id != current_user_id:
            drivers.append((username, chat_id))
    
    # Sort: prioritized first, then others alphabetically
    sorted_drivers = []
    for prio in prioritized:
        for username, chat_id in drivers:
            if username == prio:
                sorted_drivers.append((username, chat_id))
    
    for username, chat_id in sorted(drivers, key=lambda x: x[0]):
        if username not in prioritized:
            sorted_drivers.append((username, chat_id))
    
    if not sorted_drivers:
        return InlineKeyboardMarkup([[InlineKeyboardButton("No other drivers available", callback_data="no_others")]])
    
    buttons = []
    for username, chat_id in sorted_drivers:
        buttons.append([InlineKeyboardButton(username, callback_data=f"assign_to|{order_id}|{username}")])
    
    return InlineKeyboardMarkup(buttons)
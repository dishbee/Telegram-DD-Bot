# mdg.py - Main Dispatching Group functions for Telegram Dispatch Bot

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from utils import (
    STATE, RECENT_ORDERS, DISPATCH_MAIN_CHAT_ID, VENDOR_GROUP_MAP,
    RESTAURANT_SHORTCUTS, logger, safe_send_message, safe_edit_message,
    safe_delete_message, cleanup_mdg_messages
)

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
        from utils import validate_phone

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
            # Multi-vendor: show vendor names above items
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

        if request_type == "ASAP":
            # ASAP request: show "Will prepare at" + "Something is wrong"
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
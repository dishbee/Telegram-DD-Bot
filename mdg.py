"""MDG (Main Dispatching Group) helpers."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

STATE: Dict[str, Dict[str, Any]] = {}
RESTAURANT_SHORTCUTS: Dict[str, str] = {}


def configure(state_ref: Dict[str, Dict[str, Any]], restaurant_shortcuts: Dict[str, str]) -> None:
    """Configure module-level references used by MDG helpers."""
    global STATE, RESTAURANT_SHORTCUTS
    STATE = state_ref
    RESTAURANT_SHORTCUTS = restaurant_shortcuts


def get_recent_orders_for_same_time(current_order_id: str) -> List[Dict[str, str]]:
    """Get recent CONFIRMED orders (last 1 hour) for 'same time as' functionality."""
    one_hour_ago = datetime.now() - timedelta(hours=1)
    recent: List[Dict[str, str]] = []

    for order_id, order_data in STATE.items():
        if order_id == current_order_id:
            continue
        if not order_data.get("confirmed_time"):
            continue
        created_at = order_data.get("created_at")
        if created_at and created_at > one_hour_ago:
            if order_data.get("order_type") == "shopify":
                display_name = f"#{order_data['name'][-2:]}"
            else:
                address_parts = order_data['customer']['address'].split(',')
                street_info = address_parts[0] if address_parts else "Unknown"
                display_name = f"*{street_info}*"

            recent.append({
                "order_id": order_id,
                "display_name": display_name,
                "vendor": order_data.get("vendors", ["Unknown"])[0],
            })

    return recent[-10:]


def get_last_confirmed_order(vendor: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get the most recent order with confirmed time from today."""
    today = datetime.now().date()
    confirmed_orders: List[Dict[str, Any]] = []

    for order_data in STATE.values():
        created_at = order_data.get("created_at")
        if not created_at or created_at.date() != today:
            continue
        if not order_data.get("confirmed_time"):
            continue
        if vendor and vendor not in order_data.get("vendors", []):
            continue
        confirmed_orders.append(order_data)

    if confirmed_orders:
        confirmed_orders.sort(key=lambda x: x["created_at"], reverse=True)
        return confirmed_orders[0]
    return None


def build_smart_time_suggestions(order_id: str, vendor: Optional[str] = None) -> InlineKeyboardMarkup:
    """Build smart time suggestions based on last confirmed order."""
    last_order = get_last_confirmed_order(vendor)

    if not last_order:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("EXACT TIME ⏰", callback_data=f"vendor_exact|{order_id}|{vendor or 'all'}")]
        ])

    last_time_str = last_order["confirmed_time"]
    last_order_num = last_order["name"][-2:] if len(last_order["name"]) >= 2 else last_order["name"]

    try:
        hour, minute = map(int, last_time_str.split(':'))
        base_time = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)

        buttons: List[List[InlineKeyboardButton]] = []
        for i, minutes_to_add in enumerate([5, 10, 15, 20]):
            suggested_time = base_time + timedelta(minutes=minutes_to_add)
            button_text = f"#{last_order_num} {last_time_str} + {minutes_to_add}min"
            callback_data = f"smart_time|{order_id}|{vendor or 'all'}|{suggested_time.strftime('%H:%M')}"

            if i % 2 == 0:
                buttons.append([])
            buttons[-1].append(InlineKeyboardButton(button_text, callback_data=callback_data))

        buttons.append([InlineKeyboardButton("EXACT TIME ⏰", callback_data=f"vendor_exact|{order_id}|{vendor or 'all'}")])
        return InlineKeyboardMarkup(buttons)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building smart suggestions: %s", exc)
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("EXACT TIME ⏰", callback_data=f"vendor_exact|{order_id}|{vendor or 'all'}")]
        ])


def build_mdg_dispatch_text(order: Dict[str, Any]) -> str:
    """Build MDG dispatch message per user's exact specifications."""
    try:
        order_type = order.get("order_type", "shopify")
        vendors = order.get("vendors", [])

        if order_type == "shopify":
            order_num = order.get('name', '')[-2:] if len(order.get('name', '')) >= 2 else order.get('name', '')
            if len(vendors) > 1:
                shortcuts = [RESTAURANT_SHORTCUTS.get(v, v[:2].upper()) for v in vendors]
                title = f"🔖 #{order_num} - dishbee ({'+'.join(shortcuts)})"
            else:
                shortcut = RESTAURANT_SHORTCUTS.get(vendors[0], vendors[0][:2].upper()) if vendors else ""
                title = f"🔖 #{order_num} - dishbee ({shortcut})"
        else:
            title = vendors[0] if vendors else "Unknown"

        customer_line = f"🧑 {order['customer']['name']}"

        full_address = order['customer']['address']
        original_address = order['customer'].get('original_address', full_address)
        address_parts = full_address.split(',')
        if len(address_parts) >= 2:
            street_part = address_parts[0].strip()
            zip_part = address_parts[-1].strip().strip('()')
            display_address = f"{street_part} ({zip_part})"
        else:
            display_address = full_address.strip()

        maps_link = f"https://www.google.com/maps?q={original_address.replace(' ', '+')}"
        address_line = f"🗺️ [{display_address}]({maps_link})"

        note_line = ""
        note = order.get("note", "")
        if note:
            note_line = f"❕ Note: {note}\n"

        tips_line = ""
        tips = order.get("tips", 0.0)
        if tips and float(tips) > 0:
            tips_line = f"❕ Tip: {float(tips):.2f}€\n"

        payment_line = ""
        if order_type == "shopify":
            payment = order.get("payment_method", "Paid")
            total = order.get("total", "0.00€")
            if payment.lower() == "cash on delivery":
                payment_line = f"❕ Cash on delivery: {total}\n"

        if order_type == "shopify" and len(vendors) > 1:
            vendor_items = order.get("vendor_items", {})
            items_text_parts: List[str] = []
            for vendor in vendors:
                items_text_parts.append(f"\n{vendor}:")
                vendor_products = vendor_items.get(vendor, [])
                for item in vendor_products:
                    clean_item = item.lstrip('- ').strip()
                    items_text_parts.append(clean_item)
            items_text = "\n".join(items_text_parts)
        else:
            items_text = order.get("items_text", "")
            lines = items_text.split('\n')
            clean_lines = [line.lstrip('- ').strip() for line in lines if line.strip()]
            items_text = '\n'.join(clean_lines)

        total = order.get("total", "0.00€")
        if order_type == "shopify":
            payment = order.get("payment_method", "Paid")
            if payment.lower() != "cash on delivery":
                items_text += f"\n{total}"

        phone = order['customer']['phone']
        phone_line = ""
        if phone and phone != "N/A":
            phone_line = f"[{phone}](tel:{phone})\n"

        text = f"{title}\n"
        text += f"{customer_line}\n"
        text += f"{address_line}\n\n"
        text += note_line
        text += tips_line
        text += payment_line
        if note_line or tips_line or payment_line:
            text += "\n"
        text += f"{items_text}\n\n"
        text += phone_line

        return text
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building MDG text: %s", exc)
        return f"Error formatting order {order.get('name', 'Unknown')}"


def mdg_time_request_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build MDG time request buttons per assignment requirements."""
    try:
        order = STATE.get(order_id)
        if not order:
            return InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Request ASAP", callback_data=f"req_asap|{order_id}|{int(datetime.now().timestamp())}"),
                    InlineKeyboardButton("Request TIME", callback_data=f"req_time|{order_id}|{int(datetime.now().timestamp())}")
                ]
            ])

        vendors = order.get("vendors", [])
        logger.info("Order %s has vendors: %s (count: %s)", order_id, vendors, len(vendors))

        if len(vendors) > 1:
            logger.info("MULTI-VENDOR detected: %s", vendors)
            buttons = []
            for vendor in vendors:
                shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
                logger.info("Adding button for vendor: %s (shortcut: %s)", vendor, shortcut)
                buttons.append([InlineKeyboardButton(
                    f"Request {shortcut}",
                    callback_data=f"req_vendor|{order_id}|{vendor}|{int(datetime.now().timestamp())}"
                )])
            logger.info("Sending restaurant selection with %s buttons", len(buttons))
            return InlineKeyboardMarkup(buttons)

        logger.info("SINGLE VENDOR detected: %s", vendors)
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Request ASAP", callback_data=f"req_asap|{order_id}|{int(datetime.now().timestamp())}"),
                InlineKeyboardButton("Request TIME", callback_data=f"req_time|{order_id}|{int(datetime.now().timestamp())}")
            ]
        ])

    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building time request keyboard: %s", exc)
        return InlineKeyboardMarkup([])


def mdg_time_submenu_keyboard(order_id: str, vendor: Optional[str] = None) -> InlineKeyboardMarkup:
    """Build TIME submenu: show recent confirmed orders (not delivered, <1hr) or just EXACT TIME button."""
    try:
        order = STATE.get(order_id)
        if not order:
            return InlineKeyboardMarkup([])

        # Get all confirmed orders (not delivered) from last 1 hour
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_orders: List[Dict[str, Any]] = []

        for oid, order_data in STATE.items():
            if oid == order_id:
                continue
            if not order_data.get("confirmed_time"):
                continue
            if order_data.get("status") == "delivered":
                continue
            created_at = order_data.get("created_at")
            if created_at and created_at > one_hour_ago:
                # Safe access to customer address
                address = order_data.get('customer', {}).get('address', 'Unknown')
                address_short = address.split(',')[0].strip() if ',' in address else address
                
                recent_orders.append({
                    "order_id": oid,
                    "confirmed_time": order_data["confirmed_time"],
                    "address": address_short,
                    "vendors": order_data.get("vendors", []),
                    "order_num": order_data['name'][-2:] if len(order_data['name']) >= 2 else order_data['name']
                })

        buttons: List[List[InlineKeyboardButton]] = []

        # If we have recent orders, show them
        if recent_orders:
            for recent in recent_orders:
                # Build button text: "20:46 - Lederergasse 15 (LR, #59)"
                vendor_shortcuts = ", ".join([RESTAURANT_SHORTCUTS.get(v, v[:2].upper()) for v in recent["vendors"]])
                button_text = f"{recent['confirmed_time']} - {recent['address']} ({vendor_shortcuts}, #{recent['order_num']})"
                
                # Store vendor info in callback for later matching
                vendors_str = ",".join(recent["vendors"])
                callback_data = f"order_ref|{order_id}|{recent['order_id']}|{recent['confirmed_time']}|{vendors_str}"
                if vendor:
                    callback_data += f"|{vendor}"
                
                buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

        # Always show EXACT TIME button at bottom
        vendor_param = f"|{vendor}" if vendor else ""
        buttons.append([InlineKeyboardButton("EXACT TIME ⏰", callback_data=f"req_exact|{order_id}{vendor_param}")])

        return InlineKeyboardMarkup(buttons)

    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building TIME submenu keyboard: %s", exc)
        return InlineKeyboardMarkup([])


def order_reference_options_keyboard(current_order_id: str, ref_order_id: str, ref_time: str, ref_vendors_str: str, current_vendor: Optional[str] = None) -> InlineKeyboardMarkup:
    """Build Same / +5 / +10 / +15 / +20 keyboard after user selects a reference order."""
    try:
        ref_vendors = ref_vendors_str.split(",")
        
        # Calculate +5, +10, +15, +20 times from reference time
        ref_hour, ref_min = map(int, ref_time.split(':'))
        ref_datetime = datetime.now().replace(hour=ref_hour, minute=ref_min, second=0, microsecond=0)
        
        buttons: List[List[InlineKeyboardButton]] = []
        
        # First row: Same button
        # Check if current vendor matches any vendor in reference order
        if current_vendor:
            # Multi-vendor order - only show "Same" if vendor matches
            if current_vendor in ref_vendors:
                same_callback = f"time_same|{current_order_id}|{ref_order_id}|{ref_time}|{current_vendor}"
                buttons.append([InlineKeyboardButton("Same", callback_data=same_callback)])
        else:
            # Single vendor order
            order = STATE.get(current_order_id)
            if order:
                current_vendors = order.get("vendors", [])
                # Check if any current vendor matches ref vendors
                if any(v in ref_vendors for v in current_vendors):
                    same_callback = f"time_same|{current_order_id}|{ref_order_id}|{ref_time}"
                    buttons.append([InlineKeyboardButton("Same", callback_data=same_callback)])
        
        # Build +5, +10, +15, +20 buttons (2 per row)
        time_buttons = []
        for minutes in [5, 10, 15, 20]:
            new_time = ref_datetime + timedelta(minutes=minutes)
            time_str = new_time.strftime("%H:%M")
            vendor_param = f"|{current_vendor}" if current_vendor else ""
            callback = f"time_relative|{current_order_id}|{time_str}|{ref_order_id}{vendor_param}"
            time_buttons.append(InlineKeyboardButton(f"+{minutes}", callback_data=callback))
        
        # Add time buttons in rows of 2
        buttons.append([time_buttons[0], time_buttons[1]])
        buttons.append([time_buttons[2], time_buttons[3]])
        
        return InlineKeyboardMarkup(buttons)
    
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building order reference options keyboard: %s", exc)
        return InlineKeyboardMarkup([])


def same_time_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build same time as selection keyboard."""
    try:
        recent = get_recent_orders_for_same_time(order_id)
        rows: List[List[InlineKeyboardButton]] = []

        for order_info in recent:
            text = f"{order_info['display_name']} ({order_info['vendor']})"
            callback = f"same_selected|{order_id}|{order_info['order_id']}"
            rows.append([InlineKeyboardButton(text, callback_data=callback)])

        if not recent:
            rows.append([InlineKeyboardButton("No recent orders", callback_data="no_recent")])

        return InlineKeyboardMarkup(rows)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building same time keyboard: %s", exc)
        return InlineKeyboardMarkup([])


def time_picker_keyboard(order_id: str, action: str, requested_time: Optional[str] = None) -> InlineKeyboardMarkup:
    """Build time picker for various actions."""
    try:
        current_time = datetime.now()
        if requested_time:
            try:
                req_hour, req_min = map(int, requested_time.split(':'))
                base_time = datetime.now().replace(hour=req_hour, minute=req_min)
            except Exception:  # pragma: no cover - defensive
                base_time = current_time
        else:
            base_time = current_time

        intervals: List[str] = []
        if action == "later_time":
            for minutes in [5, 10, 15, 20]:
                time_option = base_time + timedelta(minutes=minutes)
                intervals.append(time_option.strftime("%H:%M"))
        else:
            for minutes in [5, 10, 15, 20]:
                time_option = current_time + timedelta(minutes=minutes)
                intervals.append(time_option.strftime("%H:%M"))

        rows: List[List[InlineKeyboardButton]] = []
        for i in range(0, len(intervals), 2):
            row = [InlineKeyboardButton(intervals[i], callback_data=f"{action}|{order_id}|{intervals[i]}")]
            if i + 1 < len(intervals):
                row.append(InlineKeyboardButton(intervals[i + 1], callback_data=f"{action}|{order_id}|{intervals[i + 1]}"))
            rows.append(row)

        return InlineKeyboardMarkup(rows)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building time picker: %s", exc)
        return InlineKeyboardMarkup([])


def exact_time_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build exact time picker - shows hours."""
    try:
        current_hour = datetime.now().hour
        rows: List[List[InlineKeyboardButton]] = []
        hours: List[str] = [f"{hour:02d}:XX" for hour in range(current_hour, 24)]

        for i in range(0, len(hours), 4):
            row: List[InlineKeyboardButton] = []
            for j in range(4):
                if i + j < len(hours):
                    hour_str = hours[i + j].split(':')[0]
                    row.append(InlineKeyboardButton(
                        hours[i + j],
                        callback_data=f"exact_hour|{order_id}|{hour_str}"
                    ))
            if row:
                rows.append(row)

        rows.append([InlineKeyboardButton("← Back", callback_data=f"exact_hide|{order_id}")])
        return InlineKeyboardMarkup(rows)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building exact time keyboard: %s", exc)
        return InlineKeyboardMarkup([])


def exact_hour_keyboard(order_id: str, hour: int) -> InlineKeyboardMarkup:
    """Build minute picker for exact time - 3 minute intervals."""
    try:
        current_time = datetime.now()
        rows: List[List[InlineKeyboardButton]] = []
        minutes_options: List[str] = []

        for minute in range(0, 60, 3):
            if hour == current_time.hour and minute <= current_time.minute:
                continue
            minutes_options.append(f"{hour:02d}:{minute:02d}")

        for i in range(0, len(minutes_options), 4):
            row: List[InlineKeyboardButton] = []
            for j in range(4):
                if i + j < len(minutes_options):
                    time_str = minutes_options[i + j]
                    row.append(InlineKeyboardButton(
                        time_str,
                        callback_data=f"exact_selected|{order_id}|{time_str}"
                    ))
            if row:
                rows.append(row)

        rows.append([InlineKeyboardButton("← Back to hours", callback_data=f"exact_back_hours|{order_id}")])
        return InlineKeyboardMarkup(rows)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building exact hour keyboard: %s", exc)
        return InlineKeyboardMarkup([])
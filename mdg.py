"""MDG (Main Dispatching Group) helpers."""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils import get_district_from_address

logger = logging.getLogger(__name__)

STATE: Dict[str, Dict[str, Any]] = {}
RESTAURANT_SHORTCUTS: Dict[str, str] = {}


def configure(state_ref: Dict[str, Dict[str, Any]], restaurant_shortcuts: Dict[str, str]) -> None:
    """Configure module-level references used by MDG helpers."""
    global STATE, RESTAURANT_SHORTCUTS
    STATE = state_ref
    RESTAURANT_SHORTCUTS = restaurant_shortcuts


def shortcut_to_vendor(shortcut: str) -> Optional[str]:
    """Convert vendor shortcut back to full vendor name."""
    for full_name, short in RESTAURANT_SHORTCUTS.items():
        if short == shortcut:
            return full_name
    return None


def get_recent_orders_for_same_time(current_order_id: str) -> List[Dict[str, str]]:
    """Get recent CONFIRMED orders (last 5 hours) for 'same time as' functionality."""
    one_hour_ago = datetime.now() - timedelta(hours=5)
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


def build_mdg_dispatch_text(order: Dict[str, Any], show_details: bool = False) -> str:
    """
    Build MDG dispatch message with collapsible details.
    
    Summary view (show_details=False):
    - 🔖 #28 - dishbee
    - 🏠 JS+LR 🍕 3+1
    - 🧑 Customer Name
    - 🗺️ Address
    - Note/Tip/COD (if applicable)
    - Phone link
    
    Details view (show_details=True):
    - Same header but shows full product list
    """
    try:
        order_type = order.get("order_type", "shopify")
        vendors = order.get("vendors", [])
        order_num = order.get('name', '')[-2:] if len(order.get('name', '')) >= 2 else order.get('name', '')

        # Build title line
        title = f"🔖 #{order_num} - dishbee"

        # Build vendor line with product counts
        if order_type == "shopify":
            vendor_items = order.get("vendor_items", {})
            vendor_counts = []
            shortcuts = []
            
            logger.info(f"DEBUG Product Count - vendor_items structure: {vendor_items}")
            
            for vendor in vendors:
                shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
                shortcuts.append(shortcut)
                
                # Count TOTAL QUANTITY for this vendor (not just line items)
                items = vendor_items.get(vendor, [])
                total_qty = 0
                for item_line in items:
                    # Extract quantity from formatted string like "- 2 x Product Name"
                    # Pattern: "- {qty} x {name}" or just "- {name}" (qty=1)
                    match = re.match(r'^-\s*(\d+)\s*x\s+', item_line)
                    if match:
                        total_qty += int(match.group(1))
                    else:
                        # No quantity prefix, assume 1
                        total_qty += 1
                
                logger.info(f"DEBUG Product Count - {vendor}: items={items}, total_qty={total_qty}")
                vendor_counts.append(str(total_qty))
            
            if len(vendors) > 1:
                vendor_line = f"🏠 {'+'.join(shortcuts)} 🍕 {'+'.join(vendor_counts)}"
            else:
                vendor_line = f"🏠 {shortcuts[0]} 🍕 {vendor_counts[0]}"
        else:
            vendor_line = f"🏠 {vendors[0] if vendors else 'Unknown'}"

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
                payment_line = f"❕ Cash: {total}\n"

        phone = order['customer']['phone']
        phone_line = ""
        if phone and phone != "N/A":
            phone_line = f"[{phone}](tel:{phone})\n"

        # Build base text (always shown)
        text = f"{title}\n"
        text += f"{vendor_line}\n"
        text += f"{customer_line}\n"
        text += f"{address_line}\n\n"
        text += note_line
        text += tips_line
        text += payment_line
        if note_line or tips_line or payment_line:
            text += "\n"
        text += phone_line

        # Add product details if requested
        if show_details:
            logger.info(f"DISTRICT DEBUG - Entering show_details block for order {order.get('name', 'Unknown')}")
            logger.info(f"DISTRICT DEBUG - original_address value: '{original_address}'")
            
            # Add blank line before district
            text += "\n"
            
            # Add district line at the beginning of details section
            district = get_district_from_address(original_address)
            
            logger.info(f"District detection: address='{original_address}', district='{district}'")
            
            if district:
                # Extract zip code from address_parts (already parsed above)
                zip_code = ""
                if len(address_parts) >= 2:
                    zip_code = address_parts[-1].strip().strip('()')
                text += f"🏙️ {district} ({zip_code})\n"
                logger.info(f"Added district line: 🏙️ {district} ({zip_code})")
            else:
                logger.info(f"No district found for address: {original_address}")
            
            if order_type == "shopify" and len(vendors) > 1:
                vendor_items = order.get("vendor_items", {})
                items_text_parts: List[str] = []
                for vendor in vendors:
                    # Use shortcut instead of full vendor name
                    shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
                    items_text_parts.append(f"\n{shortcut}: ")
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

            text += f"{items_text}\n"

        return text
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building MDG text: %s", exc)
        return f"Error formatting order {order.get('name', 'Unknown')}"


def mdg_initial_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """
    Build initial MDG keyboard with Details button above time request buttons.
    
    Layout:
    [Details ▸]
    [Request ASAP] [Request TIME]
    
    Or for multi-vendor:
    [Details ▸]
    [Request JS]
    [Request LR]
    """
    try:
        order = STATE.get(order_id)
        if not order:
            return InlineKeyboardMarkup([
                [InlineKeyboardButton("Details ▸", callback_data=f"mdg_toggle|{order_id}|{int(datetime.now().timestamp())}")],
                [
                    InlineKeyboardButton("Request ASAP", callback_data=f"req_asap|{order_id}|{int(datetime.now().timestamp())}"),
                    InlineKeyboardButton("Request TIME", callback_data=f"req_time|{order_id}|{int(datetime.now().timestamp())}")
                ]
            ])

        vendors = order.get("vendors", [])
        order.setdefault("mdg_expanded", False)  # Track expansion state
        
        is_expanded = order.get("mdg_expanded", False)
        toggle_button = InlineKeyboardButton(
            "◂ Hide" if is_expanded else "Details ▸",
            callback_data=f"mdg_toggle|{order_id}|{int(datetime.now().timestamp())}"
        )

        buttons = [[toggle_button]]

        if len(vendors) > 1:
            # Multi-vendor: show vendor selection buttons
            for vendor in vendors:
                shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
                buttons.append([InlineKeyboardButton(
                    f"Request {shortcut}",
                    callback_data=f"req_vendor|{order_id}|{vendor}|{int(datetime.now().timestamp())}"
                )])
        else:
            # Single vendor: show ASAP/TIME buttons
            buttons.append([
                InlineKeyboardButton("Request ASAP", callback_data=f"req_asap|{order_id}|{int(datetime.now().timestamp())}"),
                InlineKeyboardButton("Request TIME", callback_data=f"req_time|{order_id}|{int(datetime.now().timestamp())}")
            ])

        return InlineKeyboardMarkup(buttons)

    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building initial MDG keyboard: %s", exc)
        return InlineKeyboardMarkup([])


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

        # Get all confirmed orders (not delivered) from last 5 hours
        one_hour_ago = datetime.now() - timedelta(hours=5)
        recent_orders: List[Dict[str, Any]] = []
        
        logger.info(f"BTN-TIME: Searching for recent orders (current order: {order_id}, vendor: {vendor})")
        logger.info(f"BTN-TIME: One hour ago cutoff: {one_hour_ago}")
        logger.info(f"BTN-TIME: Total orders in STATE: {len(STATE)}")

        for oid, order_data in STATE.items():
            if oid == order_id:
                continue
                
            confirmed_time = order_data.get("confirmed_time")
            status = order_data.get("status")
            created_at = order_data.get("created_at")
            
            logger.info(f"BTN-TIME: Order {oid} - confirmed_time={confirmed_time}, status={status}, created_at={created_at}")
            
            if not confirmed_time:
                logger.info(f"BTN-TIME: Order {oid} - SKIP: no confirmed_time")
                continue
                
            if status == "delivered":
                logger.info(f"BTN-TIME: Order {oid} - SKIP: status is delivered")
                continue
                
            if created_at and created_at > one_hour_ago:
                # Safe access to customer address
                address = order_data.get('customer', {}).get('address', 'Unknown')
                address_short = address.split(',')[0].strip() if ',' in address else address
                
                logger.info(f"BTN-TIME: Order {oid} - PASSED all filters, adding to list")
                
                recent_orders.append({
                    "order_id": oid,
                    "confirmed_time": confirmed_time,
                    "address": address_short,
                    "vendors": order_data.get("vendors", []),
                    "order_num": order_data['name'][-2:] if len(order_data['name']) >= 2 else order_data['name']
                })
            else:
                logger.info(f"BTN-TIME: Order {oid} - SKIP: created_at check failed (created_at: {created_at}, cutoff: {one_hour_ago})")

        logger.info(f"BTN-TIME: Found {len(recent_orders)} recent confirmed orders")
        buttons: List[List[InlineKeyboardButton]] = []

        # If we have recent orders, show them + EXACT TIME button
        if recent_orders:
            for recent in recent_orders:
                # Build button text: "20:46 - Lederergasse 15 (LR, #59)"
                vendor_shortcuts = ", ".join([RESTAURANT_SHORTCUTS.get(v, v[:2].upper()) for v in recent["vendors"]])
                button_text = f"{recent['confirmed_time']} - {recent['address']} ({vendor_shortcuts}, #{recent['order_num']})"
                
                # Store vendor SHORTCUTS in callback (not full names) to avoid 64-byte limit
                # Use shortcuts: "LR,SA" instead of "Leckerolls,i Sapori della Toscana"
                vendor_shortcuts_str = ",".join([RESTAURANT_SHORTCUTS.get(v, v[:2].upper()) for v in recent["vendors"]])
                callback_data = f"order_ref|{order_id}|{recent['order_id']}|{recent['confirmed_time']}|{vendor_shortcuts_str}"
                if vendor:
                    # Add current vendor shortcut
                    vendor_shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
                    callback_data += f"|{vendor_shortcut}"
                
                buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

            # Show EXACT TIME button at bottom when there are recent orders
            vendor_param = f"|{vendor}" if vendor else ""
            buttons.append([InlineKeyboardButton("EXACT TIME ⏰", callback_data=f"req_exact|{order_id}{vendor_param}")])
        
        # If NO recent orders, return None to signal that hour picker should be shown directly
        # The handler in main.py will detect this and show exact_time_keyboard() immediately
        else:
            return None

        return InlineKeyboardMarkup(buttons)

    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building TIME submenu keyboard: %s", exc)
        return InlineKeyboardMarkup([])


def order_reference_options_keyboard(current_order_id: str, ref_order_id: str, ref_time: str, ref_vendors_str: str, current_vendor: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    Build Same / +5 / +10 / +15 / +20 keyboard after user selects a reference order.
    
    Args:
        ref_vendors_str: Comma-separated vendor SHORTCUTS (e.g., "LR,SA")
        current_vendor: Current vendor SHORTCUT if multi-vendor order
    """
    try:
        # Convert shortcuts back to full vendor names
        ref_vendor_shortcuts = ref_vendors_str.split(",")
        ref_vendors = [shortcut_to_vendor(s) or s for s in ref_vendor_shortcuts]
        
        # Convert current_vendor shortcut to full name if provided
        current_vendor_full = shortcut_to_vendor(current_vendor) if current_vendor else None
        
        # Calculate +5, +10, +15, +20 times from reference time
        ref_hour, ref_min = map(int, ref_time.split(':'))
        ref_datetime = datetime.now().replace(hour=ref_hour, minute=ref_min, second=0, microsecond=0)
        
        buttons: List[List[InlineKeyboardButton]] = []
        
        # Determine if vendors match between current and reference orders
        vendor_matches = False
        if current_vendor_full:
            # Multi-vendor order - check if current vendor matches any ref vendor
            vendor_matches = current_vendor_full in ref_vendors
        else:
            # Single vendor order - check if any current vendor matches ref vendors
            order = STATE.get(current_order_id)
            if order:
                current_vendors = order.get("vendors", [])
                vendor_matches = any(v in ref_vendors for v in current_vendors)
        
        # First row: Show BTN-SAME if vendors match, BTN-GROUP if different vendors
        if vendor_matches:
            # Same vendor - show "Same time" button (existing behavior)
            if current_vendor_full:
                same_callback = f"time_same|{current_order_id}|{ref_order_id}|{ref_time}|{current_vendor_full}"
            else:
                same_callback = f"time_same|{current_order_id}|{ref_order_id}|{ref_time}"
            buttons.append([InlineKeyboardButton("Same time", callback_data=same_callback)])
        else:
            # Different vendors - show "Group" button (opens time adjustment menu)
            group_callback = f"show_group_menu|{current_order_id}|{ref_order_id}|{ref_time}"
            if current_vendor_full:
                group_callback += f"|{current_vendor_full}"
            buttons.append([InlineKeyboardButton("Group", callback_data=group_callback)])
        
        # Build +5, +10, +15, +20 buttons (2 per row)
        time_buttons = []
        for minutes in [5, 10, 15, 20]:
            new_time = ref_datetime + timedelta(minutes=minutes)
            time_str = new_time.strftime("%H:%M")
            # Use full vendor name in callback
            vendor_param = f"|{current_vendor_full}" if current_vendor_full else ""
            callback = f"time_relative|{current_order_id}|{time_str}|{ref_order_id}{vendor_param}"
            # Show both increment and calculated time: "+5m (19:35)"
            button_text = f"+{minutes}m ({time_str})"
            time_buttons.append(InlineKeyboardButton(button_text, callback_data=callback))
        
        # Add time buttons in rows of 2
        buttons.append([time_buttons[0], time_buttons[1]])
        buttons.append([time_buttons[2], time_buttons[3]])
        
        return InlineKeyboardMarkup(buttons)
    
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building order reference options keyboard: %s", exc)
        return InlineKeyboardMarkup([])


def group_time_adjustment_keyboard(current_order_id: str, ref_order_id: str, ref_time: str, current_vendor: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    Build time adjustment menu for grouping orders with DIFFERENT vendors.
    Shows ±3m and ±5m options relative to reference order time.
    
    Args:
        current_order_id: Current order being grouped
        ref_order_id: Reference order ID
        ref_time: Reference order time (HH:MM)
        current_vendor: Current vendor SHORTCUT if multi-vendor order
    """
    try:
        # Parse reference time
        ref_hour, ref_min = map(int, ref_time.split(':'))
        ref_datetime = datetime.now().replace(hour=ref_hour, minute=ref_min, second=0, microsecond=0)
        
        buttons: List[List[InlineKeyboardButton]] = []
        
        # Build time adjustment buttons: +3m, +5m, -3m, -5m
        adjustments = [
            (3, "+3m"),
            (5, "+5m"),
            (-3, "-3m"),
            (-5, "-5m")
        ]
        
        row1 = []  # +3m, +5m
        row2 = []  # -3m, -5m
        
        for minutes, label in adjustments:
            adjusted_time = ref_datetime + timedelta(minutes=minutes)
            time_str = adjusted_time.strftime("%H:%M")
            
            # Build callback with vendor if multi-vendor order
            vendor_param = f"|{current_vendor}" if current_vendor else ""
            callback = f"time_group|{current_order_id}|{time_str}|{ref_order_id}{vendor_param}"
            
            # Button text: "+3m (19:33)"
            button_text = f"{label} ({time_str})"
            button = InlineKeyboardButton(button_text, callback_data=callback)
            
            if minutes > 0:
                row1.append(button)
            else:
                row2.append(button)
        
        buttons.append(row1)  # [+3m, +5m]
        buttons.append(row2)  # [-3m, -5m]
        
        return InlineKeyboardMarkup(buttons)
    
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building group time adjustment keyboard: %s", exc)
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


def time_picker_keyboard(order_id: str, action: str, requested_time: Optional[str] = None, vendor: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    Build time picker for various actions.
    
    Args:
        vendor: Full vendor name - will be converted to shortcut for callback data
    """
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
        minute_increments = [5, 10, 15, 20]
        
        if action == "later_time":
            for minutes in minute_increments:
                time_option = base_time + timedelta(minutes=minutes)
                intervals.append(time_option.strftime("%H:%M"))
        else:
            for minutes in minute_increments:
                time_option = current_time + timedelta(minutes=minutes)
                intervals.append(time_option.strftime("%H:%M"))

        # Convert vendor name to shortcut for callback data (avoid 64-byte limit)
        vendor_shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper()) if vendor else None

        rows: List[List[InlineKeyboardButton]] = []
        for i in range(0, len(intervals), 2):
            # Add minute increment label to button text
            button_text = f"{intervals[i]} ({minute_increments[i]} mins)"
            
            # Include vendor SHORTCUT in callback if provided (for prepare_time and later_time actions)
            if vendor_shortcut:
                callback = f"{action}|{order_id}|{intervals[i]}|{vendor_shortcut}"
            else:
                callback = f"{action}|{order_id}|{intervals[i]}"
            row = [InlineKeyboardButton(button_text, callback_data=callback)]
            
            if i + 1 < len(intervals):
                button_text2 = f"{intervals[i + 1]} ({minute_increments[i + 1]} mins)"
                if vendor_shortcut:
                    callback2 = f"{action}|{order_id}|{intervals[i + 1]}|{vendor_shortcut}"
                else:
                    callback2 = f"{action}|{order_id}|{intervals[i + 1]}"
                row.append(InlineKeyboardButton(button_text2, callback_data=callback2))
            rows.append(row)
        
        # Add EXACT TIME button at the bottom
        if vendor_shortcut:
            exact_callback = f"vendor_exact_time|{order_id}|{vendor_shortcut}|{action}"
        else:
            exact_callback = f"exact_time|{order_id}|{action}"
        rows.append([InlineKeyboardButton("EXACT TIME ⏰", callback_data=exact_callback)])

        return InlineKeyboardMarkup(rows)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building time picker: %s", exc)
        return InlineKeyboardMarkup([])


def exact_time_keyboard(order_id: str, vendor: Optional[str] = None) -> InlineKeyboardMarkup:
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
                    # Include vendor in callback if provided
                    callback = f"exact_hour|{order_id}|{hour_str}"
                    if vendor:
                        callback += f"|{vendor}"
                    row.append(InlineKeyboardButton(
                        hours[i + j],
                        callback_data=callback
                    ))
            if row:
                rows.append(row)

        rows.append([InlineKeyboardButton("← Back", callback_data=f"exact_hide|{order_id}")])
        return InlineKeyboardMarkup(rows)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building exact time keyboard: %s", exc)
        return InlineKeyboardMarkup([])


def exact_hour_keyboard(order_id: str, hour: int, vendor: Optional[str] = None) -> InlineKeyboardMarkup:
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
                    # Include vendor in callback if provided
                    callback = f"exact_selected|{order_id}|{time_str}"
                    if vendor:
                        callback += f"|{vendor}"
                    row.append(InlineKeyboardButton(
                        time_str,
                        callback_data=callback
                    ))
            if row:
                rows.append(row)

        # Include vendor in back button if provided
        back_callback = f"exact_back_hours|{order_id}"
        if vendor:
            back_callback += f"|{vendor}"
        rows.append([InlineKeyboardButton("← Back to hours", callback_data=back_callback)])
        return InlineKeyboardMarkup(rows)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building exact hour keyboard: %s", exc)
        return InlineKeyboardMarkup([])
# -*- coding: utf-8 -*-
"""MDG (Main Dispatching Group) helpers."""

import logging
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils import get_district_from_address, abbreviate_street, format_phone_for_android

logger = logging.getLogger(__name__)

# Timezone configuration for Passau, Germany (Europe/Berlin)
TIMEZONE = ZoneInfo("Europe/Berlin")

def now() -> datetime:
    """Get current time in Passau timezone (Europe/Berlin)."""
    return datetime.now(TIMEZONE)

STATE = None  # Configured via configure() from main.py
RESTAURANT_SHORTCUTS: Dict[str, str] = {}

# Chef emojis for rotating display in multi-vendor buttons
CHEF_EMOJIS = ['👩‍🍳', '👩🏻‍🍳', '👩🏼‍🍳', '👩🏾‍🍳', '🧑‍🍳', '🧑🏻‍🍳', '🧑🏼‍🍳', '🧑🏾‍🍳', '👨‍🍳', '👨🏻‍🍳', '👨🏼‍🍳', '👨🏾‍🍳']

# Courier shortcuts for combine orders menu
COURIER_SHORTCUTS = {
    "Bee 1": "B1",
    "Bee 2": "B2",
    "Bee 3": "B3"
    # Others: First 2 letters of username from assigned_by field
}

# Group colors for combined orders (max 7 groups, rotating)
GROUP_COLORS = ["🟣", "🔵", "🟢", "🟡", "🟠", "🔴", "🟤"]


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


def get_courier_shortcut(courier_id: int) -> str:
    """
    Get courier shortcut from user_id for combine orders menu.
    
    Looks up courier name from DRIVERS dict, then maps to shortcut:
    - "Bee 1" → "B1"
    - "Bee 2" → "B2"
    - "Bee 3" → "B3"
    - Other couriers → First 2 letters of name (e.g., "Michael" → "MI")
    
    Args:
        courier_id: Telegram user_id from order["assigned_to"]
    
    Returns:
        Courier shortcut (e.g., "B1", "B2", "MI")
    """
    from main import DRIVERS
    
    # Find courier name by user_id
    courier_name = None
    for name, uid in DRIVERS.items():
        if uid == courier_id:
            courier_name = name
            break
    
    # If not found in DRIVERS, return fallback
    if not courier_name:
        return "??"
    
    # Check if this is a known courier with shortcut
    if courier_name in COURIER_SHORTCUTS:
        return COURIER_SHORTCUTS[courier_name]
    
    # For unknown couriers, use first 2 letters
    return courier_name[:2].upper() if len(courier_name) >= 2 else courier_name.upper()


def get_vendor_shortcuts_string(vendors: List[str]) -> str:
    """
    Convert list of vendor names to comma-separated shortcuts.
    
    Args:
        vendors: List of full vendor names
    
    Returns:
        Comma-separated shortcuts (e.g., "LR,DD" for multi-vendor)
    """
    shortcuts = []
    for vendor in vendors:
        shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
        shortcuts.append(f"**{shortcut}**")
    
    # Return first shortcut only for display in combine menu
    return shortcuts[0] if shortcuts else "**??**"


def get_recent_orders_for_same_time(current_order_id: str, vendor: Optional[str] = None) -> List[Dict[str, str]]:
    """Get recent CONFIRMED orders (last 5 hours) for 'same time as' functionality.
    
    Args:
        current_order_id: The current order to exclude from results
        vendor: Optional vendor name to filter by (only show orders containing this vendor)
    """
    five_hours_ago = now() - timedelta(hours=5)
    recent: List[Dict[str, str]] = []

    for order_id, order_data in STATE.items():
        if order_id == current_order_id:
            continue
        
        # Check if order has ANY confirmed time (single-vendor OR multi-vendor)
        confirmed_time = order_data.get("confirmed_time")
        confirmed_times = order_data.get("confirmed_times", {})
        has_confirmation = confirmed_time or (confirmed_times and any(confirmed_times.values()))
        
        if not has_confirmation:
            continue
        
        # Filter by vendor if specified
        if vendor and vendor not in order_data.get("vendors", []):
            continue
            
        created_at = order_data.get("created_at")
        if not created_at:
            continue
        
        # Handle both string (Shopify) and datetime (Smoothr)
        if isinstance(created_at, str):
            try:
                created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except:
                continue
        else:
            created_dt = created_at
        
        if created_dt > five_hours_ago:
            if order_data.get("order_type") == "shopify":
                display_name = f"{order_data['name'][-2:]}"
            else:
                # Safely access customer address for Smoothr orders
                customer = order_data.get('customer', {})
                address = customer.get('address', '')
                if address:
                    address_parts = address.split(',')
                    street_info = address_parts[0] if address_parts else "Unknown"
                    display_name = f"*{street_info}*"
                else:
                    # Fallback to order name if address missing
                    display_name = f"Order {order_data.get('name', 'Unknown')}"

            recent.append({
                "order_id": order_id,
                "display_name": display_name,
                "vendor": order_data.get("vendors", ["Unknown"])[0],
            })

    return recent[-10:]


def get_last_confirmed_order(vendor: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get the most recent order with confirmed time from today."""
    today = now().date()
    confirmed_orders: List[Dict[str, Any]] = []

    for order_data in STATE.values():
        created_at = order_data.get("created_at")
        if not created_at:
            continue
        
        # Handle both string (Shopify) and datetime (Smoothr)
        if isinstance(created_at, str):
            try:
                created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except:
                continue
        else:
            created_dt = created_at
        
        if created_dt.date() != today:
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
        base_time = now().replace(hour=hour, minute=minute, second=0, microsecond=0)

        buttons: List[List[InlineKeyboardButton]] = []
        for i, minutes_to_add in enumerate([5, 10, 15, 20]):
            suggested_time = base_time + timedelta(minutes=minutes_to_add)
            button_text = f"{last_order_num} {last_time_str} + {minutes_to_add}min"
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
    - � JS+LR 🍕 3+1
    - 🧑 Customer Name
    - 🗺️ Address
    - Note/Tip/COD (if applicable)
    - Phone link
    
    Details view (show_details=True):
    - Same header but shows full product list
    """
    try:
        from utils import build_status_lines
        
        # Build status lines (prepend to message)
        status_text = build_status_lines(order, "mdg", RESTAURANT_SHORTCUTS, COURIER_SHORTCUTS)
        
        order_type = order.get("order_type", "shopify")
        vendors = order.get("vendors", [])
        
        # Extract order number for display
        if order_type == "shopify":
            # Shopify: "dishbee #26" -> take last 2 digits
            order_num = order.get('name', '')[-2:] if len(order.get('name', '')) >= 2 else order.get('name', '')
        else:
            # Smoothr: use full display number (already formatted by parser)
            order_num = order.get('name', 'Order')

        # Build title line (NO "dishbee" in order number line)
        title = f"🔖 {order_num}"
        
        # Add scheduled delivery time for Smoothr orders (if not ASAP)
        is_asap = order.get("is_asap", True)
        requested_time = order.get("requested_time")
        if not is_asap and requested_time:
            title += f"\n⏰ {requested_time}"

        # Build vendor line with product counts (works for both Shopify and Smoothr)
        vendor_items = order.get("vendor_items", {})
        vendor_counts = []
        shortcuts = []
        
        logger.info(f"DEBUG Product Count - vendor_items structure: {vendor_items}")
        
        for vendor in vendors:
            shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
            shortcuts.append(f"**{shortcut}**")
            
            # Count TOTAL QUANTITY for this vendor (not just line items)
            items = vendor_items.get(vendor, [])
            total_qty = 0
            for item_line in items:
                # Extract quantity from formatted string
                # Smoothr format: "2 x Product Name" (no dash)
                # Shopify format: "- 2 x Product Name" (with dash)
                item_clean = item_line.lstrip('- ').strip()
                if ' x ' in item_clean:
                    qty_part = item_clean.split(' x ')[0].strip()
                    try:
                        total_qty += int(qty_part)
                    except ValueError:
                        total_qty += 1
                else:
                    # No quantity prefix, assume 1
                    total_qty += 1
            
            logger.info(f"DEBUG Product Count - {vendor}: items={items}, total_qty={total_qty}")
            vendor_counts.append(str(total_qty))
        
        # Use rotating chef emojis for vendors
        chef_emojis = ["👩‍🍳", "👩🏻‍🍳", "👩🏼‍🍳", "👩🏾‍🍳", "🧑‍🍳", "🧑🏻‍🍳", "🧑🏼‍🍳", "🧑🏾‍🍳", "👨‍🍳", "👨🏻‍🍳", "👨🏼‍🍳", "👨🏾‍🍳"]
        
        # Build vendor line with counts in parentheses
        if len(vendors) > 1:
            # Multi-vendor: ONE chef emoji for all vendors
            vendor_parts = []
            for idx, vendor in enumerate(vendors):
                shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
                count = vendor_counts[idx]
                vendor_parts.append(f"**{shortcut}** ({count})")
            vendor_line = f"{chef_emojis[0]} " + " + ".join(vendor_parts)
        else:
            # Single vendor
            chef_emoji = chef_emojis[0]
            # Don't show count for PF Lieferando orders (no products parsed)
            order_type = order.get("order_type", "")
            if order_type == "smoothr_lieferando" and vendors[0] == "Pommes Freunde":
                # PF OCR order - no product count
                vendor_line = f"{chef_emoji} **{shortcuts[0]}**"
            else:
                vendor_line = f"{chef_emoji} **{shortcuts[0]}** ({vendor_counts[0]})"

        customer_line = f"👤 {order['customer']['name']}"

        full_address = order['customer']['address']
        zip_code = order['customer'].get('zip', '')
        original_address = order['customer'].get('original_address', full_address)
        address_parts = full_address.split(',')
        
        if len(address_parts) >= 2:
            # Shopify format: "Street, Zip"
            street_part = address_parts[0].strip()
            zip_part = address_parts[-1].strip().strip('()')
            display_address = f"{street_part} ({zip_part})"
        else:
            # Smoothr format: street only, zip stored separately
            if zip_code:
                display_address = f"{full_address.strip()} ({zip_code})"
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
            # Format for Android auto-detection (no spaces, ensure +49)
            phone_line = f"📞 {format_phone_for_android(phone)}"

        # Determine source label
        order_type = order.get("order_type", "shopify")
        if order_type == "shopify":
            source_line = "🔗 dishbee"
        elif order_type == "smoothr_dishbee":
            source_line = "🔗 dishbee"
        elif order_type == "smoothr_dnd":
            source_line = "🔗 D&D App"
        elif order_type == "smoothr_lieferando":
            source_line = "🔗 Lieferando"
        else:
            source_line = "🔗 dishbee"

        # Build base text with separator and proper spacing
        text = "--------------------------------\n"
        text += "\n"  # Blank line after separator
        text += f"{title}\n"
        text += "\n"  # Blank line after order number
        text += f"{vendor_line}\n"
        text += "\n"  # Blank line after vendor
        text += f"{address_line}\n"
        text += "\n"  # Blank line after address
        text += f"{customer_line}\n"
        text += "\n"  # Blank line after customer
        text += f"{phone_line}\n"
        text += "\n"  # Blank line after phone
        text += f"{source_line}"
        # Add notes/tips/cash after source (if present)
        if note_line or tips_line or payment_line:
            text += "\n\n"  # Blank line before notes section
            text += note_line
            if note_line:
                text += "\n"  # Blank line after note
            text += tips_line
            if tips_line:
                text += "\n"  # Blank line after tip
            text += payment_line
            if payment_line:
                text = text.rstrip("\n")  # Remove trailing newline from payment

        # Add product details if requested
        if show_details:
            logger.info(f"DISTRICT DEBUG - Entering show_details block for order {order.get('name', 'Unknown')}")
            logger.info(f"DISTRICT DEBUG - original_address value: '{original_address}'")
            
            # Blank line before expanded details
            text += "\n\n"
            
            # Add email if available (expanded view only, before district)
            email = order['customer'].get('email')
            if email:
                text += f"✉️ {email}\n"
                text += "\n"  # Blank line after email
            
            # Add district line at the beginning of details section
            district = get_district_from_address(original_address)
            
            logger.info(f"District detection: address='{original_address}', district='{district}'")
            
            if district:
                # Get zip code directly from STATE (works for both Shopify and Smoothr)
                zip_code = order['customer'].get('zip', '')
                text += f"🏙️ {district} ({zip_code})\n"
                text += "\n"  # Blank line after district
                logger.info(f"Added district line: 🏙️ {district} ({zip_code})")
            else:
                logger.info(f"No district found for address: {original_address}")
            
            # Build product list (works for both Shopify and Smoothr)
            if len(vendors) > 1:
                # Multi-vendor product display
                vendor_items = order.get("vendor_items", {})
                items_text_parts: List[str] = []
                for vendor in vendors:
                    # Use shortcut instead of full vendor name
                    shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
                    items_text_parts.append(f"**{shortcut}**:")
                    vendor_products = vendor_items.get(vendor, [])
                    for item in vendor_products:
                        clean_item = item.lstrip('- ').strip()
                        items_text_parts.append(clean_item)
                items_text = "\n".join(items_text_parts)
            else:
                # Single vendor product display (works for both Shopify and Smoothr)
                vendor_items = order.get("vendor_items", {})
                items_text_parts: List[str] = []
                
                # Get products from vendor_items (populated for both order types)
                if vendor_items and vendors:
                    vendor = vendors[0]  # Single vendor
                    vendor_products = vendor_items.get(vendor, [])
                    for item in vendor_products:
                        clean_item = item.lstrip('- ').strip()
                        items_text_parts.append(clean_item)
                
                # Fallback to items_text if vendor_items not available
                if not items_text_parts:
                    items_text = order.get("items_text", "")
                    lines = items_text.split('\n')
                    clean_lines = [line.lstrip('- ').strip() for line in lines if line.strip()]
                    items_text = '\n'.join(clean_lines)
                else:
                    items_text = '\n'.join(items_text_parts)

            # Only add product section if items exist
            if items_text and items_text.strip():
                text += f"{items_text}\n"
                text += "\n"  # Blank line after products
                # Add total after products
                total = order.get("total", "0.00€")
                payment = order.get("payment_method", "Paid")
                if not (order_type == "shopify" and payment.lower() == "cash on delivery"):
                    text += f"Total: {total}"
            else:
                # No products - just add total
                total = order.get("total", "0.00€")
                text += f"Total: {total}"
            
        else:
            # Collapsed view - no products shown
            pass

        # Prepend status lines at the top
        return status_text + text
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building MDG text: %s", exc)
        return f"Error formatting order {order.get('name', 'Unknown')}"


def mdg_initial_keyboard(order: Dict[str, Any]) -> InlineKeyboardMarkup:
    """
    Build initial MDG keyboard with Details button above time request buttons.
    
    Layout:
    [Details ▸]
    [⚡ Asap]
    [🕒 Time picker]
    [🗂 Scheduled orders] (conditional)
    
    Or for multi-vendor:
    [Details ▸]
    [Ask 👩‍🍳 JS]
    [Ask 👨‍🍳 LR]
    """
    try:
        order_id = order["order_id"]
        vendors = order.get("vendors", [])
        logger.info(f"🔍 MDG_INITIAL_KEYBOARD DEBUG - order_id: {order_id}, vendors: {vendors}, len: {len(vendors)}")
        order.setdefault("mdg_expanded", False)  # Track expansion state
        
        is_expanded = order.get("mdg_expanded", False)
        toggle_button = InlineKeyboardButton(
            "◂ Hide" if is_expanded else "Details ▸",
            callback_data=f"mdg_toggle|{order_id}|{int(now().timestamp())}"
        )

        buttons = [[toggle_button]]

        if len(vendors) > 1:
            # Multi-vendor: show vendor selection buttons
            for vendor in vendors:
                shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
                chef_emoji = CHEF_EMOJIS[vendors.index(vendor) % len(CHEF_EMOJIS)]
                buttons.append([InlineKeyboardButton(
                    f"Ask {chef_emoji} {shortcut}",
                    callback_data=f"req_vendor|{order_id}|{vendor}|{int(now().timestamp())}"
                )])
        else:
            # Single vendor: show ASAP/TIME/SCHEDULED buttons (vertical)
            buttons.append([InlineKeyboardButton("⚡ Asap", callback_data=f"req_asap|{order_id}|{int(now().timestamp())}")])
            buttons.append([InlineKeyboardButton("🕒 Time picker", callback_data=f"req_exact|{order_id}|{int(now().timestamp())}")])
            
            # Show "Scheduled orders" button only if recent orders exist
            recent_orders = get_recent_orders_for_same_time(order_id, vendor=None)
            if recent_orders:
                buttons.append([InlineKeyboardButton("🗂 Scheduled orders", callback_data=f"req_scheduled|{order_id}|{int(now().timestamp())}")])

        return InlineKeyboardMarkup(buttons)

    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building initial MDG keyboard: %s", exc)
        return InlineKeyboardMarkup([])


def mdg_time_request_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build MDG time request buttons per assignment requirements. Includes Details button."""
    try:
        order = STATE.get(order_id)
        if not order:
            return InlineKeyboardMarkup([
                [InlineKeyboardButton("Details ▸", callback_data=f"mdg_toggle|{order_id}|{int(now().timestamp())}")],
                [InlineKeyboardButton("⚡ Asap", callback_data=f"req_asap|{order_id}|{int(now().timestamp())}")],
                [InlineKeyboardButton("🕒 Time picker", callback_data=f"req_exact|{order_id}|{int(now().timestamp())}")]
            ])

        vendors = order.get("vendors", [])
        order.setdefault("mdg_expanded", False)  # Track expansion state
        
        is_expanded = order.get("mdg_expanded", False)
        toggle_button = InlineKeyboardButton(
            "◂ Hide" if is_expanded else "Details ▸",
            callback_data=f"mdg_toggle|{order_id}|{int(now().timestamp())}"
        )
        
        buttons = [[toggle_button]]
        
        logger.info("Order %s has vendors: %s (count: %s)", order_id, vendors, len(vendors))

        if len(vendors) > 1:
            logger.info("MULTI-VENDOR detected: %s", vendors)
            for vendor in vendors:
                shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
                chef_emoji = CHEF_EMOJIS[vendors.index(vendor) % len(CHEF_EMOJIS)]
                logger.info("Adding button for vendor: %s (shortcut: %s)", vendor, shortcut)
                buttons.append([InlineKeyboardButton(
                    f"Ask {chef_emoji} {shortcut}",
                    callback_data=f"req_vendor|{order_id}|{vendor}|{int(now().timestamp())}"
                )])
            logger.info("Sending restaurant selection with %s buttons", len(buttons))
            return InlineKeyboardMarkup(buttons)

        logger.info("SINGLE VENDOR detected: %s", vendors)
        buttons.append([InlineKeyboardButton("⚡ Asap", callback_data=f"req_asap|{order_id}|{int(now().timestamp())}")])
        buttons.append([InlineKeyboardButton("🕒 Time picker", callback_data=f"req_exact|{order_id}|{int(now().timestamp())}")])
        
        # Show "Scheduled orders" button only if recent orders exist
        recent_orders = get_recent_orders_for_same_time(order_id, vendor=None)
        if recent_orders:
            buttons.append([InlineKeyboardButton("🗂 Scheduled orders", callback_data=f"req_scheduled|{order_id}|{int(now().timestamp())}")])
        
        return InlineKeyboardMarkup(buttons)

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
        one_hour_ago = now() - timedelta(hours=5)
        recent_orders: List[Dict[str, Any]] = []
        
        logger.info(f"BTN-TIME: Searching for recent orders (current order: {order_id}, vendor: {vendor})")
        logger.info(f"BTN-TIME: One hour ago cutoff: {one_hour_ago}")
        logger.info(f"BTN-TIME: Total orders in STATE: {len(STATE)}")

        for oid, order_data in STATE.items():
            if oid == order_id:
                continue
                
            confirmed_time = order_data.get("confirmed_time")
            confirmed_times = order_data.get("confirmed_times", {})  # Dict of vendor -> time
            status = order_data.get("status")
            created_at = order_data.get("created_at")
            
            logger.info(f"BTN-TIME: Order {oid} - confirmed_time={confirmed_time}, confirmed_times={confirmed_times}, status={status}, created_at={created_at}")
            
            if not confirmed_time:
                logger.info(f"BTN-TIME: Order {oid} - SKIP: no confirmed_time")
                continue
                
            if status == "delivered":
                logger.info(f"BTN-TIME: Order {oid} - SKIP: status is delivered")
                continue
            
            # Normalize created_at to datetime for comparison
            if isinstance(created_at, str):
                try:
                    created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                except:
                    logger.info(f"BTN-TIME: Order {oid} - SKIP: invalid created_at format")
                    continue
            else:
                created_dt = created_at
                
            if created_dt and created_dt > one_hour_ago:
                # Safe access to customer address
                address = order_data.get('customer', {}).get('address', 'Unknown')
                address_short = address.split(',')[0].strip() if ',' in address else address
                
                logger.info(f"BTN-TIME: Order {oid} - PASSED all filters, adding to list")
                
                recent_orders.append({
                    "order_id": oid,
                    "confirmed_time": confirmed_time,
                    "confirmed_times": confirmed_times,  # Include per-vendor times
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
                chef_emoji = CHEF_EMOJIS[recent_orders.index(recent) % len(CHEF_EMOJIS)]
                
                # If multi-vendor reference order, create separate button per vendor
                if len(recent["vendors"]) > 1:
                    for ref_vendor in recent["vendors"]:
                        ref_vendor_shortcut = RESTAURANT_SHORTCUTS.get(ref_vendor, ref_vendor[:2].upper())
                        
                        # Get vendor-specific time from confirmed_times dict, fallback to confirmed_time
                        vendor_time = recent.get("confirmed_times", {}).get(ref_vendor, recent['confirmed_time'])
                        
                        # Build button text: "02 - LR - 14:15 - Grabenga. 15"
                        abbreviated_address = abbreviate_street(recent['address'], max_length=15)
                        button_text = f"{recent['order_num']} - {ref_vendor_shortcut} - {vendor_time} - {abbreviated_address}"
                        
                        # TIER 2: If button exceeds 64 chars (Telegram limit), apply aggressive abbreviation
                        if len(button_text) > 64:
                            import re
                            # Extract house number from original address
                            house_match = re.search(r'\s+(\d+[a-zA-Z]?)$', recent['address'])
                            house_num = f" {house_match.group(1)}" if house_match else ""
                            
                            # Get street name without house number
                            street_only = recent['address'][:house_match.start()] if house_match else recent['address']
                            
                            # Remove all common prefixes and just take first 4 letters
                            street_clean = re.sub(r'^(Doktor-|Professor-|Sankt-|Dr\.-|Prof\.-|St\.-)', '', street_only)
                            
                            # If still compound (has hyphens), take first part
                            if '-' in street_clean:
                                street_clean = street_clean.split('-')[0]
                            
                            # Take first 4 letters only
                            aggressive_abbr = street_clean[:4] + house_num
                            button_text = f"{recent['order_num']} - {ref_vendor_shortcut} - {vendor_time} - {aggressive_abbr}"
                        
                        # Callback contains SINGLE ref vendor shortcut (not comma-separated) and vendor-specific time
                        callback_data = f"order_ref|{order_id}|{recent['order_id']}|{vendor_time}|{ref_vendor_shortcut}"
                        if vendor:
                            # Add current vendor shortcut
                            current_vendor_shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
                            callback_data += f"|{current_vendor_shortcut}"
                        
                        buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
                else:
                    # Single vendor reference order
                    ref_vendor = recent["vendors"][0]
                    ref_vendor_shortcut = RESTAURANT_SHORTCUTS.get(ref_vendor, ref_vendor[:2].upper())
                    
                    # Build button text: "02 - LR - 14:15 - Grabenga. 15"
                    abbreviated_address = abbreviate_street(recent['address'], max_length=15)
                    button_text = f"{recent['order_num']} - {ref_vendor_shortcut} - {recent['confirmed_time']} - {abbreviated_address}"
                    
                    # TIER 2: If button exceeds 64 chars (Telegram limit), apply aggressive abbreviation
                    if len(button_text) > 64:
                        import re
                        # Extract house number from original address
                        house_match = re.search(r'\s+(\d+[a-zA-Z]?)$', recent['address'])
                        house_num = f" {house_match.group(1)}" if house_match else ""
                        
                        # Get street name without house number
                        street_only = recent['address'][:house_match.start()] if house_match else recent['address']
                        
                        # Remove all common prefixes and just take first 4 letters
                        street_clean = re.sub(r'^(Doktor-|Professor-|Sankt-|Dr\.-|Prof\.-|St\.-)', '', street_only)
                        
                        # If still compound (has hyphens), take first part
                        if '-' in street_clean:
                            street_clean = street_clean.split('-')[0]
                        
                        # Take first 4 letters only
                        aggressive_abbr = street_clean[:4] + house_num
                        button_text = f"{recent['order_num']} - {ref_vendor_shortcut} - {recent['confirmed_time']} - {aggressive_abbr}"
                    
                    # Callback contains SINGLE ref vendor shortcut
                    callback_data = f"order_ref|{order_id}|{recent['order_id']}|{recent['confirmed_time']}|{ref_vendor_shortcut}"
                    if vendor:
                        # Add current vendor shortcut
                        current_vendor_shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
                        callback_data += f"|{current_vendor_shortcut}"
                    
                    buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

            # Add Back button
            buttons.append([InlineKeyboardButton("← Back", callback_data="hide")])
        
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
        ref_vendors_str: SINGLE vendor SHORTCUT from reference order (e.g., "LR")
        current_vendor: Current vendor SHORTCUT if multi-vendor order
    """
    try:
        # Convert single ref vendor shortcut to full name
        # Note: After Task 5 split, ref_vendors_str contains SINGLE vendor (not comma-separated)
        ref_vendor_full = shortcut_to_vendor(ref_vendors_str) or ref_vendors_str
        
        # Convert current_vendor shortcut to full name if provided
        current_vendor_full = shortcut_to_vendor(current_vendor) if current_vendor else None
        
        # Calculate +5, +10, +15, +20 times from reference time
        ref_hour, ref_min = map(int, ref_time.split(':'))
        ref_datetime = now().replace(hour=ref_hour, minute=ref_min, second=0, microsecond=0)
        
        buttons: List[List[InlineKeyboardButton]] = []
        
        # Determine if vendors match between current and reference orders
        vendor_matches = False
        if current_vendor_full:
            # Multi-vendor order - check if current vendor matches THIS specific ref vendor
            vendor_matches = (current_vendor_full == ref_vendor_full)
        else:
            # Single vendor order - check if ref vendor matches any current vendor
            order = STATE.get(current_order_id)
            if order:
                current_vendors = order.get("vendors", [])
                vendor_matches = (ref_vendor_full in current_vendors)
        
        # Show "Same time" button ONLY if vendors match
        if vendor_matches:
            # Same vendor - show "Same time" button
            if current_vendor_full:
                same_callback = f"time_same|{current_order_id}|{ref_order_id}|{ref_time}|{current_vendor_full}"
            else:
                same_callback = f"time_same|{current_order_id}|{ref_order_id}|{ref_time}"
            buttons.append([InlineKeyboardButton("🔁 Same time", callback_data=same_callback)])
        # If vendors don't match: NO special button, just show offset buttons below
        
        # Build offset buttons: -5m, -3m, +3m, +5m, +10m, +15m, +20m, +25m (one per row)
        for minutes in [-5, -3, 3, 5, 10, 15, 20, 25]:
            new_time = ref_datetime + timedelta(minutes=minutes)
            time_str = new_time.strftime("%H:%M")
            # Use full vendor name in callback
            vendor_param = f"|{current_vendor_full}" if current_vendor_full else ""
            callback = f"time_relative|{current_order_id}|{time_str}|{ref_order_id}{vendor_param}"
            # Format: "+5m → ⏰ 19:35" or "-5m → ⏰ 19:25"
            button_text = f"{minutes:+d}m → ⏰ {time_str}"
            buttons.append([InlineKeyboardButton(button_text, callback_data=callback)])
        
        # Add Back button
        buttons.append([InlineKeyboardButton("← Back", callback_data="hide")])
        
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


def time_picker_keyboard(order_id: str, action: str, requested_time: Optional[str] = None, vendor: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    Build time picker for various actions.
    
    Args:
        vendor: Full vendor name - will be converted to shortcut for callback data
    """
    try:
        current_time = now()
        if requested_time:
            try:
                req_hour, req_min = map(int, requested_time.split(':'))
                base_time = now().replace(hour=req_hour, minute=req_min)
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
        
        # Determine button prefix based on action
        # RG buttons (later_time, prepare_time) use "in", others use "+"
        if action in ["later_time", "prepare_time"]:
            prefix = "in"
        else:
            prefix = "+"
        
        # Create one button per row (vertical layout)
        for i, time_str in enumerate(intervals):
            minutes = minute_increments[i]
            # Format: "⏰ 18:10 → in 5 m" (RG) or "+5m → ⏰ 18:10" (UPC)
            if prefix == "in":
                button_text = f"⏰ {time_str} → in {minutes} m"
            else:
                button_text = f"+{minutes}m → ⏰ {time_str}"
            
            # Include vendor SHORTCUT in callback if provided (for prepare_time and later_time actions)
            if vendor_shortcut:
                callback = f"{action}|{order_id}|{time_str}|{vendor_shortcut}"
            else:
                callback = f"{action}|{order_id}|{time_str}"
            
            rows.append([InlineKeyboardButton(button_text, callback_data=callback)])
        
        # Add EXACT TIME button at the bottom
        if vendor_shortcut:
            exact_callback = f"vendor_exact_time|{order_id}|{vendor_shortcut}|{action}"
        else:
            exact_callback = f"exact_time|{order_id}|{action}"
        rows.append([InlineKeyboardButton("Time picker🕒", callback_data=exact_callback)])
        
        # Add Back button
        rows.append([InlineKeyboardButton("← Back", callback_data="hide")])

        return InlineKeyboardMarkup(rows)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building time picker: %s", exc)
        return InlineKeyboardMarkup([])


def exact_time_keyboard(order_id: str, vendor: Optional[str] = None) -> InlineKeyboardMarkup:
    """Build exact time picker - shows hours."""
    try:
        current_time = now()
        current_hour = current_time.hour
        current_minute = current_time.minute
        
        # Skip current hour if past minute 57 (no valid 3-minute intervals left)
        start_hour = current_hour + 1 if current_minute >= 57 else current_hour
        
        rows: List[List[InlineKeyboardButton]] = []
        hours: List[str] = [f"{hour:02d}" for hour in range(start_hour, 24)]

        for i in range(0, len(hours), 4):
            row: List[InlineKeyboardButton] = []
            for j in range(4):
                if i + j < len(hours):
                    hour_str = hours[i + j]  # Already just the hour number
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
        current_time = now()
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


# =============================================================================
# ORDER COMBINING SYSTEM
# =============================================================================
def get_assigned_orders(state_dict: dict, exclude_order_id: str) -> List[Dict[str, str]]:
    """
    Get all assigned (not delivered) orders for combining menu (separate entry per vendor for multi-vendor).
    
    Filters STATE for orders with:
    - assigned_to field populated
    - status != "delivered"
    - order_id != exclude_order_id
    
    Creates SEPARATE entries for each vendor in multi-vendor orders (mirrors scheduled orders format).
    
    Args:
        state_dict: STATE dictionary passed from caller
        exclude_order_id: Current order ID to exclude from results
    
    Returns:
        List of dicts with keys: order_id, order_num, vendor_shortcut, 
        confirmed_time, address, assigned_to (user_id), courier_shortcut
        Sorted by courier_shortcut alphabetically
    """
    from utils import RESTAURANT_SHORTCUTS, COURIER_MAP
    import re
    
    assigned = []
    
    for oid, order_data in state_dict.items():
        # Skip current order
        if oid == exclude_order_id:
            continue
        
        # Check if order is assigned and not delivered
        assigned_to = order_data.get("assigned_to")
        status = order_data.get("status", "new")
        
        if not assigned_to or status == "delivered":
            continue
        
        # Extract last 2 digits from order number
        full_name = order_data.get("name", "??")
        order_num = full_name[-2:] if len(full_name) >= 2 else full_name
        
        vendors = order_data.get("vendors", [])
        
        # Get address and zip from customer object (STATE structure)
        customer = order_data.get("customer", {})
        street = customer.get("address", "Unknown")
        zip_code = customer.get("zip", "")
        
        # Get confirmed_times dict for multi-vendor
        confirmed_times = order_data.get("confirmed_times")
        
        # Get courier name using DRIVERS reverse lookup
        courier_name = None
        for name, uid in DRIVERS.items():
            if uid == assigned_to:
                courier_name = name
                break
        
        # Use full courier name ("Bee 1", "Bee 2", "Bee 3")
        if not courier_name:
            courier_name = "??"
        
        # For multi-vendor orders, create SEPARATE entry per vendor (like scheduled orders)
        if len(vendors) > 1 and confirmed_times:
            for vendor in vendors:
                vendor_shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
                vendor_time = confirmed_times.get(vendor, "??:??")
                
                # Start with full street name (no house number, no zip)
                final_address = street
                
                # Build button text: {address} - {time} - {vendor}  |  {courier}
                button_text = f"{final_address} - {vendor_time} - {vendor_shortcut}  |  {courier_name}"
                
                # If > 30 chars (single-line limit), reduce street name letter-by-letter
                while len(button_text) > 30 and len(final_address) > 1:
                    final_address = final_address[:-1]
                    button_text = f"{final_address} - {vendor_time} - {vendor_shortcut}  |  {courier_name}"
                
                assigned.append({
                    "order_id": oid,
                    "order_num": order_num,
                    "vendor_shortcut": vendor_shortcut,
                    "confirmed_time": vendor_time,
                    "address": final_address,
                    "assigned_to": assigned_to,
                    "courier_name": courier_name
                })
        else:
            # Single vendor order
            vendor_shortcut = RESTAURANT_SHORTCUTS.get(vendors[0], vendors[0][:2].upper()) if vendors else "??"
            confirmed_time = order_data.get("confirmed_time", "??:??")
            
            # Start with full street name (no house number, no zip)
            final_address = street
            
            # Build button text: {address} - {time} - {vendor}  |  {courier}
            button_text = f"{final_address} - {confirmed_time} - {vendor_shortcut}  |  {courier_name}"
            
            # If > 30 chars (single-line limit), reduce street name letter-by-letter
            while len(button_text) > 30 and len(final_address) > 1:
                final_address = final_address[:-1]
                button_text = f"{final_address} - {confirmed_time} - {vendor_shortcut}  |  {courier_name}"
            
            assigned.append({
                "order_id": oid,
                "order_num": order_num,
                "vendor_shortcut": vendor_shortcut,
                "confirmed_time": confirmed_time,
                "address": final_address,
                "assigned_to": assigned_to,
                "courier_name": courier_name
            })
    
    # Sort by courier name (groups orders by courier together)
    assigned.sort(key=lambda x: x["courier_name"])
    
    return assigned


def generate_group_id() -> str:
    """
    Generate unique group ID based on timestamp.
    
    Format: group_YYYYMMDD_HHMMSS
    
    Returns:
        Unique group identifier string
    """
    return f"group_{now().strftime('%Y%m%d_%H%M%S')}"


def get_next_group_color(state_dict: dict) -> str:
    """
    Get next available group color from rotation.
    
    Checks existing groups in STATE and returns next color in sequence.
    Rotates through: 🟣🔵🟢🟡🟠🔴🟤 (max 7 groups simultaneously).
    
    Args:
        state_dict: STATE dictionary passed from caller
    
    Returns:
        Color emoji string
    """
    # Get all currently used colors
    used_colors = set()
    for order_data in state_dict.values():
        color = order_data.get("group_color")
        if color:
            used_colors.add(color)
    
    # Find first unused color
    for color in GROUP_COLORS:
        if color not in used_colors:
            return color
    
    # If all colors used, rotate from beginning
    return GROUP_COLORS[0]


def get_group_orders(state_dict: dict, group_id: str) -> List[Dict[str, Any]]:
    """
    Get all orders in a specific group (excluding delivered orders).
    
    Args:
        state_dict: STATE dictionary passed from caller
        group_id: Group identifier
    
    Returns:
        List of order dicts with order_id and full order data
    """
    group_orders = []
    for oid, order_data in state_dict.items():
        if order_data.get("group_id") == group_id and order_data.get("status") != "delivered":
            group_orders.append({
                "order_id": oid,
                "data": order_data
            })
    
    return group_orders


def build_combine_keyboard(order_id: str, assigned_orders: List[Dict[str, str]]) -> InlineKeyboardMarkup:
    """
    Build inline keyboard with assigned orders for combining.
    
    Each button shows: {num} - {vendor} - {time} - {address} ({courier})
    Address ALREADY abbreviated by get_assigned_orders() - just use it.
    
    Args:
        order_id: Current order ID (for callback data)
        assigned_orders: List from get_assigned_orders() with PRE-ABBREVIATED addresses
    
    Returns:
        InlineKeyboardMarkup with order buttons + Back button
    """
    buttons = []
    
    for order in assigned_orders:
        # Use PRE-TRUNCATED address from get_assigned_orders() (already fits 30-char limit)
        address = order["address"]
        
        # Build button text: {address} - {time} - {vendor}  |  {courier}
        button_text = f"{address} - {order['confirmed_time']} - {order['vendor_shortcut']}  |  {order['courier_name']}"
        
        # Hard-truncate to 64 chars max (Telegram button limit) as safety fallback
        if len(button_text) > 64:
            button_text = button_text[:61] + "..."
        
        # Callback: combine_with|{order_id}|{target_order_id}|{timestamp}
        callback_data = f"combine_with|{order_id}|{order['order_id']}|{int(now().timestamp())}"
        
        buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    # Add Back button
    buttons.append([InlineKeyboardButton("← Back", callback_data=f"hide|{order_id}")])
    
    return InlineKeyboardMarkup(buttons)


async def show_combine_orders_menu(state_dict, order_id: str, chat_id: int, message_id: int):
    """
    Show menu to select assigned order to combine with (Phase 2 implementation).
    
    Displays all assigned (not delivered) orders sorted by courier.
    Each button shows: {num} - {vendor} - {time} - {address} ({courier})
    
    Args:
        state_dict: STATE dictionary from main.py
        order_id: Current order to combine
        chat_id: MDG chat ID
        message_id: Message to edit with combine menu
    """
    from utils import safe_edit_message
    
    logger.info(f"[PHASE 2] show_combine_orders_menu for order {order_id}")
    
    # Get all assigned orders (excluding current)
    assigned_orders = get_assigned_orders(state_dict, exclude_order_id=order_id)
    
    # If no assigned orders, button shouldn't have been shown - just return silently
    if not assigned_orders:
        logger.info(f"No assigned orders available - button should not have been shown")
        return
    
    # Get current order info for header
    order = state_dict.get(order_id)
    if not order:
        logger.warning(f"Order {order_id} not found in STATE")
        return
    
    # Extract last 2 digits from order name (e.g., "dishbee #26" -> "26")
    full_name = order.get("name", "??")
    order_num = full_name[-2:] if len(full_name) >= 2 else full_name
    
    # Get street from current order for header (no truncation)
    customer = order.get("customer", {})
    street = customer.get("address", "Unknown")
    
    # Build keyboard
    keyboard = build_combine_keyboard(order_id, assigned_orders)
    
    # Edit message with combine menu - show street and order number
    text = f"📌 Combine 🗺️ {street} (🔖 {order_num}) with:"
    
    logger.info(f"Showing {len(assigned_orders)} assigned orders for combining")
    
    # Send NEW message (don't edit MDG-CONF)
    from utils import safe_send_message
    msg = await safe_send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=keyboard
    )
    
    # Track new message for cleanup
    order = state_dict.get(order_id)
    if order and msg:
        order.setdefault("mdg_additional_messages", []).append(msg.message_id)



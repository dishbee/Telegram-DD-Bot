# -*- coding: utf-8 -*-
"""RG (Restaurant Group) helpers."""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

# Timezone configuration for Passau, Germany (Europe/Berlin)
TIMEZONE = ZoneInfo("Europe/Berlin")

def now() -> datetime:
    """Get current time in Passau timezone (Europe/Berlin)."""
    return datetime.now(TIMEZONE)

# Restaurant shortcut mapping for callback data compression
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

# Reverse mapping for decoding
SHORTCUT_TO_VENDOR = {v: k for k, v in RESTAURANT_SHORTCUTS.items()}


def build_vendor_summary_text(order: Dict[str, Any], vendor: str) -> str:
    """Build vendor short summary (default collapsed state)."""
    try:
        from utils import build_status_lines
        
        # Get order type first
        order_type = order.get("order_type", "shopify")
        
        # Build status lines - for DD/PF, status ends without newline
        status_text = build_status_lines(order, "rg", RESTAURANT_SHORTCUTS, vendor=vendor)
        if order_type in ["smoothr_dnd", "smoothr_lieferando"]:
            status_text = status_text.rstrip('\n')  # Remove trailing newline for DD/PF
        
        # Get order number display
        # For Smoothr D&D App orders (3 digits): show all 3 digits
        # For Shopify/Lieferando orders: show last 2 digits
        if order_type == "smoothr_dnd":
            order_number = order['name']  # Full 3 digits (e.g., "556")
        else:
            order_number = order['name'][-2:]  # Last 2 digits

        # Build message with order number
        if order_type in ["smoothr_dnd", "smoothr_lieferando"]:
            # DD/PF: No blank line after status, blank line after order number
            lines = [f"🔖 {order_number}", ""]
            customer_name = order.get('customer', {}).get('name', 'Unknown')
            address = order.get('customer', {}).get('address', 'No address')
            lines.append(f"👤 {customer_name}")
            lines.append(f"🗺️ {address}")
        else:
            # Shopify: Blank line after order number
            lines = [f"🔖 {order_number}", ""]

        # Get vendor items - ONLY show products if they exist
        vendor_items = order.get("vendor_items", {}).get(vendor, [])
        if vendor_items:
            for item in vendor_items:
                clean_item = item.lstrip('- ').strip()
                lines.append(clean_item)
            lines.append("")  # Empty line after products

        # Add customer note if exists
        note = order.get("note", "")
        if note:
            lines.append(f"❕ Note: {note}")

        # Join lines and prepend status
        text = "\n".join(lines)
        return status_text + text
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building vendor summary: %s", exc)
        return f"Error formatting order for {vendor}"


def build_vendor_details_text(order: Dict[str, Any], vendor: str) -> str:
    """Build vendor full details (expanded state)."""
    try:
        summary = build_vendor_summary_text(order, vendor)

        customer_name = order['customer']['name']
        phone = order['customer']['phone']
        
        # Handle both string (Shopify ISO format) and datetime (Smoothr) for created_at
        created_at = order.get('created_at', now())
        if isinstance(created_at, str):
            # Shopify: Extract HH:MM from ISO string "YYYY-MM-DDTHH:MM:SS..."
            order_time = created_at[11:16]
        else:
            # Smoothr: datetime object
            order_time = created_at.strftime('%H:%M')
        
        # Format address: street + building (zip)
        address = order['customer']['address']
        address_parts = address.split(',')
        if len(address_parts) >= 2:
            street_part = address_parts[0].strip()
            # Removed zip code display as requested
            formatted_address = street_part
        else:
            formatted_address = address.strip()

        details = f"{summary}\n"
        
        # For Shopify orders, add customer/address here (not in summary)
        # For DD/PF orders, skip (already in summary to avoid duplication)
        order_type = order.get("order_type", "shopify")
        if order_type == "shopify":
            details += f"👤 {customer_name}\n"
            details += f"🗺️ {formatted_address}\n"
        
        details += f"📞 {phone}\n"
        details += f"⏰ Ordered at: {order_time}"

        return details
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building vendor details: %s", exc)
        return f"Error formatting details for {vendor}"


def vendor_time_keyboard(order_id: str, vendor: str) -> InlineKeyboardMarkup:
    """Build time request buttons for a specific vendor (vertical layout with scheduled orders)."""
    from mdg import get_recent_orders_for_same_time
    
    buttons = []
    buttons.append([InlineKeyboardButton("⚡ Asap", callback_data=f"vendor_asap|{order_id}|{vendor}")])
    buttons.append([InlineKeyboardButton("🕒 Time picker", callback_data=f"req_exact|{order_id}|{vendor}")])
    
    # Show "Scheduled orders" button only if recent orders exist for this vendor
    recent_orders = get_recent_orders_for_same_time(order_id, vendor=vendor)
    if recent_orders:
        buttons.append([InlineKeyboardButton("🗂 Scheduled orders", callback_data=f"req_scheduled|{order_id}|{vendor}")])
    
    buttons.append([InlineKeyboardButton("← Back", callback_data="hide")])
    
    return InlineKeyboardMarkup(buttons)


def vendor_keyboard(order_id: str, vendor: str, expanded: bool) -> InlineKeyboardMarkup:
    """Build vendor toggle keyboard."""
    try:
        toggle_text = "◂ Hide" if expanded else "Details ▸"
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_text, callback_data=f"toggle|{order_id}|{vendor}|{int(now().timestamp())}")]
        ])
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building vendor keyboard: %s", exc)
        return InlineKeyboardMarkup([])


def restaurant_response_keyboard(request_type: str, order_id: str, vendor: str) -> InlineKeyboardMarkup:
    """Build restaurant response buttons for time requests."""
    try:
        rows = []
        
        if request_type == "ASAP":
            rows.append([
                InlineKeyboardButton("⏰ Yes at:", callback_data=f"prepare|{order_id}|{vendor}")
            ])
        else:
            rows.append([
                InlineKeyboardButton("Works 👍", callback_data=f"works|{order_id}|{vendor}")
            ])
            rows.append([
                InlineKeyboardButton("⏰ Later at", callback_data=f"later|{order_id}|{vendor}")
            ])
        
        rows.append([
            InlineKeyboardButton("🚩 Problem", callback_data=f"wrong|{order_id}|{vendor}")
        ])
        
        return InlineKeyboardMarkup(rows)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building restaurant response keyboard: %s", exc)
        return InlineKeyboardMarkup([])


def vendor_exact_time_keyboard(order_id: str, vendor: str, action: str) -> InlineKeyboardMarkup:
    """Build exact time picker for vendors - shows hours."""
    try:
        current_time = now()
        current_hour = current_time.hour
        current_minute = current_time.minute
        
        # Skip current hour if past minute 57 (no valid 3-minute intervals left)
        start_hour = current_hour + 1 if current_minute >= 57 else current_hour
        
        rows: List[List[InlineKeyboardButton]] = []
        hours: List[str] = [f"{hour:02d}" for hour in range(start_hour, 24)]

        # Use shortcut to compress callback data
        vendor_short = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2])
        
        # Build hour buttons (3 per row)
        for i in range(0, len(hours), 3):
            row = []
            for j in range(i, min(i + 3, len(hours))):
                hour_value = hours[j]  # Already just the hour number
                callback_data = f"vendor_exact_hour|{order_id}|{hour_value}|{vendor_short}|{action}"
                row.append(InlineKeyboardButton(hours[j], callback_data=callback_data))
            rows.append(row)
        
        # Add Back button
        rows.append([InlineKeyboardButton("← Back", callback_data="hide")])

        return InlineKeyboardMarkup(rows)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building vendor exact time keyboard: %s", exc)
        return InlineKeyboardMarkup([])


def vendor_exact_hour_keyboard(order_id: str, hour: int, vendor: str, action: str) -> InlineKeyboardMarkup:
    """Build minute picker for vendors after hour selection."""
    try:
        rows: List[List[InlineKeyboardButton]] = []
        minutes: List[str] = [f"{minute:02d}" for minute in range(0, 60, 3)]

        # Use shortcut to compress callback data
        vendor_short = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2])
        
        # Build minute buttons (4 per row)
        for i in range(0, len(minutes), 4):
            row = []
            for j in range(i, min(i + 4, len(minutes))):
                time_str = f"{hour:02d}:{minutes[j]}"
                callback_data = f"vendor_exact_selected|{order_id}|{time_str}|{vendor_short}|{action}"
                row.append(InlineKeyboardButton(minutes[j], callback_data=callback_data))
            rows.append(row)

        # Add back button
        back_callback = f"vendor_exact_back|{order_id}|{vendor_short}|{action}"
        rows.append([InlineKeyboardButton("◂ Back to hours", callback_data=back_callback)])

        return InlineKeyboardMarkup(rows)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building vendor exact hour keyboard: %s", exc)
        return InlineKeyboardMarkup([])

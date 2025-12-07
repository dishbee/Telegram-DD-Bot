# -*- coding: utf-8 -*-
"""RG (Restaurant Group) helpers."""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from utils import format_phone_for_android

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
    "Hello Burrito": "HB",
    "Kahaani": "KA",
    "i Sapori della Toscana": "SA",
    "Leckerolls": "LR",
    "dean & david": "DD",
    "Pommes Freunde": "PF",
    "Wittelsbacher Apotheke": "AP",
    "Safi": "SF"
}

# Reverse mapping for decoding
SHORTCUT_TO_VENDOR = {v: k for k, v in RESTAURANT_SHORTCUTS.items()}


def build_vendor_summary_text(order: Dict[str, Any], vendor: str) -> str:
    """Build vendor short summary (default collapsed state)."""
    try:
        from utils import build_status_lines
        
        # Get order type first
        order_type = order.get("order_type", "shopify")
        
        # Build status lines
        status_text = build_status_lines(order, "rg", RESTAURANT_SHORTCUTS, vendor=vendor)
        
        # Status lines come with \n\n - we need to remove BOTH for proper formatting
        # (separator should appear on next line with NO blank line)
        if status_text.endswith('\n\n'):
            status_text = status_text[:-2]  # Remove both newlines
        elif status_text.endswith('\n'):
            status_text = status_text[:-1]  # Remove single newline if present
        
        # Build message body based on order type
        if order_type == "shopify":
            # NEW SHOPIFY FORMAT: separator + address + products
            lines = ["────────────────", ""]  # Separator with blank line
            
            # Add street address (first part before comma)
            address = order.get('customer', {}).get('address', 'No address')
            address_parts = address.split(',')
            street = address_parts[0].strip() if address_parts else address.strip()
            lines.append(f"🗺️ {street}")
            lines.append("")  # Blank line after address
            
        else:
            # DD/PF: separator + address first, then customer
            lines = ["────────────────", ""]  # Separator with blank line
            
            # Address FIRST, then customer name
            address = order.get('customer', {}).get('address', 'No address')
            customer_name = order.get('customer', {}).get('name', 'Unknown')
            lines.append(f"🗺️ {address}")
            lines.append(f"👤 {customer_name}")
            lines.append("")  # Blank line after customer info

        # Get vendor items - ONLY show products if they exist AND not PF Lieferando
        # PF Lieferando uses product count only, not item details
        vendor_items = order.get("vendor_items", {}).get(vendor, [])
        if vendor_items and order_type != "smoothr_lieferando":
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
        from utils import build_status_lines
        
        # Get order type first
        order_type = order.get("order_type", "shopify")
        
        # Build status lines
        status_text = build_status_lines(order, "rg", RESTAURANT_SHORTCUTS, vendor=vendor)
        
        # Remove one newline from status for proper separator spacing
        if order_type == "shopify":
            if status_text.endswith('\n\n'):
                status_text = status_text[:-1]  # Remove one newline (keep 1)
        
        # For DD/PF: status has 2 newlines, we want only 1 before order number
        if order_type in ["smoothr_dnd", "smoothr_lieferando"]:
            if status_text.endswith('\n\n'):
                status_text = status_text[:-1]  # Remove one newline (keep 1)
        
        # Build message body based on order type
        if order_type == "shopify":
            # NEW SHOPIFY FORMAT: separator + address + products + customer/phone/time
            lines = ["────────────────", ""]  # Separator with blank line
            
            # Add street address (just street part, no zip)
            address = order.get('customer', {}).get('address', 'No address')
            address_parts = address.split(',')
            street = address_parts[0].strip() if address_parts else address.strip()
            lines.append(f"🗺️ {street}")
            lines.append("")  # Blank line after address
            
        else:
            # DD/PF: separator + address first, then customer
            lines = ["────────────────", ""]  # Separator with blank line
            
            # Address FIRST, then customer name
            address = order.get('customer', {}).get('address', 'No address')
            customer_name = order.get('customer', {}).get('name', 'Unknown')
            lines.append(f"🗺️ {address}")
            lines.append(f"👤 {customer_name}")
            lines.append("")  # Blank line after customer info

        # Get vendor items
        vendor_items = order.get("vendor_items", {}).get(vendor, [])
        if vendor_items:
            for item in vendor_items:
                clean_item = item.lstrip('- ').strip()
                lines.append(clean_item)
            lines.append("")  # Blank line after products

        # Add customer note if exists
        note = order.get("note", "")
        if note:
            lines.append(f"❕ Note: {note}")
            lines.append("")  # Blank line after note

        # Add phone/time - for all order types in details view
        if order_type == "shopify":
            # Shopify: add customer name, phone, confirmed time
            customer_name = order.get('customer', {}).get('name', 'Unknown')
            lines.append(f"👤 {customer_name}")
            
            phone = order.get('customer', {}).get('phone', 'N/A')
            lines.append(f"📞 {format_phone_for_android(phone)}")
            
            # Always show original order time (confirmed time is in status line)
            created_at = order.get('created_at', now())
            if isinstance(created_at, str):
                order_time = created_at[11:16]
            else:
                order_time = created_at.strftime('%H:%M')
            lines.append(f"⏰ Ordered at: {order_time}")
        else:
            # DD/PF: add phone and order time (customer already shown above)
            phone = order.get('customer', {}).get('phone', 'N/A')
            lines.append(f"📞 {format_phone_for_android(phone)}")
            
            # Always show original order time (confirmed time is in status line)
            created_at = order.get('created_at', now())
            if isinstance(created_at, str):
                order_time = created_at[11:16]
            else:
                order_time = created_at.strftime('%H:%M')
            lines.append(f"⏰ Ordered at: {order_time}")

        # Join lines and prepend status
        text = "\n".join(lines)
        return status_text + text
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


def vendor_keyboard(order_id: str, vendor: str, expanded: bool, order: Optional[Dict[str, Any]] = None) -> InlineKeyboardMarkup:
    """Build vendor toggle keyboard with conditional Problem button."""
    try:
        toggle_text = "◂ Hide" if expanded else "Details ▸"
        buttons = [
            [InlineKeyboardButton(toggle_text, callback_data=f"toggle|{order_id}|{vendor}|{int(now().timestamp())}")]
        ]
        
        # Add Problem button ONLY if:
        # 1. Vendor has confirmed time (vendor in confirmed_times)
        # 2. Order is NOT delivered yet (status != "delivered")
        if order:
            vendor_confirmed = vendor in order.get("confirmed_times", {})
            order_delivered = order.get("status") == "delivered"
            
            if vendor_confirmed and not order_delivered:
                buttons.append([
                    InlineKeyboardButton("🚩 Problem", callback_data=f"wrong|{order_id}|{vendor}")
                ])
        
        return InlineKeyboardMarkup(buttons)
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

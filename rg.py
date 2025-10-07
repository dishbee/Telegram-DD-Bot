"""RG (Restaurant Group) helpers."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

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
        order_type = order.get("order_type", "shopify")

        if order_type == "shopify":
            order_number = order['name'][-2:] if len(order['name']) >= 2 else order['name']
        else:
            address_parts = order['customer']['address'].split(',')
            order_number = address_parts[0] if address_parts else "Unknown"

        # Get vendor items and clean up formatting
        vendor_items = order.get("vendor_items", {}).get(vendor, [])
        if vendor_items:
            # Remove "- " prefix from each item line
            cleaned_items = []
            for item in vendor_items:
                cleaned_item = item.lstrip('- ').strip()
                cleaned_items.append(cleaned_item)
            items_text = "\n".join(cleaned_items)
        else:
            items_text = order.get("items_text", "")

        note = order.get("note", "")

        # Build message
        text = f"🔖 Order #{order_number}\n\n"
        text += items_text
        
        if note:
            text += f"\n\n❕ Note: {note}"

        return text
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building vendor summary: %s", exc)
        return f"Error formatting order for {vendor}"


def build_vendor_details_text(order: Dict[str, Any], vendor: str) -> str:
    """Build vendor full details (expanded state)."""
    try:
        summary = build_vendor_summary_text(order, vendor)

        customer_name = order['customer']['name']
        phone = order['customer']['phone']
        order_time = order.get('created_at', datetime.now()).strftime('%H:%M')
        
        # Format address: street + building (zip)
        address = order['customer']['address']
        address_parts = address.split(',')
        if len(address_parts) >= 2:
            street_part = address_parts[0].strip()
            # Removed zip code display as requested
            formatted_address = street_part
        else:
            formatted_address = address.strip()

        details = f"{summary}\n\n"
        details += f"🧑 {customer_name}\n"
        details += f"🗺️ {formatted_address}\n"
        details += f"📞 {phone}\n"
        details += f"⏰ Ordered at: {order_time}"

        return details
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building vendor details: %s", exc)
        return f"Error formatting details for {vendor}"


def vendor_time_keyboard(order_id: str, vendor: str) -> InlineKeyboardMarkup:
    """Build time request buttons for a specific vendor."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Request ASAP", callback_data=f"vendor_asap|{order_id}|{vendor}"),
            InlineKeyboardButton("Request TIME", callback_data=f"vendor_time|{order_id}|{vendor}")
        ]
    ])


def vendor_keyboard(order_id: str, vendor: str, expanded: bool) -> InlineKeyboardMarkup:
    """Build vendor toggle keyboard."""
    try:
        toggle_text = "◂ Hide" if expanded else "Details ▸"
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_text, callback_data=f"toggle|{order_id}|{vendor}|{int(datetime.now().timestamp())}")]
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
                InlineKeyboardButton("Will prepare at", callback_data=f"prepare|{order_id}|{vendor}")
            ])
        else:
            rows.append([
                InlineKeyboardButton("Works 👍", callback_data=f"works|{order_id}|{vendor}"),
                InlineKeyboardButton("Later at", callback_data=f"later|{order_id}|{vendor}")
            ])

        rows.append([
            InlineKeyboardButton("Something is wrong", callback_data=f"wrong|{order_id}|{vendor}")
        ])

        return InlineKeyboardMarkup(rows)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error building restaurant response keyboard: %s", exc)
        return InlineKeyboardMarkup([])


def vendor_exact_time_keyboard(order_id: str, vendor: str, action: str) -> InlineKeyboardMarkup:
    """Build exact time picker for vendors - shows hours."""
    try:
        current_hour = datetime.now().hour
        rows: List[List[InlineKeyboardButton]] = []
        hours: List[str] = [f"{hour:02d}:XX" for hour in range(current_hour, 24)]

        # Use shortcut to compress callback data
        vendor_short = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2])
        
        # Build hour buttons (3 per row)
        for i in range(0, len(hours), 3):
            row = []
            for j in range(i, min(i + 3, len(hours))):
                hour_value = str(current_hour + (j - i) + (i // 3) * 3)
                callback_data = f"vendor_exact_hour|{order_id}|{hour_value}|{vendor_short}|{action}"
                row.append(InlineKeyboardButton(hours[j], callback_data=callback_data))
            rows.append(row)

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

"""RG (Restaurant Group) helpers."""# rg.py - Restaurant Group functions for Telegram Dispatch Bot



import logging# Currently, most RG logic is handled in the webhook handler

from datetime import datetime# This file is prepared for future RG-specific functions

from typing import Any, Dict, List

from utils import logger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


def build_vendor_summary_text(order: Dict[str, Any]) -> str:
    """Build the vendor summary text for RG notifications."""
    lines: List[str] = []
    vendors = order.get("vendors", [])
    customer = order.get("customer", {})
    order_num = order.get("name", "")[-2:]

    lines.append(f"Order #{order_num}")
    if customer.get("address"):
        lines.append(customer["address"])

    for vendor in vendors:
        lines.append(f"\n{vendor}:")
        for item in order.get("vendor_items", {}).get(vendor, []):
            clean_item = item.lstrip('- ').strip()
            lines.append(clean_item)

    total = order.get("total")
    if total:
        lines.append(f"\nTotal: {total}")

    return "\n".join(lines)


def build_vendor_details_text(order: Dict[str, Any]) -> str:
    """Build detailed order text for RG interactions."""
    customer = order.get("customer", {})
    requested_time = order.get("requested_time")
    confirmed_time = order.get("confirmed_time")
    created_at = order.get("created_at")

    lines = [f"Customer: {customer.get('name', 'Unknown')}"]

    if requested_time:
        lines.append(f"Requested Time: {requested_time}")
    if confirmed_time:
        lines.append(f"Confirmed Time: {confirmed_time}")
    if created_at:
        order_time = created_at.strftime("%H:%M") if isinstance(created_at, datetime) else str(created_at)
        lines.append(f"Order Time: {order_time}")

    phone = customer.get("phone")
    if phone and phone != "N/A":
        lines.append(f"Phone: {phone}")

    address = customer.get("address")
    if address:
        lines.append(f"Address: {address}")

    note = order.get("note")
    if note:
        lines.append(f"Note: {note}")

    tips = order.get("tips")
    if tips and float(tips) > 0:
        lines.append(f"Tip: {float(tips):.2f}€")

    return "\n".join(lines)


def vendor_time_keyboard(order_id: str, vendor: str) -> InlineKeyboardMarkup:
    """Build RG vendor time adjustment keyboard."""
    """RG (Restaurant Group) helpers."""

    import logging
    from datetime import datetime
    from typing import Any, Dict

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    logger = logging.getLogger(__name__)


    def build_vendor_summary_text(order: Dict[str, Any], vendor: str) -> str:
        """Build vendor short summary (default collapsed state)."""
        try:
            order_type = order.get("order_type", "shopify")

            if order_type == "shopify":
                order_number = order['name'][-2:] if len(order['name']) >= 2 else order['name']
            else:
                address_parts = order['customer']['address'].split(',')
                order_number = address_parts[0] if address_parts else "Unknown"

            vendor_items = order.get("vendor_items", {}).get(vendor, [])
            if vendor_items:
                items_text = "\n".join(vendor_items)
            else:
                items_text = order.get("items_text", "")

            note = order.get("note", "")

            text = f"Order {order_number}\n"
            text += f"{items_text}"
            if note:
                text += f"\nNote: {note}"

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
            address = order['customer']['address']

            details = f"{summary}\n\n"
            details += f"Customer: {customer_name}\n"
            details += f"Phone: {phone}\n"
            details += f"Time of order: {order_time}\n"
            details += f"Address: {address}"

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

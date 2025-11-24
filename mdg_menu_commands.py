# -*- coding: utf-8 -*-
"""
Menu command handlers for /scheduled and /assigned commands.
Generates list messages with full street names (no truncation).
"""

from datetime import timedelta
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Dict, List


def build_scheduled_list_message(state_dict: dict, now_func) -> str:
    """
    Build list of scheduled orders (confirmed but not assigned, last 5 hours).
    Shows full street names (no truncation).
    
    Args:
        state_dict: STATE dictionary from main.py
        now_func: Function that returns current datetime
        
    Returns:
        Formatted message text
    """
    from utils import RESTAURANT_SHORTCUTS
    
    # Filter confirmed orders from last 5 hours
    cutoff = now_func() - timedelta(hours=5)
    scheduled = []
    
    for oid, order in state_dict.items():
        # Must have confirmed_times, not delivered, within 5 hours
        confirmed_times = order.get("confirmed_times", {})
        if not confirmed_times:
            continue
        # Skip only delivered orders, not assigned ones
        if order.get("status") == "delivered":
            continue
        created_at = order.get("created_at")
        if not created_at or created_at < cutoff:
            continue
        
        # Get order number (last 2 digits)
        order_num = order.get("name", "")[-2:] if len(order.get("name", "")) >= 2 else order.get("name", "??")
        
        # Get vendors and time
        vendors = order.get("vendors", [])
        if len(vendors) > 1:
            # Multi-vendor: show combo
            vendor_str = "+".join([RESTAURANT_SHORTCUTS.get(v, v[:2].upper()) for v in vendors])
            # Use first vendor's time
            time = list(confirmed_times.values())[0]
        else:
            # Single vendor
            vendor_str = RESTAURANT_SHORTCUTS.get(vendors[0], vendors[0][:2].upper()) if vendors else "??"
            time = confirmed_times.get(vendors[0], "??:??") if vendors else "??:??"
        
        # Get FULL street (no truncation)
        street = order.get("customer", {}).get("address", "Unknown")
        
        scheduled.append({
            "num": order_num,
            "vendor": vendor_str,
            "time": time,
            "street": street
        })
    
    # Sort by time
    scheduled.sort(key=lambda x: x["time"])
    
    # Build message
    if not scheduled:
        return "🗂️ Scheduled orders\n\nNo scheduled orders in the last 5 hours."
    
    lines = ["🗂️ Scheduled orders", ""]
    for item in scheduled:
        lines.append(f"{item['num']} - {item['vendor']} - {item['time']} - {item['street']}")
    
    return "\n".join(lines)


def build_assigned_list_message(state_dict: dict, drivers_dict: dict) -> str:
    """
    Build list of assigned orders (not delivered).
    NO order numbers, full street names (no truncation).
    
    Args:
        state_dict: STATE dictionary from main.py
        drivers_dict: DRIVERS dictionary for courier name lookup
        
    Returns:
        Formatted message text
    """
    from utils import RESTAURANT_SHORTCUTS
    
    assigned = []
    
    for oid, order in state_dict.items():
        # Must be assigned and not delivered
        if not order.get("assigned_to"):
            continue
        if order.get("status") == "delivered":
            continue
        
        # Get courier name
        courier_name = None
        for name, uid in drivers_dict.items():
            if uid == order["assigned_to"]:
                courier_name = name
                break
        if not courier_name:
            courier_name = "??"
        
        # Get vendors and times
        vendors = order.get("vendors", [])
        confirmed_times = order.get("confirmed_times", {})
        
        # Get FULL street (no truncation)
        street = order.get("customer", {}).get("address", "Unknown")
        
        # For multi-vendor, create separate line per vendor
        if len(vendors) > 1:
            for vendor in vendors:
                vendor_short = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
                time = confirmed_times.get(vendor, "??:??")
                assigned.append({
                    "vendor": vendor_short,
                    "time": time,
                    "street": street,
                    "courier": courier_name
                })
        else:
            vendor_short = RESTAURANT_SHORTCUTS.get(vendors[0], vendors[0][:2].upper()) if vendors else "??"
            time = confirmed_times.get(vendors[0], "??:??") if vendors else "??:??"
            assigned.append({
                "vendor": vendor_short,
                "time": time,
                "street": street,
                "courier": courier_name
            })
    
    # Sort by courier name
    assigned.sort(key=lambda x: x["courier"])
    
    # Build message
    if not assigned:
        return "📌 Assigned orders\n\nNo assigned orders awaiting delivery."
    
    lines = ["📌 Assigned orders", ""]
    for item in assigned:
        lines.append(f"{item['vendor']} - {item['time']} - {item['street']}  |  {item['courier']}")
    
    return "\n".join(lines)


def close_button_keyboard() -> InlineKeyboardMarkup:
    """Single close button for list messages."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✖️ Close", callback_data="close_temp")
    ]])

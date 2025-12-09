# -*- coding: utf-8 -*-
"""
Menu command handlers for /scheduled and /assigned commands.
Generates list messages with full street names (no truncation).
"""

from datetime import timedelta, datetime
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Dict, List


def build_scheduled_list_message(state_dict: dict, now_func) -> str:
    """
    Build list of scheduled orders (confirmed, not delivered, from today only).
    Shows street names only (no zip code).
    Format: [time - street - vendor]
    
    Args:
        state_dict: STATE dictionary from main.py
        now_func: Function that returns current datetime
        
    Returns:
        Formatted message text
    """
    from utils import RESTAURANT_SHORTCUTS
    
    # Filter confirmed orders from TODAY only (after 00:01)
    today_start = now_func().replace(hour=0, minute=1, second=0, microsecond=0)
    scheduled = []
    
    for oid, order in state_dict.items():
        # Check BOTH confirmed_time (Shopify) AND confirmed_times (Smoothr/PF)
        confirmed_time = order.get("confirmed_time")
        confirmed_times = order.get("confirmed_times", {})
        
        has_confirmation = confirmed_time or (confirmed_times and any(confirmed_times.values()))
        if not has_confirmation:
            continue
        
        # Skip delivered AND removed orders
        if order.get("status") in ["delivered", "removed"]:
            continue
        
        created_at = order.get("created_at")
        # Convert created_at to datetime if it's a string (Shopify orders use ISO strings)
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except:
                continue
        
        # TODAY filter: only show orders from today
        if not created_at or created_at < today_start:
            continue
        
        # Get vendors and time
        vendors = order.get("vendors", [])
        if len(vendors) > 1:
            # Multi-vendor: show combo
            vendor_str = "+".join([RESTAURANT_SHORTCUTS.get(v, v[:2].upper()) for v in vendors])
            # Use first vendor's time from confirmed_times dict
            time = list(confirmed_times.values())[0] if confirmed_times else "??:??"
        else:
            # Single vendor
            vendor_str = RESTAURANT_SHORTCUTS.get(vendors[0], vendors[0][:2].upper()) if vendors else "??"
            # Use confirmed_time (Shopify) or confirmed_times dict (Smoothr/PF)
            if confirmed_time:
                time = confirmed_time
            elif confirmed_times and vendors:
                time = confirmed_times.get(vendors[0], "??:??")
            else:
                time = "??:??"
        
        # Get street ONLY (extract from full address, remove zip code)
        full_address = order.get("customer", {}).get("address", "Unknown")
        # Address format: "Street 123, 94032 Passau" -> extract "Street 123"
        street = full_address.split(',')[0].strip() if ',' in full_address else full_address
        
        scheduled.append({
            "vendor": vendor_str,
            "time": time,
            "street": street
        })
    
    # Sort by time
    scheduled.sort(key=lambda x: x["time"])
    
    # Build message
    if not scheduled:
        return "🗂️ Scheduled orders\n\nNo scheduled orders."
    
    lines = ["🗂️ Scheduled orders", ""]
    for item in scheduled:
        # Format: [time - street  - vendor] (note: TWO spaces before vendor)
        lines.append(f"{item['time']} - {item['street']}  - {item['vendor']}")
    
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

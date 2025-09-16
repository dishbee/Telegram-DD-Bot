# rg.py - Restaurant Groups functionality

from shared import (
    logger, STATE, RESTAURANT_SHORTCUTS, VENDOR_GROUP_MAP,
    safe_send_message, safe_edit_message, safe_delete_message,
    get_last_confirmed_order
)
from mdg import send_mdg_confirmation
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

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

def check_all_vendors_confirmed(order_id: str):
    """Check if all vendors have confirmed their times and trigger MDG confirmation"""
    order = STATE.get(order_id)
    if not order:
        return
    
    vendors = order.get("vendors", [])
    if not vendors:
        return
    
    # Check if all vendors have confirmed times
    confirmed_vendors = order.get("confirmed_vendors", {})
    all_confirmed = all(vendor in confirmed_vendors for vendor in vendors)
    
    if all_confirmed:
        # All vendors confirmed - trigger MDG confirmation
        logger.info(f"All vendors confirmed for order {order_id}, triggering MDG confirmation")
        send_mdg_confirmation(order_id)
    else:
        logger.info(f"Order {order_id}: {len(confirmed_vendors)}/{len(vendors)} vendors confirmed")
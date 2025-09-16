# uc.py - User Chats functionality

from shared import (
    logger, STATE, safe_send_message, VENDOR_GROUP_MAP, DISPATCH_MAIN_CHAT_ID,
    build_assignment_dm_text, get_assignment_cta_keyboard, get_delay_options_keyboard
)
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

def assignment_dm(order: Dict[str, Any], user_id: int) -> str:
    """Build assignment DM message for driver using shared utility"""
    try:
        return build_assignment_dm_text(order)
    except Exception as e:
        logger.error(f"Error building assignment DM: {e}")
        return "Error building assignment message"

def assignment_cta_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build CTA buttons for assignment DM using shared utility"""
    try:
        return get_assignment_cta_keyboard(order_id)
    except Exception as e:
        logger.error(f"Error building CTA keyboard: {e}")
        return InlineKeyboardMarkup([])

def postpone_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build postpone time picker keyboard using shared utility"""
    try:
        return get_delay_options_keyboard(order_id)
    except Exception as e:
        logger.error(f"Error building postpone keyboard: {e}")
        return InlineKeyboardMarkup([])

async def send_assignment_dm(order_id: str, user_id: int):
    """Send assignment DM to user"""
    try:
        order = STATE.get(order_id)
        if not order:
            logger.warning(f"Order {order_id} not found for assignment DM")
            return
        
        # Build DM message and keyboard
        dm_message = assignment_dm(order, user_id)
        keyboard = assignment_cta_keyboard(order_id)
        
        # Send DM
        await safe_send_message(
            user_id,
            dm_message,
            keyboard,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
        
        logger.info(f"Assignment DM sent to user {user_id} for order {order_id}")
    except Exception as e:
        logger.error(f"Error sending assignment DM: {e}")

async def handle_call_customer(order_id: str, user_id: int):
    """Handle call customer button"""
    try:
        order = STATE.get(order_id)
        if not order:
            return
        
        phone = order['customer']['phone']
        if phone and phone != "N/A":
            # Send clickable phone link
            message = f"📞 Call customer: [{phone}](tel:{phone})"
            await safe_send_message(
                user_id,
                message,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await safe_send_message(
                user_id,
                "❌ Customer phone number not available"
            )
    except Exception as e:
        logger.error(f"Error handling call customer: {e}")

async def handle_navigate(order_id: str, user_id: int):
    """Handle navigate button"""
    try:
        order = STATE.get(order_id)
        if not order:
            return
        
        full_address = order['customer']['address']
        original_address = order['customer'].get('original_address', full_address)
        
        # Create Google Maps link
        maps_link = f"https://www.google.com/maps?q={original_address.replace(' ', '+')}"
        
        # Also provide Apple Maps link for iOS users
        apple_maps_link = f"https://maps.apple.com/?q={original_address.replace(' ', '+')}"
        
        message = f"🗺️ Navigate to customer:\n"
        message += f"[Google Maps]({maps_link})\n"
        message += f"[Apple Maps]({apple_maps_link})"
        
        await safe_send_message(
            user_id,
            message,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error handling navigate: {e}")

async def handle_call_restaurant(order_id: str, user_id: int):
    """Handle call restaurant button"""
    try:
        order = STATE.get(order_id)
        if not order:
            return
        
        vendors = order.get("vendors", [])
        if not vendors:
            await safe_send_message(
                user_id,
                "❌ No restaurant information available"
            )
            return
        
        # For multi-vendor, show all restaurants
        if len(vendors) > 1:
            message = "📱 Contact restaurants:\n"
            for vendor in vendors:
                chat_id = VENDOR_GROUP_MAP.get(vendor)
                if chat_id:
                    tg_link = f"tg://resolve?domain={abs(chat_id)}"  # Convert to username if possible
                    message += f"[{vendor}]({tg_link})\n"
                else:
                    message += f"{vendor}: Contact info not available\n"
        else:
            # Single vendor
            vendor = vendors[0]
            chat_id = VENDOR_GROUP_MAP.get(vendor)
            if chat_id:
                tg_link = f"tg://resolve?domain={abs(chat_id)}"
                message = f"📱 Contact {vendor}: [{vendor}]({tg_link})"
            else:
                message = f"❌ Contact info for {vendor} not available"
        
        await safe_send_message(
            user_id,
            message,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error handling call restaurant: {e}")

async def handle_complete(order_id: str, user_id: int):
    """Handle complete order button"""
    try:
        order = STATE.get(order_id)
        if not order:
            return
        
        # Mark order as completed
        order["status"] = "completed"
        order["completed_at"] = datetime.now()
        order["completed_by"] = user_id
        
        # Send completion message to MDG
        order_type = order.get("order_type", "shopify")
        if order_type == "shopify":
            order_num = order.get('name', '')[-2:] if len(order.get('name', '')) >= 2 else order.get('name', '')
            completion_msg = f"✅ Order #{order_num} was delivered."
        else:
            # For HubRise/Smoothr
            address_parts = order['customer']['address'].split(',')
            street_info = address_parts[0] if address_parts else "Unknown"
            completion_msg = f"✅ Order {street_info} was delivered."
        
        await safe_send_message(
            DISPATCH_MAIN_CHAT_ID,
            completion_msg
        )
        
        # Send confirmation to user
        await safe_send_message(
            user_id,
            "✅ Order marked as delivered. Thank you!"
        )
        
        logger.info(f"Order {order_id} completed by user {user_id}")
    except Exception as e:
        logger.error(f"Error handling complete: {e}")

async def handle_postpone(order_id: str, user_id: int):
    """Handle postpone button - show time picker"""
    try:
        keyboard = postpone_keyboard(order_id)
        await safe_send_message(
            user_id,
            "⏰ Select new delivery time:",
            keyboard
        )
    except Exception as e:
        logger.error(f"Error handling postpone: {e}")

async def handle_postpone_time(order_id: str, user_id: int, new_time: str):
    """Handle postpone time selection"""
    try:
        order = STATE.get(order_id)
        if not order:
            return
        
        # Update order time
        order["confirmed_time"] = new_time
        
        # Send delay message to restaurants
        for vendor in order["vendors"]:
            vendor_chat = VENDOR_GROUP_MAP.get(vendor)
            if vendor_chat:
                if order["order_type"] == "shopify":
                    msg = f"■ {vendor}: We have a delay - new time {new_time} ■"
                else:
                    msg = f"■ {vendor}: We have a delay - new time {new_time} ■"
                
                await safe_send_message(vendor_chat, msg)
        
        # Send confirmation to user
        await safe_send_message(
            user_id,
            f"⏰ Delivery time updated to {new_time}"
        )
        
        logger.info(f"Order {order_id} postponed to {new_time} by user {user_id}")
    except Exception as e:
        logger.error(f"Error handling postpone time: {e}")

async def assign_to_user(order_id: str, user_id: int):
    """Assign order to specific user"""
    try:
        order = STATE.get(order_id)
        if not order:
            logger.warning(f"Order {order_id} not found for assignment")
            return
        
        # Mark as assigned
        order["assigned_to"] = user_id
        order["assigned_at"] = datetime.now()
        
        # Send assignment DM
        await send_assignment_dm(order_id, user_id)
        
        logger.info(f"Order {order_id} assigned to user {user_id}")
    except Exception as e:
        logger.error(f"Error assigning order to user: {e}")

async def assign_to_myself(order_id: str, user_id: int):
    """Assign order to the user who clicked the button"""
    await assign_to_user(order_id, user_id)

async def assign_to_driver(order_id: str, driver_id: int):
    """Assign order to specific driver"""
    await assign_to_user(order_id, driver_id)
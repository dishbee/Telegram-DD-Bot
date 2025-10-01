# upc.py - User Private Chat functions for Telegram Dispatch Bot

import asyncio
from datetime import datetime, timedelta
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import utils
from utils import logger, STATE, COURIER_MAP, safe_send_message, safe_edit_message

# =============================================================================
# ORDER ASSIGNMENT SYSTEM - UPC (User Private Chats)
# =============================================================================
# WORKFLOW: After ALL vendors confirm times → assignment buttons appear in MDG
# → User clicks "Assign to me" or "Assign to [user]" → order details sent to private chat
# → Courier receives CTA buttons (call, navigate, delay, restaurant call, delivered)
# =============================================================================

def check_all_vendors_confirmed(order_id: str) -> bool:
    """Check if ALL vendors have confirmed their times for an order"""
    order = STATE.get(order_id)
    if not order:
        return False

    vendors = order.get("vendors", [])
    if not vendors:
        return False

    # Check if all vendors have confirmed_time set
    for vendor in vendors:
        if not order.get("confirmed_time"):
            logger.info(f"Order {order_id}: Vendor {vendor} has not confirmed time yet")
            return False

    logger.info(f"Order {order_id}: ALL vendors have confirmed - ready for assignment")
    return True

def assignment_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build assignment buttons that appear after all vendors confirm"""
    try:
        # Get list of available couriers from COURIER_MAP
        couriers = []
        for user_id, user_info in COURIER_MAP.items():
            if isinstance(user_info, dict) and user_info.get("is_courier", False):
                username = user_info.get("username", f"User{user_id}")
                couriers.append((user_id, username))

        buttons = []

        # "Assign to me" button (for current user - we'll need to pass user_id)
        # This will be context-dependent when called

        # "Assign to [specific user]" buttons
        for user_id, username in couriers[:5]:  # Limit to 5 for UI
            buttons.append([InlineKeyboardButton(
                f"Assign to {username}",
                callback_data=f"assign_user|{order_id}|{user_id}"
            )])

        # "Mark as delivered" button for completed orders
        buttons.append([InlineKeyboardButton(
            "Mark as delivered",
            callback_data=f"mark_delivered|{order_id}"
        )])

        return InlineKeyboardMarkup(buttons) if buttons else None

    except Exception as e:
        logger.error(f"Error building assignment keyboard: {e}")
        return None

def assignment_keyboard_with_me(order_id: str, current_user_id: int) -> InlineKeyboardMarkup:
    """Build assignment keyboard including 'Assign to me' for current user"""
    try:
        base_keyboard = assignment_keyboard(order_id)
        if not base_keyboard:
            return None

        # Add "Assign to me" at the top
        me_button = [InlineKeyboardButton(
            "Assign to me",
            callback_data=f"assign_me|{order_id}|{current_user_id}"
        )]

        # Combine keyboards
        all_buttons = me_button + base_keyboard.inline_keyboard
        return InlineKeyboardMarkup(all_buttons)

    except Exception as e:
        logger.error(f"Error building assignment keyboard with me: {e}")
        return None

async def send_assignment_to_private_chat(order_id: str, user_id: int, assigned_by: str = None):
    """Send order assignment details to user's private chat"""
    try:
        order = STATE.get(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for assignment")
            return

        # Build assignment message
        assignment_text = build_assignment_message(order)

        # Send to user's private chat
        msg = await safe_send_message(
            user_id,
            assignment_text,
            assignment_cta_keyboard(order_id)
        )

        # Update order status
        order["assigned_to"] = user_id
        order["assigned_at"] = datetime.now()
        order["assigned_by"] = assigned_by
        order["status"] = "assigned"

        # Track assignment message
        if "assignment_messages" not in order:
            order["assignment_messages"] = {}
        order["assignment_messages"][user_id] = msg.message_id

        logger.info(f"Order {order_id} assigned to user {user_id}")

    except Exception as e:
        logger.error(f"Error sending assignment to private chat: {e}")

def build_assignment_message(order: dict) -> str:
    """Build the assignment message sent to courier's private chat"""
    try:
        order_type = order.get("order_type", "shopify")

        # Header with assignment info
        if order_type == "shopify":
            header = f"🚚 **ORDER ASSIGNED** - #{order['name'][-2:]}\n"
        else:
            addr = order['customer']['address'].split(',')[0]
            header = f"🚚 **ORDER ASSIGNED** - {addr}\n"

        # Customer details
        customer_name = order['customer']['name']
        phone = order['customer']['phone']
        address = order['customer']['address']

        customer_section = f"👤 **Customer:** {customer_name}\n"
        customer_section += f"📞 **Phone:** [{phone}](tel:{phone})\n"
        customer_section += f"📍 **Address:** {address}\n\n"

        # Order details
        items_text = order.get("items_text", "")
        order_section = f"📦 **Order Details:**\n{items_text}\n\n"

        # Timing info
        confirmed_time = order.get("confirmed_time", "ASAP")
        timing_section = f"⏰ **Delivery Time:** {confirmed_time}\n\n"

        # Payment info
        payment = order.get("payment_method", "Paid")
        total = order.get("total", "0.00€")
        payment_section = f"💰 **Payment:** {payment}"
        if payment.lower() == "cash on delivery":
            payment_section += f" - {total}"
        payment_section += "\n\n"

        # Instructions
        instructions = "🎯 **Actions:** Use the buttons below to manage this delivery\n"
        instructions += "✅ Mark as delivered when complete"

        # Combine all sections
        message = header + customer_section + order_section + timing_section + payment_section + instructions

        return message

    except Exception as e:
        logger.error(f"Error building assignment message: {e}")
        return f"🚚 **ORDER ASSIGNED** - Error formatting details"

def assignment_cta_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build CTA buttons for assigned orders in private chats"""
    try:
        order = STATE.get(order_id)
        if not order:
            return None

        buttons = []

        # Row 1: Call customer, Navigate
        phone = order['customer']['phone']
        address = order['customer'].get('original_address', order['customer']['address'])

        call_customer = InlineKeyboardButton(
            "📞 Call Customer",
            url=f"tel:{phone}" if phone and phone != "N/A" else None
        )

        # Google Maps navigation
        maps_url = f"https://www.google.com/maps/dir/?api=1&destination={address.replace(' ', '+')}"
        navigate = InlineKeyboardButton("🗺️ Navigate", url=maps_url)

        buttons.append([call_customer, navigate])

        # Row 2: Delay order, Call restaurant
        delay = InlineKeyboardButton(
            "⏰ Delay",
            callback_data=f"delay_order|{order_id}"
        )

        # Call restaurant button (if single vendor)
        vendors = order.get("vendors", [])
        if len(vendors) == 1:
            vendor = vendors[0]
            call_restaurant = InlineKeyboardButton(
                f"📞 Call {vendor[:10]}",  # Truncate long names
                callback_data=f"call_restaurant|{order_id}|{vendor}"
            )
            buttons.append([delay, call_restaurant])
        else:
            # Multi-vendor - show vendor selection
            call_restaurant = InlineKeyboardButton(
                "📞 Call Restaurant",
                callback_data=f"select_restaurant|{order_id}"
            )
            buttons.append([delay, call_restaurant])

        # Row 3: Mark delivered
        delivered = InlineKeyboardButton(
            "✅ Delivered",
            callback_data=f"confirm_delivered|{order_id}"
        )
        buttons.append([delivered])

        return InlineKeyboardMarkup(buttons)

    except Exception as e:
        logger.error(f"Error building CTA keyboard: {e}")
        return None

async def handle_assignment_callback(action: str, data: list, user_id: int):
    """Handle assignment-related callback actions"""
    try:
        if action == "assign_me":
            order_id = data[1]
            await send_assignment_to_private_chat(order_id, user_id, "self")

            # Update MDG to show assignment
            await update_mdg_assignment_status(order_id, user_id, "self-assigned")

        elif action == "assign_user":
            order_id, target_user_id = data[1], int(data[2])
            target_user_info = COURIER_MAP.get(int(target_user_id), {})
            assigned_by = target_user_info.get("username", f"User{target_user_id}")

            await send_assignment_to_private_chat(order_id, int(target_user_id), assigned_by)

            # Update MDG to show assignment
            await update_mdg_assignment_status(order_id, int(target_user_id), assigned_by)

        elif action == "mark_delivered":
            order_id = data[1]
            await handle_delivery_completion(order_id, user_id)

        elif action == "confirm_delivered":
            order_id = data[1]
            await handle_delivery_completion(order_id, user_id)

        elif action == "delay_order":
            order_id = data[1]
            await show_delay_options(order_id, user_id)

        elif action == "call_restaurant":
            order_id, vendor = data[1], data[2]
            await initiate_restaurant_call(order_id, vendor, user_id)

        elif action == "select_restaurant":
            order_id = data[1]
            await show_restaurant_selection(order_id, user_id)

    except Exception as e:
        logger.error(f"Error handling assignment callback {action}: {e}")

async def update_mdg_assignment_status(order_id: str, assigned_user_id: int, assigned_by: str):
    """Update MDG message to show assignment status"""
    try:
        order = STATE.get(order_id)
        if not order or "mdg_message_id" not in order:
            return

        # Get assignee info
        assignee_info = COURIER_MAP.get(assigned_user_id, {})
        assignee_name = assignee_info.get("username", f"User{assigned_user_id}")

        # Build updated MDG text with assignment info
        import mdg
        base_text = mdg.build_mdg_dispatch_text(order)
        assignment_info = f"\n\n👤 **Assigned to:** {assignee_name}"
        if assigned_by != "self-assigned":
            assignment_info += f" (by {assigned_by})"

        updated_text = base_text + assignment_info

        # Remove assignment buttons - show only status
        await safe_edit_message(
            utils.DISPATCH_MAIN_CHAT_ID,
            order["mdg_message_id"],
            updated_text,
            None  # No keyboard - assignment complete
        )

        logger.info(f"Updated MDG for order {order_id} - assigned to {assignee_name}")

    except Exception as e:
        logger.error(f"Error updating MDG assignment status: {e}")

async def handle_delivery_completion(order_id: str, user_id: int):
    """Handle delivery completion"""
    try:
        order = STATE.get(order_id)
        if not order:
            return

        # Update order status
        order["status"] = "delivered"
        order["delivered_at"] = datetime.now()
        order["delivered_by"] = user_id

        # Send confirmation to MDG
        delivered_msg = f"✅ Order {order['name']} delivered by {COURIER_MAP.get(user_id, {}).get('username', f'User{user_id}')}"
        await safe_send_message(utils.DISPATCH_MAIN_CHAT_ID, delivered_msg)

        # Update private chat message
        completion_msg = "✅ **Delivery completed!**\n\nThank you for the successful delivery."
        await safe_send_message(user_id, completion_msg)

        logger.info(f"Order {order_id} marked as delivered by user {user_id}")

    except Exception as e:
        logger.error(f"Error handling delivery completion: {e}")

async def show_delay_options(order_id: str, user_id: int):
    """Show delay options for the assigned courier"""
    try:
        delay_buttons = [
            [InlineKeyboardButton("5 minutes", callback_data=f"delay_minutes|{order_id}|5")],
            [InlineKeyboardButton("10 minutes", callback_data=f"delay_minutes|{order_id}|10")],
            [InlineKeyboardButton("15 minutes", callback_data=f"delay_minutes|{order_id}|15")],
            [InlineKeyboardButton("20 minutes", callback_data=f"delay_minutes|{order_id}|20")],
            [InlineKeyboardButton("Custom time", callback_data=f"delay_custom|{order_id}")]
        ]

        await safe_send_message(
            user_id,
            "⏰ How long is the delay?",
            InlineKeyboardMarkup(delay_buttons)
        )

    except Exception as e:
        logger.error(f"Error showing delay options: {e}")

async def show_restaurant_selection(order_id: str, user_id: int):
    """Show restaurant selection for multi-vendor orders"""
    try:
        order = STATE.get(order_id)
        if not order:
            return

        vendors = order.get("vendors", [])
        buttons = []

        for vendor in vendors:
            buttons.append([InlineKeyboardButton(
                f"📞 Call {vendor}",
                callback_data=f"call_restaurant|{order_id}|{vendor}"
            )])

        await safe_send_message(
            user_id,
            "Select restaurant to call:",
            InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        logger.error(f"Error showing restaurant selection: {e}")

async def initiate_restaurant_call(order_id: str, vendor: str, user_id: int):
    """Initiate call to restaurant (placeholder - would integrate with phone system)"""
    try:
        # For now, just show contact info
        # In production, this would integrate with telephony system
        await safe_send_message(
            user_id,
            f"📞 Calling {vendor}...\n\nPlease contact them directly for coordination."
        )

        # Log the call attempt
        logger.info(f"User {user_id} initiated call to {vendor} for order {order_id}")

    except Exception as e:
        logger.error(f"Error initiating restaurant call: {e}")

# Placeholder functions for future implementation
def get_assignment_status(order_id: str) -> str:
    """Get current assignment status of an order"""
    order = STATE.get(order_id)
    if not order:
        return "unknown"

    status = order.get("status", "new")
    if status == "assigned":
        assigned_to = order.get("assigned_to")
        if assigned_to:
            assignee = COURIER_MAP.get(assigned_to, {}).get("username", f"User{assigned_to}")
            return f"assigned_to_{assignee}"

    return status
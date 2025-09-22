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

    # For single vendor orders, check if confirmed_time is set
    if len(vendors) == 1:
        return order.get("confirmed_time") is not None

    # For multi-vendor orders, check if all vendors have confirmed
    confirmed_vendors = order.get("confirmed_vendors", set())
    return len(confirmed_vendors) == len(vendors)

def assignment_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build assignment buttons that appear after all vendors confirm"""
    try:
        buttons = [
            [InlineKeyboardButton("👈 Assign to myself", callback_data=f"assign_myself|{order_id}")],
            [InlineKeyboardButton("👉 Assign to...", callback_data=f"assign_submenu|{order_id}")]
        ]

        return InlineKeyboardMarkup(buttons)

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

        # Get user info from COURIER_MAP
        user_info = COURIER_MAP.get(str(user_id))
        if not user_info:
            logger.error(f"User {user_id} not found in COURIER_MAP")
            return

        chat_id = user_info.get("chat_id")
        if not chat_id:
            logger.error(f"No chat_id found for user {user_id}")
            return

        # Build assignment message
        assignment_text = build_assignment_message(order)

        # Send to user's private chat
        msg = await safe_send_message(
            chat_id,
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
    """Build the assignment message sent to courier's private chat - matches MDG format"""
    try:
        order_type = order.get("order_type", "shopify")
        vendors = order.get("vendors", [])
        from utils import validate_phone

        # 1. Title with order number and shortcuts (only for Shopify) - add space after emoji
        if order_type == "shopify":
            order_num = order.get('name', '')[-2:] if len(order.get('name', '')) >= 2 else order.get('name', '')
            if len(vendors) > 1:
                # Multi-vendor: use shortcuts
                from utils import RESTAURANT_SHORTCUTS
                shortcuts = [RESTAURANT_SHORTCUTS.get(v, v[:2].upper()) for v in vendors]
                title = f"🚚 ORDER ASSIGNED - #{order_num} ({'+'.join(shortcuts)})"
            else:
                # Single vendor
                from utils import RESTAURANT_SHORTCUTS
                shortcut = RESTAURANT_SHORTCUTS.get(vendors[0], vendors[0][:2].upper()) if vendors else ""
                title = f"🚚 ORDER ASSIGNED - #{order_num} ({shortcut})"
        else:
            # For HubRise/Smoothr: only restaurant name
            title = f"🚚 ORDER ASSIGNED - {vendors[0] if vendors else 'Unknown'}"

        # 2. Customer name on second line with emoji
        customer_name = order['customer']['name']
        customer_line = f"🧑 {customer_name}"

        # 3. Address as Google Maps link with new format
        full_address = order['customer']['address']
        original_address = order['customer'].get('original_address', full_address)

        # Parse address: split by comma to get street and zip
        address_parts = full_address.split(',')
        if len(address_parts) >= 2:
            street_part = address_parts[0].strip()
            zip_part = address_parts[-1].strip().strip('()')  # Clean zip of any parentheses
            display_address = f"{street_part} ({zip_part})"
        else:
            # Fallback if parsing fails
            display_address = full_address.strip()

        # Create Google Maps link using original address (clean, no parentheses)
        maps_link = f"https://www.google.com/maps?q={original_address.replace(' ', '+')}"
        address_line = f"🗺️ [{display_address}]({maps_link})"

        # 4. Note (if added)
        note_line = ""
        note = order.get("note", "")
        if note:
            note_line = f"Note: {note}\n"

        # 5. Tips (if added)
        tips_line = ""
        tips = order.get("tips", 0.0)
        if tips and float(tips) > 0:
            tips_line = f"❕ Tip: {float(tips):.2f}€\n"

        # 6. Payment method - CoD with total (only for Shopify)
        payment_line = ""
        if order_type == "shopify":
            payment = order.get("payment_method", "Paid")
            total = order.get("total", "0.00€")

            if payment.lower() == "cash on delivery":
                payment_line = f"❕ Cash on delivery: {total}\n"
            else:
                # For paid orders, just show the total below products
                payment_line = ""

        # 7. Items (remove dashes)
        if order_type == "shopify" and len(vendors) > 1:
            # Multi-vendor: show vendor names above items
            vendor_items = order.get("vendor_items", {})
            items_text = ""
            for vendor in vendors:
                items_text += f"\n{vendor}:\n"
                vendor_products = vendor_items.get(vendor, [])
                for item in vendor_products:
                    # Remove leading dash
                    clean_item = item.lstrip('- ').strip()
                    items_text += f"{clean_item}\n"
        else:
            # Single vendor: just list items
            items_text = order.get("items_text", "")
            # Remove leading dashes from all lines
            lines = items_text.split('\n')
            clean_lines = []
            for line in lines:
                if line.strip():
                    clean_line = line.lstrip('- ').strip()
                    clean_lines.append(clean_line)
            items_text = '\n'.join(clean_lines)

        # Add total to items_text
        total = order.get("total", "0.00€")
        if order_type == "shopify":
            payment = order.get("payment_method", "Paid")
            if payment.lower() != "cash on delivery":
                # For paid orders, show total here
                items_text += f"\n{total}"

        # 8. Clickable phone number (tel: link) - only if valid
        phone = order['customer']['phone']
        phone_line = ""
        if phone and phone != "N/A":
            phone_line = f"[{phone}](tel:{phone})\n"

        # Build final message with new structure
        text = f"{title}\n"
        text += f"{customer_line}\n"  # Customer name
        text += f"{address_line}\n\n"  # Address + empty line
        text += note_line
        text += tips_line
        text += payment_line
        if note_line or tips_line or payment_line:
            text += "\n"  # Empty line after note/tips/payment block
        text += f"{items_text}\n\n"  # Items + empty line
        text += phone_line

        return text

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

        # Get order details
        phone = order['customer']['phone']
        address = order['customer'].get('original_address', order['customer']['address'])
        vendors = order.get("vendors", [])

        # Row 1: Call, Navigate, Delay
        call = InlineKeyboardButton(
            "📞 Call",
            url=f"tel:{phone}" if phone and phone != "N/A" else None
        )

        # Google Maps navigation
        maps_url = f"https://www.google.com/maps/dir/?api=1&destination={address.replace(' ', '+')}"
        navigate = InlineKeyboardButton("🗺️ Navigate", url=maps_url)

        delay = InlineKeyboardButton(
            "⏰ Delay",
            callback_data=f"delay_order|{order_id}"
        )

        buttons.append([call, navigate, delay])

        # Row 2: Restaurant Call, Delivered
        if len(vendors) == 1:
            vendor = vendors[0]
            restaurant_call = InlineKeyboardButton(
                "📞 Restaurant Call",
                callback_data=f"call_restaurant|{order_id}|{vendor}"
            )
        else:
            # Multi-vendor - show vendor selection
            restaurant_call = InlineKeyboardButton(
                "📞 Restaurant Call",
                callback_data=f"select_restaurant|{order_id}"
            )

        delivered = InlineKeyboardButton(
            "✅ Delivered",
            callback_data=f"confirm_delivered|{order_id}"
        )
        buttons.append([restaurant_call, delivered])

        return InlineKeyboardMarkup(buttons)

    except Exception as e:
        logger.error(f"Error building CTA keyboard: {e}")
        return None

async def handle_assignment_callback(action: str, data: list, user_id: int):
    """Handle assignment-related callback actions"""
    try:
        order_id = data[1] if len(data) > 1 else None
        if not order_id:
            return

        order = STATE.get(order_id)
        if not order:
            return

        # Check if order is already assigned
        current_assignee = order.get("assigned_to")
        if current_assignee is not None:
            assignee_info = COURIER_MAP.get(str(current_assignee), {})
            assignee_name = assignee_info.get("username", f"User{current_assignee}")
            await safe_send_message(
                user_id,
                f"❌ Order already assigned to {assignee_name}"
            )
            return

        if action == "assign_myself":
            await send_assignment_to_private_chat(order_id, user_id, "self")

            # Update MDG to show assignment
            await update_mdg_assignment_status(order_id, user_id, "self-assigned")

        elif action == "assign_submenu":
            await show_assign_submenu(order_id)

        elif action == "assign_me":
            await send_assignment_to_private_chat(order_id, user_id, "self")

            # Update MDG to show assignment
            await update_mdg_assignment_status(order_id, user_id, "self-assigned")

        elif action == "assign_user":
            target_user_id = int(data[2])
            target_user_info = COURIER_MAP.get(str(target_user_id), {})
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

        elif action == "delay_minutes":
            order_id, minutes = data[1], int(data[2])
            await handle_delay_minutes(order_id, minutes, user_id)

        elif action == "delay_custom":
            order_id = data[1]
            await handle_delay_custom(order_id, user_id)

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
        assignee_info = COURIER_MAP.get(str(assigned_user_id), {})
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

        # Also update the assignment message if it exists
        if "assignment_message_id" in order:
            assignment_status_text = f"✅ **Order assigned to:** {assignee_name}"
            if assigned_by != "self-assigned":
                assignment_status_text += f" (by {assigned_by})"
            
            await safe_edit_message(
                utils.DISPATCH_MAIN_CHAT_ID,
                order["assignment_message_id"],
                assignment_status_text,
                None  # Remove keyboard
            )

        # Clean up additional MDG messages after assignment
        import mdg
        await mdg.cleanup_mdg_messages(order_id)

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
        delivered_msg = f"✅ Order {order['name']} delivered by {COURIER_MAP.get(str(user_id), {}).get('username', f'User{user_id}')}"
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

async def handle_delay_minutes(order_id: str, minutes: int, user_id: int):
    """Handle delay by adding minutes to confirmed time"""
    try:
        order = STATE.get(order_id)
        if not order:
            return

        current_time = order.get("confirmed_time")
        if not current_time or current_time == "ASAP":
            await safe_send_message(user_id, "Cannot delay ASAP orders. Please set a specific time first.")
            return

        # Parse current time
        try:
            hour, minute = map(int, current_time.split(':'))
            from datetime import datetime, timedelta
            base_time = datetime.now().replace(hour=hour, minute=minute)
            new_time = base_time + timedelta(minutes=minutes)
            new_time_str = new_time.strftime("%H:%M")
            
            # Update order
            order["confirmed_time"] = new_time_str
            
            # Notify MDG
            await safe_send_message(
                utils.DISPATCH_MAIN_CHAT_ID,
                f"⏰ Order {order['name']} delayed by {minutes} minutes - new delivery time: {new_time_str}"
            )
            
            # Confirm to courier
            await safe_send_message(
                user_id,
                f"✅ Delay confirmed. New delivery time: {new_time_str}"
            )
            
            logger.info(f"Order {order_id} delayed by {minutes} minutes to {new_time_str}")
            
        except Exception as e:
            logger.error(f"Error parsing time for delay: {e}")
            await safe_send_message(user_id, "Error processing delay. Please try again.")

    except Exception as e:
        logger.error(f"Error handling delay minutes: {e}")

async def handle_delay_custom(order_id: str, user_id: int):
    """Handle custom delay time (placeholder - would need user input)"""
    try:
        await safe_send_message(
            user_id,
            "Custom delay not implemented yet. Please use preset delay options."
        )
    except Exception as e:
        logger.error(f"Error handling delay custom: {e}")

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

async def show_assign_submenu(order_id: str):
    """Show submenu with list of couriers to assign to"""
    try:
        # Get list of available couriers from COURIER_MAP
        couriers = []
        for user_id, user_info in COURIER_MAP.items():
            if isinstance(user_info, dict):
                username = user_info.get("username", f"User{user_id}")
                couriers.append((user_id, username))

        buttons = []

        # "Assign to [specific user]" buttons
        for user_id, username in couriers[:10]:  # Allow more for submenu
            buttons.append([InlineKeyboardButton(
                f"Assign to {username}",
                callback_data=f"assign_user|{order_id}|{user_id}"
            )])

        await safe_send_message(
            utils.DISPATCH_MAIN_CHAT_ID,
            "Select courier to assign:",
            InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        logger.error(f"Error showing assign submenu: {e}")

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
# -*- coding: utf-8 -*-
# upc.py - User Private Chat functions for Telegram Dispatch Bot

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from utils import logger, COURIER_MAP, DISPATCH_MAIN_CHAT_ID, VENDOR_GROUP_MAP, RESTAURANT_SHORTCUTS, safe_send_message, safe_edit_message, safe_delete_message, get_error_description

# Timezone configuration for Passau, Germany (Europe/Berlin)
TIMEZONE = ZoneInfo("Europe/Berlin")

def now() -> datetime:
    """Get current time in Passau timezone (Europe/Berlin)."""
    return datetime.now(TIMEZONE)

# =============================================================================
# ORDER ASSIGNMENT SYSTEM - UPC (User Private Chats)
# =============================================================================
# WORKFLOW: After ALL vendors confirm times → assignment buttons appear in MDG
# → User clicks "Assign to me" or "Assign to [user]" → order details sent to private chat
# → Courier receives CTA buttons (call, navigate, delay, restaurant call, delivered)
# =============================================================================

# Module-level STATE and bot reference (configured from main.py)
STATE = None
bot = None

def configure(state_ref, bot_ref=None):
    """Configure module-level STATE and bot reference"""
    global STATE, bot
    STATE = state_ref
    if bot_ref:
        bot = bot_ref

def check_all_vendors_confirmed(order_id: str) -> bool:
    """Check if ALL vendors have confirmed their times for an order"""
    order = STATE.get(order_id)
    if not order:
        logger.warning(f"DEBUG: Order {order_id} not found in STATE")
        return False

    vendors = order.get("vendors", [])
    if not vendors:
        logger.warning(f"DEBUG: Order {order_id} has no vendors")
        return False

    confirmed_times = order.get("confirmed_times", {})
    
    logger.info(f"DEBUG: Order {order_id} - Vendors: {vendors}")
    logger.info(f"DEBUG: Order {order_id} - Confirmed times: {confirmed_times}")
    
    # Check if all vendors have confirmed their time
    for vendor in vendors:
        if vendor not in confirmed_times:
            logger.info(f"DEBUG: Order {order_id} - Vendor {vendor} NOT in confirmed_times")
            return False
        else:
            logger.info(f"DEBUG: Order {order_id} - Vendor {vendor} confirmed at {confirmed_times[vendor]}")

    logger.info(f"DEBUG: Order {order_id} - ALL {len(vendors)} vendors have confirmed - ready for assignment")
    return True

def mdg_assignment_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build assignment buttons for MDG after all vendors confirm"""
    try:
        buttons = [
            [InlineKeyboardButton("👈 Assign to myself", callback_data=f"assign_myself|{order_id}")],
            [InlineKeyboardButton("Assign to 👉", callback_data=f"assign_to_menu|{order_id}")]
        ]
        return InlineKeyboardMarkup(buttons)
    except Exception as e:
        logger.error(f"Error building MDG assignment keyboard: {e}")
        return None

async def get_mdg_couriers(bot):
    """
    Get list of couriers from MDG group with fallback to COURIER_MAP.
    
    This function queries the Telegram Bot API to get current administrators
    of the Main Dispatch Group (MDG). This ensures the courier selection menu
    always shows actual group members, even if they join/leave.
    
    Flow:
    1. Query bot.get_chat_administrators() for MDG group
    2. Filter out bot accounts (include only human users)
    3. Extract user_id and username for each admin
    4. Fallback to COURIER_MAP environment variable if API call fails
    
    Note: Only administrators are returned by Telegram API. All couriers
    must be promoted to admin status in MDG for this to work correctly.
    
    Args:
        bot: Telegram Bot instance for API calls
    
    Returns:
        List of dicts: [{"user_id": int, "username": str}, ...]
        
    Raises:
        Logs error and falls back to COURIER_MAP if API call fails
    """
    try:
        if not bot:
            logger.warning("Bot instance not available, using COURIER_MAP fallback")
            return get_couriers_from_map()
        
        # Get all members from MDG
        chat_members = await bot.get_chat_administrators(DISPATCH_MAIN_CHAT_ID)
        
        couriers = []
        for member in chat_members:
            user = member.user
            # Filter out bots
            if not user.is_bot:
                couriers.append({
                    "user_id": user.id,
                    "username": user.first_name or user.username or f"User{user.id}"
                })
        
        logger.info(f"DEBUG: Found {len(couriers)} couriers from MDG group")
        
        # If no couriers found, fall back to COURIER_MAP
        if not couriers:
            logger.warning("No couriers found in MDG, using COURIER_MAP fallback")
            return get_couriers_from_map()
        
        return couriers
        
    except Exception as e:
        logger.error(f"Error getting MDG members: {e}, using COURIER_MAP fallback")
        return get_couriers_from_map()

def get_couriers_from_map():
    """Get couriers from static COURIER_MAP (fallback)"""
    couriers = []
    for user_id_str, user_data in COURIER_MAP.items():
        if isinstance(user_data, dict):
            couriers.append({
                "user_id": int(user_id_str),
                "username": user_data.get("username", f"User{user_id_str}")
            })
    logger.info(f"DEBUG: Using COURIER_MAP fallback with {len(couriers)} couriers")
    return couriers

async def courier_selection_keyboard(order_id: str, bot) -> InlineKeyboardMarkup:
    """
    Build keyboard with buttons for each available courier.
    
    Dynamically generates courier selection buttons by querying live MDG
    membership. Each button triggers assign_to_user callback with courier's
    user_id, allowing dispatcher to assign order to any courier.
    
    Priority ordering:
    1. Bee 1, Bee 2, Bee 3 (if present in MDG)
    2. All other couriers alphabetically
    
    Args:
        order_id: Shopify order ID for callback data
        bot: Bot instance to query MDG members
    
    Returns:
        InlineKeyboardMarkup with one button per courier, or None if no couriers
        
    Button format: [Courier Name] → assign_to_user|{order_id}|{user_id}
    """
    try:
        # Get couriers (live from MDG or fallback to COURIER_MAP)
        couriers = await get_mdg_couriers(bot)
        
        if not couriers:
            logger.error("No couriers available from MDG or COURIER_MAP")
            return None
        
        buttons = []
        
        # Priority couriers (Bee 1, Bee 2, Bee 3) first
        priority_names = ["Bee 1", "Bee 2", "Bee 3"]
        for priority_name in priority_names:
            for courier in couriers:
                if courier["username"] == priority_name:
                    buttons.append([InlineKeyboardButton(
                        courier["username"],
                        callback_data=f"assign_to_user|{order_id}|{courier['user_id']}"
                    )])
                    break
        
        # Then other couriers
        for courier in couriers:
            if courier["username"] not in priority_names:
                buttons.append([InlineKeyboardButton(
                    courier["username"],
                    callback_data=f"assign_to_user|{order_id}|{courier['user_id']}"
                )])
        
        # Add Back button
        buttons.append([InlineKeyboardButton("← Back", callback_data="hide")])
        
        logger.info(f"DEBUG: Built {len(buttons)} courier buttons for selection")
        return InlineKeyboardMarkup(buttons) if buttons else None
        
    except Exception as e:
        logger.error(f"Error building courier selection keyboard: {e}")
        return None

async def send_assignment_to_private_chat(order_id: str, user_id: int):
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
        order["assigned_at"] = now()
        order["status"] = "assigned"
        order["upc_assignment_message_id"] = msg.message_id  # Track for group updates

        # Track assignment message
        if "assignment_messages" not in order:
            order["assignment_messages"] = {}
        order["assignment_messages"][user_id] = msg.message_id

        logger.info(f"Order {order_id} assigned to user {user_id}")

    except Exception as e:
        logger.error(f"Error sending assignment to private chat: {e}")

async def update_mdg_with_assignment(order_id: str, assigned_user_id: int):
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

        updated_text = base_text + assignment_info

        # Keep vendor selection buttons visible
        await safe_edit_message(
            DISPATCH_MAIN_CHAT_ID,
            order["mdg_message_id"],
            updated_text,
            mdg.mdg_time_request_keyboard(order_id)  # Keep buttons
        )

        logger.info(f"Updated MDG for order {order_id} - assigned to {assignee_name}")

    except Exception as e:
        logger.error(f"Error updating MDG with assignment: {e}")

def build_assignment_message(order: dict) -> str:
    """
    Build the assignment message sent to courier's private chat.
    
    This message contains all information the courier needs to complete the delivery:
    - Order number (with 👉 emoji)
    - Each restaurant with pickup time and product count (using chef emoji)
    - Customer name and formatted address
    - Payment method and tip information
    - Phone number for customer (without "Call customer:" label)
    
    Format example:
        � #58 - dishbee
        👩‍� Leckerolls: 12:55 🍕 3
        🧑‍� Julis Spätzlerei: 13:00 🍕 2
        
        👤 John Doe
        🧭 Hauptstraße 5 (80333)
        
        ❕ Tip: 2.50€
        
        ☎️ +49...
    
    Args:
        order: Order dict from STATE with all order details
        
    Returns:
        Formatted message string for private chat display
    """
    try:
        order_type = order.get("order_type", "shopify")
        
        # Chef emojis for variety (same as MDG-CONF)
        chef_emojis = ["👩‍🍳", "👩🏻‍🍳", "👩🏼‍🍳", "👩🏾‍🍳", "🧑‍🍳", "🧑🏻‍🍳", "🧑🏼‍🍳", "🧑🏾‍🍳", "👨‍🍳", "👨🏻‍🍳", "👨🏼‍🍳", "👨🏾‍🍳"]
        
        # Group indicator (if order is in a group)
        group_header = ""
        if order.get("group_id"):
            group_color = order.get("group_color", "🟠")
            group_position = order.get("group_position", 1)
            
            # Calculate total orders in group
            group_id = order["group_id"]
            from main import GROUPS
            group = GROUPS.get(group_id)
            if group:
                group_total = len(group["order_ids"])
                group_header = f"{group_color} Group: {group_position}/{group_total}\n\n"
        
        # Header: � #34 - dishbee
        if order_type == "shopify":
            order_num = order.get('name', '')[-2:] if len(order.get('name', '')) >= 2 else order.get('name', '')
            header = f"👉 #{order_num} - dishbee\n"
        else:
            header = f"👉 {order.get('name', 'Order')}\n"
        
        # Restaurant info with confirmed times and product quantities
        vendors = order.get("vendors", [])
        confirmed_times = order.get("confirmed_times", {})
        vendor_items = order.get("vendor_items", {})
        
        restaurant_section = ""
        for idx, vendor in enumerate(vendors):
            pickup_time = confirmed_times.get(vendor, "ASAP")
            chef_emoji = chef_emojis[idx % len(chef_emojis)]
            
            # Use vendor shortcut instead of full name
            vendor_shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
            
            # Count products for this vendor
            items = vendor_items.get(vendor, [])
            product_count = 0
            for item_line in items:
                # Extract quantity from format "- 2 x Product Name"
                if ' x ' in item_line:
                    qty_part = item_line.split(' x ')[0].strip().lstrip('-').strip()
                    try:
                        product_count += int(qty_part)
                    except ValueError:
                        product_count += 1
                else:
                    product_count += 1
            
            restaurant_section += f"{chef_emoji} {vendor_shortcut}: {pickup_time} 🍕 {product_count}\n"
        
        # Customer info
        customer_name = order['customer']['name']
        address = order['customer']['address']
        
        # Format address: street + building number (zip)
        address_parts = address.split(',')
        if len(address_parts) >= 2:
            street_part = address_parts[0].strip()
            zip_part = address_parts[-1].strip()
            formatted_address = f"{street_part} ({zip_part})"
        else:
            formatted_address = address.strip()
        
        customer_section = f"\n👤 {customer_name}\n"
        customer_section += f"🧭 {formatted_address}\n"
        
        # Optional info (note, tips, cash on delivery)
        optional_section = ""
        
        note = order.get("note", "")
        if note:
            optional_section += f"\n❕ Note: {note}\n"
        
        tips = order.get("tips", 0.0)
        if tips and float(tips) > 0:
            optional_section += f"❕ Tip: {float(tips):.2f}€\n"
        
        payment = order.get("payment_method", "Paid")
        total = order.get("total", "0.00€")
        if payment.lower() == "cash on delivery":
            optional_section += f"❕ Cash: {total}\n"
        
        # Phone number section (without "Call customer:" label)
        phone = order['customer']['phone']
        phone_section = f"\n☎️ {phone}\n"
        
        # Combine all sections (group_header first if present)
        message = group_header + header + restaurant_section + customer_section + optional_section + phone_section
        
        return message

    except Exception as e:
        logger.error(f"Error building assignment message: {e}")
        return f"👉 **ORDER ASSIGNED** - Error formatting details"

def assignment_cta_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build CTA buttons for assigned orders in private chats"""
    try:
        order = STATE.get(order_id)
        if not order:
            return None

        buttons = []
        address = order['customer'].get('original_address', order['customer']['address'])
        vendors = order.get("vendors", [])

        # Row 1: Navigate (single button - phone numbers are in message text)
        # Google Maps navigation with cycling mode
        maps_url = f"https://www.google.com/maps/dir/?api=1&destination={address.replace(' ', '+')}&travelmode=bicycling"
        navigate = InlineKeyboardButton("🧭 Navigate", url=maps_url)
        
        buttons.append([navigate])

        # Row 2: Delay (single button per row)
        delay = InlineKeyboardButton(
            "⏳ Delay",
            callback_data=f"delay_order|{order_id}"
        )
        buttons.append([delay])
        
        # Row 3: Unassign (only show if not yet delivered)
        if order.get("status") != "delivered":
            unassign = InlineKeyboardButton(
                "🚫 Unassign",
                callback_data=f"unassign_order|{order_id}"
            )
            buttons.append([unassign])

        # Row 4: Call Restaurant(s) - separate button for each vendor
        chef_emojis = ["👩‍🍳", "👩🏻‍🍳", "👩🏼‍🍳", "👩🏾‍🍳", "🧑‍🍳", "🧑🏻‍🍳", "🧑🏼‍🍳", "🧑🏾‍🍳", "👨‍🍳", "👨🏻‍🍳", "👨🏼‍🍳", "👨🏾‍🍳"]
        for idx, vendor in enumerate(vendors):
            vendor_shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
            chef_emoji = chef_emojis[idx % len(chef_emojis)]
            call_btn = InlineKeyboardButton(
                f"{chef_emoji} Call {vendor_shortcut}",
                callback_data=f"call_vendor|{order_id}|{vendor}"
            )
            buttons.append([call_btn])

        # Row 5: Mark delivered
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

        # Keep vendor selection buttons visible
        await safe_edit_message(
            DISPATCH_MAIN_CHAT_ID,
            order["mdg_message_id"],
            updated_text,
            mdg.mdg_time_request_keyboard(order_id)  # Keep buttons
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
        order["delivered_at"] = now()
        order["delivered_by"] = user_id

        # Get courier info
        assignee_info = COURIER_MAP.get(str(user_id), {})
        assignee_name = assignee_info.get("username", f"User{user_id}")
        
        # Send confirmation to MDG with courier name and delivery time
        order_num = order.get('name', '')[-2:] if len(order.get('name', '')) >= 2 else order.get('name', '')
        delivery_time = order["delivered_at"].strftime("%H:%M")
        delivered_msg = f"🔖 #{order_num} was delivered by {assignee_name} at {delivery_time}"
        await safe_send_message(DISPATCH_MAIN_CHAT_ID, delivered_msg)
        
        # Delete MDG-CONF and other temporary messages
        if "mdg_additional_messages" in order:
            for msg_id in order["mdg_additional_messages"]:
                await safe_delete_message(DISPATCH_MAIN_CHAT_ID, msg_id)
            order["mdg_additional_messages"] = []
        
        # Update MDG original order message with "✅ Delivered" status
        if "mdg_message_id" in order:
            import mdg
            base_text = mdg.build_mdg_dispatch_text(order)
            
            updated_text = base_text + f"\n\n👤 **Assigned to:** {assignee_name}\n✅ **Delivered**"
            
            await safe_edit_message(
                DISPATCH_MAIN_CHAT_ID,
                order["mdg_message_id"],
                updated_text,
                mdg.mdg_time_request_keyboard(order_id)  # Keep buttons
            )

        # NO confirmation message to courier (removed as per requirement)

        logger.info(f"Order {order_id} marked as delivered by user {user_id}")
        
        # Handle group updates if order was part of a group
        if order.get("group_id"):
            await update_group_on_delivery(order_id)

    except Exception as e:
        logger.error(f"Error handling delivery completion: {e}")


async def update_group_on_delivery(delivered_order_id: str):
    """
    Update group when an order is delivered.
    Removes order from group, recalculates positions, and updates remaining orders' UPC messages.
    """
    try:
        delivered_order = STATE.get(delivered_order_id)
        if not delivered_order:
            return
        
        group_id = delivered_order.get("group_id")
        if not group_id:
            return
        
        # Import GROUPS from main
        from main import GROUPS
        
        group = GROUPS.get(group_id)
        if not group:
            logger.warning(f"Group {group_id} not found in GROUPS dict")
            return
        
        # Remove delivered order from group
        if delivered_order_id in group["order_ids"]:
            group["order_ids"].remove(delivered_order_id)
            logger.info(f"Removed order {delivered_order_id} from group {group_id}")
        
        # Clear group fields from delivered order
        delivered_order["group_id"] = None
        delivered_order["group_color"] = None
        delivered_order["group_position"] = None
        
        # If group is now empty, delete it
        if not group["order_ids"]:
            del GROUPS[group_id]
            logger.info(f"Group {group_id} is empty, deleted")
            return
        
        # Recalculate positions for remaining orders
        new_total = len(group["order_ids"])
        for position, order_id in enumerate(group["order_ids"], start=1):
            order = STATE.get(order_id)
            if order:
                order["group_position"] = position
                
                # Update UPC message if order is assigned
                if order.get("status") == "assigned" and order.get("upc_assignment_message_id"):
                    assigned_user_id = order.get("assigned_to")
                    if assigned_user_id:
                        # Rebuild assignment message with updated group position
                        updated_text = build_assignment_message(order)
                        
                        await safe_edit_message(
                            assigned_user_id,
                            order["upc_assignment_message_id"],
                            updated_text,
                            assignment_cta_keyboard(order_id)
                        )
                        
                        logger.info(f"Updated UPC message for order {order_id} - new position {position}/{new_total}")
        
        logger.info(f"Group {group_id} updated - {new_total} orders remaining")
    
    except Exception as e:
        logger.error(f"Error updating group on delivery: {e}")

async def show_delay_options(order_id: str, user_id: int):
    """Show delay options for the assigned courier - based on confirmed time"""
    try:
        order = STATE.get(order_id)
        if not order:
            return
        
        # Get the latest confirmed time from any vendor
        confirmed_times = order.get("confirmed_times", {})
        if not confirmed_times:
            await safe_send_message(
                user_id,
                "⚠️ No confirmed time available for delay calculation"
            )
            return
        
        vendors = order.get("vendors", [])
        
        # Multi-vendor: show vendor selection first
        if len(vendors) > 1:
            buttons = []
            for vendor in vendors:
                vendor_shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
                buttons.append([InlineKeyboardButton(
                    f"Request {vendor_shortcut}",
                    callback_data=f"delay_vendor_selected|{order_id}|{vendor}"
                )])
            
            # Add Back button
            buttons.append([InlineKeyboardButton("← Back", callback_data="hide")])
            
            await safe_send_message(
                user_id,
                "⏳ Select vendor to request delay:",
                InlineKeyboardMarkup(buttons)
            )
        else:
            # Single vendor: show time options directly
            await show_delay_time_picker(order_id, user_id, vendors[0] if vendors else None)

    except Exception as e:
        logger.error(f"Error showing delay options: {e}")


async def show_delay_time_picker(order_id: str, user_id: int, vendor: str = None):
    """Show time picker for delay request (called after vendor selection or directly for single vendor)"""
    try:
        order = STATE.get(order_id)
        if not order:
            return
        
        confirmed_times = order.get("confirmed_times", {})
        
        # Get confirmed time for specific vendor or latest time
        if vendor and vendor in confirmed_times:
            latest_time_str = confirmed_times[vendor]
        else:
            latest_time_str = max(confirmed_times.values())
        
        # Get order number for display
        order_num = order.get('name', '')[-2:] if len(order.get('name', '')) >= 2 else order.get('name', '')
        
        # Get vendor shortcut for display
        vendor_shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper()) if vendor else "vendors"
        
        try:
            # Parse the confirmed time
            hour, minute = map(int, latest_time_str.split(':'))
            base_time = now().replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # Calculate delay options: +5, +10, +15, +20 minutes
            delay_buttons = []
            minute_increments = [5, 10, 15, 20]
            
            for i, minutes_to_add in enumerate(minute_increments):
                delayed_time = base_time + timedelta(minutes=minutes_to_add)
                time_str = delayed_time.strftime("%H:%M")
                # UPC delay format: +5m → ⏰ 09:32
                button_text = f"+{minutes_to_add}m → ⏰ {time_str}"
                
                # Include vendor in callback if specified
                if vendor:
                    callback = f"delay_selected|{order_id}|{time_str}|{vendor}"
                else:
                    callback = f"delay_selected|{order_id}|{time_str}"
                
                delay_buttons.append([InlineKeyboardButton(
                    button_text,
                    callback_data=callback
                )])
            
            # Add Back button
            delay_buttons.append([InlineKeyboardButton("← Back", callback_data="hide")])
            
            await safe_send_message(
                user_id,
                f"⏳ Request new ({latest_time_str}) for 🔖 #{order_num} from {vendor_shortcut}",
                InlineKeyboardMarkup(delay_buttons)
            )
            
        except Exception as e:
            logger.error(f"Error parsing time for delay: {e}")
            await safe_send_message(
                user_id,
                "⚠️ Error calculating delay times"
            )

    except Exception as e:
        logger.error(f"Error showing delay time picker: {e}")

async def show_restaurant_selection(order_id: str, user_id: int):
    """Show restaurant selection for multi-vendor orders"""
    try:
        order = STATE.get(order_id)
        if not order:
            return

        vendors = order.get("vendors", [])
        buttons = []

        for vendor in vendors:
            vendor_shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
            buttons.append([InlineKeyboardButton(
                f"� Call {vendor_shortcut}",
                callback_data=f"call_vendor|{order_id}|{vendor}"
            )])
        
        # Add Back button
        buttons.append([InlineKeyboardButton("← Back", callback_data="hide")])

        await safe_send_message(
            user_id,
            "Select restaurant to call:",
            InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        logger.error(f"Error showing restaurant selection: {e}")

async def handle_unassign_order(order_id: str, user_id: int):
    """
    Handle order unassignment from courier.
    
    Flow:
    1. Courier clicks "Unassign" button in their private chat
    2. Delete UPC assignment message
    3. Clear assignment fields from order STATE
    4. Restore MDG message to pre-assignment state with assignment buttons
    5. Send notification to MDG about unassignment
    
    Args:
        order_id: Shopify order ID
        user_id: Courier's Telegram user_id who is unassigning
    """
    try:
        order = STATE.get(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for unassignment")
            return

        # Get courier name for notification
        from utils import COURIER_MAP
        courier_info = COURIER_MAP.get(str(user_id), {})
        courier_name = courier_info.get("username", f"User{user_id}")
        
        # Delete UPC assignment message
        if "upc_assignment_message_id" in order:
            await safe_delete_message(user_id, order["upc_assignment_message_id"])
            del order["upc_assignment_message_id"]
        
        # Clear assignment fields - revert to ready-for-assignment state
        order["status"] = "new"  # Reset to new status so assignment buttons can show
        if "assigned_to" in order:
            del order["assigned_to"]
        if "assigned_at" in order:
            del order["assigned_at"]
        if "assigned_by" in order:
            del order["assigned_by"]
        
        # Restore MDG message to show confirmation text (assignment buttons come next)
        if "mdg_message_id" in order:
            import mdg
            
            # Show confirmation message with vendor times
            confirmation_text = build_assignment_confirmation_message(order)
            
            # Update MDG - remove any existing buttons temporarily
            await safe_edit_message(
                DISPATCH_MAIN_CHAT_ID,
                order["mdg_message_id"],
                confirmation_text,
                None  # No buttons on main message
            )
        
        # Send notification to MDG (same style as delivery notification)
        order_num = order.get('name', '')[-2:] if len(order.get('name', '')) >= 2 else order.get('name', '')
        unassign_msg = f"🔖 #{order_num} was unassigned by {courier_name}."
        await safe_send_message(DISPATCH_MAIN_CHAT_ID, unassign_msg)
        
        # Re-show assignment buttons in MDG
        # Import here to avoid circular dependency
        from main import build_assignment_confirmation_message
        assignment_msg = await safe_send_message(
            DISPATCH_MAIN_CHAT_ID,
            build_assignment_confirmation_message(order),
            mdg_assignment_keyboard(order_id)
        )
        
        # Track assignment message for cleanup
        if "mdg_additional_messages" not in order:
            order["mdg_additional_messages"] = []
        order["mdg_additional_messages"].append(assignment_msg.message_id)
        
        logger.info(f"Order {order_id} unassigned by user {user_id} ({courier_name})")

    except Exception as e:
        logger.error(f"Error handling order unassignment: {e}")

async def send_delay_request_to_restaurants(order_id: str, new_time: str, user_id: int, vendor: str = None):
    """
    Send delay request to vendor(s) for this order.
    
    Args:
        order_id: Order ID
        new_time: New requested time (HH:MM)
        user_id: Courier user ID for confirmation message
        vendor: Specific vendor to send to (for multi-vendor), or None for all vendors (single vendor)
    """
    try:
        order = STATE.get(order_id)
        if not order:
            return
        
        # Determine which vendors to notify
        if vendor:
            # Multi-vendor: send to specific vendor only
            vendors_to_notify = [vendor]
        else:
            # Single vendor: send to all vendors
            vendors_to_notify = order.get("vendors", [])
        
        order_num = order.get('name', '')[-2:] if len(order.get('name', '')) >= 2 else order.get('name', '')
        
        # Send delay request to each vendor
        for v in vendors_to_notify:
            vendor_chat = VENDOR_GROUP_MAP.get(v)
            if vendor_chat:
                delay_msg = f"We have a delay, if possible prepare #{order_num} at {new_time}. If not, please keep it warm."
                
                # Import restaurant_response_keyboard from rg module
                from rg import restaurant_response_keyboard
                
                # Send with restaurant response buttons (Works / Later at...)
                await safe_send_message(
                    vendor_chat,
                    delay_msg,
                    restaurant_response_keyboard(new_time, order_id, v)
                )
                
                logger.info(f"Delay request sent to {v} for order {order_id} - new time {new_time}")
        
        # Confirm to user with updated format
        vendor_shortcuts = "+".join([RESTAURANT_SHORTCUTS.get(v, v[:2].upper()) for v in vendors_to_notify])
        await safe_send_message(
            user_id,
            f"📨 DELAY request ({new_time}) for 🔖 #{order_num} sent to {vendor_shortcuts}"
        )
        
    except Exception as e:
        logger.error(f"Error sending delay request: {e}")
        # Use custom error message based on exception type
        error_desc = get_error_description(e)
        await safe_send_message(user_id, f"⚠️ Error while sending a message: {error_desc}")

async def initiate_restaurant_call(order_id: str, vendor: str, user_id: int):
    """Initiate call to restaurant - placeholder for future Telegram call integration"""
    try:
        # For now, inform user to call directly
        # Future: This will integrate with Telegram calling when restaurant accounts are created
        vendor_shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
        await safe_send_message(
            user_id,
            f"� Please call {vendor_shortcut} directly.\n\n(Automatic Telegram calling will be available when restaurant accounts are set up)"
        )

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

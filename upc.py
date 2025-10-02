# upc.py - User Private Chat functions for Telegram Dispatch Bot

import asyncio
from datetime import datetime, timedelta
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from utils import logger, COURIER_MAP, DISPATCH_MAIN_CHAT_ID, VENDOR_GROUP_MAP, RESTAURANT_SHORTCUTS, safe_send_message, safe_edit_message

# =============================================================================
# ORDER ASSIGNMENT SYSTEM - UPC (User Private Chats)
# =============================================================================
# WORKFLOW: After ALL vendors confirm times → assignment buttons appear in MDG
# → User clicks "Assign to me" or "Assign to [user]" → order details sent to private chat
# → Courier receives CTA buttons (call, navigate, delay, restaurant call, delivered)
# =============================================================================

# Module-level STATE reference (configured from main.py)
STATE = None

def configure(state_ref):
    """Configure module-level STATE reference"""
    global STATE
    STATE = state_ref

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
            [InlineKeyboardButton("👉 Assign to...", callback_data=f"assign_to_menu|{order_id}")]
        ]
        return InlineKeyboardMarkup(buttons)
    except Exception as e:
        logger.error(f"Error building MDG assignment keyboard: {e}")
        return None

def courier_selection_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build courier selection menu for 'Assign to...' button"""
    try:
        buttons = []
        
        # Priority couriers (Bee 1, Bee 2, Bee 3) first
        priority_names = ["Bee 1", "Bee 2", "Bee 3"]
        for courier_name in priority_names:
            for user_id_str, user_data in COURIER_MAP.items():
                if isinstance(user_data, dict):
                    username = user_data.get("username", "")
                    if username == courier_name:
                        buttons.append([InlineKeyboardButton(
                            courier_name,
                            callback_data=f"assign_to_user|{order_id}|{user_id_str}"
                        )])
                        break
        
        # Then other couriers
        for user_id_str, user_data in COURIER_MAP.items():
            if isinstance(user_data, dict):
                username = user_data.get("username", "")
                if username not in priority_names:
                    buttons.append([InlineKeyboardButton(
                        username,
                        callback_data=f"assign_to_user|{order_id}|{user_id_str}"
                    )])
        
        return InlineKeyboardMarkup(buttons) if buttons else None
    except Exception as e:
        logger.error(f"Error building courier selection keyboard: {e}")
        return None

def assignment_keyboard_with_me(order_id: str, current_user_id: int) -> InlineKeyboardMarkup:
    """Build assignment keyboard including 'Assign to me' for current user"""
    try:
        # This function is deprecated - use mdg_assignment_keyboard instead
        return mdg_assignment_keyboard(order_id)
    except Exception as e:
        logger.error(f"Error building assignment keyboard with me: {e}")
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
        order["assigned_at"] = datetime.now()
        order["status"] = "assigned"

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

        # Remove assignment buttons - show only status
        await safe_edit_message(
            DISPATCH_MAIN_CHAT_ID,
            order["mdg_message_id"],
            updated_text,
            None  # No keyboard - assignment complete
        )

        logger.info(f"Updated MDG for order {order_id} - assigned to {assignee_name}")

    except Exception as e:
        logger.error(f"Error updating MDG with assignment: {e}")

def build_assignment_message(order: dict) -> str:
    """Build the assignment message sent to courier's private chat"""
    try:
        order_type = order.get("order_type", "shopify")
        
        # Header: 🔖 #34 - dishbee (without vendor shortcut)
        if order_type == "shopify":
            order_num = order.get('name', '')[-2:] if len(order.get('name', '')) >= 2 else order.get('name', '')
            header = f"🔖 #{order_num} - dishbee\n"
        else:
            header = f"� {order.get('name', 'Order')}\n"
        
        # Restaurant info with confirmed times and product quantities
        vendors = order.get("vendors", [])
        confirmed_times = order.get("confirmed_times", {})
        vendor_items = order.get("vendor_items", {})
        
        restaurant_section = ""
        for vendor in vendors:
            pickup_time = confirmed_times.get(vendor, "ASAP")
            
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
            
            restaurant_section += f"🏠 {vendor}: {pickup_time} 📦 {product_count}\n"
        
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
        
        customer_section = f"\n� {customer_name}\n"
        customer_section += f"🔺 {formatted_address}\n"
        
        # Optional info (tips, cash on delivery)
        optional_section = ""
        tips = order.get("tips", 0.0)
        if tips and float(tips) > 0:
            optional_section += f"\n❕ Tip: {float(tips):.2f}€\n"
        
        payment = order.get("payment_method", "Paid")
        total = order.get("total", "0.00€")
        if payment.lower() == "cash on delivery":
            optional_section += f"❕ Cash on delivery: {total}\n"
        
        # Phone number
        phone = order['customer']['phone']
        phone_section = f"\n📞 {phone}\n"
        
        # Combine all sections
        message = header + restaurant_section + customer_section + optional_section + phone_section
        
        return message

    except Exception as e:
        logger.error(f"Error building assignment message: {e}")
        return f"� **ORDER ASSIGNED** - Error formatting details"

def assignment_cta_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build CTA buttons for assigned orders in private chats"""
    try:
        order = STATE.get(order_id)
        if not order:
            return None

        buttons = []
        phone = order['customer']['phone']
        address = order['customer'].get('original_address', order['customer']['address'])

        # Row 1: Call customer, Navigate
        call_customer = InlineKeyboardButton(
            "☎️ Call customer",
            url=f"tel:{phone}" if phone and phone != "N/A" else None
        )
        
        # Google Maps navigation with cycling mode
        maps_url = f"https://www.google.com/maps/dir/?api=1&destination={address.replace(' ', '+')}&travelmode=bicycling"
        navigate = InlineKeyboardButton("🧭 Navigate", url=maps_url)
        
        buttons.append([call_customer, navigate])

        # Row 2: Delay order, Call restaurant
        delay = InlineKeyboardButton(
            "⏰ Delay",
            callback_data=f"delay_order|{order_id}"
        )

        vendors = order.get("vendors", [])
        if len(vendors) == 1:
            vendor = vendors[0]
            # Get vendor shortcut for button
            vendor_shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
            call_restaurant = InlineKeyboardButton(
                f"🍽 Call {vendor_shortcut}",
                callback_data=f"call_restaurant|{order_id}|{vendor}"
            )
            buttons.append([delay, call_restaurant])
        else:
            # Multi-vendor - show vendor selection
            call_restaurant = InlineKeyboardButton(
                "🍽 Call Restaurant",
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
            DISPATCH_MAIN_CHAT_ID,
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

        # Send confirmation to MDG: "Order #47 was delivered."
        order_num = order.get('name', '')[-2:] if len(order.get('name', '')) >= 2 else order.get('name', '')
        delivered_msg = f"Order #{order_num} was delivered."
        await safe_send_message(DISPATCH_MAIN_CHAT_ID, delivered_msg)
        
        # Update MDG original order message with "✅ Delivered" status
        if "mdg_message_id" in order:
            import mdg
            base_text = mdg.build_mdg_dispatch_text(order)
            assignee_info = COURIER_MAP.get(str(user_id), {})
            assignee_name = assignee_info.get("username", f"User{user_id}")
            
            updated_text = base_text + f"\n\n👤 **Assigned to:** {assignee_name}\n✅ **Delivered**"
            
            await safe_edit_message(
                DISPATCH_MAIN_CHAT_ID,
                order["mdg_message_id"],
                updated_text,
                None  # No keyboard
            )

        # Update private chat message
        completion_msg = "✅ **Delivery completed!**\n\nThank you for the successful delivery."
        await safe_send_message(user_id, completion_msg)

        logger.info(f"Order {order_id} marked as delivered by user {user_id}")

    except Exception as e:
        logger.error(f"Error handling delivery completion: {e}")

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
        
        # Use the latest confirmed time
        latest_time_str = max(confirmed_times.values())
        
        try:
            # Parse the confirmed time
            hour, minute = map(int, latest_time_str.split(':'))
            base_time = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # Calculate delay options: +5, +10, +15, +20 minutes
            delay_buttons = []
            for minutes_to_add in [5, 10, 15, 20]:
                delayed_time = base_time + timedelta(minutes=minutes_to_add)
                time_str = delayed_time.strftime("%H:%M")
                delay_buttons.append([InlineKeyboardButton(
                    time_str,
                    callback_data=f"delay_selected|{order_id}|{time_str}"
                )])
            
            await safe_send_message(
                user_id,
                f"⏰ Select new delivery time (current: {latest_time_str}):",
                InlineKeyboardMarkup(delay_buttons)
            )
            
        except Exception as e:
            logger.error(f"Error parsing time for delay: {e}")
            await safe_send_message(
                user_id,
                "⚠️ Error calculating delay times"
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
            vendor_shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
            buttons.append([InlineKeyboardButton(
                f"🍽 Call {vendor_shortcut}",
                callback_data=f"call_restaurant|{order_id}|{vendor}"
            )])

        await safe_send_message(
            user_id,
            "Select restaurant to call:",
            InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        logger.error(f"Error showing restaurant selection: {e}")

async def send_delay_request_to_restaurants(order_id: str, new_time: str, user_id: int):
    """Send delay request to all vendors for this order"""
    try:
        order = STATE.get(order_id)
        if not order:
            return
        
        vendors = order.get("vendors", [])
        order_num = order.get('name', '')[-2:] if len(order.get('name', '')) >= 2 else order.get('name', '')
        
        # Send delay request to each vendor
        for vendor in vendors:
            vendor_chat = VENDOR_GROUP_MAP.get(vendor)
            if vendor_chat:
                delay_msg = f"We have a delay, if possible prepare #{order_num} at {new_time}. If not, please keep it warm."
                
                # Import restaurant_response_keyboard from rg module
                from rg import restaurant_response_keyboard
                
                # Send with restaurant response buttons (Works / Later at...)
                await safe_send_message(
                    vendor_chat,
                    delay_msg,
                    restaurant_response_keyboard(new_time, order_id, vendor)
                )
                
                logger.info(f"Delay request sent to {vendor} for order {order_id} - new time {new_time}")
        
        # Confirm to user
        await safe_send_message(
            user_id,
            f"✅ Delay request sent to restaurant(s) for {new_time}"
        )
        
    except Exception as e:
        logger.error(f"Error sending delay request: {e}")
        await safe_send_message(user_id, "⚠️ Error sending delay request")

async def initiate_restaurant_call(order_id: str, vendor: str, user_id: int):
    """Initiate call to restaurant - placeholder for future Telegram call integration"""
    try:
        # For now, inform user to call directly
        # Future: This will integrate with Telegram calling when restaurant accounts are created
        await safe_send_message(
            user_id,
            f"🍽 Please call {vendor} directly.\n\n(Automatic Telegram calling will be available when restaurant accounts are set up)"
        )

        logger.info(f"User {user_id} initiated call to {vendor} for order {order_id}")

    except Exception as e:
        logger.error(f"Error initiating restaurant call: {e}")

# Placeholder functions for future implementation
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
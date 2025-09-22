# rg.py - Restaurant Group functions for Telegram Dispatch Bot

import asyncio
from datetime import datetime, timedelta
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from utils import (
    STATE, DISPATCH_MAIN_CHAT_ID, VENDOR_GROUP_MAP,
    logger, safe_send_message, safe_edit_message
)
from upc import check_all_vendors_confirmed, assignment_keyboard

async def show_assignment_buttons(order_id: str):
    """Show assignment buttons in MDG when all vendors have confirmed"""
    try:
        order = STATE.get(order_id)
        if not order or "mdg_message_id" not in order:
            return

        # Get assignment keyboard
        assign_keyboard = assignment_keyboard(order_id)
        if not assign_keyboard:
            return

        # Update MDG message with assignment buttons
        import mdg
        current_text = mdg.build_mdg_dispatch_text(order)
        updated_text = current_text + "\n\n👤 **Ready for assignment!**"

        await safe_edit_message(
            DISPATCH_MAIN_CHAT_ID,
            order["mdg_message_id"],
            updated_text,
            assign_keyboard
        )

        logger.info(f"Assignment buttons shown for order {order_id}")

    except Exception as e:
        logger.error(f"Error showing assignment buttons: {e}")

async def handle_rg_callback(action: str, data: list):
    """Handle Restaurant Group callback actions"""
    try:
        # VENDOR RESPONSES
        if action == "works":
            order_id, vendor = data[1], data[2]
            order = STATE.get(order_id)
            if order:
                # Track confirmed time per vendor
                if "vendor_confirmed_times" not in order:
                    order["vendor_confirmed_times"] = {}
                order["vendor_confirmed_times"][vendor] = order.get("requested_time", "ASAP")

            # Post status to MDG
            status_msg = f"■ {vendor} replied: Works 👍 ■"
            await safe_send_message(DISPATCH_MAIN_CHAT_ID, status_msg)

            # Check if all vendors have confirmed - if so, show assignment buttons
            if order and check_all_vendors_confirmed(order_id):
                await show_assignment_buttons(order_id)

        elif action == "later":
            order_id, vendor = data[1], data[2]
            order = STATE.get(order_id)
            requested = order.get("requested_time", "ASAP") if order else "ASAP"

            # Show time picker for vendor response
            await safe_send_message(
                VENDOR_GROUP_MAP[vendor],
                f"Select later time:",
                time_picker_keyboard(order_id, "later_time", requested)
            )

        elif action == "later_time":
            order_id, selected_time = data[1], data[2]
            order = STATE.get(order_id)
            if order:
                # Track confirmed time per vendor
                if "vendor_confirmed_times" not in order:
                    order["vendor_confirmed_times"] = {}
                
                # Find which vendor this is from
                for vendor in order["vendors"]:
                    if vendor in order.get("vendor_messages", {}):
                        order["vendor_confirmed_times"][vendor] = selected_time
                        status_msg = f"■ {vendor} replied: Later at {selected_time} ■"
                        await safe_send_message(DISPATCH_MAIN_CHAT_ID, status_msg)
                        break

                # Check if all vendors have confirmed - if so, show assignment buttons
                if check_all_vendors_confirmed(order_id):
                    await show_assignment_buttons(order_id)

        elif action == "prepare":
            order_id, vendor = data[1], data[2]

            # Show time picker for vendor response
            await safe_send_message(
                VENDOR_GROUP_MAP[vendor],
                f"Select preparation time:",
                time_picker_keyboard(order_id, "prepare_time", None)
            )

        elif action == "prepare_time":
            order_id, selected_time = data[1], data[2]
            order = STATE.get(order_id)
            if order:
                # Track confirmed time per vendor
                if "vendor_confirmed_times" not in order:
                    order["vendor_confirmed_times"] = {}
                
                # Find which vendor this is from
                for vendor in order["vendors"]:
                    if vendor in order.get("vendor_messages", {}):
                        order["vendor_confirmed_times"][vendor] = selected_time
                        status_msg = f"■ {vendor} replied: Will prepare at {selected_time} ■"
                        await safe_send_message(DISPATCH_MAIN_CHAT_ID, status_msg)
                        break

                # Check if all vendors have confirmed - if so, show assignment buttons
                if check_all_vendors_confirmed(order_id):
                    await show_assignment_buttons(order_id)

        elif action == "wrong":
            order_id, vendor = data[1], data[2]
            # Show "Something is wrong" submenu
            wrong_buttons = [
                [InlineKeyboardButton("Ordered product(s) not available", callback_data=f"wrong_unavailable|{order_id}|{vendor}")],
                [InlineKeyboardButton("Order is canceled", callback_data=f"wrong_canceled|{order_id}|{vendor}")],
                [InlineKeyboardButton("Technical issue", callback_data=f"wrong_technical|{order_id}|{vendor}")],
                [InlineKeyboardButton("Something else", callback_data=f"wrong_other|{order_id}|{vendor}")],
                [InlineKeyboardButton("We have a delay", callback_data=f"wrong_delay|{order_id}|{vendor}")]
            ]

            await safe_send_message(
                VENDOR_GROUP_MAP[vendor],
                "What's wrong?",
                InlineKeyboardMarkup(wrong_buttons)
            )

        elif action == "wrong_unavailable":
            order_id, vendor = data[1], data[2]
            order = STATE.get(order_id)
            if order and order.get("order_type") == "shopify":
                msg = f"■ {vendor}: Please call the customer and organize a replacement. If no replacement is possible, write a message to dishbee. ■"
            else:
                msg = f"■ {vendor}: Please call the customer and organize a replacement or a refund. ■"
            await safe_send_message(DISPATCH_MAIN_CHAT_ID, msg)

        elif action == "wrong_canceled":
            order_id, vendor = data[1], data[2]
            await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: Order is canceled ■")

        elif action in ["wrong_technical", "wrong_other"]:
            order_id, vendor = data[1], data[2]
            await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: Write a message to dishbee and describe the issue ■")

        elif action == "wrong_delay":
            order_id, vendor = data[1], data[2]
            order = STATE.get(order_id)
            agreed_time = order.get("confirmed_time") or order.get("requested_time", "ASAP") if order else "ASAP"

            # Show delay time picker
            try:
                if agreed_time != "ASAP":
                    hour, minute = map(int, agreed_time.split(':'))
                    base_time = datetime.now().replace(hour=hour, minute=minute)
                else:
                    base_time = datetime.now()

                delay_intervals = []
                for minutes in [5, 10, 15, 20]:
                    time_option = base_time + timedelta(minutes=minutes)
                    delay_intervals.append(time_option.strftime("%H:%M"))

                delay_buttons = []
                for i in range(0, len(delay_intervals), 2):
                    row = [InlineKeyboardButton(delay_intervals[i], callback_data=f"delay_time|{order_id}|{vendor}|{delay_intervals[i]}")]
                    if i + 1 < len(delay_intervals):
                        row.append(InlineKeyboardButton(delay_intervals[i + 1], callback_data=f"delay_time|{order_id}|{vendor}|{delay_intervals[i + 1]}"))
                    delay_buttons.append(row)

                await safe_send_message(
                    VENDOR_GROUP_MAP[vendor],
                    "Select delay time:",
                    InlineKeyboardMarkup(delay_buttons)
                )
            except:
                await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: We have a delay ■")

        elif action == "delay_time":
            order_id, vendor, delay_time = data[1], data[2], data[3]
            await safe_send_message(DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: We have a delay - new time {delay_time} ■")

    except Exception as e:
        logger.error(f"Error handling RG callback {action}: {e}")

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
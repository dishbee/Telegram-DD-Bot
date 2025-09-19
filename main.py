# main.py - Main Flask application for Telegram Dispatch Bot

# =============================================================================
# MAIN WORKFLOW OVERVIEW
# =============================================================================
# Order placed → arrives in MDG and RG → user requests time from restaurants
# → restaurants confirm time → user receives info in MDG → assigns to himself
# or another user (private chat with BOT) → order delivered → user confirms
# delivery → order state changed to delivered
#
# CODE ORGANIZATION:
# 1. utils.py - Shared utilities, constants, and global state
# 2. mdg.py - Main Dispatching Group functions
# 3. rg.py - Restaurant Group functions
# 4. upc.py - User Private Chat functions
# =============================================================================

import os
import json
import hmac
import hashlib
import base64
import asyncio
import logging
import threading
import requests  # Add this for synchronous HTTP calls
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import Flask, request, jsonify
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode

# Import modules
import utils
import mdg
import rg
import upc
from utils import STATE, logger, RESTAURANT_SHORTCUTS, get_recent_orders_for_same_time, VENDOR_GROUP_MAP, DISPATCH_MAIN_CHAT_ID, BOT_TOKEN, bot, safe_send_message, safe_edit_message, safe_delete_message, cleanup_mdg_messages, verify_webhook, fmt_address, RECENT_ORDERS, loop
from mdg import build_mdg_dispatch_text, build_vendor_summary_text, build_vendor_details_text

# --- FLASK APP SETUP ---
app = Flask(__name__)

# --- WEBHOOK ENDPOINTS ---
@app.route("/", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        "status": "healthy",
        "service": "telegram-dispatch-bot",
        "orders_in_state": len(utils.STATE),
        "timestamp": datetime.now().isoformat()
    }), 200

# --- TELEGRAM WEBHOOK ---
@app.route(f"/{utils.BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    """Handle Telegram webhooks"""
    try:
        upd = request.get_json(force=True)
        if not upd:
            return "OK"

        # Log all incoming updates for spam detection
        utils.logger.info(f"=== INCOMING UPDATE ===")
        utils.logger.info(f"Update ID: {upd.get('update_id')}")
        utils.logger.info(f"Timestamp: {datetime.now().isoformat()}")

        # Check for regular messages (potential spam source)
        if "message" in upd:
            msg = upd["message"]
            from_user = msg.get("from", {})
            chat = msg.get("chat", {})
            text = msg.get("text", "")

            utils.logger.info(f"MESSAGE RECEIVED:")
            utils.logger.info(f"  Chat ID: {chat.get('id')}")
            utils.logger.info(f"  Chat Type: {chat.get('type')}")
            utils.logger.info(f"  Chat Title: {chat.get('title', 'N/A')}")
            utils.logger.info(f"  From User ID: {from_user.get('id')}")
            utils.logger.info(f"  From Username: {from_user.get('username', 'N/A')}")
            utils.logger.info(f"  From First Name: {from_user.get('first_name', 'N/A')}")
            utils.logger.info(f"  From Last Name: {from_user.get('last_name', 'N/A')}")
            utils.logger.info(f"  Message Text: {text[:200]}{'...' if len(text) > 200 else ''}")
            utils.logger.info(f"  Message Length: {len(text)}")

            # Flag potential spam
            if "FOXY" in text.upper() or "airdrop" in text.lower() or "t.me/" in text:
                utils.logger.warning(f"🚨 POTENTIAL SPAM DETECTED: {text[:100]}...")

        cq = upd.get("callback_query")
        if not cq:
            utils.logger.info("=== NO CALLBACK QUERY - END UPDATE ===")
            return "OK"

        # Answer callback query immediately (synchronously)
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{utils.BOT_TOKEN}/answerCallbackQuery",
                json={"callback_query_id": cq["id"]},
                timeout=5
            )
            if not response.ok:
                utils.logger.error(f"Failed to answer callback query: {response.text}")
        except Exception as e:
            utils.logger.error(f"answer_callback_query error: {e}")

        # Process the callback in background
        utils.run_async(handle_callback(cq))
        return "OK"

    except Exception as e:
        utils.logger.error(f"Telegram webhook error: {e}")
        return jsonify({"error": "Internal server error"}), 500

async def handle_callback(cq):
    """Handle callback queries from Telegram"""
    data = (cq.get("data") or "").split("|")
    if not data:
        return

    action = data[0]
    utils.logger.info(f"Raw callback data: {cq.get('data')}")
    utils.logger.info(f"Parsed callback data: {data}")
    utils.logger.info(f"Processing callback: {action}")

    try:
        # Handle assignment callbacks first
        if action in ["assign_me", "assign_user", "mark_delivered", "confirm_delivered",
                     "delay_order", "call_restaurant", "select_restaurant", "delay_minutes", "delay_custom"]:
            await handle_assignment_callbacks(cq)
            return
        # VENDOR SELECTION (for multi-vendor orders)
        if action == "req_vendor":
            order_id, vendor = data[1], data[2]
            utils.logger.info(f"Selected vendor {vendor} for order {order_id}")

            # Send vendor-specific time request buttons
            msg = await utils.safe_send_message(
                utils.DISPATCH_MAIN_CHAT_ID,
                f"📍 Request time from {vendor}:",
                mdg.vendor_time_keyboard(order_id, vendor)
            )

            # Track additional message for cleanup
            order = utils.STATE.get(order_id)
            if order:
                order["mdg_additional_messages"].append(msg.message_id)

        # VENDOR-SPECIFIC ACTIONS
        elif action == "vendor_asap":
            order_id, vendor = data[1], data[2]
            order = utils.STATE.get(order_id)
            if not order:
                utils.logger.warning(f"Order {order_id} not found in state")
                return

            # Send ASAP request only to specific vendor
            vendor_chat = utils.VENDOR_GROUP_MAP.get(vendor)
            if vendor_chat:
                if order["order_type"] == "shopify":
                    msg = f"#{order['name'][-2:]} ASAP?"
                else:
                    addr = order['customer']['address'].split(',')[0]
                    msg = f"*{addr}* ASAP?"

                # Send with restaurant response buttons
                await utils.safe_send_message(
                    vendor_chat,
                    msg,
                    mdg.restaurant_response_keyboard("ASAP", order_id, vendor)
                )

            # Update MDG status
            status_msg = await utils.safe_send_message(
                utils.DISPATCH_MAIN_CHAT_ID,
                f"✅ ASAP request sent to {vendor}"
            )

            # Clean up additional MDG messages
            await utils.cleanup_mdg_messages(order_id)

        elif action == "vendor_time":
            order_id, vendor = data[1], data[2]
            utils.logger.info(f"Processing TIME request for {vendor}")
            order = utils.STATE.get(order_id)
            if not order:
                utils.logger.warning(f"Order {order_id} not found in state")
                return

            # Show TIME submenu for this vendor (same as single-vendor)
            keyboard = mdg.mdg_time_submenu_keyboard(order_id, vendor)
            title_text = f"Lederergasse 15 ({utils.RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())}, #{order['name'][-2:] if len(order['name']) >= 2 else order['name']}, {datetime.now().strftime('%H:%M')}) +"
            msg = await utils.safe_send_message(
                utils.DISPATCH_MAIN_CHAT_ID,
                title_text,
                keyboard
            )

            # Track additional message for cleanup
            order["mdg_additional_messages"].append(msg.message_id)

        elif action == "vendor_same":
            utils.logger.info("VENDOR_SAME: Starting handler")
            order_id, vendor = data[1], data[2]
            utils.logger.info(f"VENDOR_SAME: Processing for order {order_id}, vendor {vendor}")

            recent = mdg.get_recent_orders_for_same_time(order_id)
            if recent:
                msg = await utils.safe_send_message(
                    utils.DISPATCH_MAIN_CHAT_ID,
                    f"🔗 Select order to match timing for {vendor}:",
                    mdg.same_time_keyboard(order_id)
                )
                # Track additional message for cleanup
                order = utils.STATE.get(order_id)
                if order:
                    order["mdg_additional_messages"].append(msg.message_id)
            else:
                msg = await utils.safe_send_message(
                    utils.DISPATCH_MAIN_CHAT_ID,
                    "No recent orders found (last 1 hour)"
                )
                # Track additional message for cleanup
                order = utils.STATE.get(order_id)
                if order:
                    order["mdg_additional_messages"].append(msg.message_id)

        elif action == "vendor_exact":
            utils.logger.info("VENDOR_EXACT: Starting handler")
            order_id, vendor = data[1], data[2]
            utils.logger.info(f"VENDOR_EXACT: Processing for order {order_id}, vendor {vendor}")

            # Show exact time picker
            msg = await utils.safe_send_message(
                utils.DISPATCH_MAIN_CHAT_ID,
                f"🕒 Set exact time for {vendor}:",
                mdg.exact_time_keyboard(order_id)
            )

            # Track additional message for cleanup
            order = utils.STATE.get(order_id)
            if order:
                order["mdg_additional_messages"].append(msg.message_id)

        elif action == "smart_time":
            order_id, vendor, selected_time = data[1], data[2], data[3]
            order = utils.STATE.get(order_id)
            if not order:
                return

            # Send time request to specific vendor
            vendor_chat = utils.VENDOR_GROUP_MAP.get(vendor) if vendor != "all" else None

            if vendor == "all":
                # Single vendor order - send to all vendors
                for v in order["vendors"]:
                    vc = utils.VENDOR_GROUP_MAP.get(v)
                    if vc:
                        if order["order_type"] == "shopify":
                            msg = f"#{order['name'][-2:]} at {selected_time}?"
                        else:
                            addr = order['customer']['address'].split(',')[0]
                            msg = f"*{addr}* at {selected_time}?"

                        await utils.safe_send_message(
                            vc,
                            msg,
                            mdg.restaurant_response_keyboard(selected_time, order_id, v)
                        )
            else:
                # Multi-vendor - send to specific vendor
                if vendor_chat:
                    if order["order_type"] == "shopify":
                        msg = f"#{order['name'][-2:]} at {selected_time}?"
                    else:
                        addr = order['customer']['address'].split(',')[0]
                        msg = f"*{addr}* at {selected_time}?"

                    await utils.safe_send_message(
                        vendor_chat,
                        msg,
                        mdg.restaurant_response_keyboard(selected_time, order_id, vendor)
                    )

            # Update state and MDG
            order["requested_time"] = selected_time
            status_msg = await utils.safe_send_message(
                utils.DISPATCH_MAIN_CHAT_ID,
                f"✅ Time request ({selected_time}) sent to {vendor if vendor != 'all' else 'vendors'}"
            )

            # Clean up additional MDG messages
            await utils.cleanup_mdg_messages(order_id)

        # ORIGINAL TIME REQUEST ACTIONS (MDG)
        elif action == "req_asap":
            order_id = data[1]
            order = utils.STATE.get(order_id)
            if not order:
                utils.logger.warning(f"Order {order_id} not found in state")
                return

            # For single vendor, send ASAP to all vendors
            for vendor in order["vendors"]:
                vendor_chat = utils.VENDOR_GROUP_MAP.get(vendor)
                if vendor_chat:
                    if order["order_type"] == "shopify":
                        msg = f"#{order['name'][-2:]} ASAP?"
                    else:
                        addr = order['customer']['address'].split(',')[0]
                        msg = f"*{addr}* ASAP?"

                    # ASAP request buttons
                    await utils.safe_send_message(
                        vendor_chat,
                        msg,
                        mdg.restaurant_response_keyboard("ASAP", order_id, vendor)
                    )

            # Update MDG with ASAP status but keep time request buttons
            order["requested_time"] = "ASAP"
            vendors = order.get("vendors", [])
            utils.logger.info(f"Order {order_id} has vendors: {vendors} (count: {len(vendors)})")

            if len(vendors) > 1:
                utils.logger.info(f"MULTI-VENDOR detected: {vendors}")
            else:
                utils.logger.info(f"SINGLE VENDOR detected: {vendors}")

            mdg_text = mdg.build_mdg_dispatch_text(order) + f"\n\n⏰ Requested: ASAP"
            await utils.safe_edit_message(
                utils.DISPATCH_MAIN_CHAT_ID,
                order["mdg_message_id"],
                mdg_text,
                mdg.mdg_time_request_keyboard(order_id)  # Keep same buttons
            )

            # Clean up additional MDG messages
            await utils.cleanup_mdg_messages(order_id)

        elif action == "req_time":
            order_id = data[1]
            utils.logger.info(f"Processing TIME request for order {order_id}")
            order = utils.STATE.get(order_id)
            if not order:
                utils.logger.error(f"Order {order_id} not found in STATE")
                return

            vendors = order.get("vendors", [])
            utils.logger.info(f"Order {order_id} has vendors: {vendors} (count: {len(vendors)})")

            # For single vendor, show TIME submenu per assignment
            if len(vendors) <= 1:
                utils.logger.info(f"SINGLE VENDOR detected: {vendors}")
                keyboard = mdg.mdg_time_submenu_keyboard(order_id)
                title_text = f"{order['customer']['address'].split(',')[0]} ({utils.RESTAURANT_SHORTCUTS.get(vendors[0], vendors[0][:2].upper())}, #{order['name'][-2:] if len(order['name']) >= 2 else order['name']}, {datetime.now().strftime('%H:%M')}) +"
                msg = await utils.safe_send_message(
                    utils.DISPATCH_MAIN_CHAT_ID,
                    title_text,
                    keyboard
                )

                # Track additional message for cleanup
                order["mdg_additional_messages"].append(msg.message_id)
            else:
                # For multi-vendor, this shouldn't happen as they have vendor buttons
                utils.logger.warning(f"Unexpected req_time for multi-vendor order {order_id}")

        elif action == "time_plus":
            order_id, minutes = data[1], int(data[2])
            vendor = data[3] if len(data) > 3 else None
            utils.logger.info(f"Processing +{minutes} minutes for order {order_id}" + (f" (vendor: {vendor})" if vendor else ""))
            order = utils.STATE.get(order_id)
            if not order:
                return

            # Calculate new time
            current_time = datetime.now()
            new_time = current_time + timedelta(minutes=minutes)
            requested_time = new_time.strftime("%H:%M")

            # Send time request to vendors
            if vendor:
                # Multi-vendor: send to specific vendor only
                vendor_chat = utils.VENDOR_GROUP_MAP.get(vendor)
                if vendor_chat:
                    if order["order_type"] == "shopify":
                        msg = f"#{order['name'][-2:]} at {requested_time}?"
                    else:
                        addr = order['customer']['address'].split(',')[0]
                        msg = f"*{addr}* at {requested_time}?"

                    await utils.safe_send_message(
                        vendor_chat,
                        msg,
                        mdg.restaurant_response_keyboard(requested_time, order_id, vendor)
                    )
            else:
                # Single vendor: send to all vendors
                for vendor in order["vendors"]:
                    vendor_chat = utils.VENDOR_GROUP_MAP.get(vendor)
                    if vendor_chat:
                        if order["order_type"] == "shopify":
                            msg = f"#{order['name'][-2:]} at {requested_time}?"
                        else:
                            addr = order['customer']['address'].split(',')[0]
                            msg = f"*{addr}* at {requested_time}?"

                        await utils.safe_send_message(
                            vendor_chat,
                            msg,
                            mdg.restaurant_response_keyboard(requested_time, order_id, vendor)
                        )

            # Update MDG
            order["requested_time"] = requested_time
            mdg_text = mdg.build_mdg_dispatch_text(order) + f"\n\n⏰ Requested: {requested_time}"
            await utils.safe_edit_message(
                utils.DISPATCH_MAIN_CHAT_ID,
                order["mdg_message_id"],
                mdg_text,
                mdg.mdg_time_request_keyboard(order_id)
            )

            # Clean up additional MDG messages
            await utils.cleanup_mdg_messages(order_id)

        elif action == "req_same":
            order_id = data[1]
            utils.logger.info(f"Processing SAME TIME AS request for order {order_id}")

            recent = mdg.get_recent_orders_for_same_time(order_id)
            if recent:
                keyboard = mdg.same_time_keyboard(order_id)
                msg = await utils.safe_send_message(
                    utils.DISPATCH_MAIN_CHAT_ID,
                    "🔗 Select order to match timing:",
                    keyboard
                )

                # Track additional message for cleanup
                order = utils.STATE.get(order_id)
                if order:
                    order["mdg_additional_messages"].append(msg.message_id)
            else:
                msg = await utils.safe_send_message(
                    utils.DISPATCH_MAIN_CHAT_ID,
                    "No recent orders found (last 1 hour)"
                )

                # Track additional message for cleanup
                order = utils.STATE.get(order_id)
                if order:
                    order["mdg_additional_messages"].append(msg.message_id)

        elif action == "no_recent":
            # Handle click on disabled "Same as" button
            msg = await utils.safe_send_message(
                utils.DISPATCH_MAIN_CHAT_ID,
                "No recent confirmed orders available to match timing with"
            )

            # Track additional message for cleanup
            order_id = data[1] if len(data) > 1 else None
            if order_id:
                order = utils.STATE.get(order_id)
                if order:
                    order["mdg_additional_messages"].append(msg.message_id)

        elif action == "req_exact":
            order_id = data[1]
            utils.logger.info(f"Processing REQUEST EXACT TIME for order {order_id}")

            # Show hour picker for exact time
            msg = await utils.safe_send_message(
                utils.DISPATCH_MAIN_CHAT_ID,
                "🕒 Select hour:",
                mdg.exact_time_keyboard(order_id)
            )

            # Track additional message for cleanup
            order = utils.STATE.get(order_id)
            if order:
                order["mdg_additional_messages"].append(msg.message_id)

        elif action == "same_selected":
            order_id, reference_order_id = data[1], data[2]
            order = utils.STATE.get(order_id)
            reference_order = utils.STATE.get(reference_order_id)

            if not order or not reference_order:
                return

            # Get time from reference order
            reference_time = reference_order.get("confirmed_time") or reference_order.get("requested_time", "ASAP")

            # Send same time request to vendors
            for vendor in order["vendors"]:
                vendor_chat = utils.VENDOR_GROUP_MAP.get(vendor)
                if vendor_chat:
                    # Check if same restaurant as reference order
                    if vendor in reference_order.get("vendors", []):
                        # Same restaurant - special message
                        if order["order_type"] == "shopify":
                            current_display = f"#{order['name'][-2:]}"
                            ref_display = f"#{reference_order['name'][-2:]}"
                            msg = f"Can you prepare {current_display} together with {ref_display} at the same time {reference_time}?"
                        else:
                            current_addr = order['customer']['address'].split(',')[0]
                            ref_addr = reference_order['customer']['address'].split(',')[0]
                            msg = f"Can you prepare *{current_addr}* together with *{ref_addr}* at the same time {reference_time}?"
                    else:
                        # Different restaurant - standard message
                        if order["order_type"] == "shopify":
                            msg = f"#{order['name'][-2:]} at {reference_time}?"
                        else:
                            addr = order['customer']['address'].split(',')[0]
                            msg = f"*{addr}* at {reference_time}?"

                    await utils.safe_send_message(
                        vendor_chat,
                        msg,
                        mdg.restaurant_response_keyboard(reference_time, order_id, vendor)
                    )

            # Update MDG
            order["requested_time"] = reference_time
            mdg_text = mdg.build_mdg_dispatch_text(order) + f"\n\n⏰ Requested: {reference_time} (same as {reference_order.get('name', 'other order')})"
            await utils.safe_edit_message(
                utils.DISPATCH_MAIN_CHAT_ID,
                order["mdg_message_id"],
                mdg_text,
                mdg.mdg_time_request_keyboard(order_id)
            )

            # Clean up additional MDG messages
            await utils.cleanup_mdg_messages(order_id)

        # EXACT TIME ACTIONS
        elif action == "exact_hour":
            order_id, hour = data[1], data[2]
            utils.logger.info(f"Processing exact hour {hour} for order {order_id}")

            # Edit the current message to show minute picker
            chat_id = cq["message"]["chat"]["id"]
            message_id = cq["message"]["message_id"]

            await utils.safe_edit_message(
                chat_id,
                message_id,
                f"🕒 Select exact time (hour {hour}):",
                mdg.exact_hour_keyboard(order_id, int(hour))
            )

        elif action == "exact_selected":
            order_id, selected_time = data[1], data[2]
            order = utils.STATE.get(order_id)
            if not order:
                return

            # Send time request to vendors
            for vendor in order["vendors"]:
                vendor_chat = utils.VENDOR_GROUP_MAP.get(vendor)
                if vendor_chat:
                    if order["order_type"] == "shopify":
                        msg = f"#{order['name'][-2:]} at {selected_time}?"
                    else:
                        addr = order['customer']['address'].split(',')[0]
                        msg = f"*{addr}* at {selected_time}?"

                    await utils.safe_send_message(
                        vendor_chat,
                        msg,
                        mdg.restaurant_response_keyboard(selected_time, order_id, vendor)
                    )

            # Update MDG
            order["requested_time"] = selected_time
            mdg_text = mdg.build_mdg_dispatch_text(order) + f"\n\n⏰ Requested: {selected_time}"
            await utils.safe_edit_message(
                utils.DISPATCH_MAIN_CHAT_ID,
                order["mdg_message_id"],
                mdg_text,
                mdg.mdg_time_request_keyboard(order_id)
            )

            # Delete the time picker message
            chat_id = cq["message"]["chat"]["id"]
            message_id = cq["message"]["message_id"]
            await utils.safe_delete_message(chat_id, message_id)

            # Clean up additional MDG messages
            await utils.cleanup_mdg_messages(order_id)

        elif action == "exact_back_hours":
            order_id = data[1]
            utils.logger.info(f"Going back to hours for order {order_id}")

            # Edit current message back to hour picker
            chat_id = cq["message"]["chat"]["id"]
            message_id = cq["message"]["message_id"]

            await utils.safe_edit_message(
                chat_id,
                message_id,
                "🕒 Select hour:",
                mdg.exact_time_keyboard(order_id)
            )

        elif action == "exact_hide":
            order_id = data[1]
            utils.logger.info(f"Hiding exact time picker for order {order_id}")

            # Delete the exact time picker message
            chat_id = cq["message"]["chat"]["id"]
            message_id = cq["message"]["message_id"]

            await utils.safe_delete_message(chat_id, message_id)

        # VENDOR RESPONSES
        elif action == "toggle":
            order_id, vendor = data[1], data[2]
            order = utils.STATE.get(order_id)
            if not order:
                utils.logger.warning(f"Order {order_id} not found in state")
                return

            expanded = not order["vendor_expanded"].get(vendor, False)
            order["vendor_expanded"][vendor] = expanded
            utils.logger.info(f"Toggling vendor message for {vendor}, expanded: {expanded}")

            # Update vendor message
            if expanded:
                text = mdg.build_vendor_details_text(order, vendor)
            else:
                text = mdg.build_vendor_summary_text(order, vendor)

            await utils.safe_edit_message(
                utils.VENDOR_GROUP_MAP[vendor],
                order["vendor_messages"][vendor],
                text,
                mdg.vendor_keyboard(order_id, vendor, expanded)
            )

        elif action == "works":
            order_id, vendor = data[1], data[2]
            order = utils.STATE.get(order_id)
            if order:
                # Track confirmed time
                order["confirmed_time"] = order.get("requested_time", "ASAP")
                order["confirmed_by"] = vendor

            # Post status to MDG
            status_msg = f"■ {vendor} replied: Works 👍 ■"
            await utils.safe_send_message(utils.DISPATCH_MAIN_CHAT_ID, status_msg)

            # Check if all vendors have confirmed - show assignment buttons if ready
            if upc.check_all_vendors_confirmed(order_id):
                await show_assignment_buttons(order_id)

        elif action == "later":
            order_id, vendor = data[1], data[2]
            order = utils.STATE.get(order_id)
            requested = order.get("requested_time", "ASAP") if order else "ASAP"

            # Show time picker for vendor response
            await utils.safe_send_message(
                utils.VENDOR_GROUP_MAP[vendor],
                f"Select later time:",
                mdg.time_picker_keyboard(order_id, "later_time", requested)
            )

        elif action == "later_time":
            order_id, selected_time = data[1], data[2]
            order = utils.STATE.get(order_id)
            if order:
                # Track confirmed time
                order["confirmed_time"] = selected_time

                # Find which vendor this is from
                for vendor in order["vendors"]:
                    if vendor in order.get("vendor_messages", {}):
                        status_msg = f"■ {vendor} replied: Later at {selected_time} ■"
                        await utils.safe_send_message(utils.DISPATCH_MAIN_CHAT_ID, status_msg)
                        break

        elif action == "prepare":
            order_id, vendor = data[1], data[2]

            # Show time picker for vendor response
            await utils.safe_send_message(
                utils.VENDOR_GROUP_MAP[vendor],
                f"Select preparation time:",
                mdg.time_picker_keyboard(order_id, "prepare_time", None)
            )

        elif action == "prepare_time":
            order_id, selected_time = data[1], data[2]
            order = utils.STATE.get(order_id)
            if order:
                # Track confirmed time
                order["confirmed_time"] = selected_time

                # Find which vendor this is from
                for vendor in order["vendors"]:
                    if vendor in order.get("vendor_messages", {}):
                        status_msg = f"■ {vendor} replied: Will prepare at {selected_time} ■"
                        await utils.safe_send_message(utils.DISPATCH_MAIN_CHAT_ID, status_msg)
                        break

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

            await utils.safe_send_message(
                utils.VENDOR_GROUP_MAP[vendor],
                "What's wrong?",
                InlineKeyboardMarkup(wrong_buttons)
            )

        elif action == "wrong_unavailable":
            order_id, vendor = data[1], data[2]
            order = utils.STATE.get(order_id)
            if order and order.get("order_type") == "shopify":
                msg = f"■ {vendor}: Please call the customer and organize a replacement. If no replacement is possible, write a message to dishbee. ■"
            else:
                msg = f"■ {vendor}: Please call the customer and organize a replacement or a refund. ■"
            await utils.safe_send_message(utils.DISPATCH_MAIN_CHAT_ID, msg)

        elif action == "wrong_canceled":
            order_id, vendor = data[1], data[2]
            await utils.safe_send_message(utils.DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: Order is canceled ■")

        elif action in ["wrong_technical", "wrong_other"]:
            order_id, vendor = data[1], data[2]
            await utils.safe_send_message(utils.DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: Write a message to dishbee and describe the issue ■")

        elif action == "wrong_delay":
            order_id, vendor = data[1], data[2]
            order = utils.STATE.get(order_id)
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

                await utils.safe_send_message(
                    utils.VENDOR_GROUP_MAP[vendor],
                    "Select delay time:",
                    InlineKeyboardMarkup(delay_buttons)
                )
            except:
                await utils.safe_send_message(utils.DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: We have a delay ■")

        elif action == "delay_time":
            order_id, vendor, delay_time = data[1], data[2], data[3]
            await utils.safe_send_message(utils.DISPATCH_MAIN_CHAT_ID, f"■ {vendor}: We have a delay - new time {delay_time} ■")

    except Exception as e:
        utils.logger.error(f"Callback processing error: {e}")

async def show_assignment_buttons(order_id: str):
    """Show assignment buttons in MDG when all vendors have confirmed"""
    try:
        order = utils.STATE.get(order_id)
        if not order or "mdg_message_id" not in order:
            return

        # Update MDG message to show assignment is ready
        base_text = mdg.build_mdg_dispatch_text(order)
        assignment_text = base_text + "\n\n🎯 **All vendors confirmed - Ready for assignment!**"

        # Show assignment buttons
        assignment_keyboard = upc.assignment_keyboard(order_id)
        if assignment_keyboard:
            await utils.safe_edit_message(
                utils.DISPATCH_MAIN_CHAT_ID,
                order["mdg_message_id"],
                assignment_text,
                assignment_keyboard
            )

        utils.logger.info(f"Assignment buttons shown for order {order_id}")

    except Exception as e:
        utils.logger.error(f"Error showing assignment buttons: {e}")

async def handle_assignment_callbacks(cq):
    """Handle assignment-related callbacks"""
    try:
        data = (cq.get("data") or "").split("|")
        if not data:
            return

        action = data[0]
        user_id = cq["from"]["id"]

        # Assignment actions
        if action in ["assign_me", "assign_user", "mark_delivered", "confirm_delivered",
                     "delay_order", "call_restaurant", "select_restaurant"]:
            await upc.handle_assignment_callback(action, data, user_id)

        # Delay minutes selection
        elif action == "delay_minutes":
            order_id, minutes = data[1], int(data[2])
            # Handle delay logic here
            await utils.safe_send_message(
                user_id,
                f"Delay of {minutes} minutes noted. Please coordinate with customer."
            )

        elif action == "delay_custom":
            order_id = data[1]
            await utils.safe_send_message(
                user_id,
                "Please specify the delay time and coordinate with the customer."
            )

    except Exception as e:
        utils.logger.error(f"Assignment callback error: {e}")

# --- SHOPIFY WEBHOOK ---
@app.route("/webhooks/shopify", methods=["POST"])
def shopify_webhook():
    """Handle Shopify webhooks"""
    try:
        raw = request.get_data()
        hmac_header = request.headers.get("X-Shopify-Hmac-Sha256")

        if not utils.verify_webhook(raw, hmac_header):
            return jsonify({"error": "Unauthorized"}), 401

        payload = json.loads(raw.decode('utf-8'))
        order_id = str(payload.get("id"))

        utils.logger.info(f"Processing Shopify order: {order_id}")

        # Extract order data
        order_name = payload.get("name", "Unknown")

        # Extract customer data with enhanced phone extraction
        customer = payload.get("customer") or {}
        customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or "Unknown"

        # Enhanced phone extraction from multiple sources
        phone = (
            customer.get("phone") or
            payload.get("phone") or
            payload.get("billing_address", {}).get("phone") or
            payload.get("shipping_address", {}).get("phone") or
            "N/A"
        )

        # Validate and format phone
        phone = utils.validate_phone(phone)
        if not phone:
            utils.logger.warning(f"Phone number missing or invalid for order {order_id}")
            phone = "N/A"

        address = mdg.fmt_address(payload.get("shipping_address") or {})

        # Store original address for clean Google Maps URL
        shipping_addr = payload.get("shipping_address", {})
        original_address = f"{shipping_addr.get('address1', '')}, {shipping_addr.get('zip', '')}".strip()
        if original_address == ", " or not original_address:
            original_address = address  # fallback to formatted address

        # Extract vendors from line items
        line_items = payload.get("line_items", [])
        vendors = []
        vendor_items = {}
        items_text = ""

        for item in line_items:
            vendor = item.get('vendor')
            if vendor and vendor in utils.VENDOR_GROUP_MAP:
                if vendor not in vendors:
                    vendors.append(vendor)
                    vendor_items[vendor] = []

                item_line = f"- {item.get('quantity', 1)} x {item.get('name', 'Item')}"
                vendor_items[vendor].append(item_line)

        # Build items text
        if len(vendors) > 1:
            # Multi-vendor: show vendor names above items
            items_by_vendor = ""
            for vendor in vendors:
                items_by_vendor += f"\n{vendor}:\n" + "\n".join(vendor_items[vendor]) + "\n"
            items_text = items_by_vendor.strip()
        else:
            # Single vendor: just list items
            all_items = []
            for vendor_item_list in vendor_items.values():
                all_items.extend(vendor_item_list)
            items_text = "\n".join(all_items)

        # Check for pickup orders
        is_pickup = False
        payload_str = str(payload).lower()
        if "abholung" in payload_str:
            is_pickup = True
            utils.logger.info("Pickup order detected (Abholung found in payload)")

        # Extract payment method and total from Shopify payload
        payment_method = "Paid"  # Default
        total_price = "0.00"     # Default

        # Check payment gateway names for CoD detection
        payment_gateways = payload.get("payment_gateway_names", [])
        if payment_gateways:
            gateway_str = " ".join(payment_gateways).lower()
            if "cash" in gateway_str and "delivery" in gateway_str:
                payment_method = "Cash on Delivery"

        # Check transactions for more detailed payment info
        transactions = payload.get("transactions", [])
        for transaction in transactions:
            gateway = transaction.get("gateway", "").lower()
            if "cash" in gateway and "delivery" in gateway:
                payment_method = "Cash on Delivery"
                break

        # Extract total price
        total_price_raw = payload.get("total_price", "0.00")
        try:
            # Format as currency with 2 decimal places
            total_price = f"{float(total_price_raw):.2f}€"
        except (ValueError, TypeError):
            total_price = "0.00€"

        utils.logger.info(f"Payment method: {payment_method}, Total: {total_price}")

        # Extract tips from Shopify payload
        tips = 0.0
        try:
            # Check for the actual tip field used by Shopify
            if payload.get("total_tip_received"):
                tips = float(payload["total_tip_received"])
            elif payload.get("total_tip"):
                tips = float(payload["total_tip"])
            elif payload.get("tip_money") and payload["tip_money"].get("amount"):
                tips = float(payload["tip_money"]["amount"])
            elif payload.get("total_tips_set") and payload["total_tips_set"].get("shop_money", {}).get("amount"):
                tips = float(payload["total_tips_set"]["shop_money"]["amount"])
        except (ValueError, TypeError, KeyError) as e:
            utils.logger.warning(f"Error extracting tips for order {order_id}: {e}")
            tips = 0.0

        # Build order object
        order = {
            "name": order_name,
            "order_type": "shopify",
            "vendors": vendors,
            "customer": {
                "name": customer_name,
                "phone": phone,
                "address": address,
                "original_address": original_address
            },
            "items_text": items_text,
            "vendor_items": vendor_items,
            "note": payload.get("note", ""),
            "tips": tips,
            "payment_method": payment_method,
            "total": total_price,
            "delivery_time": "ASAP",
            "is_pickup": is_pickup,
            "created_at": datetime.now(),
            "vendor_messages": {},
            "vendor_expanded": {},
            "requested_time": None,
            "confirmed_time": None,
            "status": "new",
            "mdg_additional_messages": []  # Track additional MDG messages for cleanup
        }

        # Save order to STATE first
        utils.STATE[order_id] = order

        utils.logger.info(f"Order {order_id} has vendors: {vendors} (count: {len(vendors)})")
        if len(vendors) > 1:
            utils.logger.info(f"MULTI-VENDOR detected: {vendors}")
        else:
            utils.logger.info(f"SINGLE VENDOR detected: {vendors}")

        utils.run_async(process_shopify_order(order_id))
        return jsonify({"status": "success"}), 200

    except Exception as e:
        utils.logger.error(f"Shopify webhook error: {e}")
        return jsonify({"error": "Internal server error"}), 500

async def process_shopify_order(order_id):
    """Process Shopify order asynchronously"""
    try:
        order = utils.STATE.get(order_id)
        if not order:
            return

        # Send to MDG with appropriate buttons
        mdg_text = mdg.build_mdg_dispatch_text(order)

        # Special formatting for pickup orders
        if order.get("is_pickup"):
            pickup_header = "**Order for Selbstabholung**\n"
            pickup_message = f"\nPlease call the customer and arrange the pickup time on this number: {order['customer']['phone']}"
            mdg_text = pickup_header + mdg_text + pickup_message

        mdg_msg = await utils.safe_send_message(
            utils.DISPATCH_MAIN_CHAT_ID,
            mdg_text,
            mdg.mdg_time_request_keyboard(order_id)
        )
        order["mdg_message_id"] = mdg_msg.message_id

        # Send to each vendor group (summary by default)
        for vendor in order["vendors"]:
            vendor_chat = utils.VENDOR_GROUP_MAP.get(vendor)
            if vendor_chat:
                vendor_text = mdg.build_vendor_summary_text(order, vendor)
                # Order message has only expand/collapse button
                vendor_msg = await utils.safe_send_message(
                    vendor_chat,
                    vendor_text,
                    mdg.vendor_keyboard(order_id, vendor, False)
                )
                order["vendor_messages"][vendor] = vendor_msg.message_id
                order["vendor_expanded"][vendor] = False

        # Update STATE with message IDs
        utils.STATE[order_id] = order

        # Keep only recent orders
        utils.RECENT_ORDERS.append({
            "order_id": order_id,
            "created_at": datetime.now(),
            "vendors": order["vendors"]
        })

        if len(utils.RECENT_ORDERS) > 50:
            utils.RECENT_ORDERS.pop(0)

        utils.logger.info(f"Order {order_id} processed successfully")

    except Exception as e:
        utils.logger.error(f"Error processing order: {e}")
        raise

def run_async(coro):
    """Run async function in background thread"""
    asyncio.run_coroutine_threadsafe(coro, utils.loop)

def validate_phone(phone: str) -> Optional[str]:
    """Validate and format phone number for tel: links"""
    if not phone or phone == "N/A":
        return None
    
    # Remove non-numeric characters except + and spaces
    import re
    cleaned = re.sub(r'[^\d+\s]', '', phone).strip()
    
    # Basic validation: must have at least 7 digits
    digits_only = re.sub(r'\D', '', cleaned)
    if len(digits_only) < 7:
        return None
    
    return cleaned

# --- APPLICATION ENTRY POINT ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Starting Complete Assignment Implementation on port {port}")
    
    # Start the event loop in a separate thread
    def run_event_loop():
        asyncio.set_event_loop(loop)
        loop.run_forever()
    
    loop_thread = threading.Thread(target=run_event_loop)
    loop_thread.daemon = True
    loop_thread.start()
    
    app.run(host="0.0.0.0", port=port, debug=False)
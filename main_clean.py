# Telegram Dispatch Bot — Complete Assignment Implementation
# All features from requirements document implemented

# MAIN WORKFLOW OVERVIEW
# Order placed → arrives in MDG and RG → user requests time from restaurants
# → restaurants confirm time → user receives info in MDG → assigns to himself
# or another user (private chat with BOT) → order delivered → user confirms
# delivery → order state changed to delivered
#
# CODE ORGANIZATION:
# 1. MDG - Main Dispatching Group: Order arrival, time requests, status updates
# 2. RG - Restaurant Groups: Vendor communications, response handling
# 3. UPC - User Private Chats: Assignment logic, DMs, completion workflows

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
from telegram.request import HTTPXRequest
from telegram.error import TelegramError, TimedOut, NetworkError

# Import organized modules
import utils
import mdg
import rg
import upc

# Use imported configurations
BOT_TOKEN = utils.BOT_TOKEN
WEBHOOK_SECRET = utils.WEBHOOK_SECRET
DISPATCH_MAIN_CHAT_ID = utils.DISPATCH_MAIN_CHAT_ID
VENDOR_GROUP_MAP = utils.VENDOR_GROUP_MAP
DRIVERS = utils.DRIVERS
COURIER_MAP = utils.COURIER_MAP
RESTAURANT_SHORTCUTS = utils.RESTAURANT_SHORTCUTS

# Use imported state and utilities
STATE = utils.STATE
RECENT_ORDERS = utils.RECENT_ORDERS
bot = utils.bot
run_async = utils.run_async
logger = utils.logger
validate_phone = utils.validate_phone
verify_webhook = utils.verify_webhook
loop = utils.loop

# Import functions from modules
build_mdg_dispatch_text = mdg.build_mdg_dispatch_text
mdg_time_request_keyboard = mdg.mdg_time_request_keyboard
build_vendor_summary_text = rg.build_vendor_summary_text
vendor_keyboard = rg.vendor_keyboard
safe_send_message = utils.safe_send_message
fmt_address = utils.fmt_address
get_last_confirmed_order = utils.get_last_confirmed_order

# --- FLASK APP SETUP ---
app = Flask(__name__)

# → Admins click buttons to request timing from restaurants → Status updates posted here
# → After restaurant confirmation, assignment buttons appear for delivery coordination

# --- WEBHOOK ENDPOINTS ---
@app.route("/", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        "status": "healthy",
        "service": "telegram-dispatch-bot",
        "orders_in_state": len(STATE),
        "timestamp": datetime.now().isoformat()
    }), 200

# --- TELEGRAM WEBHOOK ---
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    """Handle Telegram webhooks"""
    try:
        upd = request.get_json(force=True)
        if not upd:
            return "OK"

        # Log all incoming updates for spam detection
        logger.info(f"=== INCOMING UPDATE ===")
        logger.info(f"Update ID: {upd.get('update_id')}")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")

        # Check for regular messages (potential spam source)
        if "message" in upd:
            msg = upd["message"]
            from_user = msg.get("from", {})
            chat = msg.get("chat", {})
            text = msg.get("text", "")

            logger.info(f"MESSAGE RECEIVED:")
            logger.info(f"  Chat ID: {chat.get('id')}")
            logger.info(f"  Chat Type: {chat.get('type')}")
            logger.info(f"  Chat Title: {chat.get('title', 'N/A')}")
            logger.info(f"  From User ID: {from_user.get('id')}")

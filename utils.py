# utils.py - Shared utilities, constants, and helpers for Telegram Dispatch Bot

import os
import json
import hmac
import hashlib
import base64
import asyncio
import logging
import threading
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- ENVIRONMENT VARIABLES ---
BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_SECRET = os.environ["SHOPIFY_WEBHOOK_SECRET"]
DISPATCH_MAIN_CHAT_ID = int(os.environ["DISPATCH_MAIN_CHAT_ID"])
VENDOR_GROUP_MAP: Dict[str, int] = json.loads(os.environ.get("VENDOR_GROUP_MAP", "{}"))
DRIVERS: Dict[str, int] = json.loads(os.environ.get("DRIVERS", "{}"))
COURIER_MAP: Dict[str, int] = json.loads(os.environ.get("COURIER_MAP", "{}"))  # Use COURIER_MAP instead of DRIVERS

# --- CONSTANTS AND MAPPINGS ---
RESTAURANT_SHORTCUTS = {
    "Julis Spätzlerei": "JS",
    "Zweite Heimat": "ZH",
    "Kahaani": "KA",
    "i Sapori della Toscana": "SA",
    "Leckerolls": "LR",
    "dean & david": "DD",
    "Pommes Freunde": "PF",
    "Wittelsbacher Apotheke": "AP"
}

# --- TELEGRAM BOT CONFIGURATION ---
request_cfg = HTTPXRequest(
    connection_pool_size=32,
    pool_timeout=30.0,
    read_timeout=30.0,
    write_timeout=30.0,
    connect_timeout=15.0,
)
bot = Bot(token=BOT_TOKEN, request=request_cfg)

# --- GLOBAL STATE ---
STATE: Dict[str, Dict[str, Any]] = {}
RECENT_ORDERS: List[Dict[str, Any]] = []

# Create event loop for async operations
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def run_async(coro):
    """Run async function in background thread"""
    asyncio.run_coroutine_threadsafe(coro, loop)

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

def clean_product_name(name: str) -> str:
    """
    Clean up product names according to project-specific display rules.
    
    This function simplifies product names by removing unnecessary prefixes,
    suffixes, and formatting to make them more readable in order messages.
    Applied consistently across MDG, RG, and UPC displays.
    
    Handles compound products (e.g., "Burger - Pommes") by splitting on " - "
    and cleaning each part separately. Removes duplicates (e.g., "Prosciutto - Prosciutto" → "Prosciutto").
    
    Rules implemented (17 total):
    - Extract burger names from quotes, remove "Bio-Burger" prefix
    - Simplify fries/pommes variations (Bio-Pommes → Pommes)
    - Remove pizza prefixes (Sauerteig-Pizza → keep only name)
    - Simplify Spätzle dishes (remove "& Spätzle" suffix)
    - Remove pasta prefixes (Selbstgemachte → keep only type)
    - Simplify rolls (remove roll type prefix)
    - Remove prices in brackets: (+2.6€), (1.9€)
    - Remove "/ Standard" suffixes
    - Remove Bio- prefixes from salads
    
    Args:
        name: Raw product name from Shopify line_items
    
    Returns:
        Cleaned product name for display
        
    Example:
        >>> clean_product_name('[Bio-Burger "Classic"]')
        'Classic'
        >>> clean_product_name('Veganer-Monats-Bio-Burger „BBQ Oyster" - Bio-Pommes')
        'BBQ Oyster - Pommes'
        >>> clean_product_name('Sauerteig-Pizza Prosciutto - Prosciutto')
        'Prosciutto'
    """
    import re
    
    if not name or not name.strip():
        return name
    
    # Debug logging
    logger.debug(f"clean_product_name input: '{name}'")
    
    # Rule 0: Remove " - Classic" suffix FIRST (before compound splitting)
    if ' - Classic' in name:
        name = re.sub(r'\s*-\s*Classic$', '', name)
        logger.debug(f"Rule 0 (Classic removal): removed ' - Classic' suffix → '{name}'")
    
    # Handle compound products: "Burger - Side" - split and clean each part
    if ' - ' in name:
        parts = name.split(' - ')
        logger.debug(f"Splitting compound product into parts: {parts}")
        cleaned_parts = []
        for part in parts:
            part = part.strip()
            
            # Skip empty parts or "Classic" (already removed above)
            if not part or part == 'Classic':
                continue
            
            # Handle "+ X" pattern: "Bergkäse-Spätzle - + Gebratener Speck" → ["Bergkäse-Spätzle", "+ Gebratener Speck"]
            # Keep the + prefix for additions
            if part.startswith('+ '):
                # Clean the part after "+", then re-add "+"
                cleaned = clean_product_name(part[2:].strip())  # Recursive call
                if cleaned:
                    cleaned_parts.append(f"+ {cleaned}")
                logger.debug(f"Cleaned addition '{part}' → '+ {cleaned}'")
            else:
                cleaned = clean_product_name(part)  # Recursive call
                logger.debug(f"Cleaned '{part}' → '{cleaned}'")
                if cleaned and cleaned.strip():
                    cleaned_parts.append(cleaned)
        
        # Remove duplicates: "Prosciutto - Prosciutto" -> "Prosciutto"
        if len(cleaned_parts) == 2 and cleaned_parts[0] == cleaned_parts[1]:
            result = cleaned_parts[0]
            logger.debug(f"Removed duplicate: {cleaned_parts} → '{result}'")
            return result
        
        # If we have additions (+ X), join with space instead of " - "
        if len(cleaned_parts) > 1 and any(p.startswith('+ ') for p in cleaned_parts):
            result = ' '.join(cleaned_parts)
            logger.debug(f"Compound product with additions: '{result}'")
            return result
        
        result = ' - '.join(cleaned_parts) if cleaned_parts else name
        logger.debug(f"Compound product result: '{result}'")
        return result
    
    # Remove brackets from product names
    name = name.strip('[]')
    
    # Rule 1: Remove prices in brackets (do early, affects multiple rules)
    name = re.sub(r'\s*\(\+?[\d.]+€\)', '', name)
    
    # Rule 2: Burger names - extract text between quotes (ANY burger type)
    # Handles: [Bio-Burger "X"], [Monats-Bio-Burger „X"], [Veganer-Monats-Bio-Burger „X"]
    if 'Burger' in name:
        match = re.search(r'[„"]([^"„]+)[„"]', name)
        if match:
            return match.group(1)
    
    # Rule 3: Remove "Bio-" prefix from any product
    if name.startswith('Bio-'):
        name = name.replace('Bio-', '', 1)
        logger.debug(f"Rule 3 (Bio removal): removed 'Bio-' prefix → '{name}'")
    
    # Rule 4: Chili-Cheese-Fries -> Fries: Chili-Cheese-Style
    if 'Chili-Cheese-Fries' in name:
        return 'Fries: Chili-Cheese-Style'
    
    # Rule 5: Chili-Cheese-Süßkartoffelpommes -> Süßkartoffel: Chili-Cheese-Style
    if 'Chili-Cheese-Süßkartoffelpommes' in name:
        return 'Süßkartoffel: Chili-Cheese-Style'
    
    # Rule 6: Sloppy-Fries (keep as is after price removal)
    if name.startswith('Sloppy-Fries'):
        return 'Sloppy-Fries'
    
    # Rule 7: Remove "Sauerteig-Pizza " prefix from any pizza
    if name.startswith('Sauerteig-Pizza '):
        name = name.replace('Sauerteig-Pizza ', '', 1)
        logger.debug(f"Rule 7 (Pizza prefix removal): removed 'Sauerteig-Pizza' → '{name}'")
    
    # Rule 8: Remove "-Spätzle" from any product (general spätzle removal)
    # Handle various spellings: Spätzle, Spaetzle, with or without space before hyphen
    if 'Spätzle' in name or 'Spaetzle' in name or 'spätzle' in name or 'spaetzle' in name:
        result = re.sub(r'\s*-\s*[Ss][pä][aeä]tzle', '', name, flags=re.IGNORECASE)
        logger.debug(f"Rule 8 (Spätzle removal): '{name}' → '{result}'")
        name = result
    
    # Rule 9: General spätzle cleanup: "X & Spätzle" -> "X", "X Spätzle" -> "X"
    name = re.sub(r'\s*&\s*[Ss][pä][aeä]tzle', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+[Ss][pä][aeä]tzle$', '', name, flags=re.IGNORECASE)
    
    # Rule 10: Remove "Selbstgemachte " prefix from any pasta
    if name.startswith('Selbstgemachte '):
        name = name.replace('Selbstgemachte ', '', 1)
        logger.debug(f"Rule 10 (Selbstgemachte removal): removed prefix → '{name}'")
    
    # Rule 11: Remove ANY roll type prefix: "Special roll - X" -> "X", "Cinnamon roll - X" -> "X"
    roll_pattern = r'^(Special roll|Cinnamon roll|[A-Za-z]+ roll)\s*-\s*'
    if re.search(roll_pattern, name):
        name = re.sub(roll_pattern, '', name)
        logger.debug(f"Rule 11 (Roll prefix removal): removed roll prefix → '{name}'")
    
    # Rule 12: Remove "/ Standard" suffix from any product
    name = re.sub(r'\s*/\s*Standard\s*$', '', name)
    
    return name.strip()

def verify_webhook(raw: bytes, hmac_header: str) -> bool:
    """Verify Shopify webhook HMAC"""
    try:
        if not hmac_header:
            return False
        computed = hmac.new(WEBHOOK_SECRET.encode("utf-8"), raw, hashlib.sha256).digest()
        expected = base64.b64encode(computed).decode("utf-8")
        return hmac.compare_digest(expected, hmac_header)
    except Exception as e:
        logger.error(f"HMAC verification error: {e}")
        return False

# --- ASYNC UTILITY FUNCTIONS ---
async def safe_send_message(chat_id: int, text: str, reply_markup=None, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True):
    """Send message with error handling and retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Send message attempt {attempt + 1}")
            return await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview
            )
        except Exception as e:
            logger.error(f"Send message attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            else:
                logger.error(f"Failed to send message after {max_retries} attempts: {e}")
                raise

async def safe_edit_message(chat_id: int, message_id: int, text: str, reply_markup=None, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True):
    """Edit message with error handling"""
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview
        )
    except Exception as e:
        logger.error(f"Error editing message: {e}")

async def safe_delete_message(chat_id: int, message_id: int):
    """Delete message with error handling"""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"Successfully deleted message {message_id}")
    except Exception as e:
        logger.error(f"Error deleting message {message_id}: {e}")

async def cleanup_mdg_messages(order_id: str):
    """
    Clean up temporary MDG messages to prevent chat clutter.
    
    During order workflow, temporary messages are sent to MDG:
    - Time picker keyboards ("+5 +10 +15 +20" buttons)
    - "Same time as" order selection menus
    - Exact time picker (hour/minute selection)
    - Vendor selection menus (multi-vendor orders)
    - Courier selection menus ("Assign to..." flow)
    
    These messages are tracked in order["mdg_additional_messages"] and
    deleted when the workflow step completes to keep MDG chat clean.
    
    The original order message (order["mdg_message_id"]) is NEVER deleted
    and remains as permanent record with assignment buttons.
    
    Args:
        order_id: Order to clean up messages for
        
    Side effects:
        - Deletes all messages in order["mdg_additional_messages"]
        - Clears the mdg_additional_messages list after deletion
        - Logs each deletion attempt (success or failure)
    
    Note: Uses retry logic (3 attempts) for each deletion to handle
    network issues or rate limits.
    """
    order = STATE.get(order_id)
    if not order:
        return

    additional_messages = order.get("mdg_additional_messages", [])
    if not additional_messages:
        return

    logger.info(f"Cleaning up {len(additional_messages)} additional MDG messages for order {order_id}")

    for message_id in additional_messages:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await bot.delete_message(chat_id=DISPATCH_MAIN_CHAT_ID, message_id=message_id)
                logger.info(f"Successfully deleted MDG message {message_id} for order {order_id}")
                break
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed to delete message {message_id}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                else:
                    logger.error(f"Failed to delete message {message_id} after {max_retries} attempts")

    # Clear the list after cleanup
    order["mdg_additional_messages"] = []
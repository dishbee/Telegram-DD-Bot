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

# District mapping for Passau addresses
DISTRICT_MAPPING = {
    "Innstadt": [
        "Lederergasse", "Innstraße", "Angerstraße", "Spitalhofstraße", 
        "Theresienstraße", "Nikolastraße", "Severinstraße", "Innbruckstraße"
    ],
    "Altstadt": [
        "Bräugasse", "Residenzplatz", "Domplatz", "Ludwigsplatz", "Schrottgasse",
        "Heiliggeistgasse", "Rindermarkt", "Kleine Messergasse", "Steinweg", 
        "Große Messergasse", "Wittgasse", "Nibelungenplatz"
    ],
    "Hacklberg": [
        "Ilzleite", "Hacklberg", "Dr.-Hans-Kapfinger-Straße", "Passauer Straße"
    ],
    "Grubweg": [
        "Grubweg", "Neuburger Straße", "Vilshofener Straße"
    ],
    "Hals": [
        "Regensburger Straße", "Halser Straße", "Breslauer Straße"
    ]
}

def get_district_from_address(address: str) -> Optional[str]:
    """
    Determine district from street address.
    
    Args:
        address: Full address string (e.g., "Lederergasse 15, Passau 94032")
    
    Returns:
        District name (e.g., "Innstadt") or None if not found
    """
    if not address:
        logger.info("get_district_from_address: Empty address provided")
        return None
    
    # Extract street name (first part before house number)
    address_lower = address.lower()
    logger.info(f"get_district_from_address: Checking address '{address}' (lowercase: '{address_lower}')")
    
    for district, streets in DISTRICT_MAPPING.items():
        for street in streets:
            if street.lower() in address_lower:
                logger.info(f"get_district_from_address: MATCH found! Street '{street}' matches district '{district}'")
                return district
    
    logger.info(f"get_district_from_address: No district match found for '{address}'")
    return None

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
    and cleaning each part separately. Removes duplicates (e.g., "Prosciutto - Prosciutto Funghi" → "Prosciutto Funghi").
    
    Rules implemented (25+ total):
    - Extract burger names from quotes, remove "Bio-Burger" prefix
    - Simplify fries/pommes variations (Bio-Pommes → Pommes, Süßkartoffel-Pommes → Süßkartoffel)
    - Remove pizza prefixes (Sauerteig-Pizza → keep only name)
    - Simplify Spätzle dishes (remove "& Spätzle" and "- Standard" suffixes)
    - Remove pasta prefixes (Selbstgemachte → keep only type)
    - Simplify rolls (remove ALL roll type prefixes: Special, Cinnamon, etc.)
    - Remove prices in brackets: (+2.6€), (1.9€), (13,50€) - handles both . and , decimals
    - Remove "/ Standard", "/ Classic", "/ Glutenfrei" patterns
    - Remove Bio- prefixes from salads
    - Special handling for "Gemüse Curry & Spätzle" → "Curry"
    - Duplicate word removal: "Prosciutto - Prosciutto Funghi" → "Prosciutto Funghi"
    - "Halb Pommes / Halb Salat" → "Halb P. / Halb S."
    
    Args:
        name: Raw product name from Shopify line_items
    
    Returns:
        Cleaned product name for display
        
    Example:
        >>> clean_product_name('[Bio-Burger "Classic"]')
        'Classic'
        >>> clean_product_name('Veganer-Monats-Bio-Burger „BBQ Oyster" - Bio-Pommes')
        'BBQ Oyster - Pommes'
        >>> clean_product_name('Special roll - Salted Caramel Apfel')
        'Salted Caramel Apfel'
        >>> clean_product_name('Spaghetti - Cacio e Pepe (13,50€)')
        'Spaghetti - Cacio e Pepe'
        >>> clean_product_name('Prosciutto - Prosciutto Funghi')
        'Prosciutto Funghi'
    """
    import re
    
    if not name or not name.strip():
        return name
    
    # Store original for logging
    original_input = name
    
    # Rule 0a: Special case for Curry dishes - must be BEFORE compound splitting
    # BUT: Don't apply if it's part of a Burger compound
    if 'Curry' in name and 'Spätzle' in name and 'Burger' not in name:
        return 'Curry'
    
    # Rule 0b: Special case for Gulasch dishes - must be BEFORE compound splitting
    # BUT: Don't apply if it's part of a Burger compound
    if 'Gulasch' in name and 'Spätzle' in name and 'Burger' not in name:
        return 'Gulasch'
    
    # Rule 0c: Special case for "Halb Pommes / Halb Salat" → "Halb P. / Halb S."
    # BUT: Don't apply if it's part of a Burger compound (e.g., Bio-Burger "BBQ" Halb Pommes / Halb Salat)
    if 'Halb Pommes' in name and 'Halb Salat' in name and 'Burger' not in name:
        return 'Halb P. / Halb S.'
    
    # Rule 1: Remove " - Classic" suffix FIRST (before compound splitting)
    if ' - Classic' in name:
        name = re.sub(r'\s*-\s*Classic$', '', name)
    
    # Rule 1b: Remove " / Classic" suffix
    if ' / Classic' in name:
        name = re.sub(r'\s*/\s*Classic$', '', name)
    
    # Rule 1c: Remove " / Glutenfrei" suffix but keep " - Glutenfrei"
    name = re.sub(r'\s*-\s*Classic\s*/\s*Glutenfrei$', ' - Glutenfrei', name)
    
    # Handle compound products: "Burger - Side" - split and clean each part
    if ' - ' in name:
        parts = name.split(' - ')
        cleaned_parts = []
        for part in parts:
            part = part.strip()
            
            # Skip empty parts, "Classic", "Standard", or "Vegetarisch" suffixes
            if not part or part in ['Classic', 'Standard', 'Vegetarisch']:
                continue
            
            # Handle "+ X" pattern: "Bergkäse-Spätzle - + Gebratener Speck" → ["Bergkäse-Spätzle", "+ Gebratener Speck"]
            # Keep the + prefix for additions
            if part.startswith('+ '):
                # Clean the part after "+", then re-add "+"
                cleaned = clean_product_name(part[2:].strip())  # Recursive call
                if cleaned:
                    cleaned_parts.append(f"+ {cleaned}")
            else:
                cleaned = clean_product_name(part)  # Recursive call
                if cleaned and cleaned.strip():
                    cleaned_parts.append(cleaned)
        
        # Remove duplicate first words: "Prosciutto - Prosciutto Funghi" -> "Prosciutto Funghi"
        # Also handles "Burrata - Burrata Crudo" -> "Burrata Crudo"
        if len(cleaned_parts) == 2:
            first_word_part1 = cleaned_parts[0].split()[0] if cleaned_parts[0].split() else ""
            first_word_part2 = cleaned_parts[1].split()[0] if cleaned_parts[1].split() else ""
            
            if first_word_part1 == first_word_part2:
                # Second part starts with same word as first part
                result = cleaned_parts[1]
                return result
        
        # If we have additions (+ X), join with space instead of " - "
        if len(cleaned_parts) > 1 and any(p.startswith('+ ') for p in cleaned_parts):
            result = ' '.join(cleaned_parts)
            return result
        
        result = ' - '.join(cleaned_parts) if cleaned_parts else name
        return result
    
    # Remove brackets from product names
    name = name.strip('[]')
    
    # Rule 2: Remove prices in brackets - handles both . and , as decimal separator
    # Matches: (+2.6€), (1.9€), (13,50€), (+0,90€), etc.
    name = re.sub(r'\s*\(\+?[\d.,]+€\)', '', name)
    
    # Rule 3: Burger names - extract text between quotes (ANY burger type)
    # Handles: [Bio-Burger "X"], [Monats-Bio-Burger „X"], [Veganer-Monats-Bio-Burger „X"]
    # Supports all quote types: „" "" "" and straight "
    # BUT: Must preserve compound structure after extraction
    if 'Burger' in name and (' - ' in name):
        # Example: "Veganer-Monats-Bio-Burger „BBQ Oyster" - Pommes"
        # Split first, extract burger quote from first part
        parts = name.split(' - ', 1)  # Split only on first " - "
        burger_part = parts[0]
        other_parts = parts[1] if len(parts) > 1 else ""
        
        # Try to extract quoted burger name
        match = re.search(r'[„""""]([^„""""]+)[„""""]', burger_part)
        if match:
            burger_name = match.group(1)
            if other_parts:
                # Recursively clean the other parts
                logger.info(f"DEBUG Rule 3: Burger='{burger_name}' | Cleaning side: '{other_parts}'")
                cleaned_other = clean_product_name(other_parts)
                logger.info(f"DEBUG Rule 3: Side cleaned to: '{cleaned_other}'")
                result = f"{burger_name} - {cleaned_other}"
                return result
            else:
                return burger_name
    elif 'Burger' in name:
        # No " - " separator, but might have side dish after burger name
        # Example: Bio-Burger "BBQ" Halb Pommes / Halb Salat
        match = re.search(r'[„""""]([^„""""]+)[„""""]', name)
        if match:
            burger_name = match.group(1)
            # Check if there's text after the closing quote
            quote_end_pos = match.end()
            remaining_text = name[quote_end_pos:].strip()
            
            if remaining_text:
                # There's a side dish after the burger name
                logger.info(f"DEBUG Rule 3 (no separator): Burger='{burger_name}' | Side: '{remaining_text}'")
                cleaned_side = clean_product_name(remaining_text)
                logger.info(f"DEBUG Rule 3 (no separator): Side cleaned to: '{cleaned_side}'")
                result = f"{burger_name} - {cleaned_side}"
                return result
            else:
                # Just the burger name
                return burger_name
    
    # Rule 4: Remove ANY roll type prefix BEFORE other processing
    # Matches: "Special roll - X", "Cinnamon roll - X", "Lotus roll X", etc.
    # Handles both "roll - Product" and "roll Product" formats
    # Also handles standalone "Special roll" case (return empty to filter out)
    roll_pattern = r'^([A-Za-zäöüÄÖÜß]+\s+roll)[\s\-]+(.+)$'
    roll_match = re.match(roll_pattern, name, re.IGNORECASE)
    if roll_match:
        name = roll_match.group(2).strip()
    else:
        # Check if name IS just "{Type} roll" with nothing after
        standalone_roll_pattern = r'^([A-Za-zäöüÄÖÜß]+\s+roll)$'
        if re.match(standalone_roll_pattern, name, re.IGNORECASE):
            # Return empty string to filter this part out in compound handler
            return ""
    
    # Rule 5: Remove "Bio-" prefix from any product
    if name.startswith('Bio-'):
        name = name.replace('Bio-', '', 1)
    
    # Rule 6: Remove "B-" prefix (e.g., "B-umpkin")
    if name.startswith('B-'):
        name = name.replace('B-', '', 1)
    
    # Rule 7: Chili-Cheese-Fries -> Fries: Chili-Cheese-Style
    if 'Chili-Cheese-Fries' in name:
        return 'Fries: Chili-Cheese-Style'
    
    # Rule 8: Chili-Cheese-Süßkartoffel -> Süßkart.: Chili-Cheese-Style
    if 'Chili-Cheese-Süßkartoffel' in name:
        return 'Süßkart.: Chili-Cheese-Style'
    
    # Rule 9: Sloppy-Fries (keep as is after price removal)
    if name.startswith('Sloppy-Fries'):
        logger.info(f"Rule 9 (Sloppy-Fries): MATCHED - returning 'Sloppy-Fries'")
        return 'Sloppy-Fries'
    
    # Rule 10: Süßkartoffel-Pommes → Süßkartoffel
    if 'Süßkartoffel-Pommes' in name or 'Süßkartoffelpommes' in name:
        name = re.sub(r'Süßkartoffel(-)?[Pp]ommes', 'Süßkartoffel', name)
    
    # Rule 11: Remove "Sauerteig-Pizza " prefix from any pizza
    if name.startswith('Sauerteig-Pizza '):
        name = name.replace('Sauerteig-Pizza ', '', 1)
    
    # Rule 12: Remove " Spätzle" suffix (with space) - catches "Erdnuss Pesto Spätzle"
    if name.endswith(' Spätzle'):
        name = name[:-8]  # Remove last 8 characters: " Spätzle"
    
    # Rule 13: Remove "-Spätzle" from any product (general spätzle removal with hyphen)
    # Handle various spellings: Spätzle, Spaetzle, with or without space before hyphen
    if 'Spätzle' in name or 'Spaetzle' in name or 'spätzle' in name or 'spaetzle' in name:
        result = re.sub(r'\s*-\s*[Ss][pä][aeä]tzle', '', name, flags=re.IGNORECASE)
        name = result
    
    # Rule 14: General spätzle cleanup: "X & Spätzle" -> "X"
    name = re.sub(r'\s*&\s*[Ss][pä][aeä]tzle', '', name, flags=re.IGNORECASE)
    
    # Rule 15: Remove "Selbstgemachte " prefix from any pasta
    if name.startswith('Selbstgemachte '):
        name = name.replace('Selbstgemachte ', '', 1)
    
    # Rule 16: Remove "/ Standard" suffix from any product
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

async def send_status_message(chat_id: int, text: str, auto_delete_after: int = 20):
    """
    Send a status message that auto-deletes after specified seconds.
    
    Used for temporary status updates like:
    - Vendor confirmations: "Vendor replied: Will prepare #90 at 14:57 👍"
    - ASAP/TIME requests sent: "✅ ASAP request sent to Vendor"
    - Delays: "Vendor: We have a delay for #90 - new time 15:00"
    
    Args:
        chat_id: Chat to send message to
        text: Message text
        auto_delete_after: Seconds to wait before deletion (default: 20)
    """
    try:
        msg = await safe_send_message(chat_id, text)
        # Schedule deletion
        await asyncio.sleep(auto_delete_after)
        await safe_delete_message(chat_id, msg.message_id)
    except Exception as e:
        logger.error(f"Error in send_status_message: {e}")

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
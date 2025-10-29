# -*- coding: utf-8 -*-
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

# Google Maps API key for district detection (optional)
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

# District cache to minimize API calls
_DISTRICT_CACHE: Dict[str, Optional[str]] = {}

def get_district_from_address(address: str) -> Optional[str]:
    """
    Determine district/neighborhood from address using Google Maps Geocoding API.
    
    Caches results to minimize API calls. Returns None if API key not configured.
    
    Args:
        address: Full address string (e.g., "Lederergasse 15, Passau 94032")
    
    Returns:
        District name (e.g., "Innstadt") or None if not found/unavailable
    """
    if not address:
        return None
    
    # Check cache first
    if address in _DISTRICT_CACHE:
        logger.info(f"District cache hit for '{address}': {_DISTRICT_CACHE[address]}")
        return _DISTRICT_CACHE[address]
    
    # If no API key configured, return None
    if not GOOGLE_MAPS_API_KEY:
        logger.info("GOOGLE_MAPS_API_KEY not set - district detection disabled")
        _DISTRICT_CACHE[address] = None
        return None
    
    try:
        # Query Google Maps Geocoding API
        logger.info(f"Querying Google Maps for district: '{address}'")
        
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": f"{address}, Passau, Germany",
            "key": GOOGLE_MAPS_API_KEY,
            "language": "de"
        }
        
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") != "OK":
            logger.warning(f"Google Maps API error: {data.get('status')}")
            _DISTRICT_CACHE[address] = None
            return None
        
        # Extract district from address components
        results = data.get("results", [])
        if not results:
            logger.warning(f"No results from Google Maps for: {address}")
            _DISTRICT_CACHE[address] = None
            return None
        
        # Look for sublocality/neighborhood in components
        address_components = results[0].get("address_components", [])
        district = None
        
        # Log all components for debugging
        logger.info(f"Google Maps returned {len(address_components)} components:")
        for comp in address_components:
            logger.info(f"  - {comp.get('long_name')} | Types: {comp.get('types')}")
        
        for component in address_components:
            types = component.get("types", [])
            # Check for sublocality/neighborhood types (most specific districts)
            if any(t in types for t in ["sublocality", "sublocality_level_1", "sublocality_level_2", "neighborhood"]):
                name = component.get("long_name")
                if name:
                    district = name
                    logger.info(f"District found: '{district}' for address '{address}'")
                    break
        
        if not district:
            logger.info(f"No district/sublocality found for: {address}")
        
        _DISTRICT_CACHE[address] = district
        return district
        
    except Exception as e:
        logger.error(f"Error calling Google Maps API: {e}")
        _DISTRICT_CACHE[address] = None
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

def abbreviate_street(street_name: str, max_length: int = 20) -> str:
    """
    Abbreviate German street names for display in buttons (BTN-ORD-REF only).
    
    Keeps button text under character limit while preserving essential info.
    Used ONLY for recent order buttons where space is limited.
    
    Two-tier abbreviation system:
    
    Tier 1 (Standard): Apply common abbreviations
    - Straße→Str., Gasse→Ga., Weg→W., Platz→Pl., Allee→Al.
    - Doktor→Dr., Professor→Prof., Sankt→St.
    - Compound names: Remove hyphens, truncate middle parts to 4 letters, no dots
      Example: "Dr.-Stephan-Billinger-Straße" → "Dr.Step.Bill.Str."
    
    Tier 2 (Aggressive - if button exceeds 30 chars): 
    - Take only first 4 letters of street name (no suffix abbreviation)
    - Example: "Lederergasse 15" → "Lede 15"
    - Example: "Dr.-Stephan-Billinger-Straße 5" → "DrSt 5"
    
    Args:
        street_name: Full street name (may include house number)
        max_length: Target maximum length for Tier 1 (default: 20)
    
    Returns:
        Abbreviated street name
        
    Examples:
        >>> abbreviate_street("Innstraße 15")
        'Innstr. 15'
        >>> abbreviate_street("Lederergasse 8")
        'Ledererga. 8'
        >>> abbreviate_street("Dr.-Stephan-Billinger-Straße 42")
        'Dr.Step.Bill.Str. 42'
    """
    import re
    
    if not street_name:
        return street_name
    
    original_full = street_name
    
    # Extract house number if present (preserve it)
    house_number = ""
    match = re.search(r'\s+(\d+[a-zA-Z]?)$', street_name)
    if match:
        house_number = f" {match.group(1)}"
        street_name = street_name[:match.start()]
    
    # TIER 1: Standard abbreviation
    
    # Step 1: Replace common title prefixes
    replacements = [
        (r'\bDoktor-', 'Dr.'),
        (r'\bProfessor-', 'Prof.'),
        (r'\bSankt-', 'St.'),
    ]
    
    for pattern, replacement in replacements:
        street_name = re.sub(pattern, replacement, street_name)
    
    # Step 2: Replace common street suffixes
    suffix_replacements = [
        ('straße', 'str.'),
        ('Straße', 'Str.'),
        ('gasse', 'ga.'),
        ('Gasse', 'Ga.'),
        ('weg', 'w.'),
        ('Weg', 'W.'),
        ('platz', 'pl.'),
        ('Platz', 'Pl.'),
        ('allee', 'al.'),
        ('Allee', 'Al.'),
    ]
    
    for full, abbr in suffix_replacements:
        if street_name.endswith(full):
            street_name = street_name[:-len(full)] + abbr
            break
    
    # Check if we're under limit after basic replacements
    result = street_name + house_number
    if len(result) <= max_length:
        return result
    
    # Step 3: Smart truncation for compound names (hyphenated parts)
    # Example: "Dr.-Stephan-Billinger-Str." → "Dr.Step.Bill.Str." (NO hyphens, NO dots after parts)
    if '-' in street_name:
        parts = street_name.split('-')
        truncated_parts = []
        
        for i, part in enumerate(parts):
            # Keep first part (usually title like "Dr.") as-is
            if i == 0:
                truncated_parts.append(part)
            # Keep last part (suffix like "Str.") as-is
            elif i == len(parts) - 1:
                truncated_parts.append(part)
            # Truncate middle parts to first 4 characters (NO dot)
            else:
                truncated_parts.append(part[:4] if len(part) > 4 else part)
        
        # Join with NO hyphens - just concatenate with dots
        street_name = '.'.join(truncated_parts)
    
    tier1_result = street_name + house_number
    
    return tier1_result

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
            
            # Handle "Vegetarisch / X" pattern -> keep only "X"
            if part.startswith('Vegetarisch /'):
                part = part.replace('Vegetarisch /', '').strip()
            
            # Handle "X / Standard" pattern -> keep only "X"
            if part.endswith('/ Standard'):
                part = part.replace('/ Standard', '').strip()
            
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
    
    # Rule 14: General spätzle cleanup patterns
    # Pattern 1: "X vom Rind & Spätzle" -> "X" (removes meat description and spätzle)
    name = re.sub(r'\s+vom\s+\w+\s*&\s*[Ss][pä][aeä]tzle', '', name, flags=re.IGNORECASE)
    # Pattern 2: "X & Spätzle" -> "X" (general & Spätzle removal)
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
    # DEBUG: Force unbuffered output
    import sys
    print(f"=== MESSAGE TEXT DEBUG ===", flush=True, file=sys.stderr)
    print(f"Text length: {len(text)}", flush=True, file=sys.stderr)
    print(f"First 100 chars: {repr(text[:100])}", flush=True, file=sys.stderr)
    if len(text) > 16:
        print(f"Char at pos 16: {repr(text[16])}", flush=True, file=sys.stderr)
        print(f"Chars 0-25: {repr(text[:25])}", flush=True, file=sys.stderr)
    
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

def build_status_lines(order: dict, message_type: str, RESTAURANT_SHORTCUTS: dict = None, COURIER_SHORTCUTS: dict = None) -> str:
    """
    Build status lines from status_history to prepend to messages.
    
    Status lines show current order state at TOP of message and REPLACE (never accumulate).
    
    Args:
        order: Order dict from STATE with status_history
        message_type: "mdg", "rg", or "upc"
        RESTAURANT_SHORTCUTS: Dict mapping vendor names to shortcuts (e.g., {"Leckerolls": "LR"})
        COURIER_SHORTCUTS: Dict mapping courier names to shortcuts (e.g., {"Bee 1": "B1"})
        
    Returns:
        Formatted status line(s) with trailing newlines, or empty string if no history
        
    Examples:
        MDG: "📍 Sent ⚡ Asap to 👨‍🍳 LR\n📍 Sent ⚡ Asap to 👩‍🍳 DD\n\n"
        RG:  "📍 Asked for 🕒 14:30 by dishbee\n\n"
        UPC: "🚨 Order assigned 👉 to you (dishbee)\n\n"
    """
    status_history = order.get("status_history", [])
    if not status_history:
        return ""
    
    # Chef emojis for rotation (12 variations)
    chef_emojis = ['👩‍🍳', '👩🏻‍🍳', '👩🏼‍🍳', '👩🏾‍🍳', '🧑‍🍳', '🧑🏻‍🍳', '🧑🏼‍🍳', '🧑🏾‍🍳', '👨‍🍳', '👨🏻‍🍳', '👨🏼‍🍳', '👨🏾‍🍳']
    
    # Get latest status
    latest = status_history[-1]
    status_type = latest.get("type")
    
    # Helper: Get chef emoji for vendor
    def get_chef_emoji(vendor_name):
        return chef_emojis[hash(vendor_name) % len(chef_emojis)]
    
    # Helper: Get vendor shortcut
    def get_vendor_shortcut(vendor_name):
        if RESTAURANT_SHORTCUTS:
            return RESTAURANT_SHORTCUTS.get(vendor_name, vendor_name[:2].upper())
        return vendor_name[:2].upper()
    
    # Helper: Get courier shortcut
    def get_courier_shortcut(courier_name):
        if COURIER_SHORTCUTS:
            return COURIER_SHORTCUTS.get(courier_name, courier_name[:2] if len(courier_name) >= 2 else courier_name)
        # Default: first 2 letters
        return courier_name[:2] if len(courier_name) >= 2 else courier_name
    
    # === MDG STATUS LINES ===
    if message_type == "mdg":
        if status_type == "new":
            # Determine source: Shopify vs Smoothr
            order_type = order.get("order_type", "shopify")
            if order_type == "shopify":
                return "🚨 New order (dishbee)\n\n"
            elif order_type == "smoothr_dnd":
                return "🚨 New order (D&D App)\n\n"
            elif order_type == "smoothr_lieferando":
                return "🚨 New order (Lieferando)\n\n"
            else:
                return "🚨 New order\n\n"
        
        elif status_type == "asap_sent":
            # Show only LATEST asap_sent status (replace, don't accumulate)
            vendor = latest.get("vendor", "")
            chef_emoji = get_chef_emoji(vendor)
            shortcut = get_vendor_shortcut(vendor)
            return f"📍 Sent ⚡ Asap to {chef_emoji} {shortcut}\n\n"
        
        elif status_type == "time_sent":
            # Multi-vendor: separate line per vendor with their requested time
            lines = []
            for entry in reversed(status_history):
                if entry.get("type") == "time_sent":
                    vendor = entry.get("vendor", "")
                    time = entry.get("time", "")
                    chef_emoji = get_chef_emoji(vendor)
                    shortcut = get_vendor_shortcut(vendor)
                    lines.append(f"📍 Sent 🕒 {time} to {chef_emoji} {shortcut}")
            return "\n".join(reversed(lines)) + "\n\n"
        
        elif status_type == "confirmed":
            # Multi-vendor: separate line per vendor with their confirmed time
            lines = []
            for entry in reversed(status_history):
                if entry.get("type") == "confirmed":
                    vendor = entry.get("vendor", "")
                    time = entry.get("time", "")
                    chef_emoji = get_chef_emoji(vendor)
                    shortcut = get_vendor_shortcut(vendor)
                    lines.append(f"📍 Confirmed 👍 {time} by {chef_emoji} {shortcut}")
            return "\n".join(reversed(lines)) + "\n\n"
        
        elif status_type == "assigned":
            courier = latest.get("courier", "Unknown")
            shortcut = get_courier_shortcut(courier)
            return f"📍 Assigned 👉 to 🐝 {shortcut}\n\n"
        
        elif status_type == "delivered":
            courier = latest.get("courier", "Unknown")
            time = latest.get("time", "")
            shortcut = get_courier_shortcut(courier)
            return f"📍 Delivered ✅ at {time} by 🐝 {shortcut}\n\n"
    
    # === RG STATUS LINES ===
    elif message_type == "rg":
        if status_type == "new":
            return "🚨 New order\n\n"
        
        elif status_type == "asap_sent":
            return "📍 Asked for ⚡ Asap by dishbee\n\n"
        
        elif status_type == "time_sent":
            time = latest.get("time", "")
            return f"📍 Asked for 🕒 {time} by dishbee\n\n"
        
        elif status_type == "confirmed":
            time = latest.get("time", "")
            return f"📍 Prepare this order at {time} 🫕\n\n"
        
        elif status_type == "delivered":
            return "📍 Delivered ✅\n\n"
    
    # === UPC STATUS LINES ===
    elif message_type == "upc":
        if status_type == "assigned":
            return "🚨 Order assigned 👉 to you (dishbee)\n\n"
        
        elif status_type == "delay_sent":
            vendors = latest.get("vendors", [])
            shortcuts = "+".join([get_vendor_shortcut(v) for v in vendors])
            return f"📍 Delay ⏰ sent to {shortcuts}\n\n"
        
        elif status_type == "delivered":
            time = latest.get("time", "")
            return f"📍 Delivered ✅ at {time}\n\n"
    
    # Default: no status line
    return ""

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


def get_error_description(error: Exception) -> str:
    """
    Get a human-readable short error description based on exception type.
    
    Converts technical Telegram API errors into user-friendly messages.
    Used for universal error handling across all message sending operations.
    
    Args:
        error: The exception that was raised
        
    Returns:
        Short error description string for display to user
        
    Examples:
        TimedOut → "Network timeout"
        NetworkError → "Network connection lost"
        RetryAfter → "Rate limit exceeded"
    """
    from telegram.error import TimedOut, NetworkError, RetryAfter, Forbidden, BadRequest, ChatMigrated
    
    error_name = type(error).__name__
    
    # Telegram-specific errors
    if isinstance(error, TimedOut):
        return "Network timeout"
    elif isinstance(error, NetworkError):
        return "Network connection lost"
    elif isinstance(error, RetryAfter):
        return f"Rate limit exceeded (retry in {error.retry_after}s)"
    elif isinstance(error, Forbidden):
        return "Bot blocked by user or insufficient permissions"
    elif isinstance(error, BadRequest):
        error_msg = str(error).lower()
        if "chat not found" in error_msg:
            return "Chat not found"
        elif "user not found" in error_msg:
            return "User not found"
        elif "message is too long" in error_msg:
            return "Message too long"
        elif "message can't be deleted" in error_msg:
            return "Message already deleted"
        elif "message to edit not found" in error_msg:
            return "Message not found"
        else:
            return f"Invalid request ({error_msg[:50]})"
    elif isinstance(error, ChatMigrated):
        return "Chat was migrated to supergroup"
    
    # Generic errors
    elif isinstance(error, ConnectionError):
        return "Connection error"
    elif isinstance(error, TimeoutError):
        return "Request timeout"
    elif isinstance(error, ValueError):
        return f"Invalid value ({str(error)[:30]})"
    
    # Fallback to exception name
    return f"{error_name}: {str(error)[:50]}"


# =============================================================================
# SMOOTHR ORDER DETECTION AND PARSING
# =============================================================================

def is_smoothr_order(text: str) -> bool:
    """
    Detect Smoothr orders by unique '- Order:' field format.
    
    Smoothr orders contain '- Order:' field and other hyphen-prefixed fields.
    The message may have "Smoothr BOT" as first line (sent by Smoothr Bot),
    or start directly with "-" (sent by channel).
    
    Format examples:
    - Order: BMW74X (6 chars: letters+numbers, Lieferando)
    - Order: 562 (3 digits starting with 500+, D&D App)
    - Order: GHPD97 (alphanumeric, Lieferando)
    
    Args:
        text: Message text to check
        
    Returns:
        True if text contains '- Order:' field
    """
    if not text:
        return False
    
    # Check if message contains Smoothr order format (regardless of first line)
    return "- Order:" in text and "- Customer:" in text


def get_smoothr_order_type(order_code: str) -> tuple[str, str]:
    """
    Determine order type and display number from Smoothr order code.
    
    D&D App orders: 3-4 digits in range 500-599 (e.g., "500", "515", "599")
    Lieferando orders: Alphanumeric code (e.g., "3DX8TD")
    
    Args:
        order_code: The order code from Smoothr
        
    Returns:
        Tuple of (order_type, display_num)
        - D&D App: ("smoothr_dnd", "500") - full number
        - Lieferando: ("smoothr_lieferando", "TD") - last 2 chars
    """
    order_code = order_code.strip()
    
    # Check if it's a D&D App order (digits in range 500-599)
    if order_code.isdigit() and 500 <= int(order_code) <= 599:
        return ("smoothr_dnd", order_code)  # Full 3-4 digits
    else:
        # Lieferando order - use last 2 characters
        return ("smoothr_lieferando", order_code[-2:] if len(order_code) >= 2 else order_code)


def parse_smoothr_order(text: str) -> dict:
    """
    Parse Smoothr order message into STATE-compatible dictionary.
    
    Extracts:
    - Order code and type (D&D App vs Lieferando)
    - Customer name, phone, email
    - Address (street + building) and zip
    - ASAP status
    - Requested delivery time (UTC → Local +2h)
    
    Args:
        text: Smoothr order message text
        
    Returns:
        Dictionary with parsed order data
        
    Raises:
        ValueError: If required fields are missing or parsing fails
    """
    from zoneinfo import ZoneInfo
    
    lines = text.strip().split('\n')
    order_data = {}
    
    # Parse line by line
    address_lines = []
    in_address_block = False
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        if line.startswith("- Order:"):
            order_code = line.split(":", 1)[1].strip()
            order_data["order_code"] = order_code
            order_type, display_num = get_smoothr_order_type(order_code)
            order_data["order_type"] = order_type
            order_data["order_num"] = display_num
            
        elif line.startswith("- Customer:"):
            order_data["customer_name"] = line.split(":", 1)[1].strip()
            
        elif line.startswith("- Address:"):
            in_address_block = True
            # Address is on following lines
            
        elif line.startswith("- Phone:"):
            in_address_block = False
            phone = line.split(":", 1)[1].strip()
            order_data["phone"] = phone
            
        elif line.startswith("- Email:"):
            email = line.split(":", 1)[1].strip()
            order_data["email"] = email if email else None
            
        elif line.startswith("- ASAP:"):
            asap_value = line.split(":", 1)[1].strip()
            order_data["is_asap"] = asap_value.lower() == "yes"
            
        elif line.startswith("- Order Date:"):
            order_date_str = line.split(":", 1)[1].strip()
            order_data["order_date_raw"] = order_date_str
            
            # Parse ISO timestamp and convert UTC to local (+2h for Germany)
            try:
                # Parse: 2025-10-23T10:00:00.000Z
                dt_utc = datetime.fromisoformat(order_date_str.replace('Z', '+00:00'))
                # Convert to Europe/Berlin timezone (UTC+1 or UTC+2 depending on DST)
                dt_local = dt_utc.astimezone(ZoneInfo("Europe/Berlin"))
                order_data["order_datetime"] = dt_local
                order_data["requested_delivery_time"] = dt_local.strftime("%H:%M")
            except Exception as e:
                logger.error(f"Failed to parse order date '{order_date_str}': {e}")
                order_data["requested_delivery_time"] = None
                
        elif in_address_block and line and not line.startswith("-"):
            # Collect address lines until next field
            address_lines.append(line)
    
    # Process address lines
    if address_lines:
        # First line is street + building
        order_data["street"] = address_lines[0] if len(address_lines) > 0 else ""
        
        # Last line usually has zip + city
        if len(address_lines) > 1:
            last_line = address_lines[-1]
            # Extract zip (5 digits)
            zip_match = None
            for part in last_line.split():
                if part.isdigit() and len(part) == 5:
                    zip_match = part
                    break
            order_data["zip"] = zip_match if zip_match else "94032"  # Default Passau zip
        else:
            order_data["zip"] = "94032"
        
        # Full address for Google Maps
        order_data["full_address"] = ", ".join(address_lines)
    
    # Validate required fields
    required = ["order_code", "customer_name", "phone"]
    missing = [field for field in required if not order_data.get(field)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    
    # Build STATE-compatible structure
    result = {
        "order_id": order_data["order_code"],
        "order_num": order_data["order_num"],
        "order_type": order_data["order_type"],
        "customer": {
            "name": order_data["customer_name"],
            "phone": order_data["phone"],
            "email": order_data.get("email"),
            "address": order_data.get("street", ""),
            "zip": order_data.get("zip", "94032"),
            "original_address": order_data.get("full_address", "")
        },
        "is_asap": order_data["is_asap"],
        "requested_delivery_time": None if order_data["is_asap"] else order_data.get("requested_delivery_time"),
        "smoothr_raw": text  # Keep original for debugging
    }
    
    return result
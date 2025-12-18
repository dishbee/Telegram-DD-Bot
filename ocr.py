"""
OCR Module for Pommes Freunde Lieferando Orders
Extracts text from order photos and parses required fields
"""

import os
import re
import requests
import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class ParseError(Exception):
    """Raised when OCR parsing fails"""
    pass

def extract_text_from_image(photo_path: str) -> str:
    """
    Run OCR.space API on image and return raw text.
    
    Args:
        photo_path: Absolute path to downloaded photo
        
    Returns:
        Raw OCR text output
        
    Raises:
        ParseError: If image cannot be processed
    """
    api_key = os.getenv('OCR_API_KEY')
    if not api_key:
        raise ParseError("OCR_API_KEY not set in environment")
    
    try:
        # Call OCR.space API
        with open(photo_path, 'rb') as f:
            response = requests.post(
                'https://api.ocr.space/parse/image',
                files={'file': f},
                data={
                    'apikey': api_key,
                    'language': 'ger',  # German for Lieferando orders
                    'isOverlayRequired': False,
                    'detectOrientation': True,
                    'scale': True,
                    'isTable': False  # Optimize for document text layout
                },
                timeout=30
            )        # Check HTTP status first
        if response.status_code != 200:
            logger.error(f"[OCR] API returned status {response.status_code}")
            logger.error(f"[OCR] Response text: {response.text[:500]}")
            raise ParseError(f"OCR API HTTP error: {response.status_code}")
        
        # Check if response is valid JSON
        try:
            result = response.json()
        except ValueError as e:
            logger.error(f"[OCR] Invalid JSON response from API")
            logger.error(f"[OCR] Response text: {response.text[:500]}")
            raise ParseError(f"OCR API returned invalid JSON: {str(e)}")
        
        # Check for API errors
        if result.get('IsErroredOnProcessing'):
            error_msg = result.get('ErrorMessage', 'Unknown error')
            logger.error(f"[OCR] API processing error: {error_msg}")
            raise ParseError(f"OCR API error: {error_msg}")
        
        # Check if parsed results exist
        if not result.get('ParsedResults') or len(result['ParsedResults']) == 0:
            logger.error(f"[OCR] No ParsedResults in API response")
            logger.error(f"[OCR] Full response: {result}")
            raise ParseError("OCR API returned no results")
        
        text = result['ParsedResults'][0]['ParsedText']
        
        # Log raw output for debugging
        logger.info(f"[OCR] Raw text extracted from {photo_path}:")
        logger.info(f"[OCR] FULL TEXT:\n{text}")
        logger.info(f"[OCR] Total length: {len(text)} characters")
        
        return text
        
    except ParseError:
        # Re-raise ParseError as-is (already has descriptive message)
        raise
    except requests.RequestException as e:
        logger.error(f"[OCR] Network error calling OCR API: {str(e)}")
        raise ParseError(f"Network error: {str(e)}")
    except Exception as e:
        logger.error(f"[OCR] Unexpected error: {str(e)}")
        raise ParseError(f"Unexpected error: {str(e)}")

def parse_pf_order(ocr_text: str) -> dict:
    """
    Parse Pommes Freunde order fields from OCR text.
    
    Args:
        ocr_text: Raw OCR output from extract_text_from_image()
        
    Returns:
        dict with keys: order_num, customer, phone, address, zip, time, total, note, product_count
        
    Raises:
        ParseError: If any required field is missing
    """
    result = {}
    
    # 0. Check for Selbstabholung (pickup orders - reject immediately)
    if re.search(r'Bestellung zur Abholung|zur Abholung', ocr_text, re.IGNORECASE):
        raise ParseError("SELBSTABHOLUNG")
    
    # 1. Order # (optional): #ABC XYZ format
    # Extract last 2 chars from 2nd group for display
    # Example: "#VCJ 34V" → order_num="4V"
    # Example: "#SM9 8H3" → order_num="H3"
    # If OCR fails to extract order code, use "N/A" as fallback
    order_match = re.search(r'[#*]\s*([A-Z0-9]{3})\s+([A-Z0-9]{3})', ocr_text, re.IGNORECASE)
    if not order_match:
        result['order_num'] = "N/A"
        logger.warning(f"[ORDER-N/A] Order code not found in OCR text, using fallback")
        # When order code missing, use "Bezahlt" marker as starting point for name/address search
        bezahlt_match = re.search(r'Bezahlt', ocr_text, re.IGNORECASE)
        if bezahlt_match:
            order_end = bezahlt_match.end()
        else:
            # Fallback: use ZIP code as reference point
            zip_fallback = re.search(r'\b940\d{2}\b', ocr_text)
            order_end = zip_fallback.start() if zip_fallback else 0
    else:
        full_code = order_match.group(2).upper()
        result['order_num'] = full_code[-2:]  # Last 2 chars
        logger.info(f"[ORDER-{result['order_num']}] Parsed PF order from OCR")
        order_end = order_match.end()
    
    # 2. ZIP (required): 5 digits (Passau = 940XX)
    zip_match = re.search(r'\b(940\d{2})\b', ocr_text)
    if not zip_match:
        raise ParseError(detect_collapse_error(ocr_text))
    result['zip'] = zip_match.group(1)
    
    # 3. Customer Name (required): After order code, before full address
    # Pattern: Standalone line with name, may have prefix ("A. Hasan", "L. Hoffmann")
    # Must NOT be from note section (check for note indicators first)
    
    # Find text between order code and phone number
    # Skip phones inside quoted notes (e.g., "Bitte anrufen... +49...")
    # Match phone with emoji OR on own line OR after newline
    phone_pattern = r'(?:📞\s*|^\s*|\n\s*)(\+?\d{10,20})'
    phone_matches = list(re.finditer(phone_pattern, ocr_text[order_end:], re.MULTILINE))
    
    # Filter out phones inside quotes by checking quote count before match
    phone_pos = None
    for match in phone_matches:
        start_pos = order_end + match.start()
        # Look back 100 chars for context
        lookback = ocr_text[max(0, start_pos-100):start_pos]
        # Count quotes before this phone
        quote_count = lookback.count('"')
        # If even number of quotes (or zero), phone is NOT inside quoted text
        if quote_count % 2 == 0:
            phone_pos = match
            break
    
    if phone_pos:
        # Search for name in section BEFORE phone
        search_area = ocr_text[order_end:order_end + phone_pos.start()]
    else:
        # Fallback: search in next 300 chars after order code
        search_area = ocr_text[order_end:order_end + 300]
    
    # Strip multi-line quoted notes from search_area
    # Notes like "text...\n more text...\n end" have quotes only on first/last line
    # This prevents note lines from matching as customer name
    search_area = re.sub(r'[""\u201c\u201d][^""\u201c\u201d]*[""\u201c\u201d]', '', search_area, flags=re.DOTALL)
    
    # Find name line: starts with letter (upper or lower case), not a street name pattern, not in quotes
    # Exclude lines with: numbers at start, quotes, bicycle emoji, UI elements
    # Allow patterns: "H. Buchner", "LT. Welke", "M. Steinleitner", "Welke", "h. Khatib", "F. Auriemma", "É. Frowein-Hundertmark"
    # Pattern: One or more uppercase/lowercase letters (including accents), optional dot, optional space + more letters
    # Filter out: "Bezahlt" (payment status), "Fertig" (UI tab), "Wird zubereitet", "In Lieferung" (UI tabs)
    name_match = re.search(r'\n\s*(?!(?:Bezahlt|Fertig|Wird|In Lieferung)(?:\s|$))([A-ZÄÖÜÉÈÊÀa-zäöüéèêàß][A-ZÄÖÜÉÈÊÀa-zäöüéèêàß]*\.?(?:[ \t]+[A-ZÄÖÜÉÈÊÀa-zäöüéèêàß][^\n]{1,30})?)\s*\n', search_area, re.IGNORECASE)
    
    if not name_match:
        raise ParseError(detect_collapse_error(ocr_text))
    
    result['customer'] = name_match.group(1).strip()
    
    # 4. Address (required): Full address from customer details section
    # Located AFTER customer name, BEFORE phone
    # Extract complete address including apartment/floor info
    # Pattern: Street + number, may span multiple lines with apartment info
    
    # Find full address block: everything between customer name and phone
    name_end = order_end + name_match.end()
    logger.info(f"[OCR] phone_pos found: {phone_pos is not None}")
    
    if phone_pos:
        address_block = ocr_text[name_end:order_end + phone_pos.start()].strip()
        logger.info(f"[OCR] Using phone_pos for address_block, length: {len(address_block)}")
    else:
        # Fallback: look for address pattern before ZIP
        address_block = ocr_text[name_end:name_end + 200].strip()
        logger.info(f"[OCR] Using fallback for address_block, length: {len(address_block)}")
    
    # Extract ONLY first line before comma (street + number only)
    # Ignore everything after comma (Etage, apartment, floor info)
    address_lines = []
    apartment_info = None  # Store apartment info separately if found
    logger.info(f"[OCR] address_block to process: {repr(address_block[:150])}")
    for line in address_block.split('\n'):
        line = line.strip()
        logger.info(f"[OCR] Processing address line: '{line}' (len={len(line)})")
        # Stop at ZIP code line
        if re.match(r'^940\d{2}', line):
            break
        # Stop at "Bezahlt", "Fertig" (UI button), or empty lines
        if not line or line in ('Bezahlt', 'Fertig', 'Passau'):
            continue
        # Skip lines with quotes (notes are always quoted)
        if '"' in line:
            logger.info(f"[OCR] Skipping quoted line (likely note): '{line}'")
            continue
        # Detect apartment-only lines: "1/ app Nr 316", "App. 5", "Wohnung 12", etc.
        # These should be stored separately, not as part of street address
        # Pattern: optional building number + apartment keyword + optional apartment number
        # Does NOT contain street name indicators (straße, weg, platz, etc.)
        has_street_suffix = any(suffix in line.lower() for suffix in ('straße', 'strasse', 'str.', 'weg', 'platz', 'gasse', 'ring', 'allee'))
        apartment_pattern = re.search(r'(?:app\.?\s*(?:nr\.?\s*)?|wohnung\s*|apt\.?\s*|[1-9]\.\s*og)', line, re.IGNORECASE)
        if apartment_pattern and not has_street_suffix:
            apartment_info = line
            logger.info(f"[OCR] Detected apartment info (stored separately): '{line}'")
            continue
        # Fix OCR misread: "I Franz-Stockbauer-Weg" → "1 Franz-Stockbauer-Weg"
        if re.match(r'^[IO]\s+\w', line) and any(suffix in line.lower() for suffix in ('straße', 'str', 'weg', 'platz', 'ring', 'gasse')):
            line = re.sub(r'^[IO](\s)', r'1\1', line)
            logger.info(f"[OCR] Fixed OCR misread in address: {line}")
        # Skip lines that are just ZIP
        if re.match(r'^\d{5}$', line):
            continue
        # Stop at phone number line (digits only, 10+ chars)
        if re.match(r'^\+?\d{10,}$', line):
            break
        # Stop at total/price line (e.g., "28,90 €" or "37,56 €")
        if re.match(r'^\d+[,\.]\d{2}\s*€', line):
            break
        # Stop at lines with just numbers (like "28" or "37" from total parsing errors)
        # But KEEP alphanumeric building numbers like "9A", "19-21", "4a"
        if re.match(r'^\d{1,3}$', line) and not re.match(r'^\d{1,3}[A-Za-z-]', line):
            break
        # Append valid address line
        address_lines.append(line)
        # Stop after first valid address line (before comma/Etage)
        if ',' in line:
            # Take only part before comma (DON'T replace entire list - keep building number!)
            address_lines[-1] = line.split(',')[0].strip()
            break
    
    logger.info(f"[OCR] address_lines collected: {address_lines}")
    if not address_lines:
        logger.error(f"[OCR] No valid address lines found in address_block")
        raise ParseError(detect_collapse_error(ocr_text))
    
    # Check for duplicate address collection - stop if we have split street name
    # OCR often shows address twice: split in header + complete in details
    if len(address_lines) >= 2:
        first_line = address_lines[0]
        # Pattern: "77 Waldschmidtstr" (number + incomplete street, not ending with complete suffix)
        # Only match COMPLETE suffixes to avoid false positives (e.g., "str" in "Waldschmidtstr")
        complete_suffixes = ('straße', 'strasse', 'weg', 'platz', 'gasse', 'ring', 'allee')
        if first_line and first_line[0].isdigit() and not first_line.lower().endswith(complete_suffixes):
            second_line = address_lines[1] if len(address_lines) > 1 else ""
            # If second line completes the street (e.g., "aße"), keep only first 2 lines
            if second_line and not second_line[0].isdigit():
                address_lines = address_lines[:2]
                logger.info(f"[OCR] Detected split address, keeping only first 2 lines: {address_lines}")
    
    # Join address lines WITH spaces (preserve multi-word patterns like "1/ app Nr 316")
    # Handle word wrapping in street names (e.g., "Dr.-Hans-Kapfi\nger-Straße" split across lines)
    full_address_raw = ' '.join(address_lines)
    # Remove word-wrap artifacts: if hyphenated word is split with space, rejoin it
    full_address_raw = re.sub(r'(\w+)- (\w+)', r'\1-\2', full_address_raw)
    # Fix OCR word breaks in German street names: "Waldschmidtstr aße" → "Waldschmidtstraße"
    full_address_raw = re.sub(r'(str|straß|gass|plätz|wag)\s+(aße|e|en)', r'\1\2', full_address_raw, flags=re.IGNORECASE)
    
    # Remove ZIP and city if they appear in address
    full_address_raw = re.sub(r',?\s*940\d{2}\s*,?', '', full_address_raw)
    full_address_raw = re.sub(r',?\s*Passau\s*', '', full_address_raw)
    full_address_raw = full_address_raw.strip().rstrip(',')
    
    # Reformat address: "Number Street" → "Street Number"
    # Handle patterns like "13 Dr.-Hans-Kapfinger-Straße" or "1/ app Nr 316 Leonhard-Paminger-Straße"
    address_parts = full_address_raw.split()
    
    if len(address_parts) >= 2:
        # Define street patterns for comprehensive detection
        street_suffixes = ('straße', 'strasse', 'str', 'gasse', 'platz', 'ring', 'weg', 'allee', 'hof', 'damm', 'ort', 'markt', 'dobl')
        street_prefixes = ('untere', 'obere', 'alte', 'neue', 'große', 'kleine', 'innere', 'äußere', 'am')
        
        # Check for pattern: "Number Street" (e.g., "60 Neuburger Straße" or "129 Göttweiger Str.")
        # First part starts with digit (allows alphanumeric like "25a", "1A"), last part has street suffix
        first_starts_with_digit = address_parts[0][0].isdigit() if address_parts[0] else False
        last_has_suffix = address_parts[-1].lower().rstrip('.').endswith(street_suffixes)
        
        if first_starts_with_digit and last_has_suffix:
            # Pattern: "60 Neuburger Straße" → number="60", street="Neuburger Straße"
            number = address_parts[0]
            street = ' '.join(address_parts[1:])
            result['address'] = f"{street} {number}"
            logger.info(f"OCR Address parsed (number-first pattern): street='{street}', number='{number}'")
        elif len(address_parts) == 2 and first_starts_with_digit:
            # Simple 2-word pattern: "8 Roßtränke" → assume "Roßtränke 8"
            number = address_parts[0]
            street = address_parts[1]
            result['address'] = f"{street} {number}"
            logger.info(f"OCR Address parsed (2-word pattern): street='{street}', number='{number}'")
        else:
            # Original logic: Scan for street start marker
            # OCR shows address in order: building number FIRST, street name AFTER
            # Example: "2 Traminer Straße" or "1/ app Nr 316 Leonhard-Paminger-Straße"
            # Need to identify where street name starts, collect everything before as building number
            
            building_number_parts = []
            street_name_parts = []
            found_street = False
            
            for part in address_parts:
                if not found_street:
                    # Check if this looks like start of street name:
                    # 1) Contains hyphen (e.g., "Dr.-Hans-Kapfinger-Straße")
                    # 2) Ends with street suffix (straße, gasse, platz, ring, etc.)
                    # 3) Is a multi-word street prefix (Untere, Alte, Neue, etc.)
                    if ('-' in part or 
                        part.lower().endswith(street_suffixes) or 
                        part.lower() in street_prefixes):
                        # This is the street name
                        found_street = True
                        street_name_parts.append(part)
                    else:
                        # Still part of building number
                        building_number_parts.append(part)
                else:
                    # Already found street, rest is part of street name
                    street_name_parts.append(part)
            
            if street_name_parts and building_number_parts:
                # Format: "Street Name Building Number" (e.g., "Traminer Straße 2")
                street = ' '.join(street_name_parts)
                number = ' '.join(building_number_parts)
                result['address'] = f"{street} {number}"
                logger.info(f"OCR Address parsed: street='{street}', number='{number}'")
            elif street_name_parts:
                # Only street name found, no building number
                result['address'] = ' '.join(street_name_parts)
                logger.info(f"OCR Address parsed: only street='{result['address']}'")
            else:
                # No street name pattern found, use raw address
                result['address'] = full_address_raw
                logger.info(f"OCR Address parsed: no pattern match, using raw='{result['address']}'")
    else:
        result['address'] = full_address_raw
        logger.info(f"OCR Address parsed: single word, using raw='{result['address']}'")
    
    # 5. Phone (required): Extract from expanded details section (after customer name, before total)
    # Phone appears with emoji: 📞 +4917647373945 or 📞 015739645573
    # Search in section AFTER customer name to avoid capturing ZIP or other numbers
    phone_search_area = ocr_text[name_end:name_end + 300]  # Search in next 300 chars after name
    logger.info(f"[OCR] Phone search area: {repr(phone_search_area[:100])}")
    # Allow any whitespace (including newlines) before phone number
    # Match: +49..., 0... (German format), or phone emoji followed by number
    phone_match = re.search(r'📞?\s*([O0+]?\d[\d -)]{8,20})', phone_search_area)
    # Fallback: try matching bare phone numbers starting with 0 (e.g., "017677276446")
    if not phone_match:
        phone_match = re.search(r'\b(0\d{9,14})\b', phone_search_area)
    logger.info(f"[OCR] Phone match result: {phone_match}")
    
    if not phone_match:
        logger.error(f"[OCR] Phone regex failed. Search area length: {len(phone_search_area)}")
        raise ParseError(detect_collapse_error(ocr_text))
    
    phone = phone_match.group(1).replace(' ', '').replace('-', '').replace(')', '').strip()
    # Fix OCR errors: O → 0
    phone = phone.replace('O', '0')
    
    # Normalize phone: add +49 if missing, remove leading 0
    if not phone.startswith('+'):
        if phone.startswith('0'):
            phone = '+49' + phone[1:]  # Remove 0, add +49
        else:
            phone = '+49' + phone  # Add +49
    
    if len(phone) < 10:  # Minimum valid phone length with country code
        raise ParseError(detect_collapse_error(ocr_text))
    result['phone'] = phone
    
    # 6. Product count: Extract from "X Artikel" (fallback to "N/A" if OCR misreads)
    artikel_match = re.search(r'(\d+)\s*Artike?l?', ocr_text, re.IGNORECASE)
    if artikel_match:
        result['product_count'] = int(artikel_match.group(1))
    else:
        # Fallback: OCR may misread number (e.g., "3" as "$")
        result['product_count'] = 'N/A'
    
    # 7. Scheduled Time: Check for "Geplant" indicator
    # Pattern: OCR shows "XX Min." (minutes until ready) near "Geplant", need to calculate actual time
    # Extract: screen_time (from top) + minutes = scheduled_time
    geplant_pos = ocr_text.lower().find('geplant')
    if geplant_pos != -1:
        # Look in last 50 chars before "Geplant" for "XX Min" pattern
        pre_geplant = ocr_text[max(0, geplant_pos - 50):geplant_pos]
        logger.info(f"[OCR] pre_geplant text: {repr(pre_geplant)}")
        
        # Match "XX Min" pattern OR standalone minutes (just "45" on its own line before Geplant)
        min_pattern_match = re.search(r'(\d{1,3})\s*Min', pre_geplant, re.IGNORECASE)
        
        # Fallback: standalone number at end of pre_geplant (e.g., "45\r\n" without "Min")
        # Only match 1-3 digit numbers that are reasonable minutes (1-180)
        standalone_min_match = None
        if not min_pattern_match:
            standalone_min_match = re.search(r'(\d{1,3})\s*\r?\n\s*$', pre_geplant)
            if standalone_min_match:
                mins = int(standalone_min_match.group(1))
                if mins < 1 or mins > 180:
                    standalone_min_match = None  # Invalid range, ignore
        
        if min_pattern_match or standalone_min_match:
            # Found minutes pattern - need to calculate scheduled time
            if min_pattern_match:
                minutes_until_ready = int(min_pattern_match.group(1))
                logger.info(f"[OCR] Found 'XX Min' pattern: {minutes_until_ready} minutes")
            else:
                minutes_until_ready = int(standalone_min_match.group(1))
                logger.info(f"[OCR] Found standalone minutes: {minutes_until_ready} minutes")
            
            # Extract screen time from top of OCR (first time pattern in text)
            screen_time_match = re.search(r'^[^\n]*?(\d{1,2}):(\d{2})', ocr_text, re.MULTILINE)
            
            if screen_time_match:
                from datetime import datetime, timedelta
                screen_hour = int(screen_time_match.group(1))
                screen_minute = int(screen_time_match.group(2))
                
                # Handle 12-hour format (5:43 could be AM or PM)
                # Food delivery orders are typically PM (afternoon/evening)
                # But hours 10-11 should NOT add 12 (10:34 is already 10:34, not 22:34)
                current_time = datetime.now().replace(hour=screen_hour, minute=screen_minute, second=0, microsecond=0)
                
                # Only add 12 hours if hour is clearly morning (1-9)
                # Hours 10-11 could be either AM or PM, assume AM (don't add 12)
                # Hours 12+ are already PM
                if screen_hour >= 1 and screen_hour <= 9:
                    current_time = current_time.replace(hour=screen_hour + 12)
                
                scheduled_time = current_time + timedelta(minutes=minutes_until_ready)
                result['time'] = scheduled_time.strftime("%H:%M")
                logger.info(f"[OCR] Calculated Geplant time: {screen_hour}:{screen_minute:02d} + {minutes_until_ready} min = {result['time']}")
            else:
                # Fallback: can't find screen time, use 'asap'
                logger.warning(f"[OCR] Found minutes but no screen time, using asap")
                result['time'] = 'asap'
        else:
            # No minutes pattern - this is a direct scheduled time like "12:35 Geplant"
            # Search in the text before "Geplant" for a time pattern (HH:MM)
            direct_time_match = re.search(r'(\d{1,2}):(\d{2})', pre_geplant)
            
            if direct_time_match:
                hour = int(direct_time_match.group(1))
                minute = int(direct_time_match.group(2))
                if hour > 23 or minute > 59:
                    raise ParseError(detect_collapse_error(ocr_text))
                result['time'] = f"{hour:02d}:{minute:02d}"
                logger.info(f"[OCR] Found direct Geplant time: {result['time']}")
            else:
                result['time'] = 'asap'
                logger.warning(f"[OCR] Found 'Geplant' but no time pattern in pre_geplant: {repr(pre_geplant)}")
    else:
        result['time'] = 'asap'
    
    # 8. Total (required): Format "XX,XX €"
    total_match = re.search(r'(\d+,\d{2})\s*€', ocr_text)
    if not total_match:
        raise ParseError(detect_collapse_error(ocr_text))
    result['total'] = float(total_match.group(1).replace(',', '.'))
    
    # 9. Note (optional): Extract if note section present
    # Look for bicycle emoji indicator (🚴) - this appears when customer added a note
    bike_emoji_match = re.search(r'🚴', ocr_text)
    
    if bike_emoji_match:
        # Found bike emoji - note section exists
        # Check if collapsed (arrow symbol present AFTER the emoji)
        emoji_pos = bike_emoji_match.start()
        text_after_emoji = ocr_text[emoji_pos:emoji_pos + 50]
        is_collapsed = bool(re.search(r'[▸▼▽►]', text_after_emoji))
        if is_collapsed:
            raise ParseError(detect_collapse_note(ocr_text))
        
        # Extract note from quotes ONLY in area AFTER bike emoji (within 200 chars)
        # This prevents capturing product names like "Classic Patty" from product section
        note_search_area = ocr_text[emoji_pos:emoji_pos + 200]
        # Use DOTALL to match multi-line notes (quotes on first/last line only)
        note_match = re.search(r'[""\u201c\u201d]([^""\u201c\u201d]{5,})[""\u201c\u201d]', note_search_area, re.DOTALL)
        result['note'] = note_match.group(1).strip().replace('\r\n', ' ').replace('\n', ' ') if note_match else None
    else:
        # No bike emoji = no customer note
        result['note'] = None
    
    return result


def detect_collapse_error(ocr_text: str) -> str:
    """
    Detect specific collapse errors and return appropriate error code.
    
    Returns:
        Error code string: DETAILS_COLLAPSED, NOTE_COLLAPSED, 
        DETAILS_AND_NOTE_COLLAPSED, or OCR_FAILED
    """
    # Check if phone number is missing (details collapsed)
    has_phone = bool(re.search(r'📞?\s*\+?\d{10,20}', ocr_text))
    
    # Check if note indicator present with arrow (collapsed)
    has_note_indicator = bool(re.search(r'[🚚🚴]', ocr_text))
    # Expanded arrow pattern to catch Unicode variations: ▼▽►▻⊳>vV( and parentheses
    has_collapsed_arrow = bool(re.search(r'[▼▽►▻⊳>vV(]', ocr_text))
    has_collapsed_note = has_note_indicator and has_collapsed_arrow
    
    # Determine error type
    if not has_phone and has_collapsed_note:
        return "DETAILS_AND_NOTE_COLLAPSED"
    elif not has_phone:
        return "DETAILS_COLLAPSED"
    elif has_collapsed_note:
        return "NOTE_COLLAPSED"
    else:
        return "OCR_FAILED"


def detect_collapse_note(ocr_text: str) -> str:
    """Check if details are also collapsed along with note."""
    has_phone = bool(re.search(r'📞?\s*\+?\d{10,20}', ocr_text))
    
    if not has_phone:
        return "DETAILS_AND_NOTE_COLLAPSED"
    else:
        return "NOTE_COLLAPSED"

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
    
    # 1. Order # (required): #ABC XYZ format
    # Extract last 2 chars from 2nd group for display
    # Example: "#VCJ 34V" → order_num="4V"
    # Example: "#SM9 8H3" → order_num="H3"
    order_match = re.search(r'[#*]\s*([A-Z0-9]{3})\s+([A-Z0-9]{3})', ocr_text, re.IGNORECASE)
    if not order_match:
        raise ParseError(detect_collapse_error(ocr_text))
    
    full_code = order_match.group(2).upper()
    result['order_num'] = full_code[-2:]  # Last 2 chars
    
    # 2. ZIP (required): 5 digits (Passau = 940XX)
    zip_match = re.search(r'\b(940\d{2})\b', ocr_text)
    if not zip_match:
        raise ParseError(detect_collapse_error(ocr_text))
    result['zip'] = zip_match.group(1)
    
    # 3. Customer Name (required): After order code, before full address
    # Pattern: Standalone line with name, may have prefix ("A. Hasan", "L. Hoffmann")
    # Must NOT be from note section (check for note indicators first)
    order_end = order_match.end()
    
    # Find text between order code and phone number
    phone_pattern = r'📞?\s*\+?\d{10,}'
    phone_pos = re.search(phone_pattern, ocr_text[order_end:])
    
    if phone_pos:
        # Search for name in section BEFORE phone
        search_area = ocr_text[order_end:order_end + phone_pos.start()]
    else:
        # Fallback: search in next 300 chars after order code
        search_area = ocr_text[order_end:order_end + 300]
    
    # Find name line: starts with letter (upper or lower case), not a street name pattern, not in quotes
    # Exclude lines with: numbers at start, quotes, bicycle emoji, "Geplant"
    name_match = re.search(r'\n\s*([A-ZÄÖÜa-zäöüß][a-zäöüß]*\.?\s+[A-ZÄÖÜa-zäöüß][^\n]{1,30})\s*\n', search_area)
    
    if not name_match:
        raise ParseError(detect_collapse_error(ocr_text))
    
    result['customer'] = name_match.group(1).strip()
    
    # 4. Address (required): Full address from customer details section
    # Located AFTER customer name, BEFORE phone
    # Extract complete address including apartment/floor info
    # Pattern: Street + number, may span multiple lines with apartment info
    
    # Find full address block: everything between customer name and phone
    name_end = order_end + name_match.end()
    
    if phone_pos:
        address_block = ocr_text[name_end:order_end + phone_pos.start()].strip()
    else:
        # Fallback: look for address pattern before ZIP
        address_block = ocr_text[name_end:name_end + 200].strip()
    
    # Extract ONLY first line before comma (street + number only)
    # Ignore everything after comma (Etage, apartment, floor info)
    address_lines = []
    for line in address_block.split('\n'):
        line = line.strip()
        # Stop at ZIP code line
        if re.match(r'^940\d{2}', line):
            break
        # Stop at "Bezahlt" or empty lines
        if not line or line == 'Bezahlt' or line == 'Passau':
            continue
        # Skip lines that are just ZIP
        if re.match(r'^\d{5}$', line):
            continue
        address_lines.append(line)
        # Stop after first valid address line (before comma/Etage)
        if ',' in line:
            # Take only part before comma
            address_lines = [line.split(',')[0].strip()]
            break
    
    if not address_lines:
        raise ParseError(detect_collapse_error(ocr_text))
    
    # Join address lines WITHOUT spaces (handles word wrapping in OCR)
    # Example: "Dr.-Hans-Kapfin\nger-Straße" → "Dr.-Hans-Kapfinger-Straße"
    full_address_raw = ''.join(address_lines)
    
    # Remove ZIP and city if they appear in address
    full_address_raw = re.sub(r',?\s*940\d{2}\s*,?', '', full_address_raw)
    full_address_raw = re.sub(r',?\s*Passau\s*', '', full_address_raw)
    full_address_raw = full_address_raw.strip().rstrip(',')
    
    # Reformat address: "Number Street" → "Street Number"
    # Handle patterns like "13 Dr.-Hans-Kapfinger-Straße" or "1/ app Nr 316 Leonhard-Paminger-Straße"
    address_parts = full_address_raw.split()
    
    if len(address_parts) >= 2:
        # Check if first part is a number (building number)
        first_part = address_parts[0].rstrip(',')
        if re.match(r'^\d+[a-z]?/?$', first_part, re.IGNORECASE):
            # Starts with number - move to end
            # Example: "13 Dr.-Hans-Kapfinger-Straße" → "Dr.-Hans-Kapfinger-Straße 13"
            number = first_part
            street_parts = address_parts[1:]
            
            # Find where street name ends (before next number or special keyword)
            street_end = len(street_parts)
            for idx, part in enumerate(street_parts):
                if re.match(r'^\d+', part) and idx > 0:  # Another number (not first word after original number)
                    # Keep this as part of address (apartment info)
                    break
            
            street = ' '.join(street_parts[:street_end])
            extra = ' '.join(street_parts[street_end:]) if street_end < len(street_parts) else ''
            
            if extra:
                result['address'] = f"{street} {number} {extra}".strip()
            else:
                result['address'] = f"{street} {number}"
        else:
            # Address doesn't start with number, use as-is
            result['address'] = full_address_raw
    else:
        result['address'] = full_address_raw
    
    # 5. Phone (required): After address, stop at newline to prevent capturing next line
    # Normalize: add +49 if missing, remove leading 0
    phone_match = re.search(r'📞?\s*(\+?\d[\d\s-]{9,20})(?=\s*\n|$)', ocr_text)
    if not phone_match:
        raise ParseError(detect_collapse_error(ocr_text))
    
    phone = phone_match.group(1).replace(' ', '').replace('-', '').strip()
    
    # Normalize phone: add +49 if missing, remove leading 0
    if not phone.startswith('+'):
        if phone.startswith('0'):
            phone = '+49' + phone[1:]  # Remove 0, add +49
        else:
            phone = '+49' + phone  # Add +49
    
    if len(phone) < 7:
        raise ParseError(detect_collapse_error(ocr_text))
    result['phone'] = phone
    
    # 6. Product count (required): Extract from "X Artikel"
    artikel_match = re.search(r'(\d+)\s*Artike?l?', ocr_text, re.IGNORECASE)
    if not artikel_match:
        raise ParseError(detect_collapse_error(ocr_text))
    result['product_count'] = int(artikel_match.group(1))
    
    # 7. Scheduled Time: Check for "Geplant" indicator
    # Pattern: "17:40\nGeplant" → extract "17:40"
    geplant_match = re.search(r'(\d{1,2}):(\d{2})\s*\n\s*Geplant', ocr_text, re.IGNORECASE)
    
    if geplant_match:
        hour = int(geplant_match.group(1))
        minute = int(geplant_match.group(2))
        if hour > 23 or minute > 59:
            raise ParseError(detect_collapse_error(ocr_text))
        result['time'] = f"{hour:02d}:{minute:02d}"
    else:
        result['time'] = 'asap'
    
    # 8. Total (required): Format "XX,XX €"
    total_match = re.search(r'(\d+,\d{2})\s*€', ocr_text)
    if not total_match:
        raise ParseError(detect_collapse_error(ocr_text))
    result['total'] = float(total_match.group(1).replace(',', '.'))
    
    # 9. Note (optional): Extract if bicycle emoji present and expanded
    has_note_indicator = bool(re.search(r'[🚚🚴]', ocr_text))
    
    if has_note_indicator:
        # Check if collapsed (arrow symbol present)
        is_collapsed = bool(re.search(r'[▸▼▽]', ocr_text))
        if is_collapsed:
            raise ParseError(detect_collapse_note(ocr_text))
        
        # Extract note from quotes
        note_match = re.search(r'[""\'\u201c\u201d]([^""\'\u201c\u201d\n]{5,})[""\'\u201c\u201d]', ocr_text)
        result['note'] = note_match.group(1).strip() if note_match else None
    else:
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
    has_collapsed_arrow = bool(re.search(r'[▼▽]', ocr_text))
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

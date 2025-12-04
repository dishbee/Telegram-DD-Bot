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
        dict with keys: order_num, customer, phone, address, zip, time, total, note
        
    Raises:
        ParseError: If any required field is missing
    """
    result = {}
    
    # 1. Order # (required): #ABC XYZ format
    # Extract last 2 chars from XYZ group for display
    # Example: "#VCJ 34V" → order_num="4V"
    # Example: "#4T6 M46" → order_num="46"
    # OCR may misread # as * or missing space
    order_match = re.search(r'[#*]\s*([A-Z0-9]{3})\s+([A-Z0-9]{3})', ocr_text, re.IGNORECASE)
    if not order_match:
        raise ParseError(detect_collapse_error(ocr_text))
    
    full_code = order_match.group(2).upper()  # e.g., "34V"
    result['order_num'] = full_code[-2:]  # Last 2 chars: "4V"
    
    # 2. ZIP (required): 5 digits (Passau = 940XX)
    zip_match = re.search(r'\b(940\d{2})\b', ocr_text)
    if not zip_match:
        raise ParseError(detect_collapse_error(ocr_text))
    result['zip'] = zip_match.group(1)
    
    # 3. Address: Prioritize 2nd occurrence (below customer name), fallback to 1st
    # Pattern: Street name/number before ZIP
    # Strategy: 2nd occurrence is more reliable (not wrapped), 1st may be truncated at top
    
    # Try to find address AFTER order code area (more reliable)
    # Look for pattern with street before ZIP
    address_matches = list(re.finditer(r'([^\n]+?)\s*\n\s*940\d{2}', ocr_text))
    
    if len(address_matches) >= 2:
        # Use 2nd occurrence (below customer name, not wrapped)
        candidate_address = address_matches[1].group(1).strip()
    elif len(address_matches) == 1:
        # Fallback to 1st occurrence
        candidate_address = address_matches[0].group(1).strip()
    else:
        raise ParseError(detect_collapse_error(ocr_text))
    
    # 4. Customer Name: Find name near order code
    # Pattern: After order code, before address/zip area
    # Example: "#VCJ 34V\n\nA. Hasan\n"
    order_end = order_match.end()
    text_after_order = ocr_text[order_end:order_end+200]  # Look in next 200 chars
    
    # Find first meaningful line (not empty, not number-only)
    name_match = re.search(r'\n\s*([A-ZÄÖÜa-zäöüß][^\n]{1,40}?)\s*\n', text_after_order)
    if not name_match:
        raise ParseError(detect_collapse_error(ocr_text))
    
    candidate_name = name_match.group(1).strip()
    result['customer'] = candidate_name
    
    # 5. Address validation: Not just a number
    if re.match(r'^\d+$', candidate_address):
        raise ParseError(detect_collapse_error(ocr_text))
    
    address = candidate_address
    
    # FIX: Replace capital I with 1 when it appears as building number (OCR error)
    # Pattern: "Straße I/" or "Straße I," or "Straße I " → "Straße 1/"
    address = re.sub(r'(\s)I([/,\s])', r'\g<1>1\g<2>', address)
    
    # Remove trailing comma
    address = address.rstrip(',').strip()
    
    # Reformat address: "50 Lederergasse" → "Lederergasse 50"
    # Pattern: "Number Street" at start of address
    address_reformat = re.match(r'^(\d+[a-z]?)\s+(.+)$', address, re.IGNORECASE)
    if address_reformat:
        number = address_reformat.group(1)
        street = address_reformat.group(2)
        address = f"{street} {number}"
    
    result['address'] = address
    
    # 6. Phone (required): After 📞 emoji (if present) or standalone phone number line
    # OCR may not capture emoji, so try multiple patterns
    # Pattern 1: With optional emoji + continuous digits (minimum 10 to avoid ZIP codes)
    phone_match = re.search(r'📞?\s*(\+?\d{10,20})', ocr_text)
    # Pattern 2: If not found, try with spaces between digits
    if not phone_match:
        phone_match = re.search(r'📞?\s*(\+?[\d\s]{10,25})', ocr_text)
    
    if not phone_match:
        raise ParseError(detect_collapse_error(ocr_text))
    
    phone = phone_match.group(1).replace(' ', '').replace('\n', '').replace('\t', '')
    if len(phone) < 7 or len(phone) > 20:
        raise ParseError(f"Invalid phone number length: {len(phone)}")
    result['phone'] = phone
    
    # 7. Product count (required): Extract from "X Artikel"
    # Example: "6 Artikel" → 6
    # OCR may misread as "Artike" or "Artikei"
    artikel_match = re.search(r'(\d+)\s*Artike?l?', ocr_text, re.IGNORECASE)
    if not artikel_match:
        raise ParseError(detect_collapse_error(ocr_text))
    result['product_count'] = int(artikel_match.group(1))
    
    # 8. Time: Check for "Geplant" indicator (scheduled order)
    # New PF Lieferando UI shows scheduled time with "Geplant" below it
    # Example: "17:40\nGeplant" → extract "17:40" as scheduled time
    # If no "Geplant" found → ASAP order (default)
    geplant_match = re.search(r'(\d{1,2}):(\d{2})\s*\n\s*Geplant', ocr_text, re.IGNORECASE)
    
    if geplant_match:
        hour = int(geplant_match.group(1))
        minute = int(geplant_match.group(2))
        if hour > 23 or minute > 59:
            raise ParseError(detect_collapse_error(ocr_text))
        result['time'] = f"{hour:02d}:{minute:02d}"
    else:
        # No "Geplant" indicator → ASAP order
        result['time'] = 'asap'
    
    # 9. Total (required): Format "XX,XX €"
    # May appear with Artikel count on same line or separate
    total_match = re.search(r'(\d+,\d{2})\s*€', ocr_text)
    
    if not total_match:
        raise ParseError(detect_collapse_error(ocr_text))
    total_str = total_match.group(1).replace(',', '.')
    result['total'] = float(total_str)
    
    # 10. Note (optional): Check if note exists and is expanded
    # Note indicated by bicycle emoji 🚚 or delivery icon 🚴
    has_note_indicator = bool(re.search(r'[🚚🚴]', ocr_text))
    
    if has_note_indicator:
        # Check if note is collapsed (arrow down symbol ▼ or ▽ present)
        is_collapsed = bool(re.search(r'[▼▽]', ocr_text))
        if is_collapsed:
            raise ParseError(detect_collapse_note(ocr_text))
        
        # Note is expanded - extract it
        note_match = re.search(r'["""""']([^"""""'\n]{5,})["""""']', ocr_text)
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

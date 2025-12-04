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
    
    # 1. Order # (required): #ABC XYZ format (3 letters, space, 3 chars)
    # Extract last 3 chars (XYZ) as order code, display last 2
    # Example: "#VXD G3B" → order_num="G3B", display="3B"
    # OCR may misread # as * or missing space
    order_match = re.search(r'[#*]\s*([A-Z]{3})\s+([A-Z0-9]{3})', ocr_text, re.IGNORECASE)
    if not order_match:
        raise ParseError("Order number not found")
    result['order_num'] = order_match.group(2).upper()  # Last 3 chars (G3B)
    
    # 2. ZIP (required): 5 digits (Passau = 940XX)
    zip_match = re.search(r'\b(940\d{2})\b', ocr_text)
    if not zip_match:
        raise ParseError("ZIP code not found")
    result['zip'] = zip_match.group(1)
    
    # 3. Customer (required): Line after order # line
    # Skip UI text like "x", "Drucken", "Details ausblenden"
    # Pattern: Find first proper name (at least 2 words starting with capitals)
    # New format: #ABC XYZ (e.g., #VXD G3B)
    order_line_end = re.search(r'#\s*([A-Z]{3})\s+([A-Z0-9]{3})\s*[^\n]*', ocr_text, re.IGNORECASE)
    if not order_line_end:
        raise ParseError("Order line not found for customer extraction")
    
    # Search text after order line but BEFORE "Tel" or "Bestellinf" for customer name
    # This prevents matching product names like "Ix Hot Cheese"
    text_after_order = ocr_text[order_line_end.end():]
    # Limit search to text before "Tel" or "Bestellinf"
    tel_match = re.search(r'\bTel\b', text_after_order, re.IGNORECASE)
    bestellung_match = re.search(r'\bBestellinf', text_after_order, re.IGNORECASE)
    search_end = min(tel_match.start() if tel_match else len(text_after_order),
                     bestellung_match.start() if bestellung_match else len(text_after_order))
    customer_search_text = text_after_order[:search_end]
    
    # Find first line with proper German name (2+ words, case-insensitive)
    # Handles: "Max Müller", "david stowasser", "Anna-Maria Schmidt", "S G", "ANNA MUELLER"
    # EXCLUDE: German articles and common words that are not names
    # Examples: "Am Fernsehturm", "Im Stadtpark", "Der Kunde", "Die Straße"
    EXCLUDE_ARTICLES = r'\b(am|im|der|die|das|zum|zur|von|beim|an|in|auf|mit|für|über|unter|hinter|vor|neben|zwischen)\b'
    
    # Find first line with proper German name (2+ words, case-insensitive)
    # Allow 0+ lowercase chars to handle initials ("S G") and all-caps ("JOHN DOE")
    # EXCLUDE street patterns (word + number like "Innstraße 79a")
    customer_match = re.search(
        r'\n\s*([A-ZÄÖÜa-zäöüß][a-zäöüß\-]*(?:[ \t]+[A-ZÄÖÜa-zäöüß][a-zäöüß\-]*)+)',
        customer_search_text,
        re.IGNORECASE
    )
    
    # Filter out street patterns (contains digits) and German articles
    if customer_match:
        candidate_name = customer_match.group(1).strip()
        # Check for digits or German articles
        has_digits = bool(re.search(r'\d', candidate_name))
        has_article = bool(re.search(EXCLUDE_ARTICLES, candidate_name, re.IGNORECASE))
        if has_digits or has_article:
            customer_match = None
    
    # Fallback: Accept single word names (3+ chars, case-insensitive)
    if not customer_match:
        customer_match = re.search(r'\n\s*([A-ZÄÖÜa-zäöüß][a-zäöüß]{2,})', customer_search_text, re.IGNORECASE)
    
    if not customer_match:
        raise ParseError("Customer name not found")
    result['customer'] = customer_match.group(1).strip()
    
    # 4. Address (required): Line with street name/number before ZIP
    # Pattern: "Street Name Number, \n ZIP City"
    address_match = re.search(
        r'([^\n]+)\s*,?\s*\n\s*940\d{2}',
        ocr_text
    )
    if not address_match:
        raise ParseError("Address not found")
    address = address_match.group(1).strip()
    # Remove customer name if it leaked into address
    if result['customer'] in address:
        address = address.replace(result['customer'], '').strip()
    
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
    
    # 5. Phone (required): After 📞 emoji (if present) or standalone phone number line
    # OCR may not capture emoji, so try multiple patterns
    # Pattern 1: With optional emoji + continuous digits (minimum 10 to avoid ZIP codes)
    phone_match = re.search(r'📞?\s*(\+?\d{10,20})', ocr_text)
    # Pattern 2: If not found, try with spaces between digits
    if not phone_match:
        phone_match = re.search(r'📞?\s*(\+?[\d\s]{10,25})', ocr_text)
    
    if not phone_match:
        raise ParseError("Phone number not found")
    
    phone = phone_match.group(1).replace(' ', '').replace('\n', '').replace('\t', '')
    if len(phone) < 7 or len(phone) > 20:
        raise ParseError(f"Invalid phone number length: {len(phone)}")
    result['phone'] = phone
    
    # 6. Time: Default to ASAP (scheduled orders will be handled later)
    result['time'] = 'asap'
    
    # 7. Total (required): Format "XX,XX €" (may have "Y Artikel" on same or different line)
    # Pattern 1: "XX,XX € Y Artikel" on same line
    total_match = re.search(r'(\d+,\d{2})\s*€\s*\d+\s*Artikel', ocr_text, re.IGNORECASE)
    # Pattern 2: Just "XX,XX €" (Artikel count elsewhere)
    if not total_match:
        total_match = re.search(r'(\d+,\d{2})\s*€', ocr_text)
    
    if not total_match:
        raise ParseError("Total price not found")
    total_str = total_match.group(1).replace(',', '.')
    result['total'] = float(total_str)
    
    # 8. Note (optional): Text in quotes (Lieferando customer note)
    # May have prefix like "A " before quote
    note_match = re.search(r'[A-Z]?\s*["""""]([^"""""\n]{5,})["""""]', ocr_text)
    if note_match:
        result['note'] = note_match.group(1).strip()
    else:
        result['note'] = None
    
    return result

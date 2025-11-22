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
                    'scale': True
                },
                timeout=30
            )
        
        # Check HTTP status first
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
    
    # 1. Order # (required): #XXXXXX or # XXXXXX (6 alphanumeric chars)
    # OCR may misread # as * or other symbols
    order_match = re.search(r'[#*]\s*([A-Z0-9]{6})', ocr_text, re.IGNORECASE)
    if not order_match:
        raise ParseError("Order number not found")
    result['order_num'] = order_match.group(1).upper()
    
    # 2. ZIP (required): 5 digits (Passau = 940XX)
    zip_match = re.search(r'\b(940\d{2})\b', ocr_text)
    if not zip_match:
        raise ParseError("ZIP code not found")
    result['zip'] = zip_match.group(1)
    
    # 3. Customer (required): Line after order # line
    # Skip UI text like "x", "Drucken", "Details ausblenden"
    # Pattern: Find first proper name (at least 2 words starting with capitals)
    order_line_end = re.search(r'#\s*[A-Z0-9]{6}\s+[^\n]*', ocr_text, re.IGNORECASE)
    if not order_line_end:
        raise ParseError("Order line not found for customer extraction")
    
    # Search text after order line for customer name
    text_after_order = ocr_text[order_line_end.end():]
    # Find first line with proper German name (capitalized, 2+ words)
    # Handles: "Max Müller", "Anna-Maria Schmidt", "Jean-Claude König" (on same line only)
    customer_match = re.search(
        r'\n\s*([A-ZÄÖÜ][a-zäöüß\-]+(?:[ \t]+[A-ZÄÖÜ][a-zäöüß\-]+)+)',
        text_after_order
    )
    # Fallback: Accept single word names (3+ chars, capitalized)
    if not customer_match:
        customer_match = re.search(r'\n\s*([A-ZÄÖÜ][a-zäöüß]{2,})', text_after_order)
    
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
    # Remove trailing comma
    address = address.rstrip(',').strip()
    result['address'] = address
    
    # 5. Phone (required): After "Tel" (may or may not have space)
    phone_match = re.search(r'Tel\s*(\+?[\d\s]{7,20})', ocr_text, re.IGNORECASE)
    if not phone_match:
        raise ParseError("Phone number not found")
    phone = phone_match.group(1).replace(' ', '').replace('\n', '')
    if len(phone) < 7 or len(phone) > 20:
        raise ParseError(f"Invalid phone number length: {len(phone)}")
    result['phone'] = phone
    
    # 6. Time (required): Either "ASAP" or actual time near "Lieferzeit"
    asap_match = re.search(r'\bASAP\b', ocr_text, re.IGNORECASE)
    # Time pattern: "Lieferzeit \n 10 MIN \n HH:MM" (skip the duration line)
    time_match = re.search(r'Lieferzeit.*?(\d{1,2}):(\d{2})', ocr_text, re.IGNORECASE | re.DOTALL)
    
    if asap_match:
        result['time'] = 'asap'
    elif time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        if hour > 23 or minute > 59:
            raise ParseError(f"Invalid time: {hour}:{minute}")
        result['time'] = f"{hour:02d}:{minute:02d}"
    else:
        raise ParseError("Delivery time not found (neither ASAP nor Lieferzeit)")
    
    # 7. Total (required): Line with "Total" followed by amount
    # Currency symbol may be misread (€ as c, e, etc.) or missing
    # CRITICAL: Must match "Total" keyword to avoid matching Stempelkarte or other amounts
    # Use word boundary to exclude "Subtotal"
    
    # Pattern 1: "Total" followed by spaces/tabs and amount on same line
    total_match = re.search(r'\bTotal\s*[\s\t]*(\d+[,\.]\d{2})', ocr_text, re.IGNORECASE)
    
    # Fallback 1: "Total" on one line, amount on next line
    if not total_match:
        total_match = re.search(r'\bTotal\s*\n\s*(\d+[,\.]\d{2})', ocr_text, re.IGNORECASE)
    
    # Fallback 2: "Total" with currency symbol explicitly
    if not total_match:
        total_match = re.search(r'\bTotal[^\d]*(\d+[,\.]\d{2})\s*[€ecC]', ocr_text, re.IGNORECASE)
    
    # Fallback 3: Find all amounts after "Total" keyword and take the first one
    if not total_match:
        # Find "Total" position first
        total_pos = re.search(r'\bTotal\b', ocr_text, re.IGNORECASE)
        if total_pos:
            # Look for amount within 100 chars after "Total"
            text_after_total = ocr_text[total_pos.end():total_pos.end()+100]
            amount_match = re.search(r'(\d+[,\.]\d{2})', text_after_total)
            if amount_match:
                total_match = amount_match
    
    if not total_match:
        raise ParseError("Total price not found")
    total_str = total_match.group(1).replace(',', '.')
    result['total'] = float(total_str)
    
    # 8. Note (optional): Text in quotes (Lieferando customer note)
    note_match = re.search(r'[""""]([^""""\n]{5,})[""""]', ocr_text)
    if note_match:
        result['note'] = note_match.group(1).strip()
    else:
        result['note'] = None
    
    return result

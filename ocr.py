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
        
        result = response.json()
        
        if not result.get('IsErroredOnProcessing'):
            text = result['ParsedResults'][0]['ParsedText']
        else:
            raise ParseError(f"OCR API error: {result.get('ErrorMessage', 'Unknown error')}")
        
        # Log raw output for debugging
        logger.info(f"[OCR] Raw text extracted from {photo_path}:")
        logger.info(f"[OCR] FULL TEXT:\n{text}")
        logger.info(f"[OCR] Total length: {len(text)} characters")
        
        return text
        
    except Exception as e:
        raise ParseError(f"Failed to extract text from image: {str(e)}")

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
    order_match = re.search(r'#\s*([A-Z0-9]{6})', ocr_text, re.IGNORECASE)
    if not order_match:
        raise ParseError("Order number not found")
    result['order_num'] = order_match.group(1).upper()
    
    # 2. ZIP (required): 5 digits (Passau = 940XX)
    zip_match = re.search(r'\b(940\d{2})\b', ocr_text)
    if not zip_match:
        raise ParseError("ZIP code not found")
    result['zip'] = zip_match.group(1)
    
    # 3. Customer (required): Line after order # line
    # Pattern: "#XXXXXX Lieferung ... \n Customer Name"
    customer_match = re.search(
        r'#\s*[A-Z0-9]{6}\s+[^\n]*\n\s*([^\n]+)',
        ocr_text,
        re.IGNORECASE
    )
    if not customer_match:
        raise ParseError("Customer name not found")
    result['customer'] = customer_match.group(1).strip()
    
    # 4. Address (required): Line with street name/number before ZIP
    # Pattern: "Street Name Number, \n ZIP City"
    address_match = re.search(
        r'([^\n]+?)\s*,?\s*\n\s*940\d{2}',
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
    # Time shown at bottom: "Lieferzeit \n HH:MM"
    time_match = re.search(r'Lieferzeit[^\d]*(\d{1,2}):(\d{2})', ocr_text, re.IGNORECASE)
    
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
    # Must be at end of line to avoid partial matches like "Subtotal"
    total_match = re.search(r'Total\s+(\d+[,\.]\d{2})\s*€?\s*$', ocr_text, re.IGNORECASE | re.MULTILINE)
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

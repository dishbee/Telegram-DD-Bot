"""
Test script for OCR module
Usage: python test_ocr.py <path_to_photo>
"""

import sys
from ocr import extract_text_from_image, parse_pf_order, ParseError

def test_ocr(photo_path: str):
    print(f"Testing OCR on: {photo_path}\n")
    print("="*60)
    
    try:
        # Step 1: Extract text
        print("[1/2] Running OCR extraction...")
        ocr_text = extract_text_from_image(photo_path)
        print(f"\n✅ OCR Complete. Extracted {len(ocr_text)} characters\n")
        print("="*60)
        print("RAW OCR TEXT:")
        print("="*60)
        print(ocr_text)
        print("="*60)
        
        # Step 2: Parse fields
        print("\n[2/2] Parsing order fields...")
        parsed = parse_pf_order(ocr_text)
        print("\n✅ Parsing Complete\n")
        print("="*60)
        print("PARSED FIELDS:")
        print("="*60)
        for key, value in parsed.items():
            print(f"{key:15s}: {value}")
        print("="*60)
        
    except ParseError as e:
        print(f"\n❌ Parse Error: {e}")
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_ocr.py <path_to_photo>")
        sys.exit(1)
    
    test_ocr(sys.argv[1])

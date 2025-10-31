# 📸 OCR Implementation Plan for Pommes Freunde Orders

## 🔍 REVISED ANALYSIS: OCR for Pommes Freunde Orders

### ✅ What We're Actually Building

**Input**: Photo sent to **RG Pommes Freunde** chat  
**Output**: Standard MDG-ORD + RG-SUM messages (just like Shopify/Smoothr)  
**Purpose**: Dispatch orders to couriers (restaurant already has the info)

---

## 📸 What We Need to Parse (7 Fields Only)

From photos, clearly visible:

| Field | Example | Location | Difficulty |
|-------|---------|----------|-----------|
| **Order #** | `#MFQHVG` | Top left, bold | ✅ Easy (regex) |
| **Customer** | `Amelie Jürgens` | Below order #, bold | ✅ Easy (consistent position) |
| **Address** | `Schustergasse 2` | Multi-line below name | ⚠️ Moderate (street + number only) |
| **Phone** | `015164741555` | `Tel` prefix | ✅ Easy (regex) |
| **ASAP/Time** | `ASAP` or `Lieferzeit 17:40` | Top right OR bottom | ✅ Easy (look for both) |
| **Note** | Yellow box text | Variable position | ⚠️ Moderate (icon + yellow bg) |
| **ZIP** | `94032` | In address | ✅ Easy (5 digits) |

**NOT parsing**: Products, prices, modifiers, subtotals → **Huge simplification!**

---

## 🎯 Expected Success Rate

| Field | Confidence | Why |
|-------|-----------|-----|
| Order # | 98% | Clear format, always same position |
| Customer | 95% | Bold text, consistent location |
| Phone | 98% | "Tel" prefix always present |
| Address | 90% | Street + number pattern reliable |
| ZIP | 95% | 5-digit validation easy |
| ASAP/Time | 95% | Either "ASAP" text or "Lieferzeit" label |
| Note | 75% | Yellow box sometimes faint/cropped |

**Overall**: ~90% success rate (vs 80% initially estimated)

---

## 🚫 Error Handling (Simplified)

**Retry Logic (2 attempts max):**
1. Photo arrives → OCR → Parse
2. If **any required field** fails → Reply to RG: *"Please send another clearer photo, we are not able to read and process it correctly."*
3. New photo arrives → OCR → Parse
4. Still fails → Send to MDG: *"Photo of the order sent to PF can't be processed correctly. Verify manually."*

**Required fields**: Order #, Customer, Phone, Address (street + number), ZIP, ASAP/Time  
**Optional field**: Note (if missing, just skip - don't fail)

---

## 💰 Render Cost Analysis

**Current Setup**: Free tier (512MB RAM, shared CPU)

**OCR Requirements**:
- Tesseract binary: ~15MB
- pytesseract + Pillow: ~10MB
- Per-request: ~50MB RAM, ~2-3s processing

**Daily Load**: 30 orders × 3s = 90 seconds/day processing  
**Peak**: Assume 10 orders/hour = 30 seconds/hour

**Verdict**: ✅ **Free tier is fine**
- Well within 512MB RAM limit
- No sustained load (cold starts acceptable)
- Only concern: First photo after 15min idle takes 30-40s (Render spin-up)

**If issues**: Upgrade to Starter ($7/mo) for always-on + 512MB dedicated RAM

---

## 📋 IMPLEMENTATION PLAN (Step-by-Step)

### **Phase 1: Environment Setup** (10 min)

**1.1 Add Dependencies**
```bash
# Add to requirements.txt
pytesseract==0.3.10
Pillow==10.4.0
```

**1.2 Configure Render Buildpack**
```bash
# Add to render.yaml (or dashboard Settings → Environment)
RUN apt-get update && apt-get install -y tesseract-ocr tesseract-ocr-deu
```

**1.3 Add ENV Variable**
```bash
PF_RG_CHAT_ID=-4955033989  # Pommes Freunde restaurant group
```

---

### **Phase 2: OCR Core Logic** (30 min)

**2.1 Create `ocr.py` module**
```python
def extract_text_from_image(photo_path: str) -> str:
    """Run Tesseract OCR on image, return raw text"""

def parse_pf_order(ocr_text: str) -> dict:
    """
    Parse 7 fields using regex:
    - Order # (6-char alphanumeric after #)
    - Customer (line after order #)
    - Phone (after "Tel")
    - Address (street + number before ZIP)
    - ZIP (5 digits)
    - ASAP/Time (either "ASAP" or "Lieferzeit HH:MM")
    - Note (optional, yellow box text)
    
    Returns dict or raises ParseError
    """
```

**2.2 Validation Rules**
- Order #: Must match `[A-Z0-9]{6}`
- Phone: Must be 7-15 digits
- Address: Must have street name + number
- ZIP: Must be exactly 5 digits
- Time: If not ASAP, must match `HH:MM` (validate hour 00-23)

---

### **Phase 3: Photo Handler** (20 min)

**3.1 Add Photo Detection in main.py**
```python
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = request.json
    message = update.get("message", {})
    
    # NEW: Detect photo in PF restaurant group
    if message.get("chat", {}).get("id") == int(os.getenv("PF_RG_CHAT_ID")):
        if message.get("photo"):
            run_async(handle_pf_photo(message))
            return jsonify({"status": "ok"})
```

**3.2 Implement `handle_pf_photo()`**
```python
async def handle_pf_photo(message: dict):
    """
    1. Download photo from Telegram
    2. Run OCR
    3. Parse fields
    4. Create STATE entry (vendor: "Pommes Freunde")
    5. Send MDG-ORD + RG-SUM
    6. Reply to photo with "✅ Order processed: #{order_num}"
    
    On failure:
    - Check retry count in message thread
    - If < 2: Reply "Please send another clearer photo..."
    - If >= 2: Send to MDG "Photo can't be processed..."
    """
```

---

### **Phase 4: Retry Tracking** (15 min)

**4.1 Track Retry Count**
```python
# Use message reply_to_message_id to track retries
# Store in temporary dict: {message_id: retry_count}
PF_PHOTO_RETRIES = {}  # Clear after 1 hour

def get_retry_count(message_id: int) -> int:
    """Check if this is a retry attempt"""
    # Look at reply chain, count previous failures
```

**4.2 Cleanup Old Retries**
```python
# Run every hour, remove entries > 1 hour old
def cleanup_old_retries():
    cutoff = datetime.now() - timedelta(hours=1)
    # Remove old entries
```

---

### **Phase 5: Integration** (15 min)

**5.1 STATE Creation**
```python
order_id = f"PF_{order_num}_{int(time.time())}"  # Unique ID
STATE[order_id] = {
    "name": f"PF #{order_num}",
    "order_type": "pf_photo",
    "vendors": ["Pommes Freunde"],
    "customer": {"name": customer, "phone": phone, "address": address, "zip": zip_code},
    "requested_time": parsed_time,  # "asap" or "14:30"
    "vendor_items": {"Pommes Freunde": []},  # Empty products
    "note": note,  # Optional
    # ... standard fields
}
```

**5.2 Message Building**
- Use existing `build_mdg_dispatch_text()` from mdg.py
- Use existing `build_vendor_summary_text()` from rg.py
- Add `order_source = "PF"` to STATE for icon/label

---

### **Phase 6: Testing** (20 min)

**6.1 Unit Tests** (Manual)
```python
# Test OCR with sample images
# Verify each regex pattern
# Test validation edge cases
```

**6.2 Integration Test**
1. Send test photo to PF RG
2. Verify MDG-ORD created
3. Verify RG-SUM shows in PF chat
4. Test time request flow (ASAP/TIME buttons)
5. Test assignment flow

**6.3 Failure Tests**
1. Send blurry photo → Verify retry message
2. Send 3 bad photos → Verify MDG alert
3. Send photo with missing field → Verify retry

---

## 🎯 DEPLOYMENT CHECKLIST

### Before Pushing to GitHub:

- [ ] requirements.txt updated (pytesseract, Pillow)
- [ ] `PF_RG_CHAT_ID` added to `.env` and Render dashboard
- [ ] Tesseract buildpack configured in Render
- [ ] `ocr.py` module complete with tests
- [ ] `handle_pf_photo()` implemented
- [ ] Retry logic tested locally
- [ ] Error messages verified

### After Deployment:

- [ ] Send test photo to PF RG
- [ ] Verify MDG-ORD appears correctly
- [ ] Test ASAP vs Vorbestellung detection
- [ ] Test note parsing (yellow box)
- [ ] Test retry flow (bad photo × 2)
- [ ] Verify cold start time acceptable (<40s)

---

## ⚠️ KNOWN LIMITATIONS

1. **Photo Quality**: Glare/tilt reduces accuracy (user must retake)
2. **Cold Starts**: First photo after 15min idle takes 30-40s
3. **No Product Info**: MDG-ORD shows `📦 0` (acceptable per requirement)
4. **Manual Fallback**: After 2 retries, requires manual MDG entry

---

## 📊 ESTIMATED TIMELINE

| Phase | Duration | Complexity |
|-------|----------|-----------|
| 1. Environment | 10 min | Low |
| 2. OCR Logic | 30 min | Medium |
| 3. Photo Handler | 20 min | Medium |
| 4. Retry Tracking | 15 min | Low |
| 5. Integration | 15 min | Low |
| 6. Testing | 20 min | Medium |
| **TOTAL** | **~2 hours** | - |

---

## ✅ KEY REQUIREMENTS

- ✅ Photos sent to PF RG only (not MDG)
- ✅ No product parsing needed
- ✅ 2 retry attempts before manual fallback
- ✅ Free Render tier sufficient (30 orders/day)
- ✅ ASAP clearly visible (text "ASAP" or "Vorbestellung")
- ✅ "Lieferzeit" label easy to detect (bottom of screen)
- ✅ No manual verification needed (auto-retry instead)
- ✅ Order format: Same as Smoothr Lieferando (6-char alphanumeric)

---

## 🔧 TECHNICAL NOTES

### Tesseract Configuration
```python
# Language: German + English
custom_config = r'--oem 3 --psm 6 -l deu+eng'

# PSM modes:
# 6 = Assume a single uniform block of text
# 3 = Fully automatic page segmentation (default)
```

### Image Preprocessing (Optional)
```python
from PIL import Image, ImageEnhance

def preprocess_image(image_path: str) -> str:
    """
    1. Convert to grayscale
    2. Increase contrast
    3. Resize if too small/large
    4. Save preprocessed version
    """
```

### Regex Patterns
```python
ORDER_PATTERN = r'#([A-Z0-9]{6})'
PHONE_PATTERN = r'Tel[:\s]+(\+?\d[\d\s]{7,15})'
ZIP_PATTERN = r'\b(94\d{3})\b'
TIME_PATTERN = r'Lieferzeit[:\s]+(\d{1,2}):(\d{2})'
ASAP_PATTERN = r'\bASAP\b'
```

---

**Status**: Ready for implementation  
**Priority**: Low (can be implemented later)  
**Dependencies**: pytesseract, Pillow, Tesseract OCR binary  
**Estimated Effort**: 2 hours implementation + 1 week testing with real orders

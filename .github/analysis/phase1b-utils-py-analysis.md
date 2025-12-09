# Phase 1B: utils.py Deep Analysis

**File**: utils.py  
**Total Lines**: 1,144
**Purpose**: Shared utilities, helpers, validators, async wrappers, parsers

---

## 📦 IMPORTS & CONFIGURATION

**External Libraries**:
- `hmac`, `hashlib`, `base64`: Webhook HMAC validation
- `asyncio`, `threading`: Async operations
- `telegram`: Telegram Bot API
- `requests`: HTTP calls (Google Maps API)

**Environment Variables** (lines 25-32):
```python
BOT_TOKEN
SHOPIFY_WEBHOOK_SECRET
DISPATCH_MAIN_CHAT_ID = -4825320632
VENDOR_GROUP_MAP = {...}
DRIVERS = {...}
COURIER_MAP = {...}  # Preferred over DRIVERS
GOOGLE_MAPS_API_KEY (optional)
```

**Restaurant Shortcuts** (lines 35-45):
```python
RESTAURANT_SHORTCUTS = {
    "Julis Spätzlerei": "JS", "Zweite Heimat": "ZH", "Hello Burrito": "HB",
    "Kahaani": "KA", "i Sapori della Toscana": "SA", "Leckerolls": "LR",
    "dean & david": "DD", "Pommes Freunde": "PF", "Wittelsbacher Apotheke": "AP",
    "Safi": "SF"
}
```

---

## 🔧 UTILITY FUNCTIONS (16 total)

### 1. Address & Location (line 54)

**`get_district_from_address(address: str) -> Optional[str]`**:
- **Purpose**: Get district/neighborhood from address
- **Method**: Google Maps Geocoding API
- **Caching**: In-memory `_DISTRICT_CACHE` dict
- **Returns**: District name ("Innstadt") or None
- **Usage**: Optional feature (requires API key)

### 2. Async Executor (line 151)

**`run_async(coro)`**:
- **Purpose**: Schedule async coroutine from sync context
- **Pattern**: Flask handlers call this to schedule Telegram API calls
- **Returns**: Future object
- **Critical**: All Telegram API calls go through this

### 3. Phone Validation (lines 155-187)

**`validate_phone(phone: str) -> Optional[str]`** (line 155):
- **Purpose**: Validate and clean phone number
- **Logic**:
  - Strip non-digits
  - Min 7 digits required
  - Returns cleaned number or None
- **Usage**: Called on customer phone from Shopify/Smoothr

**`format_phone_for_android(phone: str) -> str`** (line 172):
- **Purpose**: Format phone for Android "tel:" links
- **Logic**:
  - Adds `+` prefix if missing
  - Returns cleaned format
- **Usage**: UPC "Call Restaurant" buttons

### 4. Street Abbreviation (line 191)

**`abbreviate_street(street_name: str, max_length: int = 20) -> str`**:
- **Purpose**: Shorten long street names
- **Rules**:
  - "straße" → "str."
  - "platz" → "pl."
  - "gasse" → "g."
  - Truncate if still too long
- **Returns**: Abbreviated street name
- **Usage**: Compact address display in messages

### 5. Product Name Cleaning (line 300)

**`clean_product_name(name: str) -> str`**:
- **Purpose**: Simplify product names for display
- **Rules** (17 total):
  1. Burger prefixes: `[Bio-Burger "Classic"]` → `Classic`
  2. Fries simplification: `Bio-Pommes` → `Pommes`
  3. Chili-Cheese-Fries: → `Fries: Chili-Cheese-Style`
  4. Pizza prefixes: `Sauerteig-Pizza Margherita` → `Margherita`
  5. Spätzle: `Bergkäse-Spätzle` → `Bergkäse`
  6. Pasta prefixes: `Selbstgemachte Tagliatelle` → `Tagliatelle`
  7. Roll types: `Cinnamon roll - Classic` → `Classic`
  8. Price removal: `Product (+2.50€)` → `Product`
  9. "/ Standard" removal
  10-17. Additional burger/side cleaning logic

**Debug Logging** (lines 470, 472, 489, 491):
- `logger.debug("DEBUG Rule 3: Burger=... | Cleaning side...")` (lines 470, 472)
- `logger.debug("DEBUG Rule 3 (no separator): Burger=... | Side...")` (lines 489, 491)
- Changed to `logger.debug()` level (Phase 0 cleanup)

**Example Transformations**:
```python
"[Bio-Burger \"Classic\"] - Fries" → "Classic - Fries"
"Bio-Pommes (1.50€)" → "Pommes"
"Sauerteig-Pizza Margherita" → "Margherita"
"Bergkäse-Spätzle / Standard" → "Bergkäse"
"Chili-Cheese-Fries (+2.60€)" → "Fries: Chili-Cheese-Style"
```

### 6. Webhook Verification (line 572)

**`verify_webhook(raw: bytes, hmac_header: str) -> bool`**:
- **Purpose**: Validate Shopify webhook HMAC signature
- **Algorithm**: HMAC-SHA256
- **Secret**: `SHOPIFY_WEBHOOK_SECRET`
- **Returns**: True if valid, False otherwise
- **Security**: Prevents unauthorized webhook calls

### 7. Safe Telegram API Wrappers (lines 585-637)

**`async safe_send_message(...)`** (line 585):
- **Purpose**: Send Telegram message with retry logic
- **Retries**: 3 attempts with exponential backoff
- **Errors Handled**: Rate limits (429), timeouts, network errors
- **Returns**: Message object or None
- **Usage**: ALL message sends go through this

**`async safe_edit_message(...)`** (line 616):
- **Purpose**: Edit Telegram message with retry logic
- **Same retry pattern as send**
- **Catches**: "Message not modified" errors (safe to ignore)

**`async safe_delete_message(...)`** (line 630):
- **Purpose**: Delete Telegram message with error handling
- **Errors**: Logs but doesn't fail if message already gone

### 8. Status Line Builder (line 638)

**`build_status_lines(order, message_type, RESTAURANT_SHORTCUTS, COURIER_SHORTCUTS, vendor) -> str`**:
- **Purpose**: Build status history line for messages
- **Message Types**:
  - `"mdg"`: Main dispatch group format
  - `"rg"`: Restaurant group format
  - `"upc"`: User private chat format
- **Shows**:
  - ⏰ Time sent/confirmed
  - ✅ Assigned courier
  - 🚚 Delivered status
- **Format Examples**:
  ```
  ⏰ JS: 14:30 (sent) → 14:35 ✓
  ✅ Assigned: Bee 1
  🚚 Delivered: 15:20
  ```

**Status History Types**:
- `time_sent`: Time request sent to vendor
- `time_confirmed`: Vendor confirmed time
- `assignment`: Order assigned to courier
- `delivery`: Order delivered

### 9. Temporary Message Helper (line 789)

**`async send_status_message(chat_id, text, auto_delete_after=20)`**:
- **Purpose**: Send temporary status message
- **Auto-delete**: Default 20 seconds
- **Usage**: Confirmations, errors, temporary notices
- **Returns**: Message object

### 10. Error Description (line 811)

**`get_error_description(error: Exception) -> str`**:
- **Purpose**: Human-readable error messages
- **Maps**:
  - `TimedOut` → "Request timed out"
  - `NetworkError` → "Network connection error"
  - `TelegramError` → Extracts API error message
  - Generic → Exception string
- **Usage**: Error logging and user messages

---

## 📊 SMOOTHR PARSING (lines 875-1144)

### 11. Smoothr Detection (line 875)

**`is_smoothr_order(text: str) -> bool`**:
- **Purpose**: Detect if text is a Smoothr order
- **Checks**:
  - Contains "Order Number:" or "Order Confirmation"
  - Contains "Customer:" and "Phone:"
  - Contains "Items:" or "Order Type:"
- **Returns**: True if Smoothr order
- **Usage**: Channel post detection

### 12. Order Type Detection (line 901)

**`get_smoothr_order_type(order_code: str) -> tuple[str, str]`**:
- **Purpose**: Determine Smoothr platform and vendor
- **Patterns**:
  - `UB-XXXX-XXXX`: Uber Eats
  - `GO-XXXX-XXXX`: getfaster.io
  - `DD-XXXX-XXXX`: dean & david
  - `PF-XXXX-XXXX`: Pommes Freunde
- **Returns**: `(order_type, vendor_name)`
- **Examples**:
  ```python
  "UB-1234-5678" → ("smoothr", "Uber Eats")
  "DD-1234-5678" → ("smoothr_dd", "dean & david")
  "PF-1234-5678" → ("smoothr_lieferando", "Pommes Freunde")
  ```

### 13. Smoothr Parser (line 934)

**`parse_smoothr_order(text: str) -> dict`**:
- **Purpose**: Parse Smoothr plain text order to STATE-compatible dict
- **Extracts**:
  - Order code/number
  - Customer name, phone, email
  - Address (street, zip, full)
  - Products list
  - Delivery time (ASAP or scheduled)
  - Note, tip, payment method
  - Total amount
- **Returns**: Dict with same structure as Shopify orders
- **Validation**: Checks required fields (order_code, customer_name, phone)

**Parsing Logic**:
```
1. Extract order number: "Order Number: UB-1234-5678"
2. Extract customer info block
3. Extract address block (multi-line)
4. Extract products: "- 2x Product Name"
5. Extract delivery time
6. Extract note/tip/payment
7. Build STATE-compatible structure
```

**Output Structure**:
```python
{
    "order_id": "UB-1234-5678",
    "order_num": "1234",
    "order_type": "smoothr",
    "customer": {
        "name": "John Doe",
        "phone": "+491234567890",
        "email": "john@example.com",
        "address": "Street 123",
        "zip": "94032",
        "original_address": "Street 123, 94032 Passau"
    },
    "is_asap": True,
    "requested_delivery_time": None,
    "order_datetime": "2024-12-06T14:30:00",
    "products": [
        {"name": "Product A", "quantity": 2},
        {"name": "Product B", "quantity": 1}
    ],
    "note": "Please ring doorbell",
    "tip": "2.50€",
    "payment_method": "Credit Card",
    "delivery_fee": "3.00€",
    "total": "25.50€",
    "smoothr_raw": "[original text]"
}
```

---

## 🔐 OCR PARSER (lines 950-1144)

**`parse_pf_lieferando_ocr(text: str) -> dict`** (implied from structure):
- **Purpose**: Parse Pommes Freunde Lieferando OCR text
- **Input**: Raw OCR text from photo
- **Extracts**:
  - Order number
  - Customer name
  - Address (multi-line)
  - Phone
  - Products (line items with quantities)
  - Total payment
- **Debug Logging**:
  - Line 965: `logger.debug(f"DEBUG PARSER - Total lines found: {len(lines)}")`
  - Line 1046: `logger.debug(f"DEBUG PARSER - Found Total Payment line: '{line}'")`
  - Line 1052: `logger.debug(f"DEBUG PARSER - Extracted total: {order_data['total']}")`
  - Changed to `logger.debug()` level (Phase 0 cleanup)

**OCR Text Pattern**:
```
Order Number: #12345
Customer Name
Customer Address Line 1
Customer Address Line 2
Passau 94032
- Product Name
  Quantity: 2
  Price: 10.00 €
- Total Payment: 25.00 €
```

**Parsing Steps**:
1. Split by newlines
2. Log total line count (debug level)
3. Iterate lines looking for patterns
4. Extract order number (# or "Order")
5. Extract customer name (after "Customer:")
6. Extract address block (multi-line until products)
7. Extract phone (regex: digits only, 7+ length)
8. Extract products (lines starting with "-")
9. Extract total (regex: `\d+\.\d+`)
10. Log found total (debug level)

---

## 📈 CONSTANTS & MAPPINGS

**Restaurant Shortcuts** (line 35):
- 10 restaurants mapped to 2-letter codes
- Used across MDG, RG, UPC messages
- Synced with `main.py` local definition

**Courier Map** (line 32):
- User IDs for all couriers
- Used for assignment buttons
- Fallback if MDG admin query fails

**Vendor Group Map** (line 30):
- Chat IDs for each restaurant group
- 10 restaurants currently configured
- Used for message routing

---

## 🎨 MESSAGE FORMATTING HELPERS

**Status Line Builder** (line 638):
- Centralizes status history formatting
- Supports 3 message types (MDG, RG, UPC)
- Handles restaurant shortcuts
- Shows courier names
- Displays timestamps

**Phone Formatter** (line 172):
- Android-compatible tel: links
- Adds `+` prefix automatically
- Used in "Call Restaurant" buttons

**Street Abbreviator** (line 191):
- Compact address display
- German-specific abbreviations
- Max length enforcement

---

## 🚨 CRITICAL PATTERNS

### 1. Async Wrappers Pattern
All Telegram API calls MUST use safe wrappers:
```python
await safe_send_message(chat_id, text, reply_markup)  # ✅ Correct
await bot.send_message(chat_id, text)  # ❌ Wrong - no retry
```

### 2. Product Name Cleaning
Applied at ORDER CREATION (Shopify/Smoothr webhooks):
```python
clean_product_name(raw_product_name)  # Called during parsing
# NOT called when displaying - names already clean in STATE
```

### 3. Phone Validation
Three-step fallback in Shopify orders:
```python
customer.phone → billing_address.phone → shipping_address.phone
```

### 4. HMAC Validation
**CRITICAL**: All Shopify webhooks must pass HMAC check:
```python
if not verify_webhook(request.data, request.headers.get("X-Shopify-Hmac-Sha256")):
    return "Unauthorized", 401
```

### 5. Status History Structure
Consistent format across all modules:
```python
{
    "type": "time_sent|time_confirmed|assignment|delivery",
    "time": "14:30",
    "vendor": "Restaurant Name",  # Optional
    "courier": "Bee 1",  # Optional
    "timestamp": datetime_obj
}
```

---

## 📊 FUNCTION USAGE MAP

**Called From main.py**:
- `verify_webhook()`: Shopify webhook validation
- `validate_phone()`: Order processing (Shopify/Smoothr)
- `format_phone_for_android()`: UPC button generation
- `clean_product_name()`: Order processing (Shopify/Smoothr/PF)
- `safe_send_message()`: ALL message sends (via run_async)
- `safe_edit_message()`: ALL message edits
- `safe_delete_message()`: Message cleanup
- `send_status_message()`: Temporary notifications
- `build_status_lines()`: Status updates (MDG/RG/UPC)
- `is_smoothr_order()`: Channel post detection
- `get_smoothr_order_type()`: Order type routing
- `parse_smoothr_order()`: Smoothr webhook processing

**Called From mdg.py**:
- `build_status_lines()`: MDG status line updates
- `clean_product_name()`: (if needed during display - usually pre-cleaned)

**Called From rg.py**:
- `build_status_lines()`: RG status line updates
- `format_phone_for_android()`: Phone display formatting

**Called From upc.py**:
- `build_status_lines()`: UPC status line updates
- `format_phone_for_android()`: Call button generation
- `send_status_message()`: UPC temporary messages

---

## 🔄 DATA FLOW

**Order Creation Flow**:
```
1. Webhook arrives → verify_webhook()
2. Extract customer → validate_phone()
3. Extract products → clean_product_name() for each
4. Build STATE dict
5. Send to MDG → safe_send_message()
6. Send to RG → safe_send_message()
```

**Status Update Flow**:
```
1. Vendor confirms time
2. Build status line → build_status_lines()
3. Edit MDG message → safe_edit_message()
4. Edit RG message → safe_edit_message()
```

**Smoothr Order Flow**:
```
1. Text arrives → is_smoothr_order()
2. Detect platform → get_smoothr_order_type()
3. Parse text → parse_smoothr_order()
4. Clean products → clean_product_name()
5. Validate phone → validate_phone()
6. Send to channels → safe_send_message()
```

---

## ✅ PHASE 1B COMPLETE

**Key Findings**:
- 16 utility functions (validation, formatting, parsing)
- 3 async wrappers with retry logic (send, edit, delete)
- 17 product cleaning rules
- Smoothr parser (3 functions)
- OCR parser (PF Lieferando)
- Status line builder (3 message types)
- Phone validation & formatting
- HMAC webhook verification

**Critical Utilities**:
- `safe_send_message()` / `safe_edit_message()` - ALL Telegram API calls
- `clean_product_name()` - Applied at order creation
- `build_status_lines()` - Centralized status formatting
- `verify_webhook()` - Security gate for Shopify

**Next**: Phase 1C - mdg.py analysis (~1,350 lines)

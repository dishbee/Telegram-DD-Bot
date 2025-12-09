# Phase 1D: rg.py Analysis

**File**: `rg.py`
**Total Lines**: 333
**Purpose**: Restaurant Group (RG) message builders, vendor keyboards, and RG-specific helpers

---

## File Overview

This module handles all RG-related functionality:
- Message text building (summary/details views)
- Vendor-specific keyboards (toggle, time request, response)
- Time picker keyboards (hour/minute selection)
- Format differentiation between Shopify and Smoothr orders

**Critical Pattern**: RG messages maintain workflow equality - after parsing, Shopify and Smoothr orders use identical message builders and keyboards.

---

## Imports & Configuration

### Standard Library (Lines 4-7)
```python
logging
datetime, timedelta
zoneinfo.ZoneInfo
typing (Any, Dict, List, Optional)
```

### Telegram Library (Line 9)
```python
InlineKeyboardButton, InlineKeyboardMarkup
```

### Project Modules (Line 11)
```python
from utils import format_phone_for_android
```

### Module-Level Constants (Lines 15-37)
- **TIMEZONE**: `ZoneInfo("Europe/Berlin")` - Passau timezone
- **RESTAURANT_SHORTCUTS**: Dict mapping full vendor names to 2-letter codes (10 restaurants)
- **SHORTCUT_TO_VENDOR**: Reverse mapping (shortcut → full name) for callback decoding

---

## Function Catalog (8 Functions)

### 1. `now()` - Line 18
**Purpose**: Get current time in Passau timezone (Europe/Berlin)

**Returns**: `datetime` object with timezone awareness

**Usage**: Called for timestamp generation in callback data, time calculations

---

### 2. `build_vendor_summary_text(order, vendor)` - Line 40
**Purpose**: Build vendor summary message (collapsed state - default view)

**Parameters**:
- `order`: Order dict from STATE
- `vendor`: Full vendor name (e.g., "Leckerolls")

**Shopify Format** (Collapsed):
```
[Status lines from build_status_lines()]
────────────────

🗺️ Street Name

2 x Product Name
1 x Another Product

❕ Note: {text} (optional)
```

**DD/PF Format** (Collapsed):
```
[Status lines from build_status_lines()]
────────────────

🗺️ Full Address
👤 Customer Name

2 x Product Name (if products exist)

❕ Note: {text} (optional)
```

**Key Differences**:
1. **Shopify**: Address shows street only (no customer name in collapsed view)
2. **DD/PF**: Address shows full address + customer name in collapsed view
3. **PF Lieferando**: NO product list shown (uses product count only, not item details)
4. **Blank line management**: Status ends with 2 newlines → remove 1 for proper separator spacing

**Logic Flow**:
1. Get order_type ("shopify", "smoothr_dnd", "smoothr_lieferando")
2. Call `build_status_lines()` from utils.py with message_type="rg"
3. Adjust status text newlines (remove 1 of 2 trailing newlines)
4. Add separator: "────────────────" with blank line
5. Shopify: Add street only
6. DD/PF: Add full address + customer name
7. Get vendor_items for this vendor
8. If items exist AND not PF Lieferando: Show product list
9. If note exists: Add note line
10. Return status_text + message body

**Returns**: Formatted message string

**Usage**: Called from main.py webhook handlers and toggle callbacks

**Critical**: Line 88 checks `order_type != "smoothr_lieferando"` to skip product display for PF orders

---

### 3. `build_vendor_details_text(order, vendor)` - Line 106
**Purpose**: Build vendor details message (expanded state)

**Parameters**:
- `order`: Order dict from STATE
- `vendor`: Full vendor name

**Shopify Format** (Expanded):
```
[Status lines]
────────────────

🗺️ Street Name

2 x Product Name
1 x Another Product

❕ Note: {text}

👤 Customer Name
📞 +491234567890
⏰ Ordered at: 14:30
```

**DD/PF Format** (Expanded):
```
[Status lines]
────────────────

🗺️ Full Address
👤 Customer Name

2 x Product Name

❕ Note: {text}

📞 +491234567890
⏰ Ordered at: 14:30
```

**Key Differences from Summary**:
1. **Shopify expanded**: Now shows customer name, phone, ordered time (not in summary)
2. **DD/PF expanded**: Now shows phone and ordered time (customer already shown in summary)
3. **Blank line after note** (summary doesn't have this)
4. **All order types**: Show full product list (except PF Lieferando)

**Logic Flow**:
1. Same as summary for status/separator/address section
2. Add product list with blank line after
3. Add note with blank line after (if exists)
4. Shopify: Add customer name, phone, ordered time
5. DD/PF: Add phone, ordered time (customer already shown above)
6. Format phone via `format_phone_for_android()`
7. Extract order time from created_at (HH:MM format)
8. Return status_text + message body

**Returns**: Formatted message string

**Usage**: Called from main.py toggle callback when expanding details

**Note**: "Ordered at" always shows original order time, NOT confirmed time (confirmed time is in status line)

---

### 4. `vendor_time_keyboard(order_id, vendor)` - Line 202
**Purpose**: Build time request keyboard for specific vendor (vertical layout)

**Structure**:
```
[⚡ Asap]
[🕒 Time picker]
[🗂 Scheduled orders]  (only if recent orders exist)
[← Back]
```

**Logic**:
1. Always show "Asap" and "Time picker" buttons
2. Call `get_recent_orders_for_same_time()` from mdg.py with vendor filter
3. If recent orders exist: Show "Scheduled orders" button
4. Show "Back" button

**Callback Formats**:
- Asap: `vendor_asap|{order_id}|{vendor}`
- Time picker: `req_exact|{order_id}|{vendor}`
- Scheduled orders: `req_scheduled|{order_id}|{vendor}`
- Back: `hide`

**Returns**: InlineKeyboardMarkup

**Usage**: Called after vendor confirms/responds to time request in main.py

---

### 5. `vendor_keyboard(order_id, vendor, expanded, order)` - Line 220
**Purpose**: Build vendor toggle keyboard with conditional Problem button

**Structure** (Collapsed):
```
[Details ▸]
[🚩 Problem]  (conditional)
```

**Structure** (Expanded):
```
[◂ Hide]
[🚩 Problem]  (conditional)
```

**Problem Button Logic**:
Shows Problem button ONLY if:
1. Vendor has confirmed time (`vendor in order.get("confirmed_times", {})`)
2. Order is NOT delivered yet (`order.get("status") != "delivered"`)

**Rationale**: Problem button only relevant after vendor confirms but before delivery completes

**Callback Formats**:
- Toggle: `toggle|{order_id}|{vendor}|{timestamp}`
- Problem: `wrong|{order_id}|{vendor}`

**Returns**: InlineKeyboardMarkup

**Usage**: Called from main.py for all RG message edits (initial, toggle, after response)

**Critical**: Lines 234-241 implement conditional Problem button visibility

---

### 6. `restaurant_response_keyboard(request_type, order_id, vendor)` - Line 246
**Purpose**: Build restaurant response buttons after time request

**Parameters**:
- `request_type`: "ASAP" or "TIME"
- `order_id`: Order identifier
- `vendor`: Full vendor name

**ASAP Request Structure**:
```
[⏰ Yes at:]
[🚩 Problem]
```

**TIME Request Structure**:
```
[Works 👍]
[⏰ Later at]
[🚩 Problem]
```

**Logic**:
- ASAP: Only show "Yes at" (vendor picks time)
- TIME: Show "Works" (accept requested time) and "Later at" (propose different time)
- Both: Show "Problem" button

**Callback Formats**:
- Yes at (ASAP): `prepare|{order_id}|{vendor}`
- Works: `works|{order_id}|{vendor}`
- Later at: `later|{order_id}|{vendor}`
- Problem: `wrong|{order_id}|{vendor}`

**Returns**: InlineKeyboardMarkup

**Usage**: Called from main.py after sending time request to RG

---

### 7. `vendor_exact_time_keyboard(order_id, vendor, action)` - Line 273
**Purpose**: Build hour selection keyboard for vendor time picker

**Parameters**:
- `order_id`: Order identifier
- `vendor`: Full vendor name
- `action`: Action context ("prepare", "later", or "works")

**Structure**:
```
[18] [19] [20]
[21] [22] [23]
[← Back]
```

**Logic**:
1. Get current hour and minute
2. If past 57 minutes: Start from next hour (no valid 3-min intervals left in current hour)
3. Generate hours from start_hour to 23 (midnight)
4. Show 3 hours per row
5. Compress callback data using vendor shortcut (e.g., "LR" instead of "Leckerolls")

**Callback Format**: `vendor_exact_hour|{order_id}|{hour}|{vendor_short}|{action}`

**Example**: `vendor_exact_hour|123|19|LR|prepare`

**Returns**: InlineKeyboardMarkup

**Usage**: Called from main.py after vendor clicks "Time picker" or "Later at"

**Critical**: Line 285-286 skips current hour if past minute 57 to avoid empty minute picker

---

### 8. `vendor_exact_hour_keyboard(order_id, hour, vendor, action)` - Line 307
**Purpose**: Build minute selection keyboard after hour selected

**Parameters**:
- `order_id`: Order identifier
- `hour`: Selected hour (0-23)
- `vendor`: Full vendor name
- `action`: Action context

**Structure**:
```
[00] [03] [06] [09]
[12] [15] [18] [21]
[24] [27] [30] [33]
[36] [39] [42] [45]
[48] [51] [54] [57]
[◂ Back to hours]
```

**Logic**:
1. Generate minutes from 00 to 57 in 3-minute intervals (20 buttons total)
2. Show 4 minutes per row
3. Format time as HH:MM
4. Compress callback data using vendor shortcut

**Callback Formats**:
- Minute: `vendor_exact_selected|{order_id}|{time}|{vendor_short}|{action}`
- Back: `vendor_exact_back|{order_id}|{vendor_short}|{action}`

**Example**: `vendor_exact_selected|123|19:30|LR|prepare`

**Returns**: InlineKeyboardMarkup

**Usage**: Called from main.py after vendor selects hour

---

## Critical Patterns

### 1. Workflow Equality (Shopify vs Smoothr)
**After parsing, workflows are identical** - only message format differs:

```python
# Same keyboard builders for both order types
vendor_keyboard(order_id, vendor, expanded, order)
vendor_time_keyboard(order_id, vendor)
restaurant_response_keyboard(request_type, order_id, vendor)

# Same status update system
build_status_lines(order, "rg", RESTAURANT_SHORTCUTS, vendor=vendor)

# Same response handlers in main.py
# BTN-WORKS, BTN-LATER, BTN-WRONG work identically
```

**Only difference**: Message text format (summary/details) based on `order_type`

### 2. Order Type Branching
Every message builder checks `order_type`:

```python
order_type = order.get("order_type", "shopify")

if order_type == "shopify":
    # Shopify format: street only in summary
    lines.append(f"🗺️ {street}")
else:
    # DD/PF format: full address + customer in summary
    lines.append(f"🗺️ {address}")
    lines.append(f"👤 {customer_name}")
```

### 3. Blank Line Management
**Critical spacing rules** (see Failure Pattern #13 - RG-SUM spacing):

```python
# Status text ends with 2 newlines
status_text = build_status_lines(...)

# Remove 1 newline for proper separator spacing
if status_text.endswith('\n\n'):
    status_text = status_text[:-1]  # Keep 1 newline

# Result: 1 newline before separator
[status_text with 1 trailing newline]
────────────────
[blank line]
[content]
```

**Pattern throughout**:
- After separator: Always 1 blank line
- After address: Shopify = 1 blank line, DD/PF = 0 (customer follows)
- After customer (DD/PF): 1 blank line
- After products: 1 blank line
- After note: Details = 1 blank line, Summary = 0 (end of message)

### 4. Product Display Rules
**PF Lieferando Exception**:

```python
# Get vendor items
vendor_items = order.get("vendor_items", {}).get(vendor, [])

# Show products ONLY if:
# 1. Items exist
# 2. NOT PF Lieferando order
if vendor_items and order_type != "smoothr_lieferando":
    for item in vendor_items:
        lines.append(item.lstrip('- ').strip())
```

**Reason**: PF Lieferando uses OCR → only product count available, not item details

### 5. Vendor Shortcut Compression
**Callback data optimization** (Telegram 64-byte limit):

```python
# Full name in function calls
vendor_keyboard(order_id, "Leckerolls", expanded, order)

# Shortcut in callback data
RESTAURANT_SHORTCUTS.get(vendor, vendor[:2])
# "Leckerolls" → "LR"

# Callback: vendor_exact_hour|123|19|LR|prepare (24 chars)
# vs: vendor_exact_hour|123|19|Leckerolls|prepare (37 chars)
```

**Reverse decoding** in main.py:
```python
SHORTCUT_TO_VENDOR = {v: k for k, v in RESTAURANT_SHORTCUTS.items()}
full_name = SHORTCUT_TO_VENDOR.get(shortcut, shortcut)
```

### 6. Conditional Button Visibility
**Problem button logic** (Lines 234-241):

```python
if order:
    vendor_confirmed = vendor in order.get("confirmed_times", {})
    order_delivered = order.get("status") == "delivered"
    
    if vendor_confirmed and not order_delivered:
        buttons.append([
            InlineKeyboardButton("🚩 Problem", callback_data=f"wrong|{order_id}|{vendor}")
        ])
```

**States when Problem button shows**:
- ✅ Vendor confirmed time, order assigned (status="assigned")
- ✅ Vendor confirmed time, order ready (status="ready")
- ❌ Vendor not confirmed yet (no confirmed_times entry)
- ❌ Order delivered (status="delivered")

### 7. Time Picker Smart Start
**Skip current hour if too late** (Line 285-286):

```python
current_minute = current_time.minute
start_hour = current_hour + 1 if current_minute >= 57 else current_hour
```

**Reason**: 3-minute intervals (00, 03, 06, ..., 57). If current time is 19:58, no valid intervals left in hour 19.

**Example**:
- Current: 19:30 → Show hours: 19, 20, 21, 22, 23
- Current: 19:58 → Show hours: 20, 21, 22, 23 (skip 19)

### 8. Phone Formatting
**All phone displays use Android auto-detection**:

```python
from utils import format_phone_for_android

phone = order.get('customer', {}).get('phone', 'N/A')
lines.append(f"📞 {format_phone_for_android(phone)}")
```

**Format**: No spaces, ensures +49 prefix → Android recognizes as clickable phone number

---

## Usage Map (What Calls What)

### Called By main.py (Webhook/Callback Handlers):
- `build_vendor_summary_text()` - Initial RG message after order creation, after toggle collapse
- `build_vendor_details_text()` - After toggle expand
- `vendor_keyboard()` - Every RG message edit (initial, toggle, after response)
- `vendor_time_keyboard()` - After vendor response to time request
- `restaurant_response_keyboard()` - After sending time request to RG
- `vendor_exact_time_keyboard()` - After vendor clicks "Time picker" or "Later at"
- `vendor_exact_hour_keyboard()` - After vendor selects hour

### Internal Call Chains:
```
build_vendor_summary_text()
  ├→ build_status_lines() (from utils.py)
  └→ Reads vendor_items, note from STATE

build_vendor_details_text()
  ├→ build_status_lines() (from utils.py)
  ├→ format_phone_for_android() (from utils.py)
  └→ Reads vendor_items, note, phone, created_at from STATE

vendor_time_keyboard()
  └→ get_recent_orders_for_same_time() (from mdg.py)

vendor_keyboard()
  └→ Reads confirmed_times, status from STATE
```

### Callback Data Consumed By main.py:
- `toggle|{order_id}|{vendor}|{timestamp}` → Toggle summary/details
- `vendor_asap|{order_id}|{vendor}` → Vendor requests ASAP
- `req_exact|{order_id}|{vendor}` → Vendor opens time picker
- `req_scheduled|{order_id}|{vendor}` → Vendor views scheduled orders
- `prepare|{order_id}|{vendor}` → Vendor confirms ASAP (picks time)
- `works|{order_id}|{vendor}` → Vendor accepts requested time
- `later|{order_id}|{vendor}` → Vendor proposes different time
- `wrong|{order_id}|{vendor}` → Vendor reports problem
- `vendor_exact_hour|{order_id}|{hour}|{vendor_short}|{action}` → Hour selected
- `vendor_exact_selected|{order_id}|{time}|{vendor_short}|{action}` → Time selected
- `vendor_exact_back|{order_id}|{vendor_short}|{action}` → Back to hour picker

---

## Data Flow Diagrams

### RG Message Creation Flow
```
Shopify/Smoothr Webhook
  ↓
main.py: Order created in STATE
  ↓
Get VENDOR_GROUP_MAP[vendor] → RG chat_id
  ↓
build_vendor_summary_text(order, vendor)
  ├→ build_status_lines(order, "rg", shortcuts, vendor)
  ├→ Check order_type
  ├→ Format address (street vs full)
  ├→ Add customer (DD/PF only)
  ├→ Add products (if not PF Lieferando)
  └→ Add note (if exists)
  ↓
vendor_keyboard(order_id, vendor, expanded=False, order)
  ├→ Check confirmed_times
  ├→ Check status
  └→ Add Problem button conditionally
  ↓
Send to RG chat
Store rg_message_ids[vendor] in STATE
```

### Toggle Details Flow
```
User clicks "Details ▸" or "◂ Hide" in RG
  ↓
main.py: Handle toggle callback
  ↓
Parse: order_id, vendor, timestamp
  ↓
Get current state: order["vendor_expanded"][vendor]
  ↓
Toggle state: expanded = not expanded
  ↓
If expanded:
  build_vendor_details_text(order, vendor)
Else:
  build_vendor_summary_text(order, vendor)
  ↓
vendor_keyboard(order_id, vendor, expanded, order)
  ↓
Edit RG message with new text + keyboard
Update STATE: order["vendor_expanded"][vendor] = expanded
```

### Time Request → Vendor Response Flow
```
MDG: User sends time request (ASAP or TIME)
  ↓
main.py: Update STATE, send to RG
  ↓
build_vendor_summary_text(order, vendor)
  └→ Status shows "⏰ 19:30 requested"
  ↓
restaurant_response_keyboard(request_type, order_id, vendor)
  └→ Show: Works/Later (TIME) or Yes at (ASAP)
  ↓
Edit RG message with response keyboard
  ↓
[Vendor clicks response button]
  ↓
main.py: Handle response callback
  ↓
If "Works":
  ├→ Set confirmed_times[vendor] = requested_time
  ├→ Update STATE, MDG, RG
  └→ Show vendor_keyboard (toggle + Problem)
  
If "Later at" or "Yes at":
  ├→ vendor_exact_time_keyboard(order_id, vendor, action)
  └→ Vendor picks hour → minute → time
  ├→ Set confirmed_times[vendor] = picked_time
  ├→ Update STATE, MDG, RG
  └→ Show vendor_keyboard (toggle + Problem)
```

### Vendor Time Picker Flow
```
Vendor clicks "⏰ Later at" or "⏰ Yes at:"
  ↓
main.py: Handle later|{order_id}|{vendor} or prepare|{order_id}|{vendor}
  ↓
vendor_exact_time_keyboard(order_id, vendor, action)
  ├→ Get current hour/minute
  ├→ Skip current hour if past 57 minutes
  └→ Show hours (3 per row)
  ↓
Edit RG message with hour picker
  ↓
[Vendor clicks hour]
  ↓
main.py: Handle vendor_exact_hour callback
  ↓
Parse: order_id, hour, vendor_short, action
Resolve vendor_short → full vendor name
  ↓
vendor_exact_hour_keyboard(order_id, hour, vendor, action)
  └→ Show minutes 00-57 in 3-min intervals (4 per row)
  ↓
Edit RG message with minute picker
  ↓
[Vendor clicks minute]
  ↓
main.py: Handle vendor_exact_selected callback
  ↓
Parse: order_id, time, vendor_short, action
Resolve vendor_short → full vendor name
  ↓
Set confirmed_times[vendor] = time
Update STATE, MDG, RG
Show vendor_keyboard (toggle + Problem)
```

### Problem Button Flow
```
Vendor clicks "🚩 Problem"
  ↓
main.py: Handle wrong|{order_id}|{vendor}
  ↓
[User-defined logic - varies by scenario]
  ├→ Notify MDG
  ├→ Request new time
  └→ Mark order for manual handling
```

---

## Constants & Mappings

### RESTAURANT_SHORTCUTS (Lines 23-34)
```python
{
    "Julis Spätzlerei": "JS",
    "Zweite Heimat": "ZH",
    "Hello Burrito": "HB",
    "Kahaani": "KA",
    "i Sapori della Toscana": "SA",
    "Leckerolls": "LR",
    "dean & david": "DD",
    "Pommes Freunde": "PF",
    "Wittelsbacher Apotheke": "AP",
    "Safi": "SF"
}
```

### SHORTCUT_TO_VENDOR (Line 37)
```python
{
    "JS": "Julis Spätzlerei",
    "ZH": "Zweite Heimat",
    "HB": "Hello Burrito",
    "KA": "Kahaani",
    "SA": "i Sapori della Toscana",
    "LR": "Leckerolls",
    "DD": "dean & david",
    "PF": "Pommes Freunde",
    "AP": "Wittelsbacher Apotheke",
    "SF": "Safi"
}
```

**Usage**: Compress callback data, decode in main.py handlers

---

## Critical Logic Deep Dives

### Blank Line Spacing Logic (Lines 48-63, 117-128)
**Problem**: Status lines from `build_status_lines()` end with 2 newlines, but RG format needs 1 before separator

**Solution**:
```python
status_text = build_status_lines(order, "rg", RESTAURANT_SHORTCUTS, vendor=vendor)

# Status text structure:
# "⏰ 19:30 confirmed\n\n"
#                      ^^— 2 newlines

# Remove 1 newline for proper separator spacing
if status_text.endswith('\n\n'):
    status_text = status_text[:-1]  # Result: "⏰ 19:30 confirmed\n"

# Now build message:
lines = ["────────────────", ""]  # Separator with blank line
#                           ^^— This creates proper spacing

# Final result:
# "⏰ 19:30 confirmed\n────────────────\n\n[content]"
#                    ^                 ^^
#                    |                 └─ Blank line after separator
#                    └─ 1 newline before separator
```

**Why This Matters**: See Failure Pattern #13 - Hallucinating Message Formats. Wrong spacing breaks RG message display.

### Shopify vs DD/PF Format Differences (Lines 65-85, 131-151)
**Collapsed View**:

**Shopify Logic**:
```python
# Extract street part only (before comma)
address_parts = address.split(',')
street = address_parts[0].strip()
lines.append(f"🗺️ {street}")
lines.append("")  # Blank line

# Customer NOT shown in collapsed view
# Result:
# 🗺️ Ludwigstraße 15
# 
# 2 x Pizza
```

**DD/PF Logic**:
```python
# Show full address (already in correct format from parser)
lines.append(f"🗺️ {address}")
lines.append(f"👤 {customer_name}")
lines.append("")  # Blank line

# Result:
# 🗺️ Ludwigstraße 15
# 👤 Peter Weber
# 
# 2 x Roll
```

**Expanded View Additions**:

**Shopify**:
```python
# NOW add customer info (not in summary)
lines.append(f"👤 {customer_name}")
lines.append(f"📞 {phone}")
lines.append(f"⏰ Ordered at: {order_time}")
```

**DD/PF**:
```python
# Customer already shown above, just add phone/time
lines.append(f"📞 {phone}")
lines.append(f"⏰ Ordered at: {order_time}")
```

### PF Lieferando Product Handling (Line 88)
**Problem**: PF Lieferando orders come from OCR → no product details, only count

**Data Structure**:
```python
order = {
    "order_type": "smoothr_lieferando",
    "product_count": 3,  # From OCR extraction
    "vendor_items": {
        "Pommes Freunde": []  # Empty - no details
    }
}
```

**Solution**:
```python
vendor_items = order.get("vendor_items", {}).get(vendor, [])

# Check: items exist AND not PF Lieferando
if vendor_items and order_type != "smoothr_lieferando":
    for item in vendor_items:
        lines.append(item.lstrip('- ').strip())
    lines.append("")  # Blank line after products
```

**Result**: PF Lieferando RG messages show NO product list (just address, customer, note)

### Problem Button Conditional Logic (Lines 234-241)
**Requirements**: Show Problem button ONLY when relevant

**Implementation**:
```python
if order:
    vendor_confirmed = vendor in order.get("confirmed_times", {})
    order_delivered = order.get("status") == "delivered"
    
    # Show if: confirmed AND not delivered
    if vendor_confirmed and not order_delivered:
        buttons.append([
            InlineKeyboardButton("🚩 Problem", callback_data=f"wrong|{order_id}|{vendor}")
        ])
```

**Truth Table**:
| Confirmed | Delivered | Show Button |
|-----------|-----------|-------------|
| ❌ False  | ❌ False  | ❌ No       |
| ❌ False  | ✅ True   | ❌ No       |
| ✅ True   | ❌ False  | ✅ Yes      |
| ✅ True   | ✅ True   | ❌ No       |

**Rationale**:
- Before confirmation: Vendor handling time request, Problem button premature
- After delivery: Order complete, too late for problems

### Vendor Shortcut Encoding/Decoding (Lines 290, 316)
**Problem**: Callback data limited to 64 bytes

**Hour Picker Encoding**:
```python
vendor_short = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2])
callback_data = f"vendor_exact_hour|{order_id}|{hour_value}|{vendor_short}|{action}"

# "Leckerolls" → "LR"
# Callback: vendor_exact_hour|123|19|LR|prepare (31 chars)
# vs Full: vendor_exact_hour|123|19|Leckerolls|prepare (42 chars)
```

**Minute Picker Encoding**:
```python
vendor_short = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2])
time_str = f"{hour:02d}:{minutes[j]}"
callback_data = f"vendor_exact_selected|{order_id}|{time_str}|{vendor_short}|{action}"

# Callback: vendor_exact_selected|123|19:30|LR|prepare (38 chars)
```

**Decoding in main.py**:
```python
# Parse callback data
vendor_short = data[3]  # "LR"

# Resolve to full name
vendor = SHORTCUT_TO_VENDOR.get(vendor_short, vendor_short)
# "LR" → "Leckerolls"
```

---

## Stats Summary

**Total Functions**: 8
- Utilities: 1 (`now()`)
- Message Builders: 2 (`build_vendor_summary_text()`, `build_vendor_details_text()`)
- Keyboard Factories: 5 (vendor toggle, time request, response, exact time, exact hour)

**Total Lines**: 333

**Most Complex Function**: `build_vendor_summary_text()` (40-104, 65 lines) - Handles both order types, format differences, blank line management, product filtering, note display

**Most Called Function**: `build_vendor_summary_text()` - Called for initial RG message, toggle collapse, status updates

**Critical Dependencies**:
- utils.py: `build_status_lines()`, `format_phone_for_android()`
- mdg.py: `get_recent_orders_for_same_time()` (for Scheduled orders button)
- main.py: STATE (read via function parameters), VENDOR_GROUP_MAP (for chat_id lookup)

**Callback Actions Defined**: 11
- Toggle: `toggle`
- Vendor actions: `vendor_asap`, `req_exact`, `req_scheduled`
- Response: `prepare`, `works`, `later`, `wrong`
- Time picker: `vendor_exact_hour`, `vendor_exact_selected`, `vendor_exact_back`
- Navigation: `hide`

**Message Types**: 2 (Summary, Details)
**Order Type Branches**: 3 (Shopify, DD, PF Lieferando)

---

## Phase 1D Complete ✅

**rg.py Analysis**: Complete documentation of all 8 RG functions, 2 message builders (summary/details), 5 keyboard factories, format differentiation logic, blank line management, PF Lieferando handling, conditional button visibility, and vendor shortcut compression. Ready to proceed to Phase 1E (upc.py).

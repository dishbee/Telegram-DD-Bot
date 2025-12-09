# Phase 1C: mdg.py Analysis

**File**: `mdg.py`
**Total Lines**: 1,337
**Purpose**: MDG (Main Dispatch Group) message builders, keyboard factories, and time logic

---

## File Overview

This module handles all MDG-related functionality:
- Message text building (collapsed/expanded views)
- Keyboard factories (initial, time request, vendor selection, time pickers)
- Time logic (smart suggestions based on recent orders)
- Order combination system (group orders by courier)
- Status display with emoji indicators

**Critical Pattern**: Module receives STATE reference via `configure()` call from main.py (line 40). Never imports STATE directly to avoid circular dependencies.

---

## Imports & Configuration

### Standard Library (Lines 4-8)
```python
logging, re
datetime, timedelta
zoneinfo.ZoneInfo
typing (Any, Dict, List, Optional)
```

### Telegram Library (Line 10)
```python
InlineKeyboardButton, InlineKeyboardMarkup
```

### Project Modules (Line 11)
```python
from utils import get_district_from_address, abbreviate_street, format_phone_for_android
```

### Module-Level State (Lines 14-23)
- **TIMEZONE**: `ZoneInfo("Europe/Berlin")` - Passau timezone
- **STATE**: `None` - Set via `configure()` from main.py
- **RESTAURANT_SHORTCUTS**: `{}` - Set via `configure()` from main.py
- **CHEF_EMOJIS**: List of 12 chef emoji variations for multi-vendor buttons
- **COURIER_SHORTCUTS**: Dict mapping courier names to 2-letter codes (B1, B2, B3)
- **GROUP_COLORS**: List of 7 emoji colors for combined order groups (🟣🔵🟢🟡🟠🔴🟤)

---

## Function Catalog (23 Functions)

### 1. `now()` - Line 18
**Purpose**: Get current time in Passau timezone (Europe/Berlin)

**Returns**: `datetime` object with timezone awareness

**Usage**: Called throughout module for time calculations, comparisons, filtering

---

### 2. `configure(state_ref, restaurant_shortcuts)` - Line 40
**Purpose**: Configure module-level references (called from main.py startup)

**Parameters**:
- `state_ref`: Reference to main.py STATE dict
- `restaurant_shortcuts`: Dict mapping full vendor names to 2-letter codes

**Critical**: MUST be called before any other MDG functions. Sets global STATE and RESTAURANT_SHORTCUTS.

**Called By**: main.py line 176 during app initialization

---

### 3. `shortcut_to_vendor(shortcut)` - Line 47
**Purpose**: Convert vendor shortcut back to full vendor name

**Parameters**:
- `shortcut`: 2-letter vendor code (e.g., "LR")

**Returns**: Full vendor name (e.g., "Leckerolls") or None if not found

**Usage**: Used in callback handlers to resolve vendor from button data

---

### 4. `get_courier_shortcut(courier_id)` - Line 55
**Purpose**: Get courier shortcut from Telegram user_id

**Parameters**:
- `courier_id`: Telegram user_id from `order["assigned_to"]`

**Logic**:
1. Looks up courier name in DRIVERS dict from main.py
2. If "Bee 1/2/3" → returns "B1/B2/B3"
3. Otherwise → returns first 2 letters uppercase (e.g., "Michael" → "MI")
4. Fallback if not found → returns "??"

**Returns**: 2-letter courier code (e.g., "B1", "MI", "??")

**Usage**: Combine orders menu, assigned orders list

---

### 5. `get_vendor_shortcuts_string(vendors)` - Line 92
**Purpose**: Convert list of vendor names to comma-separated shortcuts

**Parameters**:
- `vendors`: List of full vendor names

**Returns**: Comma-separated shortcuts (e.g., "LR,DD" for multi-vendor)

**Usage**: MDG message header, UPC assignment confirmation

**Example**:
```python
["Leckerolls", "dean & david"] → "LR,DD"
```

---

### 6. `get_recent_orders_for_same_time(current_order_id, vendor)` - Line 111
**Purpose**: Get last 10 confirmed orders from last 5 hours (for "same time as" feature)

**Parameters**:
- `current_order_id`: Current order (excluded from results)
- `vendor`: Optional vendor filter (only show orders with same vendor)

**Logic**:
1. Filter orders created within last 5 hours
2. Must have confirmed_time set
3. If vendor specified, filter to orders containing that vendor
4. For Shopify: display as last 2 digits (e.g., "26")
5. For Smoothr: display as street name (e.g., "*Ludwigstraße*")
6. Return last 10 orders (most recent)

**Returns**: List of dicts with `order_id`, `display_name`, `vendor`

**Usage**: `same_time_keyboard()`, `mdg_time_submenu_keyboard()`

---

### 7. `get_last_confirmed_order(vendor)` - Line 181
**Purpose**: Get most recent order with confirmed time from today

**Parameters**:
- `vendor`: Optional vendor filter

**Logic**:
1. Filter orders created today
2. Must have confirmed_time set
3. If vendor specified, filter to orders with that vendor
4. Sort by created_at descending, return first

**Returns**: Order dict or None if no confirmed orders today

**Usage**: `build_smart_time_suggestions()` to show +5/+10/+15/+20 buttons

---

### 8. `build_smart_time_suggestions(order_id, vendor)` - Line 214
**Purpose**: Build smart time suggestion buttons based on last confirmed order

**Parameters**:
- `order_id`: Current order
- `vendor`: Optional vendor context (for multi-vendor orders)

**Logic**:
1. Get last confirmed order for vendor (or any vendor if not specified)
2. If found: Show 4 buttons: "+5min", "+10min", "+15min", "+20min" relative to that time
3. Each button shows: "{last_order_num} {last_time} + {minutes}min"
4. Always show "EXACT TIME ⏰" button at bottom
5. If no recent order: Show only "EXACT TIME ⏰" button

**Returns**: InlineKeyboardMarkup with 2x2 grid + exact time button

**Callback Format**: `smart_time|{order_id}|{vendor or 'all'}|{suggested_time}`

**Usage**: Multi-vendor time request workflow

---

### 9. `build_mdg_dispatch_text(order, show_details)` - Line 249
**Purpose**: Build MDG dispatch message text (collapsed or expanded view)

**Parameters**:
- `order`: Order dict from STATE
- `show_details`: False = collapsed (default), True = expanded

**Summary View Format** (show_details=False):
```
────────────────

🗺️ [Street 123 (80333)](maps_link)

👨‍🍳 **LR** (3)

📞 +491234567890

👤 Customer Name

Total: 18.50€
```

**Details View Format** (show_details=True):
```
[Same as above, plus:]

🔗 dishbee

🏙️ Innstadt (94032)

✉️ email@example.com

2 x Product Name
1 x Another Product
```

**Multi-Vendor Format**:
```
👨‍🍳 **LR** (3) + **DD** (1)
```

**Key Features**:
1. Calls `build_status_lines()` from utils.py first (prepends to message)
2. For Shopify: order_num = last 2 digits of `order['name']`
3. For Smoothr: order_num = full display number from parser
4. Product count: Sums quantities from `vendor_items` (e.g., "2 x Pizza" + "1 x Salad" = 3)
5. For PF Lieferando: Uses stored `product_count` field (OCR doesn't provide item details)
6. Address format: "Street (Zip)" with Google Maps link
7. Phone: Formatted via `format_phone_for_android()` (no spaces, +49 prefix)
8. Optional lines: Note, Tip, Cash on delivery
9. Expanded view only: Source (dishbee/D&D/Lieferando), District, Email, Product list
10. District detection: Calls `get_district_from_address()` from utils.py

**Returns**: Formatted message string

**Usage**: Called by every MDG message edit/send operation in main.py

**Critical Debug Logs** (Lines 320, 333, 355):
- Product count calculation for debugging vendor_items structure
- Shows total_qty per vendor

---

### 10. `mdg_initial_keyboard(order)` - Line 538
**Purpose**: Build initial MDG keyboard after order arrival

**Structure**:
```
[Details ▸]
[Time Request Buttons - varies by vendor count]
```

**Multi-Vendor Logic**:
- If 1 vendor: Show "Request ASAP" + "Request TIME" buttons
- If 2+ vendors: Show vendor selection buttons (one per vendor)

**Vendor Button Format**: Uses rotating chef emojis (12 variations)
```
"👨‍🍳 Request LR"
"👩‍🍳 Request DD"
```

**Callback Formats**:
- Details: `toggle_details|{order_id}`
- Single vendor ASAP: `req_asap|{order_id}`
- Single vendor TIME: `req_time|{order_id}`
- Multi-vendor: `req_vendor|{order_id}|{vendor_full_name}`

**Returns**: InlineKeyboardMarkup

**Usage**: Shopify/Smoothr webhook handlers after order creation

---

### 11. `mdg_time_request_keyboard(order_id)` - Line 592
**Purpose**: Build time request keyboard (ASAP/TIME/CUSTOM) - shown after "Request TIME" button

**Structure**:
```
[Request ASAP 🚀]
[Request TIME ⏰]
[CUSTOM ⚙️]
[← Back]
```

**Logic**:
1. Gets order from STATE
2. Checks if multi-vendor or single-vendor
3. Multi-vendor: Callback includes vendor parameter
4. Single-vendor: Callback without vendor parameter

**Callback Formats**:
- ASAP: `req_asap|{order_id}|{vendor}` (multi) or `req_asap|{order_id}` (single)
- TIME: `req_time|{order_id}|{vendor}` (multi) or `req_time|{order_id}` (single)
- CUSTOM: `req_custom|{order_id}|{vendor}` (multi) or `req_custom|{order_id}` (single)
- Back: `hide`

**Returns**: InlineKeyboardMarkup

**Usage**: Called after user clicks vendor button (multi-vendor) or "Request TIME" (single-vendor)

---

### 12. `mdg_time_submenu_keyboard(order_id, vendor)` - Line 652
**Purpose**: Build TIME submenu with recent orders + hour picker

**Structure** (if recent orders exist):
```
[🔖 26 - LR]  [🔖 24 - DD]
[🔖 22 - LR]  [🔖 19 - DD]
[...up to 10 orders]
[HOUR PICKER ⏰]
[← Back]
```

**Structure** (if NO recent orders):
Returns `None` → signals handler to show hour picker directly

**Logic**:
1. Calls `get_recent_orders_for_same_time(order_id, vendor)`
2. Filters to orders with same vendor (if vendor specified)
3. Shows last 10 confirmed orders in 2-column grid
4. Each button: "{display_name} - {vendor_shortcut}"
5. If no recent orders: Returns None (handler shows hour picker)

**Callback Formats**:
- Recent order: `time_ref|{order_id}|{ref_order_id}|{vendor or 'all'}`
- Hour picker: `vendor_exact|{order_id}|{vendor or 'all'}`
- Back: `hide`

**Returns**: InlineKeyboardMarkup or None

**Usage**: Called after user clicks "Request TIME" button

---

### 13. `order_reference_options_keyboard(current_order_id, ref_order_id, ref_time, ref_vendors_str, current_vendor)` - Line 817
**Purpose**: Build offset buttons after user selects reference order

**Structure**:
```
[🔁 Same time]  (only if vendors match)
[-5m → ⏰ 19:25]
[-3m → ⏰ 19:27]
[+3m → ⏰ 19:33]
[+5m → ⏰ 19:35]
[+10m → ⏰ 19:40]
[+15m → ⏰ 19:45]
[+20m → ⏰ 19:50]
[+25m → ⏰ 19:55]
[← Back]
```

**Logic**:
1. Converts shortcuts to full vendor names
2. Checks if current vendor matches reference vendor
3. If vendors match: Shows "Same time" button
4. If vendors don't match: Skips "Same time" button
5. Shows 8 offset buttons: -5, -3, +3, +5, +10, +15, +20, +25 minutes
6. Calculates each time from reference time

**Callback Formats**:
- Same time: `time_same|{order_id}|{ref_order_id}|{ref_time}|{vendor_full}` (multi) or `time_same|{order_id}|{ref_order_id}|{ref_time}` (single)
- Offset: `time_relative|{order_id}|{calculated_time}|{ref_order_id}|{vendor_full}` (multi) or `time_relative|{order_id}|{calculated_time}|{ref_order_id}` (single)
- Back: `hide`

**Returns**: InlineKeyboardMarkup

**Usage**: Called after user clicks recent order button

---

### 14. `same_time_keyboard(order_id)` - Line 882
**Purpose**: Build "same time as" selection keyboard (legacy - rarely used)

**Structure**:
```
[26 (Leckerolls)]
[24 (dean & david)]
[22 (Leckerolls)]
```

**Logic**: Similar to TIME submenu but simpler format

**Returns**: InlineKeyboardMarkup

**Usage**: Legacy feature, mostly replaced by TIME submenu workflow

---

### 15. `time_picker_keyboard(order_id, action, requested_time, vendor)` - Line 902
**Purpose**: Build time picker with +3min increment buttons

**Structure**:
```
Current: 19:30

[+3min] [+6min]
[+9min] [+12min]
[+15min] [+18min]
[+21min] [+24min]

[Set Time ⏰]
[← Back]
```

**Logic**:
1. If requested_time provided: Use as base
2. Otherwise: Use current time rounded to nearest 3min interval
3. Show 8 buttons: +3, +6, +9, +12, +15, +18, +21, +24 minutes
4. "Set Time" button: Opens exact hour picker

**Callback Formats**:
- Plus button: `time_plus|{order_id}|{minutes}|{action}|{vendor or 'all'}`
- Set Time: `exact|{order_id}|{vendor or 'all'}`
- Back: `hide`

**Usage**: Called from various time request flows

---

### 16. `exact_time_keyboard(order_id, vendor)` - Line 977
**Purpose**: Build hour selection keyboard (current hour to midnight)

**Structure**:
```
[19:xx] [20:xx]
[21:xx] [22:xx]
[23:xx]

[← Back]
```

**Logic**:
1. Get current hour
2. Show buttons from current hour to 23 (midnight)
3. 2-column grid

**Callback Format**: `exact_hour|{order_id}|{hour}|{vendor or 'all'}`

**Returns**: InlineKeyboardMarkup

**Usage**: Called from time picker "Set Time" button or directly from TIME submenu

---

### 17. `exact_hour_keyboard(order_id, hour, vendor)` - Line 1013
**Purpose**: Build minute selection keyboard for chosen hour (3min intervals)

**Structure**:
```
[19:00] [19:03] [19:06]
[19:09] [19:12] [19:15]
[19:18] [19:21] [19:24]
[19:27] [19:30] [19:33]
[19:36] [19:39] [19:42]
[19:45] [19:48] [19:51]
[19:54] [19:57]

[← Back]
```

**Logic**:
1. Generate all minutes from 00 to 57 in 3min steps (20 buttons total)
2. 3-column grid
3. Format: HH:MM

**Callback Format**: `exact_selected|{order_id}|{time}|{vendor or 'all'}`

**Returns**: InlineKeyboardMarkup

**Usage**: Called after user selects hour from exact_time_keyboard

---

### 18. `get_assigned_orders(state_dict, exclude_order_id)` - Line 1055
**Purpose**: Get all assigned (not delivered) orders for combine menu

**Parameters**:
- `state_dict`: STATE dict from main.py
- `exclude_order_id`: Current order (excluded from results)

**Logic**:
1. Filter orders with status="assigned" (not delivered)
2. Exclude current order
3. For multi-vendor: Create separate entry per vendor
4. Extract: order_num (last 2 digits), vendor_shortcut, confirmed_time, street address, courier_name
5. Button text: "{address} - {time} - {vendor} | {courier}"
6. If button text > 30 chars: Truncate address letter-by-letter until fits
7. Sort by courier_name (groups orders by courier together)

**Returns**: List of dicts with order details

**Usage**: `build_combine_keyboard()`, `show_combine_orders_menu()`

---

### 19. `generate_group_id()` - Line 1175
**Purpose**: Generate unique group ID for combined orders

**Format**: `group_YYYYMMDD_HHMMSS`

**Example**: `group_20241206_193045`

**Returns**: String group identifier

**Usage**: Order combination system (Phase 2 feature)

---

### 20. `get_next_group_color(state_dict)` - Line 1187
**Purpose**: Get next available group color from 7-color rotation

**Colors**: 🟣🔵🟢🟡🟠🔴🟤

**Logic**:
1. Get all currently used colors from orders with group_id
2. Find first color in GROUP_COLORS not in use
3. If all 7 colors used: Reuse first color (🟣)

**Returns**: Color emoji string

**Usage**: Order combination system (Phase 2 feature)

---

### 21. `get_group_orders(state_dict, group_id)` - Line 1216
**Purpose**: Get all orders belonging to a group

**Parameters**:
- `state_dict`: STATE dict
- `group_id`: Group identifier from `generate_group_id()`

**Returns**: List of order dicts with matching group_id

**Usage**: Order combination system (Phase 2 feature)

---

### 22. `build_combine_keyboard(order_id, assigned_orders)` - Line 1238
**Purpose**: Build keyboard to select order to combine with

**Structure**:
```
[Ludwigstraße - 19:30 - LR | Bee 1]
[Innstraße - 19:35 - DD | Bee 1]
[Bahnhofstraße - 19:40 - LR | Bee 2]
[← Back]
```

**Logic**:
1. One button per assigned order (from `get_assigned_orders()`)
2. Button text: "{address} - {time} - {vendor} | {courier}"
3. Already truncated by `get_assigned_orders()` to fit 30 chars

**Callback Format**: `combine_with|{order_id}|{target_order_id}`

**Returns**: InlineKeyboardMarkup

**Usage**: `show_combine_orders_menu()`

---

### 23. `show_combine_orders_menu(state_dict, order_id, chat_id, message_id)` - Line 1276
**Purpose**: Display combine orders menu in MDG

**Parameters**:
- `state_dict`: STATE dict
- `order_id`: Current order to combine
- `chat_id`: MDG chat ID
- `message_id`: Message to edit (not used - sends new message instead)

**Logic**:
1. Get assigned orders via `get_assigned_orders()`
2. If none: Return silently (button shouldn't have been shown)
3. Get current order street and order_num for header
4. Build keyboard via `build_combine_keyboard()`
5. Send NEW message (doesn't edit existing MDG message)
6. Track new message in `order["mdg_additional_messages"]` for cleanup

**Message Format**: `📌 Combine 🗺️ {street} (🔖 {num}) with:`

**Returns**: None (async function)

**Usage**: Called from main.py callback handler for combine button

---

## Critical Patterns

### 1. STATE Access Pattern
**Never imports STATE directly** - avoids circular dependencies:
```python
STATE = None  # Module-level
RESTAURANT_SHORTCUTS = {}

def configure(state_ref, restaurant_shortcuts):
    global STATE, RESTAURANT_SHORTCUTS
    STATE = state_ref
    RESTAURANT_SHORTCUTS = restaurant_shortcuts
```

Called from main.py:
```python
configure_mdg(STATE, RESTAURANT_SHORTCUTS)
```

### 2. Multi-Vendor Branching
Almost every function checks vendor count:
```python
if len(vendors) > 1:
    # Multi-vendor logic
    callback_data = f"action|{order_id}|{vendor}"
else:
    # Single-vendor logic
    callback_data = f"action|{order_id}"
```

### 3. Product Count Calculation
Sums quantities from formatted strings:
```python
# "2 x Pizza" → extract 2
# "1 x Salad" → extract 1
# Total = 3
for item_line in items:
    item_clean = item_line.lstrip('- ').strip()
    if ' x ' in item_clean:
        qty_part = item_clean.split(' x ')[0].strip()
        total_qty += int(qty_part)
```

**Exception for PF Lieferando**: Uses stored `product_count` field (OCR doesn't provide details)

### 4. Vendor Shortcut Resolution
Two-way conversion:
```python
# Full name → shortcut
RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())

# Shortcut → full name
def shortcut_to_vendor(shortcut):
    for full_name, short in RESTAURANT_SHORTCUTS.items():
        if short == shortcut:
            return full_name
    return None
```

### 5. Time Filtering
Recent orders (5 hours):
```python
five_hours_ago = now() - timedelta(hours=5)
if created_dt > five_hours_ago:
    # Include in recent orders
```

Today's orders only:
```python
today = now().date()
if created_dt.date() != today:
    continue
```

### 6. Button Text Truncation
Combine orders menu (30 char limit):
```python
final_address = street
button_text = f"{final_address} - {time} - {vendor} | {courier}"
while len(button_text) > 30 and len(final_address) > 1:
    final_address = final_address[:-1]
    button_text = f"{final_address} - {time} - {vendor} | {courier}"
```

### 7. Callback Data Piping
Consistent format throughout:
```python
# Single-vendor
callback_data = f"action|{order_id}|{param}"

# Multi-vendor
callback_data = f"action|{order_id}|{param}|{vendor_full_name}"

# With timestamp (for deduplication)
callback_data = f"action|{order_id}|{param}|{timestamp}"
```

### 8. Rotating Emojis
Chef emojis for visual variety:
```python
CHEF_EMOJIS = ['👩‍🍳', '👩🏻‍🍳', '👩🏼‍🍳', ..., '👨🏾‍🍳']
chef_emoji = CHEF_EMOJIS[vendor_index % len(CHEF_EMOJIS)]
```

Group colors for combined orders:
```python
GROUP_COLORS = ["🟣", "🔵", "🟢", "🟡", "🟠", "🔴", "🟤"]
```

---

## Usage Map (What Calls What)

### Called By main.py (Webhook Handlers):
- `build_mdg_dispatch_text()` - Every MDG message edit/send
- `mdg_initial_keyboard()` - After order creation
- `mdg_time_request_keyboard()` - After "Request TIME" button
- `mdg_time_submenu_keyboard()` - After vendor selection
- `time_picker_keyboard()` - Various time request flows
- `exact_time_keyboard()` - From time picker or TIME submenu
- `exact_hour_keyboard()` - After hour selection
- `order_reference_options_keyboard()` - After recent order selection
- `build_smart_time_suggestions()` - Multi-vendor time workflow
- `show_combine_orders_menu()` - From combine button callback

### Internal Call Chains:
```
mdg_time_submenu_keyboard()
  └→ get_recent_orders_for_same_time()

build_smart_time_suggestions()
  └→ get_last_confirmed_order()

order_reference_options_keyboard()
  └→ shortcut_to_vendor()

build_mdg_dispatch_text()
  ├→ build_status_lines() (from utils.py)
  ├→ get_district_from_address() (from utils.py)
  ├→ abbreviate_street() (from utils.py)
  └→ format_phone_for_android() (from utils.py)

show_combine_orders_menu()
  ├→ get_assigned_orders()
  └→ build_combine_keyboard()

build_combine_keyboard()
  └→ get_assigned_orders()

get_assigned_orders()
  └→ get_courier_shortcut()

get_courier_shortcut()
  └→ DRIVERS (from main.py)
```

---

## Data Flow Diagrams

### Order Creation → MDG Message
```
Shopify/Smoothr Webhook
  ↓
main.py: Create order in STATE
  ↓
build_mdg_dispatch_text(order, show_details=False)
  ├→ build_status_lines() - prepend status
  ├→ Extract order_num (last 2 digits or full name)
  ├→ Count products per vendor
  ├→ Format address with maps link
  ├→ Format phone for Android
  └→ Build collapsed view
  ↓
mdg_initial_keyboard(order)
  ├→ Check len(vendors)
  ├→ Multi-vendor: Show vendor buttons
  └→ Single-vendor: Show ASAP/TIME buttons
  ↓
Send to MDG chat
Store mdg_message_id in STATE
```

### Time Request Flow (Multi-Vendor)
```
User clicks vendor button (e.g., "👨‍🍳 Request LR")
  ↓
main.py: Handle req_vendor callback
  ↓
mdg_time_request_keyboard(order_id)
  └→ Show ASAP / TIME / CUSTOM buttons
  ↓
User clicks "Request TIME"
  ↓
main.py: Handle req_time callback
  ↓
mdg_time_submenu_keyboard(order_id, vendor)
  ├→ get_recent_orders_for_same_time()
  ├→ Filter to same vendor
  └→ Show recent orders + HOUR PICKER
  ↓
User clicks recent order (e.g., "🔖 26 - LR")
  ↓
main.py: Handle time_ref callback
  ↓
order_reference_options_keyboard(...)
  ├→ Check if vendors match
  ├→ Show "Same time" if match
  └→ Show offset buttons (-5m to +25m)
  ↓
User clicks offset (e.g., "+5m → ⏰ 19:35")
  ↓
main.py: Handle time_relative callback
  ├→ Send to RG
  ├→ Update STATE
  └→ Update MDG message
```

### Time Request Flow (Single-Vendor)
```
User clicks "Request TIME"
  ↓
main.py: Handle req_time callback
  ↓
mdg_time_request_keyboard(order_id)
  └→ Show ASAP / TIME / CUSTOM buttons
  ↓
User clicks "Request TIME" again
  ↓
main.py: Handle req_time callback
  ↓
mdg_time_submenu_keyboard(order_id, vendor=None)
  ├→ get_recent_orders_for_same_time()
  └→ Show all recent orders + HOUR PICKER
  ↓
[Same as multi-vendor flow from here]
```

### Exact Time Picker Flow
```
User clicks "HOUR PICKER ⏰"
  ↓
main.py: Handle vendor_exact callback
  ↓
exact_time_keyboard(order_id, vendor)
  └→ Show hours (current to 23:00)
  ↓
User clicks hour (e.g., "19:xx")
  ↓
main.py: Handle exact_hour callback
  ↓
exact_hour_keyboard(order_id, hour, vendor)
  └→ Show minutes (00 to 57 in 3min steps)
  ↓
User clicks time (e.g., "19:30")
  ↓
main.py: Handle exact_selected callback
  ├→ Send to RG
  ├→ Update STATE
  └→ Update MDG message
```

### Combine Orders Flow
```
Order assigned to courier
  ↓
User clicks "🔗 Combine" button
  ↓
main.py: Handle combine_orders callback
  ↓
show_combine_orders_menu(STATE, order_id, chat_id, msg_id)
  ├→ get_assigned_orders(STATE, exclude=order_id)
  │   ├→ Filter status="assigned"
  │   ├→ Extract details per vendor
  │   ├→ Truncate address if needed
  │   └→ Sort by courier_name
  ├→ build_combine_keyboard(order_id, assigned_orders)
  │   └→ One button per order
  ├→ Send NEW message
  └→ Track in mdg_additional_messages
  ↓
User clicks order (e.g., "Ludwigstraße - 19:30 - LR | B1")
  ↓
main.py: Handle combine_with callback
  ├→ Create group_id
  ├→ Assign group_color
  ├→ Update both orders with group_id
  ├→ Update MDG messages
  └→ Cleanup temporary message
```

---

## Constants & Mappings

### RESTAURANT_SHORTCUTS (Set via configure())
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

### COURIER_SHORTCUTS (Lines 32-36)
```python
{
    "Bee 1": "B1",
    "Bee 2": "B2",
    "Bee 3": "B3"
    # Others: First 2 letters
}
```

### CHEF_EMOJIS (Line 27)
```python
['👩‍🍳', '👩🏻‍🍳', '👩🏼‍🍳', '👩🏾‍🍳', '🧑‍🍳', '🧑🏻‍🍳', '🧑🏼‍🍳', '🧑🏾‍🍳', '👨‍🍳', '👨🏻‍🍳', '👨🏼‍🍳', '👨🏾‍🍳']
```

### GROUP_COLORS (Line 38)
```python
["🟣", "🔵", "🟢", "🟡", "🟠", "🔴", "🟤"]
```

---

## Critical Logic Deep Dives

### Product Count Logic (Lines 320-355)
**Problem**: Must count total quantity, not just line items

**Example**:
```python
vendor_items = {
    "Leckerolls": [
        "2 x Classic Roll",
        "1 x Cinnamon Roll"
    ]
}
# Should show: LR (3), not LR (2)
```

**Implementation**:
```python
for item_line in items:
    item_clean = item_line.lstrip('- ').strip()
    if ' x ' in item_clean:
        qty_part = item_clean.split(' x ')[0].strip()
        total_qty += int(qty_part)
    else:
        total_qty += 1  # No quantity, assume 1
```

**Special Case - PF Lieferando**:
```python
if order_type == "smoothr_lieferando" and "product_count" in order:
    total_qty = order["product_count"]  # Use OCR-extracted count
    continue  # Skip item parsing
```

### Address Display Logic (Lines 376-394)
**Collapsed View**:
- Format: "Street (Zip)"
- Shopify: "Street, Zip" → extract both parts
- Smoothr: street + zip stored separately
- Google Maps link uses original_address (preserves full format)

**Expanded View**:
- Same as collapsed
- Plus district line: "🏙️ Innstadt (94032)"
- District from `get_district_from_address(original_address)`

### Vendor Matching Logic (Line 847-863)
**Purpose**: Determine if "Same time" button should show

**Multi-Vendor Order**:
```python
if current_vendor_full:
    # Check if THIS vendor matches reference vendor
    vendor_matches = (current_vendor_full == ref_vendor_full)
```

**Single-Vendor Order**:
```python
else:
    # Check if ref vendor in current order's vendors
    vendor_matches = (ref_vendor_full in current_vendors)
```

**Result**:
- Match: Show "🔁 Same time" button
- No match: Skip same time button, show only offset buttons

### Button Text Truncation (Lines 1143-1152)
**Problem**: Telegram inline buttons max 30 chars

**Algorithm**:
```python
final_address = street  # Start with full street
button_text = f"{address} - {time} - {vendor} | {courier}"

# Reduce address character-by-character until fits
while len(button_text) > 30 and len(final_address) > 1:
    final_address = final_address[:-1]
    button_text = f"{final_address} - {time} - {vendor} | {courier}"
```

**Example**:
```
Original: "Wittelsbacherstraße - 19:30 - LR | Bee 1" (43 chars)
Final: "Wittelsbach - 19:30 - LR | Bee 1" (33 chars → still too long)
Final: "Wittelsbac - 19:30 - LR | Bee 1" (32 chars → still too long)
Final: "Wittelsba - 19:30 - LR | Bee 1" (31 chars → still too long)
Final: "Wittelsb - 19:30 - LR | Bee 1" (30 chars → ✓)
```

---

## Stats Summary

**Total Functions**: 23
- Configuration: 1 (`configure()`)
- Utilities: 4 (time, shortcuts, courier lookup, vendor string)
- Time Logic: 3 (recent orders, last confirmed, smart suggestions)
- Message Builders: 1 (`build_mdg_dispatch_text()`)
- Keyboard Factories: 10 (initial, time request, time submenu, reference options, same time, time picker, exact time, exact hour, combine keyboard, combine menu)
- Combine Orders: 4 (get assigned, generate group ID, get group color, get group orders)

**Total Lines**: 1,337

**Most Complex Function**: `build_mdg_dispatch_text()` (249-537, 289 lines) - Handles both order types, collapsed/expanded views, multi-vendor product display, address formatting, phone validation, district detection, email display, product list building

**Most Called Function**: `build_mdg_dispatch_text()` - Called by every MDG message operation in main.py (order creation, time requests, confirmations, assignments, status updates)

**Critical Dependencies**:
- utils.py: `build_status_lines()`, `get_district_from_address()`, `abbreviate_street()`, `format_phone_for_android()`, `safe_send_message()`, `safe_edit_message()`
- main.py: STATE (via configure()), RESTAURANT_SHORTCUTS (via configure()), DRIVERS (imported directly by get_courier_shortcut())

**Callback Actions Defined**: 20+
- Toggle: `toggle_details`
- Time Requests: `req_asap`, `req_time`, `req_custom`, `req_vendor`
- Time Selection: `time_ref`, `time_same`, `time_relative`, `smart_time`
- Time Pickers: `vendor_exact`, `exact_hour`, `exact_selected`, `time_plus`
- Combine: `combine_orders`, `combine_with`
- Navigation: `hide` (back button)

---

## Phase 1C Complete ✅

**mdg.py Analysis**: Complete documentation of all 23 MDG functions, 10 keyboard factories, time logic, product counting, address formatting, vendor matching, and combine orders system. Ready to proceed to Phase 1D (rg.py).

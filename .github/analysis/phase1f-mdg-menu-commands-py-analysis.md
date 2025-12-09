# Phase 1F: mdg_menu_commands.py Analysis

**File**: `mdg_menu_commands.py`
**Total Lines**: 179
**Purpose**: Menu command message builders for `/scheduled` and `/assigned` commands

---

## File Overview

This module handles MDG menu commands that display order lists:
- `/scheduled` - Shows confirmed orders awaiting assignment (last 5 hours)
- `/assigned` - Shows assigned orders awaiting delivery (grouped by courier)

**Key Features**:
- Full street names (no truncation, unlike MDG-ORD collapse)
- Time-based filtering (5-hour window for scheduled)
- Multi-vendor handling (expand into separate lines for assigned list)
- Courier grouping for assigned orders
- Clean list format optimized for quick overview

---

## Imports & Dependencies

### Standard Library (Lines 7-8)
```python
from datetime import timedelta, datetime
from typing import Dict, List
```

### Telegram Library (Line 8)
```python
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
```

### Project Modules (Imported Inside Functions)
```python
from utils import RESTAURANT_SHORTCUTS
```

**Note**: RESTAURANT_SHORTCUTS imported inside functions (lines 35, 112) to avoid circular import issues

---

## Function Catalog (3 Functions)

### 1. `build_scheduled_list_message(state_dict, now_func)` - Line 12
**Purpose**: Build list of scheduled orders (confirmed but not delivered)

**Parameters**:
- `state_dict`: STATE dictionary from main.py
- `now_func`: Function returning current datetime (for 5-hour cutoff)

**Filtering Logic** (Lines 29-58):

**Inclusion Criteria**:
1. ✅ Has `confirmed_times` dict (at least one vendor confirmed)
2. ✅ Status is NOT "delivered" (includes "assigned" and "new")
3. ✅ Created within last 5 hours

**Exclusion Criteria**:
- ❌ No confirmed_times
- ❌ Status is "delivered"
- ❌ Created before 5-hour cutoff
- ❌ Invalid/missing created_at

**Debug Logging** (Lines 32, 45-46, 57-58, 63):
```python
logger.info(f"SCHED DEBUG: Order {order_name} skipped - status is delivered")
logger.info(f"SCHED DEBUG: Order {order_name} skipped - invalid created_at format: {created_at}")
logger.info(f"SCHED DEBUG: Order {order_name} skipped - outside 5h window (created_at={created_at}, cutoff={cutoff})")
logger.info(f"SCHED DEBUG: Order {order_name} INCLUDED - status={status}, assigned_to={assigned_to}")
```

**Message Format**:
```
🗂️ Scheduled orders

02 - JS - 14:30 - Hauptstraße 5
26 - DD+LR - 14:45 - Bahnhofstraße 12
58 - HB - 15:00 - Ludwigstraße 15
```

**Components**:
- Order number (last 2 digits)
- Vendor(s) shortcut(s) (JS, DD+LR for multi-vendor)
- Confirmed time
- Full street name (NO truncation)

**Multi-Vendor Handling** (Lines 70-75):
```python
if len(vendors) > 1:
    # Multi-vendor: show combo with + separator
    vendor_str = "+".join([RESTAURANT_SHORTCUTS.get(v, v[:2].upper()) for v in vendors])
    # Use first vendor's time
    time = list(confirmed_times.values())[0]
```

**Single-Vendor Handling** (Lines 76-79):
```python
else:
    vendor_str = RESTAURANT_SHORTCUTS.get(vendors[0], vendors[0][:2].upper()) if vendors else "??"
    time = confirmed_times.get(vendors[0], "??:??") if vendors else "??:??"
```

**Sorting** (Line 87):
```python
scheduled.sort(key=lambda x: x["time"])  # Chronological order
```

**Empty State** (Lines 91-92):
```python
if not scheduled:
    return "🗂️ Scheduled orders\n\nNo scheduled orders in the last 5 hours."
```

**Returns**: Formatted message string

**Usage**: Called from main.py callback handler for `/scheduled` command

---

### 2. `build_assigned_list_message(state_dict, drivers_dict)` - Line 100
**Purpose**: Build list of assigned orders awaiting delivery

**Parameters**:
- `state_dict`: STATE dictionary from main.py
- `drivers_dict`: DRIVERS dictionary (maps courier name → user_id)

**Filtering Logic** (Lines 116-121):

**Inclusion Criteria**:
1. ✅ Has `assigned_to` field (courier assigned)
2. ✅ Status is NOT "delivered"

**Exclusion Criteria**:
- ❌ No assigned_to
- ❌ Status is "delivered"

**Message Format**:
```
📌 Assigned orders

LR - 19:30 - Hauptstraße 5  |  Bee 1
DD - 19:35 - Bahnhofstraße 12  |  Bee 1
JS - 19:45 - Ludwigstraße 15  |  Bee 2
```

**Components**:
- Vendor shortcut (NO order number, per requirements)
- Confirmed time
- Full street name (NO truncation)
- Courier name (right-aligned with `|` separator)

**Multi-Vendor Expansion** (Lines 141-150):
```python
if len(vendors) > 1:
    # Create SEPARATE LINE per vendor
    for vendor in vendors:
        vendor_short = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
        time = confirmed_times.get(vendor, "??:??")
        assigned.append({
            "vendor": vendor_short,
            "time": time,
            "street": street,
            "courier": courier_name
        })
```

**Example Multi-Vendor Expansion**:
```
Input: Order #26 (DD + LR, confirmed 19:30 and 19:35, assigned to Bee 1)

Output:
DD - 19:30 - Hauptstraße 5  |  Bee 1
LR - 19:35 - Hauptstraße 5  |  Bee 1
```

**Reason**: Each vendor has different pickup time, needs separate line for clarity

**Single-Vendor Handling** (Lines 151-157):
```python
else:
    vendor_short = RESTAURANT_SHORTCUTS.get(vendors[0], vendors[0][:2].upper()) if vendors else "??"
    time = confirmed_times.get(vendors[0], "??:??") if vendors else "??:??"
    assigned.append({...})
```

**Courier Name Lookup** (Lines 123-130):
```python
courier_name = None
for name, uid in drivers_dict.items():
    if uid == order["assigned_to"]:
        courier_name = name
        break
if not courier_name:
    courier_name = "??"
```

**Sorting** (Line 160):
```python
assigned.sort(key=lambda x: x["courier"])  # Group by courier
```

**Result**: All Bee 1 orders together, then Bee 2, etc.

**Empty State** (Lines 164-165):
```python
if not assigned:
    return "📌 Assigned orders\n\nNo assigned orders awaiting delivery."
```

**Returns**: Formatted message string

**Usage**: Called from main.py callback handler for `/assigned` command

---

### 3. `close_button_keyboard()` - Line 174
**Purpose**: Single close button for list messages

**Structure**:
```
[✖️ Close]
```

**Callback Format**: `close_temp`

**Returns**: InlineKeyboardMarkup

**Usage**: Attached to all list messages (scheduled, assigned) for cleanup

---

## Critical Patterns

### 1. Full Street Names (No Truncation)
**Design Decision**: List messages show FULL addresses, unlike MDG-ORD collapse

**Reason**: List views prioritize information density over space savings

**Comparison**:
- MDG-ORD collapse: "Ludwigstraße 1... (80333)"
- List messages: "Ludwigstraße 15"

**Implementation** (Lines 82, 136):
```python
street = order.get("customer", {}).get("address", "Unknown")
# No truncation logic - use full string
```

### 2. No Order Numbers in Assigned List
**Requirement**: Assigned list shows NO order numbers (lines 100-101 docstring)

**Reason**: Focus on pickup logistics (vendor + time + location), not order tracking

**Implementation**:
```python
# Scheduled: "02 - JS - 14:30 - Street"
# Assigned: "JS - 14:30 - Street  |  Bee 1"  (no order number)
```

### 3. Multi-Vendor Line Expansion
**Problem**: Multi-vendor orders have different pickup times per vendor

**Solution**: Expand into separate lines (lines 141-150)

**Example**:
```
Input Order:
- Vendors: ["dean & david", "Leckerolls"]
- Confirmed times: {"dean & david": "19:30", "Leckerolls": "19:35"}
- Address: "Hauptstraße 5"
- Assigned to: Bee 1

Output in /assigned:
DD - 19:30 - Hauptstraße 5  |  Bee 1
LR - 19:35 - Hauptstraße 5  |  Bee 1
```

**Contrast with /scheduled**: Shows combined "DD+LR - 19:30" (uses first vendor's time only)

### 4. Time-Based Filtering (5-Hour Window)
**Logic** (Lines 27-58):

```python
cutoff = now_func() - timedelta(hours=5)

for oid, order in state_dict.items():
    created_at = order.get("created_at")
    
    # Convert ISO string to datetime if needed
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
    
    if not created_at or created_at < cutoff:
        continue  # Skip orders older than 5 hours
```

**Purpose**: Keep scheduled list relevant (exclude old confirmed orders)

**Applies To**: `/scheduled` only (not `/assigned`)

### 5. Courier Grouping in Assigned List
**Sorting Key** (Line 160):
```python
assigned.sort(key=lambda x: x["courier"])
```

**Result**: All orders for same courier grouped together

**Example**:
```
📌 Assigned orders

LR - 19:30 - Street 1  |  Bee 1
DD - 19:35 - Street 2  |  Bee 1
JS - 19:45 - Street 3  |  Bee 1
HB - 20:00 - Street 4  |  Bee 2
PF - 20:15 - Street 5  |  Bee 2
```

**Benefit**: Easy to see which courier has how many orders

### 6. Status Filtering Differences

**Scheduled List** (Lines 44-46):
```python
if order.get("status") == "delivered":
    continue  # Skip delivered only
```
**Includes**: "new" and "assigned" orders

**Assigned List** (Lines 119-121):
```python
if not order.get("assigned_to"):
    continue  # Skip unassigned
if order.get("status") == "delivered":
    continue  # Skip delivered
```
**Includes**: "assigned" only (not "new" or "delivered")

### 7. Lazy Import Pattern
**All imports inside functions** (Lines 35, 112):

```python
def build_scheduled_list_message(...):
    from utils import RESTAURANT_SHORTCUTS  # Import inside function
```

**Reason**: Avoid circular imports (main.py imports this module, this module needs utils)

---

## Data Flow Diagrams

### /scheduled Command Flow
```
User sends /scheduled in MDG
  ↓
main.py: handle_telegram_command()
  ↓
build_scheduled_list_message(STATE, now)
  ├→ Filter: confirmed_times exists
  ├→ Filter: status != "delivered"
  ├→ Filter: created_at within 5 hours
  ├→ Extract: order_num, vendors, time, street
  ├→ Multi-vendor: combine with "+" (DD+LR)
  ├→ Single-vendor: use vendor shortcut
  ├→ Sort by time (chronological)
  └→ Format: "02 - JS - 14:30 - Hauptstraße 5"
  ↓
close_button_keyboard()
  └→ [✖️ Close] button
  ↓
Send message to MDG with keyboard
```

### /assigned Command Flow
```
User sends /assigned in MDG
  ↓
main.py: handle_telegram_command()
  ↓
build_assigned_list_message(STATE, DRIVERS)
  ├→ Filter: assigned_to exists
  ├→ Filter: status != "delivered"
  ├→ Lookup courier name from DRIVERS dict
  ├→ Extract: vendors, confirmed_times, street
  ├→ Multi-vendor: CREATE SEPARATE LINE PER VENDOR
  │   └→ Each vendor gets own line with its time
  ├→ Single-vendor: single line
  ├→ Sort by courier (group orders by courier)
  └→ Format: "JS - 14:30 - Hauptstraße 5  |  Bee 1"
  ↓
close_button_keyboard()
  └→ [✖️ Close] button
  ↓
Send message to MDG with keyboard
```

---

## Usage Map (What Calls What)

### Called By main.py:
- `build_scheduled_list_message()` - `/scheduled` command handler
- `build_assigned_list_message()` - `/assigned` command handler
- `close_button_keyboard()` - Attached to both list messages

### Internal Dependencies:
```
build_scheduled_list_message()
  └→ utils.RESTAURANT_SHORTCUTS (imported lazily)

build_assigned_list_message()
  └→ utils.RESTAURANT_SHORTCUTS (imported lazily)

close_button_keyboard()
  └→ (no dependencies)
```

---

## Message Format Examples

### Scheduled List (Empty)
```
🗂️ Scheduled orders

No scheduled orders in the last 5 hours.
```

### Scheduled List (With Orders)
```
🗂️ Scheduled orders

02 - JS - 14:30 - Hauptstraße 5
26 - DD+LR - 14:45 - Bahnhofstraße 12
58 - HB - 15:00 - Ludwigstraße 15
```

### Assigned List (Empty)
```
📌 Assigned orders

No assigned orders awaiting delivery.
```

### Assigned List (With Orders)
```
📌 Assigned orders

LR - 19:30 - Hauptstraße 5  |  Bee 1
DD - 19:35 - Hauptstraße 5  |  Bee 1
JS - 19:45 - Ludwigstraße 15  |  Bee 2
HB - 20:00 - Bahnhofstraße 12  |  Bee 3
```

---

## Constants & Mappings

### RESTAURANT_SHORTCUTS (from utils.py, imported inside functions)
```python
{
    "Julis Spätzlerei": "JS",
    "dean & david": "DD",
    "Leckerolls": "LR",
    "Hello Burrito": "HB",
    ...
}
```

**Usage**: Convert full vendor names to 2-letter shortcuts for compact display

### DRIVERS (passed as parameter from main.py)
```python
{
    "Bee 1": 383910036,
    "Bee 2": 6389671774,
    "Bee 3": 8483568436
}
```

**Usage**: Reverse lookup to get courier name from user_id

---

## Critical Logic Deep Dives

### 5-Hour Window Calculation (Lines 27-28)
```python
cutoff = now_func() - timedelta(hours=5)
# Example: Current time is 20:00
# Cutoff = 15:00
# Orders created after 15:00 are included
```

**Why 5 Hours**: Typical order lifecycle (confirmation → assignment → delivery) rarely exceeds 5 hours

**Application**: Only scheduled list (assigned list has no time filter)

### created_at ISO String Conversion (Lines 50-54)
```python
# Shopify orders store created_at as ISO string: "2024-12-06T14:30:00Z"
# Must convert to datetime for comparison
if isinstance(created_at, str):
    try:
        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
    except:
        continue  # Skip if invalid format
```

**Why Needed**: Smoothr orders use datetime objects, Shopify uses strings

### Multi-Vendor Time Selection (Lines 70-75)
**Problem**: Multi-vendor order has multiple confirmed times

**Scheduled List Solution**: Use first vendor's time only
```python
if len(vendors) > 1:
    time = list(confirmed_times.values())[0]  # Take first time
```

**Assigned List Solution**: Show separate line per vendor
```python
if len(vendors) > 1:
    for vendor in vendors:
        time = confirmed_times.get(vendor, "??:??")  # Each vendor's time
        assigned.append(...)  # Separate entry
```

**Reasoning**:
- Scheduled: Quick overview, don't need per-vendor times
- Assigned: Courier needs exact pickup time for each vendor

### Order Number Extraction (Lines 66-67)
```python
order_num = order.get("name", "")[-2:] if len(order.get("name", "")) >= 2 else order.get("name", "??")
```

**Logic**:
- If name length >= 2: Take last 2 chars ("dishbee #26" → "26")
- Else: Use full name or "??"

**Defensive Coding**: Handles edge cases (missing name, single-char name)

### Courier Name Lookup (Lines 123-130)
```python
courier_name = None
for name, uid in drivers_dict.items():
    if uid == order["assigned_to"]:
        courier_name = name
        break
if not courier_name:
    courier_name = "??"
```

**Why Manual Loop**: DRIVERS dict is keyed by name, need reverse lookup by user_id

**Alternative Approach**: Could use dict comprehension, but loop is clearer

---

## Stats Summary

**Total Functions**: 3
- Message builders: 2 (`build_scheduled_list_message`, `build_assigned_list_message`)
- Keyboard factory: 1 (`close_button_keyboard`)

**Total Lines**: 179

**Most Complex Function**: `build_scheduled_list_message()` (12-98, 87 lines) - Handles 5-hour filtering, ISO string conversion, multi-vendor combining, sorting, formatting

**Debug Logging**: Extensive in `build_scheduled_list_message()` (4 log statements for filter decisions)

**Critical Dependencies**:
- utils.py: `RESTAURANT_SHORTCUTS` (lazy import)
- main.py: `STATE` dict, `DRIVERS` dict (passed as parameters)

**Command Handlers**: 2
- `/scheduled` → `build_scheduled_list_message()`
- `/assigned` → `build_assigned_list_message()`

**Callback Actions Defined**: 1
- `close_temp` - Close list message button

**Async Functions**: 0 (all message builders are synchronous)

---

## Design Decisions

### 1. No Truncation
**Decision**: Show full street names in list messages

**Rationale**: List views have more horizontal space than MDG-ORD collapse

**Trade-off**: Longer messages, but better readability

### 2. Separate Lines for Multi-Vendor (Assigned Only)
**Decision**: Expand multi-vendor orders into separate lines in `/assigned`

**Rationale**: Each vendor has different pickup time, courier needs per-vendor clarity

**Contrast**: `/scheduled` combines vendors (DD+LR) for compactness

### 3. No Order Numbers in Assigned List
**Decision**: Omit order numbers from `/assigned` format

**Rationale**: Focus on logistics (vendor, time, location), not tracking

**Trade-off**: Can't reference specific orders, but cleaner display

### 4. 5-Hour Window for Scheduled
**Decision**: Only show orders created in last 5 hours

**Rationale**: Keep list relevant, exclude stale confirmed orders

**Trade-off**: Very old orders disappear, but they're likely irrelevant

### 5. Courier Grouping for Assigned
**Decision**: Sort assigned list by courier name

**Rationale**: Easy to see order distribution across couriers

**Trade-off**: Not chronological, but grouping more useful

---

## Phase 1F Complete ✅

**mdg_menu_commands.py Analysis**: Complete documentation of all 3 menu command functions (/scheduled and /assigned message builders, close button keyboard). Comprehensive coverage of filtering logic, multi-vendor handling, format differences, and design decisions. Ready to proceed to Phase 1G (redis_state.py) and Phase 1H (ocr.py).

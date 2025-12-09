# Phase 1E: upc.py Analysis

**File**: `upc.py`
**Total Lines**: 1,169
**Purpose**: User Private Chat (UPC) functions for courier assignment, delivery tracking, and CTA interactions

---

## File Overview

This module handles all UPC-related functionality:
- Courier assignment system (MDG buttons + private chat messages)
- Live courier detection from MDG administrators
- Assignment message building with group indicators
- CTA keyboards (navigate, problem, delay, call, delivered)
- Delivery completion and undelivery workflows
- Problem handling (delay requests, restaurant communication)
- Group order management (update UPC messages when group changes)

**Critical Pattern**: UPC is the final stage of order lifecycle - after vendors confirm times, couriers receive detailed assignment messages with actionable buttons.

---

## Imports & Configuration

### Standard Library (Lines 4-6)
```python
asyncio
datetime, timedelta
zoneinfo.ZoneInfo
```

### Telegram Library (Line 7)
```python
InlineKeyboardMarkup, InlineKeyboardButton
```

### Project Modules (Line 8)
```python
from utils import logger, COURIER_MAP, DISPATCH_MAIN_CHAT_ID, VENDOR_GROUP_MAP, RESTAURANT_SHORTCUTS,
    safe_send_message, safe_edit_message, safe_delete_message, get_error_description, 
    format_phone_for_android, send_status_message
```

### Module-Level State (Lines 11-27)
- **TIMEZONE**: `ZoneInfo("Europe/Berlin")` - Passau timezone
- **STATE**: `None` - Set via `configure()` from main.py (with circular import guard)
- **bot**: `None` - Telegram Bot instance reference

---

## Function Catalog (23 Functions)

### 1. `now()` - Line 13
**Purpose**: Get current time in Passau timezone (Europe/Berlin)

**Returns**: `datetime` object with timezone awareness

**Usage**: Timestamps for status history, message formatting, group IDs

---

### 2. `configure(state_ref, bot_ref)` - Line 29
**Purpose**: Configure module-level STATE and bot reference

**Parameters**:
- `state_ref`: Reference to main.py STATE dict
- `bot_ref`: Telegram Bot instance (optional)

**Critical Guard** (Lines 34-38):
```python
if STATE is not None:
    logger.warning("STATE already set. Ignoring reconfiguration attempt")
    return
```

**Reason**: Prevents circular import issues - STATE should only be set once during app initialization

**Called By**: main.py line 176 during app startup

---

### 3. `check_all_vendors_confirmed(order_id)` - Line 44
**Purpose**: Check if ALL vendors have confirmed their times for an order

**Parameters**:
- `order_id`: Order identifier

**Logic**:
1. Get order from STATE
2. Get vendors list and confirmed_times dict
3. Check each vendor in confirmed_times
4. Return True if all vendors present, False otherwise

**Debug Logs** (Lines 58-69):
- Shows vendors list
- Shows confirmed_times dict
- Per-vendor confirmation status
- Final result with vendor count

**Returns**: Boolean

**Usage**: Called before showing assignment buttons in MDG

---

### 4. `mdg_assignment_keyboard(order_id)` - Line 72
**Purpose**: Build assignment buttons for MDG after all vendors confirm

**Structure**:
```
[👈 Assign to myself]
[Assign to 👉]
[📌 Assigned orders]  (conditional)
```

**Assigned Orders Button Logic** (Lines 82-88):
- Scans all orders in STATE
- Shows button only if at least 1 order is assigned (status != "delivered")
- NOT per-order check - global STATE scan

**Callback Formats**:
- Assign myself: `assign_myself|{order_id}`
- Assign to menu: `assign_to_menu|{order_id}`
- Assigned orders: `show_assigned|{order_id}|{timestamp}`

**Returns**: InlineKeyboardMarkup

**Usage**: Called from main.py after all vendors confirm times

---

### 5. `mdg_unassign_keyboard(order_id)` - Line 96
**Purpose**: Build single Unassign button for MDG-CONF after assignment

**Structure**:
```
[🔁 Unassign]
```

**Callback Format**: `unassign|{order_id}`

**Returns**: InlineKeyboardMarkup

**Usage**: Replaces assignment buttons in MDG-CONF message after courier assigned

---

### 6. `get_mdg_couriers(bot)` - Line 110 (async)
**Purpose**: Get live courier list from MDG administrators + fallback to COURIER_MAP

**Logic**:
1. Call `bot.get_chat_administrators(DISPATCH_MAIN_CHAT_ID)`
2. Filter out bots and non-courier users
3. Extract user_id, username, first_name
4. If API call fails: Fallback to COURIER_MAP environment variable
5. Always prioritize live MDG data over static config

**Returns**: List of dicts with courier info:
```python
[
    {"user_id": 123, "username": "Bee 1", "first_name": "John"},
    {"user_id": 456, "username": "Bee 2", "first_name": "Jane"},
    ...
]
```

**Debug Logs** (Lines 154-176):
- API call status
- Courier count from MDG
- Fallback trigger
- COURIER_MAP usage

**Usage**: Called by `courier_selection_keyboard()` to build assign menu

---

### 7. `get_couriers_from_map()` - Line 167
**Purpose**: Convert COURIER_MAP to courier list format (fallback helper)

**Logic**:
```python
# COURIER_MAP format: {user_id: {"username": "Bee 1", "is_courier": True}}
# Output: [{"user_id": 123, "username": "Bee 1"}]
```

**Returns**: List of courier dicts

**Usage**: Fallback when `get_mdg_couriers()` API call fails

---

### 8. `courier_selection_keyboard(order_id, bot)` - Line 179 (async)
**Purpose**: Build courier selection menu for "Assign to 👉" button

**Structure**:
```
[Bee 1]
[Bee 2]
[Bee 3]
[Other Courier 1]
[Other Courier 2]
[← Back]
```

**Priority Logic** (Lines 205-214):
1. Show "Bee 1", "Bee 2", "Bee 3" first (priority couriers)
2. Then show all other couriers
3. Maintains order from priority_names list

**Callback Format**: `assign_to_user|{order_id}|{user_id}`

**Returns**: InlineKeyboardMarkup

**Usage**: Called from main.py after user clicks "Assign to 👉"

---

### 9. `update_group_upc_messages(group_id)` - Line 240 (async)
**Purpose**: Update UPC assignment messages for all orders in a group

**Called When**:
- New order joins group (group size changes)
- Order delivered (positions need recalculation)
- Group dissolved (group indicator removed)

**Logic**:
1. Get all orders in group via `get_group_orders()`
2. For each order: Skip if not assigned or no UPC message
3. Rebuild assignment message with updated group info
4. Edit UPC message with new text

**Updated Info**:
- Group position (1, 2, 3...)
- Group total size
- Group color emoji

**Returns**: None (async function, updates messages directly)

**Usage**: Called from main.py group management callbacks

---

### 10. `send_assignment_to_private_chat(order_id, user_id)` - Line 300 (async)
**Purpose**: Send order details to assigned courier's private chat

**Logic**:
1. Get order from STATE
2. Build assignment message via `build_assignment_message()`
3. Build CTA keyboard via `assignment_cta_keyboard()`
4. Send message to user_id (courier's private chat)
5. Store message_id in `order["upc_assignment_message_id"]`
6. Add to status_history: "assigned" entry with timestamp

**Message Format**: See `build_assignment_message()` for details

**Returns**: None (async function)

**Usage**: Called from main.py after user clicks assign button

---

### 11. `update_mdg_with_assignment(order_id, assigned_user_id)` - Line 365 (async)
**Purpose**: Update MDG and RG messages after assignment

**Updates**:
1. **MDG-CONF**: Edit with `build_assignment_confirmation_message()` + unassign keyboard
2. **Status**: Add "assigned" entry to status_history
3. **Result**: MDG shows assigned courier, RG shows assignment status

**Called By**: main.py assignment callbacks (assign_myself, assign_to_user)

**Returns**: None (async function)

---

### 12. `build_assignment_message(order)` - Line 414
**Purpose**: Build courier assignment message for private chat

**Format**:
```
[Status lines from build_status_lines()]
────────────────

[Group indicator if grouped]
🕒 19:30 ➞ 👩‍🍳 LR (3)
🕒 19:35 ➞ 🧑‍🍳 JS (2)

🗺️ [Ludwigstraße 15 (80333)](maps_link)

👤 Customer Name

☎️ +491234567890

❕ Note: {text} (optional)
❕ Tip: 2.50€ (optional)
❕ Cash: 18.50€ (optional)
```

**Key Features**:
1. **Status line modification**: If assigned, shows "👇 Assigned order #{num}"
2. **Separator**: "────────────────" with blank line
3. **Group indicator**: "{color} Group: {position}/{total}" if order in group
4. **Restaurant info**: New format - "🕒 {time} ➞ {chef_emoji} {shortcut} ({count})"
5. **Address**: Clickable map link (same as MDG)
6. **Phone**: Formatted via `format_phone_for_android()` (no label)
7. **Optional info**: Note, Tip, Cash (only if NOT delivered)
8. **Chef emojis**: Rotating variations for visual variety

**Product Count Logic** (Lines 527-544):
- Sums quantities from vendor_items
- Extracts from "2 x Product" or "- 2 x Product" format
- Handles both Shopify (with dash) and Smoothr (no dash)

**Returns**: Formatted message string

**Usage**: Called for initial assignment, status updates, group updates

---

### 13. `assignment_cta_keyboard(order_id)` - Line 582
**Purpose**: Build CTA buttons for assigned orders in private chats

**Structure** (Not Delivered):
```
[🧭 Navigate]
[🚩 Problem]
[☎️ Call restaurant]  (multi-vendor only)
[✅ Delivered]
```

**Structure** (Delivered):
```
[🔁 Undeliver]
```

**Navigate Button**:
- URL button with Google Maps directions
- Bicycling mode
- Uses original_address for accuracy

**Problem Button**:
- Callback button opening submenu
- Shows delay + restaurant call options

**Call Restaurant Button** (Lines 606-610):
- Only shown for multi-vendor orders
- Opens vendor selection menu
- Single-vendor: No button (call option in Problem menu)

**Delivered Button**:
- Confirms delivery completion
- Triggers `handle_delivery_completion()`

**Undeliver Button**:
- Only shown after delivery
- Allows reverting delivered status
- Triggers `handle_undelivery()`

**Callback Formats**:
- Problem: `show_problem_menu|{order_id}`
- Call restaurant: `call_restaurant_menu|{order_id}`
- Delivered: `confirm_delivered|{order_id}`
- Undeliver: `undeliver|{order_id}`

**Returns**: InlineKeyboardMarkup

**Usage**: Called for all UPC message edits (initial assignment, updates)

---

### 14. `problem_options_keyboard(order_id)` - Line 617
**Purpose**: Build problem submenu after courier clicks "🚩 Problem"

**Structure** (Single-Vendor):
```
[⏰ Delay order]
[☎️ Call restaurant]
[← Back]
```

**Structure** (Multi-Vendor):
```
[⏰ Delay order]
[← Back]
```

**Logic**:
- Single-vendor: Show both delay + call buttons
- Multi-vendor: Only delay button (call button already in main CTA keyboard)

**Callback Formats**:
- Delay: `delay_order|{order_id}`
- Call: `call_single_vendor|{order_id}|{vendor}`
- Back: `back_to_cta|{order_id}`

**Returns**: InlineKeyboardMarkup

**Usage**: Called from main.py after user clicks "🚩 Problem"

---

### 15. `handle_delivery_completion(order_id, user_id)` - Line 665 (async)
**Purpose**: Handle order delivery confirmation

**Logic**:
1. Update STATE: `status = "delivered"`
2. Add to status_history: "delivered" entry with timestamp
3. Update MDG message: Remove assignment buttons, show delivered status
4. Update RG messages: Show delivered status
5. Update UPC message: Show "Undeliver" button only
6. Send confirmation to MDG: "🔖 {order_num} was delivered by {courier_name} at {time}"
7. If order in group: Call `update_group_on_delivery()` to recalculate positions

**Returns**: None (async function)

**Usage**: Called from main.py after courier clicks "✅ Delivered"

---

### 16. `handle_undelivery(order_id, user_id)` - Line 759 (async)
**Purpose**: Handle delivery reversal (undo delivered status)

**Logic**:
1. Update STATE: `status = "assigned"` (restore previous state)
2. Remove last "delivered" entry from status_history
3. Update MDG message: Restore assignment buttons, remove delivered status
4. Update RG messages: Remove delivered status
5. Update UPC message: Restore full CTA keyboard
6. Send notification to MDG: "🔖 {order_num} was undelivered by {courier_name} at {time}"

**Returns**: None (async function)

**Usage**: Called from main.py after courier clicks "🔁 Undeliver"

---

### 17. `update_group_on_delivery(delivered_order_id)` - Line 848 (async)
**Purpose**: Update group when an order is delivered

**Logic**:
1. Remove group fields from delivered order (group_id, group_color, group_position)
2. Get remaining orders in group
3. If only 1 order remains: Dissolve group (remove group fields from last order, update UPC message)
4. If 2+ orders remain: Recalculate positions, update all UPC messages

**Returns**: None (async function)

**Usage**: Called from `handle_delivery_completion()` if order is in group

---

### 18. `show_delay_options(order_id, user_id)` - Line 919 (async)
**Purpose**: Show delay options menu after courier clicks "⏰ Delay order"

**Structure** (Single-Vendor):
```
[🕒 Time picker]
[← Back]
```

**Structure** (Multi-Vendor):
```
[Select restaurant first]
[← Back]
```

**Logic**:
- Single-vendor: Show time picker directly
- Multi-vendor: Show restaurant selection menu (must pick which vendor to delay)

**Callback Formats**:
- Time picker: `delay_time_picker|{order_id}`
- Select restaurant: `delay_select_restaurant|{order_id}`
- Back: `back_to_problem|{order_id}`

**Returns**: None (async function, sends message)

**Usage**: Called from main.py after user clicks "⏰ Delay order"

---

### 19. `show_delay_time_picker(order_id, user_id, vendor)` - Line 963 (async)
**Purpose**: Show exact time picker for delay request

**Structure**:
```
Current time: 19:30
Pick new time:

[19] [20] [21]
[22] [23]
[← Back]
```

**Logic**:
1. Get current hour/minute
2. If past 57 minutes: Start from next hour
3. Show hours from start_hour to 23 (midnight)
4. 3 hours per row

**Callback Format**: `delay_exact_hour|{order_id}|{hour}|{vendor or 'all'}`

**Returns**: None (async function, sends message)

**Usage**: Called from main.py after user picks delay option

---

### 20. `show_restaurant_selection(order_id, user_id)` - Line 1029 (async)
**Purpose**: Show restaurant selection for multi-vendor delay

**Structure**:
```
[👩‍🍳 LR]
[🧑‍🍳 DD]
[← Back]
```

**Logic**:
1. Get vendors from order
2. Show one button per vendor with chef emoji + shortcut
3. Use rotating chef emojis for variety

**Callback Format**: `delay_select_vendor|{order_id}|{vendor}`

**Returns**: None (async function, sends message)

**Usage**: Called from `show_delay_options()` for multi-vendor orders

---

### 21. `send_delay_request_to_restaurants(order_id, new_time, user_id, vendor)` - Line 1058 (async)
**Purpose**: Send delay request to vendor(s)

**Parameters**:
- `order_id`: Order identifier
- `new_time`: New requested time (HH:MM)
- `user_id`: Courier user_id for confirmation
- `vendor`: Specific vendor (multi-vendor) or None (single-vendor, send to all)

**Message Format**: 
```
We have a delay, if possible prepare {order_num} at {new_time}. 
If not, please keep it warm.
```

**Logic**:
1. Determine vendors to notify (specific or all)
2. Add "delay_sent" entry to status_history
3. Send message to each vendor's RG with restaurant response keyboard
4. Update UPC message with new status
5. Send confirmation to courier: "✅ Delay request for 🔖 {num} sent to {vendors}"
6. Auto-delete confirmation after 20 seconds

**Returns**: None (async function)

**Usage**: Called from main.py after courier picks delay time

---

### 22. `initiate_restaurant_call(order_id, vendor, user_id)` - Line 1138 (async)
**Purpose**: Initiate call to restaurant (placeholder for future Telegram integration)

**Current Implementation**:
- Sends message: "📞 Please call {vendor_shortcut} directly."
- Notes that automatic calling will be available when restaurant accounts are set up

**Future Implementation**:
- Will integrate with Telegram calling API
- Direct in-app calling to restaurant accounts

**Returns**: None (async function)

**Usage**: Called from main.py after courier clicks call button

---

### 23. `get_assignment_status(order_id)` - Line 1155
**Purpose**: Get current assignment status of an order

**Returns**: 
- "assigned_to_{courier_name}" if assigned
- "new" / "delivered" based on order status
- "unknown" if order not found

**Usage**: Status checking, logging, debugging

---

## Critical Patterns

### 1. STATE Configuration Guard
**Problem**: Circular imports can cause STATE to be reconfigured multiple times

**Solution** (Lines 34-38):
```python
def configure(state_ref, bot_ref=None):
    global STATE, bot
    
    if STATE is not None:
        logger.warning("STATE already set. Ignoring reconfiguration attempt")
        return
    
    STATE = state_ref
    if bot_ref:
        bot = bot_ref
```

**Critical**: Prevents STATE corruption during module imports

### 2. Live Courier Detection + Fallback
**Two-tier system**:

```python
async def get_mdg_couriers(bot):
    try:
        # TIER 1: Live query MDG administrators
        admins = await bot.get_chat_administrators(DISPATCH_MAIN_CHAT_ID)
        couriers = [extract_courier_info(admin) for admin in admins if is_courier(admin)]
        return couriers
    except Exception:
        # TIER 2: Fallback to COURIER_MAP environment variable
        return get_couriers_from_map()
```

**Benefits**:
- Always current (reflects MDG membership changes)
- Graceful degradation (fallback ensures assignment works)
- No manual config updates needed (auto-detects new couriers)

### 3. Priority Courier Ordering
**Always show Bee 1, Bee 2, Bee 3 first** (Lines 205-214):

```python
priority_names = ["Bee 1", "Bee 2", "Bee 3"]

# Add priority couriers first
for priority_name in priority_names:
    for courier in couriers:
        if courier["username"] == priority_name:
            buttons.append([InlineKeyboardButton(...)])
            break

# Then add other couriers
for courier in couriers:
    if courier["username"] not in priority_names:
        buttons.append([InlineKeyboardButton(...)])
```

**Result**: Consistent button order, key couriers always accessible

### 4. Group Indicator in UPC Messages
**Dynamic group info** (Lines 483-494):

```python
if order.get("group_id"):
    from mdg import get_group_orders
    
    group_color = order.get("group_color", "🔵")
    group_position = order.get("group_position", 1)
    group_id = order["group_id"]
    
    group_orders = get_group_orders(STATE, group_id)
    group_total = len(group_orders)
    
    group_header = f"{group_color} Group: {group_position}/{group_total}\n\n"
```

**Example**: "🟣 Group: 2/3" → Courier knows this is 2nd of 3 grouped orders

### 5. Conditional CTA Buttons
**Multi-vendor vs Single-vendor** (Lines 606-610):

```python
# Call restaurant button - only for multi-vendor
if len(order.get("vendors", [])) > 1:
    call_restaurant = InlineKeyboardButton(
        "☎️ Call restaurant",
        callback_data=f"call_restaurant_menu|{order_id}"
    )
    buttons.append([call_restaurant])
```

**Reason**: Multi-vendor needs restaurant selection menu, single-vendor can call directly from Problem menu

### 6. Auto-Delete Confirmations
**20-second auto-delete** (Lines 1127-1129):

```python
if confirm_msg:
    loop = asyncio.get_event_loop()
    loop.call_later(20, lambda: asyncio.create_task(safe_delete_message(user_id, confirm_msg.message_id)))
```

**Purpose**: Keep courier chat clean, auto-remove temporary confirmations

### 7. Delivery → Group Update Chain
**Cascade effect**:

```python
handle_delivery_completion(order_id, user_id)
  ↓
If order in group:
  update_group_on_delivery(delivered_order_id)
    ↓
    Remove group fields from delivered order
    ↓
    If 1 order remains:
      Dissolve group (remove fields, update UPC)
    Else:
      Recalculate positions, update all UPC messages
```

**Result**: Group positions always accurate, no stale indicators

### 8. Status History Tracking
**Every action appends to status_history**:

```python
order["status_history"].append({
    "type": "assigned",
    "assigned_to": user_id,
    "assigned_by": assigner_user_id,
    "timestamp": now()
})

order["status_history"].append({
    "type": "delay_sent",
    "vendors": vendors_to_notify,
    "time": new_time,
    "timestamp": now()
})

order["status_history"].append({
    "type": "delivered",
    "delivered_by": user_id,
    "time": now().strftime('%H:%M'),
    "timestamp": now()
})
```

**Used By**: `build_status_lines()` in utils.py to show timeline in messages

---

## Usage Map (What Calls What)

### Called By main.py (Webhook/Callback Handlers):
- `check_all_vendors_confirmed()` - Before showing assignment buttons
- `mdg_assignment_keyboard()` - After all vendors confirm
- `mdg_unassign_keyboard()` - After assignment complete
- `courier_selection_keyboard()` - After "Assign to 👉" clicked
- `send_assignment_to_private_chat()` - After assign button clicked
- `update_mdg_with_assignment()` - After assignment complete
- `assignment_cta_keyboard()` - For all UPC message edits
- `problem_options_keyboard()` - After "🚩 Problem" clicked
- `handle_delivery_completion()` - After "✅ Delivered" clicked
- `handle_undelivery()` - After "🔁 Undeliver" clicked
- `show_delay_options()` - After "⏰ Delay order" clicked
- `show_delay_time_picker()` - After delay option selected
- `show_restaurant_selection()` - For multi-vendor delay
- `send_delay_request_to_restaurants()` - After delay time picked
- `initiate_restaurant_call()` - After call button clicked

### Internal Call Chains:
```
send_assignment_to_private_chat()
  ├→ build_assignment_message()
  │   ├→ build_status_lines() (from utils.py)
  │   └→ format_phone_for_android() (from utils.py)
  └→ assignment_cta_keyboard()

handle_delivery_completion()
  ├→ update_mdg_with_assignment()
  ├→ build_assignment_message()
  ├→ assignment_cta_keyboard()
  └→ update_group_on_delivery()
      └→ get_group_orders() (from mdg.py)
      └→ build_assignment_message()
      └→ assignment_cta_keyboard()

update_group_upc_messages()
  ├→ get_group_orders() (from mdg.py)
  ├→ build_assignment_message()
  └→ assignment_cta_keyboard()

courier_selection_keyboard()
  └→ get_mdg_couriers()
      └→ get_couriers_from_map() (fallback)

send_delay_request_to_restaurants()
  ├→ restaurant_response_keyboard() (from rg.py)
  ├→ build_assignment_message()
  ├→ assignment_cta_keyboard()
  └→ get_error_description() (from utils.py)
```

---

## Data Flow Diagrams

### Assignment Flow (All Vendors Confirmed)
```
All vendors confirm times
  ↓
main.py: check_all_vendors_confirmed(order_id)
  └→ Returns True
  ↓
Update MDG message with assignment buttons
mdg_assignment_keyboard(order_id)
  ├→ Scan STATE for assigned orders
  └→ Build: [Assign to myself] [Assign to 👉] [Assigned orders]
  ↓
User clicks "👈 Assign to myself" or "Assign to 👉"
  ↓
If "Assign to myself":
  assign_myself|{order_id} callback
  ↓ set assigned_to = user_id
  
If "Assign to 👉":
  assign_to_menu|{order_id} callback
  ↓
  courier_selection_keyboard(order_id, bot)
    ├→ get_mdg_couriers(bot)
    │   ├→ Live query MDG admins
    │   └→ Fallback to COURIER_MAP
    └→ Build courier buttons (priority first)
  ↓
  User clicks courier name
  ↓
  assign_to_user|{order_id}|{user_id} callback
  ↓ set assigned_to = user_id
  ↓
send_assignment_to_private_chat(order_id, user_id)
  ├→ build_assignment_message(order)
  │   ├→ Status lines
  │   ├→ Group indicator (if grouped)
  │   ├→ Restaurant info with times/counts
  │   ├→ Customer info + address + phone
  │   └→ Optional: note/tip/cash
  ├→ assignment_cta_keyboard(order_id)
  │   └→ [Navigate] [Problem] [Call restaurant] [Delivered]
  └→ Send to user_id private chat
  ↓
Store upc_assignment_message_id in STATE
  ↓
update_mdg_with_assignment(order_id, user_id)
  ├→ Edit MDG-CONF with assignment confirmation
  └→ Show mdg_unassign_keyboard: [🔁 Unassign]
```

### Delivery Completion Flow
```
Courier clicks "✅ Delivered" in UPC
  ↓
main.py: confirm_delivered|{order_id} callback
  ↓
handle_delivery_completion(order_id, user_id)
  ├→ Update STATE: status = "delivered"
  ├→ Add status_history entry: type="delivered"
  ├→ Update MDG message (remove buttons, show delivered)
  ├→ Update RG messages (show delivered)
  ├→ Update UPC message (show only [Undeliver] button)
  ├→ Send MDG notification: "🔖 {num} delivered by {courier}"
  └→ If order in group:
      update_group_on_delivery(delivered_order_id)
        ├→ Remove group fields from delivered order
        ├→ Get remaining orders in group
        └→ If 1 order remains:
            Dissolve group
              ├→ Remove group fields from last order
              └→ Update last order UPC message
        └→ If 2+ orders remain:
            Recalculate positions
              ├→ Update group_position for each order
              └→ Update all UPC messages
```

### Problem → Delay Request Flow
```
Courier clicks "🚩 Problem" in UPC
  ↓
main.py: show_problem_menu|{order_id} callback
  ↓
problem_options_keyboard(order_id)
  └→ [⏰ Delay order] [☎️ Call restaurant] [← Back]
  ↓
Courier clicks "⏰ Delay order"
  ↓
main.py: delay_order|{order_id} callback
  ↓
show_delay_options(order_id, user_id)
  ├→ Check vendor count
  └→ If single-vendor:
      Show: [🕒 Time picker] [← Back]
  └→ If multi-vendor:
      Show: [Select restaurant first] [← Back]
  ↓
If single-vendor:
  Courier clicks "🕒 Time picker"
  ↓
  main.py: delay_time_picker|{order_id} callback
  ↓
  show_delay_time_picker(order_id, user_id, vendor=None)
    └→ Show hour buttons (current to 23)
    
If multi-vendor:
  Courier clicks "Select restaurant first"
  ↓
  main.py: delay_select_restaurant|{order_id} callback
  ↓
  show_restaurant_selection(order_id, user_id)
    └→ Show vendor buttons with chef emojis
  ↓
  Courier clicks vendor
  ↓
  main.py: delay_select_vendor|{order_id}|{vendor} callback
  ↓
  show_delay_time_picker(order_id, user_id, vendor)
    └→ Show hour buttons
  ↓
[Both paths converge]
Courier clicks hour
  ↓
main.py: delay_exact_hour|{order_id}|{hour}|{vendor} callback
  ↓
Show minute picker (00-57 in 3-min intervals)
  ↓
Courier clicks minute
  ↓
main.py: delay_exact_selected|{order_id}|{time}|{vendor} callback
  ↓
send_delay_request_to_restaurants(order_id, new_time, user_id, vendor)
  ├→ Add status_history entry: type="delay_sent"
  ├→ Send message to RG with restaurant_response_keyboard
  ├→ Update UPC message with new status
  ├→ Send confirmation to courier
  └→ Auto-delete confirmation after 20 seconds
```

### Group Update Flow
```
Order joins group OR Order delivered from group
  ↓
update_group_upc_messages(group_id)
  ├→ get_group_orders(STATE, group_id)
  └→ For each order in group:
      ├→ Skip if not assigned or no UPC message
      ├→ build_assignment_message(order)
      │   └→ Includes updated group indicator
      ├→ assignment_cta_keyboard(order_id)
      └→ safe_edit_message(user_id, message_id, text, keyboard)
```

---

## Constants & Mappings

### COURIER_MAP (from utils.py, imported line 8)
```python
{
    383910036: {"username": "Bee 1", "is_courier": True},
    6389671774: {"username": "Bee 2", "is_courier": True},
    8483568436: {"username": "Bee 3", "is_courier": True}
}
```

**Usage**: Fallback when live MDG query fails, courier name lookup

### RESTAURANT_SHORTCUTS (from utils.py, imported line 8)
```python
{
    "Leckerolls": "LR",
    "dean & david": "DD",
    "Julis Spätzlerei": "JS",
    ...
}
```

**Usage**: Vendor shortcut display in assignment messages

---

## Critical Logic Deep Dives

### Live Courier Detection Logic (Lines 110-165)
**Problem**: Need current courier list without manual config updates

**Solution**:
```python
async def get_mdg_couriers(bot):
    try:
        # Query MDG administrators
        admins = await bot.get_chat_administrators(DISPATCH_MAIN_CHAT_ID)
        
        couriers = []
        for admin in admins:
            user = admin.user
            
            # Filter: not bot, not anonymous
            if user.is_bot or user.username == "Channel":
                continue
            
            # Extract info
            couriers.append({
                "user_id": user.id,
                "username": user.username or user.first_name,
                "first_name": user.first_name
            })
        
        return couriers
        
    except Exception:
        # Fallback to COURIER_MAP
        return get_couriers_from_map()
```

**Benefits**:
- Reflects MDG membership changes immediately
- No manual environment variable updates
- Graceful degradation ensures assignment always works

### Group Indicator Calculation (Lines 483-494)
**Problem**: Show courier their position in grouped orders

**Data Structure**:
```python
order = {
    "group_id": "group_20241206_193045",
    "group_color": "🟣",  # From GROUP_COLORS rotation
    "group_position": 2,  # Assigned when joining group
}
```

**Calculation**:
```python
if order.get("group_id"):
    from mdg import get_group_orders
    
    group_orders = get_group_orders(STATE, group_id)  # All orders with same group_id
    group_total = len(group_orders)  # Current total (changes when orders delivered)
    
    group_header = f"{group_color} Group: {group_position}/{group_total}\n\n"
    # Example: "🟣 Group: 2/3"
```

**Why Dynamic Total**: Orders can be delivered individually → group size shrinks → total must recalculate

### Product Count Calculation (Lines 527-544)
**Same logic as mdg.py** (see Phase 1C analysis):

```python
for item_line in items:
    item_clean = item_line.lstrip('- ').strip()  # Remove dash prefix
    if ' x ' in item_clean:
        qty_part = item_clean.split(' x ')[0].strip()
        product_count += int(qty_part)
    else:
        product_count += 1  # No quantity, assume 1
```

**Handles both formats**:
- Shopify: "- 2 x Pizza" → extract 2
- Smoothr: "2 x Roll" → extract 2

### Conditional CTA Button Logic (Lines 599-615)
**Problem**: Multi-vendor needs restaurant selection, single-vendor can call directly

**Implementation**:
```python
# Problem button - always shown
problem = InlineKeyboardButton("🚩 Problem", callback_data=f"show_problem_menu|{order_id}")
buttons.append([problem])

# Call restaurant button - only for multi-vendor
if len(order.get("vendors", [])) > 1:
    call_restaurant = InlineKeyboardButton(
        "☎️ Call restaurant",
        callback_data=f"call_restaurant_menu|{order_id}"
    )
    buttons.append([call_restaurant])

# Delivered button
delivered = InlineKeyboardButton("✅ Delivered", callback_data=f"confirm_delivered|{order_id}")
buttons.append([delivered])
```

**Result**:
- Single-vendor: [Navigate] [Problem] [Delivered]
- Multi-vendor: [Navigate] [Problem] [Call restaurant] [Delivered]

### Group Dissolution Logic (Lines 865-894)
**Problem**: When 1 order remains in group, group is meaningless

**Solution**:
```python
remaining_orders = get_group_orders(STATE, group_id)

if len(remaining_orders) == 1:
    # Dissolve group
    last_order_id = remaining_orders[0]["order_id"]
    last_order = STATE.get(last_order_id)
    
    # Remove group fields
    del last_order["group_id"]
    del last_order["group_color"]
    del last_order["group_position"]
    
    # Update UPC message (removes group indicator)
    if last_order.get("upc_assignment_message_id"):
        updated_text = build_assignment_message(last_order)  # No group_id → no indicator
        await safe_edit_message(...)
```

**Result**: Courier sees updated message without "🟣 Group: 1/1" (cleaned)

---

## Stats Summary

**Total Functions**: 23
- Configuration: 2 (`now()`, `configure()`)
- Assignment: 6 (check confirmed, keyboards, courier selection, send to chat, update MDG)
- Message Building: 1 (`build_assignment_message()`)
- CTA Keyboards: 2 (assignment, problem options)
- Delivery: 3 (completion, undelivery, group update)
- Delay System: 5 (options, time picker, restaurant selection, send request, call)
- Utilities: 1 (`get_assignment_status()`)
- Group Management: 1 (`update_group_upc_messages()`)
- Courier Detection: 2 (`get_mdg_couriers()`, `get_couriers_from_map()`)

**Total Lines**: 1,169

**Most Complex Function**: `build_assignment_message()` (414-580, 167 lines) - Handles status lines, group indicators, restaurant info with times/counts, address formatting, phone formatting, optional info, multi-vendor logic

**Most Called Function**: `build_assignment_message()` - Called for initial assignment, status updates, group updates, delivery/undelivery

**Critical Dependencies**:
- utils.py: `build_status_lines()`, `format_phone_for_android()`, `safe_send_message()`, `safe_edit_message()`, `safe_delete_message()`, `get_error_description()`, `send_status_message()`
- mdg.py: `get_group_orders()`, `COURIER_SHORTCUTS`
- rg.py: `restaurant_response_keyboard()`
- main.py: STATE (via configure()), bot (via configure()), `build_assignment_confirmation_message()`

**Callback Actions Defined**: 20+
- Assignment: `assign_myself`, `assign_to_menu`, `assign_to_user`, `unassign`, `show_assigned`
- CTA: `show_problem_menu`, `call_restaurant_menu`, `confirm_delivered`, `undeliver`, `back_to_cta`
- Problem: `delay_order`, `call_single_vendor`, `back_to_problem`
- Delay: `delay_time_picker`, `delay_select_restaurant`, `delay_select_vendor`, `delay_exact_hour`, `delay_exact_selected`

**Async Functions**: 14 (All message sending/editing functions)

---

## Phase 1E Complete ✅

**upc.py Analysis**: Complete documentation of all 23 UPC functions, courier assignment system, live courier detection, private chat message building, CTA keyboards, delivery workflows, problem handling (delay/call), group order management, and conditional button logic. Ready to proceed to Phase 1F (support modules: mdg_menu_commands.py, redis_state.py, ocr.py).

# STATE Schema Documentation

**Last Updated**: December 8, 2024  
**Purpose**: Comprehensive reference for all STATE dictionary fields used across the Telegram Dispatch Bot

---

## Overview

`STATE` is the single source of truth for all orders in the system. It's an in-memory dictionary keyed by `order_id` (Shopify order ID, Smoothr code, or test order ID). **Redis persistence via Upstash** - orders automatically saved to Redis on every STATE update, survive server restarts, and auto-expire after 7 days.

**Location**: `main.py` (global variable)  
**Persistence**: `redis_state.py` (Upstash Redis backend)  
**Structure**: `STATE[order_id] = {field: value, ...}`

**Redis Features**:
- Automatic serialization of datetime objects to ISO format
- Atomic per-order saves via `redis_save_order(order_id, order_data)`
- 7-day TTL (orders auto-delete after 1 week)
- Graceful degradation (app works without Redis if credentials missing)
- Restore on startup via `redis_get_all_orders()`

---

## Core Fields (Always Present)

### `order_id` (str)
- **Type**: string
- **Set at**: Order creation (Shopify webhook, Smoothr handler, OCR PF handler, test commands)
- **Format**: 
  - Shopify: Numeric ID from Shopify API (e.g., "8191753420076")
  - Smoothr: 6-char alphanumeric (e.g., "JR6ZO9") or 2-3 digit (e.g., "545", "24")
  - OCR PF: 6-char code from OCR (e.g., "VCJ34V")
  - Test: Generated random (e.g., "Test-26-1733692800")
- **Usage**: Primary key for STATE dict, used in all callback data
- **WARNING**: Never assume format - check `order_type` field first

### `name` (str)
- **Type**: string
- **Set at**: Order creation
- **Format**:
  - Shopify: **FULL order name from Shopify** (e.g., "dishbee #12345", NOT just "45")
  - Smoothr D&D: Display number - all 3 digits (e.g., "545")
  - Smoothr Lieferando: Display number - last 2 chars (e.g., "O9" from "JR6ZO9")
  - OCR PF: Display number - last 2 chars (e.g., "4V" from "VCJ34V")
  - Test: **FULL test order name** (e.g., "Test-26", NOT just "26")
- **Usage**: Display in MDG/RG messages. For logging, extract display number via `order['name'][-2:]`
- **CRITICAL**: This is NOT pre-formatted - Shopify and test orders contain FULL names, not just numbers
- **WARNING**: Always extract last 2 chars when needing display number: `order['name'][-2:]`

### `order_type` (str)
- **Type**: string
- **Set at**: Order creation
- **Values**:
  - `"shopify"` - Orders from Shopify webhook
  - `"smoothr_dnd"` - dean & david App orders (3-digit codes)
  - `"smoothr_lieferando"` - Lieferando orders via Smoothr (6-char alphanumeric)
  - `"smoothr_dishbee"` - dishbee App orders (2-digit codes, rare)
  - `"ocr_pf_lieferando"` - Pommes Freunde OCR orders
  - `"test"` - Test orders from `/testjs`, `/testzh`, etc.
- **Usage**: Branch logic for time requests, message formatting, vendor handling
- **WARNING**: Check this field before accessing order-type-specific fields

### `vendors` (list[str])
- **Type**: list of strings
- **Set at**: Order creation
- **Format**: `["Restaurant Name", ...]` (exact match to `VENDOR_GROUP_MAP` keys)
- **Examples**: 
  - Single vendor: `["Julis Spätzlerei"]`
  - Multi-vendor: `["Julis Spätzlerei", "Leckerolls"]`
- **Usage**: RG message routing, multi-vendor vs single-vendor branching
- **WARNING**: Length determines keyboard logic (`if len(order["vendors"]) > 1`)

### `vendor_items` (dict)
- **Type**: dict mapping vendor name to list of item strings
- **Set at**: Order creation
- **Format**: `{"Restaurant Name": ["- 2 x Product Name", ...], ...}`
- **Example**: 
  ```python
  {
    "Julis Spätzlerei": ["- 1 x Bergkäse", "- 2 x Truffle"],
    "Leckerolls": ["- 1 x Classic"]
  }
  ```
- **Usage**: RG-DET expanded view, product count calculations
- **WARNING**: Shopify/Smoothr have full items, OCR PF is empty (shows `product_count` instead)

### `customer` (dict)
- **Type**: nested dictionary
- **Set at**: Order creation
- **Required fields**:
  - `"name"` (str): Customer full name
  - `"phone"` (str): Validated phone number or "N/A"
  - `"address"` (str): Street address
  - `"zip"` (str): 5-digit ZIP code
- **Optional fields**:
  - `"original_address"` (str): Full address for Google Maps (Shopify only)
  - `"email"` (str): Customer email (Shopify only)
- **Usage**: MDG-ORD display, RG-DET display, Google Maps links
- **WARNING**: Phone can be "N/A" if validation fails - check before calling

### `status` (str)
- **Type**: string
- **Set at**: Order creation, updated during lifecycle
- **Values**: `"new"`, `"assigned"`, `"delivered"`
- **Transitions**:
  - `"new"` → `"assigned"` (when courier assigns via UPC)
  - `"assigned"` → `"delivered"` (when courier confirms delivery)
  - `"delivered"` → `"assigned"` (if courier reverts via "Undeliver")
- **Usage**: Filter delivered orders, prevent duplicate assignment buttons
- **WARNING**: Check before showing assignment keyboard

### `status_history` (list[dict])
- **Type**: list of status event dictionaries
- **Set at**: Order creation, appended on each status change
- **Format**: `[{"type": "new|confirmed|assigned|delivered", "timestamp": "ISO8601", ...}, ...]`
- **Example**: 
  ```python
  [
    {"type": "new", "timestamp": "2024-12-08T01:30:00"},
    {"type": "confirmed", "vendor": "JS", "time": "12:50", "timestamp": "2024-12-08T01:32:00"},
    {"type": "assigned", "user_id": 383910036, "timestamp": "2024-12-08T01:35:00"}
  ]
  ```
- **Usage**: Audit trail, debugging, potential future analytics
- **WARNING**: Grows unbounded - no cleanup implemented yet

### `created_at` (str or datetime)
- **Type**: ISO 8601 string or datetime object
- **Set at**: Order creation
- **Format**: `"2024-12-08T01:30:00.123456"` or `datetime` object from `now()`
- **Usage**: Order age calculations, `RECENT_ORDERS` filtering (1 hour window)
- **WARNING**: Shopify uses payload timestamp, others use `now()` - formats may differ

---

## Message Tracking Fields

### `mdg_message_id` (int | None)
- **Type**: integer or None
- **Set at**: MDG-ORD sent (after order creation)
- **Format**: Telegram message ID (e.g., `123456`)
- **Usage**: Edit MDG message during workflow (time requests, confirmations, assignments)
- **WARNING**: None if MDG send failed - check before editing

### `rg_message_ids` (dict[str, int])
- **Type**: dict mapping vendor name to Telegram message ID
- **Set at**: RG-SUM sent for each vendor
- **Format**: `{"Restaurant Name": 789012, ...}`
- **Usage**: Edit vendor-specific messages (toggle details, update after confirmation)
- **WARNING**: Missing vendor key if RG send failed for that vendor

### `upc_message_id` (int | None)
- **Type**: integer or None
- **Set at**: UPC assignment message sent
- **Format**: Telegram message ID
- **Usage**: Edit courier's private assignment message (update delivery status)
- **Aliases**: `upc_assignment_message_id` (backwards compatibility)
- **WARNING**: None until courier assignment happens

### `mdg_additional_messages` (list[int])
- **Type**: list of integers
- **Set at**: Created during time picker workflows, courier selection menus
- **Format**: `[123, 456, 789]` (list of Telegram message IDs)
- **Usage**: Cleanup temporary messages after workflow completion
- **Cleanup**: `cleanup_mdg_messages()` deletes all tracked IDs
- **WARNING**: Initialize as empty list if missing before appending

### `mdg_conf_message_id` (int | None)
- **Type**: integer or None
- **Set at**: Assignment confirmation message sent (after all vendors confirm)
- **Format**: Telegram message ID
- **Usage**: Track final confirmation message with assignment buttons
- **WARNING**: Separate from `mdg_message_id` - this is the "✅ Restaurants confirmed" message

### `vendor_expanded` (dict[str, bool])
- **Type**: dict mapping vendor name to boolean
- **Set at**: Order creation (all False), toggled by RG "Details ▸" button
- **Format**: `{"Restaurant Name": False, ...}`
- **Usage**: Track RG message state (summary vs details view)
- **WARNING**: Must exist for all vendors in `vendors` list

---

## Time Management Fields

### `is_asap` (bool)
- **Type**: boolean
- **Set at**: Order creation or ASAP time request
- **Values**: `True` if ASAP requested, `False` if specific time
- **Usage**: MDG display ("ASAP" vs time), RG time request logic
- **WARNING**: Smoothr orders may have this pre-set from platform data

### `requested_time` (str | None)
- **Type**: string or None
- **Set at**: Time request workflow (ASAP, time picker, same-as reference)
- **Format**: `"HH:MM"` (24-hour) or `"ASAP"` or None
- **Examples**: `"12:50"`, `"ASAP"`, `None`
- **Usage**: Show requested time in RG messages, time negotiation
- **WARNING**: Can change multiple times during time request workflow

### `original_requested_time` (str | None)
- **Type**: string or None
- **Set at**: First time request
- **Format**: Same as `requested_time`
- **Usage**: Preserve original request if vendor requests delay
- **WARNING**: Smoothr orders may have this from platform delivery time

### `confirmed_time` (str | None)
- **Type**: string or None
- **Set at**: Vendor confirms time (clicks "✅ Works" or custom time)
- **Format**: `"HH:MM"` or `"ASAP"`
- **Usage**: MDG-CONF display, `RECENT_ORDERS` filtering, assignment message
- **Backwards compatibility**: Set when first vendor confirms (single source for old code)
- **WARNING**: With multi-vendor, this is just first confirmed time - use `confirmed_times` instead

### `confirmed_times` (dict[str, str])
- **Type**: dict mapping vendor name to confirmed time
- **Set at**: Each vendor confirms time
- **Format**: `{"Restaurant Name": "12:50", ...}`
- **Usage**: Track per-vendor confirmed times for multi-vendor orders
- **Example**: `{"Julis Spätzlerei": "12:50", "Leckerolls": "12:55"}`
- **WARNING**: Single-vendor orders may only set `confirmed_time` for backwards compatibility

### `confirmed_by` (str | None)
- **Type**: string or None
- **Set at**: Vendor confirms time
- **Format**: Vendor name (e.g., `"Julis Spätzlerei"`)
- **Usage**: Track which vendor confirmed (mostly for debugging)
- **WARNING**: Only tracks last vendor to confirm - check `confirmed_times` for full list

### `rg_time_request_ids` (dict[str, int])
- **Type**: dict mapping vendor name to Telegram message ID
- **Set at**: Time request sent to RG
- **Format**: `{"Restaurant Name": 789012, ...}`
- **Usage**: Track time request messages for cleanup after response
- **WARNING**: Only created when time request is sent - check existence before accessing

---

## Assignment & Delivery Fields

### `assigned_to` (int | None)
- **Type**: integer (Telegram user ID) or None
- **Set at**: Courier assignment (assign_myself or assign_to_user)
- **Format**: Telegram user ID (e.g., `383910036`)
- **Usage**: Track courier assignment, filter assigned orders, prevent duplicate assignments
- **WARNING**: None until assignment happens - check before showing delivery buttons

### `assigned_at` (str | None)
- **Type**: ISO 8601 string or None
- **Set at**: Courier assignment
- **Format**: `"2024-12-08T01:35:00.123456"`
- **Usage**: Calculate delivery duration, assignment timestamps
- **WARNING**: Added in recent update - older orders may not have this field

### `assigned_by` (int | None)
- **Type**: integer (Telegram user ID) or None
- **Set at**: Manual assignment by dispatcher (assign_to_user)
- **Format**: Telegram user ID
- **Usage**: Track who assigned the order (for "Assign to..." workflow)
- **WARNING**: None if courier self-assigned (assign_myself)

### `delivered_at` (str | None)
- **Type**: ISO 8601 string or None
- **Set at**: Delivery confirmation
- **Format**: `"2024-12-08T02:00:00.123456"`
- **Usage**: Calculate delivery time, delivery timestamps
- **WARNING**: None until delivery confirmed

### `delivered_by` (int | None)
- **Type**: integer (Telegram user ID) or None
- **Set at**: Delivery confirmation
- **Format**: Telegram user ID
- **Usage**: Track who delivered (should match `assigned_to` unless reassigned)
- **WARNING**: Can differ from `assigned_to` if order was reassigned

### `assignment_messages` (dict[int, int])
- **Type**: dict mapping user ID to message ID
- **Set at**: UPC assignment message sent
- **Format**: `{user_id: message_id, ...}`
- **Usage**: Track multiple assignment messages (if order reassigned)
- **WARNING**: Only created if needed - check existence before accessing

---

## Payment & Order Details

### `total` (str | float | None)
- **Type**: string, float, or None
- **Set at**: Order creation
- **Format**: 
  - Shopify: `"45.90"` (string with 2 decimals)
  - Smoothr: float or string
  - OCR PF: `"45.90€"` (string with currency symbol)
- **Usage**: MDG-ORD display, payment verification
- **WARNING**: Format varies by order type - may need parsing

### `tips` (str | float | None)
- **Type**: string, float, or None
- **Set at**: Order creation (Shopify, Smoothr only)
- **Format**: Same as `total`
- **Usage**: Show tip amount in MDG-ORD
- **WARNING**: Not present in OCR PF orders

### `payment_method` (str | None)
- **Type**: string or None
- **Set at**: Order creation (Shopify, Smoothr only)
- **Values**: `"online"`, `"cash"`, `"card"`, etc.
- **Usage**: Show cash-on-delivery icon in MDG-ORD
- **WARNING**: Detection logic varies by order type

### `note` (str | None)
- **Type**: string or None
- **Set at**: Order creation
- **Format**: Free text from customer
- **Usage**: Show in MDG-ORD, RG-DET if present
- **WARNING**: Can be empty string, None, or missing - check truthiness

### `product_count` (int)
- **Type**: integer
- **Set at**: Order creation (OCR PF only)
- **Format**: Number of items (e.g., `3`)
- **Usage**: Show product count for OCR PF orders (no itemized list)
- **WARNING**: Only present in OCR PF orders - Shopify/Smoothr use `vendor_items` length

### `is_pickup` (bool)
- **Type**: boolean
- **Set at**: Order creation (Shopify only)
- **Values**: `True` if "Abholung" detected, `False` otherwise
- **Usage**: Change MDG-ORD header and footer for pickup orders
- **WARNING**: Only Shopify orders check this - others always False

---

## Order Grouping Fields (Experimental)

### `group_id` (str | None)
- **Type**: string or None
- **Set at**: Group assignment workflow
- **Format**: Generated UUID
- **Usage**: Link orders in same delivery group
- **WARNING**: Feature may not be fully implemented - experimental

### `group_color` (str | None)
- **Type**: string or None
- **Set at**: Group assignment
- **Values**: Color emoji (e.g., `"🔴"`, `"🟢"`, `"🔵"`)
- **Usage**: Visual grouping in MDG
- **WARNING**: Experimental feature

### `group_position` (int | None)
- **Type**: integer or None
- **Set at**: Group assignment
- **Format**: Position in group (1, 2, 3, ...)
- **Usage**: Order within delivery group
- **WARNING**: Experimental feature

---

## Workflow-Specific Fields

### `waiting_for_issue_description` (str | None)
- **Type**: string (vendor name) or None
- **Set at**: Vendor clicks "⚠️ Wrong/Delay" button
- **Format**: Vendor name (e.g., `"Julis Spätzlerei"`)
- **Usage**: Track pending issue description from vendor
- **Cleanup**: Deleted after issue description received
- **WARNING**: Check existence before prompting for issue text

### `mdg_expanded` (bool | None)
- **Type**: boolean or None
- **Set at**: MDG "Details ▸" / "◂ Hide" button clicked
- **Values**: `True` if expanded, `False` if collapsed, None if never toggled
- **Usage**: Track MDG message state (summary vs details)
- **WARNING**: Similar to `vendor_expanded` but for MDG channel

### `smoothr_raw` (str)
- **Type**: string
- **Set at**: Smoothr order parsing
- **Format**: Original Smoothr message text
- **Usage**: Debugging Smoothr parsing issues
- **WARNING**: Only present in Smoothr orders, can be very long

---

## Field Dependencies & Validation

### Critical Checks Before Access

**Before showing assignment buttons**:
```python
if order.get("status") != "delivered" and all(vendor has confirmed time):
    # Show assignment buttons
```

**Before editing MDG message**:
```python
if order.get("mdg_message_id"):
    await safe_edit_message(DISPATCH_MAIN_CHAT_ID, order["mdg_message_id"], ...)
```

**Before sending delivery confirmation**:
```python
if order.get("assigned_to") and order.get("upc_message_id"):
    # Can update delivery status
```

**Multi-vendor vs single-vendor branching**:
```python
if len(order["vendors"]) > 1:
    # Show vendor selection keyboard
else:
    # Show direct time request keyboard
```

### Lifecycle State Transitions

```
[Order Created]
  ↓ (set: order_id, name, vendors, status="new")
  ↓ (send: MDG-ORD, RG-SUM)
  ↓ (set: mdg_message_id, rg_message_ids)
  
[Time Requested]
  ↓ (set: requested_time, is_asap)
  ↓ (send: RG time request)
  ↓ (set: rg_time_request_ids)
  
[Vendor Confirms]
  ↓ (set: confirmed_time, confirmed_times, confirmed_by)
  ↓ (send: MDG-CONF with assignment buttons)
  ↓ (set: mdg_conf_message_id)
  
[Courier Assigned]
  ↓ (set: assigned_to, assigned_at, status="assigned")
  ↓ (send: UPC assignment message)
  ↓ (set: upc_message_id)
  
[Delivery Confirmed]
  ↓ (set: status="delivered", delivered_at, delivered_by)
  ↓ (update: MDG shows delivery status)
```

---

## Common Pitfalls

1. **Assuming fields exist**: Always use `.get()` with defaults for optional fields
2. **Wrong order type checks**: Check `order_type` before accessing type-specific fields
3. **Message ID None**: Check message IDs exist before editing messages
4. **Length checks**: `len(order["vendors"])` determines keyboard logic - critical for multi-vendor
5. **Time format assumptions**: `confirmed_time` can be "ASAP", "12:50", or None - handle all cases
6. **Status checks**: Delivered orders should not show assignment buttons - filter by status
7. **Phone validation**: Customer phone can be "N/A" if validation failed
8. **vendor_items format**: OCR PF has empty dict, Shopify/Smoothr have full items

---

## STATE Cleanup & Maintenance

**Current Implementation**:
- ✅ **Redis persistence**: All orders saved to Upstash Redis automatically
- ✅ **7-day TTL**: Orders auto-expire and delete after 1 week
- ✅ **Restart recovery**: STATE restored from Redis on server restart
- ✅ **Atomic updates**: Each order saved individually for data consistency
- ⚠️ `status_history` grows unbounded per order (no per-field limits)
- ⚠️ `RECENT_ORDERS` only tracks last 50 orders with confirmed times (in-memory only)

**Redis Functions** (from `redis_state.py`):
- `redis_save_order(order_id, order_data)` - Save single order
- `redis_get_order(order_id)` - Retrieve single order
- `redis_get_all_orders()` - Restore full STATE on startup
- `redis_delete_order(order_id)` - Manual deletion
- `redis_get_order_count()` - Count stored orders

**Potential Improvements**:
- Manual cleanup command for delivered orders > 24 hours old
- Limit `status_history` to last 20 entries per order
- Redis backup for `RECENT_ORDERS` (currently in-memory only)

---

## Usage Examples

### Creating a new order (Shopify):
```python
STATE[order_id] = {
    "order_id": "8191753420076",
    "name": "dishbee #12345",  # FULL order name, not just "45"
    "order_type": "shopify",
    "vendors": ["Julis Spätzlerei", "Leckerolls"],
    "vendor_items": {
        "Julis Spätzlerei": ["- 1 x Bergkäse"],
        "Leckerolls": ["- 2 x Classic"]
    },
    "customer": {
        "name": "John Doe",
        "phone": "+491234567890",
        "address": "Hauptstraße 123",
        "zip": "80331",
        "original_address": "Hauptstraße 123, 80331 Munich",
        "email": "john@example.com"
    },
    "total": "45.90",
    "tips": "5.00",
    "note": "Please ring doorbell",
    "payment_method": "online",
    "is_pickup": False,
    "status": "new",
    "status_history": [{"type": "new", "timestamp": "2024-12-08T01:30:00"}],
    "mdg_message_id": None,
    "rg_message_ids": {},
    "vendor_expanded": {"Julis Spätzlerei": False, "Leckerolls": False},
    "mdg_additional_messages": [],
    "created_at": "2024-12-08T01:30:00"
}
```

### Updating after vendor confirmation:
```python
order = STATE[order_id]
confirmed_time = order.get("requested_time", "ASAP")

if "confirmed_times" not in order:
    order["confirmed_times"] = {}
order["confirmed_times"][vendor] = confirmed_time
order["confirmed_time"] = confirmed_time  # Backwards compatibility
order["confirmed_by"] = vendor

order["status_history"].append({
    "type": "confirmed",
    "vendor": vendor,
    "time": confirmed_time,
    "timestamp": now()
})
```

### Assignment workflow:
```python
order["assigned_to"] = user_id
order["assigned_at"] = now()
order["status"] = "assigned"
order["status_history"].append({
    "type": "assigned",
    "user_id": user_id,
    "timestamp": now()
})
```

---

**End of STATE_SCHEMA.md**

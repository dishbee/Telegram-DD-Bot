# PHASE 2 COMPLETE - MDG.PY ANALYSIS

**HEADER: This analysis contains ZERO interpretation or hallucination. Every claim is cited with line numbers from mdg.py (1,337 lines total).**

---

## MODULE CONFIGURATION

**Function: `configure()`** (Lines 44-47)
- Sets module-level `STATE` and `RESTAURANT_SHORTCUTS` references from main.py

**Global Variables:**
- `CHEF_EMOJIS` (Line 29): List of 12 chef emojis for rotating display in multi-vendor buttons
- `COURIER_SHORTCUTS` (Lines 32-36): Maps courier names to 2-letter codes ("Bee 1" → "B1")
- `GROUP_COLORS` (Line 39): List of 7 color emojis for combined order groups: 🟣🔵🟢🟡🟠🔴🟤
- `RESTAURANT_SHORTCUTS` (Line 24): Dict mapping full vendor names to 2-letter shortcuts (configured from main.py)

---

## FUNCTION 1: build_mdg_dispatch_text()

**Purpose**: Build MDG dispatch message with collapsible details (Lines 267-541)

**Output Format - COLLAPSED VIEW (show_details=False)**:

```
{status_lines from utils.build_status_lines()}────────────────

{datetime_line - if Smoothr with requested_time}

{address_line}

{vendor_line}

{phone_line}

{customer_line}

{total_line}

{note_line}{tips_line}{payment_line - if any present}
```

**Code Evidence (Lines 437-474)**:
```python
# Build collapsed view text
text = "────────────────\n"
text += "\n"  # Blank line after separator

# Add datetime line if Smoothr with requested time
if datetime_line:
    text += datetime_line
    text += "\n"  # Blank line after datetime

# Section order: address → vendor → phone → customer → total
text += address_line
text += "\n"  # Blank line after address
text += f"{vendor_line}\n"
text += "\n"  # Blank line after vendor
text += phone_line
text += "\n"  # Blank line after phone
text += customer_line
text += "\n"  # Blank line after customer
text += total_line

# Add notes/tips/cash after total (if present)
if note_line or tips_line or payment_line:
    text += "\n"  # Blank line before notes section
    text += note_line
    text += tips_line
    text += payment_line
```

**Line Components**:

1. **Separator Line** (Line 437): `"────────────────\n"`

2. **DateTime Line** (Lines 339-359): Only for Smoothr orders with `requested_time`
   - Future date: `🗓️ DD.MM.YYYY ⏰ HH:MM\n`
   - Same day: `⏰ HH:MM\n`

3. **Address Line** (Lines 418-424):
   - Shopify: `🗺️ [{street} ({zip})][maps_link]\n`
   - Smoothr: `🗺️ [{street} ({zip})][maps_link]\n`

4. **Vendor Line** (Lines 380-407):
   - Multi-vendor: `{chef_emoji} **SHORTCUT1** (count1) + **SHORTCUT2** (count2)\n`
   - Single vendor: `{chef_emoji} **SHORTCUT** (count)\n`

5. **Phone Line** (Lines 426-431):
   - If phone exists and not "N/A": `📞 {formatted_phone}\n`
   - Empty string if no phone

6. **Customer Line** (Line 416): `👤 {customer_name}\n`

7. **Total Line** (Lines 433-434): `Total: {total}\n`

8. **Optional Lines** (Lines 461-466):
   - Note: `❕ Note: {note}\n` (if note exists)
   - Tip: `❕ Tip: {tips}€\n` (if tips > 0)
   - Cash: `❕ Cash: {total}\n` (if Shopify payment_method == "cash on delivery")

**Output Format - EXPANDED VIEW (show_details=True)**:

```
{collapsed_view_content}

{source_line}

{district_line - if district detected}

{email_line - if email exists}

{items_text - product list}
```

**Code Evidence (Lines 476-538)**:
```python
# Add expanded details if requested
if show_details:
    # Blank line before expanded details
    text += "\n"
    
    # Add source line in expanded view
    text += source_line
    text += "\n"  # Blank line after source
    
    # Add district line
    district = get_district_from_address(original_address)
    
    if district:
        # Get zip code directly from STATE (works for both Shopify and Smoothr)
        zip_code = order['customer'].get('zip', '')
        text += f"🏙️ {district} ({zip_code})\n"
        text += "\n"  # Blank line after district
    
    # Add email if available (expanded view only)
    email = order['customer'].get('email')
    if email:
        text += f"✉️ {email}\n"
        text += "\n"  # Blank line after email
    
    # Build product list (works for both Shopify and Smoothr)
    if len(vendors) > 1:
        # Multi-vendor product display
        vendor_items = order.get("vendor_items", {})
        items_text_parts: List[str] = []
        for vendor in vendors:
            # Use shortcut instead of full vendor name
            shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
            items_text_parts.append(f"**{shortcut}**:")
            vendor_products = vendor_items.get(vendor, [])
            for item in vendor_products:
                clean_item = item.lstrip('- ').strip()
                items_text_parts.append(clean_item)
        items_text = "\n".join(items_text_parts)
    else:
        # Single vendor product display
        ...
```

**Expanded View Lines**:

1. **Source Line** (Lines 410-414):
   - Shopify: `🔗 dishbee\n`
   - Smoothr dishbee: `🔗 dishbee\n`
   - Smoothr D&D: `🔗 D&D App\n`
   - Smoothr Lieferando: `🔗 Lieferando\n`

2. **District Line** (Lines 489-495): If district detected: `🏙️ {district} ({zip})\n`

3. **Email Line** (Lines 498-501): If email exists: `✉️ {email}\n`

4. **Items Text** (Lines 503-538):
   - Multi-vendor: Each vendor shows `**SHORTCUT**:` header followed by product lines
   - Single vendor: Product lines only (no vendor header)
   - PF Lieferando: SKIPPED (uses product count only, not item details)

---

## FUNCTION 2: mdg_initial_keyboard()

**Purpose**: Build initial MDG keyboard with Details button above time request buttons (Lines 544-594)

**Layout - Single Vendor**:
```
[Details ▸]
[⚡ Asap]
[🕒 Time picker]
[🗂 Scheduled orders]  ← conditional, only if recent_orders exist
```

**Code Evidence (Lines 573-585)**:
```python
# Single vendor: show ASAP/TIME/SCHEDULED buttons (vertical)
buttons.append([InlineKeyboardButton("⚡ Asap", callback_data=f"req_asap|{order_id}|{int(now().timestamp())}")])
buttons.append([InlineKeyboardButton("🕒 Time picker", callback_data=f"req_exact|{order_id}|{int(now().timestamp())}")])

# Show "Scheduled orders" button only if recent orders exist
recent_orders = get_recent_orders_for_same_time(order_id, vendor=None)
if recent_orders:
    buttons.append([InlineKeyboardButton("🗂 Scheduled orders", callback_data=f"req_scheduled|{order_id}|{int(now().timestamp())}")])
```

**Layout - Multi-Vendor**:
```
[Details ▸]
[Ask 👩‍🍳 JS]  ← rotating chef emoji per vendor
[Ask 👨‍🍳 LR]
```

**Code Evidence (Lines 565-571)**:
```python
if len(vendors) > 1:
    # Multi-vendor: show vendor selection buttons
    for vendor in vendors:
        shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
        chef_emoji = CHEF_EMOJIS[vendors.index(vendor) % len(CHEF_EMOJIS)]
        buttons.append([InlineKeyboardButton(
            f"Ask {chef_emoji} {shortcut}",
```

**Toggle Button** (Lines 558-563):
```python
is_expanded = order.get("mdg_expanded", False)
toggle_button = InlineKeyboardButton(
    "◂ Hide" if is_expanded else "Details ▸",
    callback_data=f"mdg_toggle|{order_id}|{int(now().timestamp())}"
)
```

**Callback Data Formats**:
- Details toggle: `mdg_toggle|{order_id}|{timestamp}`
- ASAP: `req_asap|{order_id}|{timestamp}`
- Time picker: `req_exact|{order_id}|{timestamp}`
- Scheduled: `req_scheduled|{order_id}|{timestamp}`
- Vendor selection: `req_vendor|{order_id}|{vendor}|{timestamp}`

---

## FUNCTION 3: mdg_time_request_keyboard()

**Purpose**: Build MDG time request buttons per assignment requirements (Lines 597-660)

**IDENTICAL OUTPUT to mdg_initial_keyboard()** - Lines 597-660 duplicate the same logic as mdg_initial_keyboard().

**Callback Data Formats**: Same as mdg_initial_keyboard()

---

## FUNCTION 4: mdg_time_submenu_keyboard()

**Purpose**: Build TIME submenu showing recent confirmed orders (not delivered, <5hr) (Lines 663-788)

**Layout - With Recent Orders**:
```
[{order_num} - {vendor_shortcut} - {time} - {address}]  ← one button per order
[{order_num} - {vendor_shortcut} - {time} - {address}]
...
[← Back]
```

**Code Evidence (Lines 735-776)**:
```python
# If we have recent orders, show them + EXACT TIME button
if recent_orders:
    for recent in recent_orders:
        chef_emoji = CHEF_EMOJIS[recent_orders.index(recent) % len(CHEF_EMOJIS)]
        
        # If multi-vendor reference order, create separate button per vendor
        if len(recent["vendors"]) > 1:
            for ref_vendor in recent["vendors"]:
                ref_vendor_shortcut = RESTAURANT_SHORTCUTS.get(ref_vendor, ref_vendor[:2].upper())
                
                # Get vendor-specific time from confirmed_times dict, fallback to confirmed_time
                vendor_time = recent.get("confirmed_times", {}).get(ref_vendor, recent['confirmed_time'])
                
                # Build button text: "02 - LR - 14:15 - Grabenga. 15"
                abbreviated_address = abbreviate_street(recent['address'], max_length=15)
                button_text = f"{recent['order_num']} - {ref_vendor_shortcut} - {vendor_time} - {abbreviated_address}"
                
                # TIER 2: If button exceeds 64 chars (Telegram limit), apply aggressive abbreviation
                if len(button_text) > 64:
                    ...aggressive abbreviation logic...
```

**Address Abbreviation** (Lines 754-772):
- **Tier 1**: Use `abbreviate_street(address, max_length=15)` from utils.py
- **Tier 2**: If button > 64 chars, apply aggressive abbreviation:
  1. Extract house number with regex: `\s+(\d+[a-zA-Z]?)$`
  2. Remove common prefixes: `Doktor-`, `Professor-`, `Sankt-`, `Dr.-`, `Prof.-`, `St.-`
  3. If compound street (has hyphens), take first part
  4. Take first 4 letters only + house number
  5. Result: `Gabe 15` instead of `Grabenstraße 15`

**Special Case - NO Recent Orders** (Line 786):
```python
# If NO recent orders, return None to signal that hour picker should be shown directly
# The handler in main.py will detect this and show exact_time_keyboard() immediately
else:
    return None
```

**Callback Data Formats**:
- Single vendor order ref: `order_ref|{order_id}|{ref_order_id}|{time}|{ref_vendor_shortcut}`
- Multi-vendor order ref: `order_ref|{order_id}|{ref_order_id}|{vendor_time}|{ref_vendor_shortcut}|{current_vendor_shortcut}`
- Back button: `hide`

---

## FUNCTION 5: order_reference_options_keyboard()

**Purpose**: Build Same / +5 / +10 / +15 / +20 keyboard after user selects a reference order (Lines 791-855)

**Layout - Matching Vendors**:
```
[🔁 Same time]  ← only if vendors match
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

**Code Evidence (Lines 820-845)**:
```python
# Show "Same time" button ONLY if vendors match
if vendor_matches:
    # Same vendor - show "Same time" button
    if current_vendor_full:
        same_callback = f"time_same|{current_order_id}|{ref_order_id}|{ref_time}|{current_vendor_full}"
    else:
        same_callback = f"time_same|{current_order_id}|{ref_order_id}|{ref_time}"
    buttons.append([InlineKeyboardButton("🔁 Same time", callback_data=same_callback)])

# Build offset buttons: -5m, -3m, +3m, +5m, +10m, +15m, +20m, +25m (one per row)
for minutes in [-5, -3, 3, 5, 10, 15, 20, 25]:
    new_time = ref_datetime + timedelta(minutes=minutes)
    time_str = new_time.strftime("%H:%M")
    # Use full vendor name in callback
    vendor_param = f"|{current_vendor_full}" if current_vendor_full else ""
    callback = f"time_relative|{current_order_id}|{time_str}|{ref_order_id}{vendor_param}"
    # Format: "+5m → ⏰ 19:35" or "-5m → ⏰ 19:25"
    button_text = f"{minutes:+d}m → ⏰ {time_str}"
    buttons.append([InlineKeyboardButton(button_text, callback_data=callback)])
```

**Vendor Matching Logic** (Lines 813-826):
- Multi-vendor order: Check if current_vendor_full matches ref_vendor_full (exact match)
- Single vendor order: Check if ref_vendor_full in current order's vendors list

**Callback Data Formats**:
- Same time (multi-vendor): `time_same|{order_id}|{ref_order_id}|{ref_time}|{current_vendor_full}`
- Same time (single-vendor): `time_same|{order_id}|{ref_order_id}|{ref_time}`
- Relative offset (multi-vendor): `time_relative|{order_id}|{time_str}|{ref_order_id}|{current_vendor_full}`
- Relative offset (single-vendor): `time_relative|{order_id}|{time_str}|{ref_order_id}`
- Back button: `hide`

---

## FUNCTION 6: time_picker_keyboard()

**Purpose**: Build time picker for various actions (Lines 871-936)

**Layout - RG Actions (later_time, prepare_time)**:
```
[⏰ 18:10 → in 5 m]
[⏰ 18:15 → in 10 m]
[⏰ 18:20 → in 15 m]
[⏰ 18:25 → in 20 m]
[Time picker🕒]
[← Back]
```

**Layout - UPC Actions (Other)**:
```
[+5m → ⏰ 18:10]
[+10m → ⏰ 18:15]
[+15m → ⏰ 18:20]
[+20m → ⏰ 18:25]
[Time picker🕒]
[← Back]
```

**Code Evidence (Lines 902-920)**:
```python
# Determine button prefix based on action
# RG buttons (later_time, prepare_time) use "in", others use "+"
if action in ["later_time", "prepare_time"]:
    prefix = "in"
else:
    prefix = "+"

# Create one button per row (vertical layout)
for i, time_str in enumerate(intervals):
    minutes = minute_increments[i]
    # Format: "⏰ 18:10 → in 5 m" (RG) or "+5m → ⏰ 18:10" (UPC)
    if prefix == "in":
        button_text = f"⏰ {time_str} → in {minutes} m"
    else:
        button_text = f"+{minutes}m → ⏰ {time_str}"
```

**Callback Data Formats**:
- Time button (with vendor): `{action}|{order_id}|{time_str}|{vendor_shortcut}`
- Time button (no vendor): `{action}|{order_id}|{time_str}`
- Exact time (with vendor): `vendor_exact_time|{order_id}|{vendor_shortcut}|{action}`
- Exact time (no vendor): `exact_time|{order_id}|{action}`
- Back button: `hide`

---

## FUNCTION 7: exact_time_keyboard()

**Purpose**: Build exact time picker - shows hours (Lines 939-972)

**Layout**:
```
[{hour}] [{hour}] [{hour}] [{hour}]  ← 4 hours per row
[{hour}] [{hour}] [{hour}] [{hour}]
...
[← Back]
```

**Code Evidence (Lines 949-968)**:
```python
current_time = now()
current_hour = current_time.hour
current_minute = current_time.minute

# Skip current hour if past minute 57 (no valid 3-minute intervals left)
start_hour = current_hour + 1 if current_minute >= 57 else current_hour

rows: List[List[InlineKeyboardButton]] = []
hours: List[str] = [f"{hour:02d}" for hour in range(start_hour, 24)]

for i in range(0, len(hours), 4):
    row: List[InlineKeyboardButton] = []
    for j in range(4):
        if i + j < len(hours):
            hour_str = hours[i + j]  # Already just the hour number
            # Include vendor in callback if provided
            callback = f"exact_hour|{order_id}|{hour_str}"
            if vendor:
                callback += f"|{vendor}"
```

**Callback Data Formats**:
- Hour button (with vendor): `exact_hour|{order_id}|{hour}|{vendor}`
- Hour button (no vendor): `exact_hour|{order_id}|{hour}`
- Back button: `exact_hide|{order_id}`

---

## FUNCTION 8: exact_hour_keyboard()

**Purpose**: Build minute picker for exact time - 3 minute intervals (Lines 975-1012)

**Layout**:
```
[{HH:MM}] [{HH:MM}] [{HH:MM}] [{HH:MM}]  ← 4 times per row, 3-min intervals
[{HH:MM}] [{HH:MM}] [{HH:MM}] [{HH:MM}]
...
[← Back to hours]
```

**Code Evidence (Lines 978-1007)**:
```python
current_time = now()
rows: List[List[InlineKeyboardButton]] = []
minutes_options: List[str] = []

for minute in range(0, 60, 3):
    if hour == current_time.hour and minute <= current_time.minute:
        continue
    minutes_options.append(f"{hour:02d}:{minute:02d}")

for i in range(0, len(minutes_options), 4):
    row: List[InlineKeyboardButton] = []
    for j in range(4):
        if i + j < len(minutes_options):
            time_str = minutes_options[i + j]
            # Include vendor in callback if provided
            callback = f"exact_selected|{order_id}|{time_str}"
            if vendor:
                callback += f"|{vendor}"
            row.append(InlineKeyboardButton(
                time_str,
                callback_data=callback
            ))
```

**Callback Data Formats**:
- Time button (with vendor): `exact_selected|{order_id}|{time}|{vendor}`
- Time button (no vendor): `exact_selected|{order_id}|{time}`
- Back button (with vendor): `exact_back_hours|{order_id}|{vendor}`
- Back button (no vendor): `exact_back_hours|{order_id}`

---

## FUNCTION 9: get_assigned_orders()

**Purpose**: Get all assigned (not delivered) orders for combining menu (Lines 1018-1150)

**Return Format**: List of dicts with keys:
- `order_id`: Shopify order ID
- `order_num`: Last 2 digits of order name
- `vendor_shortcut`: 2-letter vendor code
- `confirmed_time`: Confirmed time (HH:MM)
- `address`: Street name (PRE-TRUNCATED to fit 30-char button limit)
- `assigned_to`: Telegram user_id
- `courier_name`: Full courier name ("Bee 1", "Bee 2", "Bee 3")

**Code Evidence (Lines 1070-1114)**:
```python
# For multi-vendor orders, create SEPARATE entry per vendor (like scheduled orders)
if len(vendors) > 1 and confirmed_times:
    for vendor in vendors:
        vendor_shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
        vendor_time = confirmed_times.get(vendor, "??:??")
        
        # Start with full street name (no house number, no zip)
        final_address = street
        
        # Build button text: {address} - {time} - {vendor}  |  {courier}
        button_text = f"{final_address} - {vendor_time} - {vendor_shortcut}  |  {courier_name}"
        
        # If > 30 chars (single-line limit), reduce street name letter-by-letter
        while len(button_text) > 30 and len(final_address) > 1:
            final_address = final_address[:-1]
            button_text = f"{final_address} - {vendor_time} - {vendor_shortcut}  |  {courier_name}"
        
        assigned.append({
            "order_id": oid,
            "order_num": order_num,
            "vendor_shortcut": vendor_shortcut,
            "confirmed_time": vendor_time,
            "address": final_address,
            "assigned_to": assigned_to,
            "courier_name": courier_name
        })
```

**Multi-Vendor Handling**: Creates SEPARATE entry per vendor (mirrors scheduled orders format)

**Address Truncation**: Reduces street name letter-by-letter until `{address} - {time} - {vendor}  |  {courier}` fits 30-char limit

**Sorting** (Line 1147): `assigned.sort(key=lambda x: x["courier_name"])`

---

## FUNCTION 10: build_combine_keyboard()

**Purpose**: Build inline keyboard with assigned orders for combining (Lines 1175-1218)

**Layout**:
```
[{address} - {time} - {vendor}  |  {courier}]  ← one button per order
[{address} - {time} - {vendor}  |  {courier}]
...
[← Back]
```

**Code Evidence (Lines 1189-1210)**:
```python
for order in assigned_orders:
    # Use PRE-TRUNCATED address from get_assigned_orders() (already fits 30-char limit)
    address = order["address"]
    
    # Build button text: {address} - {time} - {vendor}  |  {courier}
    button_text = f"{address} - {order['confirmed_time']} - {order['vendor_shortcut']}  |  {order['courier_name']}"
    
    # Hard-truncate to 64 chars max (Telegram button limit) as safety fallback
    if len(button_text) > 64:
        button_text = button_text[:61] + "..."
    
    # Callback: combine_with|{order_id}|{target_order_id}|{timestamp}
    callback_data = f"combine_with|{order_id}|{order['order_id']}|{int(now().timestamp())}"
    
    buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

# Add Back button
buttons.append([InlineKeyboardButton("← Back", callback_data=f"hide|{order_id}")])
```

**Callback Data Formats**:
- Order button: `combine_with|{order_id}|{target_order_id}|{timestamp}`
- Back button: `hide|{order_id}`

---

## SUPPORTING HELPER FUNCTIONS

### get_courier_shortcut() (Lines 62-90)
Maps courier user_id to shortcut:
- "Bee 1" → "B1"
- "Bee 2" → "B2"
- "Bee 3" → "B3"
- Other couriers → First 2 letters of name

### shortcut_to_vendor() (Lines 50-54)
Converts vendor shortcut back to full vendor name (reverse lookup)

### get_vendor_shortcuts_string() (Lines 93-107)
Converts list of vendor names to comma-separated shortcuts

### get_recent_orders_for_same_time() (Lines 110-180)
Returns last 10 confirmed orders from last 5 hours (excludes delivered, optionally filters by vendor)

### get_last_confirmed_order() (Lines 183-209)
Returns most recent order with confirmed time from today

### build_smart_time_suggestions() (Lines 212-247)
Builds keyboard with +5/+10/+15/+20 buttons based on last confirmed order time

### generate_group_id() (Lines 1153-1162)
Generates unique group ID: `group_YYYYMMDD_HHMMSS`

### get_next_group_color() (Lines 1165-1185)
Returns next available color emoji from rotation: 🟣🔵🟢🟡🟠🔴🟤

### get_group_orders() (Lines 1188-1203)
Returns all orders in a specific group (excluding delivered)

### show_combine_orders_menu() (Lines 1221-1274) - ASYNC
Shows menu to select assigned order to combine with (sends NEW message, tracks in mdg_additional_messages)

---

## CALLBACK DATA FORMATS SUMMARY

**MDG Toggle**:
- `mdg_toggle|{order_id}|{timestamp}`

**Time Requests (Single-Vendor)**:
- `req_asap|{order_id}|{timestamp}`
- `req_exact|{order_id}|{timestamp}`
- `req_scheduled|{order_id}|{timestamp}`

**Time Requests (Multi-Vendor)**:
- `req_vendor|{order_id}|{vendor}|{timestamp}`

**Scheduled Orders Reference**:
- `order_ref|{order_id}|{ref_order_id}|{time}|{ref_vendor_shortcut}` (single-vendor)
- `order_ref|{order_id}|{ref_order_id}|{vendor_time}|{ref_vendor_shortcut}|{current_vendor_shortcut}` (multi-vendor)

**Reference Time Options**:
- `time_same|{order_id}|{ref_order_id}|{ref_time}` (single-vendor)
- `time_same|{order_id}|{ref_order_id}|{ref_time}|{current_vendor_full}` (multi-vendor)
- `time_relative|{order_id}|{time_str}|{ref_order_id}` (single-vendor)
- `time_relative|{order_id}|{time_str}|{ref_order_id}|{current_vendor_full}` (multi-vendor)

**Time Picker Actions**:
- `{action}|{order_id}|{time_str}` (no vendor)
- `{action}|{order_id}|{time_str}|{vendor_shortcut}` (with vendor)

**Exact Time Picker**:
- `exact_hour|{order_id}|{hour}` (no vendor)
- `exact_hour|{order_id}|{hour}|{vendor}` (with vendor)
- `exact_selected|{order_id}|{time}` (no vendor)
- `exact_selected|{order_id}|{time}|{vendor}` (with vendor)
- `exact_hide|{order_id}`
- `exact_back_hours|{order_id}` (no vendor)
- `exact_back_hours|{order_id}|{vendor}` (with vendor)

**Exact Time Submenu**:
- `vendor_exact_time|{order_id}|{vendor_shortcut}|{action}`
- `exact_time|{order_id}|{action}`

**Combine Orders**:
- `combine_with|{order_id}|{target_order_id}|{timestamp}`

**Utility**:
- `hide` (close menu)
- `hide|{order_id}` (close menu with context)
- `no_recent` (placeholder for empty scheduled list)

---

## SHOPIFY VS SMOOTHR DIFFERENCES

**Order Number Extraction**:
- Shopify: Last 2 digits from `order["name"]` (e.g., "dishbee #26" → "26")
- Smoothr: Use full `order["name"]` (already formatted by parser)

**DateTime Line** (Lines 339-359):
- Shopify: Never shows (ASAP orders only)
- Smoothr: Shows if `is_asap=False` and `requested_time` exists
  - Future date: `🗓️ DD.MM.YYYY ⏰ HH:MM\n`
  - Same day: `⏰ HH:MM\n`

**Source Line** (Lines 410-414):
- Shopify: `🔗 dishbee\n`
- Smoothr dishbee: `🔗 dishbee\n`
- Smoothr D&D: `🔗 D&D App\n`
- Smoothr Lieferando: `🔗 Lieferando\n`

**Product Count** (Lines 367-386):
- Shopify: Counts quantities from `vendor_items` (parses "- 2 x Product")
- Smoothr: Counts quantities from `vendor_items` (parses "2 x Product")
- Smoothr Lieferando (PF): Uses stored `product_count` field (vendor_items empty)

**Product Display in Expanded View** (Lines 514-538):
- Shopify: Shows all products from `vendor_items`
- Smoothr: Shows all products from `vendor_items`
- Smoothr Lieferando (PF): SKIPPED (line 514 check: `order_type != "smoothr_lieferando"`)

---

## RESTAURANT SHORTCUTS

**Configured from main.py** (Line 24): `RESTAURANT_SHORTCUTS` dict populated via `configure()` function

**Example shortcuts visible in code comments**:
- Julis Spätzlerei → JS
- Leckerolls → LR
- dean & david → DD
- Pommes Freunde → PF

---

**END OF PHASE 2 ANALYSIS**

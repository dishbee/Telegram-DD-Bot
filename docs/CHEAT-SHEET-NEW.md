commi# ⚡ TELEGRAM BOT CHEAT SHEET

> **Purpose**: Quick reference for AI prompting - shortcuts, formats, and workflows

---

## 📡 CHANNELS

| Code | Name | Purpose |
|------|------|---------|
| **MDG** | Main Dispatch Group | Order arrival, time coordination, assignment |
| **RG** | Restaurant Groups | Vendor-specific details, time responses |
| **UPC** | User Private Chat | Courier assignment, delivery actions |

---

## 💬 MESSAGES

### 📍 MDG Messages

#### **MDG-ORD** - Initial Order (Collapsed)
```
🚨 New order

🔖 #{num} - {source}
{chef} {Shortcuts} 🍕 {count}
👤 {Customer}
🗺️ [{Address}]({link})

❕ Note: {text} (optional)
❕ Tip: {amt}€ (optional)
❕ Cash: {amt}€ (optional)

[{phone}](tel:{phone})

[Details ▸] [Action buttons...]
```

**Action Buttons:**
- Single vendor: `[⚡ Asap]` `[🕒 Time picker]` `[🗂 Scheduled]*`
- Multi-vendor: `[Ask {chef} {Shortcut}]` per vendor

**Expanded View** (after Details ▸):
```
🏙️ {District} ({zip})

{Vendor}: (if multi-vendor)
{qty} x {Product}
...

{Total}€ (if not COD)

[◂ Hide] [Action buttons...]
```

---

#### **MDG-CONF** - All Vendors Confirmed
```
 #{num} - dishbee 🍕 {count}+{count} (multi)
� #{num} - dishbee 🍕 {count} (single)

{chef} {Shortcut}: {time}
{chef} {Shortcut}: {time} (multi-vendor)

[👈 Assign to myself] [👉 Assign to...]
```

**Product Count Logic:**
- Parses `vendor_items` to sum quantities per vendor
- Multi-vendor: Shows `+` separated counts (e.g., `2+3+1`)
- Single-vendor: Shows single count

---

### 🏪 RG Messages

#### **RG-SUM** - Order Summary (Collapsed)
```
🚨 New order

🔖 #{num}

{qty} x {Product}
{qty} x {Product}

❕ Note: {text} (optional)

[Details ▸]
```

#### **RG-DET** - Order Details (Expanded)
```
🚨 New order

🔖 #{num}

{qty} x {Product}
{qty} x {Product}

❕ Note: {text}

🧑 {Customer}
🗺️ {Address}
📞 {phone}
⏰ Ordered at: {HH:MM}

[◂ Hide]
```

#### **RG-TIME-REQ** - Time Request
```
"Can you prepare 🔖 #{num} at {time}?"
"Can you prepare 🔖 #{num} ⚡ Asap?"
"Can you prepare 🔖 #{num} together with 🔖 #{ref} at {time}?"

[Works 👍]
[⏰ Later at]
[🚩 Problem]
```

#### **RG-CONF** - Vendor Confirmation
```
"Confirmation was sent to dishbee. 
Please prepare 🔖 #{num} at {time} for courier."
```

---

### 💼 UPC Messages

#### **UPC-ASSIGN** - Courier Assignment
```
🚨 Order assigned 👉 to you (dishbee)

👉 #{num} - {source}
{chef} {Shortcut}: {time} 🍕 {count}
{chef} {Shortcut}: {time} 🍕 {count} (multi-vendor)
👤 {Customer}
🧭 {Address} ({zip})
❕ Tip: {amt}€ (optional)
❕ Cash: {amt}€ (optional)
☎️ {phone}

[🧭 Navigate]
[⏳ Delay]
[🚫 Unassign]
[{chef} Call {Shortcut}]
[✅ Delivered]
```

**Group Orders**: Shows `{color} Group {pos}/{total}` after status

---

### 📨 Temporary Status (Auto-delete 20s)

Separate messages sent to MDG:

```
ST-WORKS       {chef} {Vendor} replied: {time} for 🔖 #{num} works 👍
ST-PREP        {chef} {Vendor} replied: Will prepare 🔖 #{num} at {time} 👍
ST-LATER       {chef} {Vendor} replied: Will prepare 🔖 #{num} later at {time} 👍
ST-DELAY       {chef} {Vendor}: We have a delay for 🔖 #{num} - new time {time}
ST-CANCEL      {chef} {Vendor}: Order 🔖 #{num} is canceled
ST-WRITE       {chef} {Vendor}: Issue with 🔖 #{num}: "{message}"
ST-ASAP-SENT   ⚡ Asap request for 🔖 #{num} sent to {Shortcut}
ST-TIME-SENT   🕒 Time request ({time}) for 🔖 #{num} sent to {Shortcut}
ST-UPC-DELAY   🕒 DELAY request ({time}) for 🔖 #{num} sent to {Shortcut}
```

---

## 🔘 BUTTONS

### 📍 MDG Buttons

**Initial Actions**
```
BTN-ASAP        Asap
BTN-TIME       🕒 Time picker
BTN-SCHEDULED  🗂 Scheduled orders (conditional)
BTN-VENDOR     Ask {chef} {Shortcut} (multi-vendor)
BTN-DETAILS    Details ▸ / ◂ Hide
```

**Scheduled Orders**
```
BTN-ORD-REF    {num} - {short} - {time} - {addr}
               Example: "02 - LR - 20:46 - Ledererga. 15"
```

**Time Selection**
```
BTN-SAME       🔁 Same time (if vendors match)
BTN-OFFSET     -5m / -3m / +3m / +5m / +10m / +15m / +20m / +25m
BTN-HOUR       12:XX, 13:XX... 23:XX
BTN-MINUTE     00, 03, 06... 57 (3-min intervals)
```

**Assignment**
```
BTN-ASSIGN-ME  👈 Assign to myself
BTN-ASSIGN-TO  👉 Assign to...
BTN-COURIER    Individual courier buttons (from live MDG admins)
BTN-COMBINE    📌 Assigned orders (shows combine menu)
BTN-BACK       ← Back
```

**Combine Orders:**
- Shows all assigned (not delivered) orders
- Button format: `{num} - {Shortcut} - {time} - {addr} (🐝{courier})`
- Example: `"02 - LR - 20:46 - Ledererga. 15 (🐝B1)"`
- Clicking order combines current order with selected order

---

### 🏪 RG Buttons

**View Toggle**
```
BTN-TOGGLE     Details ▸ / ◂ Hide
```

**Time Response**
```
BTN-WORKS      Works 👍
BTN-LATER      ⏰ Later at
BTN-PREP       Will prepare at...
BTN-WRONG      🚩 Problem
```

**Issue Submenu**
```
BTN-UNAVAIL    🍕 Product(s) N/A
BTN-DELAY      ⏳ We have a delay
BTN-CANCEL     ❌ Order is canceled
BTN-OTHER      💬 Something else
BTN-BACK       ← Back
```

**Time Picker**
```
BTN-TIME-OPTS  +5 / +10 / +15 / +20
BTN-EXACT      EXACT TIME ⏰
BTN-V-HOUR     Hour selection
BTN-V-MINUTE   Minute selection
```

---

### 💼 UPC Buttons

**Before Delivery:**
```
BTN-NAVIGATE   🧭 Navigate
BTN-DELAY      ⏳ Delay
BTN-UNASSIGN   🚫 Unassign
BTN-CALL       {chef} Call {Shortcut}
BTN-DELIVERED  ✅ Delivered
```

**After Delivery:**
```
BTN-UNDELIVER  ❌ Undeliver (reverts to assigned status)
```

**Undeliver Behavior:**
- Removes `delivered_at` and `delivered_by` from STATE
- Reverts status from "delivered" → "assigned"
- Restores full UPC keyboard (Navigate, Delay, Call, Delivered)
- Updates MDG and UPC messages

---

## ⏱️ STATUS SYSTEM

Status lines **prepended** to messages showing current state.

### MDG Status Lines

```
1. 🚨 New order
2. 📍 Sent ⚡ Asap to {chef} {Shortcut}
3. 📍 Sent 🕒 {time} to {chef} {Shortcut}
4. 📍 Confirmed 👍 {time} by {chef} {Shortcut}
5. 🚚 Assigned 👉 to 🐝 {courier}
6. 📍 Delivered ✅ at {HH:MM} by 🐝 {courier}
```

Multi-vendor: Separate line per vendor

---

### RG Status Lines

```
1. 🚨 New order
2. 📍 Asked for ⚡ Asap by dishbee
3. 📍 Asked for 🕒 {time} by dishbee
4. 📍 Prepare this order at {time} 🫕
5. 📍 Delivered ✅
```

---

### UPC Status Lines

```
1. 🚨 Order assigned 👉 to you (dishbee)
2. 📍 Delay ⏰ sent to {Shortcut}
3. 📍 Delivered ✅ at {HH:MM}
```

**Note**: After delivery, keyboard shows only `[❌ Undeliver]`. Clicking Undeliver reverts to assigned status and restores full keyboard.

---

## 🔗 CALLBACKS

**Format**: `action|order_id|param1|param2|...|timestamp`

### MDG Actions
```
req_asap               ASAP request
req_exact              Exact time picker
req_scheduled          Scheduled orders list
req_vendor             Vendor menu (multi-vendor)
vendor_asap            Vendor-specific ASAP
vendor_time            Vendor-specific time picker
toggle_details         Toggle MDG details
order_ref              Scheduled order clicked
time_same              Same time as reference
time_relative          Offset from reference
exact_hour             Hour selected
exact_selected         Final time selected
assign_myself          Self-assign
assign_to              Show courier menu
assign_other           Assign to courier
hide                   Close menu
```

### RG Actions
```
toggle                 Toggle RG details
works                  Confirm time
later                  Show later picker
prepare                Show prepare picker
later_time             Select later time
prepare_time           Select prepare time
wrong                  Open problem menu
wrong_unavailable      Product N/A
wrong_delay            Delay issue
wrong_canceled         Order canceled
wrong_other            Other issue
delay_time             Select delay time
vendor_exact_time      Vendor exact picker
vendor_exact_hour      Vendor hour
vendor_exact_selected  Vendor final time
```

### UPC Actions
```
navigate               Open Maps
delay_order            Show delay picker
delay_vendor_selected  Select vendor for delay (multi-vendor)
delay_selected         Select delay time
unassign_order         Unassign courier
call_vendor            Call vendor
call_vendor_menu       Show call menu (multi-vendor)
select_restaurant      Alias for call_vendor_menu
confirm_delivered      Mark delivered
undeliver_order        Revert from delivered to assigned
show_assigned          Show combine orders menu
combine_with           Combine with selected order (Phase 3)
```

**Delay Flow (Multi-Vendor):**
1. Click `[⏳ Delay]` → Shows vendor selection
2. Select vendor → Shows time picker (+5/+10/+15/+20)
3. Select time → Sends delay request to vendor
4. ST-UPC-DELAY sent to MDG

---

## 💾 STATE

Core fields in `STATE[order_id]`:

```python
{
    # Identity
    "order_id": "7404590039306",
    "name": "dishbee #62",
    "order_type": "shopify|smoothr_dnd|smoothr_lieferando",
    "order_source": "dishbee",
    
    # Customer
    "customer": {
        "name": "John Doe",
        "phone": "+49123456789",
        "address": "Lederergasse 15",
        "zip": "94032",
        "original_address": "Full for maps"
    },
    
    # Vendors
    "vendors": ["Leckerolls", "dean & david"],
    "vendor_items": {
        "Leckerolls": ["1 x Classic", "2 x Fries"],
        "dean & david": ["1 x Salad"]
    },
    
    # Time
    "requested_time": "14:30",
    "confirmed_times": {
        "Leckerolls": "14:35",
        "dean & david": "14:40"
    },
    "created_at": datetime,
    
    # Assignment
    "status": "new|assigned|delivered",
    "assigned_to": 383910036,
    "assigned_by": "self-assigned",
    "delivered_at": datetime,
    "delivered_by": 383910036,
    
    # Messages
    "mdg_message_id": 123456,
    "rg_message_ids": {
        "Leckerolls": 789,
        "dean & david": 790
    },
    "upc_message_id": 654321,
    "mdg_additional_messages": [111, 222],
    
    # UI State
    "vendor_expanded": {"Leckerolls": False},
    "mdg_details_expanded": False,
    
    # Status History
    "status_history": [
        {"type": "new", "timestamp": datetime},
        {"type": "asap_sent", "vendor": "LR", "timestamp": datetime},
        {"type": "confirmed", "vendor": "LR", "time": "14:35", "timestamp": datetime},
        {"type": "assigned", "courier": "Bee 1", "courier_id": 383910036, "timestamp": datetime},
        {"type": "delivered", "courier": "Bee 1", "time": "14:52", "timestamp": datetime}
    ],
    
    # Payment
    "payment_method": "Paid|Cash on Delivery",
    "total": "45.50",
    "tips": "5.00",
    "note": "Customer note",
    
    # Optional
    "district": "Innstadt",
    "group_id": "grp_123",
    "group_color": "🟣",
    "group_position": 1
}
```

---

## ⚙️ KEY FUNCTIONS

```python
# Message Building
build_mdg_dispatch_text()          # MDG-ORD text
build_vendor_summary_text()        # RG-SUM collapsed
build_vendor_details_text()        # RG-DET expanded
build_assignment_message()         # UPC-ASSIGN
build_assignment_confirmation_message()  # MDG-CONF with counts

# Keyboards
mdg_initial_keyboard()             # MDG buttons (initial)
mdg_time_request_keyboard()        # MDG buttons (after time sent)
build_vendor_response_keyboard()   # RG buttons
build_assignment_keyboard()        # UPC buttons
mdg_time_submenu_keyboard()        # Scheduled orders list
build_time_offset_keyboard()       # +/- buttons
courier_selection_keyboard()       # Live courier menu
build_combine_keyboard()           # Assigned orders menu

# Status System
build_status_lines()               # Generate status from history
send_status_message()              # Send temp (auto-delete 20s)

# Time Logic
get_recent_orders_for_same_time()  # Last 10 orders (5h max)
abbreviate_street()                # Shorten street names
build_smart_time_suggestions()     # +N minute buttons

# Product Handling
clean_product_name()               # Simplify names (17 rules)

# Courier Management
get_couriers_from_mdg()            # Live from MDG admins
get_couriers_from_map()            # Fallback to COURIER_MAP
update_mdg_with_assignment()       # Update after assignment
send_assignment_to_private_chat()  # Send UPC-ASSIGN

# State Management
check_all_vendors_confirmed()      # All vendors ready?
cleanup_mdg_messages()             # Delete temp messages
handle_delivery_completion()       # Mark as delivered
handle_undelivery()                # Revert to assigned

# Delay Management
show_delay_options()               # Vendor selection (multi)
show_delay_time_picker()           # Time picker (+5/+10/+15/+20)

# Restaurant Communication
show_restaurant_selection()        # Call vendor menu
forward_restaurant_message_to_mdg()  # RG → MDG forwarding
forward_mdg_reply_to_restaurant()    # MDG → RG forwarding

# Smoothr Integration
parse_smoothr_order()              # Parse text format
process_smoothr_order()            # Process order
is_smoothr_order()                 # Detect format

# Test Commands
handle_test_smoothr_command()      # /test_smoothr simulation
handle_test_shopify_command()      # /test_shopify simulation

# District Detection
get_district_from_address()        # Google Maps API

# Group Orders (Phase 3)
generate_group_id()                # New group ID
get_next_group_color()             # Assign color
get_group_orders()                 # Orders in group
get_assigned_orders()              # All assigned orders
show_combine_orders_menu()         # Combine UI
```

---

## 🚀 WORKFLOWS

### 📦 Complete Order Flow

```
1. ORDER ARRIVAL
   Shopify webhook → parse → create STATE
   Smoothr HTTP POST → parse → create STATE
   
2. INITIAL MESSAGES
   MDG-ORD (collapsed + buttons)
   RG-SUM (collapsed + toggle)
   
3. TIME REQUEST
   Single: [⚡ Asap] [🕒 Time] [🗂 Scheduled]
   Multi: [Ask {chef} {Vendor}] → submenu
   
4. SCHEDULED ORDERS (if recent exist)
   Click reference → offset menu:
   [🔁 Same]* [-5m] [+3m] [+5m] [+10m] [+15m] [+20m] [+25m]
   
5. VENDOR RESPONSE
   RG-TIME-REQ sent
   Vendor: [Works 👍] [⌚️ Later] [🚩 Problem]
   
6. CONFIRMATION
   ST-WORKS/PREP/LATER → MDG (20s)
   RG-CONF → Vendor
   MDG-ORD updated
   All confirmed → Assignment buttons
   
7. ASSIGNMENT
   [👈 Myself] or [👉 Assign to...]
   UPC-ASSIGN → Courier
   MDG-ORD updated
   
8. DELIVERY
   [✅ Delivered]
   MDG-ORD updated
   Order complete
```

---

### 🔄 Smoothr Integration

```
1. HTTP POST to /smoothr
   {"text": "- Order: 505\n...", "secret": "..."}
   
2. Validate secret → Parse text
   
3. Determine type:
   500-series → smoothr_dnd
   6-char alphanumeric → smoothr_lieferando
   
4. Create STATE (vendor: dean & david)
   
5. Send MDG-ORD + RG-SUM
   
6. Continue normal workflow
```

**Test**: `/test_smoothr [dnd|dnd_asap|lieferando|lieferando_asap]`

---

## 🏪 RESTAURANTS

```
JS = Julis Spätzlerei
LR = Leckerolls
ZH = Zweite Heimat
DD = dean & david
PF = Pommes Freunde
KA = Kahaani
SA = i Sapori della Toscana
AP = Wittelsbacher Apotheke
```

**Chef Emojis**: 12 variations rotate via `hash(vendor_name) % 12`
```
👩‍🍳 👩🏻‍🍳 👩🏼‍🍳 👩🏾‍🍳 🧑‍🍳 🧑🏻‍🍳 🧑🏼‍🍳 🧑🏾‍🍳 👨‍🍳 👨🏻‍🍳 👨🏼‍🍳 👨🏾‍🍳
```

---

## 🚴 COURIERS

```
B1 = Bee 1 (383910036)
B2 = Bee 2 (6389671774)
B3 = Bee 3 (8483568436)
```

**Priority**: B1, B2, B3 first, then alphabetically  
**Detection**: Live from MDG admins → fallback to COURIER_MAP  
**Auto-shortcut**: First 2 letters of username

---

## 🎨 VISUAL ELEMENTS

### Chef Emojis
- **Usage**: Headers, status, buttons
- **Selection**: `CHEF_EMOJIS[hash(vendor) % 12]`

### Group Colors
```
🟣 🔵 🟢 🟡 🟠 🔴 🟤
Rotation: color = GROUP_COLORS[index % 7]
```

### District Detection
- **API**: Google Maps Geocoding
- **Display**: `🏙️ {District} ({zip})`
- **Requires**: `GOOGLE_MAPS_API_KEY` env var

---

## 🗑️ AUTO-DELETE

### 20-Second Timer
```python
send_status_message(chat_id, text, auto_delete_after=20)
```

**With auto-delete:**
- ✅ ST-WORKS, ST-PREP, ST-LATER
- ✅ ST-ASAP-SENT, ST-TIME-SENT
- ✅ ST-DELAY, ST-CANCEL, ST-WRITE

**WITHOUT auto-delete:**
- ❌ MDG-ORD, RG-SUM/DET, RG-CONF, UPC-ASSIGN

### Temp Menu Cleanup
```python
cleanup_mdg_messages(order_id)  # Deletes mdg_additional_messages
```

**Triggers**: Final selection, assignment, [← Back]

---

## 🔧 ENVIRONMENT VARIABLES

```bash
# Authentication
BOT_TOKEN=7064983715:AAH6xz2p1QxP5h2EZMIp1Uw9pq57zUX3ikM

# Webhooks
SHOPIFY_WEBHOOK_SECRET=0cd9ef469300a40e7a9c03646e4336a19c592bb60cae680f86b41074250e9666
SMOOTHR_WEBHOOK_SECRET=8Lfwef9XRhmCaOnR0GizQd53VXLCiPdF

# Chat IDs
DISPATCH_MAIN_CHAT_ID=-4825320632

# Vendors (JSON)
VENDOR_GROUP_MAP={"Pommes Freunde":-4955033989,"Zweite Heimat":-4850816432,...}

# Couriers (JSON, fallback)
COURIER_MAP={"383910036":{"username":"Bee 1","is_courier":true},...}

# Optional
GOOGLE_MAPS_API_KEY=your_key  # District detection
```

---

## 📚 PROMPTING EXAMPLES

### ✅ Good
```
"Update MDG-CONF to show per-vendor product counts"
"Add 🔥 emoji to urgent orders in RG-SUM header"
"Fix BTN-WORKS not updating confirmed_times dict"
"Change scheduled orders to show last 15 instead of 10"
"Add district line to UPC-ASSIGN after address"
```

### ❌ Bad
```
"The button doesn't work"           ← Too vague
"Show more info"                    ← Unclear what/where
"Fix the order"                     ← Which? What's broken?
"Make it better"                    ← Subjective
```

---

## 🐛 RECENT FIXES (Oct 2025)

1. **CHEF_EMOJIS Import** - Added to main.py imports (03d6a20)
2. **Missing Vendor Param** - Added to get_recent_orders (5e379ed)
3. **Invalid Hour Picker** - Skip hour if minute >= 57 (5cfe5b4)
4. **Circular Import** - Changed rg.py imports (23b227e)
5. **Multi-Vendor Time** - Use confirmed_times dict (pending)
6. **ASAP Status Missing** ⚠️ - Re-added send_status_message (62b7785)
7. **Street "Unkn"** - Fixed abbreviation (62b7785)
8. **Smoothr Detection** - Added channel_post support (pending)

## 🆕 NEW FEATURES (Oct 31, 2025)

1. **Undeliver Functionality** - Revert delivered orders back to assigned
2. **Combine Orders UI** - Show assigned orders menu (Phase 2 complete)
3. **Multi-Vendor Delay** - Select specific vendor for delay requests
4. **Assignment Confirmation Format** - New format with vendor shortcuts + product counts
5. **Test Commands** - `/test_smoothr` and `/test_shopify` for order simulation
6. **Enhanced UPC Delay** - Separate delay flow for single vs multi-vendor
7. **Live Courier Detection** - Queries MDG admins API (fallback to COURIER_MAP)

---

**Last Updated**: October 31, 2025 • **Version**: 3.1 (Undeliver + Combine Orders Phase 2)  
**See also**: AI-INSTRUCTIONS.md, SYSTEM-REFERENCE.md

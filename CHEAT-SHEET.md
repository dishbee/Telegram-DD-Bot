# ⚡ TELEGRAM BOT CHEAT SHEET

> **Purpose**: Quick reference for prompting AI agents with shortcuts, message formats, button actions, and workflows.

---

## 🎯 QUICK NAVIGATION

| Section | Description |
|---------|-------------|
| [📡 **CHANNELS**](#-channels) | MDG, RG, UPC communication surfaces |
| [💬 **MESSAGES**](#-messages) | All message formats (MDG-ORD, RG-SUM, UPC-ASSIGN, etc.) |
| [🔘 **BUTTONS**](#-buttons) | All interactive buttons and actions |
| [⏱️ **STATUS**](#️-status-system) | Status lines and auto-updates |
| [🔗 **CALLBACKS**](#-callbacks) | Callback data formats |
| [💾 **STATE**](#-state) | Order state structure |
| [⚙️ **FUNCTIONS**](#️-functions) | Key functions reference |
| [🚀 **WORKFLOWS**](#-workflows) | Complete order flows (Shopify + Smoothr) |
| [🏪 **RESTAURANTS**](#-restaurants) | Restaurant shortcuts (JS, LR, DD...) |
| [🚴 **COURIERS**](#-couriers) | Courier shortcuts (B1, B2, B3...) |

---

## 📡 CHANNELS

Three communication surfaces handle the complete order lifecycle:

| Shortcut | Full Name | Purpose | Who Sees It |
|----------|-----------|---------|-------------|
| **MDG** | Main Dispatch Group | Order arrival, time coordination, assignment | Coordinators + Couriers |
| **RG** | Restaurant Groups | Vendor-specific details, time responses | Specific vendor only |
| **UPC** | User Private Chat | Courier assignment, delivery actions | Assigned courier only |

**Flow**: Shopify/Smoothr → **MDG + RG** → Time negotiation → Assignment → **UPC** → Delivery

---

## 💬 MESSAGES

### 📍 MDG Messages (Main Dispatch Group)

**MDG-ORD** - Order arrives (main message - summary by default)
```
Format: 🔖 #{num} - dishbee
        👩‍🍳 {Vendor Shortcuts} 🍕 {Product Counts}
        👤 {Customer Name}
        🗺️ [{Address} ({zip})](maps link)
        
        ❕ Note: {Customer Note} (if exists)
        ❕ Tip: {Amount}€ (if tip)
        ❕ Cash: {Total}€ (if COD)
        
        [{phone}](tel:{phone}) (if phone exists)

Note: Chef emoji (👩‍🍳) is first of 12 rotating emojis, same across all vendors in header
```

Buttons (single vendor):
[Details ▸]
[⚡ Asap]
[🕒 Time picker]
[🗂 Scheduled orders] (only if recent orders exist)

Buttons (multi-vendor):
[Details ▸]
[Ask 👩‍🍳 JS] (one button per vendor, chef emoji rotates)
[Ask 👨‍🍳 LR]
[Ask 👨🏻‍🍳 DD]
```

**MDG-ORD → After BTN-TIME clicked**
```
Shows scheduled orders menu (if available):
Header: "⏰ ASAP, 🕒 Time picker, 🗂 Scheduled orders"

Scheduled orders (recent confirmed orders, last 10, within 5 hours):
[02 - LR - 20:46 - Ledererga. 15]
[60 - JS - 20:50 - Grabeng. 8]
[60 - DD - 20:55 - Grabeng. 8]  ← Multi-vendor shows separate buttons
[← Back]

Format: {num} - {vendor_shortcut} - {time} - {abbreviated_address}
- Multi-vendor orders show separate button per vendor with their specific confirmed time
- Street names abbreviated (max 15 chars, tier 2 if button >64 chars total)

Or direct to exact time picker (if no recent orders):
[12:XX] [13:XX] [14:XX]... [23:XX]
[← Back]

Note: Hour picker skips current hour if current minute >= 57 (no valid future minutes)
Note: If NO recent orders exist, 🕒 Time picker goes directly to hour picker instead of scheduled orders list
```

**MDG-ORD → After selecting scheduled order**
```
Shows time adjustment options:
[🔁 Same time] (only if vendors match between current and reference orders)
[-5m → ⏰ 20:41]
[-3m → ⏰ 20:43]
[+3m → ⏰ 20:49]
[+5m → ⏰ 20:51]
[+10m → ⏰ 20:56]
[+15m → ⏰ 21:01]
[+20m → ⏰ 21:06]
[+25m → ⏰ 21:11]
[← Back]

Format: "{offset}m → ⏰ {time}"
Note: "Same time" only appears if current order shares vendor with reference order
Note: 8 offset options (negative and positive) - NO "EXACT TIME" in this submenu
```

**MDG-ORD → After BTN-VENDOR clicked (multi-vendor only)**
```
Shows vendor-specific action menu:
Message: "Request time from {chef_emoji} **{Vendor Name}**:"

[⚡ Asap]
[🕒 Time picker]
[🗂 Scheduled orders] (only if recent orders exist for this vendor)
[← Back]

Note: This is the vendor-specific menu, NOT the scheduled orders list itself
Note: Clicking "🗂 Scheduled orders" opens scheduled orders filtered by vendor
Note: Clicking "🕒 Time picker" opens hour picker directly OR scheduled orders if available
```

**MDG-ORD (Expanded)** - When Details clicked
```
First shows district if detected:
🏙️ {District} ({zip})

Then full product list:

{Vendor Name}: (if multi-vendor)
{qty} x {Product Name}
{qty} x {Product Name}

Or: (if single vendor, no vendor name shown)
{qty} x {Product Name}
{qty} x {Product Name}
{Total}€ (if NOT COD)

[◂ Hide] button
Same action buttons as collapsed view (Asap/Time picker/Scheduled orders OR vendor buttons)
```

**MDG-CONF** - All vendors confirmed
```
Format: 👍 #{num} - dishbee 🍕 {count} or {count1+count2}
        
        👩‍🍳 {Vendor Shortcut}: {time}
        🧑‍🍳 {Vendor Shortcut}: {time}

Examples:
Single vendor: 👍 #58 - dishbee 🍕 3
               
               👩‍🍳 LR: 12:55

Multi-vendor:  👍 #58 - dishbee 🍕 1+3
               
               👩‍🍳 JS: 12:50
               🧑‍🍳 LR: 12:55

Chef emojis rotate through 12 variations:
['👩‍🍳', '👩🏻‍🍳', '👩🏼‍🍳', '👩🏾‍🍳', '🧑‍🍳', '🧑🏻‍🍳', '🧑🏼‍🍳', '🧑🏾‍🍳', '👨‍🍳', '👨🏻‍🍳', '👨🏼‍🍳', '👨🏾‍🍳']

Note: Uses vendor shortcuts (JS, LR, DD) not full names
Note: Product counts shown in header (1+3), not per vendor line
```

**MDG-ASSIGNED** - Order assigned to courier
```
Adds: "👤 **Assigned to:** {courier name}"
```

**MDG-DELIVERED** - Order completed
```
Adds: "👤 **Assigned to:** {courier}
       ✅ **Delivered**"
```

---

### 🏪 RG Messages (Restaurant Groups)

**RG-SUM** - Order arrives (vendor summary - collapsed by default)
```
Format: 🔖 Order #{num}

        {qty} x {Product Name}
        {qty} x {Product Name}
        
        ❕ Note: {Customer Note} (if exists)
        
        [Details ▸] button
```

**RG-DET** - Order details (expanded view)
```
Format: 🔖 Order #{num}

        {qty} x {Product Name}
        {qty} x {Product Name}
        
        ❕ Note: {Customer Note} (if exists)
        
        🧑 {Customer Name}
        🗺️ {Street + Building}
        📞 {phone}
        ⏰ Ordered at: {time}
        
        [◂ Hide] button
```

**RG-TIME-REQ** - Time request to vendor
```
"Can you prepare 🔖 #{num} at {time}?" (from +X or EXACT)
"Can you prepare 🔖 #{num} ASAP?" (from BTN-ASAP)
"Can you prepare {order} together with {ref_order} at {time}?" (from BTN-SAME)
```

**RG-UNAVAIL** - Product unavailable (sent to RG, not MDG)
```
"Please call customer and ask him which product he wants instead. If he wants a refund - please write dishbee into this group."
```

**RG-CONF** - Vendor confirmation (sent to RG after vendor confirms time)
```
"Confirmation was sent to dishbee. Please prepare 🔖 #{num} at {time} for courier."

Sent immediately after vendor clicks BTN-WORKS, BTN-LATER, or BTN-PREP
```

**RG-DELAY-REQ** - Delay request from courier
```
"We have a delay, if possible prepare #{num} at {time}. If not, please keep it warm."
```

---

### 💼 UPC Messages (User Private Chat)

**UPC-ASSIGN** - Assignment message to courier
```
Format: 👉 #{num} - dishbee
        👩‍🍳 {Vendor Shortcut}: {time} 🍕 {count}
        🧑‍🍳 {Vendor Shortcut}: {time} 🍕 {count}
        👤 {Customer Name}
        🧭 {Address} ({zip})
        ❕ Tip: {amount}€ (if applicable)
        ❕ Cash: {amount}€ (if COD)
        ☎️ {phone}

Chef emojis rotate: 👩‍🍳👩🏻‍🍳👩🏼‍🍳👩🏾‍🍳🧑‍🍳🧑🏻‍🍳🧑🏼‍🍳🧑🏾‍🍳👨‍🍳👨🏻‍🍳👨🏼‍🍳👨🏾‍🍳

NOTE: Vendor shortcuts used (JS, LR, DD, etc.) instead of full names
NOTE: No delivery completion message sent to courier after BTN-DELIVERED clicked
```

---

## 🔘 BUTTONS

### 📍 MDG Buttons (Main Dispatch Group)

**Initial Actions:**
```
BTN-ASAP        = ⚡ Asap (single vendor only)
                  └─ Sends ASAP request to restaurant
                  └─ Message: "Can you prepare 🔖 #{num} ASAP?"
BTN-TIME-PICKER = 🕒 Time picker (single vendor only)
                  └─ Opens hour picker directly
BTN-SCHEDULED   = � Scheduled orders (single vendor, conditional)
                  └─ Only shown if recent confirmed orders exist
                  └─ Opens scheduled orders list
BTN-VENDOR      = Ask {chef_emoji} {Vendor Shortcut} (multi-vendor orders)
                  └─ Opens vendor-specific action menu
                  └─ Shows: ⚡ Asap, 🕒 Time picker, 🗂 Scheduled orders (conditional), ← Back
                  └─ Chef emoji rotates based on vendor index
```

**After BTN-TIME clicked:**
```
BTN-ORD-REF     = Scheduled order button (e.g., "02 - LR - 20:46 - Ledererga. 15")
                  └─ Format: {num} - {vendor_shortcut} - {time} - {address}
                  └─ Street names abbreviated (max 15 chars normally, tier 2 if button >64 chars)
                  └─ Multi-vendor reference orders show separate button per vendor with their specific time
                  └─ Shows: BTN-SAME (if vendors match) / BTN-OFFSET options
```

**Time Selection:**
```
BTN-SAME        = 🔁 Same time (only if vendors match)
                  └─ Sends "together with" message to matching vendor
                  └─ Format: "Can you prepare {current} together with {ref} at {time}?"
BTN-OFFSET      = -5m / -3m / +3m / +5m / +10m / +15m / +20m / +25m (from reference time)
                  └─ Format: "+5m → ⏰ 20:51" or "-5m → ⏰ 20:41"
                  └─ Sends time request with calculated time
BTN-EXACT       = Hour picker access (🕒 Time picker button when no recent orders)
                  └─ Opens hour picker (hour → minute)
                  └─ Hour picker skips current hour if minute >= 57 (no valid future minutes)
                  └─ Minutes shown in 3-minute intervals (00, 03, 06... 57)
BTN-BACK        = ← Back (closes menu)
```

**After All Vendors Confirm:**
```
BTN-ASSIGN-ME   = 👈 Assign to myself
BTN-ASSIGN-TO   = 👉 Assign to... (shows courier list)
```

**Courier Selection:**
```
BTN-COURIER     = Individual courier buttons (Bee 1, Bee 2, etc.)
BTN-BACK        = ← Back (closes selection)
```

> 📝 Note: All MDG temporary menus have "← Back" button

---

### 🏪 RG Buttons (Restaurant responses)

**On RG-SUM/RG-DET message:**
```
BTN-TOGGLE      = Details ▸ (expand) / ◂ Hide (collapse)
                  └─ Toggles between summary and detailed view
                  └─ Updates vendor_expanded state
```

**On TIME Request (from MDG dispatcher):**
```
BTN-WORKS       = Works 👍
                  └─ Confirms requested time works
                  └─ Updates confirmed_times in STATE
                  └─ Sends ST-WORKS to MDG (auto-delete 20s)
                  └─ Triggers assignment buttons if all vendors confirmed

BTN-LATER       = ⏰ Later at...
                  └─ Opens time picker (+5/+10/+15/+20 from requested time)
                  └─ Plus: EXACT TIME ⏰ button
                  └─ Plus: ← Back button
                  └─ On selection: Updates confirmed_times, sends ST-LATER

BTN-WRONG       = ⚠️ Issue
                  └─ Opens issue type submenu with 5 options:
                  └─ BTN-UNAVAIL (🍕 Product(s) N/A)
                  └─ BTN-DELAY (⏳ We have a delay)
                  └─ BTN-CANCEL (❌ Order is canceled)
                  └─ BTN-OTHER (💬 Something else)
                  └─ BTN-BACK (← Back)
                  └─ See BTN-WRONG Submenu section below for details
```

**On ASAP Request (from MDG dispatcher):**
```
BTN-PREP        = Will prepare at...
                  └─ Opens time picker (+5/+10/+15/+20 from now)
                  └─ Plus: EXACT TIME ⏰ button
                  └─ Plus: ← Back button
                  └─ On selection: Updates confirmed_times, sends ST-PREP

BTN-WRONG       = ⚠️ Issue
                  └─ Opens issue type submenu (same as TIME request)
                  └─ See BTN-WRONG Submenu section below for details
```

**Time Picker (from BTN-LATER or BTN-PREP):**
```
BTN-TIME-OPTS   = +5 / +10 / +15 / +20 minute buttons
                  └─ Quick selection relative to requested/current time
                  └─ On click: Confirms time, updates STATE, notifies MDG

BTN-EXACT-TIME  = EXACT TIME ⏰
                  └─ Opens hour selection picker
                  └─ See Exact Time Flow below

BTN-BACK        = ← Back
                  └─ Returns to main response buttons
```

**Exact Time Flow:**
```
BTN-EXACT-TIME  = EXACT TIME ⏰ (from time picker)
                  └─ Opens hour picker: 12:XX, 13:XX, 14:XX... (current hour to 23:XX)
                  └─ Skips current hour if current minute >= 57 (no valid future minutes remain)
                  └─ Has ← Back button (returns to +5/+10/+15/+20 picker or scheduled orders)

BTN-HOUR        = Hour selection (e.g., "14:XX")
                  └─ Opens minute picker for selected hour
                  └─ Minutes: 00, 03, 06, 09... 57 (3-minute intervals)
                  └─ If current hour selected: only shows future minutes (current_minute rounded up to next 3-min interval)
                  └─ Has ◂ Back button (returns to hour selection)

BTN-MINUTE      = Minute selection (e.g., "14:35")
                  └─ Confirms exact time
                  └─ Updates confirmed_times in STATE
                  └─ Sends status to MDG (ST-LATER or ST-PREP)
                  └─ Deletes picker message
```

**BTN-WRONG Submenu:**
```
BTN-WRONG       = ⚠️ Issue (main button)
                  └─ Opens issue type submenu with options:

    BTN-UNAVAIL     = 🍕 Product(s) N/A
                      └─ Sends message to RG (vendor's group):
                      └─ "Please call customer and ask him which product he wants instead.
                          If he wants a refund - please write dishbee into this group."

    BTN-DELAY       = ⏳ We have a delay
                      └─ Opens delay time picker (+5/+10/+15/+20)
                      └─ On selection: Sends ST-DELAY to MDG and courier
                      └─ Updates confirmed_times with new delayed time

    BTN-CANCEL      = ❌ Order is canceled
                      └─ Sends ST-CANCEL to MDG: "Order is canceled"

    BTN-OTHER       = 💬 Something else
                      └─ Prompts vendor for text input
                      └─ Sends ST-WRITE to MDG with vendor's message

    BTN-BACK        = ← Back
                      └─ Closes submenu, returns to main response buttons
```

> 📝 Note: All RG temporary menus (time pickers, issue submenu) have "← Back" button

---

### 💼 UPC Buttons (Courier actions)

**On UPC-ASSIGN message:**
```
BTN-NAVIGATE    = 🧭 Navigate (Google Maps cycling mode)
BTN-DELAY-ORD   = ⏰ Delay (triggers delay workflow)
                  └─ Shows picker: "14:35 (+5 mins)", "14:40 (+10 mins)", etc.
                  └─ Sends to vendors: "We have a delay..."
                  └─ Confirms to courier: "✅ Delay request sent..."
                  └─ Vendors respond with BTN-WORKS or BTN-LATER
BTN-UNASSIGN    = 🔓 Unassign (only before delivery)
                  └─ Removes assignment from courier
                  └─ Deletes UPC message
                  └─ Updates MDG order message (removes "Assigned to:" line)
                  └─ Re-shows MDG-CONF with assignment buttons
                  └─ Sends notification to MDG
BTN-CALL-VEND   = 🏪 Call {Shortcut} (single vendor: direct button)
                  └─ Shows vendor shortcut (JS, LR, DD, etc.)
                  └─ Multi-vendor: opens restaurant selection menu
                  └─ Placeholder for Telegram calling integration
BTN-DELIVERED   = ✅ Delivered (completes order)
                  ├─ Marks "delivered" → records timestamp
                  ├─ Sends ST-DELIVERED to MDG: "🔖 #{num} was delivered by {courier} at {HH:MM}"
                  └─ NOTE: No confirmation message sent to courier

> 📝 Note: All buttons displayed vertically (one per row) for easy mobile access
```

**Delay Time Picker:**
```
BTN-DELAY-SEL   = Time buttons with +X labels
                  ├─ Format: "HH:MM (+X mins)" e.g., "14:35 (+5 mins)"
                  └─ On click: Sends ST-UPC-DELAY to MDG: "📨 DELAY request ({time}) for 🔖 #{num} sent to {Shortcut}"
BTN-BACK        = ← Back (closes delay menu)
```

**Restaurant Call Menu (multi-vendor):**
```
BTN-CALL-VEND   = � Call {Shortcut} (opens phone dialer)
BTN-BACK        = ← Back (closes menu)
```

> 📝 Note: All UPC temporary menus have "← Back" button

---

## ⏱️ STATUS UPDATES

**NEW SYSTEM:** Status updates are **PREPENDED at the TOP** of message text showing current order state. Status lines **REPLACE** previous status (never accumulate).

### MDG-ORD (Main Dispatch Message) - Status Lines

Status appears at TOP before order details:

```
1. 🚨 New order
   → Initial state when order arrives from Shopify

2. 📍 Sent ⚡ Asap to 👨‍🍳 {Shortcut}
   → After BTN-ASAP clicked (req_asap / vendor_asap handler)
   → Multi-vendor: Separate line per vendor with rotating chef emoji
   
3. 📍 Sent 🕒 {time} to 👨‍🍳 {Shortcut}
   → After time request sent (exact_selected / time_relative / time_same)
   → Multi-vendor: Separate line per vendor with rotating chef emoji
   
4. 📍 Confirmed 👍 {time} by 👨‍🍳 {Shortcut}
   → After vendor confirms (BTN-WORKS / BTN-PREP / BTN-LATER)
   → Multi-vendor: Separate line per vendor with rotating chef emoji + their confirmed time
   
5. � Assigned 👉 to 🐝 {courier}
   → After BTN-ASSIGN-ME / BTN-ASSIGN-OTHER clicked
   → Uses courier shortcut (B1, B2, B3) or username
   
6. 📍 Delivered ✅ at {HH:MM} by 🐝 {courier}
   → After BTN-DELIVERED clicked
   → Shows delivery time and courier shortcut
```

**Multi-Vendor Example:**
```
📍 Sent ⚡ Asap to 👩‍🍳 LR
📍 Sent ⚡ Asap to 👨‍🍳 DD

🔖 #58 - dishbee
...
```

---

### RG-SUM (Restaurant Group Message) - Status Lines

Status appears at TOP before product list:

```
1. 🚨 New order
   → Initial state when order arrives

2. 📍 Asked for ⚡ Asap by dishbee
   → After ASAP request received from MDG

3. 📍 Asked for 🕒 {time} by dishbee
   → After time request received from MDG

4. 📍 Prepare this order at {time} 🫕
   → After vendor confirms (BTN-WORKS / BTN-PREP / BTN-LATER)
   → Shows vendor's confirmed time from confirmed_times[vendor]

5. 📍 Delivered ✅
   → After BTN-DELIVERED clicked in UPC
```

---

### UPC-ASSIGN (Courier Private Chat) - Status Lines

Status appears at TOP before order details:

```
1. 🚨 Order assigned 👉 to you (dishbee)
   → Initial assignment message

2. 📍 Delay ⏰ sent to {Shortcut}
   → After BTN-DELAY-ORD clicked + time selected
   → Multi-vendor: Shows all vendor shortcuts (LR+DD)

3. 📍 Delivered ✅ at {HH:MM}
   → After BTN-DELIVERED clicked
   → Shows delivery time
```

**Group Orders:** If order is in a Group (combining system), add **empty line** between status and order details.

---

### Temporary Status Messages (Auto-Delete 20s)

These are **SENT as separate messages** (not part of status lines):

```
ST-WORKS      = {chef_emoji} {Vendor} replied: {time} for 🔖 #{num} works 👍
ST-PREP       = {chef_emoji} {Vendor} replied: Will prepare 🔖 #{num} at {time} 👍
ST-LATER      = {chef_emoji} {Vendor} replied: Will prepare 🔖 #{num} later at {time} 👍
ST-DELAY      = {chef_emoji} {Vendor}: We have a delay for 🔖 #{num} - new time {time}
ST-CANCEL     = {chef_emoji} {Vendor}: Order 🔖 #{num} is canceled
ST-WRITE      = {chef_emoji} {Vendor}: Issue with 🔖 #{num}: "{vendor's message}"
ST-ASAP-SENT  = ⚡ Asap request for 🔖 #{num} sent to {Shortcut}
ST-TIME-SENT  = 🕒 Time request ({time}) for 🔖 #{num} sent to {Shortcut}
ST-UPC-DELAY  = 🕒 DELAY request ({time}) for 🔖 #{num} sent to {Shortcut}
```

> 📝 Note: Chef emoji rotates through 12 variations based on vendor name hash

---

## 🗑️ TEMPORARY MESSAGES
*(Cleaned up after action)*

```
TMP-REQ-VENDOR  = 📍 Request time from {vendor}:
TMP-TIME-PICK   = Time picker menus (BTN-PLUS buttons)
TMP-SAME-SEL    = Recent order selection menu
TMP-EXACT-HOUR  = Hour selection (10:XX-23:XX)
TMP-EXACT-MIN   = Minute selection (00-57 in 3-min intervals)
TMP-COURIER-SEL = Courier selection menu
TMP-DELAY-PICK  = Delay time picker (UPC)
```

---

## ⚙️ FUNCTIONS

```
FN-CLEAN-NAME   = Clean product names (removes prefixes, extracts quoted text)
                  └─ 17 rules: removes burger/pizza/spätzle/pasta/roll prefixes
                  └─ Extracts quoted text: [Bio-Burger "Classic"] → Classic
                  └─ Simplifies fries/pommes: Bio-Pommes → Pommes
                  └─ Location: utils.py clean_product_name()

FN-ABBREV-STREET = Abbreviate street names for buttons (BTN-ORD-REF only)
                   └─ Tier 1: Straße→Str., compound→Dr.Step.Bill.Str.
                   └─ Tier 2 (>64 chars total): First 4 letters only (Lede 15)
                   └─ Location: mdg.py abbreviate_street()

FN-CHECK-CONF   = Check if all vendors confirmed (checks confirmed_times dict)
                  └─ Returns True if all vendors have entry in confirmed_times
                  └─ Location: main.py check_all_vendors_confirmed()

FN-SEND-ASSIGN  = Send assignment to courier (UPC-ASSIGN)
                  └─ Sends private message with order details + action buttons
                  └─ Updates MDG message with assignment status
                  └─ Location: upc.py send_assignment_to_courier()

FN-UPDATE-MDG   = Update MDG message with assignment/delivery status
                  └─ Edits original order message to add/update status lines
                  └─ Location: main.py (inline in handlers)

FN-CLEANUP      = Delete temp msgs (time pickers, selection menus)
                  └─ Deletes all messages in order["mdg_additional_messages"]
                  └─ Location: main.py cleanup_mdg_messages()

FN-DELAY-REQ    = Send delay request to vendors
                  └─ Sends "We have a delay..." message to RG
                  └─ Location: main.py (inline in delay handler)

FN-DELIVERED    = Mark order as delivered, update STATE
                  └─ Sets delivered_at timestamp and delivered_by
                  └─ Updates MDG message with ✅ Delivered status
                  └─ Location: main.py (inline in confirm_delivered handler)

FN-GET-RECENT   = Get recent orders for scheduled orders menu (vendor filter optional)
                  └─ Returns last 10 confirmed orders within 5 hours
                  └─ Includes confirmed_times dict for multi-vendor support
                  └─ Location: mdg.py get_recent_orders_for_same_time()

FN-SEND-STATUS  = Send status message with auto-delete (wrapper function)
                  └─ Sends message to MDG and auto-deletes after X seconds (default 20s)
                  └─ Tracks message ID for cleanup
                  └─ Location: main.py send_status_message(), utils.py send_status_message()

FN-COMBINE-KEYBOARD = Build combining orders keyboard for courier
                      └─ Groups assigned orders by courier with color indicators
                      └─ Shows order num, vendor shortcut, time, abbreviated address
                      └─ Location: mdg.py build_combine_keyboard()

FN-BUILD-STATUS     = Build status lines from status_history (NEW)
                      └─ Generates current status text based on message type (mdg/rg/upc)
                      └─ Returns formatted status line(s) to prepend to message
                      └─ Handles multi-vendor status (separate lines per vendor)
                      └─ Uses rotating chef emoji based on vendor name hash
                      └─ Location: utils.py build_status_lines()
```

**Note:** Added FN-BUILD-STATUS for new status update system. All status updates now use single centralized function.

---

## 💾 STATE

```
order_id            = Shopify order ID (key)
name                = Order number (e.g., "dishbee #62")
vendors             = List of restaurant names
confirmed_time      = Single time (last vendor confirmed, backward compatibility)
confirmed_times     = {vendor: time} dict for multi-vendor per-vendor tracking
requested_time      = Time requested by dispatcher
status              = new/assigned/delivered
status_history      = List tracking all status changes (NEW)
assigned_to         = courier user_id
assigned_by         = Who assigned (username or "self-assigned")
delivered_at        = Timestamp of delivery
delivered_by        = courier user_id who delivered
mdg_message_id      = Main MDG message ID
rg_message_ids      = {vendor: message_id} dict for RG messages (replaces vendor_messages)
upc_message_id      = Message ID for courier's private chat assignment
vendor_messages     = DEPRECATED - use rg_message_ids
vendor_expanded     = {vendor: True/False} toggle state
mdg_additional_messages = List of temp message IDs for cleanup
order_type          = "shopify" or other
customer            = {name, phone, address, original_address}
vendor_items        = {vendor: [item_lines]} dict
payment_method      = "Paid" or "Cash on Delivery"
total               = Order total amount
tips                = Tip amount
note                = Customer note
created_at          = Order timestamp
```

**status_history Structure (NEW):**
```python
status_history = [
    {"type": "new", "timestamp": datetime},
    {"type": "asap_sent", "vendor": "Leckerolls", "timestamp": datetime},
    {"type": "time_sent", "vendor": "dean & david", "time": "14:30", "timestamp": datetime},
    {"type": "confirmed", "vendor": "Leckerolls", "time": "14:35", "timestamp": datetime},
    {"type": "assigned", "courier": "Bee 1", "courier_id": 383910036, "timestamp": datetime},
    {"type": "delay_sent", "vendors": ["Leckerolls"], "time": "14:45", "timestamp": datetime},
    {"type": "delivered", "courier": "Bee 1", "time": "14:52", "timestamp": datetime}
]
```

**Notes:**
- `status_history` tracks ALL status changes chronologically
- `rg_message_ids` replaces `vendor_messages` (old name kept for compatibility)
- `upc_message_id` tracks courier's private chat message for updates
- `confirmed_times` dict for multi-vendor per-vendor time tracking

---

## � AUTO-DELETE PATTERNS

**20-Second Auto-Delete Timer:**
All temporary status messages use `send_status_message(chat_id, text, auto_delete_after=20)`

**Implementation:**
```python
asyncio.create_task(_delete_after_delay(chat_id, message_id, seconds))
```

**Messages with Auto-Delete:**
- ✅ All vendor response statuses (ST-WORKS, ST-PREP, ST-LATER)
- ✅ ASAP/TIME request confirmations (ST-ASAP-SENT, ST-TIME-SENT)
- ✅ Delay request confirmations (ST-UPC-DELAY)
- ✅ Vendor issue notifications (ST-DELAY, ST-CANCEL, ST-WRITE)

**Messages WITHOUT Auto-Delete:**
- ❌ RG-CONF (restaurant confirmation message in vendor group)
- ❌ UPC-ASSIGN (assignment message to courier)
- ❌ MDG-ORD (original order message - permanent)

**Cleanup System:**
- Temporary menus (time pickers, selection menus) tracked in `order["mdg_additional_messages"]`
- Cleaned via `cleanup_mdg_messages(order_id)` after workflow completion
- 3 retry attempts with exponential backoff for network resilience

**Locations:**
- `send_status_message()`: main.py line 234, utils.py line 587
- `_delete_after_delay()`: main.py line 251, 1484, 1558, 1629, 1688, 1843 (6 calls)
- `cleanup_mdg_messages()`: main.py (multiple handler locations)

---

## �🔄 FLOW

```
Shopify Order
    ↓
MDG-ORD + RG-SUM (simultaneously)
    ↓
Single Vendor:                        Multi-Vendor:
[⚡ Asap]                             [Ask 👩‍🍳 JS]
[🕒 Time picker]                      [Ask 👨‍🍳 LR] → Vendor menu:
[🗂 Scheduled orders] (conditional)   [Ask 👨🏻‍🍳 DD]    [⚡ Asap]
                                                     [🕒 Time picker]
                                                     [🗂 Scheduled orders] (conditional)
    ↓
Option A: ⚡ Asap
    └─ Sends ASAP request to restaurant
    
Option B: 🕒 Time picker
    └─ Opens hour picker directly
    
Option C: 🗂 Scheduled orders
    └─ Shows recent confirmed orders list
    └─ Select reference order (BTN-ORD-REF)
        └─ BTN-SAME (if vendors match) or BTN-OFFSET (-5m to +25m)
    ↓
RG-TIME-REQ (time request to restaurant)
    ↓
BTN-WORKS / BTN-LATER / BTN-PREP (vendor response)
    ↓
ST-WORKS / ST-LATER / ST-PREP (auto-delete 20s)
    ↓
Updates confirmed_times dict in STATE
    ↓
FN-CHECK-CONF (checks if all vendors confirmed)
    ↓
MDG-CONF (all vendors confirmed, shows per-vendor times + counts)
    ↓
BTN-ASSIGN-ME / BTN-ASSIGN-TO
    ↓
UPC-ASSIGN (DM to courier with order details)
    ↓
MDG-ASSIGNED (MDG shows assignment)
    ↓
BTN-NAVIGATE / BTN-DELAY-ORD / BTN-UNASSIGN / BTN-DELIVERED
    ↓
BTN-DELIVERED clicked
    ↓
FN-DELIVERED (update STATE, send confirmations)
    ↓
MDG-DELIVERED (updated with delivery status)

Note: ASAP still available, "Same time as" kept (conditional on vendor match)
```

---

## 🕐 SCHEDULED ORDERS FEATURE

The **Scheduled Orders** feature (formerly "Same Time As") shows recent confirmed orders to enable efficient time selection and order coordination.

### Display Format

**Button Format:**
```
{num} - {vendor_shortcut} - {time} - {abbreviated_address}

Example: "02 - LR - 20:46 - Ledererga. 15"
```

**Street Abbreviation (2-tier system):**

Tier 1 (Standard - under 30 chars):
- Straße → Str., Gasse → Ga., Weg → W., Platz → Pl., Allee → Al.
- Doktor → Dr., Professor → Prof., Sankt → St.
- Compound: "Dr.-Stephan-Billinger-Straße" → "Dr.Step.Bill.Str." (no hyphens)

Tier 2 (Aggressive - if button text exceeds 64 chars total):
- First 4 letters only + house number
- "Lederergasse 15" → "Lede 15"
- "Dr.-Stephan-Billinger-Straße 5" → "DrSt 5"

### Criteria for Display

**Order must meet ALL conditions:**
- Has `confirmed_time` (vendor confirmed)
- Status is NOT "delivered"
- Confirmed within last **5 hours** (changed from 1 hour)
- Maximum **10 most recent** orders shown (changed from 50)

### Multi-Vendor Behavior

**Multi-vendor reference orders:**
- Each vendor in the reference order gets **separate button**
- Each button shows that **vendor's specific confirmed time**
- Uses `confirmed_times` dict: `{"Leckerolls": "14:12", "dean & david": "14:15"}`

Example: Order #02 has two vendors with different times:
```
[02 - LR - 14:12 - Grabenge. 15]  ← Leckerolls' time
[02 - DD - 14:15 - Grabenge. 15]  ← dean & david's time
```

**Vendor-specific filtering:**
- When "Ask 👩‍🍳 LR" clicked in multi-vendor order
- Shows only scheduled orders containing Leckerolls
- Each vendor button shows their specific confirmed time

### Time Selection Flow

**Step 1: Click BTN-TIME**
```
Shows scheduled orders (if available):
⏰ ASAP, 🕒 Time picker, 🗂 Scheduled orders

[02 - LR - 20:46 - Ledererga. 15]
[60 - JS - 20:50 - Grabeng. 8]
[← Back]

If NO recent orders: Goes directly to hour picker instead
```

**Step 2: Select scheduled order (BTN-ORD-REF)**
```
Shows time adjustment options with reference time header:
⏰ Reference time: {time} (#{ref_num})
Select option:

[🔁 Same time] (only if vendors match)
[-5m → ⏰ 20:41]
[-3m → ⏰ 20:43]
[+3m → ⏰ 20:49]
[+5m → ⏰ 20:51]
[+10m → ⏰ 20:56]
[+15m → ⏰ 21:01]
[+20m → ⏰ 21:06]
[+25m → ⏰ 21:11]
[← Back]
```

**Step 3: Choose action**

**BTN-SAME** (Same time - only if vendors match):
- Sends "together with" message: `"Can you prepare {current} together with {reference} at {time}?"`
- Only shown if current order shares at least one vendor with reference order

**BTN-OFFSET** (-5m / -3m / +3m / +5m / +10m / +15m / +20m / +25m):
- Sends time request at reference time ± X minutes
- Message: `"Can you prepare 🔖 #{num} at {time}?"`

**Note:** No "EXACT TIME ⏰" button in scheduled orders list. If no recent orders exist, 🕒 Time picker goes directly to hour picker.

### State Tracking

```python
# Per-order state
confirmed_time = "14:15"  # Single time (last vendor confirmed, for backward compatibility)
confirmed_times = {"Leckerolls": "14:12", "dean & david": "14:15"}  # Per-vendor times

# Scheduled orders list (last 10, max 5 hours old)
{
    "order_id": "7404590039306",
    "order_num": "59",
    "confirmed_time": "20:46",  # Fallback for single-vendor
    "confirmed_times": {"Leckerolls": "20:46"},  # Per-vendor dict
    "address": "Lederergasse 15",
    "vendors": ["Leckerolls"],
    "created_at": timestamp
}
```

### Key Changes from Old System

**Removed:**
- ❌ "REQUEST TIME" button label - now "🕒 Time picker"
- ❌ "REQUEST ASAP" button label - now "⚡ Asap"
- ❌ Chef emoji rotation in scheduled order buttons
- ❌ Bookmark (🔖) and map (🗺️) emojis in button format

**Added:**
- ✅ Simplified button format: "{num} - {shortcut} - {time} - {address}"
- ✅ Per-vendor time tracking in confirmed_times dict
- ✅ Separate buttons for each vendor in multi-vendor reference orders
- ✅ Vendor-specific filtering when clicking "Ask 👩‍🍳 {Vendor}"
- ✅ Extended time window (5 hours vs 1 hour)
- ✅ Reduced display count (10 orders vs 50)
- ✅ Hour picker skip logic (skip current hour if minute >= 57)
- ✅ 8 time offset options: -5m, -3m, +3m, +5m, +10m, +15m, +20m, +25m
- ✅ Conditional "🗂 Scheduled orders" button (only if recent orders exist)
- ✅ Vendor-specific action menu for multi-vendor orders

**Kept:**
- ✅ BTN-ASAP functionality - still used for single vendor and vendor-specific requests
- ✅ BTN-SAME ("Same time as") - sends "together with" if vendors match
- ✅ EXACT TIME concept - accessed via "🕒 Time picker" button

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

---

## 🚴 COURIERS

```
B1 = Bee 1
B2 = Bee 2
B3 = Bee 3
```

**Note:** Priority couriers (Bee 1, Bee 2, Bee 3) shown first in assignment menu. Other couriers displayed alphabetically by username with automatic 2-letter shortcut (first 2 letters of username).

---

## 🎨 VISUAL ELEMENTS

### Chef Emojis (Rotating)
```
12 variations: 👩‍🍳👩🏻‍🍳👩🏼‍🍳👩🏾‍🍳🧑‍🍳🧑🏻‍🍳🧑🏼‍🍳🧑🏾‍🍳👨‍🍳👨🏻‍🍳👨🏼‍🍳👨🏾‍🍳

Selection: hash(vendor_name) % 12
Usage: MDG-CONF headers, status messages, vendor buttons
```

### Group Colors (Combining System)
```
7 colors (rotating): 🟣 🔵 🟢 🟡 🟠 🔴 🟤

Used in: build_combine_keyboard() for grouping assigned orders by courier
Max groups: 7 (reuses colors if more couriers)
```

---

## 🏙️ DISTRICTS (Passau)

District detection uses Google Maps Geocoding API to automatically identify the neighborhood/district (sublocality) from the address.

**Requirements:**
- `GOOGLE_MAPS_API_KEY` environment variable
- Results cached per address to minimize API calls

**Display:**
- Shown in MDG Details view as: `🏙️ {District} ({zip})`
- Returns district names like: Innstadt, Altstadt, Hacklberg, Grubweg, Hals, etc.

> 📝 Note: Set `GOOGLE_MAPS_API_KEY` in Render environment variables to enable

---

## 🔗 CALLBACK ACTIONS

**Format:** `action|order_id|param1|param2|...|timestamp`

### MDG Actions (Main Dispatch Group)
```
req_asap            = Request ASAP (single vendor orders)
                      └─ Sends "Can you prepare 🔖 #{num} ASAP?" to vendor(s)
                      └─ Sends status: "⚡ Asap request for 🔖 #{num} sent to {Shortcut}"
                      └─ Handler: main.py line 841 (req_asap)

req_exact           = Show hour picker directly (🕒 Time picker button)
                      └─ Opens hour selection: 12:XX, 13:XX... 23:XX
                      └─ Skips current hour if minute >= 57

req_scheduled       = Show scheduled orders list (🗂 Scheduled orders button)
                      └─ Shows last 10 confirmed orders within 5 hours
                      └─ Conditional: only if recent orders exist

req_vendor          = Show vendor-specific action menu (multi-vendor)
                      └─ Format: req_vendor|{order_id}|{vendor}
                      └─ Displays: ⚡ Asap, 🕒 Time picker, 🗂 Scheduled orders, ← Back

vendor_asap         = ASAP request for specific vendor (multi-vendor)
                      └─ Format: vendor_asap|{order_id}|{vendor}
                      └─ Sends ASAP request to single vendor only

vendor_time         = TIME request for specific vendor (shows scheduled orders or hour picker)
                      └─ Format: vendor_time|{order_id}|{vendor}
                      └─ Shows vendor-filtered scheduled orders if available

time_same           = Send "together with" request (if vendors match)
                      └─ Format: time_same|{order_id}|{ref_order_id}
                      └─ Message: "Can you prepare {current} together with {ref} at {time}?"
                      └─ Only shown if current order shares vendor with reference

time_relative       = Send time with offset (-5m to +25m) from reference order
                      └─ Format: time_relative|{order_id}|{ref_order_id}|{offset_minutes}
                      └─ Offsets: -5, -3, +3, +5, +10, +15, +20, +25 minutes

exact_hour          = Hour selected in exact time picker
                      └─ Format: exact_hour|{order_id}|{hour}
                      └─ Opens minute picker (00, 03, 06... 57 in 3-min intervals)

exact_selected      = Final time selected from exact picker
                      └─ Format: exact_selected|{order_id}|{HH:MM}
                      └─ Sends time request to vendor(s)

order_ref           = Scheduled order button clicked (shows offset options + optional SAME)
                      └─ Format: order_ref|{order_id}|{ref_order_id}|{vendor}
                      └─ vendor="all" for single vendor orders
                      └─ Shows: BTN-SAME (if match), BTN-OFFSET options, ← Back

assign_myself       = User assigns order to themselves
                      └─ Format: assign_myself|{order_id}
                      └─ Self-assigns to button clicker

assign_other        = Assign to specific courier
                      └─ Format: assign_other|{order_id}|{courier_user_id}
                      └─ Assigns to selected courier from menu

assign_to           = Show courier selection menu
                      └─ Format: assign_to|{order_id}
                      └─ Lists: Priority couriers (B1, B2, B3) first, then others alphabetically

hide                = Generic back button (deletes temporary message)
                      └─ Format: hide|{order_id}
                      └─ Calls cleanup_mdg_messages()
```

### RG Actions (Vendor responses)
```
toggle              = Toggle Details ▸ / ◂ Hide
                      └─ Format: toggle|{order_id}|{vendor}
                      └─ Updates vendor_expanded state
                      └─ Switches between RG-SUM and RG-DET

works               = Vendor confirms time works
                      └─ Format: works|{order_id}|{vendor}
                      └─ Updates confirmed_times[vendor]
                      └─ Sends ST-WORKS + RG-CONF
                      └─ Triggers assignment buttons if all vendors confirmed

later               = Show "later at" time picker
                      └─ Format: later|{order_id}|{vendor}
                      └─ Shows +5/+10/+15/+20, EXACT TIME ⏰, ← Back

prepare             = Show "will prepare at" time picker
                      └─ Format: prepare|{order_id}|{vendor}
                      └─ Shows +5/+10/+15/+20, EXACT TIME ⏰, ← Back
                      └─ Used for ASAP responses

later_time          = Vendor selects later time
                      └─ Format: later_time|{order_id}|{vendor}|{minutes}
                      └─ Updates confirmed_times, sends ST-LATER + RG-CONF

prepare_time        = Vendor selects prepare time
                      └─ Format: prepare_time|{order_id}|{vendor}|{minutes}
                      └─ Updates confirmed_times, sends ST-PREP + RG-CONF

wrong_delay         = Vendor reports delay
                      └─ Format: wrong_delay|{order_id}|{vendor}
                      └─ Opens delay time picker

wrong_unavailable   = Product not available
                      └─ Format: wrong_unavailable|{order_id}|{vendor}
                      └─ Sends RG-UNAVAIL to vendor group (NOT MDG)

wrong_canceled      = Order canceled
                      └─ Format: wrong_canceled|{order_id}|{vendor}
                      └─ Sends ST-CANCEL to MDG

wrong_other         = Other issue (text input)
                      └─ Format: wrong_other|{order_id}|{vendor}
                      └─ Prompts for text, sends ST-WRITE

delay_time          = Vendor selects delay time
                      └─ Format: delay_time|{order_id}|{vendor}|{minutes}
                      └─ Updates confirmed_times, sends ST-DELAY

vendor_exact_time   = Show vendor exact time (hour picker)
                      └─ Format: vendor_exact_time|{order_id}|{vendor}
                      └─ Opens hour picker for vendor

vendor_exact_hour   = Vendor selects hour
                      └─ Format: vendor_exact_hour|{order_id}|{vendor}|{hour}
                      └─ Opens minute picker

vendor_exact_selected = Vendor confirms exact time
                        └─ Format: vendor_exact_selected|{order_id}|{vendor}|{HH:MM}|{mode}
                        └─ mode="later" or "prepare"
                        └─ Updates confirmed_times, sends status
```

### UPC Actions (Courier)
```
delay_order         = Show delay time picker
                      └─ Format: delay_order|{order_id}
                      └─ Shows +5/+10/+15/+20 from current time

delay_selected      = Courier selects delay time
                      └─ Format: delay_selected|{order_id}|{minutes}
                      └─ Sends delay request to vendors
                      └─ Sends ST-UPC-DELAY to MDG

unassign_order      = Unassign order from courier (only before delivery)
                      └─ Format: unassign_order|{order_id}
                      └─ Removes assignment, deletes UPC message
                      └─ Updates MDG, re-shows assignment buttons

call_vendor         = Call specific vendor (single vendor direct, or after menu selection)
                      └─ Format: call_vendor|{order_id}|{vendor}
                      └─ Placeholder for Telegram calling integration

call_vendor_menu    = Show vendor selection menu for calling
                      └─ Format: call_vendor_menu|{order_id}
                      └─ Lists all vendors with 🏪 Call {Shortcut} buttons

confirm_delivered   = Mark order as delivered
                      └─ Format: confirm_delivered|{order_id}
                      └─ Sets delivered_at timestamp
                      └─ Updates MDG with ✅ Delivered
                      └─ NO confirmation message sent to courier

navigate            = Open Google Maps
                      └─ Format: navigate|{order_id}
                      └─ Opens cycling mode to customer address
```

**Note:** All callback data includes timestamp to prevent replay attacks and ensure freshness.

---

## 📚 EXAMPLES

❌ **Bad:** "The button doesn't work"  
✅ **Good:** "BTN-WORKS not updating confirmed_times"

❌ **Bad:** "Show more info"  
✅ **Good:** "Add count to RG-SUM like MDG-CONF"

---

## 🐛 RECENT BUG FIXES (Oct 19-20, 2025)

**Bug 1: CHEF_EMOJIS Import Error**
- **Issue:** `req_vendor` handler failed with "name 'CHEF_EMOJIS' is not defined"
- **Fix:** Added `CHEF_EMOJIS` to imports from mdg in main.py line 59
- **Commit:** 03d6a20

**Bug 2: Missing Vendor Parameter**
- **Issue:** `get_recent_orders_for_same_time()` called with vendor= but didn't accept it
- **Fix:** Added `vendor: Optional[str] = None` parameter with filtering logic
- **Commit:** 5e379ed

**Bug 3: Invalid Hour in Time Picker**
- **Issue:** Hour picker showed current hour at X:57 with no valid future minutes (empty keyboard)
- **Fix:** Skip current hour if `current_minute >= 57`, start from `current_hour + 1`
- **Location:** mdg.py lines 738-746, rg.py lines 163-171
- **Commit:** 5cfe5b4

**Bug 4: Circular Import Causing STATE Reset**
- **Issue:** rg.py imported from main.py creating circular dependency → STATE reset to empty {}
- **Symptom:** MDG keyboards reverted to old format after vendor confirmation
- **Fix:** Changed rg.py line 107 from `from main import` to `from mdg import`
- **Commit:** 23b227e

**Bug 5: Multi-Vendor Time Display**
- **Issue:** Multi-vendor reference orders showed same time for all vendors instead of per-vendor times
- **Example:** Order #02 (LR: 14:12, DD: 14:15) displayed both as 14:15
- **Fix:** Modified mdg.py to extract vendor-specific times from `confirmed_times` dict
- **Location:** mdg.py lines 444-488
- **Status:** Fixed (pending commit)

**Bug 6: ASAP Status Message Not Sent** ⚠️ **CRITICAL**
- **Issue:** After clicking ⚡ Asap, status message "⚡ Asap request for 🔖 #{num} sent to {Shortcut}" not sent to MDG
- **Root Cause:** Agent DELETED `send_status_message()` call during formatting commit e7d5c8a while claiming to only change visual formatting
- **Symptom:** Coordinator sees vendor receives ASAP request but no confirmation in MDG
- **Fix:** Added missing `send_status_message()` call in req_asap handler (main.py line 860-867)
- **Location:** main.py line 860-867 (req_asap handler)
- **Commit:** 62b7785
- **Lesson:** NEVER delete working code during "formatting changes" - trace FULL code flow before modifying

**Bug 7: Street Showing "Unkn" in Assigned Orders**
- **Issue:** Street names displayed as "Unkn" in Combined Orders keyboard (build_combine_keyboard)
- **Root Cause 1:** Empty street defaulted to "Unknown address" → abbreviate_street() → "Unkn"
- **Root Cause 2:** Duplicate abbreviation in build_combine_keyboard() after address already abbreviated
- **Fix 1:** Changed default from "Unknown address" to "Unknown" (not abbreviated)
- **Fix 2:** Removed duplicate abbreviation call (address already abbreviated in get_assigned_orders)
- **Location:** mdg.py line 928, lines 1094-1128
- **Commit:** 62b7785

**Bug 8: Smoothr Orders Not Detected** ⚠️ **CRITICAL**
- **Issue:** Real Smoothr orders not parsed/logged at all - appeared in MDG but completely ignored
- **Symptom:** Order visible in chat but no processing, no logs showing detection
- **Root Cause 1:** Smoothr sends messages as `channel_post` updates, not regular `message` updates
- **Root Cause 2:** Detection checked 7 fields - brittle and prone to breaking if Smoothr changes format
- **Fix 1:** Added support for all message types:
  - `message` - Regular messages
  - `channel_post` - Channel posts (Smoothr orders come this way)
  - `edited_message` - Edited regular messages  
  - `edited_channel_post` - Edited channel posts
- **Fix 2:** Simplified detection to only check `"- Order:"` field (unique identifier, future-proof)
- **Location:** 
  - main.py telegram_webhook() lines ~1160-1190 (message type handling)
  - utils.py is_smoothr_order() lines ~873-891 (detection logic)
- **Testing:** Use `/test_smoothr` command to verify detection still works
- **Commit:** Pending

---

**More info:** SYSTEM-REFERENCE.md

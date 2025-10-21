# ⚡ CHEAT SHEET

---

## 📡 CHANNELS

```
MDG  = Main Dispatch Group (all coordinators + couriers)
RG   = Restaurant Groups (vendor-specific chats)
UPC  = User Private Chat (individual couriers)
```

---

## 🔖 ORDER REFERENCE

```
order_id  = Shopify ID (e.g., 7404590039306)
#{num}    = Display number (last 2 digits, e.g., #62)
🔖 #{num} = Order reference with bookmark emoji
```

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
*(Auto-delete after 20 seconds)*

### From RG (Vendor responses)
```
ST-WORKS      = {Vendor} replied: {time} for 🔖 #{num} works 👍
ST-PREP       = {Vendor} replied: Will prepare 🔖 #{num} at {time} 👍
ST-LATER      = {Vendor} replied: Will prepare 🔖 #{num} later at {time} 👍
ST-DELAY      = {Vendor}: We have a delay for 🔖 #{num} - new time {time}
ST-CANCEL     = {Vendor}: Order 🔖 #{num} is canceled
ST-WRITE      = {Vendor}: Issue with 🔖 #{num}: "{vendor's message}"
```

> 📝 Note: ST-CALL removed - BTN-UNAVAIL now sends message directly to RG group instead of MDG

### From MDG (Dispatcher actions)
```
ST-DELIVERED  = 🔖 #{num} was delivered by {courier} at {HH:MM}
ST-UNASSIGNED = 🔖 #{num} was unassigned by {courier}.
ST-ASAP-SENT  = 📨 ASAP request for 🔖 #{num} sent to {Shortcut}
ST-TIME-SENT  = 📨 TIME request ({time}) for 🔖 #{num} sent to {Shortcut}
```

### From UPC (Courier confirmations)
```
ST-UPC-DELAY  = 📨 DELAY request ({time}) for 🔖 #{num} sent to {Shortcut}
ST-UPC-ERR    = ⚠️ {Custom error description from get_error_description()}
```

> 📝 Note: No delivery completion message sent to courier (ST-UPC-DONE removed)

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
FN-ABBREV-STREET = Abbreviate street names for buttons (BTN-ORD-REF only)
                   └─ Tier 1: Straße→Str., compound→Dr.Step.Bill.Str.
                   └─ Tier 2 (>64 chars total): First 4 letters only (Lede 15)
FN-CHECK-CONF   = Check if all vendors confirmed (checks confirmed_times dict)
FN-SEND-ASSIGN  = Send assignment to courier (UPC-ASSIGN)
FN-UPDATE-MDG   = Update MDG message with assignment/delivery status
FN-CLEANUP      = Delete temp msgs (time pickers, selection menus)
FN-DELAY-REQ    = Send delay request to vendors
FN-DELIVERED    = Mark order as delivered, update STATE
FN-GET-RECENT   = Get recent orders for scheduled orders menu (vendor filter optional)
                  └─ Returns last 10 confirmed orders within 5 hours
                  └─ Includes confirmed_times dict for multi-vendor support
```

**Note:** FN-GET-RECENT added for scheduled orders feature with vendor filtering and confirmed_times dict support.

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
assigned_to         = courier user_id
assigned_by         = Who assigned (username or "self-assigned")
delivered_at        = Timestamp of delivery
delivered_by        = courier user_id who delivered
mdg_message_id      = Main MDG message ID
vendor_messages     = {vendor: message_id} dict for RG messages
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

**Note:** `confirmed_times` dict added for multi-vendor per-vendor time tracking. Each vendor's specific confirmed time stored separately. `confirmed_time` kept for backward compatibility (always reflects last vendor's time).

---

## 🔄 FLOW

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

### MDG Actions
```
req_asap            = Request ASAP (single vendor orders)
req_exact           = Show hour picker directly (🕒 Time picker button)
req_scheduled       = Show scheduled orders list (🗂 Scheduled orders button)
req_vendor          = Show vendor-specific action menu (multi-vendor)
                      └─ Displays: ⚡ Asap, 🕒 Time picker, 🗂 Scheduled orders, ← Back

vendor_asap         = ASAP request for specific vendor (multi-vendor)
vendor_time         = TIME request for specific vendor (shows scheduled orders or hour picker)

time_plus           = Send time with +X minutes from reference order (deprecated - use time_relative)
time_same           = Send "together with" request (if vendors match)
time_relative       = Send time with offset (-5m to +25m) from reference order

exact_hour          = Hour selected in exact time picker
exact_selected      = Final time selected from exact picker
exact_back_hours    = Go back to hour selection
exact_hide          = Hide exact time picker

order_ref           = Scheduled order button clicked (shows offset options + optional SAME)

assign_myself       = User assigns order to themselves
assign_other        = Assign to specific courier
assign_to           = Show courier selection menu

hide                = Generic back button (deletes temporary message)
```

### RG Actions (Vendor responses)
```
toggle              = Toggle Details ▸ / ◂ Hide
works               = Vendor confirms time works
later               = Show "later at" time picker
prepare             = Show "will prepare at" time picker
later_time          = Vendor selects later time
prepare_time        = Vendor selects prepare time

wrong_delay         = Vendor reports delay
wrong_unavailable   = Product not available
wrong_canceled      = Order canceled
wrong_other         = Other issue (text input)
delay_time          = Vendor selects delay time

vendor_exact_time   = Show vendor exact time (hour picker)
vendor_exact_hour   = Vendor selects hour
vendor_exact_selected = Vendor confirms exact time
vendor_exact_back   = Back to hour picker
```

### UPC Actions (Courier)
```
delay_order         = Show delay time picker
delay_selected      = Courier selects delay time
unassign_order      = Unassign order from courier (only before delivery)
call_vendor         = Call specific vendor (single vendor direct, or after menu selection)
call_vendor_menu    = Show vendor selection menu for calling
confirm_delivered   = Mark order as delivered
navigate            = Open Google Maps
```

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

---

**More info:** SYSTEM-REFERENCE.md

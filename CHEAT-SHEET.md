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
        🏪 {Vendor Shortcuts} 🍕 {Product Counts}
        🧑 {Customer Name}
        🗺️ [{Address} ({zip})](maps link)
        
        ❕ Note: {Customer Note} (if exists)
        ❕ Tip: {Amount}€ (if tip)
        ❕ Cash: {Total}€ (if COD)
        
        [{phone}](tel:{phone}) (if phone exists)
        
        [Details ▸] button
        [Request ASAP] [Request TIME] (or vendor buttons if multi-vendor)
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
[Request ASAP] [Request TIME]
```

**MDG-CONF** - All vendors confirmed
```
Format: 👍 #{num} - dishbee 🍕 {count}+{count}
        
        👩‍🍳 Vendor: {time}
        🧑‍🍳 Vendor: {time}

Chef emojis rotate: 👩‍🍳👩🏻‍🍳👩🏼‍🍳👩🏾‍🍳🧑‍🍳🧑🏻‍🍳🧑🏼‍🍳🧑🏾‍🍳👨‍🍳👨🏻‍🍳👨🏼‍🍳👨🏾‍🍳
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
BTN-ASAP        = Request ASAP
BTN-TIME        = Request TIME (shows recent orders or exact picker)
                  └─ Has "← Back" button
BTN-VENDOR      = Request {Vendor} (multi-vendor orders)
                  └─ Opens vendor-specific ASAP/TIME menu with "← Back"
```

**After BTN-TIME clicked:**
```
BTN-ORD-REF     = Recent order (e.g., "20:46 - Lederergasse 15 (LR, #59)")
                  └─ Shows: BTN-SAME / BTN-PLUS options
```

**Time Selection:**
```
BTN-SAME        = Same (send "together with" to matching vendor)
BTN-PLUS        = +5 / +10 / +15 / +20 (from reference time)
BTN-EXACT       = Exact time picker (hour → minute)
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
                  └─ Has ← Back button (returns to +5/+10/+15/+20 picker)

BTN-HOUR        = Hour selection (e.g., "14:XX")
                  └─ Opens minute picker for selected hour
                  └─ Minutes: 00, 03, 06, 09... (3-minute intervals)
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
FN-CHECK-CONF   = Check if all vendors confirmed
FN-SEND-ASSIGN  = Send assignment to courier (UPC-ASSIGN)
FN-UPDATE-MDG   = Update MDG message with assignment/delivery status
FN-CLEANUP      = Delete temp msgs (time pickers, selection menus)
FN-DELAY-REQ    = Send delay request to vendors
FN-DELIVERED    = Mark order as delivered, update STATE
```

---

## 💾 STATE

```
order_id            = Shopify order ID (key)
name                = Order number (e.g., "dishbee #62")
vendors             = List of restaurant names
confirmed_times     = {vendor: time} dict
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

---

## 🔄 FLOW

```
Shopify Order
    ↓
MDG-ORD + RG-SUM (simultaneously)
    ↓
BTN-ASAP / BTN-TIME (or BTN-VENDOR if multi-vendor)
    ↓
RG-TIME-REQ (time request to restaurant)
    ↓
BTN-WORKS / BTN-LATER / BTN-PREP
    ↓
ST-WORKS / ST-LATER / ST-PREP (auto-delete 20s)
    ↓
FN-CHECK-CONF
    ↓
MDG-CONF (all vendors confirmed)
    ↓
BTN-ASSIGN-ME / BTN-ASSIGN-TO
    ↓
UPC-ASSIGN (DM to courier with order details)
    ↓
MDG-ASSIGNED (MDG shows assignment)
    ↓
BTN-NAVIGATE / BTN-DELAY-ORD / BTN-DELIVERED
    ↓
BTN-DELIVERED clicked
    ↓
FN-DELIVERED (update STATE, send confirmations)
    ↓
MDG-DELIVERED + UPC-DELIVERED
```

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
req_asap            = Request ASAP from vendors
req_time            = Show time request menu
req_same            = Show recent orders for "same time"
req_exact           = Show exact time picker (hour selection)
time_plus           = Send time with +X minutes
time_same           = Send "same time as" request
time_relative       = Send time from +X button
exact_hour          = Hour selected in exact time picker
exact_selected      = Final time selected from exact picker
exact_back_hours    = Go back to hour selection
exact_hide          = Hide exact time picker

vendor_asap         = Request ASAP from specific vendor (multi-vendor)
vendor_time         = Show time menu for specific vendor
vendor_same         = Show same time for specific vendor
vendor_exact        = Show exact time for specific vendor
smart_time          = Use smart time suggestion (+X from recent order)

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

**More info:** SYSTEM-REFERENCE.md

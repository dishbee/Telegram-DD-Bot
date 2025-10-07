# ⚡ CHEAT SHEET

## CHANNELS
```
MDG  = Main Dispatch (coordination)
RG   = Restaurants (vendors)  
UPC  = Private Chat (couriers)
```

## ORDER
```
ORD       = General order reference
  ├─ order_id = Shopify ID (e.g., 7404590039306)
  ├─ #{num}   = Display number (last 2 digits, e.g., #62)
  └─ 🔖 #{num} = Order reference with bookmark emoji
```

## MESSAGES
```
MDG-ORD         = Order arrives (main message)
  └─ MDG-UPDATE = Status updates (edits MDG-ORD)
  
RG-SUM          = Order arrives (vendor summary)
RG-DET          = Order details (expanded view)

MDG-REQ-VENDOR  = 📍 Request time from {vendor}: (multi-vendor)
MDG-CONF        = All confirmed (with vendor details)
  └─ Format: 🔖 #{num} - dishbee (JS+LR)
              ✅ Restaurants confirmed:
              🏠 Vendor: {time} 📦 {count}

RG-TIME-REQ     = Time request to vendor
  ├─ "Can you prepare 🔖 #{num} at {time}?" (from +X or EXACT)
  ├─ "Can you prepare 🔖 #{num} ASAP?" (from BTN-ASAP)
  └─ "Can you prepare {order} together with {ref_order} at {time}?" (from BTN-SAME)

RG-TIME-PICK    = Select later time: / Will prepare at... (time picker menu)
RG-HOUR-PICK    = 🕒 Select hour: (exact time - hour selection)
RG-MIN-PICK     = 🕒 Select exact time (hour {X}): (minute selection)

UPC-ASSIGN      = Assignment message to courier
  └─ Format: 🔖 #{num} - dishbee
              🏠 {Vendor}: {time} 📦 {count}
              👤 {Customer Name}
              🔺 {Address} ({zip})
              ❕ Tip: {amount}€ (if applicable)
              ❕ Cash on delivery: {amount}€ (if COD)
              ☎️ Call customer: {phone}
              🍽 Call Restaurant:

UPC-DELAY-PICK  = Delay request - select new time: (delay time picker)
UPC-DELIVERED   = ✅ **Delivery completed!** Thank you...

MDG-ASSIGNED    = MDG update showing assignment
  └─ Adds: "👤 **Assigned to:** {courier name}"

MDG-DELIVERED   = MDG final update
  └─ Adds: "👤 **Assigned to:** {courier}
           ✅ **Delivered**"
```

## BUTTONS

### MDG Buttons (Main Dispatch Group)
```
BTN-ASAP        = Request ASAP
BTN-TIME        = Request TIME
  └─ Shows recent confirmed orders (not delivered, <1hr) or BTN-EXACT only

BTN-VENDOR      = Vendor selection button (multi-vendor orders)
  └─ Format: "Request {Vendor Shortcut}" (e.g., "Request LR")
     
--- After clicking BTN-TIME ---
BTN-ORD-REF     = Recent order button (e.g., "20:46 - Lederergasse 15 (LR, #59)")
  └─ Shows: BTN-SAME / BTN-PLUS options
     
--- After selecting order reference ---
BTN-SAME        = Same (send "together with" to matching vendor only)
BTN-PLUS        = +5 / +10 / +15 / +20 (calculated from reference time)
BTN-EXACT       = Exact time picker (always at bottom)

--- After all vendors confirm ---
BTN-ASSIGN-ME   = 👈 Assign to myself
BTN-ASSIGN-TO   = 👉 Assign to... (courier selection)

--- Courier selection submenu ---
BTN-COURIER     = Individual courier buttons (e.g., "Bee 1", "Bee 2")
```

### RG Buttons (Restaurant responses)
```
BTN-TOGGLE      = Details ▸ / ◂ Hide (on RG-SUM/RG-DET)

--- On RG-TIME-REQ (TIME request) ---
BTN-WORKS       = Works 👍
BTN-LATER       = Later at... (time picker with labels)
  └─ Shows: "09:52 (5 mins)", "09:57 (10 mins)", "10:02 (15 mins)", "10:07 (20 mins)"
  └─ Plus: EXACT TIME ⏰ button at bottom
BTN-WRONG       = Something is wrong

--- On RG-TIME-REQ (ASAP request) ---
BTN-PREP        = Will prepare at... (time picker with labels)
  └─ Shows: "09:52 (5 mins)", "09:57 (10 mins)", "10:02 (15 mins)", "10:07 (20 mins)"
  └─ Plus: EXACT TIME ⏰ button at bottom
BTN-WRONG       = Something is wrong

--- On BTN-EXACT (Vendor exact time flow) ---
BTN-HOUR        = Hour selection (12:XX, 13:XX, 14:XX...)
  └─ BTN-MINUTE = Minute selection (00, 03, 06... in 3-min intervals)
     └─ BTN-BACK = ◂ Back to hours

--- On BTN-WRONG submenu ---
BTN-UNAVAIL     = Product not available
BTN-CANCEL      = Order is canceled
BTN-TECH        = Technical issue
BTN-OTHER       = Something else (text input)
BTN-DELAY       = We have a delay (time picker)
```

### UPC Buttons (Courier actions)
```
BTN-NAVIGATE    = 🧭 Navigate (Google Maps with cycling mode)
BTN-DELAY-ORD   = ⏰ Delay (shows delay time picker)
BTN-DELIVERED   = ✅ Delivered (completes order)

--- On delay time picker ---
BTN-DELAY-SEL   = Time selection buttons (+5/+10/+15/+20 from confirmed time)
```

## STATUS UPDATES (Auto-delete after 20 seconds)

### From RG (Vendor responses)
```
ST-WORKS      = {Vendor} replied: {time} for 🔖 #{num} works 👍
ST-PREP       = {Vendor} replied: Will prepare 🔖 #{num} at {time} 👍
ST-LATER      = {Vendor} replied: Will prepare 🔖 #{num} later at {time} 👍
ST-DELAY      = {Vendor}: We have a delay for 🔖 #{num} - new time {time}
ST-CANCEL     = {Vendor}: Order 🔖 #{num} is canceled
ST-CALL       = {Vendor}: Please call customer for 🔖 #{num} (replacement/refund)
ST-WRITE      = {Vendor}: Issue with 🔖 #{num}: "{vendor's message}"
```

### From MDG (User actions)
```
ST-DELIVERED  = Order #{num} was delivered.
ST-ASAP-SENT  = ✅ ASAP request sent to {vendor}
ST-TIME-SENT  = ✅ Time request ({time}) sent to {vendor}
```

### UPC Status (to courier)
```
ST-UPC-DONE   = ✅ **Delivery completed!** Thank you...
ST-UPC-DELAY  = ✅ Delay request sent to restaurant(s) for {time}
ST-UPC-ERR    = ⚠️ Error sending delay request
```

## TEMPORARY MESSAGES (Cleaned up after action)
```
TMP-REQ-VENDOR  = 📍 Request time from {vendor}:
TMP-TIME-PICK   = Time picker menus (BTN-PLUS buttons)
TMP-SAME-SEL    = Recent order selection menu
TMP-EXACT-HOUR  = Hour selection (10:XX-23:XX)
TMP-EXACT-MIN   = Minute selection (00-57 in 3-min intervals)
TMP-COURIER-SEL = Courier selection menu
TMP-DELAY-PICK  = Delay time picker (UPC)
```

## RG MESSAGES (Restaurant notifications)
```
RG-TIME-REQ     = Time request from MDG
  ├─ "Can you prepare 🔖 #{num} at {time}?"
  ├─ "Can you prepare 🔖 #{num} ASAP?"
  └─ "Can you prepare {order} together with {ref} at {time}?"

RG-TIME-PICK    = Select later time: / Will prepare at... (time picker)
RG-DELAY-REQ    = Delay request from courier
  └─ "We have a delay, if possible prepare #{num} at {time}..."
```

## FUNCTIONS
```
FN-CLEAN-NAME   = Clean product names (removes prefixes, extracts quoted text)
FN-CHECK-CONF   = Check if all vendors confirmed
FN-SEND-ASSIGN  = Send assignment to courier (UPC-ASSIGN)
FN-UPDATE-MDG   = Update MDG message with assignment/delivery status
FN-CLEANUP      = Delete temp msgs (time pickers, selection menus)
FN-DELAY-REQ    = Send delay request to vendors
FN-DELIVERED    = Mark order as delivered, update STATE
```

## STATE
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

## FLOW
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

## RESTAURANTS
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

## CALLBACK ACTIONS
```
--- MDG Actions ---
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

--- RG Actions (Vendor responses) ---
toggle              = Toggle Details ▸ / ◂ Hide
works               = Vendor confirms time works
later               = Show "later at" time picker
prepare             = Show "will prepare at" time picker
later_time          = Vendor selects later time
prepare_time        = Vendor selects prepare time

wrong_delay         = Vendor reports delay
wrong_unavailable   = Product not available
wrong_canceled      = Order canceled
wrong_technical     = Technical issue
wrong_other         = Other issue (text input)
delay_time          = Vendor selects delay time

vendor_exact_time   = Show vendor exact time (hour picker)
vendor_exact_hour   = Vendor selects hour
vendor_exact_selected = Vendor confirms exact time
vendor_exact_back   = Back to hour picker

--- UPC Actions (Courier) ---
delay_order         = Show delay time picker
confirm_delivered   = Mark order as delivered
```

---

**EXAMPLES**

❌ Bad: "The button doesn't work"  
✅ Good: "BTN-WORKS not updating confirmed_times"

❌ Bad: "Show more info"  
✅ Good: "Add count to RG-SUM like MDG-CONF"

---

**More info:** SYSTEM-REFERENCE.md

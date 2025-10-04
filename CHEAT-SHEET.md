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
MDG-CONF        = All confirmed  
RG-TIME-REQ     = Time request to vendor
  ├─ "Can you prepare 🔖 #{num} at {time}?" (from +X buttons)
  └─ "Can you also prepare 🔖 #{num} at {time} together with 🔖 #{ref_num}?" (from Same button)
UPC-ASSIGN      = Courier gets order
MDG-STATUS      = Status alerts (■ Vendor: ... ■)
```

## BUTTONS

### MDG Buttons
```
BTN-TIME        = Request TIME
  └─ Shows recent confirmed orders (not delivered, <1hr) or BTN-EXACT only
     
--- After clicking BTN-TIME ---
BTN-ORD-REF     = Recent order button (e.g., "20:46 - Lederergasse 15 (LR, #59)")
  └─ Shows: BTN-SAME / BTN-PLUS options
     
--- After selecting order reference ---
BTN-SAME        = Same (send "together with" to matching vendor only)
BTN-PLUS        = +5 / +10 / +15 / +20 (calculated from reference time)
BTN-EXACT       = Exact time picker (always at bottom)

BTN-ASAP        = Request ASAP
BTN-ASSIGN-ME   = Assign to myself
BTN-ASSIGN-TO   = Assign to... (courier selection)
```

### RG Buttons (Restaurant responses)
```
BTN-TOGGLE      = Details ▸ / ◂ Hide (on RG-SUM/RG-DET)

--- On RG-TIME-REQ (TIME request) ---
BTN-WORKS       = Works 👍
BTN-LATER       = Later at... (time picker)
BTN-WRONG       = Something is wrong

--- On RG-TIME-REQ (ASAP request) ---
BTN-PREP        = Will prepare at... (time picker)
BTN-WRONG       = Something is wrong

--- On BTN-WRONG submenu ---
BTN-UNAVAIL     = Product not available
BTN-CANCEL      = Order is canceled
BTN-TECH        = Technical issue
BTN-OTHER       = Something else (text input)
BTN-DELAY       = We have a delay (time picker)
```

### UPC Buttons (Courier actions)
```
BTN-NAVIGATE    = 🧭 Navigate
BTN-DELAY-ORD   = ⏰ Delay
BTN-DELIVERED   = ✅ Delivered
```

## STATUS UPDATES (Auto-delete after 10 seconds)

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
TMP-REQ-TIME  = 📍 Request time from {vendor}:
```

## RG MESSAGES (Restaurant notifications)
```
RG-DELAY-REQ = We have a delay, if possible prepare #{num} at {time}...
```

## FUNCTIONS
```
FN-CHECK-CONF   = Check vendors
FN-SEND-ASSIGN  = Send to courier
FN-CLEANUP      = Delete temp msgs
```

## STATE
```
confirmed_times = {vendor: time}
status          = new/assigned/delivered
assigned_to     = courier_id
```

## FLOW
```
Shopify Order
    ↓
MDG-ORD + RG-SUM (simultaneously)
    ↓
BTN-TIME / BTN-ASAP
    ↓
RG-TIME-REQ
    ↓
BTN-WORKS
    ↓
MDG-CONF
    ↓
BTN-ASSIGN-ME
    ↓
UPC-ASSIGN
    ↓
BTN-DELIVERED
```

## RESTAURANTS
```
JS = Julis Spätzlerei
LR = Leckerolls
ZH = Zweite Heimat
DD = dean & david
PF = Pommes Freunde
```

---

**EXAMPLES**

❌ Bad: "The button doesn't work"  
✅ Good: "BTN-WORKS not updating confirmed_times"

❌ Bad: "Show more info"  
✅ Good: "Add count to RG-SUM like MDG-CONF"

---

**More info:** SYSTEM-REFERENCE.md

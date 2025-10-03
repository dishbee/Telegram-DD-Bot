# ⚡ CHEAT SHEET

## CHANNELS
```
MDG  = Main Dispatch (coordination)
RG   = Restaurants (vendors)  
UPC  = Private Chat (couriers)
```

## MESSAGES
```
MDG-ORD      = Order arrives (main message)
RG-SUM       = Order arrives (vendor summary)
RG-DET       = Order details (expanded view)
MDG-CONF     = All confirmed  
RG-TIME-REQ  = Time request to vendor
UPC-ASSIGN   = Courier gets order
```

## BUTTONS
```
BTN-TIME        = Request TIME
BTN-ASAP        = Request ASAP
  └─ FN-MDG-KB  = Keyboard with both buttons
BTN-TOGGLE      = Details ▸ / ◂ Hide (RG)
BTN-WORKS       = Works 👍
BTN-ASSIGN-ME   = Assign to myself
BTN-DELIVERED   = ✅ Delivered
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

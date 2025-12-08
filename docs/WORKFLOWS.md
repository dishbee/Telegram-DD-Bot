# WORKFLOWS - Visual Guide

**Element Shortcuts**: WF-ORDER-ARRIVAL, WF-TIME-REQ, WF-VENDOR-CONF, WF-ASSIGNMENT, WF-DELIVERY, etc. (Full list at bottom)

**Restaurant Shortcuts**: JS=Julis Spätzlerei, ZH=Zweite Heimat, HB=Hello Burrito, KA=Kahaani, SA=i Sapori della Toscana, LR=Leckerolls, DD=dean & david, PF=Pommes Freunde, AP=Wittelsbacher Apotheke, SF=Safi, KI=Kimbu

**Courier Shortcuts**: B1=Bee 1, B2=Bee 2, B3=Bee 3

**New Features (December 2025)**:
- **Order ID Logging**: All logs include `[ORDER-XX]` prefix for easy filtering (grep "ORDER-26")
- **STATE Documentation**: See `STATE_SCHEMA.md` for all 60+ STATE fields with types, formats, examples
- **Code Constants**: Magic numbers extracted to named constants (TELEGRAM_BUTTON_TEXT_LIMIT, RECENT_ORDERS_MAX_SIZE, etc.)

---

## 1️⃣ WF-ORDER-ARRIVAL: New Order Arrival

**Shopify webhook arrives** → Bot creates order in STATE

**MDG-ORD** (collapsed view):
```
🚨 New order (# 28)
────────────────

🗺️ [address link]

👩‍🍳 JS (2) + LR (3)

📞 phone

👤 customer name

Total: 29.50€
```

**Initial Buttons**:
```
BTN-DETAILS     [Details ▸]
BTN-VENDOR      [Ask 👩‍🍳 JS]  ← multi-vendor
BTN-VENDOR      [Ask 👨‍🍳 LR]
```

OR (single vendor):
```
BTN-DETAILS     [Details ▸]
BTN-ASAP        [⚡ Asap]
BTN-TIME        [🕒 Time picker]
BTN-SCHEDULED   [🗂 Scheduled orders]  ← conditional
```

**RG-SUM** (collapsed, each vendor gets own message):
```
🚨 New order (# 28)

────────────────

🗺️ Hauptstraße 15

2 x Burger Classic
1 x Fries

❕ Note: No onions
```

**Initial Button**:
```
BTN-DETAILS     [Details ▸]
```

---

## 2️⃣ WF-TIME-REQ-MULTI: Time Request - Multi-Vendor

**User clicks** BTN-VENDOR `Ask 👩‍🍳 JS` in MDG-ORD → Bot shows submenu

**MDG-VENDOR-MENU** for JS:
```
BTN-ASAP        [⚡ Asap]
BTN-TIME        [🕒 Time picker]
BTN-SCHEDULED   [🗂 Scheduled orders]  ← conditional
BTN-BACK        [← Back]
```

### ASAP Path

**User clicks** BTN-ASAP `⚡ Asap` → Bot sends **RG-TIME-REQ** to JS group:

```
🔖 28: Asap?
```

**Buttons**:
```
BTN-YESAT       [⏰ Yes at:]
BTN-PROBLEM     [🚩 Problem]
```

**JS clicks** BTN-YESAT `⏰ Yes at:` → **RG-TIME-PICKER** appears:

```
BTN-TIME-OPT    [⏰ 18:10 → in 5 m]
BTN-TIME-OPT    [⏰ 18:15 → in 10 m]
BTN-TIME-OPT    [⏰ 18:20 → in 15 m]
BTN-TIME-OPT    [⏰ 18:25 → in 20 m]
BTN-EXACT       [Time picker🕒]
BTN-BACK        [← Back]
```

**JS selects** BTN-TIME-OPT `⏰ 18:15 → in 10 m` → Confirmation

**MDG-ORD updates**:
```
🕒 18:15? (# 28)
────────────────

🗺️ [address]

👩‍🍳 JS (2) + 🆕 LR (3)  ← JS confirmed, LR pending

📞 phone

👤 customer

Total: 29.50€
```

**RG-SUM** (JS) updates:
```
🕒 18:15? (# 28)

────────────────

🗺️ Hauptstraße 15

2 x Burger Classic

BTN-HIDE        [◂ Hide]
```

Note: **"🆕"** appears next to vendors NOT yet confirmed

---

### TIME PICKER Path

**User clicks** BTN-TIME `🕒 Time picker` → Bot shows **MDG-SCHED-MENU** (recent orders from last 5 hours):

```
BTN-ORD-REF     [28 - JS - 18:15 - Graben. 15]
BTN-ORD-REF     [27 - LR - 18:20 - Haupt. 42]
BTN-ORD-REF     [26 - DD - 18:30 - Bahn. 8]
BTN-BACK        [← Back]
```

**User clicks** BTN-ORD-REF `28 - JS - 18:15 - Graben. 15` → **MDG-TIME-OFFSET**:

```
BTN-SAME        [🔁 Same time]  ← conditional
BTN-OFFSET      [-5m → ⏰ 18:10]
BTN-OFFSET      [-3m → ⏰ 18:12]
BTN-OFFSET      [+3m → ⏰ 18:18]
BTN-OFFSET      [+5m → ⏰ 18:20]
BTN-OFFSET      [+10m → ⏰ 18:25]
BTN-OFFSET      [+15m → ⏰ 18:30]
BTN-OFFSET      [+20m → ⏰ 18:35]
BTN-OFFSET      [+25m → ⏰ 18:40]
BTN-BACK        [← Back]
```

**User clicks** BTN-OFFSET `+5m → ⏰ 18:20` → Bot sends **RG-TIME-REQ** to JS group:

```
🔖 28: 18:20?
```

**Buttons**:
```
BTN-WORKS       [Works 👍]
BTN-LATER       [⏰ Later at]
BTN-PROBLEM     [🚩 Problem]
```

**JS clicks** BTN-WORKS `Works 👍` → Confirmation (same MDG-ORD/RG-SUM updates as ASAP path)

---

### EXACT TIME Path

If **NO recent orders**, clicking BTN-TIME `🕒 Time picker` shows **MDG-TIME-HOUR**:

```
BTN-HOUR        [18] [19] [20] [21]
BTN-HOUR        [22] [23]
BTN-BACK        [← Back]
```

**User clicks** BTN-HOUR `19` → **MDG-TIME-MIN** (3-minute intervals):

```
BTN-MINUTE      [19:00] [19:03] [19:06] [19:09]
BTN-MINUTE      [19:12] [19:15] [19:18] [19:21]
BTN-MINUTE      [19:24] [19:27] [19:30] [19:33]
...
BTN-BACK        [← Back to hours]
```

**User clicks** BTN-MINUTE `19:15` → Same RG-TIME-REQ flow as TIME PICKER path

---

## 3️⃣ WF-TIME-REQ-SINGLE: Time Request - Single Vendor

**User clicks** BTN-ASAP `⚡ Asap` in MDG-ORD → Bot sends RG-TIME-REQ to vendor directly (no submenu)

**Flow identical to multi-vendor ASAP**, except:
- No MDG-VENDOR-MENU
- MDG-ORD shows vendor name without "🆕" marker

---

## 4️⃣ WF-VENDOR-CONF: Vendor Confirmation

**After ALL vendors confirm** → MDG-ORD shows assignment buttons

**MDG-CONF** (NEW message below MDG-ORD):
```
📌 Order to assign
────────────────

🗺️ [Ludwigstraße 15 (94032)](https://google.com/maps?q=...)

🕒 18:15 ➞ 👩‍🍳 JS (2)
🕒 18:20 ➞ 🧑‍🍳 LR (3)

🔖 28
```

**Buttons**:
```
BTN-ASSIGN-ME   [👈 Assign to myself]
BTN-ASSIGN-TO   [Assign to 👉]
BTN-COMBINE     [📌 Assigned orders]  ← conditional
```

---

## 5️⃣ WF-ASSIGNMENT: Assignment

### Assign to Myself

**User clicks** BTN-ASSIGN-ME `👈 Assign to myself` → Bot assigns to user

### Assign to Another Courier

**User clicks** BTN-ASSIGN-TO `Assign to 👉` → **MDG-COURIER-MENU**:

```
BTN-COURIER     [Bee 1]  ← priority first
BTN-COURIER     [Bee 2]
BTN-COURIER     [Bee 3]
BTN-COURIER     [Other Courier Name]  ← alphabetically
BTN-BACK        [← Back]
```

**User clicks** BTN-COURIER `Bee 1` → Assignment sent

---

### After Assignment

**MDG-ORD updates**:
```
👇 Assigned to B1 (# 28)
────────────────

🗺️ [address]

👩‍🍳 JS (2) + 👨‍🍳 LR (3)

📞 phone

👤 customer

Total: 29.50€
```

**MDG-CONF updates**:
```
📌 Assigned: 🐝 Bee 1
────────────────

🗺️ [Ludwigstraße 15 (94032)](https://google.com/maps?q=...)

🕒 18:15 ➞ 👩‍🍳 JS (2)
🕒 18:20 ➞ 🧑‍🍳 LR (3)

🔖 28

[🚫 Unassign]
```

**RG messages update**:
```
👇 Assigned to B1 (# 28)

────────────────

🗺️ Hauptstraße 15

2 x Burger Classic

[◂ Hide]
[🚩 Problem]  ← appears after confirmation
```

**UPC (Courier's Private Chat)**:
```
👇 Assigned order #28
────────────────

🕒 18:15 ➞ 👩‍🍳 JS (2)
🕒 18:20 ➞ 👨‍🍳 LR (3)

🗺️ [Hauptstraße 15 (80333)]

👤 Max Mustermann

☎️ +49 123 456789

BTN-NAVIGATE    [🧭 Navigate]
BTN-PROBLEM     [🚩 Problem]
BTN-DELIVERED   [✅ Delivered]
```

---

## 6️⃣ WF-PROBLEM-MENU: Courier Problem Menu

**Courier clicks** BTN-PROBLEM `🚩 Problem` → **UPC-PROBLEM-MENU**:

```
BTN-DELAY       [⏳ Delay]
BTN-UNASSIGN    [🚫 Unassign]
BTN-CALL        [👩‍🍳 Call JS]
BTN-CALL        [👨‍🍳 Call LR]
BTN-BACK        [← Back]
```

### Delay Workflow

**Multi-vendor**: Click BTN-DELAY `⏳ Delay` → **UPC-DELAY-VENDOR**:

```
BTN-REQ-VENDOR  [Request JS]
BTN-REQ-VENDOR  [Request LR]
BTN-BACK        [← Back]
```

**Click** BTN-REQ-VENDOR `Request JS` → **UPC-DELAY-TIME**:

```
⏳ Request new (18:15) for 🔖 28 from JS

BTN-DELAY-TIME  [+5m → ⏰ 18:20]
BTN-DELAY-TIME  [+10m → ⏰ 18:25]
BTN-DELAY-TIME  [+15m → ⏰ 18:30]
BTN-DELAY-TIME  [+20m → ⏰ 18:35]
BTN-BACK        [← Back]
```

**Click** BTN-DELAY-TIME `+5m → ⏰ 18:20` → Bot sends **RG-DELAY-REQ** to JS group:

```
We have a delay, if possible prepare 28 at 18:20. If not, please keep it warm.
```

**Buttons**:
```
BTN-WORKS       [Works 👍]
BTN-LATER       [⏰ Later at]
BTN-PROBLEM     [🚩 Problem]
```

**Courier receives ST-UPC-DELAY confirmation**:
```
✅ Delay request for 🔖 28 sent to JS
```
(Auto-deletes after 20 seconds)

**Single-vendor**: Skip UPC-DELAY-VENDOR, show UPC-DELAY-TIME directly

---

## 7️⃣ WF-DELIVERY: Delivery

**Courier clicks** BTN-DELIVERED `✅ Delivered` in UPC-ASSIGN → Confirmation

**MDG receives ST-DELIVER notification**:
```
Order 🔖 28: ✅ Delivered by 🐝 B1 at 18:45
```

**MDG-ORD updates**:
```
✅ Delivered (# 28)
────────────────

🗺️ [address]

👩‍🍳 JS (2) + 👨‍🍳 LR (3)

📞 phone

👤 customer

Total: 29.50€
```

**MDG-CONF deleted** (temporary message removed)

**RG-SUM** updates:
```
✅ Delivered (# 28)

────────────────

🗺️ Hauptstraße 15

2 x Burger Classic

[◂ Hide]
[🚩 Problem]
```

**UPC-DELIVERED** replaces UPC-ASSIGN:
```
✅ Delivered: 18:45
────────────────

🕒 18:15 ➠ 👩‍🍳 JS (2)
🕒 18:20 ➠ 👨‍🍳 LR (3)

🗺️ [Hauptstraße 15 (80333)]

👤 Max Mustermann

☎️ +49 123 456789

BTN-UNDELIVER   [❌ Undeliver]  ← keyboard replaced
```

---

## 8️⃣ WF-UNDELIVERY: Undelivery

**Courier clicks** BTN-UNDELIVER `❌ Undeliver` in UPC-DELIVERED → Revert

**MDG receives ST-UNDELIVER notification**:
```
🔖 28 was undelivered by B1 at 18:47
```

**All messages revert** to assigned state (MDG-ORD, RG-SUM, UPC-ASSIGN restored with full keyboards)

---

## 9️⃣ WF-DETAILS-TOGGLE: Details Toggle

### MDG Details

**Click** BTN-DETAILS `Details ▸` in MDG-ORD → **MDG-ORD-EXP**:

```
🚨 New order (# 28)
────────────────

🗺️ [address]

👩‍🍳 JS (2) + LR (3)

📞 phone

👤 customer

Total: 29.50€

🔗 dishbee

🏙️ Innenstadt (80333)

✉️ max@example.com

**JS**:
2 x Burger Classic

**LR**:
1 x Cinnamon Roll
2 x Coffee
```

**Button changes to** BTN-HIDE `◂ Hide` (click to collapse)

### RG Details

**Click** BTN-DETAILS `Details ▸` in RG-SUM → **RG-DET**:

```
🚨 New order (# 28)

────────────────

🗺️ Hauptstraße 15

2 x Burger Classic

❕ Note: No onions

👤 Max Mustermann
📞 +49 123 456789
⏰ Ordered at: 17:45
```

**Button changes to** BTN-HIDE `◂ Hide` (click to collapse)

---

## 🔟 WF-COMBINE: Order Combining (Groups)

**After assignment**, click BTN-COMBINE `📌 Assigned orders` in MDG-CONF → **MDG-COMBINE-MENU**:

```
BTN-ASSIGNED    [Haupt - 18:15 - JS  |  B1]
BTN-ASSIGNED    [Graben - 18:20 - LR  |  B2]
BTN-ASSIGNED    [Bahn - 18:30 - DD  |  B1]
BTN-BACK        [← Back]
```

**Click** BTN-ASSIGNED `Haupt - 18:15 - JS  |  B1` → Order 28 combined with selected order

**Group Color**: 🟣🔵🟢🟡🟠🔴🟤 (assigned per group)

**UPC-ASSIGN updates** with UPC-GROUP indicator:

```
👇 Assigned order #28
────────────────

🔵 Group: 1/2

🕒 18:15 ➞ 👩‍🍳 JS (2)

🗺️ [Hauptstraße 15 (80333)]

👤 Max Mustermann

☎️ +49 123 456789
```

**When 1 order delivered** → Group position updates (e.g., "2/2" becomes "1/1")

**When last order delivered** → Group dissolved

---

## 📋 STATUS PROGRESSION

**Order Status Flow**:
```
🚨 New order
    ↓
⚡ Asap? / 🕒 18:15?  ← time sent
    ↓
🔔 Prepare at 18:15  ← vendor confirmed
    ↓
👇 Assigned to B1  ← courier assigned
    ↓
✅ Delivered  ← delivery confirmed
```

**MDG Header Changes**:
- New: `🚨 New order (# 28)`
- ASAP sent: `Can you prepare address (# 28) ⚡ Asap?`
- Time sent: `🕒 18:15? (# 28)`
- Confirmed: `🔔 Prepare at 18:15 (# 28)`
- Assigned: `👇 Assigned to B1 (# 28)`
- Delivered: `✅ Delivered (# 28)`

**RG Header Changes**: Same status progression

**UPC Header Changes**:
- Assigned: `👇 Assigned order #28`
- Delivered: `✅ Delivered: 18:45`

---

## 🎨 VISUAL MARKERS

**Multi-Vendor Status**:
- `👩‍🍳 JS (2) + 🆕 LR (3)` ← "🆕" = not yet confirmed
- `👩‍🍳 JS (2) + 👨‍🍳 LR (3)` ← both confirmed (no "🆕")

**Chef Emojis** (rotating per vendor):
👩‍🍳 👩🏻‍🍳 👩🏼‍🍳 👩🏾‍🍳 🧑‍🍳 🧑🏻‍🍳 🧑🏼‍🍳 🧑🏾‍🍳 👨‍🍳 👨🏻‍🍳 👨🏼‍🍳 👨🏾‍🍳

**Group Colors** (rotating per group):
🟣🔵🟢🟡🟠🔴🟤

**Courier Shortcuts**:
- B1 = Bee 1
- B2 = Bee 2
- B3 = Bee 3
- 🐝 = Used in delivery notifications

**Vendor Shortcuts**:
JS, ZH, HB, KA, SA, LR, DD, PF, AP, SF

**Button Shortcuts**:
- ⚡ = ASAP
- 🕒 = Time picker
- 🗂 = Scheduled orders
- 🧭 = Navigate (Google Maps)
- 🚩 = Problem
- ⏳ = Delay
- ✅ = Delivered
- ❌ = Undeliver
- 🚫 = Unassign
- 👈/👉 = Assignment direction
- 📌 = Assigned orders
- 🔁 = Same time
- ◂/▸ = Hide/Show details

---

## 🔄 AUTOMATIC BEHAVIORS

**Message Cleanup**: Time pickers, vendor menus, courier selection menus auto-delete after user completes action

**Temporary Messages**: MDG-CONF created after all vendors confirm, deleted after delivery

**Auto-Delete Confirmations**: Delay confirmation deletes after 20 seconds

**Button State**: Details buttons toggle between "Details ▸" and "◂ Hide"

**Problem Button**: Only appears in RG after vendor confirms AND before delivery

**Scheduled Orders Button**: Only appears if recent orders exist (last 5 hours, confirmed times only)

**Assigned Orders Button**: Only appears in MDG-CONF if assigned orders exist in system

---

## 📋 COMPLETE SHORTCUTS REFERENCE

### Workflows
```
WF-ORDER-ARRIVAL       New order arrives (Shopify webhook → MDG-ORD + RG-SUM)
WF-TIME-REQ-MULTI      Time request for multi-vendor orders
WF-TIME-REQ-SINGLE     Time request for single-vendor orders  
WF-VENDOR-CONF         All vendors confirmed → MDG-CONF appears
WF-ASSIGNMENT          Courier assignment flow
WF-PROBLEM-MENU        Courier problem menu (delay/unassign/call)
WF-DELIVERY            Delivery completion flow
WF-UNDELIVERY          Revert delivered order back to assigned
WF-DETAILS-TOGGLE      Toggle collapsed/expanded views
WF-COMBINE             Combine orders into groups
```

### Messages - MDG (Main Dispatch Group)
```
MDG-ORD                Order dispatch message (collapsed)
MDG-ORD-EXP            Order dispatch message (expanded)
MDG-CONF               Vendor confirmation message
MDG-VENDOR-MENU        Vendor selection submenu (multi-vendor)
MDG-SCHED-MENU         Scheduled orders menu
MDG-TIME-OFFSET        Time offset selection (+5m, -3m, etc.)
MDG-TIME-HOUR          Hour picker (18, 19, 20...)
MDG-TIME-MIN           Minute picker (3-min intervals)
MDG-COURIER-MENU       Courier selection menu
MDG-COMBINE-MENU       Assigned orders for combining
```

### Messages - RG (Restaurant Groups)
```
RG-SUM                 Order summary (collapsed)
RG-DET                 Order details (expanded)
RG-TIME-REQ            Time request sent to restaurant
RG-TIME-PICKER         Vendor time picker (+5m, +10m, etc.)
RG-DELAY-REQ           Delay request from courier
```

### Messages - UPC (User Private Chat - Courier)
```
UPC-ASSIGN             Assignment message
UPC-DELIVERED          Delivered state message
UPC-GROUP              Group indicator in assignment
UPC-PROBLEM-MENU       Problem submenu
UPC-DELAY-VENDOR       Vendor selection for delay
UPC-DELAY-TIME         Delay time picker
```

### Status Notifications
```
ST-DELIVER             "Order 🔖 {num}: ✅ Delivered by 🐝 {courier} at {time}"
ST-UNDELIVER           "🔖 {num} was undelivered by {courier} at {time}"
ST-UPC-DELAY           "✅ Delay request for 🔖 {num} sent to {shortcut}"
```

### Buttons - MDG
```
BTN-DETAILS            Details ▸ / ◂ Hide
BTN-ASAP               ⚡ Asap
BTN-TIME               🕒 Time picker
BTN-SCHEDULED          🗂 Scheduled orders
BTN-VENDOR             Ask {chef} {Shortcut}
BTN-ASSIGN-ME          👈 Assign to myself
BTN-ASSIGN-TO          👉 Assign to...
BTN-COURIER            {Courier Name}
BTN-UNASSIGN           🚫 Unassign
BTN-COMBINE            📌 Assigned orders
BTN-SAME               🔁 Same time
BTN-OFFSET             -5m / -3m / +3m / +5m / +10m / +15m / +20m / +25m
BTN-HOUR               18, 19, 20... 23
BTN-MINUTE             19:00, 19:03, 19:06... (3-min intervals)
BTN-ORD-REF            {num} - {short} - {time} - {addr}
BTN-ASSIGNED           {addr} - {time} - {short}  |  {courier}
BTN-BACK               ← Back
```

### Buttons - RG
```
BTN-YESAT              ⏰ Yes at:
BTN-WORKS              Works 👍
BTN-LATER              ⏰ Later at
BTN-PROBLEM            🚩 Problem
BTN-TIME-OPT           ⏰ {time} → in {min} m
BTN-EXACT              Time picker🕒
BTN-HIDE               ◂ Hide
```

### Buttons - UPC
```
BTN-NAVIGATE           🧭 Navigate
BTN-DELIVERED          ✅ Delivered
BTN-UNDELIVER          ❌ Undeliver
BTN-DELAY              ⏳ Delay
BTN-CALL               {chef} Call {Shortcut}
BTN-REQ-VENDOR         Request {Shortcut}
BTN-DELAY-TIME         +5m → ⏰ {time}
```

### Restaurant Shortcuts
```
JS  = Julis Spätzlerei
ZH  = Zweite Heimat
HB  = Hello Burrito
KA  = Kahaani
SA  = i Sapori della Toscana
LR  = Leckerolls
DD  = dean & david
PF  = Pommes Freunde
AP  = Wittelsbacher Apotheke
SF  = Safi
KI  = Kimbu
```

### Courier Shortcuts
```
B1  = Bee 1
B2  = Bee 2
B3  = Bee 3
🐝  = Generic courier (in notifications)
```

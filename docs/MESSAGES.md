# MESSAGES - Visual Format Reference

**All formats shown EXACTLY as they appear in Telegram**

**Element Shortcuts**: MDG-ORD, RG-SUM, UPC-ASSIGN, BTN-WORKS, etc. (Full list at bottom)

**Restaurant Shortcuts**: JS=Julis Spätzlerei, ZH=Zweite Heimat, HB=Hello Burrito, KA=Kahaani, SA=i Sapori della Toscana, LR=Leckerolls, DD=dean & david, PF=Pommes Freunde, AP=Wittelsbacher Apotheke, SF=Safi, KI=Kimbu

**Courier Shortcuts**: B1=Bee 1, B2=Bee 2, B3=Bee 3

**New Features (December 2025)**:
- **Order ID Logging**: All logs include `[ORDER-XX]` prefix for easy filtering (grep "ORDER-26")
- **STATE Documentation**: See `STATE_SCHEMA.md` for all 60+ STATE fields with types, formats, examples
- **Code Constants**: Magic numbers extracted to named constants (TELEGRAM_BUTTON_TEXT_LIMIT, RECENT_ORDERS_MAX_SIZE, etc.)

---

## 📍 MDG MESSAGES (Main Dispatch Group)

### MDG-ORD: Order Dispatch Message (Collapsed)

```
🚨 New order (# 28)
────────────────

🗺️ [Hauptstraße 15 (80333)]

👩‍🍳 JS (2) + LR (3)

📞 +49 123 456789

👤 Max Mustermann

Total: 29.50€
```

**Buttons**:
```
[Details ▸]
[Ask 👩‍🍳 JS]
[Ask 👨‍🍳 LR]
```

OR (single vendor):
```
[Details ▸]
[⚡ Asap]
[🕒 Time picker]
[🗂 Scheduled orders]
```

**With Optional Fields**:
```
🚨 New order (# 28)
────────────────

🗺️ [Hauptstraße 15 (80333)]

👩‍🍳 JS (2)

📞 +49 123 456789

👤 Max Mustermann

Total: 29.50€

❕ Note: No onions please
❕ Tip: 3.50€
❕ Cash: 29.50€
```

---

### MDG-ORD: Expanded View

```
🚨 New order (# 28)
────────────────

🗺️ [Hauptstraße 15 (80333)]

👩‍🍳 JS (2) + LR (3)

📞 +49 123 456789

👤 Max Mustermann

Total: 29.50€

🔗 dishbee

🏙️ Innenstadt (80333)

✉️ max@example.com

**JS**:
2 x Burger Classic
1 x Fries

**LR**:
1 x Cinnamon Roll
2 x Coffee
```

**Button**:
```
[◂ Hide]
[Ask 👩‍🍳 JS]
[Ask 👨‍🍳 LR]
```

---

### MDG-ORD: Status Variations

**ASAP Sent**:
```
⚡ Asap? (# 28)
────────────────

🗺️ [address]
...
```

**Time Sent**:
```
🕒 18:15? (# 28)
────────────────

🗺️ [address]
...
```

**Confirmed (Multi-Vendor - One Pending)**:
```
🔔 Prepare at 18:15 (# 28)
────────────────

🗺️ [address]

👩‍🍳 JS (2) + 🆕 LR (3)

...
```

**Confirmed (All)**:
```
🔔 Prepare at 18:15 (# 28)
────────────────

🗺️ [address]

👩‍🍳 JS (2) + 👨‍🍳 LR (3)

...
```

**Assigned**:
```
👇 Assigned to B1 (# 28)
────────────────

🗺️ [address]
...
```

**Delivered**:
```
✅ Delivered (# 28)
────────────────

🗺️ [address]
...
```

---

### MDG-CONF: Confirmation Message

**After All Vendors Confirm**:
```
📌 Order to assign
────────────────

🗺️ [Ludwigstraße 15 (94032)](https://google.com/maps?q=...)

🕒 12:50 ➞ 👩‍🍳 JS (2)
🕒 12:55 ➞ 🧑‍🍳 LR (3)

🔖 28
```

**Buttons (Before Assignment)**:
```
[👈 Assign to myself]
[Assign to 👉]
[📌 Assigned orders]
```

**Buttons (After Assignment)**:
```
[🚫 Unassign]
```

---

### MDG-TIME-REQ: Time Request Message

**To Single Vendor (ASAP)**:
```
Can you prepare 🗺️ Ludwigstraße 15 (# 28) ⚡ Asap?
```

**To Single Vendor (Specific Time)**:
```
🔖 28: 18:15?
```

**Sent to Restaurant Group, NOT MDG** (these are RG-TIME-REQ messages shown later)

---

### MDG Notification Messages

**Delivery Notification**:
```
Order 🔖 28: ✅ Delivered by 🐝 B1 at 18:45
```

**Undelivery Notification**:
```
🔖 28 was undelivered by B1 at 18:47
```

---

### MDG Submenus (Temporary Messages)

**Vendor Time Menu**:
```
[⚡ Asap]
[🕒 Time picker]
[🗂 Scheduled orders]
[← Back]
```

**Scheduled Orders List** (Recent orders from last 5 hours):
```
[28 - JS - 18:15 - Graben. 15]
[27 - LR - 18:20 - Haupt. 42]
[26 - DD - 18:30 - Bahn. 8]
[← Back]
```

**Relative Time Menu** (After selecting reference order):
```
[🔁 Same time]  ← only if vendor matches
[-5m → ⏰ 18:10]
[-3m → ⏰ 18:12]
[+3m → ⏰ 18:18]
[+5m → ⏰ 18:20]
[+10m → ⏰ 18:25]
[+15m → ⏰ 18:30]
[+20m → ⏰ 18:35]
[+25m → ⏰ 18:40]
[← Back]
```

**Hour Picker** (If no recent orders):
```
[18] [19] [20] [21]
[22] [23]
[← Back]
```

**Minute Picker** (3-minute intervals):
```
[19:00] [19:03] [19:06] [19:09]
[19:12] [19:15] [19:18] [19:21]
[19:24] [19:27] [19:30] [19:33]
[19:36] [19:39] [19:42] [19:45]
[19:48] [19:51] [19:54] [19:57]
[← Back to hours]
```

**Courier Selection Menu**:
```
[Bee 1]
[Bee 2]
[Bee 3]
[Other Courier Name]
[← Back]
```

**Assigned Orders List** (For combining):
```
[Haupt - 18:15 - JS  |  B1]
[Graben - 18:20 - LR  |  B2]
[Bahn - 18:30 - DD  |  B1]
[← Back]
```

---

## 🍕 RG MESSAGES (Restaurant Groups)

### RG-SUM: Summary View (Collapsed)

**Shopify Order**:
```
🚨 New order (# 28)

────────────────

🗺️ Hauptstraße 15

2 x Burger Classic
1 x Fries

❕ Note: No onions
```

**Button**:
```
[Details ▸]
```

**Smoothr Order (DD/PF)**:
```
🚨 New order (# 28)

────────────────

🗺️ Bahnhofstraße 42, 80333

👤 Max Mustermann

2 x Burger Classic
1 x Fries

❕ Note: No onions
```

---

### RG-DET: Details View (Expanded)

**Shopify Order**:
```
🚨 New order (# 28)

────────────────

🗺️ Hauptstraße 15

2 x Burger Classic
1 x Fries

❕ Note: No onions

👤 Max Mustermann
📞 +49 123 456789
⏰ Ordered at: 17:45
```

**Buttons**:
```
[◂ Hide]
[🚩 Problem]  ← only after confirmation
```

**Smoothr Order**:
```
🚨 New order (# 28)

────────────────

🗺️ Bahnhofstraße 42, 80333

👤 Max Mustermann

2 x Burger Classic
1 x Fries

❕ Note: No onions

📞 +49 123 456789
⏰ Ordered at: 17:45
```

---

### RG Status Variations

**Same Status Progression as MDG**:
- `🚨 New order (# 28)` → New
- `Can you prepare 🗺️ address (# 28) ⚡ Asap?` → ASAP sent
- `🕒 18:15? (# 28)` → Time sent
- `🔔 Prepare at 18:15 (# 28)` → Confirmed
- `👇 Assigned to B1 (# 28)` → Assigned
- `✅ Delivered (# 28)` → Delivered

---

### RG-TIME-REQ: Time Request Messages

**ASAP Request** (sent from MDG to RG):
```
🔖 28: Asap?
```

**Buttons**:
```
[⏰ Yes at:]
[🚩 Problem]
```

**Specific Time Request**:
```
🔖 28: 18:15?
```

**Buttons**:
```
[Works 👍]
[⏰ Later at]
[🚩 Problem]
```

---

### RG-TIME-PICK: Vendor Time Picker

**After vendor clicks** `⏰ Yes at:` or `⏰ Later at`:

```
[⏰ 18:10 → in 5 m]
[⏰ 18:15 → in 10 m]
[⏰ 18:20 → in 15 m]
[⏰ 18:25 → in 20 m]
[Time picker🕒]
[← Back]
```

---

### RG-DELAY-REQ: Delay Request Message

**Sent from UPC when courier requests delay**:
```
We have a delay, if possible prepare 28 at 18:20. If not, please keep it warm.
```

**Buttons**:
```
[Works 👍]
[⏰ Later at]
[🚩 Problem]
```

---

## 📱 UPC MESSAGES (User Private Chat - Courier)

### UPC-ASSIGN: Assignment Message

**Standard Assignment**:
```
👇 Assigned order #28
────────────────

🕒 18:15 ➞ 👩‍🍳 JS (2)
🕒 18:20 ➞ 👨‍🍳 LR (3)

🗺️ [Hauptstraße 15 (80333)]

👤 Max Mustermann

☎️ +49 123 456789
```

**Buttons**:
```
[🧭 Navigate]
[🚩 Problem]
[✅ Delivered]
```

**With Optional Fields** (Note/Tip/Cash shown only if NOT delivered):
```
👇 Assigned order #28
────────────────

🕒 18:15 ➞ 👩‍🍳 JS (2)

🗺️ [Hauptstraße 15 (80333)]

👤 Max Mustermann

☎️ +49 123 456789

❕ Note: No onions please
❕ Tip: 3.50€
❕ Cash: 29.50€
```

**With Group Indicator**:
```
👇 Assigned order #28
────────────────

🔵 Group: 1/2

🕒 18:15 ➞ 👩‍🍳 JS (2)

🗺️ [Hauptstraße 15 (80333)]

👤 Max Mustermann

☎️ +49 123 456789
```

---

### UPC-DELIVERED: Delivered State

```
✅ Delivered: 18:45
────────────────

🕒 18:15 ➞ 👩‍🍳 JS (2)
🕒 18:20 ➞ 👨‍🍳 LR (3)

🗺️ [Hauptstraße 15 (80333)]

👤 Max Mustermann

☎️ +49 123 456789
```

**Button**:
```
[❌ Undeliver]
```

Note: Optional fields (note/tip/cash) NOT shown after delivery

---

### UPC Submenus

**Problem Menu**:
```
[⏳ Delay]
[🚫 Unassign]
[👩‍🍳 Call JS]
[👨‍🍳 Call LR]
[← Back]
```

**Delay Vendor Selection** (Multi-vendor only):
```
[Request JS]
[Request LR]
[← Back]
```

**Delay Time Picker**:
```
⏳ Request new (18:15) for 🔖 28 from JS

[+5m → ⏰ 18:20]
[+10m → ⏰ 18:25]
[+15m → ⏰ 18:30]
[+20m → ⏰ 18:35]
[← Back]
```

**Delay Confirmation** (Auto-deletes after 20 seconds):
```
✅ Delay request for 🔖 28 sent to JS
```

---

## 📊 FORMATTING RULES

### Address Formats

**MDG (Collapsed)**: `🗺️ [Hauptstraße 15 (80333)]` ← clickable link
**MDG (Expanded)**: Same + district line: `🏙️ Innenstadt (80333)`
**RG (Shopify)**: `🗺️ Hauptstraße 15` ← street only, no zip
**RG (Smoothr)**: `🗺️ Bahnhofstraße 42, 80333` ← full address
**UPC**: `🗺️ [Hauptstraße 15 (80333)]` ← clickable link

### Vendor Display

**Multi-Vendor (Before All Confirm)**:
- `👩‍🍳 JS (2) + 🆕 LR (3)` ← "🆕" = not confirmed

**Multi-Vendor (After All Confirm)**:
- `👩‍🍳 JS (2) + 👨‍🍳 LR (3)` ← no "🆕"

**Single Vendor**:
- `👩‍🍳 JS (2)`

**Chef Emojis Rotate**: 👩‍🍳 👩🏻‍🍳 👩🏼‍🍳 👩🏾‍🍳 🧑‍🍳 🧑🏻‍🍳 🧑🏼‍🍳 🧑🏾‍🍳 👨‍🍳 👨🏻‍🍳 👨🏼‍🍳 👨🏾‍🍳

### Product Count

**Format**: `(count)` where count = total quantity of all items for that vendor
- Example: `2 x Burger + 1 x Fries` = `(3)`

### Status Lines

**MDG/RG Headers**: Always include order number
- `🚨 New order (# 28)`
- `Can you prepare address (# 28) ⚡ Asap?`
- `🕒 18:15? (# 28)`
- `🔔 Prepare at 18:15 (# 28)`
- `👇 Assigned to B1 (# 28)`
- `✅ Delivered (# 28)`

**UPC Headers**: Different format
- `👇 Assigned order #28`
- `✅ Delivered: 18:45`

### Separator Line

**Always**: `────────────────` (16 characters)
**Always followed by**: One blank line

### Optional Fields Order

**MDG/UPC**: Note → Tip → Cash
**RG**: Note only (tip/cash not shown)

### Blank Lines

**MDG-ORD (Collapsed)**:
```
{status}
────────────────
↓ blank line
🗺️ address
↓ blank line
👩‍🍳 vendor
↓ blank line
📞 phone
↓ blank line
👤 customer
↓ blank line
Total: amount
↓ blank line (only if optional fields)
❕ Note/Tip/Cash
```

**RG-SUM**:
```
{status}
↓ blank line
────────────────
↓ blank line
🗺️ address
↓ blank line (Smoothr only: 👤 customer here)
products
↓ blank line
❕ Note
```

**UPC-ASSIGN**:
```
{status}
────────────────
↓ blank line
(optional: group indicator + blank line)
🕒 restaurant lines
↓ blank line
🗺️ address
↓ blank line
👤 customer
↓ blank line
☎️ phone
↓ blank line (only if optional fields)
❕ Note/Tip/Cash
```

---

## 🎨 EMOJI LEGEND

**Status Icons**:
- 🚨 = New order
- ⚡ = ASAP request
- 🕒 = Time request
- 🔔 = Confirmed (prepare at)
- 👇 = Assigned
- ✅ = Delivered
- ❌ = Undeliver
- 🚩 = Problem
- ⏳ = Delay
- 🚫 = Unassign

**Content Icons**:
- 🗺️ = Address
- 👤 = Customer name
- 📞/☎️ = Phone
- 🔖 = Order number reference
- 📦 = Product count
- ❕ = Note/tip/cash
- ✉️ = Email
- 🔗 = Source
- 🏙️ = District

**Navigation Icons**:
- 🧭 = Navigate (Google Maps)
- ← = Back button
- ▸ = Show details
- ◂ = Hide details

**Vendor Icons**:
- 👩‍🍳 👨‍🍳 🧑‍🍳 = Chef emojis (rotating)
- 🆕 = Not yet confirmed

**Assignment Icons**:
- 👈 = Assign to myself
- 👉 = Assign to another
- 📌 = Assigned orders
- 🐝 = Courier (in notifications)

**Group Colors**:
- 🟣🔵🟢🟡🟠🔴🟤 = Group indicators

**Button Icons**:
- 🔁 = Same time
- ➞ = Direction arrow (pickup times)

---

## 🔢 SHORTCUTS REFERENCE

**Restaurants**:
- JS = Julis Spätzlerei
- ZH = Zweite Heimat
- HB = Hello Burrito
- KA = Kahaani
- SA = i Sapori della Toscana
- LR = Leckerolls
- DD = dean & david
- PF = Pommes Freunde
- AP = Wittelsbacher Apotheke
- SF = Safi
- KI = Kimbu

**Couriers**:
- B1 = Bee 1
- B2 = Bee 2
- B3 = Bee 3

**Used in**: MDG-CONF vendor names, button labels, combining menu, delay confirmations, courier assignments

---

## 📋 COMPLETE SHORTCUTS REFERENCE

### Message Types - MDG
```
MDG-ORD                Order dispatch message (collapsed)
MDG-ORD-EXP            Order dispatch message (expanded)
MDG-CONF               Vendor confirmation message
MDG-TIME-REQ           Time request to restaurant (Can you prepare... ⚡ Asap? / 🕒 18:15?)
MDG-VENDOR-MENU        Vendor selection submenu
MDG-SCHED-MENU         Scheduled orders list
MDG-TIME-OFFSET        Time offset menu (Same/+5m/-3m)
MDG-TIME-HOUR          Hour picker grid
MDG-TIME-MIN           Minute picker grid (3-min intervals)
MDG-COURIER-MENU       Courier selection list
MDG-COMBINE-MENU       Assigned orders for combining
```

### Message Types - RG
```
RG-SUM                 Order summary (collapsed)
RG-DET                 Order details (expanded)
RG-TIME-REQ            Time request (Can you prepare... ⚡ Asap? / 🕒 18:15?)
RG-TIME-PICKER         Vendor time options (+5m, +10m, etc.)
RG-DELAY-REQ           Delay request message
```

### Message Types - UPC
```
UPC-ASSIGN             Courier assignment message
UPC-DELIVERED          Delivered state message
UPC-GROUP              Group indicator (🔵 Group: 1/2)
UPC-PROBLEM-MENU       Problem options menu
UPC-DELAY-VENDOR       Vendor selection for delay
UPC-DELAY-TIME         Delay time picker
```

### Status Notifications
```
ST-DELIVER             "Order 🔖 28: ✅ Delivered by 🐝 B1 at 18:45"
ST-UNDELIVER           "🔖 28 was undelivered by B1 at 18:47"
ST-UPC-DELAY           "✅ Delay request for 🔖 28 sent to JS"
```

### Button Types - MDG
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
BTN-HOUR               18, 19, 20, 21, 22, 23
BTN-MINUTE             19:00, 19:03, 19:06... (3-min)
BTN-ORD-REF            {num} - {short} - {time} - {addr}
BTN-ASSIGNED           {addr} - {time} - {short}  |  {courier}
BTN-BACK               ← Back
```

### Button Types - RG
```
BTN-YESAT              ⏰ Yes at:
BTN-WORKS              Works 👍
BTN-LATER              ⏰ Later at
BTN-PROBLEM            🚩 Problem
BTN-TIME-OPT           ⏰ 18:10 → in 5 m
BTN-EXACT              Time picker🕒
BTN-HIDE               ◂ Hide
```

### Button Types - UPC
```
BTN-NAVIGATE           🧭 Navigate
BTN-DELIVERED          ✅ Delivered
BTN-UNDELIVER          ❌ Undeliver
BTN-DELAY              ⏳ Delay
BTN-CALL               {chef} Call {Shortcut}
BTN-REQ-VENDOR         Request {Shortcut}
BTN-DELAY-TIME         +5m → ⏰ 18:20
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
🐝  = Generic courier (used in notifications)
```

### Status Icons
```
🚨  = New order
⚡  = ASAP request
🕒  = Time request
🔔  = Confirmed (prepare at)
👇  = Assigned
✅  = Delivered
❌  = Undeliver
🚩  = Problem
⏳  = Delay
🚫  = Unassign
🔖  = Order number reference
📦  = Product count
🆕  = Not yet confirmed (multi-vendor)
```

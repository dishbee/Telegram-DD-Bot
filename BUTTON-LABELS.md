# 🔘 BUTTON LABELS QUICK REFERENCE

## 📍 MDG Buttons (Main Dispatch Group)

```
[Request ASAP]              → Sends ASAP request to all vendors
[Request TIME]              → Shows time selection menu (recent orders or exact picker)
[Request {Vendor}]          → Shows ASAP/TIME menu for specific vendor (multi-vendor)
[Details ▸]                 → Expands order to show full product list
[◂ Hide]                    → Collapses order back to summary view

--- Time Selection Menu ---
[20:46 - Address (LR, #59)] → Recent order button → shows SAME/PLUS options
[Same]                      → Send "together with" to matching vendor
[+5] [+10] [+15] [+20]      → Add X minutes to reference time
[EXACT TIME ⏰]             → Opens hour/minute picker
[← Back]                    → Closes menu

--- After All Vendors Confirm ---
[👈 Assign to myself]       → Assign order to yourself
[👉 Assign to...]           → Shows courier selection menu

--- Courier Selection ---
[Bee 1] [Bee 2] [Bee 3]     → Assign to specific courier
[← Back]                    → Closes courier menu
```

---

## 🏪 RG Buttons (Restaurant Group)

```
[Details ▸]                 → Shows full order details
[◂ Hide]                    → Hides details, back to summary

--- On TIME Request ---
[Works 👍]                  → Confirm requested time works
[Later at]                  → Shows time picker with +5/+10/+15/+20 options
[Something is wrong]        → Opens issue submenu

--- On ASAP Request ---
[Will prepare at]           → Shows time picker to select preparation time

--- Time Picker ---
[09:52 (5 mins)]            → Select time (5 mins from now)
[09:57 (10 mins)]           → Select time (10 mins from now)
[10:02 (15 mins)]           → Select time (15 mins from now)
[10:07 (20 mins)]           → Select time (20 mins from now)
[EXACT TIME ⏰]             → Opens hour/minute picker
[← Back]                    → Closes picker

--- Exact Time Picker ---
[12:XX] [13:XX] [14:XX]     → Select hour
[00] [03] [06] [09]...      → Select minute (3-min intervals)
[◂ Back to hours]           → Return to hour selection
[← Back]                    → Closes picker

--- "Something is wrong" Submenu ---
[Product not available]     → Report unavailable product
[Order is canceled]         → Cancel order
[Technical issue]           → Report technical problem
[Something else]            → Type custom message
[We have a delay]           → Opens delay time picker (+10/+15/+20/+30 mins)
[← Back]                    → Closes submenu
```

---

## 💼 UPC Buttons (Courier Private Chat)

```
[🧭 Navigate]               → Opens Google Maps with cycling directions
[⏰ Delay]                  → Opens delay time picker
[✅ Delivered]              → Marks order as delivered, completes workflow
[🍽 Call {Vendor}]          → Shows restaurant selection menu (multi-vendor)

--- Delay Time Picker ---
[14:35 (+5 mins)]           → Delay by 5 minutes
[14:40 (+10 mins)]          → Delay by 10 minutes
[14:45 (+15 mins)]          → Delay by 15 minutes
[14:50 (+20 mins)]          → Delay by 20 minutes
[← Back]                    → Closes delay picker

--- Restaurant Call Menu ---
[🍽 Call {Vendor}]          → Opens phone dialer for specific vendor
[← Back]                    → Closes restaurant menu
```

---

## 🔄 ACTION RESULTS

### ✅ Status Messages (auto-delete after 20 seconds)

**From RG (Vendor responses):**
```
"JS replied: 12:50 for 🔖 #62 works 👍"
"LR replied: Will prepare 🔖 #62 at 13:00 👍"
"DD replied: Will prepare 🔖 #62 later at 13:15 👍"
"KA: We have a delay for 🔖 #62 - new time 14:00"
"SA: Order 🔖 #62 is canceled"
"PF: Please call customer for 🔖 #62 (replacement/refund)"
"AP: Issue with 🔖 #62: [vendor's message]"
```

**From MDG (Dispatcher actions):**
```
"✅ ASAP request sent to JS"
"✅ Time request (12:50) sent to LR"
"Order #62 was delivered."
```

**From UPC (Courier confirmations):**
```
"✅ **Delivery completed!** Thank you..."
"✅ Delay request sent to restaurant(s) for 14:00"
"⚠️ Error sending delay request"
```

### 📝 Message Updates

**MDG message updates:**
```
After vendor confirms → Shows: "👍 #62 - dishbee 🍕 3+1"
                               "👩‍🍳 JS: 12:50"
                               "🧑‍🍳 LR: 13:00"

After assignment     → Adds:   "👤 **Assigned to:** Bee 1"

After delivery       → Adds:   "✅ **Delivered**"
```

**RG time requests:**
```
"Can you prepare 🔖 #62 at 12:50?"
"Can you prepare 🔖 #62 ASAP?"
"Can you prepare 🔖 #62 together with 🔖 #59 at 12:50?"
```

**RG delay requests:**
```
"We have a delay, if possible prepare #62 at 13:00. If not, please keep it warm."
```

**UPC assignment:**
```
"👉 #62 - dishbee
👩‍🍳 JS: 12:50 🍕 2
👤 Max Mustermann
🧭 Hauptstraße 15 (94032)
☎️ 0851123456"
```

---

## 🔍 QUICK LOOKUP

**To request time:** `[Request TIME]` or `[Request {Vendor}]` → `[+10]` or `[EXACT TIME ⏰]`

**To confirm time:** `[Works 👍]` or select time from picker

**To delay order:** `[⏰ Delay]` → `[14:40 (+10 mins)]`

**To assign order:** `[👈 Assign to myself]` or `[👉 Assign to...]` → `[Bee 1]`

**To deliver order:** `[✅ Delivered]`

**To navigate:** `[🧭 Navigate]`

**To report issue:** `[Something is wrong]` → select issue type

**To go back:** `[← Back]` (available on all temporary menus)

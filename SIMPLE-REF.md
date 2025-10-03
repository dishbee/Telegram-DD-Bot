# 🚀 Simple Reference - Telegram Dispatch Bot

**One-page cheat sheet** - Print this!

---

## 📱 Channels

**MDG** = Main Dispatch Group (coordination center)  
**RG** = Restaurant Groups (vendor chats)  
**UPC** = User Private Chats (courier DMs)

---

## 📨 Messages

### MDG
- **MDG-ORD** = Initial order message (when order arrives)
- **MDG-CONF** = "✅ Restaurants confirmed" (after all vendors confirm)
- **MDG-ASSIGN** = Assignment buttons (assign to courier)

### RG
- **RG-SUM** = Order summary (collapsed view - when order arrives)
- **RG-DET** = Order details (expanded view - click "Details ▸")
- **RG-TIME-REQ** = Time request to vendor (from MDG)

### UPC
- **UPC-ASSIGN** = Assignment DM to courier (order details + CTA buttons)

---

## 🔘 Buttons

- **BTN-TIME** = Request TIME (MDG)
- **BTN-ASAP** = Request ASAP (MDG)
- **BTN-TOGGLE** = Details ▸ / ◂ Hide (RG - expand/collapse)
- **BTN-WORKS** = Works 👍 (RG - vendor confirms)
- **BTN-ASSIGN-ME** = 👈 Assign to myself (MDG)
- **BTN-ASSIGN-TO** = 👉 Assign to... (MDG)
- **BTN-DELAY** = ⏰ Delay (UPC - courier requests delay)
- **BTN-DELIVERED** = ✅ Delivered (UPC - mark complete)

---

## 🔧 Functions

- **FN-CHECK-CONF** = Check all vendors confirmed
- **FN-SEND-ASSIGN** = Send assignment to courier
- **FN-CLEANUP** = Delete temporary messages
- **FN-CLEAN-NAME** = Clean product names

---

## 📊 STATE Fields

- `confirmed_times` = Per-vendor times
- `status` = "new" / "assigned" / "delivered"
- `assigned_to` = Courier user_id
- `vendors` = List of restaurants

---

## 🔄 Basic Flow

```
1. Shopify Order → MDG-ORD + RG-SUM (both sent at same time)
2. User clicks BTN-TIME → RG-TIME-REQ (to vendor)
3. Vendor clicks BTN-WORKS → MDG-CONF (confirmation)
4. User clicks BTN-ASSIGN-ME → UPC-ASSIGN (to courier)
5. Courier clicks BTN-DELIVERED → Order complete
```

---

## 🏪 Restaurants

**JS** = Julis Spätzlerei  
**LR** = Leckerolls  
**ZH** = Zweite Heimat  
**DD** = dean & david  
**PF** = Pommes Freunde  
**SA** = i Sapori della Toscana  
**KA** = Kahaani

---

## 💬 Quick Examples

**Bug report:**
> "BTN-WORKS not updating confirmed_times in STATE"

**Feature request:**
> "Add product count to RG-SUM like MDG-CONF"

**Question:**
> "Does FN-CLEANUP delete MDG-ORD?"

---

**Full details:** See SYSTEM-REFERENCE.md

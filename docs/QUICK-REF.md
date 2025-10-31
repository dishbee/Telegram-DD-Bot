# Quick Reference Card - Telegram Dispatch Bot

**Fast lookup for daily use** 🚀

---

## 🎯 Most Common Elements

### Messages You'll Reference Daily

| Code | What It Is | Example Use |
|------|------------|-------------|
| **MDG-ORD** | Initial order message | "Update MDG-ORD to show tips differently" |
| **MDG-CONF** | Vendor confirmation with details | "MDG-CONF should show product count" |
| **UPC-ASSIGN** | Courier assignment DM | "Add restaurant phone to UPC-ASSIGN" |
| **RG-TIME-REQ** | Time request to restaurant | "RG-TIME-REQ not showing correct time" |

### Buttons You'll Mention Most

| Code | Button Text | Use Case |
|------|-------------|----------|
| **BTN-ASSIGN-ME** | 👈 Assign to myself | Assignment issues |
| **BTN-WORKS** | Works 👍 | Vendor confirmation problems |
| **BTN-DELIVERED** | ✅ Delivered | Delivery completion bugs |
| **BTN-TIME-PLUS** | +5/+10/+15/+20 | Time picker adjustments |

### Functions You'll Debug Often

| Code | Function | Common Issues |
|------|----------|---------------|
| **FN-CHECK-CONF** | Check all vendors confirmed | Assignment buttons not appearing |
| **FN-SEND-ASSIGN** | Send assignment to courier | DM not received |
| **FN-CLEANUP** | Delete temporary messages | Chat clutter |
| **FN-CLEAN-NAME** | Clean product names | Display formatting |

### STATE Fields You'll Check

| Field | Purpose | Debug Use |
|-------|---------|-----------|
| `confirmed_times` | Per-vendor times | "Is vendor X confirmed?" |
| `status` | Order lifecycle | "Why duplicate buttons?" |
| `assigned_to` | Courier ID | "Who has this order?" |
| `mdg_message_id` | Original order message | "Which message to edit?" |

---

## 💬 Communication Templates

### Reporting a Bug
```
"BTN-WORKS not updating confirmed_times[vendor] in STATE.
Order #1058, vendor LR, FN-CHECK-CONF returns False."
```

### Requesting a Change
```
"Add product count to RG-SUM (like MDG-CONF shows).
Use same logic from FN-MDG-CONF function."
```

### Asking for Clarification
```
"Should BTN-ASSIGN-TO trigger FN-CLEANUP for MDG-COURIER-SEL
after user selects courier?"
```

---

## 🔄 Quick Workflow Reference

**Normal Order:**
```
MDG-ORD → BTN-TIME → BTN-TIME-PLUS → RG-TIME-REQ → BTN-WORKS 
→ MDG-CONF → BTN-ASSIGN-ME → UPC-ASSIGN → BTN-DELIVERED
```

**With Delay:**
```
UPC-ASSIGN → BTN-DELAY → UPC-DELAY-PICK → BTN-DELAY-SEL 
→ RG-DELAY → BTN-WORKS (status="assigned" blocks duplicate buttons)
```

---

## 🏪 Restaurant Shortcuts

**JS** = Julis Spätzlerei  
**LR** = Leckerolls  
**ZH** = Zweite Heimat  
**DD** = dean & david  
**PF** = Pommes Freunde  
**SA** = i Sapori della Toscana  
**KA** = Kahaani  

---

## 📱 Channel Quick Ref

**MDG** = Main Dispatch Group (coordination)  
**RG** = Restaurant Groups (vendor chats)  
**UPC** = User Private Chats (courier DMs)  

---

**Full details:** See `SYSTEM-REFERENCE.md`

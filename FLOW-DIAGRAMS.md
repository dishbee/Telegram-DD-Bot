# System Flow Diagrams - Telegram Dispatch Bot

Visual representation of all major workflows.

---

## 📊 Order Lifecycle Overview

```
┌─────────────┐
│   Shopify   │
│   Webhook   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  STAGE 1: ORDER ARRIVAL                 │
│  ─────────────────────────────────────  │
│  • Create STATE[order_id]               │
│  • FN-CLEAN-NAME for products           │
│  • Send MDG-ORD (main message)          │
│  • Send RG-SUM to each vendor           │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  STAGE 2: TIME REQUEST                  │
│  ─────────────────────────────────────  │
│  User clicks BTN-TIME in MDG            │
│  ├─→ Single vendor: Direct time picker  │
│  └─→ Multi vendor: BTN-VENDOR selection │
│                                          │
│  Time selected → RG-TIME-REQ to vendors │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  STAGE 3: VENDOR CONFIRMATION           │
│  ─────────────────────────────────────  │
│  Vendor clicks BTN-WORKS                │
│  • Update confirmed_times[vendor]       │
│  • FN-CHECK-CONF                        │
│  • If all confirmed → MDG-CONF          │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  STAGE 4: ASSIGNMENT                    │
│  ─────────────────────────────────────  │
│  • Show BTN-ASSIGN-ME / BTN-ASSIGN-TO   │
│  • User selects courier                 │
│  • FN-SEND-ASSIGN → UPC-ASSIGN          │
│  • Update STATE: status = "assigned"    │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  STAGE 5: DELIVERY                      │
│  ─────────────────────────────────────  │
│  • Courier sees BTN-NAV, BTN-DELAY      │
│  • Courier clicks BTN-DELIVERED         │
│  • Update STATE: status = "delivered"   │
│  • Send confirmation to MDG             │
└─────────────────────────────────────────┘
```

---

## 🔀 Multi-Vendor Flow

```
                    ┌─────────────┐
                    │  MDG-ORD    │
                    │ (2 vendors) │
                    └──────┬──────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ BTN-VENDOR (JS) │
                  │ BTN-VENDOR (LR) │
                  └────┬───────┬────┘
                       │       │
         ┌─────────────┘       └─────────────┐
         ▼                                    ▼
  ┌──────────────┐                    ┌──────────────┐
  │ RG-TIME-REQ  │                    │ RG-TIME-REQ  │
  │   to JS      │                    │   to LR      │
  └──────┬───────┘                    └──────┬───────┘
         │                                    │
         ▼                                    ▼
    ┌────────┐                          ┌────────┐
    │BTN-WORKS│                         │BTN-WORKS│
    └────┬───┘                          └────┬───┘
         │                                    │
         └──────────┬────────────────────────┘
                    │
                    ▼
        ┌─────────────────────────┐
        │ FN-CHECK-CONF           │
        │ confirmed_times = {     │
        │   "JS": "12:50",        │
        │   "LR": "12:55"         │
        │ }                       │
        │ ✓ All confirmed!        │
        └────────┬────────────────┘
                 │
                 ▼
        ┌─────────────────┐
        │   MDG-CONF      │
        │ Shows both times│
        │ + product counts│
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │ Assignment Flow │
        └─────────────────┘
```

---

## 👥 Assignment System Architecture

```
                    ┌──────────────┐
                    │   MDG-CONF   │
                    │ (All vendors │
                    │  confirmed)  │
                    └──────┬───────┘
                           │
                           ▼
               ┌─────────────────────┐
               │ Check order status  │
               └─────────┬───────────┘
                         │
          ┌──────────────┴──────────────┐
          │                             │
          ▼                             ▼
    status="new"                  status="assigned"
          │                             │
          ▼                             ▼
    Show buttons                   Skip (duplicate
          │                        prevention)
          │
          ▼
  ┌───────────────┐
  │ BTN-ASSIGN-ME │
  │ BTN-ASSIGN-TO │
  └───┬───────┬───┘
      │       │
      │       └────────────────┐
      │                        │
      ▼                        ▼
┌───────────┐         ┌────────────────┐
│Self-assign│         │ MDG-COURIER-SEL│
└─────┬─────┘         │ (Live detection)│
      │               └────────┬───────┘
      │                        │
      │                        ▼
      │               ┌────────────────┐
      │               │  FN-GET-COURIERS│
      │               │  (API call)    │
      │               └────────┬───────┘
      │                        │
      │                        ▼
      │               ┌────────────────┐
      │               │ BTN-COURIER x4 │
      │               │ (Bee 1/2/3/M)  │
      │               └────────┬───────┘
      │                        │
      └────────────┬───────────┘
                   │
                   ▼
         ┌─────────────────┐
         │ FN-SEND-ASSIGN  │
         │  • UPC-ASSIGN   │
         │  • status =     │
         │    "assigned"   │
         └─────────────────┘
```

---

## ⏰ Time Selection Flow

```
                    ┌──────────┐
                    │ BTN-TIME │
                    └────┬─────┘
                         │
                         ▼
              ┌──────────────────┐
              │ MDG-TIME-SUBMENU │
              └────┬────┬────┬───┘
                   │    │    │
        ┌──────────┘    │    └──────────┐
        │               │               │
        ▼               ▼               ▼
┌───────────────┐ ┌───────────┐ ┌──────────────┐
│ BTN-TIME-PLUS │ │ BTN-SAME  │ │  BTN-EXACT   │
│ (+5/+10/...)  │ │           │ │              │
└───────┬───────┘ └─────┬─────┘ └──────┬───────┘
        │               │               │
        │               ▼               │
        │      ┌─────────────────┐      │
        │      │  Recent orders  │      │
        │      │  (last 1 hour)  │      │
        │      └────────┬────────┘      │
        │               │               │
        │               ▼               │
        │      ┌─────────────────┐      │
        │      │ BTN-SAME-SEL    │      │
        │      │ (copy time)     │      │
        │      └────────┬────────┘      │
        │               │               │
        │               │               ▼
        │               │      ┌─────────────────┐
        │               │      │  Hour selection │
        │               │      │  (10:00-23:00)  │
        │               │      └────────┬────────┘
        │               │               │
        │               │               ▼
        │               │      ┌─────────────────┐
        │               │      │Minute selection │
        │               │      │ (3-min intervals)│
        │               │      └────────┬────────┘
        │               │               │
        └───────────────┴───────────────┘
                        │
                        ▼
              ┌──────────────────┐
              │  Time confirmed  │
              │  • STATE update  │
              │  • RG-TIME-REQ   │
              │  • FN-CLEANUP    │
              └──────────────────┘
```

---

## 🚴 Courier Action Flow (UPC)

```
                  ┌──────────────┐
                  │  UPC-ASSIGN  │
                  │  (DM arrives)│
                  └──────┬───────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
  ┌──────────┐    ┌──────────┐   ┌──────────────┐
  │ BTN-NAV  │    │BTN-DELAY │   │BTN-DELIVERED │
  │          │    │          │   │              │
  │ (Opens   │    └────┬─────┘   └──────┬───────┘
  │  Maps)   │         │                │
  └──────────┘         │                │
                       ▼                │
            ┌──────────────────┐        │
            │ UPC-DELAY-PICK   │        │
            │ (+5/+10/+15/+20) │        │
            └────────┬─────────┘        │
                     │                  │
                     ▼                  │
            ┌──────────────────┐        │
            │ BTN-DELAY-SEL    │        │
            │ (Select new time)│        │
            └────────┬─────────┘        │
                     │                  │
                     ▼                  │
            ┌──────────────────┐        │
            │ FN-DELAY-REQ     │        │
            │ → RG-DELAY       │        │
            │   (all vendors)  │        │
            └────────┬─────────┘        │
                     │                  │
                     ▼                  │
            ┌──────────────────┐        │
            │ Vendors confirm  │        │
            │ BTN-WORKS        │        │
            │ (no duplicate    │        │
            │  assign buttons) │        │
            └──────────────────┘        │
                                        │
                                        ▼
                              ┌──────────────────┐
                              │ FN-DELIVERED     │
                              │ • status =       │
                              │   "delivered"    │
                              │ • Update MDG     │
                              │ • Confirmation   │
                              └──────────────────┘
```

---

## 🛡️ Duplicate Button Prevention

```
         ┌──────────────────┐
         │ All vendors      │
         │ confirmed time   │
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────┐
         │ FN-CHECK-CONF    │
         │ Returns True     │
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────┐
         │ Check STATUS     │
         └────────┬─────────┘
                  │
     ┌────────────┴────────────┐
     │                         │
     ▼                         ▼
┌─────────┐              ┌──────────┐
│ "new"   │              │"assigned"│
└────┬────┘              └────┬─────┘
     │                        │
     ▼                        ▼
┌──────────────┐         ┌──────────────┐
│ Show buttons │         │ Skip buttons │
│ • MDG-CONF   │         │ (Prevents    │
│ • BTN-ASSIGN │         │  duplicates  │
└──────────────┘         │  after delay)│
                         └──────────────┘

CRITICAL: Status check added October 2025
Prevents duplicate assignment buttons when:
- Courier requests delay
- Vendors confirm new time
- System would otherwise show buttons again
```

---

## 🧹 Message Cleanup Flow

```
  Order workflow progresses
         │
         ├─→ MDG-TIME-PICK sent
         │   └─→ Track in mdg_additional_messages[]
         │
         ├─→ MDG-SAME sent
         │   └─→ Track in mdg_additional_messages[]
         │
         ├─→ MDG-EXACT sent
         │   └─→ Track in mdg_additional_messages[]
         │
         ├─→ MDG-COURIER-SEL sent
         │   └─→ Track in mdg_additional_messages[]
         │
         ▼
  User completes action
  (selects time, assigns courier, etc.)
         │
         ▼
  ┌──────────────────┐
  │  FN-CLEANUP      │
  │  • Iterate       │
  │    messages[]    │
  │  • Delete each   │
  │    (3 retries)   │
  │  • Clear list    │
  └──────────────────┘
         │
         ▼
  ┌──────────────────┐
  │ Result:          │
  │ • Temp messages  │
  │   removed        │
  │ • MDG-ORD stays  │
  │ • Clean chat     │
  └──────────────────┘

PRESERVED: mdg_message_id (original order)
DELETED: All messages in mdg_additional_messages
```

---

## 📦 Product Name Cleaning Pipeline

```
Shopify Webhook
      │
      ▼
┌─────────────────────┐
│ line_items array    │
│ Raw product names   │
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────────────┐
│ FN-CLEAN-NAME (17 rules)         │
│ ─────────────────────────────────│
│ 1. Extract burger quotes         │
│ 2. Bio-Pommes → Pommes           │
│ 3. Chili-Cheese-Fries → styled   │
│ 4. Remove prices (+X€)           │
│ 5. Süßkartoffel styling          │
│ 6. Remove Sauerteig-Pizza prefix │
│ 7. Remove -Spätzle suffix        │
│ 8. Curry & Spätzle → Curry       │
│ 9. Gulasch & Spätzle → Gulasch   │
│ 10. Walnuss Pesto simplify       │
│ 11. Remove Selbstgemachte        │
│ 12. Cinnamon roll simplify       │
│ 13. Special roll simplify        │
│ 14-15. Monats-Bio-Burger extract │
│ 16. Preiselbeere handling        │
│ 17. Bio-Salat → Salat            │
└──────────┬───────────────────────┘
           │
           ▼
┌─────────────────────┐
│ vendor_items dict   │
│ Cleaned names       │
└──────────┬──────────┘
           │
           ├─→ MDG-ORD (clean)
           ├─→ RG-SUM (clean)
           ├─→ RG-DET (clean)
           └─→ UPC-ASSIGN (clean)

SINGLE POINT: All cleaning happens in main.py
RESULT: Consistent display across all channels
```

---

## 🔄 STATE Lifecycle

```
┌─────────────────────────────────────────────┐
│ CREATION (Shopify webhook)                  │
│ ─────────────────────────────────────────── │
│ STATE[order_id] = {                         │
│   "name": "#1058",                          │
│   "status": "new",                          │
│   "vendors": ["LR"],                        │
│   "confirmed_times": {},                    │
│   "mdg_additional_messages": []             │
│ }                                           │
└───────────────────┬─────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│ TIME CONFIRMATION                           │
│ ─────────────────────────────────────────── │
│ confirmed_times["LR"] = "14:30"             │
│ requested_time = "14:30"                    │
│ confirmed_time = "14:30"                    │
└───────────────────┬─────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│ ASSIGNMENT                                  │
│ ─────────────────────────────────────────── │
│ status = "assigned"                         │
│ assigned_to = 383910036                     │
│ assigned_at = datetime.now()                │
└───────────────────┬─────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│ DELIVERY                                    │
│ ─────────────────────────────────────────── │
│ status = "delivered"                        │
│ delivered_at = datetime.now()               │
│ delivered_by = 383910036                    │
└─────────────────────────────────────────────┘

NOTE: State persists only in memory
Render restart = all STATE cleared
```

---

**Use these diagrams to:**
- Understand complex workflows
- Debug flow issues  
- Explain system to others
- Plan new features

---

**Related Files:**
- `SYSTEM-REFERENCE.md` - Complete element list
- `QUICK-REF.md` - Daily use shortcuts

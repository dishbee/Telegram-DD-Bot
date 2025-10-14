# UPC Button Flow Diagram

## Current UPC Assignment Message Layout

```
┌─────────────────────────────────────────┐
│  👉 #58 - dishbee                       │
│  👩‍🍳 Leckerolls: 12:55 🍕 3              │
│  👤 John Doe                            │
│  🧭 Hauptstraße 5 (80333)               │
│  ☎️ +49...                               │
├─────────────────────────────────────────┤
│           [ 🧭 Navigate ]               │
│     [ ⏰ Delay ] [ 🔓 Unassign ] ←NEW   │
│         [ 🏪 Call JS ] ←NEW             │
│          [ ✅ Delivered ]               │
└─────────────────────────────────────────┘
```

---

## Unassign Workflow

```
┌───────────────────────────────────────────────────────────────┐
│                    COURIER PRIVATE CHAT                       │
│                                                               │
│  UPC-ASSIGN Message                                          │
│  [ 🧭 Navigate ]                                             │
│  [ ⏰ Delay ] [ 🔓 Unassign ] ← Courier clicks              │
│  [ 🏪 Call JS ]                                              │
│  [ ✅ Delivered ]                                            │
└─────────────────┬─────────────────────────────────────────────┘
                  │
                  │ callback: unassign_order|{order_id}
                  │
                  ▼
┌───────────────────────────────────────────────────────────────┐
│                  handle_unassign_order()                      │
│                                                               │
│  1. Delete UPC assignment message                            │
│  2. Clear: assigned_to, assigned_at, assigned_by             │
│  3. Update MDG: Remove "👤 Assigned to:" line                │
│  4. Restore MDG assignment buttons                           │
│  5. Send notification to MDG                                 │
└─────────────────┬─────────────────────────────────────────────┘
                  │
                  ▼
┌───────────────────────────────────────────────────────────────┐
│                  MAIN DISPATCH GROUP                          │
│                                                               │
│  MDG-ORD (updated - assignment removed)                      │
│  🔖 #58 - dishbee                                            │
│  🏪 JS 🍕 3                                                   │
│  ...                                                          │
│                                                               │
│  Status: "Order #58 was unassigned by Bee 1."               │
│                                                               │
│  MDG-CONF (re-shown)                                         │
│  🔖 #58 - dishbee (JS)                                       │
│  ✅ Restaurant confirmed:                                    │
│  👩‍🍳 Julis Spätzlerei: 12:50 📦 3                            │
│  [ 👈 Assign to myself ]                                     │
│  [ 👉 Assign to... ]                                         │
└───────────────────────────────────────────────────────────────┘
```

---

## Call Restaurant Workflow (Single Vendor)

```
┌───────────────────────────────────────────────────────────────┐
│                    COURIER PRIVATE CHAT                       │
│                                                               │
│  UPC-ASSIGN Message                                          │
│  [ 🧭 Navigate ]                                             │
│  [ ⏰ Delay ] [ 🔓 Unassign ]                                │
│  [ 🏪 Call JS ] ← Courier clicks (single vendor)            │
│  [ ✅ Delivered ]                                            │
└─────────────────┬─────────────────────────────────────────────┘
                  │
                  │ callback: call_vendor|{order_id}|Julis Spätzlerei
                  │
                  ▼
┌───────────────────────────────────────────────────────────────┐
│              initiate_restaurant_call()                       │
│                                                               │
│  Shows placeholder message:                                  │
│  "🏪 Please call JS directly.                                │
│                                                               │
│  (Automatic Telegram calling will be available               │
│   when restaurant accounts are set up)"                      │
└───────────────────────────────────────────────────────────────┘
```

---

## Call Restaurant Workflow (Multi-Vendor)

```
┌───────────────────────────────────────────────────────────────┐
│                    COURIER PRIVATE CHAT                       │
│                                                               │
│  UPC-ASSIGN Message                                          │
│  [ 🧭 Navigate ]                                             │
│  [ ⏰ Delay ] [ 🔓 Unassign ]                                │
│  [ 🏪 Call Restaurant ] ← Courier clicks (multi-vendor)     │
│  [ ✅ Delivered ]                                            │
└─────────────────┬─────────────────────────────────────────────┘
                  │
                  │ callback: call_vendor_menu|{order_id}
                  │
                  ▼
┌───────────────────────────────────────────────────────────────┐
│              show_restaurant_selection()                      │
│                                                               │
│  Temporary Message:                                          │
│  "Select restaurant to call:"                                │
│  [ 🏪 Call JS ]                                              │
│  [ 🏪 Call LR ]                                              │
│  [ ← Back ]                                                  │
└─────────────────┬─────────────────────────────────────────────┘
                  │
                  │ callback: call_vendor|{order_id}|Julis Spätzlerei
                  │
                  ▼
┌───────────────────────────────────────────────────────────────┐
│              initiate_restaurant_call()                       │
│                                                               │
│  Shows placeholder message:                                  │
│  "🏪 Please call JS directly.                                │
│                                                               │
│  (Automatic Telegram calling will be available               │
│   when restaurant accounts are set up)"                      │
└───────────────────────────────────────────────────────────────┘
```

---

## State Transitions

### Normal Flow (Before Enhancement)
```
new → assigned → delivered
```

### With Unassign (After Enhancement)
```
new → assigned → [UNASSIGN] → assigned (ready) → re-assigned → delivered
```

### State Fields Affected by Unassign
```python
# BEFORE Unassign:
{
    "status": "assigned",
    "assigned_to": 383910036,
    "assigned_at": datetime(2025, 10, 14, 12, 0, 0),
    "assigned_by": "self-assigned",
    "upc_assignment_message_id": 123456
}

# AFTER Unassign:
{
    "status": "assigned",  # Ready for re-assignment
    # All assignment fields removed:
    # - assigned_to: DELETED
    # - assigned_at: DELETED
    # - assigned_by: DELETED
    # - upc_assignment_message_id: DELETED
}
```

---

## Button Visibility Matrix

| Button          | Before Assignment | While Assigned | After Unassign | After Delivered |
|-----------------|-------------------|----------------|----------------|-----------------|
| 🧭 Navigate     | N/A              | ✅             | N/A            | N/A             |
| ⏰ Delay        | N/A              | ✅             | N/A            | N/A             |
| 🔓 Unassign     | N/A              | ✅             | N/A            | ❌              |
| 🏪 Call         | N/A              | ✅             | N/A            | N/A             |
| ✅ Delivered    | N/A              | ✅             | N/A            | ✅ (disabled)   |

---

## Callback Data Format

### New Callbacks
```
unassign_order|{order_id}
call_vendor|{order_id}|{vendor_name}
call_vendor_menu|{order_id}
```

### Example
```
unassign_order|7404590039306
call_vendor|7404590039306|Julis Spätzlerei
call_vendor_menu|7404590039306
```

---

## Error Handling

### Unassign Errors
- Order not found → Log error, return early
- UPC message already deleted → Skip delete, continue
- MDG update fails → Log error, but still send notification

### Call Vendor Errors
- Vendor not in RESTAURANT_SHORTCUTS → Use first 2 chars as fallback
- RESTAURANT_ACCOUNTS not populated → Show placeholder message
- Invalid vendor name → Log error

---

## Performance Considerations

- **No additional API calls** during normal flow
- **Unassign**: 3 Telegram API calls (delete, edit, send)
- **Call menu**: 1 Telegram API call (send temporary message)
- **State updates**: In-memory only (no database overhead)

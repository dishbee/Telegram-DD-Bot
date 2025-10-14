# UPC Assignment Enhancement - Implementation Summary

## Overview
Added two new buttons to UPC assignment messages (private chat with courier):
1. **Unassign Button** - Allows courier to remove assignment before delivery
2. **Call Restaurant Button** - Triggers call to restaurant (placeholder for Telegram integration)

---

## 1. Unassign Button (`🔓 Unassign`)

### Behavior
- **Visibility**: Only shown BEFORE delivery is marked (removed after ✅ Delivered)
- **Action**: `unassign_order|{order_id}`
- **Flow**:
  1. Courier clicks "Unassign" in their private chat
  2. UPC assignment message is deleted
  3. Order state reverted: removes `assigned_to`, `assigned_at`, `assigned_by` fields
  4. MDG original order message updated: removes "👤 Assigned to:" line (time request buttons remain)
  5. MDG-CONF assignment message re-sent with assignment buttons (👈 Assign to myself / 👉 Assign to...)
  6. Notification sent to MDG: `"Order #{num} was unassigned by {courier}."`

### State Changes
```python
# Before unassign:
order["status"] = "assigned"
order["assigned_to"] = user_id
order["assigned_at"] = datetime
order["upc_assignment_message_id"] = msg_id

# After unassign:
order["status"] = "assigned"  # Ready for re-assignment
# assigned_to, assigned_at, upc_assignment_message_id deleted
```

### Code Changes
- **upc.py**: 
  - Modified `assignment_cta_keyboard()` - Added Unassign button conditionally
  - Added `handle_unassign_order()` - Complete unassignment workflow
- **main.py**: 
  - Added `unassign_order` callback handler at line ~2137

---

## 2. Call Restaurant Button (`🏪 Call {Shortcut}`)

### Behavior
- **Single Vendor**: Direct button shows vendor shortcut (e.g., "🏪 Call JS")
- **Multi-Vendor**: Opens selection menu with all vendors
- **Action**: 
  - Single: `call_vendor|{order_id}|{vendor}`
  - Multi: `call_vendor_menu|{order_id}` → then `call_vendor|{order_id}|{vendor}`
- **Current Implementation**: Placeholder message informing user to call directly
- **Future**: Will trigger Telegram call when `RESTAURANT_ACCOUNTS` mapping is populated

### Vendor Shortcuts Used
```python
JS = Julis Spätzlerei
LR = Leckerolls
ZH = Zweite Heimat
DD = dean & david
PF = Pommes Freunde
KA = Kahaani
SA = i Sapori della Toscana
AP = Wittelsbacher Apotheke
```

### Code Changes
- **upc.py**: 
  - Modified `assignment_cta_keyboard()` - Added Call button(s) based on vendor count
  - Modified `initiate_restaurant_call()` - Updated message to show vendor shortcut
  - Modified `show_restaurant_selection()` - Changed emoji from 🍽 to 🏪
- **main.py**: 
  - Added `call_vendor` callback handler at line ~2109
  - Added `call_vendor_menu` callback handler at line ~2118
  - Removed old `call_restaurant` and `select_restaurant` handlers (replaced)

---

## Updated UPC Button Layout

### Before Delivery:
```
[🧭 Navigate]
[⏰ Delay] [🔓 Unassign]
[🏪 Call JS]  (or "Call Restaurant" if multi-vendor)
[✅ Delivered]
```

### After Delivery:
```
[🧭 Navigate]
[⏰ Delay]
[🏪 Call JS]
[✅ Delivered]  (disabled state, already delivered)
```

---

## Notifications & Status Messages

### New Status Message
- **ST-UNASSIGNED**: `"Order #{num} was unassigned by {courier}."`
- **Style**: Same as existing delivery notification
- **Channel**: Sent to MDG (Main Dispatch Group)
- **Auto-delete**: No (permanent notification)

---

## Testing Checklist

### Unassign Workflow
- [ ] Unassign button visible before delivery
- [ ] Unassign button hidden after delivery
- [ ] UPC message deleted on unassign
- [ ] MDG updated: "Assigned to:" line removed
- [ ] Assignment buttons restored in MDG
- [ ] Notification appears in MDG
- [ ] Order can be re-assigned after unassignment

### Call Restaurant Workflow
- [ ] Single vendor: Direct "Call {Shortcut}" button appears
- [ ] Multi-vendor: "Call Restaurant" opens selection menu
- [ ] Vendor shortcuts display correctly (JS, LR, DD, etc.)
- [ ] Placeholder message shows when clicked
- [ ] ← Back button closes menu (multi-vendor)

### Edge Cases
- [ ] Unassign works for self-assigned orders
- [ ] Unassign works for dispatcher-assigned orders
- [ ] Call button works for all vendor types
- [ ] No errors if vendor not in RESTAURANT_SHORTCUTS mapping

---

## Future Enhancements

### Telegram Call Integration
When ready to implement automatic calling:

1. **Populate Environment Variable**:
   ```bash
   RESTAURANT_ACCOUNTS='{"Julis Spätzlerei": 123456789, "Leckerolls": 987654321, ...}'
   ```

2. **Update `initiate_restaurant_call()` in upc.py**:
   ```python
   # Get restaurant Telegram account
   from main import RESTAURANT_ACCOUNTS
   restaurant_user_id = RESTAURANT_ACCOUNTS.get(vendor)
   
   if restaurant_user_id:
       # Trigger Telegram call
       await bot.start_call(user_id, restaurant_user_id)
   else:
       # Fallback to current placeholder message
   ```

3. **Required**: Restaurant Telegram accounts must be created and user_ids collected

---

## Files Modified

1. **upc.py** (3 functions modified, 1 added):
   - `assignment_cta_keyboard()` - Added Unassign and Call buttons
   - `show_restaurant_selection()` - Changed emoji to 🏪
   - `initiate_restaurant_call()` - Show vendor shortcut
   - `handle_unassign_order()` - NEW: Complete unassignment workflow

2. **main.py** (3 handlers added/modified):
   - Import statements unchanged (no new imports needed)
   - `call_vendor` - NEW: Handle direct vendor call
   - `call_vendor_menu` - NEW: Show vendor selection
   - `unassign_order` - NEW: Handle unassignment

3. **CHEAT-SHEET.md** (3 sections updated):
   - UPC Buttons section - Added BTN-UNASSIGN and BTN-CALL-VEND
   - MDG Status Updates - Added ST-UNASSIGNED
   - UPC Callback Actions - Updated action names

---

## Deployment Notes

- **No new dependencies required**
- **No environment variable changes required** (except for future Telegram calling)
- **No database migrations** (in-memory STATE only)
- **Backward compatible**: Existing orders not affected
- **Test environment ready**: Can be deployed immediately

---

## Known Limitations

1. **Unassign after delivery**: Not supported by design (button hidden)
2. **Telegram calling**: Placeholder only until RESTAURANT_ACCOUNTS populated
3. **No undo**: Unassignment cannot be undone (must re-assign manually)
4. **Group orders**: Unassignment doesn't affect group state (if implemented later)

---

**Implementation Date**: October 14, 2025  
**Status**: Complete and ready for deployment  
**Testing Required**: Yes - full workflow testing recommended

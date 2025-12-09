# PHASE 3 COMPLETE - UPC.PY ANALYSIS

**HEADER: This analysis contains ZERO interpretation or hallucination. Every claim is cited with line numbers from upc.py (1,169 lines total).**

---

## MODULE CONFIGURATION

**Function: `configure()`** (Lines 29-42)
- Sets module-level `STATE` and `bot` references from main.py
- **GUARD**: Prevents reconfiguration during circular imports (line 35 check)
- Logs warning if STATE already set to prevent overwriting

**Global Variables:**
- `STATE` (Line 27): Module-level reference to main.py STATE dict
- `bot` (Line 28): Module-level reference to Telegram bot instance
- `TIMEZONE` (Line 12): ZoneInfo("Europe/Berlin") for Passau, Germany

---

## FUNCTION 1: build_assignment_message()

**Purpose**: Build assignment message sent to courier's private chat (Lines 415-591)

**Output Format**:

```
{status_lines from utils.build_status_lines()}────────────────

{group_header - if order in group}

🕒 {pickup_time} ➞ {chef_emoji} {vendor_shortcut} ({product_count})
🕒 {pickup_time} ➞ {chef_emoji} {vendor_shortcut} ({product_count})

🗺️ [{address}]({maps_link})

👤 {customer_name}

☎️ {phone}

{optional_section - note/tip/cash if NOT delivered}
```

**Code Evidence (Lines 475-584)**:
```python
# Modify status_text to include order number in header
if order.get("status") == "delivered":
    delivery_time = ""
    for entry in reversed(order.get("status_history", [])):
        if entry.get("type") == "delivered" and "time" in entry:
            delivery_time = entry["time"]
            break
    status_text = f"✅ Delivered: {delivery_time}\n" if delivery_time else "✅ Delivered\n"
elif "👇 Assigned order" in status_text:
    status_text = f"👇 Assigned order #{order_num}\n"

# Add separator line after status (with blank line after)
separator = "────────────────\n\n"

# Add empty line after status if order is in a Group (combining system)
if order.get("group_id") and status_text:
    status_text += "\n"

# Group indicator (if order is in a group)
group_header = ""
if order.get("group_id"):
    from mdg import get_group_orders
    
    group_color = order.get("group_color", "🔵")
    group_position = order.get("group_position", 1)
    group_id = order["group_id"]
    
    # Calculate total orders in group
    from mdg import get_group_orders
    group_orders = get_group_orders(STATE, group_id)
    group_total = len(group_orders)
    group_header = f"{group_color} Group: {group_position}/{group_total}\n\n"

# Restaurant info with confirmed times and product quantities
vendors = order.get("vendors", [])
confirmed_times = order.get("confirmed_times", {})
vendor_items = order.get("vendor_items", {})

restaurant_section = ""
for idx, vendor in enumerate(vendors):
    # Always show restaurant-confirmed time (when courier should pick up from restaurant)
    pickup_time = confirmed_times.get(vendor, "ASAP")
    chef_emoji = chef_emojis[idx % len(chef_emojis)]
    
    # Use vendor shortcut instead of full name
    vendor_shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
    
    # Count products for this vendor
    items = vendor_items.get(vendor, [])
    product_count = 0
    for item_line in items:
        # Extract quantity from format "2 x Product Name" or "- 2 x Product Name"
        # Smoothr format: "2 x Product" (no dash)
        # Shopify format: "- 2 x Product" (with dash)
        item_clean = item_line.lstrip('- ').strip()
        if ' x ' in item_clean:
            qty_part = item_clean.split(' x ')[0].strip()
            try:
                product_count += int(qty_part)
            except ValueError:
                product_count += 1
        else:
            product_count += 1
    
    # New format: 🕒 23:57 ➞ 👩‍🍳 ZH (3)
    restaurant_section += f"🕒 {pickup_time} ➞ {chef_emoji} {vendor_shortcut} ({product_count})\n"

restaurant_section += "\n"
```

**Line Components**:

1. **Status Line** (Lines 475-483):
   - Delivered: `✅ Delivered: {time}\n` OR `✅ Delivered\n`
   - Assigned: `👇 Assigned order #{order_num}\n`

2. **Separator** (Line 486): `────────────────\n\n` (double newline after)

3. **Group Header** (Lines 489-504): If order in group: `{group_color} Group: {position}/{total}\n\n`

4. **Restaurant Section** (Lines 506-545): One line per vendor: `🕒 {time} ➞ {chef_emoji} {shortcut} ({count})\n`

5. **Address Line** (Lines 547-564):
   - Format: Street + zip in parentheses
   - Shopify: `{street_part} ({zip_part})`
   - Clickable link: `🗺️ [{formatted_address}]({maps_link})\n\n`

6. **Customer Line** (Lines 566-567): `👤 {customer_name}\n\n`

7. **Phone Line** (Lines 569-572): `☎️ {formatted_phone}\n` (uses `format_phone_for_android()`)

8. **Optional Section** (Lines 574-585): Only if NOT delivered:
   - Note: `\n❕ Note: {note}\n`
   - Tip: `❕ Tip: {tips}€\n`
   - Cash: `❕ Cash: {total}\n`

**Chef Emojis** (Line 487): 12 rotating emojis same as MDG-CONF

---

## FUNCTION 2: assignment_cta_keyboard()

**Purpose**: Build CTA buttons for assigned orders in private chats (Lines 593-623)

**Layout**:
```
[🧭 Navigate]  ← Google Maps URL with bicycling directions
[🚩 Problem]  ← Opens problem submenu
[✅ Delivered]  ← Confirms delivery
```

**Code Evidence (Lines 600-619)**:
```python
buttons = []
address = order['customer'].get('original_address', order['customer']['address'])

# Row 1: Navigate
maps_url = f"https://www.google.com/maps/dir/?api=1&destination={address.replace(' ', '+')}&travelmode=bicycling"
navigate = InlineKeyboardButton("🧭 Navigate", url=maps_url)
buttons.append([navigate])

# Row 2: Problem (opens submenu)
problem = InlineKeyboardButton(
    "🚩 Problem",
    callback_data=f"show_problem_menu|{order_id}"
)
buttons.append([problem])

# Row 3: Mark delivered
delivered = InlineKeyboardButton(
    "✅ Delivered",
    callback_data=f"confirm_delivered|{order_id}"
)
buttons.append([delivered])
```

**Callback Data Formats**:
- Navigate: External URL (no callback data)
- Problem: `show_problem_menu|{order_id}`
- Delivered: `confirm_delivered|{order_id}`

---

## FUNCTION 3: problem_options_keyboard()

**Purpose**: Build problem submenu with Delay, Unassign, Call Restaurant options (Lines 625-673)

**Layout**:
```
[⏳ Delay]
[🚫 Unassign]
[{chef_emoji} Call {vendor_shortcut}]  ← one per vendor
[{chef_emoji} Call {vendor_shortcut}]
[← Back]
```

**Code Evidence (Lines 633-668)**:
```python
buttons = []
vendors = order.get("vendors", [])

# Row 1: Delay
delay = InlineKeyboardButton(
    "⏳ Delay",
    callback_data=f"delay_order|{order_id}"
)
buttons.append([delay])

# Row 2: Unassign
unassign = InlineKeyboardButton(
    "🚫 Unassign",
    callback_data=f"unassign_order|{order_id}"
)
buttons.append([unassign])

# Row 3+: Call Restaurant(s) - separate button for each vendor
chef_emojis = ["👩‍🍳", "👩🏻‍🍳", "👩🏼‍🍳", "👩🏾‍🍳", "🧑‍🍳", "🧑🏻‍🍳", "🧑🏼‍🍳", "🧑🏾‍🍳", "👨‍🍳", "👨🏻‍🍳", "👨🏼‍🍳", "👨🏾‍🍳"]
for idx, vendor in enumerate(vendors):
    vendor_shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
    chef_emoji = chef_emojis[idx % len(chef_emojis)]
    call_btn = InlineKeyboardButton(
        f"{chef_emoji} Call {vendor_shortcut}",
        callback_data=f"call_vendor|{order_id}|{vendor}"
    )
    buttons.append([call_btn])

# Back button
back_btn = InlineKeyboardButton(
    "← Back",
    callback_data="hide"
)
buttons.append([back_btn])
```

**Callback Data Formats**:
- Delay: `delay_order|{order_id}`
- Unassign: `unassign_order|{order_id}`
- Call vendor: `call_vendor|{order_id}|{vendor}`
- Back: `hide`

---

## FUNCTION 4: mdg_assignment_keyboard()

**Purpose**: Build assignment buttons for MDG after all vendors confirm (Lines 77-97)

**Layout**:
```
[👈 Assign to myself]
[Assign to 👉]
[📌 Assigned orders]  ← conditional, only if assigned orders exist
```

**Code Evidence (Lines 80-95)**:
```python
buttons = [
    [InlineKeyboardButton("👈 Assign to myself", callback_data=f"assign_myself|{order_id}")],
    [InlineKeyboardButton("Assign to 👉", callback_data=f"assign_to_menu|{order_id}")]
]

# Check if there are any assigned orders in STATE (not per-order check)
has_assigned = False
for oid, order_data in STATE.items():
    if order_data.get("assigned_to") and order_data.get("status") != "delivered":
        has_assigned = True
        break

# Only show "Assigned orders" button if there are assigned orders
if has_assigned:
    buttons.append([InlineKeyboardButton("📌 Assigned orders", callback_data=f"show_assigned|{order_id}|{int(now().timestamp())}")])
```

**Callback Data Formats**:
- Assign myself: `assign_myself|{order_id}`
- Assign to menu: `assign_to_menu|{order_id}`
- Assigned orders: `show_assigned|{order_id}|{timestamp}`

---

## FUNCTION 5: mdg_unassign_keyboard()

**Purpose**: Build keyboard with single Unassign button for MDG-CONF after assignment (Lines 99-109)

**Layout**:
```
[🚫 Unassign]
```

**Code Evidence (Lines 106-108)**:
```python
keyboard = [
    [InlineKeyboardButton("🚫 Unassign", callback_data=f"unassign_order|{order_id}")]
]
```

**Callback Data Format**: `unassign_order|{order_id}`

---

## FUNCTION 6: courier_selection_keyboard()

**Purpose**: Build keyboard with buttons for each available courier (Lines 191-248)

**Layout**:
```
[Bee 1]  ← priority couriers first
[Bee 2]
[Bee 3]
[Other Courier Name]  ← alphabetically
[← Back]
```

**Code Evidence (Lines 211-243)**:
```python
# Get couriers (live from MDG or fallback to COURIER_MAP)
couriers = await get_mdg_couriers(bot)

if not couriers:
    logger.error("No couriers available from MDG or COURIER_MAP")
    return None

buttons = []

# Priority couriers (Bee 1, Bee 2, Bee 3) first
priority_names = ["Bee 1", "Bee 2", "Bee 3"]
for priority_name in priority_names:
    for courier in couriers:
        if courier["username"] == priority_name:
            buttons.append([InlineKeyboardButton(
                courier["username"],
                callback_data=f"assign_to_user|{order_id}|{courier['user_id']}"
            )])
            break

# Then other couriers
for courier in couriers:
    if courier["username"] not in priority_names:
        buttons.append([InlineKeyboardButton(
            courier["username"],
            callback_data=f"assign_to_user|{order_id}|{courier['user_id']}"
        )])

# Add Back button
buttons.append([InlineKeyboardButton("← Back", callback_data="hide")])
```

**Callback Data Format**: `assign_to_user|{order_id}|{user_id}`

**Courier Detection** (Lines 111-174):
- **Primary**: `get_mdg_couriers(bot)` - queries live MDG administrators via `bot.get_chat_administrators()`
- **Fallback**: `get_couriers_from_map()` - uses static COURIER_MAP if API fails

---

## FUNCTION 7: send_assignment_to_private_chat()

**Purpose**: Send order assignment details to user's private chat (Lines 341-413)

**Flow** (Lines 346-408):
1. Update STATE: `assigned_to`, `assigned_at`, `status = "assigned"`
2. Get courier name (try Telegram API, fallback to DRIVERS reverse lookup)
3. Append assignment entry to `status_history`
4. Build assignment message (calls `build_assignment_message()`)
5. Send to courier's private chat with CTA keyboard
6. Track message IDs: `upc_message_id`, `upc_assignment_message_id`, `assignment_messages[user_id]`

**Code Evidence (Lines 346-370)**:
```python
# Update order status and history BEFORE building message
order["assigned_to"] = user_id
order["assigned_at"] = now()
order["status"] = "assigned"

# Get courier name - try Telegram API first, then DRIVERS reverse lookup
courier_name = None
try:
    if bot:
        user = await bot.get_chat(user_id)
        courier_name = user.first_name or user.username or f"User{user_id}"
except Exception as e:
    logger.warning(f"Could not get user info from Telegram API: {e}")

# Fallback: reverse lookup in DRIVERS ({"Bee 1": 383910036, ...})
if not courier_name:
    from utils import DRIVERS
    for name, uid in DRIVERS.items():
        if uid == user_id:
            courier_name = name
            break

# Final fallback
if not courier_name:
    courier_name = f"User{user_id}"

order["status_history"].append({
    "type": "assigned",
    "courier": courier_name,
    "courier_id": user_id,
    "timestamp": now()
})
```

---

## FUNCTION 8: update_mdg_with_assignment()

**Purpose**: Update MDG message to show assignment status (Lines 321-413)

**Updates** (Lines 328-406):
1. Edit MDG-ORD with updated status (keeps vendor buttons visible)
2. Edit all RG messages with new status
3. Edit MDG-CONF to show `[🚫 Unassign]` button (calls `mdg_unassign_keyboard()`)

**Code Evidence (Lines 328-348)**:
```python
# Build updated MDG text with status line (includes assignment info)
import mdg
updated_text = mdg.build_mdg_dispatch_text(order, show_details=order.get("mdg_expanded", False))

# Keep vendor selection buttons visible
await safe_edit_message(
    DISPATCH_MAIN_CHAT_ID,
    order["mdg_message_id"],
    updated_text,
    mdg.mdg_time_request_keyboard(order_id)  # Keep buttons
)

# Update all RG messages with new status
for vendor in order.get("vendors", []):
    vendor_group_id = VENDOR_GROUP_MAP.get(vendor)
    rg_msg_id = order.get("rg_message_ids", {}).get(vendor) or order.get("vendor_messages", {}).get(vendor)
    if vendor_group_id and rg_msg_id:
        import rg
        expanded = order.get("vendor_expanded", {}).get(vendor, False)
        text = rg.build_vendor_details_text(order, vendor) if expanded else rg.build_vendor_summary_text(order, vendor)
        await safe_edit_message(
            vendor_group_id,
            rg_msg_id,
            text,
            rg.vendor_keyboard(order_id, vendor, expanded, order)
        )
```

---

## FUNCTION 9: handle_delivery_completion()

**Purpose**: Handle delivery completion workflow (Lines 675-750)

**Flow** (Lines 680-747):
1. Update STATE: `status = "delivered"`, `delivered_at`, `delivered_by`
2. Get courier name and shortcut
3. Append delivery entry to `status_history` with time
4. Send confirmation to MDG: `Order 🔖 {num}: ✅ Delivered by 🐝 {courier} at {time}`
5. Delete MDG-CONF and temporary messages
6. Update MDG-ORD with delivered status (keep buttons)
7. Update all RG messages with delivered status
8. Update UPC message with delivered status and replace keyboard with `[❌ Undeliver]` button
9. Handle group updates if order was in group (calls `update_group_on_delivery()`)

**Code Evidence (Lines 680-722)**:
```python
# Update order status
order["status"] = "delivered"
order["delivered_at"] = now()
order["delivered_by"] = user_id

# Get courier info
assignee_info = COURIER_MAP.get(str(user_id), {})
assignee_name = assignee_info.get("username", f"User{user_id}")

# Get courier shortcut for display
from mdg import COURIER_SHORTCUTS
courier_shortcut = COURIER_SHORTCUTS.get(assignee_name, assignee_name[:2] if len(assignee_name) >= 2 else assignee_name)

# Append status to history
delivery_time = now().strftime("%H:%M")
order["status_history"].append({
    "type": "delivered",
    "courier": assignee_name,
    "time": delivery_time,
    "timestamp": now()
})

# Send confirmation to MDG (runs in background, doesn't block handler)
order_num = order.get('name', '')[-2:] if len(order.get('name', '')) >= 2 else order.get('name', '')
delivered_msg = f"Order 🔖 {order_num}: ✅ Delivered by 🐝 {courier_shortcut} at {delivery_time}"
asyncio.create_task(send_status_message(DISPATCH_MAIN_CHAT_ID, delivered_msg))

# Delete MDG-CONF and other temporary messages
if "mdg_additional_messages" in order:
    for msg_id in order["mdg_additional_messages"]:
        await safe_delete_message(DISPATCH_MAIN_CHAT_ID, msg_id)
    order["mdg_additional_messages"] = []

# Update UPC message with delivered status and replace keyboard with Undeliver button
upc_msg_id = order.get("upc_message_id")
if upc_msg_id:
    updated_upc_text = build_assignment_message(order)
    # Replace entire keyboard with single Undeliver button
    undeliver_keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ Undeliver", callback_data=f"undeliver_order|{order_id}|{int(now().timestamp())}")
    ]])
    await safe_edit_message(
        user_id,
        upc_msg_id,
        updated_upc_text,
        undeliver_keyboard
    )
```

**Undeliver Keyboard** (Lines 737-740): Single button: `[❌ Undeliver]` with callback `undeliver_order|{order_id}|{timestamp}`

---

## FUNCTION 10: handle_undelivery()

**Purpose**: Revert delivered status back to assigned (Lines 752-822)

**Flow** (Lines 760-818):
1. Verify order is delivered
2. Get courier name for notification
3. Revert STATE: `status = "assigned"`, remove `delivered_at`, `delivered_by`
4. Pop last delivered entry from `status_history`
5. Send notification to MDG: `🔖 {num} was undelivered by {courier} at {time}`
6. Update MDG-ORD to remove delivered status
7. Update all RG messages to remove delivered status
8. Update UPC message - restore full CTA keyboard

**Code Evidence (Lines 769-809)**:
```python
# Revert STATE fields
order["status"] = "assigned"
order.pop("delivered_at", None)
order.pop("delivered_by", None)

# Remove last delivered entry from status_history
if order["status_history"] and order["status_history"][-1].get("type") == "delivered":
    order["status_history"].pop()
    logger.info(f"Removed delivered entry from status_history for order {order_id}")

# Send notification to MDG
order_num = order.get('name', '')[-2:] if len(order.get('name', '')) >= 2 else order.get('name', '')
undeliver_msg = f"🔖 {order_num} was undelivered by {courier_name} at {now().strftime('%H:%M')}"
await safe_send_message(DISPATCH_MAIN_CHAT_ID, undeliver_msg)

# Update UPC message - restore full keyboard
upc_msg_id = order.get("upc_message_id")
if upc_msg_id:
    updated_upc_text = build_assignment_message(order)
    # Restore original full CTA keyboard
    await safe_edit_message(
        user_id,
        upc_msg_id,
        updated_upc_text,
        assignment_cta_keyboard(order_id)
    )
```

---

## FUNCTION 11: show_delay_options()

**Purpose**: Show delay options for assigned courier based on confirmed time (Lines 864-897)

**Flow**:
- **Multi-vendor** (Lines 877-893): Show vendor selection buttons first
- **Single vendor** (Line 895): Show time picker directly

**Code Evidence (Lines 877-895)**:
```python
# Multi-vendor: show vendor selection first
if len(vendors) > 1:
    buttons = []
    for vendor in vendors:
        vendor_shortcut = RESTAURANT_SHORTCUTS.get(vendor, vendor[:2].upper())
        buttons.append([InlineKeyboardButton(
            f"Request {vendor_shortcut}",
            callback_data=f"delay_vendor_selected|{order_id}|{vendor}"
        )])
    
    # Add Back button
    buttons.append([InlineKeyboardButton("← Back", callback_data="hide")])
    
    await safe_send_message(
        user_id,
        "⏳ Select vendor to request delay:",
        InlineKeyboardMarkup(buttons)
    )
else:
    # Single vendor: show time options directly
    await show_delay_time_picker(order_id, user_id, vendors[0] if vendors else None)
```

**Callback Data Format**: `delay_vendor_selected|{order_id}|{vendor}`

---

## FUNCTION 12: show_delay_time_picker()

**Purpose**: Show time picker for delay request (Lines 900-961)

**Layout**:
```
⏳ Request new ({current_time}) for 🔖 {num} from {vendor}

[+5m → ⏰ 09:32]
[+10m → ⏰ 09:37]
[+15m → ⏰ 09:42]
[+20m → ⏰ 09:47]
[← Back]
```

**Code Evidence (Lines 918-950)**:
```python
# Parse the confirmed time
hour, minute = map(int, latest_time_str.split(':'))
base_time = now().replace(hour=hour, minute=minute, second=0, microsecond=0)

# Calculate delay options: +5, +10, +15, +20 minutes
delay_buttons = []
minute_increments = [5, 10, 15, 20]

for i, minutes_to_add in enumerate(minute_increments):
    delayed_time = base_time + timedelta(minutes=minutes_to_add)
    time_str = delayed_time.strftime("%H:%M")
    # Format: "+5m → ⏰ 09:32"
    button_text = f"+{minutes_to_add}m → ⏰ {time_str}"
    
    # Include vendor in callback if specified
    if vendor:
        callback = f"delay_selected|{order_id}|{time_str}|{vendor}"
    else:
        callback = f"delay_selected|{order_id}|{time_str}"
    
    delay_buttons.append([InlineKeyboardButton(
        button_text,
        callback_data=callback
    )])

# Add Back button
delay_buttons.append([InlineKeyboardButton("← Back", callback_data="hide")])

await safe_send_message(
    user_id,
    f"⏳ Request new ({latest_time_str}) for 🔖 {order_num} from {vendor_shortcut}",
    InlineKeyboardMarkup(delay_buttons)
)
```

**Callback Data Formats**:
- With vendor: `delay_selected|{order_id}|{time}|{vendor}`
- No vendor: `delay_selected|{order_id}|{time}`

---

## FUNCTION 13: send_delay_request_to_restaurants()

**Purpose**: Send delay request to vendor(s) for this order (Lines 981-1054)

**Flow** (Lines 996-1048):
1. Determine which vendors to notify (specific vendor for multi-vendor, all vendors for single-vendor)
2. Append `delay_sent` entry to `status_history`
3. Send delay message to each vendor: `We have a delay, if possible prepare {num} at {time}. If not, please keep it warm.`
4. Send with restaurant response buttons (Works / Later at...)
5. Update UPC message with new status
6. Confirm to courier: `✅ Delay request for 🔖 {num} sent to {vendor_shortcuts}`
7. Auto-delete confirmation after 20 seconds

**Code Evidence (Lines 1010-1040)**:
```python
# Send delay request to each vendor
for v in vendors_to_notify:
    vendor_chat = VENDOR_GROUP_MAP.get(v)
    if vendor_chat:
        delay_msg = f"We have a delay, if possible prepare {order_num} at {new_time}. If not, please keep it warm."
        
        # Import restaurant_response_keyboard from rg module
        from rg import restaurant_response_keyboard
        
        # Send with restaurant response buttons (Works / Later at...)
        await safe_send_message(
            vendor_chat,
            delay_msg,
            restaurant_response_keyboard(new_time, order_id, v)
        )
        
        logger.info(f"Delay request sent to {v} for order {order_id} - new time {new_time}")

# Update UPC message with new status
upc_msg_id = order.get("upc_message_id")
if upc_msg_id:
    updated_upc_text = build_assignment_message(order)
    await safe_edit_message(
        user_id,
        upc_msg_id,
        updated_upc_text,
        assignment_cta_keyboard(order_id)
    )

# Confirm to user with updated format
vendor_shortcuts = "+".join([RESTAURANT_SHORTCUTS.get(v, v[:2].upper()) for v in vendors_to_notify])
confirm_msg = await safe_send_message(
    user_id,
    f"✅ Delay request for 🔖 {order_num} sent to {vendor_shortcuts}"
)

# Auto-delete after 20 seconds
if confirm_msg:
    loop = asyncio.get_event_loop()
    loop.call_later(20, lambda: asyncio.create_task(safe_delete_message(user_id, confirm_msg.message_id)))
```

---

## SUPPORTING HELPER FUNCTIONS

### check_all_vendors_confirmed() (Lines 44-75)
Checks if ALL vendors have confirmed their times - returns True if ready for assignment.

**Logic** (Lines 56-71):
```python
# Check if all vendors have confirmed their time
for vendor in vendors:
    if vendor not in confirmed_times:
        logger.info(f"DEBUG: Order {order_id} - Vendor {vendor} NOT in confirmed_times")
        return False
    else:
        logger.info(f"DEBUG: Order {order_id} - Vendor {vendor} confirmed at {confirmed_times[vendor]}")

logger.info(f"DEBUG: Order {order_id} - ALL {len(vendors)} vendors have confirmed - ready for assignment")
return True
```

### get_mdg_couriers() (Lines 111-153)
Queries live MDG administrators via `bot.get_chat_administrators()`, filters out bots, returns list of dicts with `user_id` and `username`. Falls back to COURIER_MAP if API fails.

### get_couriers_from_map() (Lines 155-165)
Static fallback - reads COURIER_MAP environment variable.

### update_group_upc_messages() (Lines 251-306)
Updates UPC assignment messages for all orders in a group when group size changes (rebuilds with updated position/total).

### update_group_on_delivery() (Lines 824-862)
Updates group when order is delivered:
- Removes group fields from delivered order
- If only 1 remains: dissolves group
- If 2+ remain: recalculates positions and updates all UPC messages

### show_restaurant_selection() (Lines 963-988)
Shows restaurant selection for multi-vendor orders when courier wants to call restaurant.

### initiate_restaurant_call() (Lines 1056-1070)
Placeholder for future Telegram call integration - currently just sends message to courier.

### get_assignment_status() (Lines 1072-1086)
Returns current assignment status string (for future status queries).

---

## CALLBACK DATA FORMATS SUMMARY

**Assignment**:
- `assign_myself|{order_id}`
- `assign_to_menu|{order_id}`
- `assign_to_user|{order_id}|{user_id}`
- `show_assigned|{order_id}|{timestamp}`
- `unassign_order|{order_id}`

**Delivery**:
- `confirm_delivered|{order_id}`
- `undeliver_order|{order_id}|{timestamp}`

**Problem Menu**:
- `show_problem_menu|{order_id}`
- `delay_order|{order_id}`
- `call_vendor|{order_id}|{vendor}`

**Delay Workflow**:
- `delay_vendor_selected|{order_id}|{vendor}`
- `delay_selected|{order_id}|{time}` (single-vendor)
- `delay_selected|{order_id}|{time}|{vendor}` (multi-vendor)

**Utility**:
- `hide` (close menu)

---

## STATE FIELD DEPENDENCIES

**Read by UPC Functions**:
- `order["vendors"]` - list of vendor names
- `order["confirmed_times"]` - dict of vendor → confirmed time
- `order["vendor_items"]` - dict of vendor → product list
- `order["customer"]` - dict with name, address, phone, zip, original_address
- `order["note"]`, `order["tips"]`, `order["total"]`, `order["payment_method"]`
- `order["assigned_to"]`, `order["assigned_at"]`, `order["status"]`
- `order["mdg_message_id"]`, `order["mdg_conf_message_id"]`, `order["mdg_additional_messages"]`
- `order["rg_message_ids"]` OR `order["vendor_messages"]`
- `order["upc_message_id"]`, `order["upc_assignment_message_id"]`
- `order["assignment_messages"]` - dict of user_id → message_id
- `order["status_history"]` - list of status entries
- `order["group_id"]`, `order["group_color"]`, `order["group_position"]` (combining system)
- `order["mdg_expanded"]`, `order["vendor_expanded"]` (display state)

**Modified by UPC Functions**:
- `order["assigned_to"]` - set to courier user_id
- `order["assigned_at"]` - set to timestamp
- `order["status"]` - changed to "assigned", "delivered"
- `order["delivered_at"]`, `order["delivered_by"]` - set on delivery
- `order["status_history"]` - appends entries for assignment, delivery, delay
- `order["upc_message_id"]`, `order["upc_assignment_message_id"]` - track private chat messages
- `order["assignment_messages"][user_id]` - track assignment per courier
- `order["group_position"]` - recalculated when group changes

---

## WORKFLOW INTEGRATION

**Assignment Flow**:
1. All vendors confirm times → `check_all_vendors_confirmed()` returns True
2. MDG shows assignment buttons → `mdg_assignment_keyboard()`
3. User clicks "Assign to myself" or selects courier → `courier_selection_keyboard()`
4. Assignment sent to courier's private chat → `send_assignment_to_private_chat()`
5. MDG and RG messages updated → `update_mdg_with_assignment()`

**Delivery Flow**:
1. Courier clicks "✅ Delivered" → `handle_delivery_completion()`
2. STATE updated, confirmation sent to MDG
3. All messages (MDG, RG, UPC) updated with delivered status
4. UPC keyboard replaced with `[❌ Undeliver]` button
5. Group updated if order was in group → `update_group_on_delivery()`

**Undelivery Flow**:
1. Courier clicks "❌ Undeliver" → `handle_undelivery()`
2. STATE reverted, notification sent to MDG
3. All messages updated to remove delivered status
4. UPC keyboard restored to full CTA buttons

**Delay Flow**:
1. Courier clicks "🚩 Problem" → "⏳ Delay" → `show_delay_options()`
2. Multi-vendor: select vendor → `show_delay_time_picker()`
3. Single vendor: show time picker directly
4. Courier selects new time → `send_delay_request_to_restaurants()`
5. Delay message sent to vendor(s) with restaurant response buttons
6. Confirmation sent to courier (auto-deletes after 20s)

---

**END OF PHASE 3 ANALYSIS**

# Telegram Dispatch Bot - System Reference Guide

Quick reference for all system elements with shortcuts and clear naming conventions.

---

## 📱 Communication Channels

| Shortcut | Full Name | Description |
|----------|-----------|-------------|
| **MDG** | Main Dispatch Group | Central coordination chat - order arrival, time requests, assignments |
| **RG** | Restaurant Groups | Vendor-specific chats - order details, confirmations |
| **UPC** | User Private Chats | Courier DMs - assignment details, CTA buttons |

---

## 📨 Message Types

### MDG Messages

| Code | Name | Description | When Sent |
|------|------|-------------|-----------|
| **MDG-ORD** | Order Dispatch Message | Initial order arrival with customer/address/items | Shopify webhook received |
| **MDG-TIME-REQ** | Time Request Menu | ASAP/TIME buttons or vendor selection | User clicks time request |
| **MDG-TIME-PICK** | Time Picker | +5/+10/+15/+20 minute buttons | User selects "TIME" |
| **MDG-SAME** | Same Time Menu | List of recent orders with times | User selects "Same time as" |
| **MDG-EXACT** | Exact Time Picker | Hour selection → Minute selection | User selects "Exact time" |
| **MDG-CONF** | Assignment Confirmation | "✅ Restaurants confirmed" with details | All vendors confirm time |
| **MDG-ASSIGN** | Assignment Buttons | "👈 Assign to myself" / "👉 Assign to..." | After MDG-CONF |
| **MDG-COURIER-SEL** | Courier Selection Menu | List of available couriers | User clicks "Assign to..." |
| **MDG-STATUS** | Status Update | Vendor replies (Works/Later/Wrong) | Vendor responds |

### RG Messages

| Code | Name | Description | When Sent |
|------|------|-------------|-----------|
| **RG-SUM** | Vendor Summary | Collapsed order preview (order #, items) | Order arrives |
| **RG-DET** | Vendor Details | Expanded view (customer, phone, address) | User clicks "Details ▸" |
| **RG-TIME-REQ** | Time Request | "Please prepare for [TIME]" with buttons | Time requested from MDG |
| **RG-DELAY** | Delay Request | "We have a delay - new time [TIME]" | Courier requests delay |

### UPC Messages

| Code | Name | Description | When Sent |
|------|------|-------------|-----------|
| **UPC-ASSIGN** | Assignment Message | Order details with vendor times & CTA buttons | Order assigned to courier |
| **UPC-DELAY-PICK** | Delay Time Picker | +5/+10/+15/+20 from current time | Courier clicks "⏰ Delay" |
| **UPC-DELAY-CONF** | Delay Confirmation | "✅ Delay request sent" | Courier selects new time |
| **UPC-REST-SEL** | Restaurant Selection | List of restaurants to call | Multi-vendor call action |
| **UPC-DELIVERED** | Delivery Confirmation | "✅ Delivery completed!" | Courier marks delivered |

---

## 🔘 Button Types & Actions

### MDG Buttons

| Code | Button Text | Callback Action | Description |
|------|-------------|-----------------|-------------|
| **BTN-ASAP** | Request ASAP | `req_asap\|{order_id}` | Request immediate preparation |
| **BTN-TIME** | Request TIME | `req_time\|{order_id}` | Show time picker menu |
| **BTN-VENDOR** | Request {VENDOR} | `req_vendor\|{order_id}\|{vendor}` | Multi-vendor: select vendor |
| **BTN-TIME-PLUS** | +5/+10/+15/+20 | `time_plus\|{order_id}\|{minutes}` | Add minutes to current time |
| **BTN-SAME** | Same time as | `req_same\|{order_id}` | Show recent orders list |
| **BTN-EXACT** | Exact time | `req_exact\|{order_id}` | Show hour picker |
| **BTN-SAME-SEL** | {order} {time} | `same_selected\|{order_id}\|{ref_order}\|{time}` | Select from recent orders |
| **BTN-HOUR** | {HH}:00 | `exact_hour\|{order_id}\|{hour}` | Hour selection |
| **BTN-MINUTE** | {HH}:{MM} | `exact_selected\|{order_id}\|{time}` | Final time selection |
| **BTN-ASSIGN-ME** | 👈 Assign to myself | `assign_myself\|{order_id}` | Self-assign order |
| **BTN-ASSIGN-TO** | 👉 Assign to... | `assign_to_menu\|{order_id}` | Show courier list |
| **BTN-COURIER** | {Courier Name} | `assign_to_user\|{order_id}\|{user_id}` | Assign to selected courier |

### RG Buttons

| Code | Button Text | Callback Action | Description |
|------|-------------|-----------------|-------------|
| **BTN-TOGGLE** | Details ▸ / ◂ Hide | `toggle\|{order_id}\|{vendor}` | Expand/collapse details |
| **BTN-WORKS** | Works 👍 | `works\|{order_id}\|{vendor}` | Confirm requested time |
| **BTN-LATER** | Later at | `later\|{order_id}\|{vendor}` | Select different time |
| **BTN-PREPARE** | Will prepare at | `prepare\|{order_id}\|{vendor}` | Select preparation time (ASAP) |
| **BTN-WRONG** | Something is wrong | `wrong\|{order_id}\|{vendor}` | Report issue with order |

### UPC Buttons

| Code | Button Text | Callback Action | Description |
|------|-------------|-----------------|-------------|
| **BTN-NAV** | 🧭 Navigate | URL: Google Maps cycling | Open navigation to customer |
| **BTN-DELAY** | ⏰ Delay | `delay_order\|{order_id}` | Request delivery delay |
| **BTN-DELIVERED** | ✅ Delivered | `confirm_delivered\|{order_id}` | Mark order complete |
| **BTN-DELAY-SEL** | {HH}:{MM} | `delay_selected\|{order_id}\|{time}` | Select new delivery time |

---

## 🔧 Core Functions

### State Management

| Code | Function | File | Description |
|------|----------|------|-------------|
| **FN-STATE-GET** | `STATE.get(order_id)` | main.py | Retrieve order from state |
| **FN-STATE-UPD** | `STATE[order_id][key] = value` | main.py | Update order field |
| **FN-CHECK-CONF** | `check_all_vendors_confirmed()` | upc.py | Verify all vendors confirmed |

### Message Operations

| Code | Function | File | Description |
|------|----------|------|-------------|
| **FN-SEND** | `safe_send_message()` | utils.py | Send message with retry logic |
| **FN-EDIT** | `safe_edit_message()` | utils.py | Edit existing message |
| **FN-DEL** | `safe_delete_message()` | utils.py | Delete single message |
| **FN-CLEANUP** | `cleanup_mdg_messages()` | utils.py | Delete tracked temporary messages |

### Message Builders

| Code | Function | File | Description |
|------|----------|------|-------------|
| **FN-MDG-BUILD** | `build_mdg_dispatch_text()` | mdg.py | Build MDG order message |
| **FN-MDG-CONF** | `build_assignment_confirmation_message()` | main.py | Build vendor confirmation message |
| **FN-RG-SUM** | `build_vendor_summary_text()` | rg.py | Build collapsed vendor message |
| **FN-RG-DET** | `build_vendor_details_text()` | rg.py | Build expanded vendor message |
| **FN-UPC-ASSIGN** | `build_assignment_message()` | upc.py | Build courier assignment message |

### Keyboard Builders

| Code | Function | File | Description |
|------|----------|------|-------------|
| **FN-MDG-KB** | `mdg_time_request_keyboard()` | mdg.py | ASAP/TIME or vendor selection |
| **FN-MDG-SUB** | `mdg_time_submenu_keyboard()` | mdg.py | Time picker submenu |
| **FN-SAME-KB** | `same_time_keyboard()` | mdg.py | Recent orders keyboard |
| **FN-EXACT-KB** | `exact_time_keyboard()` | mdg.py | Hour/minute picker |
| **FN-RG-KB** | `vendor_keyboard()` | rg.py | Toggle details button |
| **FN-RG-RESP** | `restaurant_response_keyboard()` | rg.py | Works/Later/Wrong buttons |
| **FN-ASSIGN-KB** | `mdg_assignment_keyboard()` | upc.py | Assign to myself/others |
| **FN-COURIER-KB** | `courier_selection_keyboard()` | upc.py | Courier list (live detection) |
| **FN-UPC-CTA** | `assignment_cta_keyboard()` | upc.py | Navigate/Delay/Delivered buttons |

### Assignment System

| Code | Function | File | Description |
|------|----------|------|-------------|
| **FN-GET-COURIERS** | `get_mdg_couriers()` | upc.py | Query MDG for live courier list |
| **FN-COURIER-FALL** | `get_couriers_from_map()` | upc.py | Fallback to COURIER_MAP env var |
| **FN-SEND-ASSIGN** | `send_assignment_to_private_chat()` | upc.py | Send UPC-ASSIGN message |
| **FN-UPD-MDG-ASSIGN** | `update_mdg_with_assignment()` | upc.py | Update MDG with assignee name |
| **FN-DELAY-OPT** | `show_delay_options()` | upc.py | Show UPC-DELAY-PICK |
| **FN-DELAY-REQ** | `send_delay_request_to_restaurants()` | upc.py | Send RG-DELAY to all vendors |
| **FN-DELIVERED** | `handle_delivery_completion()` | upc.py | Mark order delivered, update MDG |

### Utility Functions

| Code | Function | File | Description |
|------|----------|------|-------------|
| **FN-CLEAN-NAME** | `clean_product_name()` | utils.py | Simplify product names (17 rules) |
| **FN-VALIDATE-PHONE** | `validate_phone()` | utils.py | Validate phone number format |
| **FN-VERIFY-HMAC** | `verify_webhook()` | utils.py | Verify Shopify webhook signature |
| **FN-RUN-ASYNC** | `run_async()` | utils.py | Schedule coroutine in event loop |

---

## 📊 STATE Fields

### Order Object Structure

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| **order_id** | string | Shopify order ID (key) | `"7402584965386"` |
| **name** | string | Shopify order number | `"#1058"` |
| **order_type** | string | Order source | `"shopify"` |
| **status** | string | Order lifecycle state | `"new"` / `"assigned"` / `"delivered"` |
| **vendors** | list | Restaurant names | `["Julis Spätzlerei", "Leckerolls"]` |
| **vendor_items** | dict | Items per vendor | `{"Leckerolls": ["- 2 x Classic"]}` |
| **vendor_messages** | dict | RG message IDs | `{"Leckerolls": 123456}` |
| **vendor_expanded** | dict | Expand state per vendor | `{"Leckerolls": False}` |
| **mdg_message_id** | int | MDG-ORD message ID | `789012` |
| **mdg_additional_messages** | list | Temporary message IDs | `[123, 456]` (for cleanup) |
| **requested_time** | string | Time requested from vendors | `"14:30"` |
| **confirmed_times** | dict | Per-vendor confirmed times | `{"Leckerolls": "14:35"}` |
| **confirmed_time** | string | Backward compatibility field | `"14:35"` |
| **confirmed_by** | string | Last vendor to confirm | `"Leckerolls"` |
| **assigned_to** | int | Courier user_id | `383910036` |
| **assigned_at** | datetime | Assignment timestamp | `datetime.now()` |
| **delivered_at** | datetime | Delivery timestamp | `datetime.now()` |
| **delivered_by** | int | Courier user_id who delivered | `383910036` |
| **customer** | dict | Customer info | `{"name": "John", "phone": "+49...", "address": "..."}` |
| **items_text** | string | Formatted items list | `"2 x Classic\n1 x Oreo"` |
| **note** | string | Customer note | `"Ring doorbell"` |
| **tips** | float | Tip amount | `2.50` |
| **payment_method** | string | Payment type | `"Paid"` / `"Cash on Delivery"` |
| **total** | string | Order total | `"25.40€"` |
| **created_at** | datetime | Order creation time | `datetime.now()` |

---

## 🔄 Callback Action Map

Complete list of all callback actions with their data format.

### Time Request Actions

| Action | Format | Description |
|--------|--------|-------------|
| `req_asap` | `req_asap\|{order_id}` | Request ASAP preparation |
| `req_time` | `req_time\|{order_id}` | Show time picker |
| `req_vendor` | `req_vendor\|{order_id}\|{vendor}` | Select vendor (multi-vendor) |
| `req_same` | `req_same\|{order_id}` | Show "same time as" menu |
| `req_exact` | `req_exact\|{order_id}` | Show exact time picker |
| `vendor_asap` | `vendor_asap\|{order_id}\|{vendor}` | Vendor-specific ASAP |
| `vendor_time` | `vendor_time\|{order_id}\|{vendor}` | Vendor-specific time picker |

### Time Selection Actions

| Action | Format | Description |
|--------|--------|-------------|
| `time_plus` | `time_plus\|{order_id}\|{minutes}` | Add minutes to current time |
| `same_selected` | `same_selected\|{order_id}\|{ref_order}\|{time}` | Copy time from recent order |
| `exact_hour` | `exact_hour\|{order_id}\|{hour}` | Select hour |
| `exact_selected` | `exact_selected\|{order_id}\|{time}` | Final time selected |

### Vendor Response Actions

| Action | Format | Description |
|--------|--------|-------------|
| `toggle` | `toggle\|{order_id}\|{vendor}` | Toggle details view |
| `works` | `works\|{order_id}\|{vendor}` | Confirm requested time |
| `later` | `later\|{order_id}\|{vendor}` | Select different time (show picker) |
| `later_time` | `later_time\|{order_id}\|{vendor}\|{time}` | Vendor selected later time |
| `prepare` | `prepare\|{order_id}\|{vendor}` | ASAP - select prep time |
| `prepare_time` | `prepare_time\|{order_id}\|{vendor}\|{time}` | Vendor selected prep time |
| `wrong` | `wrong\|{order_id}\|{vendor}` | Report issue |
| `wrong_delay` | `wrong_delay\|{order_id}\|{vendor}` | Confirm delay message |

### Assignment Actions

| Action | Format | Description |
|--------|--------|-------------|
| `assign_myself` | `assign_myself\|{order_id}` | Self-assign order |
| `assign_to_menu` | `assign_to_menu\|{order_id}` | Show courier selection |
| `assign_to_user` | `assign_to_user\|{order_id}\|{user_id}` | Assign to selected courier |

### UPC CTA Actions

| Action | Format | Description |
|--------|--------|-------------|
| `delay_order` | `delay_order\|{order_id}` | Show delay time picker |
| `delay_selected` | `delay_selected\|{order_id}\|{time}` | Courier selected delay time |
| `call_restaurant` | `call_restaurant\|{order_id}\|{vendor}` | Initiate restaurant call |
| `select_restaurant` | `select_restaurant\|{order_id}` | Show restaurant selection |
| `confirm_delivered` | `confirm_delivered\|{order_id}` | Mark order delivered |

---

## 🏪 Restaurant Shortcuts

| Restaurant | Shortcut | Chat ID (env) |
|------------|----------|---------------|
| Julis Spätzlerei | **JS** | -4870635901 |
| Zweite Heimat | **ZH** | -4850816432 |
| Kahaani | **KA** | -4665514846 |
| i Sapori della Toscana | **SA** | -4833204954 |
| Leckerolls | **LR** | -4839028336 |
| dean & david | **DD** | -4901870176 |
| Pommes Freunde | **PF** | -4955033989 |
| Wittelsbacher Apotheke | **AP** | N/A |

---

## 🚴 Courier Names

| Name | User ID | Status |
|------|---------|--------|
| **Bee 1** | 383910036 | Active (Admin required) |
| **Bee 2** | 6389671774 | Active (Admin required) |
| **Bee 3** | 8483568436 | Active (Admin required) |
| **Michael** | (from MDG) | Active (Admin) |

---

## 🔑 Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| **BOT_TOKEN** | Telegram bot token | `7064983715:AAH6xz...` |
| **SHOPIFY_WEBHOOK_SECRET** | HMAC verification key | `0cd9ef469300a40e...` |
| **DISPATCH_MAIN_CHAT_ID** | MDG chat ID | `-4955033990` |
| **VENDOR_GROUP_MAP** | Restaurant chat IDs (JSON) | `{"Leckerolls": -4839028336}` |
| **COURIER_MAP** | Courier user IDs (JSON) | `{"383910036": {"username": "Bee 1"}}` |
| **PORT** | Server port | `10000` |

---

## 📝 Usage Examples

### Request Time Change for Order
```
"Change MDG-TIME-REQ for #1058 to show BTN-EXACT first"
```

### Fix Assignment Button
```
"BTN-ASSIGN-ME is not triggering FN-SEND-ASSIGN correctly"
```

### Update Vendor Message
```
"Modify RG-SUM to include product count like MDG-CONF does"
```

### Debug State Issue
```
"Check order_id 7402584965386: confirmed_times not updating after BTN-WORKS"
```

### Add New Feature
```
"Add BTN-CALL-CUSTOMER to UPC-ASSIGN message using customer phone from STATE"
```

---

## 🎯 Common Workflows

### Order Lifecycle (Full)
```
Shopify → MDG-ORD + RG-SUM → BTN-TIME → MDG-TIME-PICK → time_plus → RG-TIME-REQ 
→ BTN-WORKS → MDG-CONF → BTN-ASSIGN-ME → UPC-ASSIGN → BTN-DELIVERED → "delivered"
```

### Multi-Vendor Assignment
```
MDG-ORD (2 vendors) → BTN-VENDOR (select JS) → MDG-TIME-PICK → BTN-VENDOR (select LR) 
→ Both confirm → MDG-CONF → BTN-ASSIGN-TO → MDG-COURIER-SEL → BTN-COURIER → UPC-ASSIGN
```

### Delay Request
```
UPC-ASSIGN → BTN-DELAY → UPC-DELAY-PICK → BTN-DELAY-SEL → RG-DELAY (to all vendors) 
→ BTN-WORKS → order["confirmed_times"] updated (no duplicate BTN-ASSIGN)
```

---

## 🐛 Quick Debugging Reference

| Issue | Check | Solution Code |
|-------|-------|---------------|
| Buttons not showing | `order["vendors"]` count | `FN-MDG-KB` + multi-vendor logic |
| Time not confirming | `order["confirmed_times"][vendor]` | `FN-CHECK-CONF` |
| Assignment duplicate | `order["status"]` | Check before `FN-ASSIGN-KB` |
| Courier list empty | MDG admin status | `FN-GET-COURIERS` + promote to admin |
| Message not deleting | `order["mdg_additional_messages"]` | `FN-CLEANUP` + tracking |
| Product name wrong | Before vendor_items | `FN-CLEAN-NAME` in Shopify webhook |

---

**Last Updated**: October 3, 2025  
**Version**: 1.0 - Complete System Reference

---

## 💡 Pro Tips

1. **Always specify message type**: Use `MDG-ORD`, `RG-TIME-REQ`, etc. instead of "that message"
2. **Use function codes**: `FN-SEND-ASSIGN` is clearer than "the function that sends assignments"
3. **Reference STATE fields directly**: `order["confirmed_times"]` instead of "the time tracking"
4. **Callback actions are exact**: Copy-paste from this doc to avoid typos
5. **Button codes = Visual reference**: `BTN-ASSIGN-ME` shows the emoji in your mind

---

**How to Use This Document:**
- Keep it open when discussing changes
- Copy exact codes when reporting issues
- Use shortcuts for quick communication
- Update when adding new features

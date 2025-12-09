# Phase 1A: main.py Deep Analysis

**File**: main.py
**Total Lines**: 4,529
**Purpose**: Flask app core - webhooks, callbacks, STATE management, event loop

---

## 📦 IMPORTS & DEPENDENCIES

**External Libraries**:
- Flask: Web server for webhooks
- telegram-python-bot: Telegram API
- Redis: State persistence (`redis_state.py`)
- OCR: Image text extraction (`ocr.py`)

**Internal Modules**:
- `mdg.py`: MDG message/keyboard builders
- `rg.py`: RG message/keyboard builders  
- `upc.py`: Courier assignment logic
- `utils.py`: Helpers, phone validation, product cleaning

---

## 🔧 CONFIGURATION

**Environment Variables** (lines 82-92):
```python
BOT_TOKEN = "7064983715:AAH6xz2p1QxP5h2EZMIp1Uw9pq57zUX3ikM"
SHOPIFY_WEBHOOK_SECRET = "0cd9ef469300a40e7a9c03646e4336a19c592bb60cae680f86b41074250e9666"
DISPATCH_MAIN_CHAT_ID = -4825320632
VENDOR_GROUP_MAP = {...}  # Restaurant chat IDs
DRIVERS = {...}  # Courier Telegram user IDs
PF_RG_CHAT_ID = -4955033989  # Pommes Freunde group
```

**Restaurant Shortcuts** (lines 103-114):
```python
RESTAURANT_SHORTCUTS = {
    "Julis Spätzlerei": "JS", "Zweite Heimat": "ZH", "Hello Burrito": "HB",
    "Kahaani": "KA", "i Sapori della Toscana": "SA", "Leckerolls": "LR",
    "dean & david": "DD", "Pommes Freunde": "PF", "Wittelsbacher Apotheke": "AP",
    "Safi": "SF"
}
```

---

## 💾 GLOBAL STATE

**STATE Dict** (line 129):
```python
STATE: Dict[str, Dict[str, Any]] = {}
```
- **Key**: `order_id` (Shopify ID or Smoothr code)
- **Value**: Order data with all fields (see STATE FIELDS section below)
- **In-memory**: Cleared on Render restart
- **Redis Backup**: Persisted via `save_state()` / `load_state()`

**RECENT_ORDERS List** (line 130):
```python
RECENT_ORDERS: List[Dict[str, Any]] = []
```
- Tracks last 50 orders for "same time as" feature
- Only confirmed orders from last 1 hour

---

## 🗂️ STATE FIELDS (Complete)

Every order in STATE contains:

### Core Identity
- `order_id`: Unique ID (Shopify/Smoothr)
- `name`: Order number ("dishbee #XX" or "26")
- `order_type`: "shopify" | "smoothr" | "smoothr_lieferando"

### Customer & Delivery
- `customer`: `{name: str, phone: str}`
- `address`: Full address string
- `phone`: Validated phone number
- `total`: Total amount (e.g., "18.50€")
- `note`: Order notes (optional)
- `tips`: Tip amount (float, optional)
- `is_pickup`: Boolean (Selbstabholung orders)
- `cash_on_delivery`: Boolean

### Vendor Data
- `vendors`: List of restaurant names ["Restaurant A", "Restaurant B"]
- `vendor_items`: `{"Restaurant": ["2 x Product", "1 x Product"]}`
- `vendor_expanded`: `{"Restaurant": False}` - RG expand/collapse state
- `requested_time`: Time sent to vendors ("14:30")
- `confirmed_times`: `{"Restaurant": "14:35"}` - Each vendor's confirmation

### Message Tracking
- `mdg_message_id`: Main MDG order message ID
- `rg_message_ids`: `{"Restaurant": 789}` - RG summary message IDs
- `mdg_additional_messages`: `[123, 456]` - Temporary messages (time pickers, etc.)

### Assignment & Status
- `assigned_to`: Courier user_id
- `status`: "new" | "assigned" | "delivered"
- `status_history`: `[{"type": "time_sent", "time": "14:30", "vendor": "JS", ...}]`

### Metadata
- `created_at`: Datetime string
- `original_address`: Full address for Google Maps links

### PF Lieferando Special
- `product_count`: Total items (used when vendor_items empty)
- `raw_ocr_text`: OCR output from photo

---

## 🌐 FLASK ROUTES

### 1. Health Check
**Route**: `GET /`
**Handler**: `health_check()` (line 1784)
**Returns**: `{"status": "ok", "orders_in_state": count}`

### 2. Smoothr Webhook
**Route**: `POST /smoothr`
**Handler**: `smoothr_webhook()` (line 1798)
**Flow**:
- Validates webhook secret
- Parses Smoothr JSON payload
- Calls `process_smoothr_order()`
- Returns 200

### 3. Telegram Webhook
**Route**: `POST /{BOT_TOKEN}`
**Handler**: `telegram_webhook()` (line 1909)
**Flow**:
- Receives Telegram updates
- Routes to callback handlers
- Processes commands
- Handles channel posts (PF photos)
- Returns empty response

### 4. Shopify Webhook
**Route**: `POST /webhooks/shopify`
**Handler**: `shopify_webhook()` (line 4270)
**Flow**:
- Validates HMAC signature
- Parses Shopify JSON payload
- Calls `process_shopify_webhook()`
- Returns 200

---

## 🎯 CALLBACK ACTIONS (55 total)

**Format**: `action|order_id|params|timestamp`

### MDG Time Requests (14 actions)
- `req_vendor`: Select vendor for multi-vendor orders
- `req_asap`: Request ASAP time
- `req_time`: Show time options menu
- `req_scheduled`: Schedule for later
- `req_same`: Show "same time as" options
- `req_exact`: Show exact time picker
- `time_plus`: Quick time buttons (+5, +10, +15, +20 min)
- `order_ref`: Show recent order references
- `time_same`: Select exact order to copy time
- `time_relative`: Add relative time (e.g., same+10min)
- `same_selected`: Confirm "same as" selection
- `exact_hour`: Hour selection in time picker
- `exact_selected`: Confirm exact time
- `exact_back_hours`: Back to hour selection

### Vendor-Specific Time (5 actions)
- `vendor_asap`: Vendor ASAP request
- `vendor_time`: Vendor time menu
- `vendor_same`: Vendor "same as" menu
- `vendor_exact`: Vendor exact time picker
- `vendor_exact_time`, `vendor_exact_hour`, `vendor_exact_selected`, `vendor_exact_back`: Vendor time picker flow

### RG Responses (8 actions)
- `toggle`: Expand/collapse RG message
- `works`: Restaurant confirms time works
- `later`: Restaurant requests later time
- `later_time`: Select later time option
- `prepare`: Restaurant needs preparation time
- `prepare_time`: Select preparation time
- `wrong`: Something wrong menu
- `wrong_unavailable`, `wrong_canceled`, `wrong_delay`, `delay_time`: Problem handling

### MDG Display (3 actions)
- `mdg_toggle`: Expand/collapse MDG message
- `hide`: Hide temporary message
- `close_temp`: Close temporary message

### Courier Assignment (7 actions)
- `assign_myself`: Assign order to self
- `assign_to_menu`: Show courier selection menu
- `assign_to_user`: Assign to specific courier
- `show_assigned`: Show assigned orders
- `unassign_order`: Unassign order

### UPC (User Private Chat) (8 actions)
- `confirm_delivered`: Mark order delivered
- `undeliver_order`: Unmark delivery
- `combine_with`: Combine orders
- `show_problem_menu`: Show problem menu
- `delay_order`: Report delay
- `delay_vendor_selected`, `delay_selected`: Delay flow
- `call_restaurant`, `select_restaurant`, `call_vendor`, `call_vendor_menu`: Restaurant calling

### Utility (2 actions)
- `smart_time`: Smart time suggestion
- `no_recent`: No recent orders message

---

## 📝 KEY FUNCTIONS

### Core Helpers (lines 43-322)

**`now()`** (line 43):
- Returns current time in Europe/Berlin timezone
- Used for all timestamps

**`save_state()` / `load_state()`** (lines 140-174):
- Redis persistence for STATE dict
- Called after critical state changes
- Loads on startup

**`verify_webhook()`** (line 226):
- HMAC-SHA256 validation for Shopify webhooks
- Prevents unauthorized webhook calls

**`fmt_address()`** (line 239):
- Formats Shopify address dict to string
- Excludes city (per project requirements)

**`safe_send_message()` / `safe_edit_message()` / `safe_delete_message()`** (lines 257-299):
- Async wrappers with retry logic
- Handle Telegram API errors gracefully
- Exponential backoff for rate limits

**`send_status_message()`** (line 301):
- Temporary message with auto-delete
- Default 20 seconds lifetime
- Used for status updates

**`build_assignment_confirmation_message()`** (line 330):
- Formats MDG-CONF message after vendor confirmations
- Shows confirmed times and product counts
- Triggers courier assignment buttons

### Command Handlers (lines 460-1210)

**`handle_scheduled_command()`** (line 460):
- MDG command: `/scheduled`
- Shows all orders with confirmed times (not delivered)

**`handle_assigned_command()`** (line 486):
- MDG command: `/assigned`
- Shows all assigned orders (not delivered)

**Test Commands** (lines 516-1210):
- `handle_test_smoothr_command()`: /testsmoothr, /testsmoothrdd
- `handle_test_shopify_command()`: /testshopify, /testmulti
- `handle_test_pf_command()`: /testpf (with OCR)
- `handle_test_vendor_command()`: /testjs, /testzh, /testhb, etc.

### Order Processing (lines 1212-1648)

**`process_shopify_webhook()`** (line 1212):
1. Parse Shopify JSON payload
2. Extract customer, address, items, payment
3. Detect pickup orders (Selbstabholung)
4. Group items by vendor
5. Clean product names
6. Populate STATE
7. Send to MDG + RG simultaneously
8. Save state to Redis

**`process_smoothr_order()`** (line 1401):
1. Parse Smoothr JSON (Uber Eats, etc.)
2. Extract customer, address, items
3. Single vendor only
4. Populate STATE (same structure as Shopify)
5. Send to MDG + RG
6. Save state

**`handle_pf_photo()`** (line 1512):
1. Receive photo from PF Lieferando channel
2. Download photo
3. OCR extract text
4. Parse order data (name, address, total, items)
5. Populate STATE
6. Send to MDG + PF RG
7. Delete original photo message
8. Save state

### Message Management (lines 1649-1782)

**`cleanup_mdg_messages()`** (line 1649):
- Deletes temporary messages (time pickers, menus)
- Preserves main order message
- Uses `mdg_additional_messages` list

**`forward_restaurant_message_to_mdg()`** (line 1688):
- Forwards RG text messages to MDG
- Tracks message IDs for reply functionality

**`forward_mdg_reply_to_restaurant()`** (line 1731):
- Routes MDG replies back to correct RG
- Uses `RESTAURANT_FORWARDED_MESSAGES` dict

---

## 🔄 TELEGRAM WEBHOOK HANDLER

**Function**: `telegram_webhook()` (lines 1909-4268)
**Size**: 2,359 lines (52% of file!)

**Flow**:
1. Parse incoming update
2. Extract callback_query or message or channel_post
3. Route to appropriate handler:
   - **Callback Query**: Parse action, execute handler (55 action types)
   - **Message/Command**: Execute command handler (/scheduled, /assigned, test commands)
   - **Channel Post**: Handle PF photo uploads
   - **Replies in RG**: Forward to MDG
   - **Replies in MDG**: Forward to RG

**Callback Routing Logic**:
```python
if action == "req_vendor":
    # Multi-vendor time request
elif action == "vendor_asap":
    # Vendor ASAP request
elif action == "works":
    # Vendor confirms time
...
# 55 elif branches total
```

---

## 📊 STATE TRANSITIONS

**Order Lifecycle**:
```
1. Order Created (new)
   ├─ Shopify webhook → process_shopify_webhook()
   ├─ Smoothr webhook → process_smoothr_order()
   └─ PF photo → handle_pf_photo()
   
2. Time Requested
   └─ STATUS: time_sent added to status_history
   
3. Vendor Confirms
   ├─ confirmed_times[vendor] = "HH:MM"
   └─ STATUS: time_confirmed added to status_history
   
4. All Vendors Confirmed
   ├─ Build MDG-CONF message
   ├─ Show assignment buttons
   └─ STATUS: ready for assignment
   
5. Assigned (assigned)
   ├─ assigned_to = user_id
   ├─ Send UPC message to courier
   ├─ Update MDG status line
   └─ STATUS: assignment added to status_history
   
6. Delivered (delivered)
   ├─ Update MDG status line (✅ Delivered)
   ├─ Update UPC message
   └─ STATUS: delivery added to status_history
```

---

## 🎨 MESSAGE TYPES SENT

**From main.py directly**:

1. **MDG-ORD** (Order Arrival):
   - Built by: `mdg.build_mdg_dispatch_text()`
   - Sent at: Order creation
   - Keyboard: `mdg.mdg_initial_keyboard()`

2. **RG-SUM** (Restaurant Summary):
   - Built by: `rg.build_vendor_summary_text()`
   - Sent at: Order creation
   - Keyboard: Expand/collapse + vendor response

3. **MDG-CONF** (Assignment Confirmation):
   - Built by: `build_assignment_confirmation_message()`
   - Sent at: All vendors confirmed
   - Keyboard: Assignment buttons

4. **UPC-ASSIGN** (Courier Assignment):
   - Built by: `upc` module functions
   - Sent at: Order assigned
   - Keyboard: CTA buttons (call, navigate, delivered)

5. **MDG Status Updates**:
   - Time requested, confirmed, assigned, delivered
   - Edit main MDG message with status line
   - Built by: `utils.build_status_lines()`

6. **Temporary Messages**:
   - Time pickers, menus, confirmations
   - Auto-deleted after selection
   - Tracked in `mdg_additional_messages`

---

## 🔐 SECURITY

**HMAC Validation** (line 226):
- Shopify webhooks verified with HMAC-SHA256
- Secret: `SHOPIFY_WEBHOOK_SECRET`
- Prevents unauthorized order creation

**Smoothr Validation** (line 1798):
- Header-based secret validation
- Secret: `SMOOTHR_WEBHOOK_SECRET`

**Spam Detection** (lines 1918-1927):
- Rejects messages containing "FOXY", "airdrop", "t.me/" links
- Prevents bot spam in groups

---

## 🚨 CRITICAL PATTERNS

### 1. Async/Await Pattern
- All Telegram API calls use `safe_send_message()` / `safe_edit_message()`
- Flask handlers call `run_async(coro)` to schedule background work
- Event loop runs in dedicated thread

### 2. STATE Access
- Always check `order_id in STATE` before accessing
- Multi-vendor branching: `if len(order["vendors"]) > 1`
- Redis save after critical changes

### 3. Message Cleanup
- Temporary messages added to `mdg_additional_messages`
- Call `cleanup_mdg_messages(order_id)` after workflow completes
- Prevents chat clutter

### 4. Vendor Branching
```python
if len(vendors) > 1:
    # Multi-vendor: show vendor selection buttons
else:
    # Single-vendor: show ASAP/TIME buttons directly
```

### 5. Callback Data Format
- Always includes timestamp: `action|order_id|params|{timestamp}`
- Prevents stale button clicks
- Parse with: `data.split("|")`

---

## 📈 STATS

- **Total Functions**: 31
- **Flask Routes**: 4
- **Callback Actions**: 55
- **Commands**: 10+ (test commands)
- **Largest Function**: `telegram_webhook()` (2,359 lines)
- **Critical Sections**:
  - Callback routing: Lines 1909-4268 (52% of file)
  - Order processing: Lines 1212-1648
  - State management: Lines 129-174

---

## ✅ PHASE 1A COMPLETE

**Next**: Phase 1B - utils.py analysis

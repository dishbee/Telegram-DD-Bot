# Telegram Dispatch Bot – AI Agent Instructions

## ⚠️ CRITICAL: Working with Non-Technical User

**User Context**: User is NOT a coder and cannot fix anything. Paid for professional AI assistance and expects production-quality results.

### Communication Rules (MANDATORY)

**ALWAYS DO**:
- ✅ Ask for confirmation before making ANY code changes
- ✅ Make surgical changes - touch ONLY what needs fixing
- ✅ Test each change individually before moving to next
- ✅ Check every line against original requirements
- ✅ Explain exactly what will change and why

**NEVER DO**:
- ❌ NO assumptions - verify everything against assignment
- ❌ NO rewriting working code
- ❌ NO "let me also improve this while I'm here"
- ❌ NO bundling multiple changes together
- ❌ NO asking what user prefers - execute the given task
- ❌ NO breaking existing working functionality
- ❌ NO providing partial or incomplete code

### Established Failure Patterns to Avoid

Historical issues that have caused production failures:
1. Breaking working vendor detection (happened multiple times)
2. Changing working button logic unnecessarily (caused multiple failures)
3. Adding unnecessary complexity (order grouping caused deployment failures)
4. Introducing syntax errors (missing brackets, indentation issues)
5. Assuming functions exist (missing handlers broke functionality)
6. Making changes without user confirmation (caused frustration)

### Development Approach

**Implementation Pattern**:
1. **Analyze**: What exactly needs to change
2. **Propose**: Specific changes with expected outcome
3. **Confirm**: Get user approval before proceeding
4. **Implement**: Complete working solution
5. **Verify**: Ensure fix works without breaking other things

**Mindset**: Respect working code - don't "improve" what isn't broken. Quality over speed. When in doubt, ask for clarification rather than assume.

## Architecture Overview

Flask webhook service orchestrating multi-channel Telegram order dispatch for food delivery. Three communication surfaces handle the full order lifecycle:

- **MDG** (Main Dispatch Group): Order arrival, time requests, status updates, courier assignment
- **RG** (Restaurant Groups): Vendor-specific order details, time negotiation, response handling  
- **UPC** (User Private Chats): Courier assignment messages with CTA buttons (call, navigate, delivery confirmation)

**Core Flow**: Shopify webhook → MDG + RG simultaneously → time negotiation → vendor confirmation → courier assignment → delivery → completion

**Production Deployment**: Render (https://telegram-dd-bot.onrender.com) - Python 3.10.13 with Gunicorn

## State Management (CRITICAL)

- **`STATE` dict** (`main.py`): Single source of truth for all orders, keyed by `order_id` (Shopify order ID)
- **In-memory only**: No database persistence; Render restarts clear all state
- **`RECENT_ORDERS` list**: Tracks last 50 orders for "same time as" feature (max 1 hour old, confirmed times only)

### Critical `STATE` Fields Per Order

```python
{
    "order_id": {
        "name": "order_number",
        "vendors": ["Restaurant Name"],  # List of vendor names
        "mdg_message_id": 123456,  # Main dispatch message ID
        "vendor_messages": {"Restaurant": 789},  # vendor → message_id mapping
        "vendor_expanded": {"Restaurant": False},  # Toggle state for details
        "requested_time": "14:30",  # Time requested from vendors
        "confirmed_time": "14:35",  # Time confirmed by vendor
        "mdg_additional_messages": [123, 456],  # Temporary messages for cleanup
        "assigned_to": user_id,  # Courier assignment
        "status": "new|assigned|delivered"
    }
}
```

## Module Boundaries

- **`main.py`**: Flask app, webhook handlers (`/webhooks/shopify`, `/{BOT_TOKEN}`), callback routing, event loop management
- **`mdg.py`**: MDG message builders, keyboard factories, time logic (smart suggestions, "same as" feature)
- **`rg.py`**: Restaurant group message builders (summary/details), vendor keyboards
- **`upc.py`**: Courier assignment logic, private chat messages, CTA keyboards
- **`utils.py`**: Async wrappers (`safe_send_message`, `safe_edit_message`, `safe_delete_message`), phone validation, HMAC verification

## Critical Async Patterns

### Event Loop Management
- All Telegram API calls **MUST** use async/await
- Flask webhook handlers call `run_async(coro)` to schedule async work in background thread
- Dedicated event loop runs in `loop_thread` (started in `if __name__ == "__main__"`)
- **Never call `bot.send_message()` directly** – always use `safe_send_message()` (built-in retry + logging)

### Message Cleanup Pattern
```python
# Temporary messages (time pickers, confirmations) MUST be tracked
order["mdg_additional_messages"].append(msg.message_id)

# After user completes action, cleanup temporary messages
await cleanup_mdg_messages(order_id)
```

## Callback Data Protocol

Pipe-delimited format: `action|order_id|param1|...|timestamp`

**Key Actions**:
- MDG time requests: `req_asap`, `req_time`, `time_plus|{order_id}|{minutes}`, `req_same`, `req_exact`
- Vendor-specific: `req_vendor|{order_id}|{vendor}`, `vendor_asap|{order_id}|{vendor}`, `vendor_time|{order_id}|{vendor}`
- Time pickers: `exact_hour|{order_id}|{hour}`, `exact_selected|{order_id}|{time}`
- Restaurant responses: `toggle|{order_id}|{vendor}`, `works|{order_id}|{vendor}`, `wrong_delay|{order_id}|{vendor}`
- Courier actions: `assign_me`, `confirm_delivered`, `delay_order`, `call_restaurant`

## Multi-Vendor vs Single-Vendor Logic

**Branch on `len(order["vendors"])`**:

- **Multi-vendor** (>1): MDG shows vendor selection buttons first → each vendor gets individual time request
- **Single-vendor** (1): MDG shows ASAP/TIME buttons directly → all vendors get same time request

Example from `main.py`:
```python
if len(vendors) > 1:
    # Show vendor selection buttons
    return InlineKeyboardMarkup([[InlineKeyboardButton(
        f"Request {RESTAURANT_SHORTCUTS.get(vendor)}",
        callback_data=f"req_vendor|{order_id}|{vendor}"
    )] for vendor in vendors])
else:
    # Show ASAP/TIME buttons
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Request ASAP", callback_data=f"req_asap|{order_id}"),
        InlineKeyboardButton("Request TIME", callback_data=f"req_time|{order_id}")
    ]])
```

## Environment Variables

```bash
BOT_TOKEN                 # Telegram bot token: 7064983715:AAH6xz2p1QxP5h2EZMIp1Uw9pq57zUX3ikM
SHOPIFY_WEBHOOK_SECRET    # HMAC validation: 0cd9ef469300a40e7a9c03646e4336a19c592bb60cae680f86b41074250e9666
DISPATCH_MAIN_CHAT_ID     # MDG chat ID: -4955033990
VENDOR_GROUP_MAP          # JSON: {"Pommes Freunde": -4955033989, "Zweite Heimat": -4850816432, "Julis Spätzlerei": -4870635901, "i Sapori della Toscana": -4833204954, "Kahaani": -4665514846, "Leckerolls": -4839028336, "dean & david": -4901870176}
DRIVERS                   # JSON: {"Bee 1": 383910036, "Bee 2": 6389671774, "Bee 3": 8483568436}
COURIER_MAP               # Same as DRIVERS (newer convention)
PORT                      # Default: 10000
```

**Note**: These are production values. Keep synchronized across Render dashboard and local `.env` file.

## Local Development Workflow

```powershell
# PowerShell environment setup
$env:BOT_TOKEN = "your_token"
$env:SHOPIFY_WEBHOOK_SECRET = "your_secret"
$env:DISPATCH_MAIN_CHAT_ID = "-1001234567890"
$env:VENDOR_GROUP_MAP = '{"Restaurant A": -1001234567890}'
$env:COURIER_MAP = '{"123456789": {"username": "courier1", "is_courier": true}}'

# Run Flask app
python main.py

# In separate terminal: ngrok for webhook testing
ngrok http 10000
```

**Register webhooks**:
- Telegram: `https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url=https://{ngrok_url}/{BOT_TOKEN}`
- Shopify: Admin → Settings → Notifications → Webhooks → `https://{ngrok_url}/webhooks/shopify`

## Adding New Callback Actions

1. Define callback data format in keyboard factory (`mdg.py`, `rg.py`, `upc.py`)
2. Add handler branch in `main.py` `telegram_webhook()`:
   ```python
   elif action == "new_action":
       order_id = data[1]
       order = STATE.get(order_id)
       # Process action
       await cleanup_mdg_messages(order_id)  # If workflow completes
   ```
3. Update `order` state fields as needed
4. Edit MDG/RG messages via `safe_edit_message()` to reflect new state

## Project-Specific Conventions

### Restaurant Shortcuts
```python
RESTAURANT_SHORTCUTS = {
    "Julis Spätzlerei": "JS", "Zweite Heimat": "ZH", "Kahaani": "KA",
    "i Sapori della Toscana": "SA", "Leckerolls": "LR", "dean & david": "DD",
    "Pommes Freunde": "PF", "Wittelsbacher Apotheke": "AP"
}
```
Keep synced across `main.py`, `mdg.py`, and environment variables.

### Address Formatting
- `fmt_address()` excludes city (per project requirements): `"Street 123, 80333"` not `"Street 123, Munich 80333"`
- `original_address` field preserved for Google Maps links: `https://www.google.com/maps?q={original_address}`

### Phone Validation
`validate_phone()` checks multiple Shopify fields in order:
1. `customer.phone`
2. `billing_address.phone`  
3. `shipping_address.phone`

Returns `None` if invalid (< 7 digits) or missing.

### Payment Detection
Cash-on-delivery detected via:
1. `payment_gateway_names` contains "cash" AND "delivery"
2. Fallback: transaction gateway analysis

Affects MDG message formatting (shows "❕ Cash on delivery: {total}€").

### Pickup Orders
Detected by "Abholung" in Shopify payload (case-insensitive). Special handling:
- MDG header: `**Order for Selbstabholung**`
- Footer: `Please call the customer and arrange pickup time: {phone}`

### Vendor Message Expansion
- RG messages start collapsed (`build_vendor_summary_text`)
- "Details ▸" button shows full details (`build_vendor_details_text`)
- "◂ Hide" button collapses back
- State tracked in `order["vendor_expanded"][vendor]`

### Time Features
- **"Same time as"**: Shows last 10 confirmed orders from last 1 hour (filtered by vendor if applicable)
- **Smart suggestions**: If same vendor has recent confirmed order, shows +5/+10/+15/+20 buttons relative to that time
- **Exact time picker**: Hours from current hour to midnight, minutes in 3-minute intervals

## Error Handling & Recovery

### Telegram API Errors

**Rate Limits (429 Too Many Requests)**:
- Telegram enforces rate limits: ~30 messages/second to same chat, ~1 message/second to different chats
- `safe_send_message()` includes built-in retry with exponential backoff (max 3 attempts)
- If rate limited, bot automatically retries after 2^attempt seconds
- **Prevention**: Batch operations when possible, avoid rapid sequential sends to same chat

**Network Errors (TimedOut, NetworkError)**:
- Handled by `safe_send_message()` / `safe_edit_message()` retry logic
- Check logs for `"Send message attempt X failed"` entries
- If persistent: verify BOT_TOKEN validity and network connectivity

**Message Not Modified (400)**:
- Occurs when editing message with identical content
- Safe to ignore - message already in desired state
- Wrapped in try/catch in `safe_edit_message()`

**Message to Edit Not Found (400)**:
- Happens if message was manually deleted or bot lost track of message_id
- Check `order["mdg_message_id"]` and `order["vendor_messages"]` populated correctly
- Recovery: Send new message instead of editing

### Shopify Webhook Errors

**HMAC Verification Failure**:
- Returns 401 Unauthorized
- Check `SHOPIFY_WEBHOOK_SECRET` matches Shopify admin settings
- Log shows: `"HMAC verification error"`
- Verify webhook is sent from Shopify (not replay tool with wrong secret)

**Malformed Payload**:
- Missing required fields (e.g., `customer`, `line_items`, `shipping_address`)
- Use defensive `.get()` calls with defaults: `payload.get("customer") or {}`
- Log error and return 500 to trigger Shopify retry

**Webhook Replay/Duplication**:
- Shopify may retry failed webhooks
- Check if `order_id` already in `STATE` before processing
- Current implementation overwrites; consider adding duplicate detection

### State Corruption

**Order Missing from STATE**:
- Symptom: Callback handler can't find `order_id`
- Cause: Server restart (in-memory state cleared), or order never processed
- Recovery: Log warning, return early from callback handler
- Prevention: Consider persisting critical state to Redis/database

**Message ID Mismatch**:
- Symptom: Edit/delete operations fail
- Check: `order["mdg_message_id"]` matches actual Telegram message
- Recovery: Send new message, update STATE with new ID

**Orphaned Messages**:
- Temporary messages in `mdg_additional_messages` not cleaned up
- Symptom: Chat cluttered with old time pickers
- Fix: Call `cleanup_mdg_messages(order_id)` after every workflow completion
- Manual cleanup: Delete messages via Telegram UI

### Event Loop Issues

**"Event loop is closed" Error**:
- Cause: Attempting async operation after Flask shutdown
- Prevention: Ensure `loop_thread` daemon=True (already set)
- Don't call async operations in Flask teardown handlers

**"coroutine was never awaited" Warning**:
- Cause: Forgot to `await` async function or use `run_async()`
- Fix: Wrap with `run_async(coro)` in Flask webhook handlers

### Production-Specific Issues

**Gunicorn Worker Timeout**:
- Default timeout: 30 seconds
- Long-running webhooks may timeout
- Solution: Increase timeout in Procfile: `web: gunicorn --timeout 60 main:app`
- Or: Use `run_async()` to offload work to background thread

**Memory Leaks**:
- `STATE` grows unbounded (50 orders tracked in `RECENT_ORDERS`, but all orders stay in `STATE`)
- Monitor via health check: `GET /` shows `orders_in_state`
- Consider periodic cleanup of delivered orders older than 24h

**Render Cold Starts**:
- Free tier: Render spins down after 15min inactivity
- First webhook after spindown takes ~30s to respond
- Shopify may mark webhook as failed and retry
- Upgrade to paid tier for always-on instances

## Debugging

- **Health check**: `GET /` returns `{"orders_in_state": N}`
- **State inspection**: Log `STATE[order_id]` contents before state transitions
- **Verify message IDs**: Check `mdg_message_id` and `vendor_messages` populated after Shopify webhook
- **Spam detection**: All incoming messages logged with user info (watch for "FOXY", "airdrop", "t.me/" patterns)
- **Verbose logging**: All incoming updates logged with full metadata (update_id, chat_id, user_id, message text)

## Common Gotchas

- **Callback answering**: `answerCallbackQuery` called synchronously via requests library (not async) to prevent timeout
- **Message cleanup**: Forgetting `cleanup_mdg_messages()` causes MDG chat clutter
- **Multi-vendor branching**: Always check `len(order["vendors"])` before building keyboards
- **No tests**: Manual validation via Telegram sandbox + Shopify webhook replay only
- **Production deployment**: Render uses Gunicorn (`Procfile: web: gunicorn main:app`), Python 3.10.13 (`runtime.txt`)

## Dependencies

```
python-telegram-bot[webhooks]==21.6
Flask==3.0.3
requests==2.32.3
```

Deploy command: `gunicorn main:app` (PORT auto-set by Render)

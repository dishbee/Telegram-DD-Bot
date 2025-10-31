# Restaurant Communication Feature

## Overview
Two-way communication system between restaurants and MDG (Main Dispatching Group) for manual messages outside of order workflow.

## Features

### 1. Restaurant → MDG (Auto-forward)
When a restaurant account writes a manual message in their RG (Restaurant Group), it's automatically forwarded to MDG.

**Format**: `"Zweite Heimat says: [message text]"`

**Requirements**:
- Message must be from a restaurant account (user_id in `RESTAURANT_ACCOUNTS`)
- Message must be manual text (not bot-generated)
- Message must NOT be a callback button interaction

**Auto-delete**: Message auto-deletes from MDG after 10 minutes

### 2. MDG → Restaurant (Reply function)
When someone in MDG uses Telegram's "Reply" feature on a forwarded restaurant message, the reply is sent back to the original restaurant group.

**Format**: `"Bee 1 says: [reply text]"`

**Name Resolution**:
1. First tries to find user in `COURIER_MAP` (DRIVERS)
2. Falls back to user's first_name if not found

**Auto-delete**: Reply message auto-deletes from RG after 10 minutes

## Implementation Details

### State Management

#### RESTAURANT_ACCOUNTS (Placeholder)
```python
RESTAURANT_ACCOUNTS: Dict[str, int] = json.loads(os.environ.get("RESTAURANT_ACCOUNTS", "{}"))
# Format: {"Restaurant Name": user_id}
# Example: {"Zweite Heimat": 123456789, "Julis Spätzlerei": 987654321}
```

This is a **placeholder** for future implementation when restaurant Telegram accounts are created.

#### RESTAURANT_FORWARDED_MESSAGES (Tracking)
```python
RESTAURANT_FORWARDED_MESSAGES: Dict[int, Dict[str, Any]] = {}
# Format: {
#     mdg_message_id: {
#         "vendor": "Restaurant Name",
#         "rg_chat_id": -1234567890,
#         "original_msg_id": 456
#     }
# }
```

Tracks forwarded messages to enable reply functionality. When someone replies to a forwarded message in MDG, the system looks up which RG to send the reply to.

### Functions

#### `forward_restaurant_message_to_mdg()`
```python
async def forward_restaurant_message_to_mdg(
    vendor_name: str,
    message_text: str,
    rg_chat_id: int,
    original_msg_id: int
)
```

**Process**:
1. Format message: `"{vendor_name} says: {message_text}"`
2. Send to MDG using `safe_send_message()`
3. Track MDG message ID in `RESTAURANT_FORWARDED_MESSAGES`
4. Wait 10 minutes (600 seconds)
5. Delete message from MDG
6. Clean up tracking dict

#### `forward_mdg_reply_to_restaurant()`
```python
async def forward_mdg_reply_to_restaurant(
    from_user: Dict[str, Any],
    reply_text: str,
    replied_to_msg_id: int
)
```

**Process**:
1. Look up restaurant info from `RESTAURANT_FORWARDED_MESSAGES`
2. Resolve user name from `COURIER_MAP` or use first_name
3. Format message: `"{courier_name} says: {reply_text}"`
4. Send to restaurant group using `safe_send_message()`
5. Wait 10 minutes (600 seconds)
6. Delete message from RG

### Webhook Integration

#### Detection Logic (in `telegram_webhook()`)

**Restaurant → MDG**:
```python
if text and chat_id in VENDOR_GROUP_MAP.values():
    # Find vendor name
    vendor_name = ...
    
    # Check if from restaurant account
    user_id = from_user.get('id')
    if user_id in RESTAURANT_ACCOUNTS.values() and not from_user.get('is_bot', False):
        run_async(forward_restaurant_message_to_mdg(vendor_name, text, chat_id, msg.get('message_id')))
```

**MDG → Restaurant**:
```python
if chat_id == DISPATCH_MAIN_CHAT_ID and msg.get('reply_to_message') and text:
    replied_to_msg_id = msg['reply_to_message']['message_id']
    if replied_to_msg_id in RESTAURANT_FORWARDED_MESSAGES:
        run_async(forward_mdg_reply_to_restaurant(from_user, text, replied_to_msg_id))
```

## Usage Example

### Scenario 1: Restaurant sends message
1. Restaurant account writes in their RG: "We're running low on tomatoes today"
2. Bot detects message from restaurant account
3. Bot forwards to MDG: "Zweite Heimat says: We're running low on tomatoes today"
4. Message appears in MDG for 10 minutes, then auto-deletes

### Scenario 2: MDG replies
1. Courier clicks "Reply" on the restaurant message in MDG
2. Courier writes: "Okay, noted. Should we avoid tomato dishes?"
3. Bot detects reply to tracked message
4. Bot forwards to Zweite Heimat RG: "Bee 1 says: Okay, noted. Should we avoid tomato dishes?"
5. Message appears in RG for 10 minutes, then auto-deletes

## Configuration

To enable this feature, add restaurant accounts to environment variables:

```bash
RESTAURANT_ACCOUNTS='{"Zweite Heimat": 123456789, "Julis Spätzlerei": 987654321}'
```

Replace the user_id values with actual Telegram user IDs of restaurant accounts.

## Notes

- Messages only work for **manual text messages** from restaurant accounts
- Does NOT apply to bot-generated messages or button interactions
- Auto-delete ensures chat stays clean (10 minute lifetime)
- Reply tracking is in-memory only (cleared on bot restart)
- Restaurant accounts must be configured in environment variables to work

# Telegram Dispatch Bot – Copilot Instructions

## User Context
User is NOT a coder. Expects production-quality results. **LIVE ENVIRONMENT** - breaking things NOT acceptable.

## Rules
**DO**: Ask confirmation before changes · Surgical edits only · Trace code flow · Read actual code
**DON'T**: Assume · Rewrite working code · Bundle changes · Hallucinate formats · Move functions between modules

## Common Failures
Breaking vendor detection/buttons · Syntax errors · Not tracing code flow · Reading broken code vs user spec · Typos (`+=` vs `=`) · Changing signatures without updating callers

## Pattern
1. Analyze 2. Propose 3. Confirm 4. Implement 5. Verify

## Architecture
Flask webhook service for Telegram order dispatch. **MDG** (Main Dispatch), **RG** (Restaurant Groups), **UPC** (User Private Chats). Flow: Shopify→MDG+RG→time negotiation→confirmation→courier→delivery. Deploy: Render, Python 3.10.13, Gunicorn.

## State
**`STATE` dict** (main.py): Single source of truth, keyed by order_id. In-memory only. Key fields: name, vendors[], mdg_message_id, vendor_messages{}, vendor_expanded{}, requested_time, confirmed_time, mdg_additional_messages[], assigned_to, status.

## Modules
**main.py**: Flask, webhooks, callbacks, event loop
**mdg.py**: MDG messages, keyboards, time logic
**rg.py**: RG messages (summary/details), vendor keyboards
**upc.py**: Courier assignment, private chat messages
**utils.py**: Async wrappers (safe_send/edit/delete_message), phone validation

## Async Pattern
All Telegram API calls use async/await. Flask handlers call `run_async(coro)`. Always use `safe_send_message()` (retry+logging). Temp messages tracked in `mdg_additional_messages[]`, cleaned via `cleanup_mdg_messages(order_id)`.

## Callbacks
Format: `action|order_id|params|timestamp`. Examples: `req_asap`, `req_time`, `time_plus|{id}|{min}`, `req_vendor|{id}|{vendor}`, `works|{id}|{vendor}`, `assign_me`.

## Multi-vendor Logic
Branch on `len(order["vendors"])`: >1 = show vendor selection → individual time requests. =1 = show ASAP/TIME directly.

## Environment
```
BOT_TOKEN=7064983715:AAH6xz2p1QxP5h2EZMIp1Uw9pq57zUX3ikM
DISPATCH_MAIN_CHAT_ID=-4825320632
VENDOR_GROUP_MAP={"Pommes Freunde":-4955033989,"Zweite Heimat":-4850816432,...}
DRIVERS={"Bee 1":383910036,...}
```

## Recent Additions
**Assignment System** (upc.py): Live courier detection via `get_chat_administrators()`, fallback to COURIER_MAP. Buttons: "Assign to myself"/"Assign to...". Private chat with CTA buttons. Duplicate prevention via status check.

**Product Name Cleaning** (utils.py): 17 rules remove burger prefixes, extract quoted text, simplify fries/pizza/pasta names, remove prices.

**Assignment Confirmation** (main.py): Vendor shortcuts in header, confirmed times + product counts per vendor.

**Message Cleanup**: Tracks temp messages in `mdg_additional_messages[]`, cleans up time pickers/menus, preserves original order message, 3-attempt retry.

## Dependencies
python-telegram-bot[webhooks]==21.6, Flask==3.0.3, requests==2.32.3. Deploy: `gunicorn main:app`.

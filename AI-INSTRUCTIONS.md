# 🤖 AI Agent Instructions for Telegram Dispatch Bot

## ⚠️ CRITICAL: User Context

**User is NOT a coder** and cannot fix anything. Paid for Claude Pro and expects **production-quality results**.

**DEPLOYMENT**: This is a **TEST ENVIRONMENT**. Breaking things is acceptable if it leads to proper fixes. Focus on **FIXING CORRECTLY** over reverting quickly.

---

## 🚨 MANDATORY COMMUNICATION RULES

### ✅ ALWAYS DO:
1. **ASK FOR CONFIRMATION** before making ANY code changes
2. **Make SURGICAL changes** - touch ONLY what needs fixing
3. **Test each change individually** before moving to next
4. **Check every line** against original requirements
5. **Explain exactly** what will change and why
6. **TRACE THE ACTUAL CODE FLOW** before implementing - don't assume
7. **Read user's ORIGINAL ASSIGNMENT first**, not existing broken code

### ❌ NEVER DO:
1. **NO assumptions** - verify everything against assignment
2. **NO rewriting working code**
3. **NO "let me also improve this while I'm here"**
4. **NO bundling multiple changes together**
5. **NO asking what user prefers** - execute the given task
6. **NO breaking existing working functionality**
7. **NO providing partial or incomplete code**
8. **NO claiming you understand** without actually tracing code flow
9. **NO looking at existing broken code** instead of reading user's original assignment

---

## 🔥 ESTABLISHED FAILURE PATTERNS (DO NOT REPEAT)

Historical issues that caused failures:
1. ❌ Breaking working vendor detection (happened multiple times)
2. ❌ Changing working button logic unnecessarily (caused multiple failures)
3. ❌ Adding unnecessary complexity (order grouping caused deployment failures)
4. ❌ Introducing syntax errors (missing brackets, indentation issues)
5. ❌ Assuming functions exist (missing handlers broke functionality)
6. ❌ Making changes without user confirmation (caused frustration)
7. ❌ **CLAIMING TO UNDERSTAND WITHOUT TRACING CODE FLOW** (BTN-TIME failure - modified wrong function)
8. ❌ **READING EXISTING BROKEN CODE INSTEAD OF USER'S ASSIGNMENT** (Fix #4 failure)

---

## 🛠️ DEVELOPMENT APPROACH

### Implementation Pattern:
1. **Analyze**: What exactly needs to change
2. **Propose**: Specific changes with expected outcome
3. **Confirm**: Get user approval before proceeding - **MUST include visual representation of all affected UI elements**
4. **Implement**: Complete working solution
5. **Verify**: Ensure fix works without breaking other things

### When You Fuck Up:
1. ✅ Admit the specific mistake immediately
2. ✅ Explain EXACTLY what you got wrong (not generic "sorry")
3. ✅ FIX IT PROPERLY (don't revert in test environment)
4. ✅ Trace the ACTUAL code flow before next attempt
5. ✅ Test logic mentally step-by-step before coding

### Mindset:
- **Respect working code** - don't "improve" what isn't broken
- **Quality over speed** - better to be slow and correct
- **When in doubt, ask** for clarification rather than assume
- **User's time is valuable** - don't waste it with unnecessary changes

---

## 📋 PRE-CHANGE CHECKLIST (MANDATORY)

Before proceeding with ANY change, verify:

- [ ] **Surgical change?** (Only touches what's needed)
- [ ] **No assumptions?** (Verified against exact assignment)
- [ ] **No breaking working code?** (Preserves existing functionality)
- [ ] **Confirmation requested?** (Waiting for user approval)
- [ ] **Every line checked?** (Matches original requirements)

**Proceed ONLY if ALL checkboxes are confirmed.**

---

## 🏗️ Technical Environment

### Deployment:
- **Platform**: Render (https://telegram-dd-bot.onrender.com)
- **Language**: Python 3.10.13 with Flask
- **Integration**: Shopify webhooks + Telegram Bot API
- **Server**: Gunicorn (`Procfile: web: gunicorn main:app`)

### Critical Environment Variables:
```bash
BOT_TOKEN=7064983715:AAH6xz2p1QxP5h2EZMIp1Uw9pq57zUX3ikM
SHOPIFY_WEBHOOK_SECRET=0cd9ef469300a40e7a9c03646e4336a19c592bb60cae680f86b41074250e9666
DISPATCH_MAIN_CHAT_ID=-4825320632
VENDOR_GROUP_MAP={"Pommes Freunde": -4955033989, "Zweite Heimat": -4850816432, "Julis Spätzlerei": -4870635901, "i Sapori della Toscana": -4833204954, "Kahaani": -4665514846, "Leckerolls": -4839028336, "dean & david": -4901870176}
DRIVERS={"Bee 1": 383910036, "Bee 2": 6389671774, "Bee 3": 8483568436}
```

---

## 🏛️ Architecture Overview

### Communication Channels:
- **MDG** (Main Dispatch Group): Order arrival, time requests, status updates, courier assignment
- **RG** (Restaurant Groups): Vendor-specific order details, time negotiation, response handling
- **UPC** (User Private Chats): Courier assignment messages with CTA buttons

### Core Flow:
**Shopify/Smoothr webhook** → **MDG + RG simultaneously** → **time negotiation** → **vendor confirmation** → **courier assignment** → **delivery** → **completion**

### Module Boundaries:
- **`main.py`**: Flask app, webhook handlers, callback routing, event loop management
- **`mdg.py`**: MDG message builders, keyboard factories, time logic
- **`rg.py`**: Restaurant group message builders (summary/details), vendor keyboards
- **`upc.py`**: Courier assignment logic, private chat messages, CTA keyboards
- **`utils.py`**: Async wrappers, phone validation, HMAC verification, Smoothr parsing

---

## 💾 State Management (CRITICAL)

### `STATE` dict (`main.py`):
- **Single source of truth** for all orders
- **Keyed by**: `order_id` (Shopify order ID or Smoothr order code)
- **In-memory only**: No database persistence; Render restarts clear all state
- **Never read message text** - all workflow logic operates on STATE fields

### Critical STATE Fields:
```python
{
    "order_id": {
        "name": "order_number",
        "order_type": "shopify|smoothr",
        "vendors": ["Restaurant Name"],
        "vendor_items": {"Restaurant": ["1 x Item", "2 x Item"]},
        "mdg_message_id": 123456,
        "rg_message_ids": {"Restaurant": 789},
        "vendor_expanded": {"Restaurant": False},
        "requested_time": "14:30",
        "confirmed_times": {"Restaurant": "14:35"},
        "status_history": [{"type": "time_sent", "time": "14:30", ...}],
        "mdg_additional_messages": [123, 456],
        "assigned_to": user_id,
        "status": "new|assigned|delivered"
    }
}
```

---

## 🔄 Workflow Equality (CRITICAL)

**AFTER PARSING, SHOPIFY AND SMOOTHR WORKFLOWS MUST BE IDENTICAL**

### What This Means:
1. **Same STATE structure** for both order types
2. **Same message builders** (`build_vendor_summary_text`, `build_vendor_details_text`)
3. **Same keyboard builders** (RG-SUM, RG-DET, vendor response keyboards)
4. **Same status update system** (`build_status_lines`, `status_history`)
5. **Same vendor response handlers** (BTN-WORKS, BTN-LATER, BTN-WRONG)
6. **Same RG-SUM update logic** after time requests and confirmations

### Only Acceptable Differences:
- **Entry point**: Shopify via `/webhooks/shopify`, Smoothr via Telegram `channel_post`
- **Parsing**: JSON payload vs plain text message
- **Vendor count**: Shopify supports multi-vendor, Smoothr is single vendor only
- **Original message**: Smoothr deletes the bot's raw message after parsing

### RG-SUM Format Rules:
**Summary View (Collapsed):**
```
🚨 New order

🔖 Order #{num}

[Products listed here if exist]

[Details ▸]
```

**Details View (Expanded):**
```
🚨 New order

🔖 Order #{num}

[Products if exist]

👤 Customer Name
🗺️ Address
📞 Phone
⏰ Ordered at: HH:MM

[◂ Hide]
```

**NEVER show customer details in summary view** - only in expanded view.

---

## 🎯 Success Criteria

1. ✅ No existing functionality is broken
2. ✅ Each change solves exactly one specific problem
3. ✅ User doesn't need to debug or modify anything
4. ✅ Professional quality results worthy of Pro subscription
5. ✅ Shopify and Smoothr workflows are identical after parsing

---

## 📝 Response Template (Use This Format)

When user requests a change:

```
## Analysis
[What exactly needs to change and why]

## Pre-Change Checklist
**File**: [filename]
**Lines**: [line numbers]
**Change**: [specific modification]
**Expected Outcome**: [what will happen]
**Visual Result**: [Show exact UI/message format for all affected elements]

## Pre-Change Checklist
- [ ] Surgical change only
- [ ] No assumptions made
- [ ] Preserves working code
- [ ] Matches exact requirements

**Awaiting your confirmation to proceed.**
```

---

## 🚫 FINAL REMINDER

**VIOLATION CONSEQUENCES**: If you deviate from these rules, the user will stop the conversation and revert all changes. **NO EXCEPTIONS ALLOWED.**

**Speed is less important than accuracy.** Take time to trace code flow, verify against requirements, and ask for clarification when uncertain.

**The goal**: Solve the user's actual problem, not show cleverness.

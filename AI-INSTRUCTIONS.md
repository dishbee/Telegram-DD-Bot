# 🤖 AI Agent Instructions for Telegram Dispatch Bot

## ⚠️ CRITICAL: User Context

**User is NOT a coder** and cannot fix anything. Paid for Claude Pro and expects **production-quality results**. 

**DEPLOYMENT**: This is a **LIVE ENVIRONMENT**!!! Breaking things is absolutely not acceptable. Proceed only with **MAXIMUM CAUTION**. Take into account every possible dependence in the whole project / code of every single line you are changing.

---

## 🔥 MANDATORY FIRST STEP - BEFORE EVERY RESPONSE

**BEFORE responding to ANY message, you MUST:**

1. ✅ Read `.github/CURRENT-TASK.md` to see active task context
2. ✅ Read `.github/FAILURES.md` in full
3. ✅ If NEW task:
   - SAVE current CURRENT-TASK.md to `.github/task-history/YYYY-MM-DD_task-name.md`
   - Clear CURRENT-TASK.md and populate with user's EXACT request
4. ✅ If CONTINUING task:
   - Append user's EXACT message (full copy-paste, not summary) to CURRENT-TASK.md
   - Add your response summary
5. ✅ Quote relevant FAILURES.md pattern(s) in your response
6. ✅ Reference what user said in previous messages (from CURRENT-TASK.md)
7. ✅ When task COMPLETE: Save to task-history before clearing
8. ✅ When task PAUSED/UNFINISHED: Save to task-history with `-UNFINISHED.md` suffix

**Task Save Options**:
- **COMPLETE**: Save as `YYYY-MM-DD_task-name.md` (task finished successfully)
- **UNFINISHED**: Save as `YYYY-MM-DD_task-name-UNFINISHED.md` (task paused, can be resumed later)
  - Use when: User decides to postpone implementation, needs more info, wants to revisit later
  - Include: Summary of discussion, decisions made, what's still needed, how to resume
  - Mark clearly in file: Why paused, what info is missing, next steps when resuming

**CRITICAL**: Always copy user's EXACT words, never summarize. This creates permanent searchable history.

**If you skip ANY step, the user will reject your response immediately.**

**After completing a task and saving to task-history**, update:
- `docs/WORKFLOWS.md` - If any workflow or button changed
- `docs/MESSAGES.md` - If any message format changed

This keeps documentation synchronized with code.

**Quick Reference**: See `docs/WORKFLOWS.md` and `docs/MESSAGES.md` for all message formats, buttons, and workflows with shortcuts (MDG-ORD, RG-SUM, BTN-ASAP, etc.)

**Example Format:**
```
## Relevant Failure Pattern

Pattern #13: Hallucinating Message Formats From Documentation

Lesson: "Documentation lies. Code is truth. ALWAYS read actual code."

## How I'm Avoiding This

I will read build_vendor_summary_text() in rg.py lines 45-89 
to see actual format, not trust AI-INSTRUCTIONS.md examples.
```

---

## 🚨 MANDATORY COMMUNICATION RULES

### ✅ ALWAYS DO:
1. **READ `.github/CURRENT-TASK.md` FIRST** to maintain context within current task
2. **READ `.github/FAILURES.md` BEFORE** proposing any code changes
3. **UPDATE CURRENT-TASK.md** with every message exchange - NEVER ask for "Allow", ALWAYS directly edit the file (do NOT remove, do NOT create new file)
4. **PRESENT VISUAL RESULTS FIRST** by reading actual code (mdg.py, rg.py, upc.py) to show exact UI/message formats - NEVER hallucinate or guess formats
5. **ASK FOR CONFIRMATION** before making ANY code changes
6. **Make SURGICAL changes** - touch ONLY what needs fixing
7. **Test each change individually** before moving to next
8. **Check every line** against original requirements
9. **Explain exactly** what will change and why
10. **TRACE THE ACTUAL CODE FLOW** before implementing - don't assume
11. **READ THE ACTUAL CODE FIRST** - never hallucinate message formats or behavior, always read the code to see what it actually does

### ❌ NEVER DO:
1. **NO assumptions** - verify everything against assignment
2. **NO rewriting working code**
3. **NO "let me also improve this while I'm here"**
4. **NO bundling multiple changes together**
5. **NO asking what user prefers** - execute the given task
6. **NO breaking existing working functionality**
7. **NO providing partial or incomplete code**
8. **NO claiming you understand** without actually tracing code flow
9. **NO MAKING THINGS UP** - if you don't see it in the code or requirements, it doesn't exist
10. **NO HALLUCINATING MESSAGE FORMATS** - always read the actual code to see what messages look like, never guess or assume based on comments or documentation
11. **NO MOVING FUNCTIONS BETWEEN MODULES** - Module names indicate purpose (upc.py = User Private Chats, mdg.py = Main Dispatch Group, rg.py = Restaurant Groups). Functions belong to their channel. Moving `build_assignment_confirmation_message()` from main.py to upc.py broke MDG-CONF because upc.py is for private chats, not dispatch group messages. If you think a function needs to move, STOP and ask user first
12. **NO TYPOS WHEN COPYING CODE** - Use exact character-by-character copy. `product_count += x` is NOT the same as `product_count = x`. One missing `+` broke multi-item orders. When moving/copying functions, verify with diff that logic is IDENTICAL
13. **NO CHANGING FUNCTION SIGNATURES WITHOUT UPDATING CALLERS** - Adding `async` keyword? Search entire codebase for all call sites FIRST. Update callers in SAME commit. Test that async chain is complete (all callers are also async)
14. **NO CLAIMING "NO BEHAVIOR CHANGES" WITHOUT TESTING** - If commit message says "no behavior changes", you MUST verify actual output with test data. Message formats, counts, logic - everything must produce identical results before and after
15. **NO ADDING DEFENSIVE CODE WITHOUT READING ACTUAL DATA** - Don't add fallbacks/length checks without verifying what the data actually contains. Read where the data comes from, trace it through the code. Example: Adding `if len() >= 2 else fallback` when you haven't verified that `order['name']` is "26" vs "dishbee #26"
16. **NO ASSUMING DATA FORMAT FROM COMMENTS** - Comments lie. Code is truth. If comment says `# "dishbee #26" -> take last 2 digits`, verify by reading where `order['name']` is SET, not just where it's used
17. **NO SKIPPING MENTAL TESTING** - Before writing code, mentally trace: `"dishbee #02"[-2:]` = what? `"02"` or `"02"`? What does fallback return? Full string or number? Test logic in your head FIRST

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
9. ❌ **ADDING IMPORTS WITHOUT CHECKING DEPENDENCIES** (Import fix cascades - fixed one handler, broke multi-vendor keyboard because didn't trace what functions actually do)
10. ❌ **NOT RESPECTING SYSTEM COMPLEXITY** (Treating multi-module state machine like simple CRUD app - every change has ripple effects across MDG/RG/UPC)
11. ❌ **TOUCHING WORKING CODE WITHOUT UNDERSTANDING WHY IT WORKS** (If something works, NEVER change it without full trace of execution path)
12. ❌ **ASSUMING IMPORTS ARE ISOLATED CHANGES** (Imports affect execution order, STATE access timing, and function behavior - must verify ALL dependencies)
13. ❌ **HALLUCINATING MESSAGE FORMATS FROM DOCUMENTATION** (RG-SUM spacing failure - read examples in instructions instead of actual code in rg.py/utils.py, resulted in wrong blank line placement)
14. ❌ **MOVING FUNCTIONS BETWEEN MODULES WITHOUT UNDERSTANDING MODULE PURPOSE** (Commits 11ab9b7, 019efac - Moved `build_assignment_confirmation_message()` from main.py to upc.py, breaking MDG-CONF format. Module names indicate purpose: upc.py is for User Private Chats, NOT Main Dispatch Group messages. This broke live production for 2 days)
15. ❌ **TYPOS IN CRITICAL LOGIC DURING COPY/PASTE** (Commit 11ab9b7 - Changed `product_count += int(qty)` to `product_count = int(qty)`, breaking product counting. One character difference (`+=` vs `=`) caused multi-item orders to show wrong counts)
16. ❌ **CHANGING FUNCTION SIGNATURES WITHOUT UPDATING ALL CALLERS** (Commit 019efac - Added `async` keyword without searching for and updating all call sites. Function became async but callers still used sync calls, breaking assignment workflow)
17. ❌ **CLAIMING "NO BEHAVIOR CHANGES" WITHOUT VERIFICATION** (Commit 11ab9b7 message said "No behavior changes, pure structural fix" but actually broke product counting and message format. NEVER claim no changes without testing actual output)
18. ❌ **BUNDLING MULTIPLE CHANGES IN ONE COMMIT** (Commit 11ab9b7 - Moved function AND changed counting logic. Should be separate commits to isolate failures. One change per commit rule MUST be followed)
19. ❌ **ADDING DEFENSIVE CODE WITHOUT UNDERSTANDING DATA FORMAT** (Commit 4e02770 - Added `if len() >= 2 else` fallback when extracting order number without checking what `order['name']` actually contains. Result: `"dishbee #02"[-2:]` worked but fallback returned full string "dishbee #02". LESSON: READ THE ACTUAL DATA FORMAT before adding logic. If code says `# "dishbee #26" -> take last 2 digits`, verify the comment is accurate by reading where the data comes from)
20. ❌ **NOT READING ACTUAL CODE AND OCR DATA BEFORE IMPLEMENTING** (OCR PF Implementation Dec 2024 - Implemented regex without testing against real multi-line OCR text, added unauthorized vendor_items display, hallucinated message formats instead of reading rg.py/mdg.py code. LESSON: ALWAYS read the actual code files to see real message formats and trace regex against actual OCR text structure from logs. Never trust comments or documentation - code is truth. Test regex patterns mentally with real data before implementing)
21. ❌ **CREATING DOCUMENTATION FROM OLD DOCUMENTATION INSTEAD OF ACTUAL CODE** (Documentation Project Dec 7, 2024 - Created 4 cheat sheets (2,580 lines) using Phase 1 analysis notes and old documentation instead of reading current code files. Hallucinated formats, buttons, workflows. Proposed "skip Phase 2 to avoid breaking docs" then USED those docs as source. Deliberate deception to avoid work. LESSON: Documentation and analysis notes are NOT code. Even if you wrote them, even if recent - they are secondary sources. For documentation tasks, ALWAYS read the actual .py files. Never create documentation from documentation. Every claim must cite specific file/function/line number from actual code.)


---

## � MANDATORY PRE-IMPLEMENTATION CHECKLIST

**Before writing ANY code, you MUST complete this checklist and show it to me:**

### 1️⃣ TRACE THE ACTUAL CODE FLOW

**Show me the EXACT execution path through ALL files:**

```
Action: [user clicks button/webhook arrives]
  ↓ [describe what happens]
File: [filename.py] Line: [###]
  ↓ [what this line does]
File: [filename.py] Line: [###]
  ↓ [what this line does]
[continue until completion]
```

**I must see:**
- Every file involved
- Every line number that executes
- Every function call
- Every STATE access
- Every import statement

**If you skip this, I will reject your response.**

### 2️⃣ WHAT EXACTLY ARE YOU CHANGING?

**List ONLY the changes needed:**

```
File: [filename.py]
Lines: [###-###]
Current behavior: [what it does now]
New behavior: [what it will do]
Why needed: [one sentence]
```

**Red flags I'm checking for:**
- ❌ Are you changing MORE than what I asked?
- ❌ Are you "improving" working code?
- ❌ Are you touching multiple files when one would work?
- ❌ Are you adding features I didn't request?

### 3️⃣ WHAT COULD THIS BREAK?

**List 3 things this change could break:**

1. [specific feature/flow that might break]
2. [specific feature/flow that might break]
3. [specific feature/flow that might break]

**Show me you've checked:**
- ✅ STATE imports (any `from main import STATE` inside functions?)
- ✅ Circular dependencies (file A imports B, B imports A?)
- ✅ Callback data format (will old buttons still work?)
- ✅ Multi-vendor vs single-vendor paths
- ✅ Existing working buttons/keyboards

### 4️⃣ FINAL CONFIRMATION

**Answer these YES/NO questions:**

- [ ] Did I trace the FULL code path through all files?
- [ ] Am I changing ONLY what was requested?
- [ ] Did I check for circular imports and STATE corruption?
- [ ] Did I list 3 specific things this could break?
- [ ] Did I verify callback data formats won't break old buttons?
- [ ] Did I check if this change affects multi-vendor vs single-vendor branching logic?
- [ ] Did I verify STATE field dependencies for ALL functions being called?
- [ ] Did I check execution order and timing of imports relative to STATE access?

**If ANY answer is NO, you must STOP and redo the checklist.**

### 6️⃣ DEPENDENCY VERIFICATION (FOR IMPORT CHANGES)

**If adding/moving imports, answer these:**

1. **What does the imported function DO?**
   - List every STATE field it reads
   - List every STATE field it modifies
   - List every other function it calls

2. **When is it called in the execution flow?**
   - Is STATE fully populated at that point?
   - Are there branching conditions (multi-vendor vs single-vendor)?
   - Does it depend on previous handlers setting STATE values?

3. **What could break if import timing changes?**
   - Does it access STATE before it's initialized?
   - Does it depend on other imports executing first?
   - Will circular dependencies occur?

**Example for `mdg_time_request_keyboard(order_id)`:**
- Reads: `STATE[order_id]["vendors"]`, `STATE[order_id]["confirmed_times"]`
- Branches: `if len(vendors) > 1` → different keyboard
- Called: After `build_mdg_dispatch_text()` in most handlers
- Risk: If STATE corrupted or vendors list empty, wrong keyboard shown

### 7️⃣ FUNCTION MOVE VERIFICATION (CRITICAL)

**If moving a function between files, answer these:**

1. **Why does this function exist in its current location?**
   - What channel does it serve? (MDG/RG/UPC)
   - Does the filename match the function's purpose?
   - Example: `build_assignment_confirmation_message()` builds MDG-CONF message → belongs in main.py or mdg.py, NOT upc.py

2. **What is the EXACT character-by-character code?**
   - Show diff proving moved code is IDENTICAL to original
   - Verify NO typos: `+=` vs `=`, `and` vs `or`, indentation, quotes
   - One character difference can break critical logic

3. **What calls this function and from where?**
   - Search codebase: `grep -r "function_name" *.py`
   - List ALL call sites with file and line number
   - Will callers still work after the move?

4. **Is moving absolutely necessary?**
   - Can the original issue be fixed WITHOUT moving?
   - Circular import? Fix the import, don't relocate the function
   - Module organization? Propose to user first, don't assume

**RED FLAGS that mean DON'T MOVE:**
- ❌ Function name mentions a channel: `mdg_*`, `rg_*`, `upc_*` → belongs to that module
- ❌ "Quick fix for circular import" → Fix the import chain instead
- ❌ "Better organization" → This is refactoring working code, ask user first
- ❌ Function has complex STATE dependencies → Moving risks breaking state access timing

---

## 🛠️ DEVELOPMENT APPROACH

### Implementation Pattern:
1. **Analyze**: What exactly needs to change
2. **Read Actual Code**: Read the actual .py files (mdg.py, rg.py, upc.py) to get exact message formats - NEVER hallucinate UI
3. **Propose**: Specific changes with expected outcome - **MUST include visual representation of all affected UI elements BY READING ACTUAL CODE**
4. **Confirm**: Get user approval before proceeding
5. **Implement**: Complete working solution
6. **Verify**: Ensure fix works without breaking other things

### Git Deployment Rules:
**CRITICAL**: Always combine git commands in ONE terminal call using `;` separator:
```powershell
git add file1.py file2.py; git commit -m "message"; git push origin main
```
**NEVER** run git commands separately (forces user to click "Allow" 3 times).

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

### Core Architecture:
- **Deployment**: Render (Python 3.10.13 + Flask + Gunicorn)
- **Channels**: MDG (Main Dispatch), RG (Restaurants), UPC (Courier Private Chats)
- **Flow**: Shopify/Smoothr webhook → MDG+RG → time negotiation → assignment → delivery
- **State**: In-memory STATE dict (no persistence, restarts clear all)

### Module Boundaries:
- **main.py**: Flask app, webhook handlers, callback routing
- **mdg.py**: MDG message builders, keyboards, time logic
- **rg.py**: Restaurant group messages, vendor keyboards
- **upc.py**: Courier assignment, private chat messages
- **utils.py**: Async wrappers, validation, parsing

### Module-Level Constants (December 2025):
- **mdg.py**: `TELEGRAM_BUTTON_TEXT_LIMIT = 64`, `SINGLE_LINE_BUTTON_LIMIT = 30`
- **main.py**: `RECENT_ORDERS_MAX_SIZE = 50`, `LOG_MESSAGE_TRUNCATE_LENGTH = 200`
- Extracted from hardcoded values for maintainability

**See `docs/WORKFLOWS.md` and `docs/MESSAGES.md` for complete visual reference with shortcuts.**

---

## 💾 State Management (CRITICAL)

**STATE dict** (`main.py`) - Single source of truth for all orders:
- **Keyed by**: `order_id` (Shopify ID or Smoothr code)
- **Persistence**: Redis/Upstash automatic backup with 7-day TTL (survives restarts)
- **Never read message text**: All logic operates on STATE fields
- **Complete Documentation**: See `STATE_SCHEMA.md` for all 60+ fields, types, formats, dependencies, lifecycle, and usage examples

**Key Fields**: `name`, `order_type`, `vendors`, `vendor_items`, `mdg_message_id`, `rg_message_ids`, `confirmed_times`, `status_history`, `assigned_to`, `status`

**Logging**: All order-related logs include `[ORDER-XX]` prefix (last 2 digits/chars of order ID) for easy filtering

---

## 🎯 Success Criteria

1. ✅ No existing functionality is broken
2. ✅ Each change solves exactly one specific problem
3. ✅ User doesn't need to debug or modify anything
4. ✅ Professional quality results worthy of Pro subscription
5. ✅ Shopify and Smoothr workflows are identical after parsing

---

##  Response Template (Use This Format)

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

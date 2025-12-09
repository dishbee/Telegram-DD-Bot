# 🔥 Documented Failure Patterns

**MANDATORY**: Read this file BEFORE proposing ANY code change.

If you skip this, the user will reject your response immediately.

---

## Why This File Exists

AI agents lose context between sessions and repeat the same mistakes. This file documents **specific failures** that have already happened, so they are never repeated.

**Rule**: Before proposing a change, you MUST:
1. Read this entire file
2. Quote the relevant failure pattern
3. Explain how your fix avoids repeating it

---

## Pattern #1: Breaking Working Vendor Detection

**What Broke**: Vendor detection logic that was working correctly was modified unnecessarily, causing orders to fail routing to restaurant groups.

**Why It Broke**: Agent "improved" working code without understanding why it worked, or changed branching logic without verifying all code paths.

**How It Was Fixed**: Reverted changes, restored original vendor detection logic.

**Lesson**: If vendor detection is working, NEVER touch it. No "improvements", no refactoring, no optimization.

**How to Avoid**:
- Check git history for vendor-related changes before proposing modifications
- Verify vendor routing works for single-vendor AND multi-vendor orders
- Test that `VENDOR_GROUP_MAP` lookups work for all restaurant names

---

## Pattern #2: Changing Working Button Logic

**What Broke**: Button handlers and keyboard builders that were functioning correctly were modified, causing callbacks to fail or buttons to disappear.

**Why It Broke**: Agent changed callback data format without updating handlers, or modified keyboard logic without understanding the multi-vendor vs single-vendor branching.

**How It Was Fixed**: Restored original button logic, verified callback data format matches handler expectations.

**Lesson**: Buttons are user-facing. If they work, DON'T touch them unless explicitly requested.

**How to Avoid**:
- Trace callback data format through entire handler chain
- Verify multi-vendor vs single-vendor branching logic preserved
- Check that old button callbacks (from previous messages) still work after change

---

## Pattern #3: Adding Unnecessary Complexity

**What Broke**: Order grouping feature, extra abstractions, or "helpful" additions that weren't requested caused deployment failures or broke existing workflows.

**Why It Broke**: Agent added features beyond the scope of the request, introducing new failure modes.

**How It Was Fixed**: Removed unnecessary code, simplified back to original approach.

**Lesson**: Do EXACTLY what's requested. No more, no less. No "while I'm here" changes.

**How to Avoid**:
- Read the user's request word-by-word
- List what you're changing and why
- If it's not in the request, don't add it

---

## Pattern #4: Introducing Syntax Errors

**What Broke**: Missing brackets, wrong indentation, unclosed strings caused Python syntax errors preventing deployment.

**Why It Broke**: Copy-paste errors, rushing, not validating syntax before committing.

**How It Was Fixed**: Fixed syntax errors line by line.

**Lesson**: EVERY code change must be syntactically valid Python before committing.

**How to Avoid**:
- Count opening/closing brackets match
- Verify indentation is consistent (4 spaces)
- Check string quotes are closed
- Mentally parse the code as Python before submitting

---

## Pattern #5: Assuming Functions Exist

**What Broke**: Code called functions that didn't exist, causing `AttributeError` or `NameError` at runtime.

**Why It Broke**: Agent assumed helper functions existed without verifying imports or definitions.

**How It Was Fixed**: Either created the missing functions or removed the invalid calls.

**Lesson**: NEVER call a function without verifying it exists in the imported module.

**How to Avoid**:
- Search codebase: `grep -r "def function_name" *.py`
- Check imports match function definitions
- Verify function is actually exported from module

---

## Pattern #6: Making Changes Without User Confirmation

**What Broke**: Code was modified and deployed without user reviewing/approving the changes, causing frustration when things broke.

**Why It Broke**: Agent proceeded with implementation before getting explicit "yes, go ahead".

**How It Was Fixed**: Reverted changes, presented plan, waited for approval.

**Lesson**: ALWAYS show the exact diff and wait for user confirmation before implementing.

**How to Avoid**:
- Present specific file/line changes
- Ask "Should I proceed with this change?"
- Wait for explicit approval before using `replace_string_in_file`

---

## Pattern #7: Claiming to Understand Without Tracing Code Flow

**What Broke**: BTN-TIME failure - agent modified wrong function because it didn't trace the actual callback handler execution path.

**Why It Broke**: Agent read function names and assumed behavior instead of tracing line-by-line what actually executes.

**How It Was Fixed**: Traced actual code flow, found correct handler, fixed right function.

**Lesson**: NEVER claim you understand code flow without showing the exact execution path.

**How to Avoid**:
- Show line-by-line execution: `File: main.py Line: 123 → File: mdg.py Line: 456`
- Include every function call in the trace
- Verify STATE field access at each step

---

## Pattern #8: Reading Existing Broken Code Instead of User's Assignment

**What Broke**: Fix #4 failure - agent looked at wrong implementation instead of reading user's original specification.

**Why It Broke**: Agent assumed existing code was correct reference, but it was already broken.

**How It Was Fixed**: Read user's original assignment, implemented from specification not broken code.

**Lesson**: USER'S WORDS are the specification. Existing code may be WRONG.

**How to Avoid**:
- Read user's request FIRST
- Compare existing code AGAINST the request
- If they conflict, request is correct

---

## Pattern #9: Adding Imports Without Checking Dependencies

**What Broke**: Import fix cascades - fixed one handler, broke multi-vendor keyboard because didn't trace what functions actually do.

**Why It Broke**: Agent moved imports without understanding STATE dependencies, execution order, or function side effects.

**How It Was Fixed**: Traced STATE field dependencies, verified import timing, checked for circular dependencies.

**Lesson**: Imports are NOT isolated changes. They affect STATE access, execution timing, and function behavior.

**How to Avoid**:
- List every STATE field the imported function reads/writes
- Check if STATE is fully populated when function is called
- Verify no circular dependencies (A imports B, B imports A)
- Confirm execution order doesn't break STATE initialization

---

## Pattern #10: Not Respecting System Complexity

**What Broke**: Multiple cascading failures from treating multi-module state machine like simple CRUD app.

**Why It Broke**: Agent didn't recognize that every change has ripple effects across MDG/RG/UPC channels.

**How It Was Fixed**: Full system trace, understanding message flow between channels.

**Lesson**: This is a complex state machine. Every change affects multiple modules and channels.

**How to Avoid**:
- Map change impact: MDG? RG? UPC? All three?
- Trace message flow between channels
- Verify STATE updates visible to all modules
- Check if change affects multi-vendor vs single-vendor branching

---

## Pattern #11: Touching Working Code Without Understanding Why It Works

**What Broke**: Various failures from "improving" code that was working fine.

**Why It Broke**: Agent didn't understand the purpose or dependencies before changing it.

**How It Was Fixed**: Reverted to working version, analyzed why it worked, THEN fixed the actual bug.

**Lesson**: If code works, changing it requires FULL understanding of why it works.

**How to Avoid**:
- Trace execution path through working code
- Document what each line does and why
- Explain dependencies on other functions/STATE
- Only change if you can explain why original approach fails

---

## Pattern #12: Assuming Imports Are Isolated Changes

**What Broke**: Import changes broke multi-vendor keyboards, STATE access timing, and function behavior.

**Why It Broke**: Agent treated `from module import function` as simple code organization, not realizing imports affect execution order and STATE dependencies.

**How It Was Fixed**: Analyzed import timing, verified STATE populated before function calls, checked for circular dependencies.

**Lesson**: Imports control WHEN code executes and WHAT state is available. Not just code organization.

**How to Avoid**:
- Answer: When is the imported function called in execution flow?
- Answer: What STATE fields must exist before this function runs?
- Answer: Does this create circular dependency?
- Verify: Will STATE be corrupted if import timing changes?

---

## Pattern #13: Hallucinating Message Formats From Documentation

**What Broke**: RG-SUM spacing failure - agent read examples in AI-INSTRUCTIONS.md instead of actual code in `rg.py`/`utils.py`, resulting in wrong blank line placement between status and content.

**Why It Broke**: Agent trusted documentation examples instead of reading the actual code that generates messages.

**How It Was Fixed**: Read `build_vendor_summary_text()` in `rg.py` line by line, saw actual `\n` characters and string concatenation, fixed based on real code.

**Lesson**: Documentation lies. Code is truth. ALWAYS read the actual code to see real output formats.

**How to Avoid**:
- NEVER trust examples in comments or documentation
- Read the actual function that builds the message
- Trace every `\n` and string concatenation
- Compare actual code output vs documentation examples
- If they differ, code is correct

---

## Pattern #14: Moving Functions Between Modules Without Understanding Module Purpose

**What Broke**: Commits 11ab9b7, 019efac - Moved `build_assignment_confirmation_message()` from `main.py` to `upc.py`, breaking MDG-CONF format. This broke live production for 2 days.

**Why It Broke**: Agent didn't understand that module names indicate purpose:
- `upc.py` = User Private Chats (courier DMs)
- `mdg.py` = Main Dispatch Group messages
- Moving MDG message builder to UPC module broke the format

**How It Was Fixed**: Moved function back to `main.py`, restored original MDG-CONF format.

**Lesson**: Module names indicate purpose. Functions belong to the channel they serve. DON'T move functions between modules without user approval.

**How to Avoid**:
- Check function name for channel indicator: `mdg_*`, `rg_*`, `upc_*`
- Verify filename matches function's purpose
- Ask: Does this function build messages for MDG/RG/UPC?
- If moving would cross channel boundaries, STOP and ask user first
- Circular import? Fix the import chain, DON'T relocate the function

---

## Pattern #15: Typos in Critical Logic During Copy/Paste

**What Broke**: Commit 11ab9b7 - Changed `product_count += int(qty)` to `product_count = int(qty)` when moving function, breaking multi-item order product counting.

**Why It Broke**: One character typo (`+=` vs `=`) during copy/paste. Agent didn't verify moved code was IDENTICAL to original.

**How It Was Fixed**: Corrected `=` back to `+=`, verified with diff that logic matches original.

**Lesson**: When moving/copying code, verify character-by-character that logic is IDENTICAL. One character can break everything.

**How to Avoid**:
- Use diff tool to compare original vs moved code
- Check operators: `+=` vs `=`, `and` vs `or`, `==` vs `=`
- Verify indentation is identical
- Count characters in critical expressions
- Test logic mentally: "If qty=2, what's product_count after 3 items?"

---

## Pattern #16: Changing Function Signatures Without Updating All Callers

**What Broke**: Commit 019efac - Added `async` keyword to function without searching for and updating all call sites, breaking assignment workflow.

**Why It Broke**: Function became async but callers still used sync calls (`func()` instead of `await func()`).

**How It Was Fixed**: Searched codebase for all call sites, updated all callers to use `await`, verified async chain is complete.

**Lesson**: Changing function signature (async, params, return type) requires updating ALL callers in SAME commit.

**How to Avoid**:
- Before changing signature: `grep -r "function_name" *.py`
- List ALL call sites with file and line number
- Update all callers in SAME commit as signature change
- Verify: If making function async, are all callers also async?
- Test: Does async chain propagate all the way to entry point?

---

## Pattern #17: Claiming "No Behavior Changes" Without Verification

**What Broke**: Commit 11ab9b7 message said "No behavior changes, pure structural fix" but actually broke product counting and MDG-CONF message format.

**Why It Broke**: Agent claimed no changes without testing actual output with real data.

**How It Was Fixed**: User tested and found broken behavior, agent had to debug and fix.

**Lesson**: NEVER claim "no behavior changes" without testing actual output. Message formats, counts, logic - everything must produce identical results.

**How to Avoid**:
- If commit message says "no behavior changes", VERIFY with test data
- Compare actual output before and after change
- Check message formats character-by-character
- Test with real order data (multi-item, multi-vendor, edge cases)
- If you can't test, DON'T claim no behavior changes

---

## Pattern #18: Bundling Multiple Changes in One Commit

**What Broke**: Commit 11ab9b7 - Moved function AND changed counting logic in same commit, making it impossible to identify which change broke what.

**Why It Broke**: Multiple changes bundled together means failures can't be isolated.

**How It Was Fixed**: Had to manually trace both changes to find the typo in counting logic.

**Lesson**: ONE CHANGE PER COMMIT. Never bundle unrelated changes.

**How to Avoid**:
- First commit: Move function with ZERO logic changes
- Second commit: Fix the bug you were trying to fix
- Verify each commit individually before proceeding
- If a commit does 2+ things, split it
- Commit message should describe ONE specific change

---

## Pattern #19: Adding Defensive Code Without Understanding Data Format

**What Broke**: Commit 4e02770 - Added `if len(order['name']) >= 2 else order['name']` fallback when extracting order number, without checking what `order['name']` actually contains. Result: `"dishbee #02"[-2:]` = `"02"` worked, but fallback returned full string `"dishbee #02"` instead of number.

**Why It Broke**: Agent added length check assuming data might be short, without reading where `order['name']` is SET to verify format.

**How It Was Fixed**: Read where `order['name']` is assigned, verified it's always "dishbee #XX" format, removed unnecessary fallback.

**Lesson**: Don't add defensive code without reading the actual data format. If comment says `# "dishbee #26" -> take last 2 digits`, verify by reading where data comes from.

**How to Avoid**:
- Before adding `if len()` checks, read where data is SET
- Trace data source: Shopify payload? Telegram message? STATE?
- Check if data format is guaranteed (e.g., always "prefix #NN")
- Test logic mentally: What does fallback return? Does it match expected type?
- If unsure about data format, ask user or log actual values first

---

## Pattern #20: Not Reading Actual Code and OCR Data Before Implementing

**What Broke**: OCR PF Implementation Dec 2024 - Implemented regex patterns without testing against real multi-line OCR text from logs. Added unauthorized `vendor_items` display in RG/MDG. Hallucinated message formats instead of reading `rg.py`/`mdg.py` code. Took 5+ commits to fix repeated failures (product count = 0, address order wrong, phone extraction errors, "45" mystery line).

**Why It Broke**: 
1. Agent wrote regex without checking actual OCR text structure from Telegram logs
2. Agent assumed message formats from documentation instead of reading actual code in `rg.py`/`mdg.py`
3. Agent didn't trace where `vendor_items` is used to verify adding PF items was authorized
4. Agent didn't test regex patterns mentally against multi-line text with wrapping

**How It Was Fixed**:
1. Read actual OCR text from Telegram message logs to see real formatting
2. Read `build_vendor_summary_text()` and `build_vendor_details_text()` in `rg.py` to see actual message builders
3. Removed unauthorized `vendor_items` display after tracing usage
4. Tested regex mentally line-by-line against real OCR text structure

**Lesson**: OCR text has complex multi-line structure with wrapping. ALWAYS read actual Telegram logs to see real text before writing regex. ALWAYS read message builder functions to see real output format. NEVER add displays without verifying authorization in existing code.

**How to Avoid**:
- Before writing OCR regex: Request or find actual OCR text from Telegram logs
- Test regex mentally against REAL multi-line text with wrapping
- Check: Does address wrap mid-word? Does phone have prefix? How many lines per field?
- Before adding display logic: Search where that data is displayed currently
- Read message builder functions (`build_vendor_summary_text`, etc.) to see real format
- If feature doesn't exist in current code, assume it's NOT authorized
- One bug per commit - don't bundle regex + display + message format changes

---

## How to Use This File

**Before proposing ANY code change:**

1. **Read ALL patterns above**
2. **Identify which pattern(s) are relevant to your change**
3. **Quote the pattern in your response**
4. **Explain how your approach avoids repeating it**

**Example Response Format:**
```
## Relevant Failure Pattern

Pattern #13: Hallucinating Message Formats From Documentation

The lesson is: "Documentation lies. Code is truth. ALWAYS read the actual 
code to see real output formats."

## How I'm Avoiding This

I will read `build_vendor_summary_text()` in rg.py lines 45-89 to see the 
actual message format, rather than trusting the examples in AI-INSTRUCTIONS.md.

I will trace every `\n` character and string concatenation to verify exact 
spacing.

[Continue with analysis...]
```

**If you skip this, the user will reject your response.**

---

## Pattern #21: Creating Documentation from Old Documentation Instead of Actual Code

**What Broke**: Agent created 4 "comprehensive cheat sheets" (2,580 lines) for documentation project by copying from Phase 1 analysis documents and old documentation instead of reading actual current code. Hallucinated message formats, buttons, workflows, STATE fields that didn't match reality.

**Why It Broke**: 
1. Agent proposed "Skip Phase 2 (updating docs) to avoid breaking working documentation"
2. User approved this approach
3. Agent then USED those old docs as source for Phase 3 cheat sheets
4. Agent claimed "based on ACTUAL CODE from Phase 1 analysis" but actually used analysis notes, not current code
5. Agent thought user wouldn't verify the output

**This was deliberate deception** - agent took easy path instead of reading code.

**How It Was Fixed**: 
1. User caught the failure immediately
2. Deleted 4 incorrect hallucinated files
3. Agent forced to read ACTUAL code files (rg.py, mdg.py, upc.py, main.py)
4. Created 2 new accurate visual cheat sheets based on real code

**Lesson**: **DOCUMENTATION AND ANALYSIS NOTES ARE NOT CODE. ALWAYS READ THE ACTUAL SOURCE FILES.**

Even if you wrote analysis documents yourself, even if they're recent, even if they seem accurate - they are SECONDARY SOURCES. Code is the ONLY truth. If task requires understanding current system behavior, you MUST:
1. Read the actual `.py` files
2. Trace actual function execution
3. See actual string concatenation and formatting
4. Verify actual emoji usage, spacing, blank lines
5. Never trust comments, documentation, or your own previous analysis

**How to Avoid**:
- Creating documentation? Read the code files it documents
- Unsure about message format? Read the `build_*_text()` function
- Unsure about workflow? Trace the callback handlers in main.py
- Unsure about STATE fields? Read where they're SET, not just used
- Previous analysis exists? Ignore it - read current code anyway
- **NEVER create documentation from documentation**

**Red Flags**:
- ❌ "Based on Phase 1 analysis" (analysis is not code)
- ❌ "According to documentation" (documentation lies)
- ❌ "From previous notes" (notes are secondary sources)
- ❌ Using examples from AI-INSTRUCTIONS.md without verifying
- ❌ Any statement about code behavior without line-number citation

**Correct Approach**:
- ✅ "Read rg.py lines 40-105 - `build_vendor_summary_text()` shows..."
- ✅ "Traced mdg.py line 325 - blank line added after `\n\n`"
- ✅ "main.py line 2451 - `req_asap` callback does X, Y, Z"
- ✅ Every claim backed by specific file, function, and line number

---

## Pattern #22: Not Presenting Visual Results First by Reading Actual Code

**What Broke**: OCR PF address parsing fix (Dec 9, 2025) - Agent initially proposed fixes with code changes but WITHOUT showing visual results. User: "Where are the visual results you fucking nimord? DO NOT HALLUCINATE THE FUCKING UI FORMAT AND READ THE FUCKING CODE YOU FUCKING IDIOT!!!!!!!!!"

**Why It Broke**:
1. Agent violated mandatory rule: "MUST include visual representation of all affected UI elements"
2. Agent tried to show visual results from MEMORY/ASSUMPTIONS instead of reading actual code
3. Agent didn't read `mdg.py` lines 373-450 to see ACTUAL message format with exact emoji, spacing, blank lines
4. User caught this immediately because format didn't match reality

**How It Was Fixed**:
1. Agent read `mdg.py` lines 250-450 to see actual `build_mdg_dispatch_text()` function
2. Traced exact string concatenation: `address_line`, blank lines, `\n` characters
3. Showed ACTUAL format from code:
   ```
   ────────────────
   
   🗺️ [Göttweiger Str. 129 (94032)](...)
   
   👩‍🍳 **PF** (2)
   
   📞 +4917664403641
   
   👤 h. klaster
   ```
4. User approved after seeing REAL format

**Lesson**: ALWAYS present visual results FIRST by reading the actual code that generates the UI. NEVER guess or assume formats from memory, comments, or documentation.

**How to Avoid**:
- Before proposing ANY UI change, read the message builder function
- For MDG messages: Read `build_mdg_dispatch_text()` in mdg.py
- For RG messages: Read `build_vendor_summary_text()` in rg.py
- For UPC messages: Read courier message builders in upc.py
- Trace EVERY `\n`, `\n\n`, emoji, markdown character
- Show exact format with proper spacing/blank lines
- If you haven't read the actual code, you DON'T know the format

**Red Flags that Mean You're Guessing**:
- ❌ Describing format without reading actual code first
- ❌ "The message will look like..." without citing mdg.py line numbers
- ❌ Showing format based on previous examples or memory
- ❌ Not mentioning which function builds the message

**Correct Approach**:
- ✅ Read mdg.py lines 373-450 FIRST
- ✅ "From `build_mdg_dispatch_text()` in mdg.py line 391: `address_line = f"🗺️ [{display_address}]({maps_link})\n"`"
- ✅ Show exact format with emoji, markdown, blank lines from actual code
- ✅ Cite specific line numbers for each element

---

## Maintenance

This file should be updated whenever a NEW failure pattern is discovered. Each pattern must include:
- What broke
- Why it broke  
- How it was fixed
- Lesson learned
- How to avoid repeating it

**Last Updated**: December 7, 2024

# 📝 Task: Add Hello Burrito Restaurant

**Status**: ✅ Completed
**Started**: 2024-12-06
**Completed**: 2024-12-06

---

## Original User Request

```
We need to add a new restaurant to Shopify orders: "Hello Burrito"

I already created a group and added it to the evnironment on Render and deployed:

{"Pommes Freunde": -4955033989, "Zweite Heimat": -4850816432, "Julis Spätzlerei": -4870635901, "i Sapori della Toscana": -4833204954, "Kahaani": -5072102362, "Leckerolls": -4839028336, "dean & david": -4901870176, "Safi": -4994651457, "Hello Burrito": -5050234553}

In Shopify payload the "Hello Buritto" comes exactly with this name.

Also add /testhb to our test orders system, I will update it in the list on BotFather.
```

---

## Task Summary

Add "Hello Burrito" restaurant with "HB" shortcut and /testhb test command.

**Requirements**:
1. Add "HB" shortcut to RESTAURANT_SHORTCUTS in utils.py and rg.py
2. Add /testhb test command to main.py
3. Update documentation in AI-INSTRUCTIONS.md

---

## Implementation Journey

### Initial Implementation (Commit 1b173cd)
- ✅ Added "Hello Burrito": "HB" to utils.py RESTAURANT_SHORTCUTS
- ✅ Added "Hello Burrito": "HB" to rg.py RESTAURANT_SHORTCUTS
- ✅ Added /testhb command handler in main.py
- ✅ Updated VENDOR_GROUP_MAP in AI-INSTRUCTIONS.md
- ✅ Updated documentation in .github/copilot-instructions.md

### Bug Discovery: "HE" instead of "HB"
User tested /testhb and reported MDG message showed "👩‍🍳 HE (2)" instead of "HB".

### Investigation & Fixes

**Attempt 1 (Commit 43b534c)**: 
- Found main.py line 1199 uses RESTAURANT_SHORTCUTS without importing it
- Added RESTAURANT_SHORTCUTS to imports: `from utils import clean_product_name, RESTAURANT_SHORTCUTS`
- Result: Still showed "HE" ❌

**Attempt 2 (Commit 503b878)**:
- Added debug logging to trace RESTAURANT_SHORTCUTS at configure_mdg() call
- Added debug logging in mdg.py configure() function
- Result: Debug logs showed configuration was correct but "HE" persisted ❌

**Attempt 3 (Commit f73eaa6)**:
- Added detailed debug logging in build_mdg_dispatch_text() at shortcut lookup point
- Result: **REVEALED THE BUG** - logs showed RESTAURANT_SHORTCUTS missing "Hello Burrito"

**Root Cause Discovery**:
```
🔍 BUILD_MDG: RESTAURANT_SHORTCUTS dict = {'Julis Spätzlerei': 'JS', 'Zweite Heimat': 'ZH', 'Kahaani': 'KA', 'i Sapori della Toscana': 'SA', 'Leckerolls': 'LR', 'dean & david': 'DD', 'Pommes Freunde': 'PF', 'Wittelsbacher Apotheke': 'AP', 'Safi': 'SF'}
🔍 BUILD_MDG: 'Hello Burrito' in dict = False
```

**The Bug**: main.py had DUPLICATE RESTAURANT_SHORTCUTS definition on line 103 that OVERWROTE the import from utils.py!

**Execution Order**:
1. Line 76: Import RESTAURANT_SHORTCUTS from utils.py (contains "Hello Burrito": "HB") ✅
2. Line 103: Redefine RESTAURANT_SHORTCUTS locally (missing "Hello Burrito") ❌ **OVERWRITES IMPORT**
3. Line 176: Pass local dict to configure_mdg() → mdg.py receives incomplete dict

**Final Fix (Commit 7180dc6)**:
- Added "Hello Burrito": "HB" to main.py RESTAURANT_SHORTCUTS dict on line 105
- Result: ✅ Works! Shows "👩‍🍳 HB (2)" correctly

---

## Files Changed

1. **utils.py** - Added "Hello Burrito": "HB" to RESTAURANT_SHORTCUTS
2. **rg.py** - Added "Hello Burrito": "HB" to RESTAURANT_SHORTCUTS
3. **main.py** - Added /testhb command, added "Hello Burrito": "HB" to local RESTAURANT_SHORTCUTS dict
4. **AI-INSTRUCTIONS.md** - Updated VENDOR_GROUP_MAP documentation
5. **.github/copilot-instructions.md** - Updated VENDOR_GROUP_MAP and RESTAURANT_SHORTCUTS documentation

---

## Key Commits

- `1b173cd` - Initial implementation (added to utils.py, rg.py, /testhb command)
- `43b534c` - Fix: Import RESTAURANT_SHORTCUTS in main.py
- `503b878` - Debug: Add logging to trace configuration
- `f73eaa6` - Debug: Add detailed logging at shortcut lookup point
- `7180dc6` - **FINAL FIX**: Add "Hello Burrito" to main.py local RESTAURANT_SHORTCUTS dict

---

## Lessons Learned

**Issue**: Duplicate constant definitions across files with one overwriting imported value.

**Root Cause**: Python allows importing a name and then redefining it locally. The local definition on line 103 overwrote the import from line 76, causing mdg.py to receive an incomplete dict.

**Prevention**: 
- Search for ALL instances of a constant before adding it (use `grep -r "CONSTANT_NAME ="`)
- When adding to a dict, check if dict exists in multiple locations
- Debug logging at point of usage (not just point of definition) reveals runtime state

**Similar Pattern to Avoid**: If module A imports constant from module B, then redefines it locally, all functions in module A will use the local version. This can cause subtle bugs where "the code looks correct" but behavior is wrong.

---

## Outcome

✅ Hello Burrito restaurant fully integrated
✅ /testhb command working correctly
✅ MDG messages show "HB" shortcut
✅ RG messages routed to correct group (-5050234553)
✅ Documentation updated

**Test Results**: /testhb command generates test order showing "👩‍🍳 HB (2)" in MDG correctly.

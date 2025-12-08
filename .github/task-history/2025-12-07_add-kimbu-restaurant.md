# 📝 Task: Add Kimbu Restaurant

**Status**: Completed
**Started**: 2024-12-07 18:30
**Completed**: 2024-12-07 18:36
**Duration**: ~6 minutes

---

## Task Overview

Add new Shopify restaurant "Kimbu" with shortcut "KI" to all relevant locations in the codebase. User already added Kimbu to VENDOR_GROUP_MAP (Group ID: -5093377174) and redeployed Render.

---

## User Request (December 7, 2025 - 18:30)

```
New task: We need to add a new Shopify restaurant "Kimbu". I already added it to the VENDOR_GROUP_MAP and redeployed, the Group id is: -5093377174

The shortcut will be: "KI"

Make sure to add it everyhwerhe related (last time you failed to add the short cum in mdg.py somwhere and it was falling back to a wrong shortcut).

Also add the /testki for test orders (also with correct shortcut display). I will update BotFather's list of commands.
```

---

## Requirements

1. ✅ Add "Kimbu": "KI" to all RESTAURANT_SHORTCUTS dictionaries
2. ✅ Add /testki test command
3. ✅ Ensure mdg.py receives correct shortcut (user mentioned this was missed last time)
4. ✅ Follow existing test command pattern
5. ✅ User will update BotFather command list separately

---

## Analysis

### RESTAURANT_SHORTCUTS Locations Found

Searched codebase for all RESTAURANT_SHORTCUTS usage:

1. **utils.py** line 35-46 - Main definition (imported by other modules)
2. **rg.py** line 23-34 - Duplicate definition (used for RG-specific logic)
3. **main.py** line 103-114 - Duplicate definition (overwrites import from utils)

**Note**: mdg.py does NOT have its own RESTAURANT_SHORTCUTS dict. It receives the dict via `configure_mdg(STATE, RESTAURANT_SHORTCUTS)` call on main.py line 175, which passes main.py's dict. So fixing main.py line 103 automatically fixes mdg.py display.

### Test Command Pattern

Found existing test commands in main.py (lines 1994-2035):
- `/testpf` - PF photo test
- `/testjs` - Julis Spätzlerei
- `/testzh` - Zweite Heimat
- `/testka` - Kahaani
- `/testsa` - i Sapori della Toscana
- `/testlr` - Leckerolls
- `/testsf` - Safi
- `/testhb` - Hello Burrito

**Pattern**:
```python
if text.startswith("/testXX"):
    logger.info("=== TEST XX COMMAND DETECTED ===")
    run_async(handle_test_vendor_command(chat_id, "Full Vendor Name", msg.get('message_id')))
    return "OK"
```

---

## Implementation

### Changes Made

**1. utils.py** (line 45)
```python
# BEFORE:
RESTAURANT_SHORTCUTS = {
    "Julis Spätzlerei": "JS",
    "Zweite Heimat": "ZH",
    "Hello Burrito": "HB",
    "Kahaani": "KA",
    "i Sapori della Toscana": "SA",
    "Leckerolls": "LR",
    "dean & david": "DD",
    "Pommes Freunde": "PF",
    "Wittelsbacher Apotheke": "AP",
    "Safi": "SF"
}

# AFTER:
RESTAURANT_SHORTCUTS = {
    "Julis Spätzlerei": "JS",
    "Zweite Heimat": "ZH",
    "Hello Burrito": "HB",
    "Kahaani": "KA",
    "i Sapori della Toscana": "SA",
    "Leckerolls": "LR",
    "dean & david": "DD",
    "Pommes Freunde": "PF",
    "Wittelsbacher Apotheke": "AP",
    "Safi": "SF",
    "Kimbu": "KI"
}
```

**2. rg.py** (line 33)
```python
# BEFORE:
RESTAURANT_SHORTCUTS = {
    "Julis Spätzlerei": "JS",
    "Zweite Heimat": "ZH",
    "Hello Burrito": "HB",
    "Kahaani": "KA",
    "i Sapori della Toscana": "SA",
    "Leckerolls": "LR",
    "dean & david": "DD",
    "Pommes Freunde": "PF",
    "Wittelsbacher Apotheke": "AP",
    "Safi": "SF"
}

# AFTER:
RESTAURANT_SHORTCUTS = {
    "Julis Spätzlerei": "JS",
    "Zweite Heimat": "ZH",
    "Hello Burrito": "HB",
    "Kahaani": "KA",
    "i Sapori della Toscana": "SA",
    "Leckerolls": "LR",
    "dean & david": "DD",
    "Pommes Freunde": "PF",
    "Wittelsbacher Apotheke": "AP",
    "Safi": "SF",
    "Kimbu": "KI"
}
```

**3. main.py** (line 113)
```python
# BEFORE:
RESTAURANT_SHORTCUTS = {
    "Julis Spätzlerei": "JS",
    "Zweite Heimat": "ZH",
    "Hello Burrito": "HB",
    "Kahaani": "KA",
    "i Sapori della Toscana": "SA",
    "Leckerolls": "LR",
    "dean & david": "DD",
    "Pommes Freunde": "PF",
    "Wittelsbacher Apotheke": "AP",
    "Safi": "SF",
}

# AFTER:
RESTAURANT_SHORTCUTS = {
    "Julis Spätzlerei": "JS",
    "Zweite Heimat": "ZH",
    "Hello Burrito": "HB",
    "Kahaani": "KA",
    "i Sapori della Toscana": "SA",
    "Leckerolls": "LR",
    "dean & david": "DD",
    "Pommes Freunde": "PF",
    "Wittelsbacher Apotheke": "AP",
    "Safi": "SF",
    "Kimbu": "KI",
}
```

**4. main.py** (after line 2035)
```python
# ADDED:
            if text.startswith("/testki"):
                logger.info("=== TEST KI COMMAND DETECTED ===")
                run_async(handle_test_vendor_command(chat_id, "Kimbu", msg.get('message_id')))
                return "OK"
```

---

## Deployment

**Commit**: ab31c70  
**Message**: "Add new restaurant Kimbu (KI) to all RESTAURANT_SHORTCUTS and add /testki test command"

**Files Changed**:
- utils.py
- rg.py
- main.py
- .github/CURRENT-TASK.md

---

## Result

✅ **RESTAURANT_SHORTCUTS** now has 12 restaurants (was 11):
- Julis Spätzlerei (JS)
- Zweite Heimat (ZH)
- Hello Burrito (HB)
- Kahaani (KA)
- i Sapori della Toscana (SA)
- Leckerolls (LR)
- dean & david (DD)
- Pommes Freunde (PF)
- Wittelsbacher Apotheke (AP)
- Safi (SF)
- **Kimbu (KI)** ← NEW

✅ **Test commands** now include:
- /testpf, /testjs, /testzh, /testka, /testsa, /testlr, /testsf, /testhb, **/testki** ← NEW

✅ **All 3 dictionaries synchronized**:
- utils.py has "Kimbu": "KI"
- rg.py has "Kimbu": "KI"
- main.py has "Kimbu": "KI"

✅ **mdg.py will display correct shortcut**:
- mdg.py receives RESTAURANT_SHORTCUTS from main.py via configure_mdg() call
- No separate update needed in mdg.py

---

## User Actions Required

- ✅ User already added Kimbu to VENDOR_GROUP_MAP with Group ID: -5093377174
- ✅ User already redeployed Render with VENDOR_GROUP_MAP change
- 🔄 User will update BotFather's command list to include /testki

---

## Testing

User can test Kimbu functionality:
1. Send `/testki` command to bot → Creates test Kimbu order
2. Check MDG message → Should show "KI" shortcut in order header
3. Check RG message → Should show "KI" in vendor-specific messages
4. Check UPC message → Should show "KI" in courier assignment message

---

## Status

**COMPLETED** - All requested changes implemented and deployed. Kimbu restaurant fully integrated with shortcut "KI" and test command /testki.

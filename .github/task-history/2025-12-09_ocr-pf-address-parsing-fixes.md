# OCR PF Address Parsing Fixes - COMPLETE

**Date**: December 9, 2025  
**Status**: ✅ COMPLETE  
**Commits**: 7a3dee8, b2a92d3, 1967cdd, 4646ae6, 918fbe9, 9582e2d, d807cdc

---

## Summary

Fixed OCR parsing for Pommes Freunde Lieferando orders after user reported 3 test images failing:
1. P4B BW9: Address "60 Neuburger Straße" parsed as "Straße 60 Neuburger" (wrong order)
2. XGT HR6: Address "129 Göttweiger Str." not swapping to "Göttweiger Str. 129"
3. T6D C9V: Complete parse failure with customer name "É. Frowein-Hundertmark"

## Root Causes Identified

### Issue #1: P4B BW9 - Number-First Pattern Not Triggering
**Problem**: Original address parsing logic assumed building number AFTER street name detection.  
**OCR Text**: `"60 Neuburger Straße, 94032,"`  
**Result**: Loop processed "60" → number, "Neuburger" → number, "Straße" → street = WRONG

### Issue #2: XGT HR6 - Period Blocking Suffix Check
**Problem**: Line 234 checked `endswith(street_suffixes)` without stripping punctuation.  
**OCR Text**: `"129 Göttweiger Str., 94032, PA"`  
**Address Parts**: `['129', 'Göttweiger', 'Str.']` (note period!)  
**Logic**: `'Str.'.lower().endswith(('str', ...))` = FALSE (because 'str.' ≠ 'str')

### Issue #3: T6D C9V - Accented Characters Not Recognized
**Problem**: Customer name regex character class `[A-ZÄÖÜa-zäöüß]` didn't include French accents.  
**OCR Text**: `"É. Frowein-Hundertmark"`  
**Result**: Name starting with `É` (E-acute) not matched → `OCR_FAILED`

## Fixes Implemented

### Commit 918fbe9: Number-First Pattern Detection + Debug Logging
**File**: `ocr.py` lines 232-241

Added new pattern detection BEFORE original fallback logic:
```python
# Check for pattern: "Number Street" (e.g., "60 Neuburger Straße" or "129 Göttweiger Str.")
first_is_number = address_parts[0].replace('/', '').replace('.', '').isdigit()
last_has_suffix = address_parts[-1].lower().endswith(street_suffixes)

if first_is_number and last_has_suffix:
    number = address_parts[0]
    street = ' '.join(address_parts[1:])
    result['address'] = f"{street} {number}"
    logger.info(f"OCR Address parsed (number-first pattern): street='{street}', number='{number}'")
```

Also added comprehensive debug logging:
- Line 164: `logger.info(f"[OCR] phone_pos found: {phone_pos is not None}")`
- Lines 167-172: Log address_block source and length
- Line 177: Log first 150 chars of address_block
- Line 180: Log each address line processed
- Line 207: Log collected address_lines

**Result**: P4B BW9 fixed ✅

### Commit 9582e2d: Fix SyntaxError (Indentation)
**File**: `ocr.py` lines 278-284

Fixed indentation error from commit 918fbe9 - `elif` clause was at wrong level.

**Before**: `elif` at same indentation as parent `else:` block  
**After**: `elif` nested inside parent `else:` block (4 spaces indent)

### Commit d807cdc: Strip Period + Add Accented Characters
**File**: `ocr.py` lines 151, 234

**Fix #1** - Line 234: Added `.rstrip('.')` to strip period before suffix check:
```python
# OLD:
last_has_suffix = address_parts[-1].lower().endswith(street_suffixes)

# NEW:
last_has_suffix = address_parts[-1].lower().rstrip('.').endswith(street_suffixes)
```

**Result**: XGT HR6 fixed ✅

**Fix #2** - Line 151: Added `ÉÈÊÀéèêà` to customer name regex (3 locations):
```python
# OLD character class:
[A-ZÄÖÜa-zäöüß]

# NEW character class:
[A-ZÄÖÜÉÈÊÀa-zäöüéèêàß]
```

**Result**: T6D C9V fixed ✅

## Security Incident (Resolved)

### Commit 7a3dee8: Initial Phone/Note Fixes (EXPOSED SECRETS!)
- Fixed phone regex to allow newlines: `\s*` instead of `[^\S\n]*`
- Fixed note extraction to check quoted text without emoji
- **CRITICAL**: Accidentally committed `.github/Temp logs` file with exposed bot token

### Commits b2a92d3 + 1967cdd: Security Cleanup
- Removed exposed file
- Updated .gitignore: `*.log`, `Temp*`, `*logs`, `.github/Temp*`
- User rotated bot token immediately
- Updated Render environment variable + webhook URL

**Old Token** (REVOKED): `7064983715:AAHJGuW59Hi3ZYZjmP64GZYHYYSxdPQWXh8`  
**New Token** (ACTIVE): `7064983715:AAFJft6aEZ12Wnc7eYEh9qhTSpcqv4WWW4c`

## Final Test Results

All 3 test images parse correctly with proper address format:

**P4B BW9**: `🗺️ [Neuburger Straße 60 (94032)](...)`  
**XGT HR6**: `🗺️ [Göttweiger Str. 129 (94032)](...)`  
**T6D C9V**: `🗺️ [Dr.-Hans-Kapfinger-Straße 32 (94032)](...)` with customer "É. Frowein-Hundertmark"

## Lessons Learned

1. **Pattern #17 Avoided**: Read actual OCR text structure before implementing regex
2. **Pattern #20 Avoided**: Traced actual code flow through logs before proposing fixes
3. **Security**: Never commit log files - comprehensive .gitignore essential
4. **Visual Results Required**: Must read actual code (mdg.py, rg.py) to show UI formats, not hallucinate
5. **Surgical Changes**: Each fix touched only failing logic, preserved working code

## Files Modified

- `ocr.py`: Address parsing logic (lines 151, 232-241, 234), debug logging (lines 164-207)
- `.gitignore`: Added log file patterns
- Environment: Rotated bot token, updated Render + webhook

## Related Documentation

- `STATE_SCHEMA.md`: No changes needed (no new STATE fields)
- `docs/WORKFLOWS.md`: No changes needed (workflows unchanged)
- `docs/MESSAGES.md`: No changes needed (message formats unchanged)

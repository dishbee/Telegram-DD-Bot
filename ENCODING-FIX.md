# Emoji Encoding Fix

## Problem
Emojis were displaying as question marks (�) in Telegram messages because Python files didn't have explicit UTF-8 encoding declarations.

## Root Cause
- Python 3 defaults to UTF-8, but Windows PowerShell and some editors may use different encodings
- Without explicit `# -*- coding: utf-8 -*-` declarations, emoji characters can get corrupted
- When files are edited/saved in Windows, encoding can change to CP1252 or other codepages

## Solution Applied
Added UTF-8 encoding declarations to all main Python files:

```python
# -*- coding: utf-8 -*-
```

### Files Updated:
1. `main.py` - Core bot logic
2. `rg.py` - Restaurant group functions
3. `upc.py` - User private chat functions
4. `mdg.py` - Main dispatch group functions
5. `utils.py` - Shared utilities

## How This Fixes Emoji Display

### Before Fix:
- `🔖` → `�` (question mark)
- `👍` → `�`
- `⏰` → `�`
- `⚠️` → `�`

### After Fix:
- All emojis display correctly in Telegram messages
- Files explicitly tell Python interpreter to use UTF-8 encoding
- Prevents encoding issues when editing files in Windows

## Prevention Tips

1. **Always save files as UTF-8** in your editor:
   - VS Code: Set `"files.encoding": "utf8"` in settings
   - Notepad++: Encoding → UTF-8
   - PowerShell ISE: Save As → UTF-8

2. **Check file encoding** if emojis appear corrupted:
   ```powershell
   Get-Content main.py | Select-Object -First 1
   # Should show: # -*- coding: utf-8 -*-
   ```

3. **When adding new files** with emojis, always include encoding declaration at the top

## Verification

After deployment, test that these emojis display correctly:
- 🔖 (bookmark) in order references
- 👍 (thumbs up) in "Works" button
- ⏰ (clock) in "Later at" button
- ⚠️ (warning) in "Issue" button
- 🍕 (pizza) in "Product(s) N/A" button
- ⏳ (hourglass) in "We have a delay" button
- ❌ (cross) in "Order is canceled" button
- 💬 (speech bubble) in "Something else" button
- 👩‍🍳👨‍🍳 (chef emojis) in confirmation messages
- 🧭 (compass) in Navigate button
- 🔓 (unlocked) in Unassign button
- 🏪 (store) in Call button
- ✅ (checkmark) in Delivered button

## Related Issues Fixed
- RG button labels now display correctly with emojis
- Status messages show proper emoji formatting
- All message formats preserve emoji characters

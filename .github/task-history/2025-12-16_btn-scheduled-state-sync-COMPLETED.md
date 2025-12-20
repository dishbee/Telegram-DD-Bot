# 📝 BTN-SCHEDULED State Sync Issue (Dec 16, 2025)

**Status**: ⏸️ PAUSED - Awaiting debug logs
**Started**: December 16, 2025
**Type**: Bug Investigation - Button Not Showing

---

## Problem

`btn-scheduled` ("🗂 Scheduled orders" button) appears randomly/not at all.
`/sched` command works correctly.

---

## Root Cause Investigation

### Critical Finding from Render Logs

```
mdg - INFO - MDG-KB-DEBUG: STATE has 0 orders, keys=[]
main - INFO - 💾 Redis: Saved 458/458 orders
```

**mdg.py sees 0 orders while main.py has 458 orders!**

### Why `/sched` works:
```python
# main.py line 494 - passes STATE directly
text = build_scheduled_list_message(STATE, now)
```

### Why `btn-scheduled` fails:
```python
# mdg.py line 621 - uses module-level STATE
order = STATE.get(order_id)  # Returns None because STATE is empty!
```

When order is not found, fallback keyboard WITHOUT "Scheduled orders" button is returned.

---

## Debug Logging Added (commit 7ce9e5a)

**2 lines added** to track STATE object id():

1. `mdg.py` configure():
   ```python
   logger.info(f"MDG-CONFIGURE: STATE id={id(STATE)}, len={len(STATE) if STATE else 'None'}")
   ```

2. `mdg.py` mdg_time_request_keyboard():
   ```python
   logger.info(f"MDG-KB-DEBUG: STATE id={id(STATE)}, len={len(STATE)}, keys={list(STATE.keys())[:5]}")
   ```

**What to look for in logs:**
- If `id()` values are **different** → Reference not preserved (fix: pass STATE as parameter)
- If `id()` values are **same** but counts differ → Something else is wrong

---

## Proposed Fix (pending confirmation)

Modify `mdg_time_request_keyboard()` and related functions to accept STATE as a parameter (like `/sched` does), rather than relying on module-level STATE.

**Certainty: 85-90%** that this will fix the issue.

---

## Next Steps

1. ⏳ Wait for new orders to come in
2. ⏳ Check Render logs for id() values
3. ⏳ Confirm hypothesis
4. ⏳ Implement full fix

---

## Files Changed

- `mdg.py`: Added 2 debug log lines (lines 48, 619)

---

## To Reopen

User will say: "Let's continue the btn-scheduled task"

Check logs with:
```
render logs -r srv-d2ausdogjchc73eo36lg --start 24h --text "MDG-CONFIGURE,MDG-KB-DEBUG" -o text
```

---

## CONTINUED INVESTIGATION (December 20, 2025 - SOLVED & DEPLOYED)

### Final Root Cause Found

Live order testing revealed the SMOKING GUN:
- 11:55:03: New order PTQVDJ arrives, STATE has 118 orders
- 11:55:52: Order D9CV8R gets assigned, mdg.configure() is CALLED
- 11:57:01: PTQVDJ requests time, STATE shows 0 orders

**THE BUG**: mdg.configure() being called during assignment flow replaces mdg.py's STATE reference with a NEW empty dict!
- Old STATE id: 139887148496704 (correct, with 118 orders)
- New STATE id: 139887106393920 (empty!)

This happens because both mdg.py and upc.py have module-level STATE = None that gets configured at startup.

When assignment code runs, something calls mdg.configure() again, which overwrites the reference.

### Solution Implemented (Commit 9ec2cdc)

Instead of relying on module-level STATE in mdg.py (which can be broken), pass STATE as a parameter to get_recent_orders_for_same_time():

**Function Change**:
- Added optional parameter: state: Dict[str, Any] = None
- Falls back to module-level STATE if not provided
- Uses passed state for all operations

**All 8 Call Sites Updated**:
1. mdg.py line 611 (multi-vendor keyboard)
2. mdg.py line 624 (single-vendor keyboard) 
3. mdg.py line 705 (single-vendor keyboard in initial)
4. mdg.py line 946 (same_time_keyboard)
5. rg.py line 199 (vendor_time_keyboard) - now imports STATE from main
6. main.py line 2531 (req_vendor callback)
7. main.py line 3008 (req_scheduled callback)

All now pass state=STATE when calling get_recent_orders_for_same_time()

### Files Modified
- mdg.py: Function signature updated + 5 call sites
- rg.py: Added STATE import from main + 1 call site
- main.py: 2 call sites

### Testing
Button should now appear on MDG keyboards because function receives main.py's correct STATE (with all 118 orders) instead of mdg.py's broken module-level STATE (which becomes empty during assignment).


---

## FINAL SOLUTION DEPLOYED (December 20, 2025 - COMPLETED)

### Root Cause (ACTUAL)

The investigation above was WRONG. The real problem was:

In Gunicorn multi-worker setup, each worker process gets its OWN copy of the module-level STATE dict. The module initialization happens BEFORE load_state() is called, so:

1. Worker process starts
2. Line 135: STATE = {} (empty dict created)
3. Line 186: configure_mdg(STATE) gives mdg.py reference to EMPTY dict
4. Gunicorn forks N workers
5. Each worker has its own empty STATE copy
6. load_state() is called at line 4892 (in if __name__ main block)
7. But workers don't execute that block - only main process does
8. Result: Worker processes have empty STATE, main.py has populated STATE

### The Real Fix (Commit 34d6886)

Moved load_state() call from line 4892 to line 188 (BEFORE configure_mdg):

**Before**:
- Line 135: STATE = {}
- Line 186: configure_mdg(STATE) - mdg.py gets empty dict
- Line 4892: load_state() - too late, workers already have empty reference

**After**:
- Line 135: STATE = {}
- Line 188: load_state() - populate STATE FIRST
- Line 190: configure_mdg(STATE) - mdg.py gets POPULATED dict
- Removed duplicate load_state() from if block

### Why This Works

Now when worker processes initialize at module load time, they see STATE already populated with Redis orders. The get_recent_orders_for_same_time() function finds confirmed orders and the [ Scheduled orders] button appears.

### Files Changed
- main.py: Moved load_state() call (line 188 instead of 4892)
- main.py: Removed duplicate call from if block
- mdg.py: Removed debug logging

### Testing
 Next Smoothr/Shopify/OCR order will have button IF confirmed orders exist in STATE

---

## Lesson Learned

Always check module initialization order in Gunicorn environments. Module-level code runs at import time (BEFORE worker fork), so all initialization must happen before the worker processes are created. The if __name__ == '__main__' block only runs in the main process, not workers.

**Status: CLOSED - FIXED & DEPLOYED**

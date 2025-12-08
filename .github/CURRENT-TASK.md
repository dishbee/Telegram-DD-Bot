#  Current Active Task

**Status**:  READY FOR NEW TASK
**Last Updated**: 2025-12-08

---

## Previous Task: Code Quality Improvements (COMPLETE)

**Saved to**: `.github/task-history/2025-12-08_code-quality-improvements.md`

**Summary**:
-  Phase 1: Added `[ORDER-XX]` request ID logging (14 locations) - DEPLOYED
-  Phase 2: Created STATE_SCHEMA.md with 60+ field documentation - DEPLOYED
-  Phase 3: Extracted magic numbers to constants (64, 30, 50, 200) - DEPLOYED
-  Updated documentation (AI-INSTRUCTIONS.md, copilot-instructions.md, WORKFLOWS.md, MESSAGES.md)
-  Fixed year to 2025 in all task-history files

**Commits**:
- `38dd47c` - Phase 1: Request ID logging
- `289e20c` - Phases 2 & 3: STATE_SCHEMA.md + magic number constants
- `0195d4e` - Documentation updates and year corrections

---

## Ready for Next Task

Waiting for new assignment...

##  User Request (December 8, 2025 - 14:26)

```
Follow the instrctions.

I noticed, that copilot-instructions still has outdated parts. This for example:

### 3. Assignment Confirmation Message Format
Enhanced vendor confirmation message showing detailed breakdown:
```
 #58 - dishbee (JS+LR)
 Restaurants confirmed:
 Julis Spätzlerei: 12:50  1
 Leckerolls: 12:55  3
```
- Shows vendor shortcuts in header
- Lists each vendor with confirmed time and product count
- Singular/plural title based on vendor count

// Update this, in ai-instructions and MESSAGES and WORKFLOWS it was alread updated, you can use that. Check also all other parts, if they are outdated, update them, replace or remove completely - if they are not actually needed in the instructions file. copilot-instructions should be more or less the same as ai-instructions, but you decide if there should be something different in copilot-instructions file.
```

**Agent Response**: Starting NEW TASK - Update copilot-instructions.md to remove outdated content and sync with ai-instructions.md


**Changes Made**:
- Removed outdated 'Assignment Confirmation Message Format' section (format no longer exists)
- Updated State Corruption section: Changed 'server restart' to 'Redis persistence with 7-day TTL'
- Fixed field name: 'vendor_messages'  'rg_message_ids'
- Updated Memory Leaks section to reflect Redis persistence and auto-cleanup
- Added Kimbu (KI) to RESTAURANT_SHORTCUTS
- Synced DEPLOYMENT CONTEXT: Changed 'TEST ENVIRONMENT' to 'LIVE ENVIRONMENT' to match AI-INSTRUCTIONS.md
- Updated 'When You Fuck Up' section to match AI-INSTRUCTIONS.md

**Status**: Ready to commit

# 📚 Documentation Index

Welcome to the Telegram Dispatch Bot documentation! This index helps you find the right document for your needs.

---

## 🎯 Quick Start

**New to the system?** Start here:
1. Read **QUICK-REF.md** (2 minutes) - Learn the shortcuts
2. Skim **FLOW-DIAGRAMS.md** (5 minutes) - Understand workflows
3. Bookmark **SYSTEM-REFERENCE.md** - Your complete guide

---

## 📄 Documentation Files

### ⚡ QUICK-REF.md
**For:** Daily use, fast lookups  
**Contains:**
- Most common message types (MDG-ORD, UPC-ASSIGN, etc.)
- Frequently used buttons (BTN-ASSIGN-ME, BTN-WORKS, etc.)
- Quick debugging reference
- Communication templates
- Restaurant shortcuts

**When to use:**
- "What's the code for that assignment button?"
- "How do I reference the vendor confirmation message?"
- "Quick, what's the Leckerolls shortcut?"

---

### 📖 SYSTEM-REFERENCE.md
**For:** Complete system knowledge  
**Contains:**
- All message types with codes
- All button types with callback formats
- All functions with descriptions
- Complete STATE field reference
- Callback action map (50+ actions)
- Environment variables
- Usage examples

**When to use:**
- Planning new features
- Debugging complex issues
- Understanding STATE structure
- Looking up callback data formats
- Checking function locations

---

### 📊 FLOW-DIAGRAMS.md
**For:** Visual understanding  
**Contains:**
- Order lifecycle diagram
- Multi-vendor flow
- Assignment system architecture
- Time selection flow
- Courier action flow
- Duplicate prevention logic
- Message cleanup flow
- Product name cleaning pipeline
- STATE lifecycle

**When to use:**
- Understanding how workflows connect
- Explaining system to others
- Debugging flow issues
- Planning workflow changes
- Seeing the big picture

---

### 🤖 .github/copilot-instructions.md
**For:** AI agent guidance  
**Contains:**
- Critical communication rules
- Failure patterns to avoid
- Architecture overview
- State management
- Recent major additions
- Common gotchas

**When to use:**
- Working with AI assistants
- Understanding system constraints
- Learning from past mistakes
- Onboarding new AI agents

---

## 🔍 Find What You Need

### "I want to change a message"
1. **QUICK-REF.md** - Find message code (e.g., MDG-CONF)
2. **SYSTEM-REFERENCE.md** - Look up builder function (e.g., FN-MDG-CONF)
3. **FLOW-DIAGRAMS.md** - See where message fits in workflow

### "Button isn't working"
1. **QUICK-REF.md** - Find button code (e.g., BTN-WORKS)
2. **SYSTEM-REFERENCE.md** - Check callback action format
3. **FLOW-DIAGRAMS.md** - Verify button position in flow

### "Need to debug STATE"
1. **QUICK-REF.md** - Common STATE fields
2. **SYSTEM-REFERENCE.md** - Complete STATE structure
3. **FLOW-DIAGRAMS.md** - STATE lifecycle diagram

### "Planning a new feature"
1. **FLOW-DIAGRAMS.md** - See current workflows
2. **SYSTEM-REFERENCE.md** - Check available functions
3. **QUICK-REF.md** - Assign shortcuts for new elements

### "Understanding assignment system"
1. **FLOW-DIAGRAMS.md** - Assignment architecture diagram
2. **SYSTEM-REFERENCE.md** - FN-GET-COURIERS, FN-SEND-ASSIGN details
3. **.github/copilot-instructions.md** - Recent additions section

---

## 💡 Documentation Best Practices

### When Communicating Issues
```
Bad:  "The button doesn't work"
Good: "BTN-WORKS not updating confirmed_times in STATE"
```

### When Requesting Changes
```
Bad:  "Make the message show more info"
Good: "Add product count to RG-SUM like MDG-CONF does"
```

### When Asking Questions
```
Bad:  "Why isn't this showing up?"
Good: "Why doesn't FN-CHECK-CONF trigger after BTN-WORKS?"
```

---

## 📝 Documentation Maintenance

### Adding New Features

1. **Choose shortcuts** (follow naming pattern)
   - Messages: `{CHANNEL}-{TYPE}` (e.g., MDG-DELAY-CONF)
   - Buttons: `BTN-{ACTION}` (e.g., BTN-CALL-VENDOR)
   - Functions: `FN-{PURPOSE}` (e.g., FN-SEND-DELAY)

2. **Update SYSTEM-REFERENCE.md**
   - Add to appropriate table
   - Include callback format
   - Document STATE changes

3. **Update QUICK-REF.md** (if commonly used)
   - Add to relevant section
   - Include use case

4. **Update FLOW-DIAGRAMS.md** (if workflow changes)
   - Modify existing diagram
   - Add new diagram if major feature

5. **Update .github/copilot-instructions.md**
   - Add to "Recent Major Additions"
   - Note any gotchas

---

## 🎓 Learning Path

### Beginner (Day 1)
- [ ] Read QUICK-REF.md
- [ ] Glance at FLOW-DIAGRAMS.md (order lifecycle)
- [ ] Understand MDG, RG, UPC channels

### Intermediate (Week 1)
- [ ] Study SYSTEM-REFERENCE.md (message types)
- [ ] Review FLOW-DIAGRAMS.md (all diagrams)
- [ ] Learn STATE structure

### Advanced (Month 1)
- [ ] Master SYSTEM-REFERENCE.md (all functions)
- [ ] Understand all callback actions
- [ ] Can modify any workflow

---

## 🔗 File Locations

```
Telegram-DD-Bot/
├── QUICK-REF.md              ⚡ Daily reference
├── SYSTEM-REFERENCE.md       📖 Complete guide
├── FLOW-DIAGRAMS.md          📊 Visual workflows
├── DOCUMENTATION-INDEX.md    📚 This file
├── .github/
│   └── copilot-instructions.md  🤖 AI guidance
├── main.py                   🐍 Core webhook logic
├── mdg.py                    📱 MDG functions
├── rg.py                     🏪 RG functions
├── upc.py                    👤 UPC functions
└── utils.py                  🔧 Utilities
```

---

## 🆘 Still Can't Find It?

1. **Search all docs**: Look for keyword across all MD files
2. **Check function comments**: Look in actual code files
3. **Ask with context**: Use shortcuts to describe what you need

Example:
```
"Looking for function that builds MDG-COURIER-SEL keyboard.
Checked SYSTEM-REFERENCE.md under 'Keyboard Builders' but
need to know what STATE fields it requires."
```

---

## 📊 Documentation Stats

- **Total shortcuts**: 100+
- **Message types**: 20+
- **Button types**: 30+
- **Functions**: 25+
- **Callback actions**: 50+
- **Diagrams**: 10+

---

**Last Updated**: October 3, 2025  
**Maintained by**: AI Agents + Human Review

---

## 💬 Quick Communication Examples

### Report Bug
```
"BTN-ASSIGN-TO shows 1 courier instead of 4.
FN-GET-COURIERS might not be getting all MDG admins.
See FLOW-DIAGRAMS.md Assignment System diagram."
```

### Request Feature
```
"Add BTN-CALL-CUSTOMER to UPC-ASSIGN.
Should use customer.phone from STATE.
Similar to existing BTN-NAV implementation."
```

### Ask Question
```
"Does FN-CLEANUP delete MDG-ORD message?
Checking mdg_additional_messages array tracking.
See SYSTEM-REFERENCE.md STATE section."
```

---

**Remember**: Clear shortcuts = Fast communication = Better results! 🚀

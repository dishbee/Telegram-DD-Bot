# 🔖 MANDATORY PRE-IMPLEMENTATION CHECKLIST

**Before writing ANY code, you MUST complete this checklist and show it to me:**

---

## 1️⃣ TRACE THE ACTUAL CODE FLOW

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

---

## 2️⃣ WHAT EXACTLY ARE YOU CHANGING?

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

---

## 3️⃣ WHAT COULD THIS BREAK?

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

---

## 4️⃣ SHOW DIFF ONLY - NO EXPLANATIONS

**Use this exact format:**

````diff
--- a/filename.py
+++ b/filename.py
@@ -line,count +line,count @@
-old code
+new code
 unchanged context
````

**Rules:**
- Show ONLY the actual code changes
- Include 3 lines of context before/after
- NO prose explanations mixed in
- NO "this will fix..." comments
- Just the diff

---

## 5️⃣ FINAL CONFIRMATION

**Answer these YES/NO questions:**

- [ ] Did I trace the FULL code path through all files?
- [ ] Am I changing ONLY what was requested?
- [ ] Did I check for circular imports and STATE corruption?
- [ ] Did I list 3 specific things this could break?
- [ ] Is my diff clean with NO extra changes?
- [ ] Did I verify callback data formats won't break old buttons?

**If ANY answer is NO, you must STOP and redo the checklist.**

---

**CRITICAL CONTEXT:**
- This is a TEST environment - fixing properly > reverting quickly
- User is non-technical and CANNOT fix your mistakes
- You have broken this bot 10+ times by skipping these checks
- You claim to understand but pattern-match instead of actually tracing code
- You bundle changes together and break working functionality
- You ignore instructions repeatedly despite promises

**Your response MUST start with the completed checklist above. If you skip straight to code, I will reject it.**

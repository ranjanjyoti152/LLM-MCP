# Quick Prompt Templates

> Copy-paste these into any AI chat to trigger specific memory workflows.

---

## 🧠 Start With Memory

> Use at the beginning of any conversation:

```
Before we start, load my memory:
1. Call get_working_context() to see my current session
2. Call recall("my preferences and recent work") to load what you know about me
3. Greet me by name if you know it, and reference what I was last working on
```

---

## 💾 Remember This

> Use when you want the AI to save something specific:

```
Remember this: [your fact/preference/decision]
Save it using save_knowledge_smart with the right category and importance.
```

---

## 🔍 What Do You Know?

> Use to query all memories about a topic:

```
What do you remember about [topic]?
Use recall("[topic]") to search all memory types, then present organized results.
```

---

## 🐛 Debug With Memory

> Use when starting a debugging session:

```
I'm debugging: [error description]
First recall any past similar bugs, then check saved code patterns,
then help me fix it. Save the solution when we're done.
```

---

## 📋 End & Save

> Use at the end of a productive conversation:

```
Let's wrap up. Please:
1. Save this conversation with a good title and summary
2. Extract any preferences or facts I mentioned
3. Consolidate any important short-term memories
4. Tell me what you saved
```

---

## 👋 Onboard Me

> Use for first-time setup:

```
I'm new here. Interview me about my coding preferences, tools, projects,
and working style. Save everything you learn so all my AI assistants know me.
```

---

## 🔧 Memory Maintenance

> Use periodically to keep memory clean:

```
Run a memory health check:
1. Show me memory_health() stats
2. Clean up expired memories
3. Consolidate short-term to long-term
4. Check for any cross-platform conflicts
5. Report what you found
```

---

## ⚔️ Fix Conflicts

> Use when platforms disagree:

```
Check for memory conflicts between my AI platforms.
Show me what's conflicting and recommend how to resolve each one.
```

---

## ⏪ Undo a Change

> Use when a memory was incorrectly updated:

```
Show me the version history for knowledge ID: [uuid]
Then rollback to the version that looks correct.
```

---

## 🏗️ Save Project

> Use when starting work on a project:

```
I'm working on a project called [name].
Tech stack: [list technologies]
Repo: [url if applicable]
Description: [what it does]
Save this as project context so all my AI assistants know about it.
```

---

## 💻 Save Code Pattern

> Use when you have reusable code:

```
Save this code pattern for future reference:
Title: [descriptive title]
Language: [language]
```python
[your code here]
```
Description: [when to use this pattern]
Tags: [relevant tags]
```

---

## 📊 Memory Stats

> Quick overview of what's stored:

```
Show me my memory stats: how many conversations, knowledge entries,
code snippets, and active short-term memories I have. Which platforms
have been most active?
```

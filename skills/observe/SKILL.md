---
name: observe
description: Force extraction of observations from the current conversation into observational memory
disable-model-invocation: true
argument-hint: "[optional: specific topic to focus on]"
---

# Observe — Extract Observations from Current Conversation

You are being asked to manually extract observations from the current conversation and save them to the observational memory system.

## Steps

1. **Determine the memory directory** by running:
   ```bash
   python3 -c "import os; print(os.path.expanduser('~/.claude/projects/' + os.getcwd().replace('/','-') + '/memory/'))"
   ```

2. **Read the current observations file** at that path (`observations.md`). If it doesn't exist, you'll create it.

3. **Review the current conversation** and extract observations following these rules:

### Observation Format
```
Date: YYYY-MM-DD
- HH:MM Observation text
  - HH:MM Sub-detail
```

### What to Extract
- 🔴 **High priority**: User-stated facts, decisions, preferences, project structure, tech stack
- 🟡 **Medium priority**: Implementation details, files modified, debugging context
- 🟢 **Low priority**: Exploratory questions, tentative ideas

### Rules
- Distinguish **assertions** ("User stated X") from **questions** ("User asked about Y")
- Use absolute dates/times
- Track state changes: "Changed X to Y (previously Z)"
- Preserve specifics: file paths, versions, package names, error messages
- Record outcomes not processes: "Created auth middleware at src/auth.ts" not "Read file, edited file..."
- Capture decisions WITH rationale
- Do NOT repeat anything already in the observations file

4. **Append new observations** to the observations file. Do not overwrite existing content.

5. **Show the user** what was observed with a brief summary.

If `$ARGUMENTS` is provided, focus your observations specifically on that topic.

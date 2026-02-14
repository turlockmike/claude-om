---
name: reflect
description: Compress and reorganize observational memory, condensing old observations
disable-model-invocation: true
---

# Reflect — Compress Observational Memory

Condense and reorganize the observations file, producing a more compact version that preserves essential information.

## Steps

1. **Determine the memory directory** by running:
   ```bash
   python3 -c "import os; print(os.path.expanduser('~/.claude/projects/' + os.getcwd().replace('/','-') + '/memory/'))"
   ```

2. **Read the observations file** (`observations.md`) from that directory.

3. **If the file is small** (under ~2000 chars), inform the user that reflection isn't needed yet.

4. **Perform reflection** by reorganizing the observations:

### Reflection Rules
- **Merge related observations** across dates into unified entries
- **Condense by age**:
  - Last 3 days: keep full detail
  - Last 2 weeks: moderate compression
  - Older: aggressive compression, essential facts only
- **Always preserve**: user preferences, project architecture, tech stack, file paths, unresolved issues
- **Safe to drop**: resolved debugging, abandoned approaches, intermediate steps, answered questions
- **Resolve state changes**: keep only final state with brief history
- **User assertions override** inferred information
- **Target ~50% reduction** in size

### Output Structure
```
## Project Context
- [consolidated project facts]

## User Preferences
- [consolidated preferences]

## Recent Activity
Date: YYYY-MM-DD
- Recent observations...
```

5. **Before writing**, show the user:
   - Current size vs projected size
   - What will be dropped or merged
   - Ask for confirmation

6. **After confirmation**:
   - Archive the current observations by appending to `reflections.log` in the same directory
   - Write the reflected version to `observations.md`
   - Show a summary of the compression results

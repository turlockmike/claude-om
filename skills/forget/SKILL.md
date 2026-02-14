---
name: forget
description: Remove specific observations from long-term memory
disable-model-invocation: true
argument-hint: "[topic or pattern to forget]"
---

# Forget — Remove Observations from Memory

Remove specific observations from the observational memory system.

## Steps

1. **Determine the memory directory** by running:
   ```bash
   python3 -c "import os; print(os.path.expanduser('~/.claude/projects/' + os.getcwd().replace('/','-') + '/memory/'))"
   ```

2. **Read the observations file** (`observations.md`) from that directory.

3. **If no arguments provided** (`$ARGUMENTS` is empty):
   - Show the current observations
   - Ask the user what they want to forget

4. **If a topic is provided** (`$ARGUMENTS`):
   - Find all observations related to the topic
   - Show the matching observations to the user
   - Ask for confirmation before removing

5. **After confirmation**:
   - Remove the matching observations from `observations.md`
   - Preserve all non-matching observations with their structure intact
   - Write the updated file

6. **Also check** `MEMORY.md` for any related entries and offer to remove those too.

7. **Confirm** what was removed and what remains.

Important: Always ask for confirmation before deleting any observations. Show exactly what will be removed.

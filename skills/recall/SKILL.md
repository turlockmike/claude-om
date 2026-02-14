---
name: recall
description: Search and display observations from long-term observational memory
argument-hint: "[optional: search topic]"
---

# Recall — Search Observational Memory

Retrieve and display observations from the observational memory system.

## Steps

1. **Determine the memory directory** by running:
   ```bash
   python3 -c "import os; print(os.path.expanduser('~/.claude/projects/' + os.getcwd().replace('/','-') + '/memory/'))"
   ```

2. **Read the observations file** (`observations.md`) from that directory.

3. **If no arguments provided** (`$ARGUMENTS` is empty):
   - Display all observations, formatted cleanly
   - Show stats: total size, approximate token count, date range covered

4. **If a search topic is provided** (`$ARGUMENTS`):
   - Search through observations for entries matching the topic
   - Show matching observations with their dates and context
   - If no matches found, say so and suggest related topics from the observations

5. **Also check** `MEMORY.md` in the same directory for any related curated facts.

6. Present the results in a clear, organized format.

#!/usr/bin/env python3
"""
Observational Memory — Context Loader
Claude Code SessionStart hook that injects observations into context.
"""

import json
import sys
import os
import re
from datetime import datetime, timezone
from pathlib import Path

MAX_CONTEXT_CHARS = 60000


def get_project_dir(transcript_path):
    """Extract the project directory from the transcript path."""
    match = re.search(r'(.*?/\.claude/projects/[^/]+)', transcript_path)
    if match:
        return Path(match.group(1))
    return Path(transcript_path).parent


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    transcript_path = input_data.get('transcript_path', '')
    if not transcript_path:
        sys.exit(0)

    project_dir = get_project_dir(transcript_path)
    memory_dir = project_dir / 'memory'
    obs_file = memory_dir / 'observations.md'

    if not obs_file.exists() or obs_file.stat().st_size == 0:
        sys.exit(0)

    observations = obs_file.read_text()
    if not observations.strip():
        sys.exit(0)

    char_count = len(observations)
    approx_tokens = char_count // 4

    # Truncate if too large — keep most recent (end of file)
    if char_count > MAX_CONTEXT_CHARS:
        observations = (
            "[... older observations truncated ...]\n\n"
            + observations[-MAX_CONTEXT_CHARS:]
        )

    # Get last modified time
    try:
        mtime = datetime.fromtimestamp(obs_file.stat().st_mtime, tz=timezone.utc)
        last_updated = mtime.strftime('%Y-%m-%d %H:%M UTC')
    except Exception:
        last_updated = 'unknown'

    # Load task continuity from observer state
    state_file = memory_dir / '.observer-state.json'
    current_task = None
    suggested_response = None
    try:
        if state_file.exists():
            state = json.loads(state_file.read_text())
            current_task = state.get('current_task')
            suggested_response = state.get('suggested_response')
    except (json.JSONDecodeError, IOError):
        pass

    # Build continuity section
    continuity = ''
    if current_task or suggested_response:
        continuity = '\n### Task Continuity (from last session)\n'
        if current_task:
            continuity += f'- **Last task**: {current_task}\n'
        if suggested_response:
            continuity += f'- **Suggested next step**: {suggested_response}\n'

    context = f"""## Observational Memory

The following observations were automatically extracted from your previous conversations with this user. They represent your long-term memory across sessions.

<observations>
{observations}
</observations>
{continuity}
### How to use these observations:
- Reference specific details from observations when relevant to the current task
- Prefer the MOST RECENT information when observations conflict
- If an observation mentions a planned action with a past date, assume it was completed unless told otherwise
- These observations supplement (don't replace) any MEMORY.md content
- New observations will be automatically extracted after this session ends

Observation stats: ~{approx_tokens} tokens, last updated: {last_updated}"""

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context
        }
    }
    print(json.dumps(output))


if __name__ == '__main__':
    main()

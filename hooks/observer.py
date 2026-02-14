#!/usr/bin/env python3
"""
Observational Memory — Observer
Claude Code async Stop hook that extracts observations from conversation transcripts.
Adapted from Mastra's Observational Memory system for Claude Code.

Uses `claude -p` for LLM calls — no API key needed.
"""

import json
import sys
import os
import subprocess
import re
from datetime import datetime, timezone
from pathlib import Path

# --- Configuration ---
# Minimum new content (chars) before triggering observation
MIN_NEW_CONTENT_CHARS = 2000
# Maximum observations file size (chars) before triggering reflection
REFLECTION_THRESHOLD_CHARS = 40000
# Model shorthand for claude CLI
OBSERVER_MODEL = os.environ.get("OM_OBSERVER_MODEL", "haiku")
REFLECTOR_MODEL = os.environ.get("OM_REFLECTOR_MODEL", "haiku")

# Script directory for locating prompts
SCRIPT_DIR = Path(__file__).resolve().parent


def get_project_dir(transcript_path):
    """Extract the project directory from the transcript path."""
    match = re.search(r'(.*?/\.claude/projects/[^/]+)', transcript_path)
    if match:
        return Path(match.group(1))
    return Path(transcript_path).parent


def get_memory_dir(transcript_path):
    """Derive the project memory directory from transcript path."""
    project_dir = get_project_dir(transcript_path)
    memory_dir = project_dir / 'memory'
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir


def read_transcript(path):
    """Read and parse a JSONL transcript file."""
    messages = []
    try:
        with open(path, 'r') as f:
            for line_num, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    entry['_line_num'] = line_num
                    messages.append(entry)
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return messages


def extract_text_content(entry):
    """Extract human-readable text from a transcript entry."""
    if not isinstance(entry, dict):
        return ""

    msg_type = entry.get('type', '')

    if msg_type in ('human', 'user'):
        msg = entry.get('message', entry)
        content = msg.get('content', '')
        text = _extract_text_from_content(content)
        return f"[User]: {text}" if text else ""

    elif msg_type in ('assistant',):
        msg = entry.get('message', entry)
        content = msg.get('content', '')
        text = _extract_assistant_content(content)
        return f"[Assistant]: {text}" if text else ""

    elif msg_type == 'summary':
        summary = entry.get('summary', '')
        return f"[Context Summary]: {summary}" if summary else ""

    return ""


def _extract_text_from_content(content):
    """Extract plain text from message content (string or content blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get('type') == 'text':
                texts.append(block.get('text', ''))
            elif isinstance(block, str):
                texts.append(block)
        return ' '.join(texts)
    return ""


def _extract_assistant_content(content):
    """Extract assistant message content, summarizing tool usage."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict):
                if block.get('type') == 'text':
                    text = block.get('text', '').strip()
                    if text:
                        texts.append(text)
                elif block.get('type') == 'tool_use':
                    tool_name = block.get('name', 'unknown')
                    tool_input = block.get('input', {})
                    texts.append(_summarize_tool_use(tool_name, tool_input))
            elif isinstance(block, str):
                texts.append(block)
        return ' '.join(texts)
    return ""


def _summarize_tool_use(tool_name, tool_input):
    """Create a concise summary of a tool invocation."""
    if tool_name == 'Bash':
        cmd = tool_input.get('command', '')[:200]
        return f"[Ran: {cmd}]"
    elif tool_name == 'Read':
        return f"[Read: {tool_input.get('file_path', '?')}]"
    elif tool_name == 'Write':
        return f"[Wrote: {tool_input.get('file_path', '?')}]"
    elif tool_name == 'Edit':
        return f"[Edited: {tool_input.get('file_path', '?')}]"
    elif tool_name == 'Glob':
        return f"[Glob: {tool_input.get('pattern', '?')}]"
    elif tool_name == 'Grep':
        return f"[Grep: {tool_input.get('pattern', '?')}]"
    elif tool_name == 'Task':
        return f"[Delegated: {tool_input.get('description', '?')}]"
    elif tool_name == 'WebFetch':
        return f"[Fetched: {tool_input.get('url', '?')}]"
    elif tool_name == 'WebSearch':
        return f"[Searched: {tool_input.get('query', '?')}]"
    else:
        return f"[Tool: {tool_name}]"


def format_messages_for_observer(messages):
    """Format messages into readable text for the observer."""
    formatted = []
    for msg in messages:
        text = extract_text_content(msg)
        if text:
            formatted.append(text)
    return '\n\n'.join(formatted)


def load_state(memory_dir):
    """Load observer cursor state."""
    state_file = memory_dir / '.observer-state.json'
    if state_file.exists():
        try:
            return json.loads(state_file.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {'last_observed_line': 0, 'transcript_path': ''}


def save_state(memory_dir, last_line, transcript_path, current_task=None, suggested_response=None):
    """Save observer cursor state."""
    state_file = memory_dir / '.observer-state.json'
    state = {
        'last_observed_line': last_line,
        'transcript_path': transcript_path,
        'last_observed_at': datetime.now(timezone.utc).isoformat()
    }
    if current_task:
        state['current_task'] = current_task
    if suggested_response:
        state['suggested_response'] = suggested_response
    state_file.write_text(json.dumps(state, indent=2))


def load_prompt(name):
    """Load a prompt template from the prompts directory."""
    prompt_file = SCRIPT_DIR / 'prompts' / f'{name}.md'
    if prompt_file.exists():
        return prompt_file.read_text()
    return ""


def call_claude(system_prompt, user_prompt, model=None):
    """Call Claude via `claude -p` pipe mode.

    Uses an environment variable guard to prevent recursive hook invocation.
    """
    # Prevent recursion: if we're already inside an OM hook call, bail out
    if os.environ.get('OM_HOOK_ACTIVE'):
        return None

    if model is None:
        model = OBSERVER_MODEL

    # Combine system + user prompt into a single input for pipe mode
    full_prompt = (
        f"<instructions>\n{system_prompt}\n</instructions>\n\n"
        f"{user_prompt}"
    )

    # Set guard env var so any child `claude -p` won't re-trigger this hook
    env = os.environ.copy()
    env['OM_HOOK_ACTIVE'] = '1'
    env.pop('CLAUDECODE', None)  # Allow nested claude -p invocation

    try:
        result = subprocess.run(
            ['claude', '-p', '--model', model],
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

        if result.stderr.strip():
            log_error(f"claude -p stderr: {result.stderr[:500]}")

        return None
    except FileNotFoundError:
        log_error("claude CLI not found in PATH")
        return None
    except subprocess.TimeoutExpired:
        log_error("claude -p timed out")
        return None
    except Exception as e:
        log_error(f"claude -p failed: {e}")
        return None


def log_error(message, memory_dir=None):
    """Log an error to the observer log file."""
    # Try memory dir first, fall back to script-relative
    if memory_dir:
        log_file = memory_dir / 'om-error.log'
    else:
        log_file = SCRIPT_DIR / 'om-error.log'
    try:
        with open(log_file, 'a') as f:
            ts = datetime.now(timezone.utc).isoformat()
            f.write(f"[{ts}] {message}\n")
    except IOError:
        pass


def parse_observer_output(raw_output):
    """Parse XML sections from observer output.

    Returns (observations, current_task, suggested_response).
    Falls back to treating the entire output as observations if no XML tags found.
    """
    observations = ''
    current_task = None
    suggested_response = None

    # Extract <observations> content
    obs_match = re.search(r'<observations>(.*?)</observations>', raw_output, re.DOTALL)
    if obs_match:
        observations = obs_match.group(1).strip()
    else:
        # Fallback: treat entire output as observations (minus any other XML tags)
        observations = raw_output
        observations = re.sub(r'<current-task>.*?</current-task>', '', observations, flags=re.DOTALL)
        observations = re.sub(r'<suggested-response>.*?</suggested-response>', '', observations, flags=re.DOTALL)
        observations = observations.strip()

    # Extract <current-task>
    task_match = re.search(r'<current-task>(.*?)</current-task>', raw_output, re.DOTALL)
    if task_match:
        current_task = task_match.group(1).strip() or None

    # Extract <suggested-response>
    resp_match = re.search(r'<suggested-response>(.*?)</suggested-response>', raw_output, re.DOTALL)
    if resp_match:
        suggested_response = resp_match.group(1).strip() or None

    return observations, current_task, suggested_response


def build_observer_prompt(new_messages_text, existing_observations):
    """Build the user prompt for the observer."""
    parts = []

    if existing_observations.strip():
        parts.append("## Previous Observations\n")
        parts.append(existing_observations.strip())
        parts.append("\n\n---\n")
        parts.append("Do NOT repeat any of the above observations. Only extract genuinely new information.\n")

    parts.append("\n## New Messages to Observe\n\n")
    parts.append(new_messages_text)
    parts.append("\n\n---\n\n")
    parts.append("## Your Task\n\n")
    parts.append("Extract new observations from the messages above. ")
    parts.append(f"Today's date is {datetime.now(timezone.utc).strftime('%Y-%m-%d')}. ")
    parts.append("Use actual timestamps from the conversation when available. ")
    parts.append("Return ONLY the new observations block, or NO_NEW_OBSERVATIONS if nothing meaningful to note.")

    return ''.join(parts)


def run_reflector(memory_dir):
    """Run the reflector to compress observations if they're too large."""
    observations_file = memory_dir / 'observations.md'
    if not observations_file.exists():
        return

    content = observations_file.read_text()
    if len(content) < REFLECTION_THRESHOLD_CHARS:
        return

    system_prompt = load_prompt('reflector-system')
    if not system_prompt:
        return

    user_prompt = (
        f"## Observations to Reflect On\n\n"
        f"{content}\n\n"
        f"---\n\n"
        f"Condense these observations. Today's date is "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}. "
        f"Current size: {len(content)} characters. "
        f"Target: ~{len(content) // 2} characters."
    )

    result = call_claude(system_prompt, user_prompt, model=REFLECTOR_MODEL)
    if not result or len(result.strip()) < 100:
        return

    # Archive the pre-reflection version
    archive_file = memory_dir / 'reflections.log'
    try:
        with open(archive_file, 'a') as f:
            ts = datetime.now(timezone.utc).isoformat()
            f.write(f"\n{'='*60}\n")
            f.write(f"Reflection at {ts}\n")
            f.write(f"Before: {len(content)} chars -> After: {len(result)} chars\n")
            f.write(f"{'='*60}\n")
            f.write(content)
            f.write(f"\n{'='*60}\n\n")
    except IOError:
        pass

    # Replace observations with reflected version
    observations_file.write_text(result.strip() + '\n')


def main():
    """Main entry point for the observer Stop hook."""
    # Recursion guard
    if os.environ.get('OM_HOOK_ACTIVE'):
        return

    # Read hook input from stdin
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    # Don't observe if already in a stop-hook continuation
    if input_data.get('stop_hook_active', False):
        return

    transcript_path = input_data.get('transcript_path', '')
    if not transcript_path or not os.path.exists(transcript_path):
        return

    # Determine memory directory
    memory_dir = get_memory_dir(transcript_path)

    # Read transcript
    all_messages = read_transcript(transcript_path)
    if not all_messages:
        return

    # Load state to find unobserved messages
    state = load_state(memory_dir)

    # Determine new messages based on cursor
    last_line = state.get('last_observed_line', 0)
    last_transcript = state.get('transcript_path', '')

    # Reset cursor if transcript changed (new session)
    if last_transcript != transcript_path:
        last_line = 0

    new_messages = [m for m in all_messages if m.get('_line_num', 0) >= last_line]
    if not new_messages:
        return

    # Format new messages
    new_text = format_messages_for_observer(new_messages)
    if len(new_text) < MIN_NEW_CONTENT_CHARS:
        return

    # Load existing observations
    observations_file = memory_dir / 'observations.md'
    existing = observations_file.read_text().strip() if observations_file.exists() else ''

    # Load observer prompt
    system_prompt = load_prompt('observer-system')
    if not system_prompt:
        log_error("Observer system prompt not found", memory_dir)
        return

    # Build and send observer prompt
    user_prompt = build_observer_prompt(new_text, existing)

    # Truncate if too large (keep last 50k chars of new messages)
    if len(user_prompt) > 80000:
        truncated_text = new_text[-50000:]
        user_prompt = build_observer_prompt(truncated_text, existing)

    result = call_claude(system_prompt, user_prompt, model=OBSERVER_MODEL)

    if not result or result.strip() == 'NO_NEW_OBSERVATIONS':
        # Still update cursor even if nothing new
        max_line = max(m.get('_line_num', 0) for m in all_messages)
        save_state(memory_dir, max_line + 1, transcript_path)
        return

    # Parse XML sections from result
    observations_text, current_task, suggested_response = parse_observer_output(result)

    # Clean up the observations
    observations_text = re.sub(r'^```\w*\n?', '', observations_text)
    observations_text = re.sub(r'\n?```$', '', observations_text)
    observations_text = observations_text.strip()

    if not observations_text:
        max_line = max(m.get('_line_num', 0) for m in all_messages)
        save_state(memory_dir, max_line + 1, transcript_path, current_task, suggested_response)
        return

    # Append new observations
    with open(observations_file, 'a') as f:
        if existing:
            f.write('\n\n')
        f.write(observations_text)
        f.write('\n')

    # Update cursor with task continuity data
    max_line = max(m.get('_line_num', 0) for m in all_messages)
    save_state(memory_dir, max_line + 1, transcript_path, current_task, suggested_response)

    # Check if reflection is needed
    updated_content = observations_file.read_text()
    if len(updated_content) >= REFLECTION_THRESHOLD_CHARS:
        run_reflector(memory_dir)

    # Output system message for async hook delivery
    output = {
        "systemMessage": (
            f"[Observational Memory] Extracted observations from "
            f"{len(new_messages)} new messages. "
            f"Observations file: {len(updated_content)} chars."
        )
    }
    print(json.dumps(output))


# Allow running as a standalone script with --force flag
if __name__ == '__main__':
    if '--force' in sys.argv:
        import glob

        projects_dir = Path.home() / '.claude' / 'projects'
        if not projects_dir.exists():
            print("No projects directory found")
            sys.exit(1)

        transcripts = glob.glob(str(projects_dir / '**' / '*.jsonl'), recursive=True)
        if not transcripts:
            print("No transcripts found")
            sys.exit(1)

        transcripts.sort(key=os.path.getmtime, reverse=True)
        transcript_path = transcripts[0]

        memory_dir = get_memory_dir(transcript_path)

        all_messages = read_transcript(transcript_path)
        if not all_messages:
            print("No messages in transcript")
            sys.exit(0)

        new_text = format_messages_for_observer(all_messages)
        existing = ''
        observations_file = memory_dir / 'observations.md'
        if observations_file.exists():
            existing = observations_file.read_text().strip()

        system_prompt = load_prompt('observer-system')
        if not system_prompt:
            print("Observer system prompt not found")
            sys.exit(1)

        user_prompt = build_observer_prompt(new_text, existing)
        if len(user_prompt) > 80000:
            new_text = new_text[-50000:]
            user_prompt = build_observer_prompt(new_text, existing)

        result = call_claude(system_prompt, user_prompt)
        if result and result.strip() != 'NO_NEW_OBSERVATIONS':
            cleaned = result.strip()
            cleaned = re.sub(r'^```\w*\n?', '', cleaned)
            cleaned = re.sub(r'\n?```$', '', cleaned)
            with open(observations_file, 'a') as f:
                if existing:
                    f.write('\n\n')
                f.write(cleaned)
                f.write('\n')
            print(f"Observations extracted and saved to {observations_file}")
            max_line = max(m.get('_line_num', 0) for m in all_messages)
            save_state(memory_dir, max_line + 1, transcript_path)
        else:
            print("No new observations to extract")
    else:
        main()

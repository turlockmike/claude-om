#!/usr/bin/env python3
"""
Observational Memory — Reflector
Claude Code PreCompact hook that compresses observations before context compaction.
Can also be run standalone via the /reflect skill.

Uses `claude -p` for LLM calls — no API key needed.
"""

import json
import sys
import os
import subprocess
import re
from datetime import datetime, timezone
from pathlib import Path

# Model shorthand for claude CLI
REFLECTOR_MODEL = os.environ.get("OM_REFLECTOR_MODEL", "haiku")
# Minimum size to bother reflecting (chars)
MIN_REFLECT_CHARS = 5000

# Script directory for locating prompts
SCRIPT_DIR = Path(__file__).resolve().parent


def get_project_dir(transcript_path):
    """Extract the project directory from the transcript path."""
    match = re.search(r'(.*?/\.claude/projects/[^/]+)', transcript_path)
    if match:
        return Path(match.group(1))
    return Path(transcript_path).parent


def get_memory_dir_from_transcript(transcript_path):
    """Derive the project memory directory from transcript path."""
    project_dir = get_project_dir(transcript_path)
    memory_dir = project_dir / 'memory'
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir


def get_memory_dir_from_cwd(cwd):
    """Derive the project memory directory from working directory."""
    project_key = cwd.replace('/', '-')
    memory_dir = Path.home() / '.claude' / 'projects' / project_key / 'memory'
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir


def load_prompt():
    """Load the reflector system prompt."""
    prompt_file = SCRIPT_DIR / 'prompts' / 'reflector-system.md'
    if prompt_file.exists():
        return prompt_file.read_text()
    return ""


def call_claude(system_prompt, user_prompt):
    """Call Claude via `claude -p` pipe mode.

    Uses an environment variable guard to prevent recursive hook invocation.
    """
    if os.environ.get('OM_HOOK_ACTIVE'):
        return None

    full_prompt = (
        f"<instructions>\n{system_prompt}\n</instructions>\n\n"
        f"{user_prompt}"
    )

    env = os.environ.copy()
    env['OM_HOOK_ACTIVE'] = '1'

    try:
        result = subprocess.run(
            ['claude', '-p', '--model', REFLECTOR_MODEL],
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=180,
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
    if memory_dir:
        log_file = memory_dir / 'om-error.log'
    else:
        log_file = SCRIPT_DIR / 'om-error.log'
    try:
        with open(log_file, 'a') as f:
            ts = datetime.now(timezone.utc).isoformat()
            f.write(f"[{ts}] REFLECTOR: {message}\n")
    except IOError:
        pass


def reflect(memory_dir, force=False):
    """Run reflection on the observations file."""
    observations_file = memory_dir / 'observations.md'
    if not observations_file.exists():
        return False, "No observations file found"

    content = observations_file.read_text()
    if not content.strip():
        return False, "Observations file is empty"

    if not force and len(content) < MIN_REFLECT_CHARS:
        return False, f"Observations too small to reflect ({len(content)} chars, minimum {MIN_REFLECT_CHARS})"

    system_prompt = load_prompt()
    if not system_prompt:
        return False, "Reflector system prompt not found"

    user_prompt = (
        f"## Observations to Reflect On\n\n"
        f"{content}\n\n"
        f"---\n\n"
        f"Condense these observations. Today's date is "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}. "
        f"Current size: {len(content)} characters ({len(content) // 4} approx tokens). "
        f"Target: ~{len(content) // 2} characters."
    )

    result = call_claude(system_prompt, user_prompt)
    if not result or len(result.strip()) < 50:
        return False, "Reflector returned empty or too-short result"

    # Clean up
    reflected = result.strip()
    reflected = re.sub(r'^```\w*\n?', '', reflected)
    reflected = re.sub(r'\n?```$', '', reflected)

    # Archive pre-reflection version
    archive_file = memory_dir / 'reflections.log'
    try:
        with open(archive_file, 'a') as f:
            ts = datetime.now(timezone.utc).isoformat()
            f.write(f"\n{'=' * 60}\n")
            f.write(f"Reflection at {ts}\n")
            f.write(f"Before: {len(content)} chars -> After: {len(reflected)} chars\n")
            f.write(f"Compression ratio: {len(reflected) / len(content):.1%}\n")
            f.write(f"{'=' * 60}\n")
            f.write(content)
            f.write(f"\n{'=' * 60}\n\n")
    except IOError:
        pass

    # Write reflected observations
    observations_file.write_text(reflected + '\n')

    return True, f"Reflected: {len(content)} -> {len(reflected)} chars ({len(reflected) / len(content):.0%})"


def main():
    """Main entry point for the PreCompact hook."""
    # Recursion guard
    if os.environ.get('OM_HOOK_ACTIVE'):
        return

    # Read hook input from stdin
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    transcript_path = input_data.get('transcript_path', '')
    if not transcript_path:
        return

    memory_dir = get_memory_dir_from_transcript(transcript_path)
    success, message = reflect(memory_dir)

    if success:
        output = {"systemMessage": f"[Observational Memory] {message}"}
        print(json.dumps(output))


if __name__ == '__main__':
    if '--force' in sys.argv:
        cwd = os.getcwd()
        if '--cwd' in sys.argv:
            idx = sys.argv.index('--cwd')
            if idx + 1 < len(sys.argv):
                cwd = sys.argv[idx + 1]

        memory_dir = get_memory_dir_from_cwd(cwd)
        success, message = reflect(memory_dir, force=True)
        print(message)
        sys.exit(0 if success else 1)
    else:
        main()

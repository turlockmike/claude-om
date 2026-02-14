# claude-om — Observational Memory for Claude Code

Automatic long-term memory for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Extracts observations from your conversations, persists them across sessions, and compresses them over time — inspired by [Mastra's Observational Memory](https://mastra.ai/docs/memory/overview) system.

## How It Works

Claude OM uses three hooks to manage memory automatically:

| Hook Event | What It Does |
|---|---|
| **Stop** | After each conversation, extracts structured observations from the transcript |
| **SessionStart** | At the start of each session, injects previous observations into context |
| **PreCompact** | Before context compaction, compresses old observations to save space |

Observations are stored per-project in `~/.claude/projects/<project>/memory/observations.md`.

## Installation

```bash
# Add the marketplace and enable the plugin
claude plugin marketplace add turlockmike/claude-om
claude plugin enable claude-om
```

## Configuration

Environment variables (all optional):

| Variable | Default | Description |
|---|---|---|
| `OM_OBSERVER_MODEL` | `haiku` | Model used to extract observations |
| `OM_REFLECTOR_MODEL` | `haiku` | Model used to compress observations |

## Skills

The plugin provides four skills:

| Skill | Description |
|---|---|
| `/claude-om:observe` | Force observation extraction from the current conversation |
| `/claude-om:recall [topic]` | Search and display observations from memory |
| `/claude-om:reflect` | Manually trigger observation compression |
| `/claude-om:forget [topic]` | Remove specific observations from memory |

## Prerequisites

- Python 3.6+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (`claude` command available in PATH)

## How Observations Work

The observer extracts structured, timestamped observations:

```
Date: 2026-02-14
- 18:07 🔴 User's project uses Next.js 14 with TypeScript
  - 18:07 PostgreSQL database with Prisma ORM
- 18:15 🟡 Created auth middleware at src/middleware/auth.ts using JWT
- 18:30 🔴 User prefers functional components over class components
```

Priority markers indicate importance:
- 🔴 **High**: Facts, decisions, preferences, architecture
- 🟡 **Medium**: Implementation details, debugging context
- 🟢 **Low**: Exploratory questions, tentative ideas

## Data Storage

All data stays local on your machine:

```
~/.claude/projects/<project>/memory/
├── observations.md          # Current observations
├── .observer-state.json     # Cursor tracking (last processed line)
└── reflections.log          # Archive of pre-compression observations
```

## License

MIT

# HAN-Agents

**HAN** = **H**ierarchical **A**pproached **N**euromorphic Agents

- **Hierarchical**: PFC coordinates specialized agents (Executor, Critic, Memory, Researcher)
- **Approached**: Task-driven methodology with planning → execution → validation workflow
- **Neuromorphic**: Brain-inspired architecture (Prefrontal Cortex, Motor Cortex, Hippocampus)

A multi-agent task system with three-layer architecture: **Skill** (intent) + **Code Graph** (reality) + **Memory** (experience).

Works with any AI coding agent that supports the [Agent Skills](https://agentskills.io) standard, including Claude Code, Cursor, Windsurf, Cline, Codex CLI, Gemini CLI, Antigravity, and Kiro.

## Installation

### Step 1: Clone to Your Platform's Skills Directory

Choose your AI coding agent and clone to the appropriate location:

<details>
<summary><b>Claude Code</b></summary>

```bash
# macOS/Linux
git clone https://github.com/Stanley-1013/han-agents.git ~/.claude/skills/han-agents

# Windows (PowerShell)
git clone https://github.com/Stanley-1013/han-agents.git "$env:USERPROFILE\.claude\skills\han-agents"

# Windows (CMD)
git clone https://github.com/Stanley-1013/han-agents.git "%USERPROFILE%\.claude\skills\han-agents"
```

Then add to `~/.claude/settings.json`:
```json
{
  "skills": ["~/.claude/skills/han-agents"]
}
```

</details>

<details>
<summary><b>Cursor</b></summary>

```bash
# macOS/Linux (global)
git clone https://github.com/Stanley-1013/han-agents.git ~/.cursor/skills/han-agents

# Windows (PowerShell)
git clone https://github.com/Stanley-1013/han-agents.git "$env:USERPROFILE\.cursor\skills\han-agents"

# Project-level
git clone https://github.com/Stanley-1013/han-agents.git .cursor/skills/han-agents
```

</details>

<details>
<summary><b>Windsurf</b></summary>

```bash
# Project-level (recommended)
git clone https://github.com/Stanley-1013/han-agents.git .windsurf/skills/han-agents
```

</details>

<details>
<summary><b>Cline</b></summary>

```bash
# macOS/Linux (global)
git clone https://github.com/Stanley-1013/han-agents.git ~/.cline/skills/han-agents

# Windows (PowerShell)
git clone https://github.com/Stanley-1013/han-agents.git "$env:USERPROFILE\.cline\skills\han-agents"

# Project-level
git clone https://github.com/Stanley-1013/han-agents.git .cline/skills/han-agents
```

> **Note**: Enable Skills in Cline: Settings → Features → Enable Skills

</details>

<details>
<summary><b>Codex CLI (OpenAI)</b></summary>

```bash
# macOS/Linux
git clone https://github.com/Stanley-1013/han-agents.git ~/.codex/skills/han-agents

# Windows (PowerShell)
git clone https://github.com/Stanley-1013/han-agents.git "$env:USERPROFILE\.codex\skills\han-agents"
```

</details>

<details>
<summary><b>Gemini CLI</b></summary>

```bash
# Project-level
git clone https://github.com/Stanley-1013/han-agents.git .gemini/skills/han-agents
```

</details>

<details>
<summary><b>Antigravity (Google)</b></summary>

```bash
# macOS/Linux (global)
git clone https://github.com/Stanley-1013/han-agents.git ~/.gemini/antigravity/skills/han-agents

# Project-level
git clone https://github.com/Stanley-1013/han-agents.git .agent/skills/han-agents
```

</details>

<details>
<summary><b>Kiro (AWS)</b></summary>

Kiro uses the **Powers** system with one-click install. Visit [kiro.dev](https://kiro.dev) and search for "han-agents", or install from GitHub URL in Kiro's Powers panel.

</details>

### Step 2: Run Install Script

Run the install script to initialize the database and configure your platform:

```bash
# Run from your skills directory (script auto-detects platform)
python <skills-path>/han-agents/scripts/install.py --skip-prompts

# Examples:
# Claude Code
python ~/.claude/skills/han-agents/scripts/install.py --skip-prompts

# Cursor
python ~/.cursor/skills/han-agents/scripts/install.py --skip-prompts

# Windsurf (project-level)
python .windsurf/skills/han-agents/scripts/install.py --skip-prompts
```

The script auto-detects your platform and performs the appropriate setup:

| Platform | Database | Agents | Hooks |
|----------|----------|--------|-------|
| Claude Code | ✅ Initialize | ✅ Copy to `~/.claude/agents/` | ✅ PostToolUse Hook |
| Cursor | ✅ Initialize | ✅ Copy to `.cursor/agents/` | ❌ Not supported |
| Others | ✅ Initialize | ❌ No agents directory | ❌ Not supported |

Install options:
- `--skip-prompts`: Non-interactive mode (recommended for scripts)
- `--all`: Run all optional setup steps
- `--add-claude-md`: Add config to project's CLAUDE.md
- `--init-ssot`: Initialize project SSOT INDEX
- `--sync-graph`: Sync Code Graph

### Verify Installation

```bash
# Adjust path based on your platform's skills directory
python ~/.claude/skills/han-agents/scripts/doctor.py
```

## Features

- **Task Lifecycle Management**: Create, execute, validate, and document tasks with multiple agents
- **Code Graph**: AST-based code analysis for TypeScript, Python, and Go
- **Drift Detection**: Compare Skill definitions against actual code implementation
- **Semantic Memory**: FTS5 + embedding-based search with LLM reranking
- **Micro-Nap Checkpoints**: Save/resume long-running tasks across conversations

## Quick Start

```python
import sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/skills/han-agents'))

from servers.facade import sync, status, check_drift
from servers.tasks import create_task, create_subtask
from servers.memory import search_memory_semantic, store_memory
```

## Project Setup

Initialize a project Skill (auto-detects platform from han-agents install location):

```bash
# Run from your skills directory
python <skills-path>/han-agents/scripts/init_project.py <project-name> [project-dir]

# Examples:
# Claude Code
python ~/.claude/skills/han-agents/scripts/init_project.py my-project /path/to/project

# Cursor
python ~/.cursor/skills/han-agents/scripts/init_project.py my-project /path/to/project

# Windsurf (project-level)
python .windsurf/skills/han-agents/scripts/init_project.py my-project .

# Override platform (optional)
python ~/.claude/skills/han-agents/scripts/init_project.py my-project . --platform cursor
```

This creates `<project>/.<platform>/skills/<project-name>/SKILL.md`:

| Platform | Project Skill Location |
|----------|------------------------|
| Claude Code | `.claude/skills/<name>/SKILL.md` |
| Cursor | `.cursor/skills/<name>/SKILL.md` |
| Windsurf | `.windsurf/skills/<name>/SKILL.md` |
| Cline | `.cline/skills/<name>/SKILL.md` |
| Codex CLI | `.codex/skills/<name>/SKILL.md` |
| Gemini CLI | `.gemini/skills/<name>/SKILL.md` |
| Antigravity | `.agent/skills/<name>/SKILL.md` |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     HAN System                      │
├──────────────┬──────────────┬──────────────┬────────────────┤
│  Skill Layer │  Code Graph  │    Memory    │     Tasks      │
│   (Intent)   │  (Reality)   │ (Experience) │  (Execution)   │
├──────────────┼──────────────┼──────────────┼────────────────┤
│  SKILL.md    │  code_nodes  │  long_term   │    tasks       │
│  flows/*.md  │  code_edges  │  episodes    │  checkpoints   │
│  domains/*   │  file_hashes │  working_mem │  agent_logs    │
└──────────────┴──────────────┴──────────────┴────────────────┘
```

## Agents

| Agent | Type | Purpose |
|-------|------|---------|
| PFC | `pfc` | Planning and task decomposition |
| Executor | `executor` | Task execution |
| Critic | `critic` | Validation and quality checks |
| Memory | `memory` | Knowledge storage and retrieval |
| Researcher | `researcher` | Information gathering |
| Drift Detector | `drift-detector` | Skill-Code drift detection |

## Key APIs

### Facade (Unified Entry Point)

```python
from servers.facade import (
    sync,              # Sync Code Graph
    status,            # Project status
    check_drift,       # Skill vs Code drift
    get_full_context,  # Three-layer context
    finish_task,       # Complete task lifecycle
)
```

### Tasks

```python
from servers.tasks import (
    create_task,       # Create parent task
    create_subtask,    # Create child task with dependencies
    get_task_progress, # Get completion stats
)
```

### Memory

```python
from servers.memory import (
    search_memory_semantic,  # Semantic search with reranking
    store_memory,            # Store to long-term memory
    save_checkpoint,         # Micro-Nap checkpoint
    load_checkpoint,         # Resume from checkpoint
)
```

## Scripts

```bash
# Install/update agents, hooks, and database
python ~/.claude/skills/han-agents/scripts/install.py --skip-prompts

# Diagnostics (verify installation)
python ~/.claude/skills/han-agents/scripts/doctor.py

# Sync Code Graph for a project
python ~/.claude/skills/han-agents/scripts/sync.py /path/to/project

# Initialize project Skill
python ~/.claude/skills/han-agents/scripts/init_project.py my-project /path/to/project
```

## Documentation

- [SKILL.md](SKILL.md) - Main skill definition
- [reference/API_REFERENCE.md](reference/API_REFERENCE.md) - Complete API documentation
- [reference/WORKFLOW_GUIDE.md](reference/WORKFLOW_GUIDE.md) - Workflow patterns
- [reference/GRAPH_GUIDE.md](reference/GRAPH_GUIDE.md) - Graph operations
- [reference/TROUBLESHOOTING.md](reference/TROUBLESHOOTING.md) - Common issues

## Database

SQLite database at `~/.claude/skills/han-agents/brain/brain.db`

Schema: [brain/schema.sql](brain/schema.sql)

## Compatibility

### Supported Platforms

| Platform | Skills Directory | Scope |
|----------|-----------------|-------|
| [Claude Code](https://claude.ai/code) | `~/.claude/skills/` | Global |
| [Cursor](https://cursor.com) | `~/.cursor/skills/` or `.cursor/skills/` | Global / Project |
| [Windsurf](https://windsurf.com) | `.windsurf/skills/` | Project |
| [Cline](https://cline.bot) | `~/.cline/skills/` or `.cline/skills/` | Global / Project |
| [Codex CLI](https://developers.openai.com/codex) | `~/.codex/skills/` | Global |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | `.gemini/skills/` | Project |
| [Antigravity](https://antigravity.google) | `~/.gemini/antigravity/skills/` or `.agent/skills/` | Global / Project |
| [Kiro](https://kiro.dev) | Powers system (one-click install) | - |

### Feature Support

| Feature | Claude Code | Other Platforms |
|---------|-------------|-----------------|
| Memory & Semantic Search | ✅ Full | ✅ Full |
| Code Graph & Drift Detection | ✅ Full | ✅ Full |
| Task Lifecycle Management | ✅ Full | ✅ Full |
| Multi-Agent Coordination | ✅ Native (Task tool) | ⚠️ Sequential |

> **Note**: Claude Code's Task tool enables true parallel agent execution with isolated contexts. Other platforms can use all APIs but run agents sequentially in shared context.

## Requirements

- Python 3.8+
- SQLite 3.35+ (with FTS5 support)

## License

MIT

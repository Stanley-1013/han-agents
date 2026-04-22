# HAN-Agents

**HAN** = **H**ierarchical **A**pproached **N**euromorphic Agents

A multi-agent task system with three-layer architecture: **Skill** (intent) + **Code Graph** (reality) + **Memory** (experience). Brain-inspired design where PFC coordinates specialized agents through automated dispatch loops.

Works with any AI coding agent that supports the [Agent Skills](https://agentskills.io) standard, including Claude Code, Cursor, Windsurf, Cline, Codex CLI, Gemini CLI, Antigravity, and Kiro.

## Features

- **Automated Dispatch Loop** — `get_next_dispatch()` auto-orchestrates Executor → Critic → Memory pipeline
- **Recipe System** — Pre-built workflows (e.g. `recipe_unit_tests()`) that auto-generate task trees
- **Task Lifecycle** — Jira-like hierarchy (Epic → Story → Task → Bug) with create, execute, validate, and document
- **Code Graph** — Tree-sitter AST + regex fallback, with call graph and method extraction (8 languages)
- **Drift Detection** — Compare Skill definitions against actual code implementation
- **Semantic Memory** — FTS5 + embedding-based search with LLM reranking
- **Auto Tech Stack Detection** — `ensure_project()` auto-detects languages, frameworks, and test tools
- **Micro-Nap Checkpoints** — Save/resume long-running tasks across conversations
- **Zero-Config** — Clone to skills directory, database auto-creates on first use

## Installation

### Step 1: Clone

Clone to your AI coding agent's skills directory:

<details>
<summary><b>Claude Code</b></summary>

```bash
# Global (recommended)
git clone https://github.com/Stanley-1013/han-agents.git ~/.claude/skills/han-agents

# Project-level
git clone https://github.com/Stanley-1013/han-agents.git .claude/skills/han-agents
```

Windows (PowerShell): replace `~` with `$env:USERPROFILE`

</details>

<details>
<summary><b>Cursor</b></summary>

```bash
# Global
git clone https://github.com/Stanley-1013/han-agents.git ~/.cursor/skills/han-agents

# Project-level
git clone https://github.com/Stanley-1013/han-agents.git .cursor/skills/han-agents
```

> Enable Skills in Cline-based Cursor: Settings → Features → Enable Skills

</details>

<details>
<summary><b>Windsurf / Cline / Codex CLI / Gemini CLI / Antigravity</b></summary>

Replace the skills directory with your platform's equivalent:

| Platform | Directory |
|----------|-----------|
| Windsurf | `.windsurf/skills/han-agents` |
| Cline | `~/.cline/skills/han-agents` |
| Codex CLI | `~/.codex/skills/han-agents` |
| Gemini CLI | `.gemini/skills/han-agents` |
| Antigravity | `~/.antigravity/skills/han-agents` |

</details>

<details>
<summary><b>Kiro (AWS)</b></summary>

Uses the **Powers** system — search for "han-agents" in Kiro's Powers panel or install from GitHub URL.

</details>

### Step 2: Just Start

That's it. No install script needed. On first use, han-agents automatically:
- Creates the database (`brain/brain.db`)
- Copies agent definitions to your platform's agents directory
- Registers hooks (Claude Code only)
- Installs tree-sitter grammars on demand (for enhanced code extraction)

Set `HAN_NO_INSTALL=1` to disable auto-installation (CI/air-gapped environments).

<details>
<summary><b>Optional: manual install / advanced setup</b></summary>

```bash
cd <path-to-han-agents>
python scripts/install.py --skip-prompts
```

| Flag | Description |
|------|-------------|
| `--skip-prompts` | Non-interactive mode |
| `--all` | Run all optional setup steps |
| `--add-claude-md` | Add config to project's CLAUDE.md |
| `--init-ssot` | Initialize project SSOT INDEX |
| `--sync-graph` | Sync Code Graph |
| `--reset` | Reset database |

Pre-install tree-sitter grammars (optional, auto-installed on first use):
```bash
pip install -r requirements-ast.txt
```

</details>

### Verify (optional)

```bash
python scripts/doctor.py
```

## Quick Start

```python
import sys, os
from servers import HAN_BASE_DIR
sys.path.insert(0, HAN_BASE_DIR)

from servers.facade import sync, status, check_drift, get_next_dispatch
from servers.tasks import create_task, create_subtask, get_task_progress
from servers.recipes import recipe_unit_tests, run_recipe
from servers.memory import search_memory_semantic, store_memory
from servers.project import ensure_project
```

### Initialize a Project

```python
result = ensure_project('my-project', '/path/to/project')
# result['tech_stack'] → {'primary_language': 'python', 'test_tool': 'pytest', ...}
```

Or via CLI:

```bash
python cli/main.py init my-project /path/to/project
```

### Recipe + Dispatch Loop

One command to generate tasks, auto-dispatch agents:

```python
# 1. Recipe auto-analyzes project, builds task tree
result = recipe_unit_tests('my-project', '/path/to/project')

# 2. Dispatch loop — repeat until done
while True:
    inst = get_next_dispatch(result['epic_id'], 'my-project', '/path/to/project')
    if inst['action'] != 'dispatch':
        break
    # Claude Code: dispatch via Task tool
    Task(subagent_type=inst['subagent_type'], prompt=inst['prompt'])
```

`get_next_dispatch()` handles automatically:
- Executor → Critic validation loop (idempotent, no duplicate critics)
- Rejected tasks → retry with feedback context
- All done → Memory agent stores lessons learned
- Returns `model_tier` for platform-specific model selection

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        HAN System                            │
├───────────────┬───────────────┬───────────────┬──────────────┤
│  Skill Layer  │  Code Graph   │    Memory     │    Tasks     │
│   (Intent)    │  (Reality)    │ (Experience)  │ (Execution)  │
├───────────────┼───────────────┼───────────────┼──────────────┤
│  SKILL.md     │  code_nodes   │ long_term_    │   tasks      │
│  flows/*.md   │  code_edges   │   memory      │ checkpoints  │
│  domains/*    │  file_hashes  │ working_      │ agent_logs   │
│               │               │   memory      │              │
└───────────────┴───────────────┴───────────────┴──────────────┘
```

## Agents

| Agent | Type | Model Tier | Purpose |
|-------|------|------------|---------|
| PFC | `pfc` | `planner` | Planning and task decomposition |
| Executor | `executor` | `worker` | Task execution |
| Critic | `critic` | `worker` | Validation and quality checks |
| Memory | `memory` | `fast` | Knowledge storage and retrieval |
| Researcher | `researcher` | `worker` | Information gathering |
| Drift Detector | `drift-detector` | `fast` | Skill-Code drift detection |

> **Model Tier**: Semantic capability levels — `planner` (strongest reasoning), `worker` (balanced), `fast` (low-cost). Each platform maps tiers to its own models.

## API Reference

### Facade (Unified Entry Point)

```python
from servers.facade import (
    sync,              # Sync Code Graph
    status,            # Project status
    check_drift,       # Skill vs Code drift
    get_full_context,  # Three-layer context
    finish_task,       # Complete task lifecycle
    get_next_dispatch, # Auto-dispatch next agent
)
```

### Recipes

```python
from servers.recipes import (
    recipe_unit_tests, # Auto-generate unit test task tree
    run_recipe,        # Run recipe by name
)
```

### Tasks

```python
from servers.tasks import (
    create_task,           # Create task (epic/story/task/bug)
    create_subtask,        # Create child task (auto-inherits hierarchy)
    reserve_critic_task,   # Atomic critic reservation (idempotent)
    get_task_progress,     # Completion stats
    get_epic_tasks,        # Epics with nested stories
    get_story_tasks,       # Tasks under a story
    get_hierarchy_summary, # Count by level {epics, stories, tasks, bugs}
)
```

### Project

```python
from servers.project import (
    ensure_project,    # Auto-init: sync Code Graph + detect tech stack + store DB
)
```

### Code Graph

```python
from servers.code_graph import (
    sync_from_directory,        # Sync folder to Code Graph
    get_class_dependencies_bfs, # BFS dependency traversal
    get_file_structure,         # File's code structure
)
```

Supported languages:

| Language | Extensions | Backend | Call Graph | Methods |
|----------|------------|---------|------------|---------|
| TypeScript | `.ts`, `.tsx` | Tree-sitter (regex fallback) | Yes | Yes |
| JavaScript | `.js`, `.jsx` | Tree-sitter (regex fallback) | Yes | Yes |
| Python | `.py` | Tree-sitter (regex fallback) | Yes | Yes |
| Java | `.java` | Tree-sitter (regex fallback) | Yes | Yes |
| Rust | `.rs` | Tree-sitter (regex fallback) | Yes | Yes |
| Go | `.go` | Tree-sitter only | Yes | Yes |
| C | `.c`, `.h` | Tree-sitter only | Yes | — |
| C++ | `.cpp`, `.cc`, `.cxx`, `.hpp`, `.hh`, `.hxx` | Tree-sitter only | Yes | Yes |

Install Tree-sitter for enhanced extraction (optional, regex fallback available for TS/JS/Python/Java/Rust):
```bash
pip install tree-sitter tree-sitter-python tree-sitter-javascript tree-sitter-typescript tree-sitter-java tree-sitter-rust tree-sitter-go tree-sitter-c tree-sitter-cpp
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

## CLI

```bash
python cli/main.py <command>
```

| Command | Description |
|---------|-------------|
| `doctor` | Diagnose system status |
| `sync` | Sync Code Graph from source files |
| `status` | Show project status overview |
| `init` | Initialize project for HAN |
| `drift` | Check SSOT vs Code drift |
| `install-hooks` | Install Git hooks for auto-sync |
| `ssot-sync` | Sync SSOT Index to Graph |
| `graph` | Query and explore the SSOT Graph |
| `dashboard` | Show full system dashboard |

## Scripts

```bash
cd <path-to-han-agents>

python scripts/install.py --skip-prompts  # Install/update
python scripts/doctor.py                  # Verify installation
python scripts/sync.py /path/to/project   # Sync Code Graph
python scripts/init_project.py my-project /path/to/project  # Init project
```

## Compatibility

| Platform | Skills Directory | Scope |
|----------|-----------------|-------|
| [Claude Code](https://claude.ai/code) | `~/.claude/skills/` or `.claude/skills/` | Global / Project |
| [Cursor](https://cursor.com) | `~/.cursor/skills/` or `.cursor/skills/` | Global / Project |
| [Windsurf](https://windsurf.com) | `.windsurf/skills/` | Project |
| [Cline](https://cline.bot) | `~/.cline/skills/` or `.cline/skills/` | Global / Project |
| [Codex CLI](https://developers.openai.com/codex) | `~/.codex/skills/` or `.codex/skills/` | Global / Project |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | `.gemini/skills/` | Project |
| [Antigravity](https://antigravity.google) | `~/.antigravity/skills/` or `.antigravity/skills/` | Global / Project |
| [Kiro](https://kiro.dev) | Powers system (one-click install) | — |

| Feature | Claude Code | Other Platforms |
|---------|-------------|-----------------|
| Memory & Semantic Search | ✅ Full | ✅ Full |
| Code Graph & Drift Detection | ✅ Full | ✅ Full |
| Task Lifecycle Management | ✅ Full | ✅ Full |
| Multi-Agent Coordination | ✅ Native (Task tool) | ⚠️ Sequential |

> Claude Code's Task tool enables parallel agent execution with isolated contexts. Other platforms run agents sequentially in shared context.

## Documentation

- [SKILL.md](SKILL.md) — Main skill definition
- [reference/API_REFERENCE.md](reference/API_REFERENCE.md) — Complete API documentation
- [reference/WORKFLOW_GUIDE.md](reference/WORKFLOW_GUIDE.md) — Workflow patterns
- [reference/GRAPH_GUIDE.md](reference/GRAPH_GUIDE.md) — Graph operations
- [reference/TROUBLESHOOTING.md](reference/TROUBLESHOOTING.md) — Common issues
- [docs/QUICKSTART_HANDOVER.md](docs/QUICKSTART_HANDOVER.md) — Quick start handover guide
- [docs/WHITEPAPER.md](docs/WHITEPAPER.md) — Architecture whitepaper

## Database

SQLite at `<han-agents>/brain/brain.db` (auto-created on first use).

- Schema: [brain/schema.sql](brain/schema.sql)
- Example: `brain/brain.example.db` — reference database for testing

## Requirements

- Python 3.8+
- SQLite 3.9+ (FTS5 support required)

## License

MIT

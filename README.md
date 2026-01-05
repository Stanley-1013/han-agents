# Cortex Multi-Agent System

A multi-agent task system with three-layer architecture: **Skill** (intent) + **Code Graph** (reality) + **Memory** (experience).

Works with any AI coding agent that supports custom skills/tools, including Claude Code, Cursor, Windsurf, Cline, and other LLM-based development tools.

## Installation

### From GitHub

```bash
# Clone to Claude Code skills directory
git clone https://github.com/Stanley-1013/cortex-agents.git ~/.claude/skills/cortex-agents

# Or for other AI agents, clone to your preferred location
git clone https://github.com/Stanley-1013/cortex-agents.git /path/to/skills/cortex-agents
```

### Initialize Database

```bash
# Run diagnostics and setup
python ~/.claude/skills/cortex-agents/scripts/doctor.py

# Or with custom path
python /path/to/skills/cortex-agents/scripts/doctor.py
```

### Configure Your AI Agent

**Claude Code**: Add to `~/.claude/settings.json`:

```json
{
  "skills": ["~/.claude/skills/cortex-agents"]
}
```

**Cursor/Windsurf/Other**: Add the skill path to your agent's configuration, or include the import in your system prompt:

```python
import sys, os
sys.path.insert(0, '/path/to/skills/cortex-agents')
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
sys.path.insert(0, os.path.expanduser('~/.claude/skills/cortex-agents'))

from servers.facade import sync, status, check_drift
from servers.tasks import create_task, create_subtask
from servers.memory import search_memory_semantic, store_memory
```

## Project Setup

Initialize a project Skill:

```bash
python ~/.claude/skills/cortex-agents/scripts/init_project.py /path/to/project [project-name]
```

This creates `<project>/.claude/skills/<name>/SKILL.md` - a template for LLM to fill with project documentation.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Cortex System                      │
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
# Diagnostics
python ~/.claude/skills/cortex-agents/scripts/doctor.py

# Sync Code Graph
python ~/.claude/skills/cortex-agents/scripts/sync.py /path/to/project

# Initialize project
python ~/.claude/skills/cortex-agents/scripts/init_project.py /path/to/project
```

## Documentation

- [SKILL.md](SKILL.md) - Main skill definition
- [reference/API_REFERENCE.md](reference/API_REFERENCE.md) - Complete API documentation
- [reference/WORKFLOW_GUIDE.md](reference/WORKFLOW_GUIDE.md) - Workflow patterns
- [reference/GRAPH_GUIDE.md](reference/GRAPH_GUIDE.md) - Graph operations
- [reference/TROUBLESHOOTING.md](reference/TROUBLESHOOTING.md) - Common issues

## Database

SQLite database at `~/.claude/skills/cortex-agents/brain/brain.db`

Schema: [brain/schema.sql](brain/schema.sql)

## Requirements

- Python 3.8+
- SQLite 3.35+ (with FTS5 support)

## License

MIT

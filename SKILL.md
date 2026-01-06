---
name: cortex-agents
description: |
  Multi-agent task system for complex tasks. Three-layer architecture (Skill + Code Graph + Memory),
  task lifecycle with validation, semantic search, drift detection. Use when: user requests PFC agent,
  complex multi-step tasks, multi-agent coordination, or mentions cortex.
allowed-tools: Read, Write, Bash, Glob, Grep, Task
---

# Cortex Multi-Agent System

> **Prerequisites**: Run `python ~/.claude/skills/cortex-agents/scripts/install.py` to install agents and hooks.

## Quick Start

```python
import sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/skills/cortex-agents'))

from servers.facade import get_full_context, check_drift, sync, finish_task
from servers.tasks import create_task, create_subtask, get_task_progress
from servers.memory import search_memory_semantic, store_memory, save_checkpoint, load_checkpoint
```

**DB**: `~/.claude/skills/cortex-agents/brain/brain.db`

## Project Initialization

初始化專案 Skill 目錄：

```bash
# macOS/Linux
python ~/.claude/skills/cortex-agents/scripts/init_project.py <project-name> <project-path>

# Windows
python "%USERPROFILE%\.claude\skills\cortex-agents\scripts\init_project.py" <project-name> <project-path>
```

建立 `<project>/.claude/skills/<project-name>/SKILL.md` 空白模板，由 LLM 填寫專案核心文檔。

## When to Use

| Use PFC System | Direct Execution |
|----------------|------------------|
| 3+ step tasks | Single-step tasks |
| Needs planning/validation | Quick fixes |
| User requests agents | Clear instructions |
| Skill consistency checks | Read-only queries |

## Agents

| Agent | subagent_type | Purpose |
|-------|---------------|---------|
| PFC | `pfc` | Planning, decomposition |
| Executor | `executor` | Task execution |
| Critic | `critic` | Validation |
| Memory | `memory` | Knowledge storage |
| Researcher | `researcher` | Information gathering |
| Drift Detector | `drift-detector` | Skill-Code drift |

## Workflow

```
PFC (plan) → Executor (do) → Critic (verify) → Memory (store)
                                  ↓ REJECTED
                            Executor (fix) → Critic (re-verify)
```

## Key APIs

```python
# Three-layer context (requires project_path)
context = get_full_context({'flow_id': 'flow.auth'}, '/path/to/project', 'my-project')

# Task management
task_id = create_task(project="PROJECT", description="Task", priority=8)
subtask = create_subtask(task_id, "Step 1", assigned_agent='executor')

# Drift detection (Skill vs Code)
report = check_drift('/path/to/project', 'my-project', 'auth')
if report['has_drift']:
    for d in report['drifts']: print(f"[{d['type']}] {d['description']}")

# Semantic search
result = search_memory_semantic("auth pattern", limit=5, rerank_mode='claude')

# Checkpoint
save_checkpoint(project='P', task_id=id, agent='pfc', state={...}, summary='...')
checkpoint = load_checkpoint(task_id)

# Store memory
store_memory(category='pattern', title='Title', content='...', project='P', importance=8)
```

## Agent Dispatch (Claude Code Task Tool)

**主對話必須使用 Claude Code Task tool 派發 agent：**

```
Task(
    subagent_type='pfc',        # 或 executor, critic, researcher, memory, drift-detector
    prompt='任務描述...'
)
```

**⭐ 派發 PFC 時的檔案範圍處理：**

> ⚠️ **主對話不要自己搜尋檔案後放入 prompt** — 這會讓 PFC 誤以為是使用者指定範圍而漏掉檔案

| 情況 | 主對話行為 | PFC 行為 |
|------|-----------|----------|
| 使用者明確指定檔案/範圍 | 將指定內容放入 prompt | 以指定範圍為主，用 Code Graph 檢查相關聯檔案 |
| 使用者沒指定範圍 | **直接傳任務描述，不搜尋檔案** | 自行使用 Code Graph 查詢完整範圍 |

```python
# ✅ 正確：使用者說「幫 src/ 寫測試」→ 直接傳描述
Task(subagent_type='pfc', prompt='為 src/ 下的模組撰寫單元測試')

# ❌ 錯誤：主對話自己先 glob 再傳（可能漏檔案，且 PFC 會誤以為是指定範圍）
files = glob('src/**/*.ts')  # 主對話搜尋
Task(subagent_type='pfc', prompt=f'為以下檔案寫測試:\n{files}')
```

**派發流程：**
1. 主對話判斷：使用者有沒有明確指定檔案範圍？
2. **沒指定 → 直接傳任務描述給 PFC，不要先搜尋**
3. PFC 用 **Code Graph 確認完整範圍**
4. PFC 規劃後輸出「派發指令」
5. **主對話**使用 Task tool 執行派發

**範例 - 派發 Executor：**
```
Task(
    subagent_type='executor',
    prompt=f'''TASK_ID = "{subtask_id}"
Task: [description]
Source: [file path]
Steps: 1. Read 2. Execute 3. Verify'''
)
```

**範例 - 派發 Critic：**
```
Task(
    subagent_type='critic',
    prompt=f'''TASK_ID = "{critic_task_id}"
ORIGINAL_TASK_ID = "{original_task_id}"
驗證任務產出...'''
)
```

## Scripts

```bash
python ~/.claude/skills/cortex-agents/scripts/install.py        # Install/update agents & hooks
python ~/.claude/skills/cortex-agents/scripts/doctor.py         # Diagnostics
python ~/.claude/skills/cortex-agents/scripts/sync.py PATH      # Graph sync
python ~/.claude/skills/cortex-agents/scripts/init_project.py   # Init project skill
```

## Reference

- [API_REFERENCE.md](reference/API_REFERENCE.md) - Complete API
- [WORKFLOW_GUIDE.md](reference/WORKFLOW_GUIDE.md) - Detailed workflow
- [GRAPH_GUIDE.md](reference/GRAPH_GUIDE.md) - Graph operations
- [TROUBLESHOOTING.md](reference/TROUBLESHOOTING.md) - Common issues
- [reference/agents/](reference/agents/) - Agent definitions

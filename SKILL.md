---
name: han-agents
description: |
  Multi-agent task system for complex tasks. Three-layer architecture (Skill + Code Graph + Memory),
  task lifecycle with validation, semantic search, drift detection. Use when: user requests PFC agent,
  complex multi-step tasks, multi-agent coordination, or mentions han.
allowed-tools: Read, Write, Bash, Glob, Grep, Task
---

# HAN-Agents

**HAN** = **H**ierarchical **A**pproached **N**euromorphic Agents

> **Zero-Config**: Clone 到 skills 目錄即可使用，資料庫會在首次呼叫時自動建立。

## Auto-Setup (首次使用時執行，冪等可重複)

```python
import sys, os, shutil, json, glob as globmod

han_dir = os.path.expanduser('~/.claude/skills/han-agents')
sys.path.insert(0, han_dir)

# 1. 確保 DB 存在（lazy init from schema.sql）
from servers import ensure_db
ensure_db()

# 2. 複製 agent 定義到 ~/.claude/agents/（如不存在）
agents_dir = os.path.expanduser('~/.claude/agents')
os.makedirs(agents_dir, exist_ok=True)
for f in globmod.glob(os.path.join(han_dir, 'reference', 'agents', '*.md')):
    dst = os.path.join(agents_dir, os.path.basename(f))
    if not os.path.exists(dst):
        shutil.copy2(f, dst)

# 3. 註冊 PostToolUse hook（如尚未設定）
settings_path = os.path.expanduser('~/.claude/settings.json')
hook_cmd = f"python3 {os.path.join(han_dir, 'hooks', 'post_task.py')}"
settings = {}
if os.path.exists(settings_path):
    with open(settings_path) as f:
        settings = json.load(f)
hooks_list = settings.setdefault('hooks', {}).setdefault('PostToolUse', [])
if not any(h.get('matcher') == 'Task' for h in hooks_list):
    hooks_list.append({"matcher": "Task", "hooks": [{"type": "command", "command": hook_cmd, "timeout": 30}]})
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

print("HAN-Agents ready.")
```

## Quick Start

```python
import sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/skills/han-agents'))

from servers.facade import get_full_context, check_drift, sync, finish_task
from servers.tasks import create_task, create_subtask, get_task_progress, get_epic_tasks, get_hierarchy_summary
from servers.memory import search_memory_semantic, store_memory, save_checkpoint, load_checkpoint
from servers.code_graph import get_class_dependencies_bfs
```

**DB**: `~/.claude/skills/han-agents/brain/brain.db`（首次呼叫時自動建立）

## Project Initialization

初始化專案 Skill 目錄：

```bash
# macOS/Linux
python ~/.claude/skills/han-agents/scripts/init_project.py <project-name> <project-path>

# Windows
python "%USERPROFILE%\.claude\skills\han-agents\scripts\init_project.py" <project-name> <project-path>
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

# BFS dependency graph (for Unit Test context)
deps = get_class_dependencies_bfs('my-project', 'UserService', max_depth=2)
# Returns: root, root_file, dependencies (with depth, via edge type)

# Hierarchical tasks (Jira-like: Epic → Story → Task → Bug)
epic_id = create_task(project='P', description='Epic task', task_level='epic')
story_id = create_task(project='P', description='Story', task_level='story', epic_id=epic_id)
task_id = create_task(project='P', description='Task', task_level='task', story_id=story_id)

# Query hierarchy
epics = get_epic_tasks('P')  # Returns epics with nested stories
summary = get_hierarchy_summary('P')  # {epics: N, stories: N, tasks: N, bugs: N}
```

## Agent Dispatch (Claude Code Task Tool)

**主對話必須使用 Claude Code Task tool 派發 agent：**

```
Task(
    subagent_type='pfc',        # 或 executor, critic, researcher, memory, drift-detector
    prompt='任務描述...'
)
```

**⭐ 派發 PFC 時必須包含的指示：**

```
Task(
    subagent_type='pfc',
    prompt=f'''PROJECT = "{project_name}"
PROJECT_PATH = "{project_path}"

任務：{user_request}

**要求：**
1. 先執行 sync(PROJECT_PATH, PROJECT) 同步 Code Graph
2. 分析任務範圍，使用 Code Graph 確認相關檔案
3. 規劃子任務 DAG
4. **必須呼叫 create_task() 將任務寫入 DB**
5. 輸出派發指令供主對話執行
'''
)
```

> ⚠️ **必要參數**：
> - `PROJECT` 和 `PROJECT_PATH` 是必填，供 agent 執行 `sync()` 和 `create_task()` 使用
> - prompt 必須明確要求 PFC 「呼叫 create_task() 將任務寫入 DB」，否則 PFC 可能只輸出規劃文字而不建立任務

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

## ⭐ 主對話：收到 PFC 輸出後的處理

**PFC agent 返回後，主對話必須：**

```python
# 1. 檢查 DB 任務狀態
from servers.tasks import get_task_progress
progress = get_task_progress(project="PROJECT_NAME")
pending_tasks = [t for t in progress.get('tasks', []) if t['status'] == 'pending']

# 2. 根據任務的 assigned_agent 派發對應 agent
# 3. 使用 Task tool 派發（executor/critic/researcher/memory 等）
```

**主對話職責（不可省略）：**
| 步驟 | 動作 |
|------|------|
| PFC 完成 | 讀取 DB 確認任務已建立 |
| 用戶確認 | 根據 `assigned_agent` 派發對應 agent |
| Agent 完成 | 檢查任務是否需要驗證，派發 critic |
| 全部完成 | 派發 memory 儲存經驗 |

**❌ 禁止：** 主對話看到 PFC 輸出後不操作 DB，只等用戶手動提醒

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
    prompt=f'''PROJECT = "{project_name}"
PROJECT_PATH = "{project_path}"
TASK_ID = "{critic_task_id}"
ORIGINAL_TASK_ID = "{original_task_id}"

**要求：**
1. 先執行 sync(PROJECT_PATH, PROJECT) 同步 Code Graph（確保驗證最新狀態）
2. 驗證任務產出...'''
)
```

> ⚠️ Critic 也需要 `PROJECT_PATH`，因為 Executor 可能修改了檔案，需要 sync 後才能正確驗證

## Scripts

```bash
python ~/.claude/skills/han-agents/scripts/install.py        # (Optional) 手動安裝，CI/CD 或非 Claude Code 平台用
python ~/.claude/skills/han-agents/scripts/doctor.py         # Diagnostics
python ~/.claude/skills/han-agents/scripts/sync.py PATH      # Graph sync
python ~/.claude/skills/han-agents/scripts/init_project.py   # Init project skill
```

## Reference

- [API_REFERENCE.md](reference/API_REFERENCE.md) - Complete API
- [WORKFLOW_GUIDE.md](reference/WORKFLOW_GUIDE.md) - Detailed workflow
- [GRAPH_GUIDE.md](reference/GRAPH_GUIDE.md) - Graph operations
- [TROUBLESHOOTING.md](reference/TROUBLESHOOTING.md) - Common issues
- [reference/agents/](reference/agents/) - Agent definitions

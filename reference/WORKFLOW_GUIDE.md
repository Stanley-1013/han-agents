# Workflow Guide

## Task Recovery

### New Conversation

```python
import sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/skills/han-agents'))
from servers.memory import get_project_context, load_checkpoint

project = os.path.basename(os.getcwd())
context = get_project_context(project)

if context['active_tasks']:
    task = context['active_tasks'][0]
    checkpoint = load_checkpoint(task['id'])
```

### Known Task ID

```python
from servers.tasks import get_task_progress
progress = get_task_progress('TASK_ID')
checkpoint = load_checkpoint('TASK_ID')
```

## Project Initialization

初始化專案 Skill 目錄：

```bash
python ~/.claude/skills/han-agents/scripts/init_project.py <project-path> [project-name]
```

建立 `<project>/.claude/skills/<project-name>/SKILL.md` 空白模板。

### 專案結構

```
<project>/
└── .claude/
    └── skills/
        └── <project-name>/
            ├── SKILL.md          # 專案核心文檔（由 LLM 填寫）
            ├── flows/            # 業務流程 (可選)
            │   └── *.md
            ├── domains/          # 領域模型 (可選)
            │   └── *.md
            └── apis/             # API 規格 (可選)
                └── *.md
```

## Starting Tasks

```python
from servers.tasks import create_task, create_subtask

task_id = create_task(project="PROJECT", description="Task", priority=8)
subtask_1 = create_subtask(task_id, "Step 1", assigned_agent='executor')
subtask_2 = create_subtask(task_id, "Step 2", depends_on=[subtask_1])
```

## Agent Dispatch Flow

```
PFC (plan) → Executor (do) → Critic (verify) → Memory (store)
     ↑                            │
     └────── REJECTED ────────────┘
```

### Dispatch Executor

```python
Task(
    subagent_type='executor',
    prompt=f'''TASK_ID = "{task_id}"
Task: [description]
Source: [file]
Steps: 1. Read 2. Execute 3. Verify'''
)
```

### Dispatch Critic

```python
Task(
    subagent_type='critic',
    prompt=f'''TASK_ID = "{critic_id}"
ORIGINAL_TASK_ID = "{original_id}"
Target: [file]
Criteria: Coverage >= 80%, Edge cases'''
)
```

## Validation Cycle

### Hook Flow

```
Executor ends → Hook: finish_task() → Phase: validation
Critic outputs APPROVED/CONDITIONAL/REJECTED → Hook: finish_validation()
```

### Handling Results

| Result | Action |
|--------|--------|
| APPROVED | Phase → documentation |
| CONDITIONAL | Store suggestions, continue |
| REJECTED | Phase → execution (retry) |

### Resume Rejected Task

```python
task = get_task(original_task_id)
if task.get('executor_agent_id'):
    Task(subagent_type='executor', resume=task['executor_agent_id'],
         prompt="Fix based on Critic feedback")
```

## Micro-Nap

```python
save_checkpoint(
    project='PROJECT',
    task_id=task_id,
    agent='pfc',
    state={'completed': [...], 'pending': [...]},
    summary='Phase 1 complete'
)
print("Suggest new conversation. Resume: Continue task {task_id}")
```

## Task/Memory APIs

```python
# Tasks
from servers.tasks import (
    create_task, create_subtask, get_task, update_task_status,
    get_next_task, get_task_progress, get_unvalidated_tasks,
    mark_validated, advance_task_phase
)
# Status: pending, running, done, failed, blocked
# Phase: execution, validation, documentation, completed

# Memory
from servers.memory import (
    search_memory, store_memory, get_working_memory, set_working_memory,
    save_checkpoint, load_checkpoint, add_episode
)
```

## Drift Detection

在開始重要修改前檢查 Skill vs Code 偏差：

```python
from servers.facade import check_drift

report = check_drift('/path/to/project', 'my-project')
if report['has_drift']:
    print(f"⚠️ {report['summary']}")
    for d in report['drifts']:
        print(f"  - [{d['severity']}] {d['description']}")
```

## 複雜任務原則

適用於：大型 codebase、多檔案變更、陌生專案

### 1. Research First（研究先行）

> 大型專案先派發 **Researcher** 收集 context，再規劃任務。

需要了解：
- 構建工具和版本（Maven/Gradle/npm）
- 測試框架（JUnit, Mockito, Jest）
- 專案慣例（命名規則、目錄結構）
- 目標範圍內的檔案清單

### 2. Context Precision（精準 context）

> 只讀必要檔案，避免 context 污染。

**錯誤**：「讀取整個 src/ 資料夾」
**正確**：「讀取被測類 + 依賴介面 + 相似範例」

### 3. Compile-First（編譯優先）

> 先確保編譯通過，再追求功能正確。

寫完代碼後立即執行編譯驗證，不要等到最後才發現依賴錯誤。

### 4. Incremental Fix（增量修復）

> 錯誤逐個修，不要一次改太多。

一次修一個編譯錯誤，確認修復後再處理下一個。

### 5. Memory Learning（記憶學習）

> 踩過的坑存入 Memory，下次避免。

```python
store_memory(
    category='error',
    title='Mock Strategy Error',
    content='使用 @Mock 而非 @MockBean 導致 Spring context 注入失敗',
    importance=8
)
```

---

## Best Practices

1. Parallel dispatch for independent tasks
2. Critic validates after each Executor
3. Store important discoveries to Memory
4. Checkpoint regularly
5. Check drift before major changes
6. Keep SKILL.md updated with implementation

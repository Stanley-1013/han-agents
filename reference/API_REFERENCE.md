# HAN API Reference

## Import

```python
import sys, os
from servers import HAN_BASE_DIR
sys.path.insert(0, HAN_BASE_DIR)

# Facade (recommended)
from servers.facade import (
    init, sync, status, get_full_context, check_drift, sync_skill_graph,
    finish_task, finish_validation, run_validation_cycle, validate_with_graph,
    get_next_dispatch,  # Dispatch loop orchestration
)

# Tasks
from servers.tasks import (
    create_task, create_subtask, get_task, update_task, update_task_status,
    get_next_task, get_task_progress, get_unvalidated_tasks, mark_validated,
    advance_task_phase, get_task_branch, set_task_branch,
    reserve_critic_task,  # Atomic critic reservation
    get_epic_tasks, get_story_tasks, get_hierarchy_summary,
)

# Recipes (automated workflows)
from servers.recipes import recipe_unit_tests, run_recipe

# Project
from servers.project import ensure_project

# Memory
from servers.memory import (
    search_memory, search_memory_semantic, store_memory, store_memory_smart,
    get_working_memory, set_working_memory, save_checkpoint, load_checkpoint,
    get_project_context, add_episode, get_recent_episodes
)
```

---

## Facade API

### init(project_path, project_name=None) -> Dict
Initialize project (first-time use).

### sync(project_path, project_name=None, incremental=True) -> Dict
Sync Code Graph. Returns `{files_processed, nodes_added, edges_added, duration_ms}`.

### status(project_path=None, project_name=None) -> Dict
Get project status overview (includes Skill status).

### get_full_context(branch, project_path=None, project_name=None) -> Dict
Get three-layer context (Skill + Code + Memory + Drift).
```python
ctx = get_full_context({'flow_id': 'flow.auth'}, '/path/to/project', 'my-project')
# {skill: {...}, code: {...}, memory: [...], drift: {...}}
```

### check_drift(project_path, project_name=None, flow_name=None) -> Dict
Check Skill vs Code drift. Returns `{has_drift, drift_count, drifts: [{type, description, severity}]}`.
```python
report = check_drift('/path/to/project', 'my-project', 'auth')
```

### sync_skill_graph(project_path=None, project_name=None) -> Dict
Sync project SKILL.md to project_nodes/edges.

### finish_task(task_id, success, result=None, error=None) -> Dict
Executor must call when done. Returns `{status, phase, next_action}`.

### finish_validation(task_id, original_task_id, approved, issues=None) -> Dict
Critic must call when done. Returns `{status, next_action, resume_agent_id}`.

### validate_with_graph(modified_files, branch, project_path=None, project_name=None) -> Dict
Graph-enhanced validation (impact analysis, Skill compliance, test coverage).

### get_next_dispatch(parent_id, project_name, project_path) -> Dict
Auto-dispatch next agent in the Executor → Critic → Memory pipeline.
Returns structured instruction for the main conversation to execute.

```python
inst = get_next_dispatch(epic_id, 'my-project', '/path/to/project')
# {
#     'action': 'dispatch' | 'done' | 'blocked' | 'waiting',
#     'subagent_type': 'executor' | 'critic' | 'memory',
#     'model_tier': 'planner' | 'worker' | 'fast',
#     'prompt': str,        # Complete prompt for Task tool
#     'task_id': str,       # For tracking
#     'progress': '3/7 tasks complete',
#     'message': str,       # Human-readable status
# }
```

**Idempotent**: repeated calls return the same critic task (no duplicates).
**Memory-aware**: waits for memory task to complete before returning `done`.

---

## Recipes API

### recipe_unit_tests(project_name, project_path, target_path=None, max_tasks=20) -> Dict
Auto-generate unit test task tree from coverage gaps.

```python
result = recipe_unit_tests('my-project', '/path/to/project', target_path='src/')
# {
#     'epic_id': str,      # Feed to get_next_dispatch()
#     'task_count': int,
#     'story_count': int,
#     'gaps_found': int,
#     'stories': [...],
#     'message': str,
# }
```

### run_recipe(name, **kwargs) -> Dict
Run recipe by name. Available: `'unit_tests'`.

---

## Project API

### ensure_project(project_name, project_path=None) -> Dict
Idempotent project initialization: sync Code Graph + detect tech stack + store in DB.

```python
result = ensure_project('my-project', '/path/to/project')
# {
#     'sync_result': {...},
#     'tech_stack': {'primary_language': 'python', 'test_tool': 'pytest', 'frameworks': [...]},
#     'already_initialized': bool,
# }
```

Tech stack is auto-detected from Code Graph (language distribution + import edges).
Upserts Tech Stack memory (no duplicate records on repeated calls).

---

## Tasks API

### create_task(project, description, priority=5, parent_id=None, task_level=None, epic_id=None, story_id=None, branch=None) -> str
Create task, returns task_id.
- `task_level`: 'epic', 'story', 'task', 'bug'
- `branch`: `{'flow_id': 'flow.auth', 'domain_ids': ['domain.user']}`

### create_subtask(parent_id, description, assigned_agent='executor', depends_on=None, requires_validation=True, task_level='task', epic_id=None, story_id=None) -> str
Create subtask with optional dependencies. Auto-inherits `epic_id`/`story_id` from parent when not specified.
- `assigned_agent`: 'executor', 'critic', 'memory', 'researcher'
- `depends_on`: list of task_ids

### get_task(task_id) -> Dict
Get task details (includes metadata, branch, executor_agent_id, rejection_count).

### update_task(task_id, **kwargs) -> None
Update task fields: executor_agent_id, rejection_count, status, phase, validation_status.

### update_task_status(task_id, status, result=None, error=None) -> None
Update status: 'pending', 'running', 'done', 'failed', 'blocked'.

### get_next_task(parent_id) -> Optional[Dict]
Get next executable task (dependencies completed).

### get_task_progress(parent_id) -> Dict
Get progress stats: `{total, completed, pending, percentage}`.

### get_unvalidated_tasks(parent_id) -> List[Dict]
Get tasks pending validation. Skips tasks that already have an active (pending/running) critic.

### reserve_critic_task(original_task_id) -> Optional[Dict]
Atomically reserve or reuse a critic task for a completed task. Uses `BEGIN IMMEDIATE` for concurrency safety.
Returns `{'id', 'original_task_id', 'original_description', 'result'}` or `None`.
**Idempotent**: repeated calls return the same critic task.

### mark_validated(task_id, status, validator_task_id=None) -> None
Mark validation: 'approved', 'rejected', 'skipped'.

### advance_task_phase(task_id, phase) -> None
Advance phase: 'execution', 'validation', 'documentation', 'completed'.

### get_task_branch(task_id) -> Optional[Dict]
Get task's branch info.

### set_task_branch(task_id, branch) -> None
Set task's branch info.

---

## Memory API

### search_memory_semantic(query, project=None, limit=5, rerank_mode='claude', **kwargs) -> Dict
Semantic search with reranking.
- `rerank_mode`: 'claude' (recommended), 'embedding', 'none'
```python
result = search_memory_semantic("auth pattern", rerank_mode='claude')
if result['mode'] == 'claude_rerank':
    print(result['rerank_prompt'])  # Agent selects best matches
```

### search_memory(query, project=None, category=None, limit=5, branch_flow=None) -> List[Dict]
Full-text search.
- `category`: 'sop', 'knowledge', 'error', 'preference', 'pattern', 'lesson'

### store_memory(category, content, title=None, project=None, importance=5, branch_flow=None) -> int
Store to long-term memory. Returns memory_id.
- `importance`: 1-10 (8-10 critical, 5-7 useful, 1-4 reference)

### store_memory_smart(category, content, title=None, project=None, importance=5, auto_supersede=True) -> Dict
Smart store: checks for similar memories first.
Returns `{id, action: 'created'|'superseded', superseded_ids}`.

### get_working_memory(task_id, key=None) -> Dict | Any
Read working memory (session-scoped key-value).

### set_working_memory(task_id, key, value, project=None) -> None
Set working memory.

### save_checkpoint(project, task_id, agent, state, summary) -> int
Save Micro-Nap checkpoint.
```python
save_checkpoint('proj', task_id, 'pfc',
    state={'completed': [...], 'pending': [...]},
    summary='Phase 1 complete')
```

### load_checkpoint(task_id) -> Optional[Dict]
Load latest checkpoint. Returns `{state, summary, created_at}`.

### get_project_context(project) -> Dict
Get project context for reconnection.
Returns `{active_tasks, last_phase, recent_activity, suggestion}`.

### add_episode(project, event_type, summary, details=None, session_id=None) -> int
Record event to episodic memory.
- `event_type`: 'task_completed', 'error_encountered', 'phase_complete', etc.

### get_recent_episodes(project, limit=5) -> List[Dict]
Get recent episodes.

---

## Memory Lifecycle

### challenge_memory(memory_id, reason, challenger='system') -> Dict
Mark memory as challenged. Returns `{success, memory_id, previous_status}`.

### resolve_challenge(memory_id, resolution, new_content=None) -> Dict
Resolve challenged memory.
- `resolution`: 'keep', 'update', 'deprecate'

### deprecate_memory(memory_id, reason=None) -> Dict
Deprecate memory directly.

### validate_memory(memory_id) -> Dict
Update last_validated timestamp.

### find_similar_memories(content, category=None, threshold=0.7, limit=5) -> List[Dict]
Find similar existing memories.

---

## Error Classes

```python
from servers.facade import (
    FacadeError, ProjectNotFoundError, NotInitializedError, CodeGraphEmptyError
)
```
All errors include actionable fix messages.

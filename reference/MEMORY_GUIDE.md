# Memory Operations Guide

記憶操作詳細指南。

## Import

```python
import sys, os
from servers import HAN_BASE_DIR
sys.path.insert(0, HAN_BASE_DIR)

from servers.memory import (
    # Search
    search_memory,           # Basic search
    search_memory_semantic,  # Semantic search with rerank

    # Store
    store_memory,            # Store to long-term memory

    # Working memory
    get_working_memory,      # Read working memory
    set_working_memory,      # Set working memory

    # Checkpoint
    save_checkpoint,         # Micro-Nap checkpoint
    load_checkpoint,         # Resume from checkpoint

    # Context
    get_project_context,     # Get active tasks

    # Events
    add_episode              # Record events
)
```

---

## Semantic Search

### Basic Search

```python
results = search_memory(
    query="authentication pattern",
    category='pattern',      # Optional filter
    project='my-project',    # Optional filter
    limit=5
)

for m in results:
    print(f"- {m['title']}: {m['content'][:100]}")
```

### Semantic Search with Rerank

```python
result = search_memory_semantic(
    query="authentication pattern",
    limit=5,
    rerank_mode='claude'  # 'fts5_only', 'claude', 'hybrid'
)

if result['mode'] == 'claude_rerank':
    # Agent selects best matches from candidates
    print(result['rerank_prompt'])
    # Contains candidates and instructions for Claude to rank
else:
    # Direct FTS5 results
    for m in result['results']:
        print(f"- {m['title']}")
```

### Rerank Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `fts5_only` | Full-text search only | Fast, keyword-based |
| `claude` | FTS5 + Claude reranking | Best relevance |
| `hybrid` | Weighted combination | Balanced |

---

## Store Memory

### Categories

| Category | Description | Examples |
|----------|-------------|----------|
| `pattern` | Reusable code patterns | Auth flow, API design |
| `lesson` | Lessons learned | Bug fixes, debugging tips |
| `procedure` | Step-by-step processes | Deployment SOP |
| `knowledge` | General knowledge | Architecture decisions |
| `sop` | Standard operating procedures | Team workflows |

### Store Pattern

```python
store_memory(
    category='pattern',
    title='JWT Token Refresh Pattern',
    content='''
When access token expires:
1. Check refresh token validity
2. Call /auth/refresh endpoint
3. Update stored tokens
4. Retry original request
    ''',
    project='my-project',
    importance=8,            # 1-10 scale
    branch_flow='flow.auth'  # Optional branch association
)
```

### Store Lesson

```python
store_memory(
    category='lesson',
    title='Race Condition in Auth Middleware',
    content='''
Problem: Multiple concurrent requests can trigger simultaneous token refreshes.
Solution: Use mutex/lock to ensure only one refresh at a time.
Files affected: src/middleware/auth.ts
    ''',
    project='my-project',
    importance=9
)
```

---

## Working Memory

Short-term key-value storage for current session.

### Set

```python
set_working_memory(
    task_id='xxx-001',
    key='current_files',
    value=['src/api/auth.ts', 'src/models/user.ts']
)

set_working_memory(
    task_id='xxx-001',
    key='critic_suggestions',
    value={'severity': 'medium', 'items': ['Add edge case test']}
)
```

### Get

```python
files = get_working_memory('xxx-001', 'current_files')
suggestions = get_working_memory('xxx-001', 'critic_suggestions')
```

### Expiration

Working memory expires automatically. Use for:
- Current task context
- Temporary state between agent calls
- Critic suggestions for main conversation

---

## Checkpoint (Micro-Nap)

### Save Checkpoint

Before context overflow or ending session:

```python
state = {
    'task_id': task_id,
    'completed': ['step1', 'step2'],
    'pending': ['step3', 'step4'],
    'current_phase': 'execution',
    'notes': 'Waiting for API response'
}

save_checkpoint(
    project='my-project',
    task_id=task_id,
    agent='pfc',              # Which agent saved this
    state=state,
    summary='Phase 1 complete, waiting on step3'
)
```

### Load Checkpoint

In new conversation:

```python
checkpoint = load_checkpoint(task_id)

if checkpoint:
    print(f"Agent: {checkpoint['agent']}")
    print(f"Summary: {checkpoint['summary']}")
    print(f"State: {checkpoint['state']}")
    # Resume from checkpoint['state']
```

### Best Practices

1. **Save regularly** - Every significant milestone
2. **Include summary** - Human-readable progress description
3. **Include pending tasks** - What needs to be done next
4. **Include context** - Any important state for resumption

---

## Project Context

### Get Active Tasks

```python
context = get_project_context('my-project')

# {
#   'active_tasks': [
#     {'id': 'xxx-001', 'description': '...', 'progress': '3/5'}
#   ],
#   'recent_memories': [...],
#   'suggestion': 'Continue task xxx-001'
# }
```

---

## Episodes

Record significant events for history:

```python
add_episode(
    session_id='session_123',
    event_type='task_completed',
    content={
        'task_id': 'xxx-001',
        'result': 'success',
        'files_modified': ['src/api/auth.ts']
    },
    project='my-project'
)

add_episode(
    session_id='session_123',
    event_type='error_encountered',
    content={
        'error': 'Connection timeout',
        'resolution': 'Retry with exponential backoff'
    },
    project='my-project'
)
```

### Event Types

- `task_created`
- `task_completed`
- `task_failed`
- `validation_passed`
- `validation_rejected`
- `error_encountered`
- `checkpoint_saved`
- `memory_stored`

---

## Memory Architecture

### Long-term Memory

Persisted across sessions:

```sql
long_term_memory (
    id, category, title, content,
    project, importance, branch_flow,
    created_at, updated_at
)
```

### Working Memory

Session-scoped key-value:

```sql
working_memory (
    task_id, key, value,
    created_at, expires_at
)
```

### Episodes

Event history:

```sql
episodes (
    id, session_id, event_type, content,
    project, created_at
)
```

### Checkpoints

Micro-Nap state:

```sql
checkpoints (
    task_id, agent, state, summary,
    created_at
)
```

---

## Agent Memory Queries

Each agent auto-queries relevant memory at startup:

| Agent | Categories | Purpose |
|-------|------------|---------|
| PFC | strategy, procedure | Task decomposition |
| Executor | pattern, lesson | Avoid mistakes |
| Critic | pattern, standard | Best practices |
| Memory | all | Knowledge management |

---

## Tips

1. **Use importance wisely** - 8-10 for critical, 5-7 for useful, 1-4 for reference
2. **Include context** - File paths, error messages, specific examples
3. **Use branch_flow** - Link memory to SSOT flows for better retrieval
4. **Don't over-store** - Only truly valuable learnings
5. **Update, don't duplicate** - Update existing memory if content evolves

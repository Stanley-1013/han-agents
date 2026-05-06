"""
HAN System - Server Tools
提供給 Agent 使用的工具庫
"""

import os
import sqlite3
import threading
from contextlib import contextmanager

# 動態計算 han-agents 根目錄和資料庫路徑
# 這樣無論安裝在哪個平台的 skills 目錄，都能正確找到資料庫
HAN_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAIN_DB = os.path.join(HAN_BASE_DIR, 'brain', 'brain.db')
SCHEMA_PATH = os.path.join(HAN_BASE_DIR, 'brain', 'schema.sql')
CACHE_DIR = os.path.join(HAN_BASE_DIR, 'cache', 'embeddings')

_db_initialized = False
_db_init_lock = threading.Lock()


def ensure_db() -> sqlite3.Connection:
    """取得資料庫連線，首次呼叫時自動從 schema.sql 初始化。"""
    global _db_initialized
    if not _db_initialized:
        with _db_init_lock:
            if not _db_initialized:
                if not os.path.exists(BRAIN_DB):
                    _init_db_from_schema()
                else:
                    _ensure_indexes()
                _db_initialized = True
    return sqlite3.connect(BRAIN_DB)


@contextmanager
def managed_connection(row_factory=False):
    """Context manager for database connections. Guarantees close() on exit."""
    conn = ensure_db()
    if row_factory:
        conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _ensure_indexes():
    """Ensure migration-safe schema additions exist on existing databases."""
    conn = sqlite3.connect(BRAIN_DB)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            INSERT OR IGNORE INTO schema_migrations (version, name)
            VALUES (1, 'base_schema');

            CREATE INDEX IF NOT EXISTS idx_code_nodes_project_file ON code_nodes(project, file_path);
            CREATE INDEX IF NOT EXISTS idx_code_edges_project_from_kind ON code_edges(project, from_id, kind);
            CREATE INDEX IF NOT EXISTS idx_code_edges_project_to_kind ON code_edges(project, to_id, kind);

            CREATE TABLE IF NOT EXISTS agent_traces (
                id TEXT PRIMARY KEY,
                workflow_name TEXT NOT NULL,
                project TEXT,
                group_id TEXT,
                metadata TEXT,
                status TEXT DEFAULT 'running',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS agent_spans (
                id TEXT PRIMARY KEY,
                trace_id TEXT NOT NULL,
                parent_span_id TEXT,
                task_id TEXT,
                name TEXT NOT NULL,
                span_type TEXT NOT NULL,
                status TEXT DEFAULT 'running',
                input TEXT,
                output TEXT,
                metadata TEXT,
                error TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                FOREIGN KEY (trace_id) REFERENCES agent_traces(id),
                FOREIGN KEY (parent_span_id) REFERENCES agent_spans(id),
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            );

            CREATE INDEX IF NOT EXISTS idx_agent_traces_project ON agent_traces(project);
            CREATE INDEX IF NOT EXISTS idx_agent_traces_group ON agent_traces(group_id);
            CREATE INDEX IF NOT EXISTS idx_agent_spans_trace ON agent_spans(trace_id);
            CREATE INDEX IF NOT EXISTS idx_agent_spans_parent ON agent_spans(parent_span_id);
            CREATE INDEX IF NOT EXISTS idx_agent_spans_task ON agent_spans(task_id);
            CREATE INDEX IF NOT EXISTS idx_agent_spans_type ON agent_spans(span_type);

            CREATE TABLE IF NOT EXISTS human_review_queue (
                id TEXT PRIMARY KEY,
                project TEXT,
                kind TEXT NOT NULL,
                severity TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'open',
                reason TEXT NOT NULL,
                task_id TEXT,
                trace_id TEXT,
                span_id TEXT,
                payload TEXT,
                reviewer TEXT,
                resolution TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(id),
                FOREIGN KEY (trace_id) REFERENCES agent_traces(id),
                FOREIGN KEY (span_id) REFERENCES agent_spans(id)
            );

            CREATE INDEX IF NOT EXISTS idx_human_review_status ON human_review_queue(status);
            CREATE INDEX IF NOT EXISTS idx_human_review_project ON human_review_queue(project);
            CREATE INDEX IF NOT EXISTS idx_human_review_task ON human_review_queue(task_id);
            CREATE INDEX IF NOT EXISTS idx_human_review_trace ON human_review_queue(trace_id);

            INSERT OR IGNORE INTO schema_migrations (version, name)
            VALUES (2, 'human_review_queue');
        """)
    except sqlite3.OperationalError:
        pass  # Tables may not exist yet
    finally:
        conn.close()


def _init_db_from_schema():
    """從 schema.sql 建立全新的資料庫。"""
    os.makedirs(os.path.dirname(BRAIN_DB), exist_ok=True)
    conn = sqlite3.connect(BRAIN_DB)
    try:
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            conn.executescript(f.read())
        conn.commit()
    finally:
        conn.close()


from .memory import *
from .tasks import *
from .platform import *
from .project import *
from .recipes import *
from .tracing import *
from .evals import *
from .guardrails import *
from .migrations import *
from .reviews import *

__version__ = "1.0.0"

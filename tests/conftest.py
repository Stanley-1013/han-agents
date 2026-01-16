"""
Pytest Fixtures for HAN Tests

提供：
- 隔離的測試資料庫
- Mock SSOT 數據
- Mock Code Graph 數據
"""

import pytest
import sqlite3
import tempfile
import os
import sys
import shutil

# 設定路徑
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BASE_DIR)

# Schema 路徑（動態計算）
SCHEMA_PATH = os.path.join(_BASE_DIR, 'brain', 'schema.sql')


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest.fixture
def test_db(tmp_path):
    """
    建立隔離的測試資料庫

    每個測試使用獨立的 SQLite 資料庫，測試結束後自動清理。
    """
    db_path = tmp_path / "test_brain.db"

    # 讀取 schema 並初始化
    conn = sqlite3.connect(str(db_path))

    with open(SCHEMA_PATH, encoding='utf-8') as f:
        conn.executescript(f.read())

    conn.commit()
    conn.close()

    yield str(db_path)

    # 清理
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def db_connection(test_db):
    """提供資料庫連線"""
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def mock_db_path(test_db, monkeypatch):
    """
    Monkey-patch 所有 servers 模組使用測試資料庫
    """
    monkeypatch.setenv('HAN_DB_PATH', test_db)

    # Patch 各模組的 DB 路徑（注意不同模組用不同變數名）
    import servers.graph as graph_mod
    import servers.memory as memory_mod
    import servers.tasks as tasks_mod
    import servers.code_graph as code_graph_mod
    import servers.registry as registry_mod

    # graph, memory, tasks 使用 BRAIN_DB
    monkeypatch.setattr(graph_mod, 'BRAIN_DB', test_db)
    monkeypatch.setattr(memory_mod, 'BRAIN_DB', test_db)
    monkeypatch.setattr(tasks_mod, 'BRAIN_DB', test_db)

    # code_graph, registry 使用 DB_PATH
    monkeypatch.setattr(code_graph_mod, 'DB_PATH', test_db)
    monkeypatch.setattr(registry_mod, 'DB_PATH', test_db)

    # 初始化 registry
    registry_mod.init_registry()

    return test_db


# =============================================================================
# SSOT Fixtures
# =============================================================================

@pytest.fixture
def mock_ssot_dir(tmp_path):
    """建立 Mock SSOT 目錄結構"""
    ssot_dir = tmp_path / "ssot"
    ssot_dir.mkdir()

    # PROJECT_DOCTRINE.md
    doctrine = ssot_dir / "PROJECT_DOCTRINE.md"
    doctrine.write_text("""# Test Project Doctrine

## 核心原則
1. 測試優先
2. 簡單設計
""")

    # PROJECT_INDEX.md
    index = ssot_dir / "PROJECT_INDEX.md"
    index.write_text("""# Project Index

## Flows
- id: flow.auth
  name: Authentication Flow
  ref: src/auth/

- id: flow.user
  name: User Management
  ref: src/user/

## Domains
- id: domain.user
  name: User Domain

## APIs
- id: api.login
  flow: flow.auth
  ref: src/api/login.py
""")

    # flows/ 目錄
    flows_dir = ssot_dir / "flows"
    flows_dir.mkdir()

    auth_flow = flows_dir / "auth.md"
    auth_flow.write_text("""# Authentication Flow

## 步驟
1. 用戶輸入憑證
2. 驗證憑證
3. 發放 Token
""")

    return ssot_dir


# =============================================================================
# Graph Fixtures
# =============================================================================

@pytest.fixture
def sample_graph_data(mock_db_path):
    """
    建立範例 Graph 數據

    結構：
    flow.auth → api.login → domain.user
              ↘ api.logout
    """
    from servers.graph import add_node, add_edge

    # Nodes - 參數順序: add_node(node_id, project, kind, name, ref=None)
    add_node("flow.auth", "test", "flow", "Auth Flow", "src/auth/")
    add_node("api.login", "test", "api", "Login API", "src/api/login.py")
    add_node("api.logout", "test", "api", "Logout API", "src/api/logout.py")
    add_node("domain.user", "test", "domain", "User Domain")

    # Edges - add_edge(from_id, to_id, kind, project)
    add_edge("flow.auth", "api.login", "implements", "test")
    add_edge("flow.auth", "api.logout", "implements", "test")
    add_edge("api.login", "domain.user", "uses", "test")

    return "test"


@pytest.fixture
def cyclic_graph_data(mock_db_path):
    """
    建立環形依賴的 Graph

    A → B → C → A
    """
    from servers.graph import add_node, add_edge

    # 參數順序: add_node(node_id, project, kind, name, ref=None)
    add_node("node.a", "cyclic", "test", "Node A")
    add_node("node.b", "cyclic", "test", "Node B")
    add_node("node.c", "cyclic", "test", "Node C")

    # add_edge(from_id, to_id, kind, project)
    add_edge("node.a", "node.b", "depends", "cyclic")
    add_edge("node.b", "node.c", "depends", "cyclic")
    add_edge("node.c", "node.a", "depends", "cyclic")

    return "cyclic"


# =============================================================================
# Code Graph Fixtures
# =============================================================================

@pytest.fixture
def sample_code_graph(mock_db_path):
    """建立範例 Code Graph 數據"""
    conn = sqlite3.connect(mock_db_path)

    # 插入 code_nodes
    nodes = [
        ("file.src/auth/login.py", "test", "file", "login.py", "src/auth/login.py", 1, 100, "python"),
        ("func.src/auth/login.py:authenticate", "test", "function", "authenticate", "src/auth/login.py", 10, 30, "python"),
        ("func.src/auth/login.py:validate_token", "test", "function", "validate_token", "src/auth/login.py", 35, 50, "python"),
        ("file.src/user/profile.py", "test", "file", "profile.py", "src/user/profile.py", 1, 80, "python"),
    ]

    for node in nodes:
        conn.execute("""
            INSERT INTO code_nodes (id, project, kind, name, file_path, line_start, line_end, language)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, node)

    # 插入 code_edges
    edges = [
        ("test", "file.src/auth/login.py", "func.src/auth/login.py:authenticate", "defines"),
        ("test", "file.src/auth/login.py", "func.src/auth/login.py:validate_token", "defines"),
        ("test", "func.src/auth/login.py:authenticate", "func.src/auth/login.py:validate_token", "calls"),
    ]

    for edge in edges:
        conn.execute("""
            INSERT INTO code_edges (project, from_id, to_id, kind)
            VALUES (?, ?, ?, ?)
        """, edge)

    conn.commit()
    conn.close()

    return "test"


# =============================================================================
# Memory Fixtures
# =============================================================================

@pytest.fixture
def sample_memories(mock_db_path):
    """建立範例記憶數據"""
    from servers.memory import store_memory

    memories = [
        ("pattern", "Auth patterns in Python", "Use JWT for stateless auth"),
        ("lesson", "Token validation", "Always validate expiry first"),
        ("knowledge", "User management", "CRUD operations on users"),
    ]

    ids = []
    for category, title, content in memories:
        mid = store_memory(
            category=category,
            content=content,
            title=title,
            project="test"
        )
        ids.append(mid)

    return ids


# =============================================================================
# Helper Functions
# =============================================================================

def insert_test_node(conn, project, node_id, kind, properties="{}"):
    """快速插入測試 node"""
    conn.execute("""
        INSERT OR REPLACE INTO project_nodes (project, id, kind, properties)
        VALUES (?, ?, ?, ?)
    """, (project, node_id, kind, properties))
    conn.commit()


def insert_test_edge(conn, project, from_id, to_id, kind):
    """快速插入測試 edge"""
    conn.execute("""
        INSERT OR REPLACE INTO project_edges (project, from_id, to_id, kind)
        VALUES (?, ?, ?, ?)
    """, (project, from_id, to_id, kind))
    conn.commit()

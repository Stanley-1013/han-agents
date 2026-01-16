"""
Graph Server - 輕量圖結構管理
==============================

Story 3: Graph Schema 與基礎 API

提供專案節點（Nodes）和邊（Edges）的管理功能，支援：
- 鄰居查詢（get_neighbors）
- 影響分析（get_impact）
- 從 L1 Index 同步節點（sync_from_index）

⚠️ API 參數順序原則：主要操作對象（node_id/from_id）在前，project 在後

使用方式：
    from servers.graph import add_node, add_edge, get_neighbors, get_impact

    # 添加節點 - add_node(node_id, project, kind, name, ref=None)
    add_node('flow.auth', 'my-project', 'flow', 'Authentication', 'flows/auth.md')

    # 添加邊 - add_edge(from_id, to_id, kind, project)
    add_edge('flow.auth', 'domain.user', 'uses', 'my-project')

    # 查詢鄰居 - get_neighbors(node_id, project, depth, direction)
    neighbors = get_neighbors('flow.auth', 'my-project', depth=1)

    # 查詢影響範圍 - get_impact(node_id, project)
    impacted = get_impact('domain.user', 'my-project')
"""

import sqlite3
import os
from typing import Optional, List, Dict, Any
from collections import deque

# 動態計算資料庫路徑（相對於此模組位置）
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAIN_DB = os.path.join(_BASE_DIR, 'brain', 'brain.db')

SCHEMA = """
=== Graph Server API ===

⚠️ 參數順序原則：主要操作對象（node_id/from_id）在前，project 在後

────────────────────────────────────────────────────────────────────
add_node(node_id, project, kind, name, ref=None) -> bool
────────────────────────────────────────────────────────────────────
    添加節點到圖中

    Parameters:
        node_id: str  - 節點 ID，如 'flow.auth', 'domain.user'
        project: str  - 專案名稱
        kind: str     - 節點類型 ('flow'|'domain'|'api'|'page'|'file'|'test')
        name: str     - 節點顯示名稱
        ref: str      - 參考位置，如 'flows/auth.md'（可選）

    Example:
        add_node('flow.auth', 'my-project', 'flow', 'Auth Flow', 'flows/auth.md')

    Returns: True if created, False if already exists

────────────────────────────────────────────────────────────────────
add_edge(from_id, to_id, kind, project) -> bool
────────────────────────────────────────────────────────────────────
    添加邊到圖中

    Parameters:
        from_id: str  - 起始節點 ID
        to_id: str    - 目標節點 ID
        kind: str     - 邊類型 ('uses'|'implements'|'calls'|'covers')
        project: str  - 專案名稱

    Example:
        add_edge('flow.auth', 'api.login', 'implements', 'my-project')

    Returns: True if created, False if already exists

────────────────────────────────────────────────────────────────────
get_neighbors(node_id, project=None, depth=1, direction='both') -> List[Dict]
────────────────────────────────────────────────────────────────────
    查詢節點的鄰居（BFS 遍歷）

    Parameters:
        node_id: str       - 節點 ID
        project: str       - 專案名稱（可選，NULL 查所有專案）
        depth: int         - 查詢深度（預設 1）
        direction: str     - 'outgoing'|'incoming'|'both'

    Example:
        get_neighbors('flow.auth', 'my-project', depth=2, direction='outgoing')

    Returns: [{id, kind, name, ref, edge_kind, distance}]

────────────────────────────────────────────────────────────────────
get_impact(node_id, project=None) -> List[Dict]
────────────────────────────────────────────────────────────────────
    查詢會被影響的節點（誰依賴我？）

    Parameters:
        node_id: str  - 節點 ID
        project: str  - 專案名稱（可選）

    Example:
        get_impact('api.login', 'my-project')

    Returns: [{id, kind, name, edge_kind}] - 所有指向此節點的節點

────────────────────────────────────────────────────────────────────
get_node(node_id, project) -> Optional[Dict]
────────────────────────────────────────────────────────────────────
    獲取節點詳情

    Parameters:
        node_id: str  - 節點 ID
        project: str  - 專案名稱

    Example:
        get_node('flow.auth', 'my-project')

    Returns: {id, project, kind, name, ref} 或 None

────────────────────────────────────────────────────────────────────
list_nodes(project, kind=None) -> List[Dict]
────────────────────────────────────────────────────────────────────
    列出專案的所有節點

    Parameters:
        project: str  - 專案名稱
        kind: str     - 節點類型過濾（可選）

    Example:
        list_nodes('my-project', kind='flow')

    Returns: [{id, kind, name, ref}]

────────────────────────────────────────────────────────────────────
sync_from_index(project, index_data) -> Dict
────────────────────────────────────────────────────────────────────
    從 L1 Index 同步節點到圖

    Parameters:
        project: str       - 專案名稱
        index_data: dict   - parse_index() 返回的結構化數據

    Returns: {nodes_added, edges_added}

────────────────────────────────────────────────────────────────────
delete_node(node_id, project) -> bool
────────────────────────────────────────────────────────────────────
    刪除節點及相關邊

────────────────────────────────────────────────────────────────────
delete_edge(from_id, to_id, kind, project) -> bool
────────────────────────────────────────────────────────────────────
    刪除特定邊

=== Story 7: Task Trace 與熱點分析 ===

record_node_access(project, node_id, agent, task_id=None, access_type='read') -> int
    記錄節點訪問

    Parameters:
        project: 專案名稱
        node_id: 訪問的節點 ID
        agent: 訪問的 agent（pfc, executor, critic）
        task_id: 關聯的任務 ID（可選）
        access_type: 訪問類型 ('read'|'write'|'validate')

    Returns: 記錄 ID

get_hot_nodes(project, limit=10, days=None) -> List[Dict]
    查詢熱點節點（最常被訪問）

    Parameters:
        project: 專案名稱
        limit: 返回數量（預設 10）
        days: 只統計最近 N 天（可選，None 表示全部）

    Returns: [{node_id, access_count, last_accessed, kind, name}]

get_cold_nodes(project, days=30) -> List[Dict]
    查詢冰區節點（長時間未訪問）

    Parameters:
        project: 專案名稱
        days: 超過 N 天未訪問視為冰區（預設 30）

    Returns: [{node_id, kind, name, last_accessed, days_since_access}]

get_access_history(project, node_id=None, limit=50) -> List[Dict]
    查詢訪問歷史

    Parameters:
        project: 專案名稱
        node_id: 節點 ID（可選，None 查全部）
        limit: 返回數量（預設 50）

    Returns: [{id, node_id, agent, task_id, access_type, accessed_at}]
"""

def get_db():
    """取得資料庫連線"""
    return sqlite3.connect(BRAIN_DB)


def _ensure_tables():
    """確保 Graph 表存在"""
    db = get_db()
    cursor = db.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS project_nodes (
            id TEXT NOT NULL,
            project TEXT NOT NULL,
            kind TEXT NOT NULL,
            name TEXT NOT NULL,
            ref TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id, project)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS project_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            from_id TEXT NOT NULL,
            to_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project, from_id, to_id, kind)
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_edges_from ON project_edges(from_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_edges_to ON project_edges(to_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_edges_project ON project_edges(project)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_nodes_project ON project_nodes(project)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_nodes_kind ON project_nodes(kind)')

    db.commit()
    db.close()


def add_node(node_id: str, project: str, kind: str, name: str,
             ref: str = None) -> bool:
    """添加節點到圖中

    Args:
        node_id: 節點 ID，如 'flow.auth', 'domain.user'
        project: 專案名稱
        kind: 節點類型 ('flow'|'domain'|'api'|'page'|'file'|'test')
        name: 節點顯示名稱
        ref: 參考位置，如 'flows/auth.md'

    Returns:
        True if created, False if already exists
    """
    _ensure_tables()
    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute('''
            INSERT INTO project_nodes (id, project, kind, name, ref)
            VALUES (?, ?, ?, ?, ?)
        ''', (node_id, project, kind, name, ref))
        db.commit()
        db.close()
        return True
    except sqlite3.IntegrityError:
        db.close()
        return False


def add_edge(from_id: str, to_id: str, kind: str, project: str) -> bool:
    """添加邊到圖中

    ⚠️ 參數順序：(from_id, to_id, kind, project) - 與 add_node 風格一致

    Args:
        from_id: 起始節點 ID（如 'flow.auth'）
        to_id: 目標節點 ID（如 'api.login'）
        kind: 邊類型 ('uses'|'implements'|'calls'|'covers')
        project: 專案名稱

    Returns:
        True if created, False if already exists

    Example:
        add_edge('flow.auth', 'api.login', 'implements', 'my-project')
    """
    _ensure_tables()
    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute('''
            INSERT INTO project_edges (project, from_id, to_id, kind)
            VALUES (?, ?, ?, ?)
        ''', (project, from_id, to_id, kind))
        db.commit()
        db.close()
        return True
    except sqlite3.IntegrityError:
        db.close()
        return False


def get_node(node_id: str, project: str) -> Optional[Dict]:
    """獲取節點詳情

    Args:
        node_id: 節點 ID
        project: 專案名稱

    Returns:
        {id, project, kind, name, ref} 或 None
    """
    _ensure_tables()
    db = get_db()
    cursor = db.cursor()

    cursor.execute('''
        SELECT id, project, kind, name, ref
        FROM project_nodes
        WHERE id = ? AND project = ?
    ''', (node_id, project))

    row = cursor.fetchone()
    db.close()

    if row:
        return {
            'id': row[0],
            'project': row[1],
            'kind': row[2],
            'name': row[3],
            'ref': row[4]
        }
    return None


def list_nodes(project: str, kind: str = None) -> List[Dict]:
    """列出專案的所有節點

    Args:
        project: 專案名稱
        kind: 節點類型過濾（可選）

    Returns:
        [{id, kind, name, ref}]
    """
    _ensure_tables()
    db = get_db()
    cursor = db.cursor()

    sql = 'SELECT id, kind, name, ref FROM project_nodes WHERE project = ?'
    params = [project]

    if kind:
        sql += ' AND kind = ?'
        params.append(kind)

    sql += ' ORDER BY kind, id'

    cursor.execute(sql, params)
    results = []

    for row in cursor.fetchall():
        results.append({
            'id': row[0],
            'kind': row[1],
            'name': row[2],
            'ref': row[3]
        })

    db.close()
    return results


def get_neighbors(node_id: str, project: str = None, depth: int = 1,
                  direction: str = 'both') -> List[Dict]:
    """查詢節點的鄰居

    使用 BFS 遍歷指定深度內的所有鄰居節點。

    Args:
        node_id: 節點 ID
        project: 專案名稱（可選，NULL 查所有專案）
        depth: 查詢深度（預設 1）
        direction: 'outgoing'|'incoming'|'both'

    Returns:
        [{id, kind, name, ref, edge_kind, distance}]
    """
    _ensure_tables()
    db = get_db()
    cursor = db.cursor()

    visited = {node_id}
    results = []
    queue = deque([(node_id, 0)])  # (node_id, current_depth)

    while queue:
        current_id, current_depth = queue.popleft()

        if current_depth >= depth:
            continue

        # 查詢 outgoing edges (current -> neighbor)
        if direction in ('outgoing', 'both'):
            sql = '''
                SELECT e.to_id, e.kind, n.kind, n.name, n.ref
                FROM project_edges e
                LEFT JOIN project_nodes n ON e.to_id = n.id AND e.project = n.project
                WHERE e.from_id = ?
            '''
            params = [current_id]

            if project:
                sql += ' AND e.project = ?'
                params.append(project)

            cursor.execute(sql, params)

            for row in cursor.fetchall():
                neighbor_id = row[0]
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    results.append({
                        'id': neighbor_id,
                        'edge_kind': row[1],
                        'kind': row[2],
                        'name': row[3],
                        'ref': row[4],
                        'distance': current_depth + 1,
                        'direction': 'outgoing'
                    })
                    queue.append((neighbor_id, current_depth + 1))

        # 查詢 incoming edges (neighbor -> current)
        if direction in ('incoming', 'both'):
            sql = '''
                SELECT e.from_id, e.kind, n.kind, n.name, n.ref
                FROM project_edges e
                LEFT JOIN project_nodes n ON e.from_id = n.id AND e.project = n.project
                WHERE e.to_id = ?
            '''
            params = [current_id]

            if project:
                sql += ' AND e.project = ?'
                params.append(project)

            cursor.execute(sql, params)

            for row in cursor.fetchall():
                neighbor_id = row[0]
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    results.append({
                        'id': neighbor_id,
                        'edge_kind': row[1],
                        'kind': row[2],
                        'name': row[3],
                        'ref': row[4],
                        'distance': current_depth + 1,
                        'direction': 'incoming'
                    })
                    queue.append((neighbor_id, current_depth + 1))

    db.close()
    return results


def get_impact(node_id: str, project: str = None) -> List[Dict]:
    """查詢會被影響的節點（誰依賴我？）

    回答問題：「如果我修改這個節點，哪些地方會受影響？」

    Args:
        node_id: 節點 ID
        project: 專案名稱（可選）

    Returns:
        [{id, kind, name, edge_kind}] - 所有指向此節點的節點
    """
    _ensure_tables()
    db = get_db()
    cursor = db.cursor()

    sql = '''
        SELECT e.from_id, e.kind, n.kind, n.name, n.ref
        FROM project_edges e
        LEFT JOIN project_nodes n ON e.from_id = n.id AND e.project = n.project
        WHERE e.to_id = ?
    '''
    params = [node_id]

    if project:
        sql += ' AND e.project = ?'
        params.append(project)

    cursor.execute(sql, params)
    results = []

    for row in cursor.fetchall():
        results.append({
            'id': row[0],
            'edge_kind': row[1],
            'kind': row[2],
            'name': row[3],
            'ref': row[4]
        })

    db.close()
    return results


def sync_from_index(project: str, index_data: Dict[str, List[Dict]]) -> Dict[str, int]:
    """從 L1 Index 同步節點到圖

    自動從 parse_index() 返回的數據中創建節點和邊。

    Args:
        project: 專案名稱
        index_data: parse_index() 返回的結構化數據
            {
                'flows': [{'id': 'flow.auth', 'name': 'Authentication', 'spec': '...'}],
                'domains': [...],
                'apis': [...],
                'pages': [...],
                'tests': [...]
            }

    Returns:
        {nodes_added: int, edges_added: int}
    """
    _ensure_tables()

    nodes_added = 0
    edges_added = 0

    # 動態處理所有類型：collection_name (複數) -> kind (單數)
    # 例如: 'flows' -> 'flow', 'apis' -> 'api', 'commands' -> 'command'
    def pluralize_to_kind(collection_name: str) -> str:
        """將複數形式轉為單數 kind"""
        if collection_name.endswith('ies'):
            return collection_name[:-3] + 'y'  # e.g. 'categories' -> 'category'
        elif collection_name.endswith('s'):
            return collection_name[:-1]  # e.g. 'flows' -> 'flow'
        return collection_name

    # 1. 創建所有節點（動態處理任何類型）
    for collection_name, items in index_data.items():
        if not isinstance(items, list):
            continue

        kind = pluralize_to_kind(collection_name)

        for item in items:
            if not isinstance(item, dict):
                continue

            node_id = item.get('id')
            name = item.get('name', node_id)
            # 支援多種 ref 字段名稱
            ref = item.get('ref') or item.get('spec') or item.get('file') or item.get('path')

            if node_id and add_node(node_id, project, kind, name, ref):
                nodes_added += 1

    # 2. 動態創建邊（從任何有 flow/domain/covers 等關聯的節點）
    for collection_name, items in index_data.items():
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            item_id = item.get('id')
            if not item_id:
                continue

            # flow 關聯 -> implements 邊
            flow_id = item.get('flow')
            if flow_id:
                # add_edge(from_id, to_id, kind, project)
                if add_edge(flow_id, item_id, 'implements', project):
                    edges_added += 1

            # domain 關聯 -> uses 邊
            domain_id = item.get('domain')
            if domain_id:
                if add_edge(item_id, domain_id, 'uses', project):
                    edges_added += 1

            # covers 關聯 -> covers 邊
            covers = item.get('covers', [])
            if isinstance(covers, list):
                for covered_id in covers:
                    if add_edge(item_id, covered_id, 'covers', project):
                        edges_added += 1

            # depends 關聯 -> depends 邊
            depends = item.get('depends', [])
            if isinstance(depends, list):
                for dep_id in depends:
                    if add_edge(item_id, dep_id, 'depends', project):
                        edges_added += 1

    return {
        'nodes_added': nodes_added,
        'edges_added': edges_added
    }


def delete_node(node_id: str, project: str) -> bool:
    """刪除節點及相關邊

    Args:
        node_id: 節點 ID
        project: 專案名稱

    Returns:
        True if deleted, False if not found
    """
    _ensure_tables()
    db = get_db()
    cursor = db.cursor()

    # 先刪除相關邊
    cursor.execute('''
        DELETE FROM project_edges
        WHERE project = ? AND (from_id = ? OR to_id = ?)
    ''', (project, node_id, node_id))

    # 再刪除節點
    cursor.execute('''
        DELETE FROM project_nodes
        WHERE id = ? AND project = ?
    ''', (node_id, project))

    deleted = cursor.rowcount > 0
    db.commit()
    db.close()
    return deleted


def delete_edge(project: str, from_id: str, to_id: str, kind: str) -> bool:
    """刪除特定邊

    Args:
        project: 專案名稱
        from_id: 起始節點 ID
        to_id: 目標節點 ID
        kind: 邊類型

    Returns:
        True if deleted, False if not found
    """
    _ensure_tables()
    db = get_db()
    cursor = db.cursor()

    cursor.execute('''
        DELETE FROM project_edges
        WHERE project = ? AND from_id = ? AND to_id = ? AND kind = ?
    ''', (project, from_id, to_id, kind))

    deleted = cursor.rowcount > 0
    db.commit()
    db.close()
    return deleted


def get_graph_stats(project: str) -> Dict[str, Any]:
    """獲取圖的統計信息

    Args:
        project: 專案名稱

    Returns:
        {
            node_count: int,
            edge_count: int,
            nodes_by_kind: {kind: count},
            edges_by_kind: {kind: count}
        }
    """
    _ensure_tables()
    db = get_db()
    cursor = db.cursor()

    # 節點統計
    cursor.execute('''
        SELECT kind, COUNT(*) FROM project_nodes
        WHERE project = ? GROUP BY kind
    ''', (project,))
    nodes_by_kind = dict(cursor.fetchall())

    # 邊統計
    cursor.execute('''
        SELECT kind, COUNT(*) FROM project_edges
        WHERE project = ? GROUP BY kind
    ''', (project,))
    edges_by_kind = dict(cursor.fetchall())

    db.close()

    return {
        'node_count': sum(nodes_by_kind.values()),
        'edge_count': sum(edges_by_kind.values()),
        'nodes_by_kind': nodes_by_kind,
        'edges_by_kind': edges_by_kind
    }


# =============================================================================
# Story 7: Task Trace 與熱點分析
# =============================================================================

def _ensure_access_table():
    """確保 task_node_access 表存在"""
    db = get_db()
    cursor = db.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_node_access (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            task_id TEXT,
            node_id TEXT NOT NULL,
            agent TEXT NOT NULL,
            access_type TEXT DEFAULT 'read',
            accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_node_access_project ON task_node_access(project)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_node_access_node ON task_node_access(node_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_node_access_time ON task_node_access(accessed_at)')

    db.commit()
    db.close()


def record_node_access(project: str, node_id: str, agent: str,
                       task_id: str = None, access_type: str = 'read') -> int:
    """記錄節點訪問

    Args:
        project: 專案名稱
        node_id: 訪問的節點 ID
        agent: 訪問的 agent（pfc, executor, critic）
        task_id: 關聯的任務 ID（可選）
        access_type: 訪問類型 ('read'|'write'|'validate')

    Returns:
        記錄 ID
    """
    _ensure_access_table()
    db = get_db()
    cursor = db.cursor()

    cursor.execute('''
        INSERT INTO task_node_access (project, task_id, node_id, agent, access_type)
        VALUES (?, ?, ?, ?, ?)
    ''', (project, task_id, node_id, agent, access_type))

    record_id = cursor.lastrowid
    db.commit()
    db.close()
    return record_id


def get_hot_nodes(project: str, limit: int = 10, days: int = None) -> List[Dict]:
    """查詢熱點節點（最常被訪問）

    Args:
        project: 專案名稱
        limit: 返回數量（預設 10）
        days: 只統計最近 N 天（可選，None 表示全部）

    Returns:
        [{node_id, access_count, last_accessed, kind, name}]
    """
    _ensure_access_table()
    _ensure_tables()
    db = get_db()
    cursor = db.cursor()

    sql = '''
        SELECT a.node_id, COUNT(*) as access_count, MAX(a.accessed_at) as last_accessed,
               n.kind, n.name
        FROM task_node_access a
        LEFT JOIN project_nodes n ON a.node_id = n.id AND a.project = n.project
        WHERE a.project = ?
    '''
    params = [project]

    if days:
        sql += " AND a.accessed_at >= datetime('now', ?)"
        params.append(f'-{days} days')

    sql += '''
        GROUP BY a.node_id
        ORDER BY access_count DESC
        LIMIT ?
    '''
    params.append(limit)

    cursor.execute(sql, params)
    results = []

    for row in cursor.fetchall():
        results.append({
            'node_id': row[0],
            'access_count': row[1],
            'last_accessed': row[2],
            'kind': row[3],
            'name': row[4]
        })

    db.close()
    return results


def get_cold_nodes(project: str, days: int = 30) -> List[Dict]:
    """查詢冰區節點（長時間未訪問）

    Args:
        project: 專案名稱
        days: 超過 N 天未訪問視為冰區（預設 30）

    Returns:
        [{node_id, kind, name, last_accessed, days_since_access}]
    """
    _ensure_access_table()
    _ensure_tables()
    db = get_db()
    cursor = db.cursor()

    # 找出所有節點及其最後訪問時間
    cursor.execute('''
        SELECT n.id, n.kind, n.name,
               MAX(a.accessed_at) as last_accessed,
               CAST(julianday('now') - julianday(MAX(a.accessed_at)) AS INTEGER) as days_since
        FROM project_nodes n
        LEFT JOIN task_node_access a ON n.id = a.node_id AND n.project = a.project
        WHERE n.project = ?
        GROUP BY n.id
        HAVING last_accessed IS NULL
           OR julianday('now') - julianday(MAX(a.accessed_at)) > ?
        ORDER BY last_accessed ASC NULLS FIRST
    ''', (project, days))

    results = []

    for row in cursor.fetchall():
        results.append({
            'node_id': row[0],
            'kind': row[1],
            'name': row[2],
            'last_accessed': row[3],
            'days_since_access': row[4] if row[4] else 'never'
        })

    db.close()
    return results


def get_access_history(project: str, node_id: str = None, limit: int = 50) -> List[Dict]:
    """查詢訪問歷史

    Args:
        project: 專案名稱
        node_id: 節點 ID（可選，None 查全部）
        limit: 返回數量（預設 50）

    Returns:
        [{id, node_id, agent, task_id, access_type, accessed_at}]
    """
    _ensure_access_table()
    db = get_db()
    cursor = db.cursor()

    sql = '''
        SELECT id, node_id, agent, task_id, access_type, accessed_at
        FROM task_node_access
        WHERE project = ?
    '''
    params = [project]

    if node_id:
        sql += ' AND node_id = ?'
        params.append(node_id)

    sql += ' ORDER BY accessed_at DESC LIMIT ?'
    params.append(limit)

    cursor.execute(sql, params)
    results = []

    for row in cursor.fetchall():
        results.append({
            'id': row[0],
            'node_id': row[1],
            'agent': row[2],
            'task_id': row[3],
            'access_type': row[4],
            'accessed_at': row[5]
        })

    db.close()
    return results


# =============================================================================
# 測試入口
# =============================================================================

if __name__ == "__main__":
    print(SCHEMA)
    print("\n" + "=" * 50 + "\n")

    # 測試基本功能
    test_project = "_test_graph_"

    print("=== Testing add_node() ===")
    add_node('flow.auth', test_project, 'flow', 'Authentication', 'flows/auth.md')
    add_node('domain.user', test_project, 'domain', 'User Management', 'domains/user.md')
    add_node('api.auth.login', test_project, 'api', 'Login API', '/api/auth/login')
    print("Added 3 nodes")

    print("\n=== Testing add_edge() ===")
    add_edge(test_project, 'flow.auth', 'domain.user', 'uses')
    add_edge(test_project, 'flow.auth', 'api.auth.login', 'implements')
    print("Added 2 edges")

    print("\n=== Testing get_neighbors() ===")
    neighbors = get_neighbors('flow.auth', project=test_project, depth=1)
    print(f"Neighbors of flow.auth: {len(neighbors)}")
    for n in neighbors:
        print(f"  - {n['id']} ({n['edge_kind']}, direction={n['direction']})")

    print("\n=== Testing get_impact() ===")
    impact = get_impact('domain.user', project=test_project)
    print(f"Impact on domain.user: {len(impact)}")
    for i in impact:
        print(f"  - {i['id']} ({i['edge_kind']})")

    print("\n=== Testing get_graph_stats() ===")
    stats = get_graph_stats(test_project)
    print(f"Stats: {stats}")

    # 清理測試數據
    print("\n=== Cleaning up ===")
    delete_node('flow.auth', test_project)
    delete_node('domain.user', test_project)
    delete_node('api.auth.login', test_project)
    print("Test data cleaned")

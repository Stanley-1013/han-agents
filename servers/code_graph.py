"""
Code Graph Server

提供 Code Graph 的查詢和更新 API。
整合 Code Graph Extractor，支援增量更新。

設計原則：
1. 與 SSOT Graph（project_nodes/edges）分開
2. 支援增量更新，只處理變更檔案
3. 提供友善的錯誤訊息
"""

import sqlite3
import json
import os
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# =============================================================================
# SCHEMA（供 Agent 參考）
# =============================================================================

SCHEMA = """
=== Code Graph API ===

sync_from_directory(project, directory, incremental=True) -> SyncResult
    從目錄同步 Code Graph（主要 API）
    - project: 專案名稱
    - directory: 目錄路徑
    - incremental: 是否增量更新（預設 True）
    Returns: {
        'nodes_added': int,
        'nodes_updated': int,
        'edges_added': int,
        'files_processed': int,
        'files_skipped': int,
        'errors': List[str]
    }

get_code_nodes(project, kind=None, file_path=None, limit=100) -> List[Dict]
    查詢 Code Nodes
    - kind: 過濾類型（可選）
    - file_path: 過濾檔案（可選）
    Returns: [{id, kind, name, file_path, line_start, line_end, ...}]

get_code_edges(project, from_id=None, to_id=None, kind=None, limit=100) -> List[Dict]
    查詢 Code Edges
    Returns: [{from_id, to_id, kind, line_number, confidence}]

get_code_dependencies(project, node_id, depth=1, direction='both') -> List[Dict]
    查詢節點的依賴關係
    - direction: 'incoming', 'outgoing', 'both'
    Returns: [{id, kind, name, relation, depth}]

get_file_structure(project, file_path) -> Dict
    取得檔案的結構摘要
    Returns: {
        'file': {...},
        'classes': [...],
        'functions': [...],
        'imports': [...]
    }

clear_code_graph(project) -> int
    清除專案的 Code Graph（重建前使用）
    Returns: 刪除的 node 數量

get_code_graph_stats(project) -> Dict
    取得 Code Graph 統計
    Returns: {
        'node_count': int,
        'edge_count': int,
        'file_count': int,
        'kinds': {kind: count},
        'last_sync': datetime
    }
"""

# =============================================================================
# Database Connection
# =============================================================================

# 動態計算資料庫路徑（相對於此模組位置）
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(_BASE_DIR, 'brain', 'brain.db')

def get_db() -> sqlite3.Connection:
    """取得資料庫連線"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# =============================================================================
# Sync API
# =============================================================================

def sync_from_directory(
    project: str,
    directory: str,
    incremental: bool = True
) -> Dict:
    """
    從目錄同步 Code Graph

    Args:
        project: 專案名稱
        directory: 目錄路徑
        incremental: 是否增量更新

    Returns:
        同步結果統計
    """
    from tools.code_graph_extractor import extract_from_directory

    conn = get_db()

    try:
        # 1. 取得現有的 file hashes（用於增量比對）
        existing_hashes = {}
        if incremental:
            cursor = conn.execute(
                "SELECT file_path, hash FROM file_hashes WHERE project = ?",
                (project,)
            )
            existing_hashes = {row['file_path']: row['hash'] for row in cursor.fetchall()}

        # 2. 提取
        result = extract_from_directory(
            directory=directory,
            incremental=incremental,
            project=project,
            file_hashes=existing_hashes
        )

        if result['errors']:
            return {
                'nodes_added': 0,
                'nodes_updated': 0,
                'edges_added': 0,
                'files_processed': 0,
                'files_skipped': 0,
                'errors': result['errors']
            }

        # 3. 更新資料庫
        nodes_added = 0
        nodes_updated = 0
        edges_added = 0

        # 插入/更新 nodes
        for node in result['nodes']:
            try:
                conn.execute(
                    """
                    INSERT INTO code_nodes
                    (id, project, kind, name, file_path, line_start, line_end, signature, language, visibility, hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id, project) DO UPDATE SET
                        kind = excluded.kind,
                        name = excluded.name,
                        file_path = excluded.file_path,
                        line_start = excluded.line_start,
                        line_end = excluded.line_end,
                        signature = excluded.signature,
                        language = excluded.language,
                        visibility = excluded.visibility,
                        hash = excluded.hash,
                        last_updated = CURRENT_TIMESTAMP
                    """,
                    (
                        node['id'], project, node['kind'], node['name'],
                        node['file_path'], node.get('line_start', 0), node.get('line_end', 0),
                        node.get('signature'), node.get('language'), node.get('visibility'), node.get('hash')
                    )
                )
                if conn.total_changes > 0:
                    nodes_added += 1
            except sqlite3.IntegrityError:
                nodes_updated += 1

        # 插入 edges（先刪除舊的再插入新的）
        processed_files = set(n['file_path'] for n in result['nodes'] if n['kind'] == 'file')
        for file_path in processed_files:
            # 刪除此檔案產出的舊 edges
            conn.execute(
                """
                DELETE FROM code_edges
                WHERE project = ? AND from_id LIKE ?
                """,
                (project, f"%.{file_path}%")
            )

        for edge in result['edges']:
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO code_edges
                    (project, from_id, to_id, kind, line_number, confidence)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project, edge['from_id'], edge['to_id'], edge['kind'],
                        edge.get('line_number'), edge.get('confidence', 1.0)
                    )
                )
                edges_added += 1
            except sqlite3.IntegrityError:
                pass

        # 更新 file hashes
        for file_path, hash_val in result['file_hashes'].items():
            node_count = sum(1 for n in result['nodes'] if n.get('file_path') == file_path or n.get('file_path', '').endswith(file_path))
            edge_count = sum(1 for e in result['edges'] if file_path in e.get('from_id', ''))

            conn.execute(
                """
                INSERT INTO file_hashes (project, file_path, hash, node_count, edge_count)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(project, file_path) DO UPDATE SET
                    hash = excluded.hash,
                    node_count = excluded.node_count,
                    edge_count = excluded.edge_count,
                    last_updated = CURRENT_TIMESTAMP
                """,
                (project, file_path, hash_val, node_count, edge_count)
            )

        conn.commit()

        return {
            'nodes_added': nodes_added,
            'nodes_updated': nodes_updated,
            'edges_added': edges_added,
            'files_processed': result['files_processed'],
            'files_skipped': result['files_skipped'],
            'errors': []
        }

    finally:
        conn.close()

# =============================================================================
# Query API
# =============================================================================

def get_code_nodes(
    project: str,
    kind: str = None,
    file_path: str = None,
    limit: int = 100
) -> List[Dict]:
    """查詢 Code Nodes"""
    conn = get_db()
    try:
        query = "SELECT * FROM code_nodes WHERE project = ?"
        params = [project]

        if kind:
            query += " AND kind = ?"
            params.append(kind)

        if file_path:
            query += " AND file_path LIKE ?"
            params.append(f"%{file_path}%")

        query += " ORDER BY file_path, line_start LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def get_code_edges(
    project: str,
    from_id: str = None,
    to_id: str = None,
    kind: str = None,
    limit: int = 100
) -> List[Dict]:
    """查詢 Code Edges"""
    conn = get_db()
    try:
        query = "SELECT * FROM code_edges WHERE project = ?"
        params = [project]

        if from_id:
            query += " AND from_id = ?"
            params.append(from_id)

        if to_id:
            query += " AND to_id = ?"
            params.append(to_id)

        if kind:
            query += " AND kind = ?"
            params.append(kind)

        query += " LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def get_code_dependencies(
    project: str,
    node_id: str,
    depth: int = 1,
    direction: str = 'both'
) -> List[Dict]:
    """
    查詢節點的依賴關係

    Args:
        project: 專案名稱
        node_id: 節點 ID
        depth: 搜尋深度
        direction: 'incoming', 'outgoing', 'both'

    Returns:
        依賴節點列表，包含關係類型和深度
    """
    conn = get_db()
    results = []
    visited = set()

    def _traverse(current_id: str, current_depth: int, relation: str):
        if current_depth > depth or current_id in visited:
            return
        visited.add(current_id)

        if direction in ('outgoing', 'both'):
            cursor = conn.execute(
                """
                SELECT e.to_id, e.kind, n.kind as node_kind, n.name, n.file_path
                FROM code_edges e
                LEFT JOIN code_nodes n ON e.to_id = n.id AND e.project = n.project
                WHERE e.project = ? AND e.from_id = ?
                """,
                (project, current_id)
            )
            for row in cursor.fetchall():
                if row['to_id'] not in visited:
                    results.append({
                        'id': row['to_id'],
                        'kind': row['node_kind'],
                        'name': row['name'],
                        'file_path': row['file_path'],
                        'relation': row['kind'],
                        'direction': 'outgoing',
                        'depth': current_depth
                    })
                    if current_depth < depth:
                        _traverse(row['to_id'], current_depth + 1, row['kind'])

        if direction in ('incoming', 'both'):
            cursor = conn.execute(
                """
                SELECT e.from_id, e.kind, n.kind as node_kind, n.name, n.file_path
                FROM code_edges e
                LEFT JOIN code_nodes n ON e.from_id = n.id AND e.project = n.project
                WHERE e.project = ? AND e.to_id = ?
                """,
                (project, current_id)
            )
            for row in cursor.fetchall():
                if row['from_id'] not in visited:
                    results.append({
                        'id': row['from_id'],
                        'kind': row['node_kind'],
                        'name': row['name'],
                        'file_path': row['file_path'],
                        'relation': row['kind'],
                        'direction': 'incoming',
                        'depth': current_depth
                    })
                    if current_depth < depth:
                        _traverse(row['from_id'], current_depth + 1, row['kind'])

    try:
        _traverse(node_id, 1, '')
        return results
    finally:
        conn.close()

def get_file_structure(project: str, file_path: str) -> Dict:
    """
    取得檔案的結構摘要

    Returns:
        {
            'file': {...},
            'classes': [...],
            'functions': [...],
            'interfaces': [...],
            'imports': [...]
        }
    """
    conn = get_db()
    try:
        # 取得檔案節點
        cursor = conn.execute(
            "SELECT * FROM code_nodes WHERE project = ? AND file_path LIKE ? AND kind = 'file'",
            (project, f"%{file_path}%")
        )
        file_node = cursor.fetchone()

        if not file_node:
            return {'error': f'File not found: {file_path}'}

        file_node = dict(file_node)
        file_id = file_node['id']

        # 取得此檔案定義的所有節點
        cursor = conn.execute(
            """
            SELECT n.* FROM code_nodes n
            JOIN code_edges e ON n.id = e.to_id AND n.project = e.project
            WHERE e.project = ? AND e.from_id = ? AND e.kind = 'defines'
            ORDER BY n.kind, n.line_start
            """,
            (project, file_id)
        )
        defined_nodes = [dict(row) for row in cursor.fetchall()]

        # 取得 imports
        cursor = conn.execute(
            """
            SELECT e.to_id, e.line_number FROM code_edges e
            WHERE e.project = ? AND e.from_id = ? AND e.kind = 'imports'
            ORDER BY e.line_number
            """,
            (project, file_id)
        )
        imports = [{'target': row['to_id'], 'line': row['line_number']} for row in cursor.fetchall()]

        # 分類
        return {
            'file': file_node,
            'classes': [n for n in defined_nodes if n['kind'] == 'class'],
            'functions': [n for n in defined_nodes if n['kind'] == 'function'],
            'interfaces': [n for n in defined_nodes if n['kind'] == 'interface'],
            'types': [n for n in defined_nodes if n['kind'] == 'type'],
            'constants': [n for n in defined_nodes if n['kind'] == 'constant'],
            'imports': imports
        }
    finally:
        conn.close()

# =============================================================================
# Management API
# =============================================================================

def clear_code_graph(project: str) -> int:
    """清除專案的 Code Graph"""
    conn = get_db()
    try:
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM code_nodes WHERE project = ?", (project,))
        count = cursor.fetchone()['cnt']

        conn.execute("DELETE FROM code_nodes WHERE project = ?", (project,))
        conn.execute("DELETE FROM code_edges WHERE project = ?", (project,))
        conn.execute("DELETE FROM file_hashes WHERE project = ?", (project,))
        conn.commit()

        return count
    finally:
        conn.close()

def get_code_graph_stats(project: str) -> Dict:
    """取得 Code Graph 統計"""
    conn = get_db()
    try:
        # Node 統計
        cursor = conn.execute(
            "SELECT COUNT(*) as cnt FROM code_nodes WHERE project = ?",
            (project,)
        )
        node_count = cursor.fetchone()['cnt']

        # Edge 統計
        cursor = conn.execute(
            "SELECT COUNT(*) as cnt FROM code_edges WHERE project = ?",
            (project,)
        )
        edge_count = cursor.fetchone()['cnt']

        # File 統計
        cursor = conn.execute(
            "SELECT COUNT(*) as cnt FROM code_nodes WHERE project = ? AND kind = 'file'",
            (project,)
        )
        file_count = cursor.fetchone()['cnt']

        # Kind 分佈
        cursor = conn.execute(
            "SELECT kind, COUNT(*) as cnt FROM code_nodes WHERE project = ? GROUP BY kind",
            (project,)
        )
        kinds = {row['kind']: row['cnt'] for row in cursor.fetchall()}

        # 最後同步時間
        cursor = conn.execute(
            "SELECT MAX(last_updated) as last_sync FROM file_hashes WHERE project = ?",
            (project,)
        )
        row = cursor.fetchone()
        last_sync = row['last_sync'] if row else None

        return {
            'node_count': node_count,
            'edge_count': edge_count,
            'file_count': file_count,
            'kinds': kinds,
            'last_sync': last_sync
        }
    finally:
        conn.close()

# =============================================================================
# 便利函數
# =============================================================================

def summarize_file(project: str, file_path: str) -> str:
    """產出檔案結構的 Markdown 摘要"""
    structure = get_file_structure(project, file_path)

    if 'error' in structure:
        return f"Error: {structure['error']}"

    lines = [f"## {structure['file']['name']}", ""]

    if structure['imports']:
        lines.append("### Imports")
        for imp in structure['imports']:
            lines.append(f"- `{imp['target']}`")
        lines.append("")

    if structure['classes']:
        lines.append("### Classes")
        for cls in structure['classes']:
            lines.append(f"- `{cls['name']}` (L{cls['line_start']}-{cls['line_end']})")
        lines.append("")

    if structure['functions']:
        lines.append("### Functions")
        for func in structure['functions']:
            vis = f"[{func['visibility']}] " if func.get('visibility') else ""
            lines.append(f"- {vis}`{func['name']}` (L{func['line_start']}-{func['line_end']})")
        lines.append("")

    if structure['interfaces']:
        lines.append("### Interfaces")
        for iface in structure['interfaces']:
            lines.append(f"- `{iface['name']}` (L{iface['line_start']}-{iface['line_end']})")
        lines.append("")

    return "\n".join(lines)

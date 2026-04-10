"""
Type Registry Server

可擴展的類型註冊系統，遵循 Open-Closed Principle。
新增 Node/Edge 類型只需 INSERT，不需改任何程式碼。

設計原則：
1. 類型不寫死在程式碼中
2. 提供驗證機制確保類型有效
3. 支援預設類型和自訂類型
"""

import sqlite3
import json
import os
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# =============================================================================
# SCHEMA（供 Agent 參考）
# =============================================================================

SCHEMA = """
=== Registry API ===

get_valid_node_kinds() -> List[str]
    取得所有有效的 Node 類型
    Returns: ['file', 'function', 'class', 'api', ...]

get_valid_edge_kinds() -> List[str]
    取得所有有效的 Edge 類型
    Returns: ['imports', 'calls', 'implements', ...]

register_node_kind(kind, display_name, description=None, icon=None, color=None, extractor=None) -> bool
    註冊新的 Node 類型
    - kind: 類型 ID（唯一）
    - display_name: 顯示名稱
    - description: 說明（可選）
    - icon: UI 圖示（可選）
    - color: UI 顏色（可選）
    - extractor: 負責提取的模組（可選）
    Returns: True 成功, False 已存在

register_edge_kind(kind, display_name, description=None, source_kinds=None, target_kinds=None, is_directional=True) -> bool
    註冊新的 Edge 類型
    - kind: 類型 ID（唯一）
    - display_name: 顯示名稱
    - description: 說明（可選）
    - source_kinds: 允許的來源 Node 類型（可選）
    - target_kinds: 允許的目標 Node 類型（可選）
    - is_directional: 是否有向（預設 True）
    Returns: True 成功, False 已存在

get_node_kind_info(kind) -> Dict
    取得 Node 類型詳細資訊
    Returns: {'kind': str, 'display_name': str, 'description': str, ...}

get_edge_kind_info(kind) -> Dict
    取得 Edge 類型詳細資訊
    Returns: {'kind': str, 'display_name': str, 'source_kinds': List, ...}

validate_node_kind(kind) -> bool
    驗證 Node 類型是否有效

validate_edge_kind(kind, from_kind=None, to_kind=None) -> bool
    驗證 Edge 類型是否有效，並可選驗證來源/目標類型

init_default_types() -> Tuple[int, int]
    初始化預設類型（冪等操作）
    Returns: (node_count, edge_count) 新增的數量
"""

# =============================================================================
# 預設類型定義
# =============================================================================

# 預設 Node 類型
# (kind, display_name, description, icon, color, extractor)
DEFAULT_NODE_KINDS: List[Tuple[str, str, str, Optional[str], Optional[str], Optional[str]]] = [
    # SSOT Layer（來自 L1 Index）
    ('flow', '流程', '業務流程', '🔄', '#4CAF50', None),
    ('domain', '領域', '業務領域', '📦', '#2196F3', None),
    ('page', '頁面', '前端頁面', '📄', '#9C27B0', None),

    # Code Graph Layer（從 AST 提取）
    ('file', '檔案', '源碼文件', '📁', '#607D8B', 'ast'),
    ('module', '模組', '套件/模組', '📚', '#795548', 'ast'),
    ('package', '套件', 'Java 套件', '📦', '#795548', 'ast'),
    ('class', '類別', '類別定義', '🏛️', '#FF9800', 'ast'),
    ('function', '函式', '函式/方法', '⚡', '#FFC107', 'ast'),
    ('interface', '介面', '介面定義', '🔌', '#00BCD4', 'ast'),
    ('type', '型別', '型別定義', '📐', '#E91E63', 'ast'),
    ('constant', '常數', '常數定義', '📌', '#9E9E9E', 'ast'),
    ('variable', '變數', '模組級變數', '📊', '#8BC34A', 'ast'),
    ('annotation', '註解', 'Java 註解定義', '🏷️', '#FF6F00', 'ast'),

    # API Layer
    ('api', 'API', 'API endpoint', '🌐', '#3F51B5', 'route'),
    ('route', '路由', '前端路由', '🛤️', '#673AB7', 'route'),

    # Data Layer
    ('model', '模型', '資料模型/schema', '💾', '#FF5722', 'model'),
    ('enum', '列舉', '列舉類型', '📋', '#CDDC39', 'ast'),

    # Rust-specific types
    ('struct', '結構', 'Rust 結構體', '🏗️', '#FF5722', 'ast'),
    ('trait', '特徵', 'Rust trait', '🔗', '#9C27B0', 'ast'),
    ('static', '靜態', 'Rust static 變數', '📍', '#607D8B', 'ast'),
    ('macro', '巨集', 'Rust macro', '🔧', '#795548', 'ast'),

    # Test Layer
    ('test', '測試', '測試文件/suite', '🧪', '#4DD0E1', 'test'),
    ('test_case', '測試案例', '單一測試案例', '✅', '#81C784', 'test'),

    # Config Layer
    ('config', '配置', '配置檔案', '⚙️', '#90A4AE', 'config'),
]

# 預設 Edge 類型
# (kind, display_name, description, source_kinds_json, target_kinds_json, is_directional)
DEFAULT_EDGE_KINDS: List[Tuple[str, str, str, Optional[str], Optional[str], int]] = [
    # 導入關係
    ('imports', '導入', '文件導入', '["file"]', '["file", "module"]', 1),

    # 調用關係
    ('calls', '調用', '函式調用', '["function", "method"]', '["function", "method"]', 1),

    # 繼承/實作
    ('extends', '繼承', '類別繼承', '["class"]', '["class"]', 1),
    ('implements', '實作', '介面實作', '["class", "file"]', '["interface", "flow"]', 1),

    # 定義關係
    ('defines', '定義', '檔案定義', '["file"]', '["class", "function", "interface", "type", "constant"]', 1),
    ('contains', '包含', '模組包含', '["module", "class"]', '["class", "function", "variable"]', 1),

    # 依賴關係
    ('uses', '使用', '通用依賴', None, None, 1),
    ('depends_on', '依賴', '模組依賴', '["module", "file"]', '["module", "file"]', 1),

    # API 關係
    ('routes_to', '路由', '路由對應', '["route", "api"]', '["function", "class"]', 1),
    ('belongs_to', '屬於', '歸屬關係', '["api", "page"]', '["domain", "module"]', 1),

    # 測試關係
    ('tests', '測試', '測試覆蓋', '["test", "test_case"]', '["function", "class", "flow"]', 1),
    ('covers', '涵蓋', '測試涵蓋', '["test"]', '["flow", "api"]', 1),

    # SSOT 關係
    ('specifies', '規範', 'SSOT 規範', '["flow", "domain"]', '["api", "page", "model"]', 1),
    ('references', '參照', '文檔參照', None, None, 1),
]

# =============================================================================
# Database Connection
# =============================================================================

from servers import managed_connection


def _get_conn():
    """Module-level connection context manager with Row factory."""
    return managed_connection(row_factory=True)

# =============================================================================
# Node Kind API
# =============================================================================

def get_valid_node_kinds() -> List[str]:
    """取得所有有效的 Node 類型"""
    with _get_conn() as conn:
        cursor = conn.execute("SELECT kind FROM node_kind_registry ORDER BY kind")
        return [row['kind'] for row in cursor.fetchall()]

def get_node_kind_info(kind: str) -> Optional[Dict]:
    """取得 Node 類型詳細資訊"""
    with _get_conn() as conn:
        cursor = conn.execute(
            "SELECT * FROM node_kind_registry WHERE kind = ?",
            (kind,)
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

def get_all_node_kinds() -> List[Dict]:
    """取得所有 Node 類型的詳細資訊"""
    with _get_conn() as conn:
        cursor = conn.execute(
            "SELECT * FROM node_kind_registry ORDER BY is_builtin DESC, kind"
        )
        return [dict(row) for row in cursor.fetchall()]

def register_node_kind(
    kind: str,
    display_name: str,
    description: str = None,
    icon: str = None,
    color: str = None,
    extractor: str = None
) -> bool:
    """
    註冊新的 Node 類型

    Returns:
        True: 成功新增
        False: 類型已存在
    """
    with _get_conn() as conn:
        try:
            conn.execute(
                """
                INSERT INTO node_kind_registry
                (kind, display_name, description, icon, color, extractor, is_builtin)
                VALUES (?, ?, ?, ?, ?, ?, 0)
                """,
                (kind, display_name, description, icon, color, extractor)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def validate_node_kind(kind: str) -> bool:
    """驗證 Node 類型是否有效"""
    return get_node_kind_info(kind) is not None

# =============================================================================
# Edge Kind API
# =============================================================================

def get_valid_edge_kinds() -> List[str]:
    """取得所有有效的 Edge 類型"""
    with _get_conn() as conn:
        cursor = conn.execute("SELECT kind FROM edge_kind_registry ORDER BY kind")
        return [row['kind'] for row in cursor.fetchall()]

def get_edge_kind_info(kind: str) -> Optional[Dict]:
    """取得 Edge 類型詳細資訊"""
    with _get_conn() as conn:
        cursor = conn.execute(
            "SELECT * FROM edge_kind_registry WHERE kind = ?",
            (kind,)
        )
        row = cursor.fetchone()
        if row:
            result = dict(row)
            # 解析 JSON 字段
            if result.get('source_kinds'):
                result['source_kinds'] = json.loads(result['source_kinds'])
            if result.get('target_kinds'):
                result['target_kinds'] = json.loads(result['target_kinds'])
            return result
        return None

def get_all_edge_kinds() -> List[Dict]:
    """取得所有 Edge 類型的詳細資訊"""
    with _get_conn() as conn:
        cursor = conn.execute(
            "SELECT * FROM edge_kind_registry ORDER BY is_builtin DESC, kind"
        )
        results = []
        for row in cursor.fetchall():
            result = dict(row)
            if result.get('source_kinds'):
                result['source_kinds'] = json.loads(result['source_kinds'])
            if result.get('target_kinds'):
                result['target_kinds'] = json.loads(result['target_kinds'])
            results.append(result)
        return results

def register_edge_kind(
    kind: str,
    display_name: str,
    description: str = None,
    source_kinds: List[str] = None,
    target_kinds: List[str] = None,
    is_directional: bool = True
) -> bool:
    """
    註冊新的 Edge 類型

    Args:
        kind: 類型 ID（唯一）
        display_name: 顯示名稱
        description: 說明
        source_kinds: 允許的來源 Node 類型
        target_kinds: 允許的目標 Node 類型
        is_directional: 是否有向（預設 True）

    Returns:
        True: 成功新增
        False: 類型已存在
    """
    with _get_conn() as conn:
        try:
            source_json = json.dumps(source_kinds) if source_kinds else None
            target_json = json.dumps(target_kinds) if target_kinds else None

            conn.execute(
                """
                INSERT INTO edge_kind_registry
                (kind, display_name, description, source_kinds, target_kinds, is_directional, is_builtin)
                VALUES (?, ?, ?, ?, ?, ?, 0)
                """,
                (kind, display_name, description, source_json, target_json, 1 if is_directional else 0)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def validate_edge_kind(
    kind: str,
    from_kind: str = None,
    to_kind: str = None
) -> bool:
    """
    驗證 Edge 類型是否有效

    Args:
        kind: Edge 類型
        from_kind: 來源 Node 類型（可選，用於驗證來源限制）
        to_kind: 目標 Node 類型（可選，用於驗證目標限制）

    Returns:
        True: 有效
        False: 無效
    """
    info = get_edge_kind_info(kind)
    if not info:
        return False

    # 如果指定了來源類型，驗證是否符合限制
    if from_kind and info.get('source_kinds'):
        if from_kind not in info['source_kinds']:
            return False

    # 如果指定了目標類型，驗證是否符合限制
    if to_kind and info.get('target_kinds'):
        if to_kind not in info['target_kinds']:
            return False

    return True

# =============================================================================
# 初始化
# =============================================================================

def init_default_types() -> Tuple[int, int]:
    """
    初始化預設類型（冪等操作）

    Returns:
        (node_count, edge_count): 新增的類型數量
    """
    with _get_conn() as conn:
        node_count = 0
        edge_count = 0

        # 初始化 Node 類型
        for kind, display_name, description, icon, color, extractor in DEFAULT_NODE_KINDS:
            try:
                conn.execute(
                    """
                    INSERT INTO node_kind_registry
                    (kind, display_name, description, icon, color, extractor, is_builtin)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                    """,
                    (kind, display_name, description, icon, color, extractor)
                )
                node_count += 1
            except sqlite3.IntegrityError:
                pass

        # 初始化 Edge 類型
        for kind, display_name, description, source_kinds, target_kinds, is_dir in DEFAULT_EDGE_KINDS:
            try:
                conn.execute(
                    """
                    INSERT INTO edge_kind_registry
                    (kind, display_name, description, source_kinds, target_kinds, is_directional, is_builtin)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                    """,
                    (kind, display_name, description, source_kinds, target_kinds, is_dir)
                )
                edge_count += 1
            except sqlite3.IntegrityError:
                pass

        conn.commit()
        return (node_count, edge_count)

def ensure_schema_exists():
    """確保 Schema 存在（讀取 schema.sql 並執行）"""
    from servers import HAN_BASE_DIR
    schema_path = os.path.join(HAN_BASE_DIR, 'brain', 'schema.sql')

    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with _get_conn() as conn:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)
        conn.commit()

def init_registry():
    """
    完整初始化 Registry（確保 Schema + 預設類型）

    這是 Agent 應該調用的入口點。
    """
    ensure_schema_exists()
    return init_default_types()

# =============================================================================
# 診斷工具
# =============================================================================

def diagnose() -> Dict:
    """
    診斷 Registry 狀態

    Returns:
        {
            'status': 'ok' | 'warning' | 'error',
            'node_kinds_count': int,
            'edge_kinds_count': int,
            'builtin_node_kinds': int,
            'builtin_edge_kinds': int,
            'custom_node_kinds': int,
            'custom_edge_kinds': int,
            'messages': List[str]
        }
    """
    result = {
        'status': 'ok',
        'messages': []
    }

    try:
        with _get_conn() as conn:
            # 檢查表是否存在
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('node_kind_registry', 'edge_kind_registry')"
            )
            tables = [row['name'] for row in cursor.fetchall()]

            if 'node_kind_registry' not in tables:
                result['status'] = 'error'
                result['messages'].append('node_kind_registry table does not exist')

            if 'edge_kind_registry' not in tables:
                result['status'] = 'error'
                result['messages'].append('edge_kind_registry table does not exist')

            if result['status'] == 'error':
                return result

            # 統計數量
            cursor = conn.execute("SELECT COUNT(*) as cnt, SUM(is_builtin) as builtin FROM node_kind_registry")
            row = cursor.fetchone()
            result['node_kinds_count'] = row['cnt']
            result['builtin_node_kinds'] = row['builtin'] or 0
            result['custom_node_kinds'] = row['cnt'] - (row['builtin'] or 0)

            cursor = conn.execute("SELECT COUNT(*) as cnt, SUM(is_builtin) as builtin FROM edge_kind_registry")
            row = cursor.fetchone()
            result['edge_kinds_count'] = row['cnt']
            result['builtin_edge_kinds'] = row['builtin'] or 0
            result['custom_edge_kinds'] = row['cnt'] - (row['builtin'] or 0)

            # 檢查是否有預設類型
            if result['node_kinds_count'] == 0:
                result['status'] = 'warning'
                result['messages'].append('No node kinds registered. Run init_default_types().')

            if result['edge_kinds_count'] == 0:
                result['status'] = 'warning'
                result['messages'].append('No edge kinds registered. Run init_default_types().')

            if result['status'] == 'ok':
                result['messages'].append('Registry is properly configured.')

            return result

    except Exception as e:
        return {
            'status': 'error',
            'messages': [f'Database error: {str(e)}']
        }


# =============================================================================
# 便利函數（給 Agent 使用）
# =============================================================================

def list_node_kinds_for_display() -> str:
    """產出適合顯示的 Node 類型列表"""
    kinds = get_all_node_kinds()
    lines = ["## Node 類型列表", ""]
    lines.append("| Kind | 名稱 | 說明 | 來源 |")
    lines.append("|------|------|------|------|")
    for k in kinds:
        source = "內建" if k.get('is_builtin') else "自訂"
        icon = k.get('icon') or ''
        lines.append(f"| `{k['kind']}` | {icon} {k['display_name']} | {k.get('description') or '-'} | {source} |")
    return "\n".join(lines)

def list_edge_kinds_for_display() -> str:
    """產出適合顯示的 Edge 類型列表"""
    kinds = get_all_edge_kinds()
    lines = ["## Edge 類型列表", ""]
    lines.append("| Kind | 名稱 | 說明 | 來源→目標 |")
    lines.append("|------|------|------|-----------|")
    for k in kinds:
        source = k.get('source_kinds') or ['*']
        target = k.get('target_kinds') or ['*']
        constraint = f"{source} → {target}"
        lines.append(f"| `{k['kind']}` | {k['display_name']} | {k.get('description') or '-'} | {constraint} |")
    return "\n".join(lines)

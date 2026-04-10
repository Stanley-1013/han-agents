"""
HAN System - 專案初始化（Lazy）
冪等的專案初始化邏輯，首次使用時自動觸發。
專案理解存 DB + Code Graph，不在專案目錄建檔案。
"""

import os
import json

from servers import managed_connection


# 常見框架偵測規則：import name → (framework, test_tool)
_FRAMEWORK_HINTS = {
    # Python
    'fastapi': ('FastAPI', 'pytest'),
    'flask': ('Flask', 'pytest'),
    'django': ('Django', 'pytest'),
    'pytest': (None, 'pytest'),
    'unittest': (None, 'pytest'),
    # TypeScript / JavaScript
    'react': ('React', 'jest'),
    'next': ('Next.js', 'jest'),
    'vue': ('Vue', 'vitest'),
    'nuxt': ('Nuxt', 'vitest'),
    'express': ('Express', 'jest'),
    'jest': (None, 'jest'),
    'vitest': (None, 'vitest'),
    'mocha': (None, 'mocha'),
    # Java
    'org.springframework': ('Spring Boot', 'junit'),
    'org.junit': (None, 'junit'),
    'org.mockito': (None, 'junit'),
    # Rust
    'tokio': ('Tokio', 'cargo test'),
    'actix': ('Actix', 'cargo test'),
    # Go
    'net/http': ('net/http', 'go test'),
    'gin': ('Gin', 'go test'),
}

# 語言 → 預設測試工具
_DEFAULT_TEST_TOOLS = {
    'python': 'pytest',
    'typescript': 'jest',
    'javascript': 'jest',
    'java': 'junit',
    'rust': 'cargo test',
    'go': 'go test',
}


def _detect_tech_stack(project_name):
    """從 Code Graph 偵測專案技術棧

    Returns:
        {
            'languages': {'python': 42, 'typescript': 18, ...},
            'primary_language': 'python',
            'frameworks': ['FastAPI', 'React'],
            'test_tool': 'pytest',
        }
    """
    result = {
        'languages': {},
        'primary_language': None,
        'frameworks': [],
        'test_tool': None,
    }

    with managed_connection(row_factory=True) as conn:
        # 1. 語言分布
        cursor = conn.execute(
            "SELECT language, COUNT(*) as cnt FROM code_nodes "
            "WHERE project = ? AND language IS NOT NULL "
            "GROUP BY language ORDER BY cnt DESC",
            (project_name,)
        )
        for row in cursor.fetchall():
            result['languages'][row['language']] = row['cnt']

        if result['languages']:
            result['primary_language'] = next(iter(result['languages']))

        # 2. 從 import edges 偵測框架
        cursor = conn.execute(
            "SELECT DISTINCT cn.name FROM code_edges ce "
            "JOIN code_nodes cn ON ce.to_id = cn.id AND ce.project = cn.project "
            "WHERE ce.project = ? AND ce.kind = 'imports'",
            (project_name,)
        )
        import_names = {row['name'].lower() for row in cursor.fetchall()}

        frameworks = set()
        test_tools = set()
        for hint_key, (framework, test_tool) in _FRAMEWORK_HINTS.items():
            if any(hint_key in name for name in import_names):
                if framework:
                    frameworks.add(framework)
                if test_tool:
                    test_tools.add(test_tool)

        result['frameworks'] = sorted(frameworks)

        # 3. 決定測試工具：偵測到的 > 語言預設
        if test_tools:
            result['test_tool'] = sorted(test_tools)[0]
        elif result['primary_language']:
            result['test_tool'] = _DEFAULT_TEST_TOOLS.get(
                result['primary_language']
            )

    return result


def ensure_project(project_name, project_path=None):
    """冪等的專案初始化：sync Code Graph + 偵測技術棧 + 存 DB

    首次對專案操作時自動呼叫，已初始化的專案直接返回快取。

    Args:
        project_name: 專案名稱
        project_path: 專案根目錄（預設 cwd）

    Returns:
        {
            'sync_result': {...},
            'tech_stack': {...},
            'already_initialized': bool,
        }
    """
    if project_path is None:
        project_path = os.getcwd()

    result = {
        'sync_result': None,
        'tech_stack': None,
        'already_initialized': False,
    }

    # 檢查是否已初始化
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM long_term_memory "
            "WHERE project = ? AND title = 'Tech Stack' "
            "ORDER BY created_at DESC LIMIT 1",
            (project_name,)
        )
        row = cursor.fetchone()
        if row and row[0]:
            try:
                result['tech_stack'] = json.loads(row[0])
                result['already_initialized'] = True
            except (json.JSONDecodeError, TypeError):
                pass

    # 1. Sync Code Graph（incremental，已有的很快）
    from servers.facade import sync
    result['sync_result'] = sync(project_path, project_name, incremental=True)

    # 2. 偵測技術棧
    tech_stack = _detect_tech_stack(project_name)
    result['tech_stack'] = tech_stack

    # 3. 存 DB（真正的 upsert：更新已有 Tech Stack 或建新的）
    tech_stack_json = json.dumps(tech_stack, ensure_ascii=False)
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, content FROM long_term_memory "
            "WHERE project = ? AND category = 'knowledge' AND title = 'Tech Stack' "
            "AND status = 'active' "
            "ORDER BY created_at DESC",
            (project_name,)
        )
        rows = cursor.fetchall()
        if rows:
            current_id = rows[0][0]
            # 只在內容有變化時才更新
            if rows[0][1] != tech_stack_json:
                cursor.execute(
                    "UPDATE long_term_memory "
                    "SET content = ?, importance = 8, updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = ?",
                    (tech_stack_json, current_id)
                )
            # 清理重複記錄
            if len(rows) > 1:
                cursor.executemany(
                    "UPDATE long_term_memory "
                    "SET status = 'superseded', superseded_by = ? "
                    "WHERE id = ?",
                    [(current_id, row[0]) for row in rows[1:]]
                )
        else:
            cursor.execute(
                "INSERT INTO long_term_memory "
                "(category, project, title, content, importance) "
                "VALUES ('knowledge', ?, 'Tech Stack', ?, 8)",
                (project_name, tech_stack_json)
            )
        conn.commit()

    # 4. 寫初始化 episode（只寫一次）
    if not result['already_initialized']:
        with managed_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO episodes (project, event_type, summary) "
                "VALUES (?, 'milestone', ?)",
                (project_name, f'專案 {project_name} 初始化')
            )
            conn.commit()

    return result

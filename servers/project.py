"""
HAN System - 專案初始化（Lazy）
冪等的專案初始化邏輯，首次使用時自動觸發
"""

import os
import sqlite3

from servers import HAN_BASE_DIR, BRAIN_DB, ensure_db
from servers.platform import detect_platform, PLATFORMS


# 各平台的 workspace-level skill 目錄
PLATFORM_SKILL_DIRS = {
    'claude': '.claude/skills',
    'cursor': '.cursor/skills',
    'windsurf': '.windsurf/skills',
    'cline': '.cline/skills',
    'codex': '.codex/skills',
    'gemini': '.gemini/skills',
    'antigravity': '.agent/skills',
}

# 專案 SKILL.md 模板
SKILL_TEMPLATE = '''---
name: {project_name}
description: |
  [由 LLM 填寫專案描述]
---

# {project_name}

## 概述
[專案目標和核心功能]

## 技術棧
- Backend:
- Frontend:
- Database:

## 核心約束
1. [不可違反的規則]
2. ...

## 參考文檔
<!-- 連結專案內的文檔，使用相對路徑 (../../../ 回到專案根目錄) -->
<!-- 例如: [API 文檔](../../../docs/api.md) -->
<!-- 例如: [資料模型](../../../src/models/README.md) -->
'''


def ensure_project(project_name, project_path=None, platform_key=None):
    """冪等的專案初始化：建 SKILL.md 模板 + DB 記錄

    首次對專案操作時自動呼叫，已初始化的專案會直接跳過。

    Args:
        project_name: 專案名稱
        project_path: 專案根目錄（預設 cwd）
        platform_key: 平台 key（預設自動偵測）

    Returns:
        dict: {skill_dir, created_skill, created_db_record}
    """
    if project_path is None:
        project_path = os.getcwd()

    if platform_key is None:
        platform_key, _ = detect_platform()

    # 確保 DB 存在
    ensure_db()

    result = {
        'skill_dir': None,
        'created_skill': False,
        'created_db_record': False,
    }

    # 1. 建立專案 SKILL.md（if not exists）
    skill_rel_dir = PLATFORM_SKILL_DIRS.get(platform_key, '.claude/skills')
    skill_dir = os.path.join(project_path, skill_rel_dir, project_name)
    result['skill_dir'] = skill_dir

    skill_md = os.path.join(skill_dir, 'SKILL.md')
    if not os.path.exists(skill_md):
        os.makedirs(skill_dir, exist_ok=True)
        with open(skill_md, 'w', encoding='utf-8') as f:
            f.write(SKILL_TEMPLATE.format(project_name=project_name))
        result['created_skill'] = True

    # 2. 寫 DB 記錄（if not exists）
    conn = sqlite3.connect(BRAIN_DB)
    try:
        cursor = conn.cursor()

        # 檢查是否已有此專案的初始化記錄
        cursor.execute(
            "SELECT COUNT(*) FROM long_term_memory WHERE project = ? AND title = 'Project Initialized'",
            (project_name,)
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO long_term_memory
                (category, project, title, content, importance)
                VALUES ('knowledge', ?, 'Project Initialized', ?, 8)
            ''', (project_name, f'專案 {project_name} 已初始化'))

            cursor.execute('''
                INSERT INTO episodes
                (project, event_type, summary)
                VALUES (?, 'milestone', ?)
            ''', (project_name, f'專案 {project_name} 初始化'))

            conn.commit()
            result['created_db_record'] = True
    finally:
        conn.close()

    return result

#!/usr/bin/env python3
"""
HAN System - 專案初始化腳本
建立專案 Skill 結構和資料庫記錄

支援平台：
- Claude Code: .claude/skills/<name>/
- Cursor: .cursor/skills/<name>/
- Windsurf: .windsurf/skills/<name>/
- Cline: .cline/skills/<name>/
- Codex CLI: .codex/skills/<name>/
- Gemini CLI: .gemini/skills/<name>/
- Antigravity: .agent/skills/<name>/
"""

import os
import sys
import sqlite3

# Windows console encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


# 平台設定（workspace-level skills 目錄）
PLATFORM_SKILL_DIRS = {
    'claude': '.claude/skills',
    'cursor': '.cursor/skills',
    'windsurf': '.windsurf/skills',
    'cline': '.cline/skills',
    'codex': '.codex/skills',
    'gemini': '.gemini/skills',
    'antigravity': '.agent/skills',
}


def detect_platform_from_han_path():
    """根據 han-agents 安裝位置偵測平台"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    normalized_path = os.path.normpath(base_dir).replace('\\', '/')

    # 檢查各平台的 global skills 目錄
    platform_global_dirs = {
        'claude': '~/.claude/skills',
        'cursor': '~/.cursor/skills',
        'windsurf': '~/.codeium/windsurf/skills',
        'cline': '~/.cline/skills',
        'codex': '~/.codex/skills',
        'gemini': '~/.gemini/skills',
        'antigravity': '~/.gemini/antigravity/skills',
    }

    for platform_key, skills_dir in platform_global_dirs.items():
        expanded = os.path.normpath(os.path.expanduser(skills_dir)).replace('\\', '/')
        if normalized_path.startswith(expanded):
            return platform_key

    # 檢查 workspace-level patterns
    for platform_key, rel_dir in PLATFORM_SKILL_DIRS.items():
        if rel_dir.replace('/', os.sep) in normalized_path or rel_dir in normalized_path:
            return platform_key

    # 預設使用 claude
    return 'claude'


# 專案 SKILL.md 模板
# 路徑說明：SKILL.md 位於 <project>/.claude/skills/<name>/
# 連結專案文檔時使用相對路徑，例如 ../../../docs/auth.md
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


def init_project_skill(project_dir, project_name, platform='claude'):
    """建立專案 Skill 目錄和空白模板

    Args:
        project_dir: 專案根目錄
        project_name: 專案名稱
        platform: 平台名稱 (claude, cursor, windsurf, cline, codex, gemini, antigravity)
    """
    skill_rel_dir = PLATFORM_SKILL_DIRS.get(platform, '.claude/skills')
    skill_dir = os.path.join(project_dir, skill_rel_dir, project_name)
    os.makedirs(skill_dir, exist_ok=True)

    skill_md = os.path.join(skill_dir, "SKILL.md")
    if not os.path.exists(skill_md):
        with open(skill_md, 'w', encoding='utf-8') as f:
            f.write(SKILL_TEMPLATE.format(project_name=project_name))
        print(f"✅ 專案 Skill 已建立: {skill_md}")
    else:
        print(f"ℹ️  專案 Skill 已存在: {skill_md}")

    return skill_dir


def init_project(project_name, project_dir=None, platform=None):
    """初始化專案

    Args:
        project_name: 專案名稱
        project_dir: 專案根目錄（預設為當前目錄）
        platform: 平台名稱（預設自動偵測）
    """
    # 使用相對路徑，相容所有平台
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, 'brain', 'brain.db')

    if project_dir is None:
        project_dir = os.getcwd()

    if platform is None:
        platform = detect_platform_from_han_path()

    platform_names = {
        'claude': 'Claude Code',
        'cursor': 'Cursor',
        'windsurf': 'Windsurf',
        'cline': 'Cline',
        'codex': 'Codex CLI',
        'gemini': 'Gemini CLI',
        'antigravity': 'Antigravity',
    }
    platform_display = platform_names.get(platform, platform)

    print(f"🚀 初始化專案: {project_name}")
    print(f"📍 平台: {platform_display}")
    print("=" * 50)

    # 1. 確認資料庫存在
    if not os.path.exists(db_path):
        print(f"❌ 資料庫不存在: {db_path}")
        print(f"請先執行: python {os.path.join(base_dir, 'scripts', 'install.py')}")
        sys.exit(1)

    # 2. 建立專案 Skill
    skill_dir = init_project_skill(project_dir, project_name, platform)

    # 3. 建立專案記錄
    db = sqlite3.connect(db_path)
    cursor = db.cursor()

    cursor.execute('''
        INSERT INTO long_term_memory
        (category, project, title, content, importance)
        VALUES ('knowledge', ?, 'Project Initialized', ?, 8)
    ''', (project_name, f'專案 {project_name} 已初始化神經擬態系統'))

    cursor.execute('''
        INSERT INTO episodes
        (project, event_type, summary)
        VALUES (?, 'milestone', ?)
    ''', (project_name, f'專案 {project_name} 初始化'))

    db.commit()
    db.close()

    # 4. 建立本地設定檔（放在專案 skill 目錄）
    config_dir = skill_dir
    os.makedirs(config_dir, exist_ok=True)

    config_content = f'''# HAN System Configuration
# 專案: {project_name}

PROJECT_NAME = "{project_name}"
BRAIN_DB = "{db_path}"
HAN_PATH = "{base_dir}"
SKILL_DIR = "{skill_dir}"

# 使用方式:
# import sys
# sys.path.insert(0, HAN_PATH)
# from servers.memory import search_memory, store_memory
# from servers.tasks import create_task, get_task_progress
'''

    config_path = os.path.join(config_dir, 'config.py')
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(config_content)

    # 5. 同步 Code Graph
    print(f"✅ 專案記錄已建立")
    print(f"✅ 本地設定: {config_path}")
    print("\n📊 同步 Code Graph...")
    try:
        sys.path.insert(0, base_dir)
        from servers.facade import sync
        result = sync(project_dir, project_name)
        if result.get('status') == 'success':
            stats = result.get('stats', {})
            print(f"✅ Code Graph 同步完成")
            print(f"   節點: {stats.get('nodes', 0)}, 邊: {stats.get('edges', 0)}")
        else:
            print(f"⚠️  Code Graph 同步有警告: {result.get('message', '')}")
    except Exception as e:
        print(f"⚠️  Code Graph 同步失敗: {e}")
        print("   可稍後執行 `python scripts/sync.py` 重試")

    # 6. 完成
    print("\n" + "=" * 50)
    print("🎉 專案初始化完成！")
    print(f"\n專案: {project_name}")
    print(f"Skill: {os.path.join(skill_dir, 'SKILL.md')}")
    print(f"資料庫: {db_path}")
    print("\n下一步:")
    print("  1. 編輯 SKILL.md 填寫專案資訊")
    print("  2. 對 Claude Code 說：")
    print(f'     「這是 {project_name} 專案，使用 pfc agent 規劃任務」')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='初始化 HAN-Agents 專案')
    parser.add_argument('project_name', help='專案名稱')
    parser.add_argument('project_dir', nargs='?', default=None, help='專案目錄（預設為當前目錄）')
    parser.add_argument('--platform', '-p', choices=list(PLATFORM_SKILL_DIRS.keys()),
                        help='目標平台（預設自動偵測）')

    args = parser.parse_args()
    init_project(args.project_name, args.project_dir, args.platform)

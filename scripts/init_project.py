#!/usr/bin/env python3
"""
Cortex System - 專案初始化腳本
建立專案 Skill 結構和資料庫記錄
"""

import os
import sys
import sqlite3

# Windows console encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

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

## 業務流程
<!-- 建立 flows/ 目錄後，在此列出連結 -->

## 領域模型
<!-- 建立 domains/ 目錄後，在此列出連結 -->

## API 規格
<!-- 建立 apis/ 目錄後，在此列出連結 -->
'''


def init_project_skill(project_dir, project_name):
    """建立專案 Skill 目錄和空白模板"""
    skill_dir = os.path.join(project_dir, ".claude", "skills", project_name)
    os.makedirs(skill_dir, exist_ok=True)

    skill_md = os.path.join(skill_dir, "SKILL.md")
    if not os.path.exists(skill_md):
        with open(skill_md, 'w') as f:
            f.write(SKILL_TEMPLATE.format(project_name=project_name))
        print(f"✅ 專案 Skill 已建立: {skill_md}")
    else:
        print(f"ℹ️  專案 Skill 已存在: {skill_md}")

    return skill_dir


def init_project(project_name, project_dir=None):
    """初始化專案"""
    base_dir = os.path.expanduser('~/.claude/skills/cortex-agents')
    db_path = os.path.join(base_dir, 'brain', 'brain.db')

    if project_dir is None:
        project_dir = os.getcwd()

    print(f"🚀 初始化專案: {project_name}")
    print("=" * 50)

    # 1. 確認資料庫存在
    if not os.path.exists(db_path):
        print(f"❌ 資料庫不存在: {db_path}")
        print(f"請先執行: python {os.path.join(base_dir, 'scripts', 'install.py')}")
        sys.exit(1)

    # 2. 建立專案 Skill
    skill_dir = init_project_skill(project_dir, project_name)

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

    # 4. 建立本地設定檔
    config_dir = os.path.join(project_dir, '.claude')
    os.makedirs(config_dir, exist_ok=True)

    config_content = f'''# Cortex System Configuration
# 專案: {project_name}

PROJECT_NAME = "{project_name}"
BRAIN_DB = "{db_path}"
NEUROMORPHIC_PATH = "{base_dir}"
SKILL_DIR = "{skill_dir}"

# 使用方式:
# import sys
# sys.path.insert(0, NEUROMORPHIC_PATH)
# from servers.memory import search_memory, store_memory
# from servers.tasks import create_task, get_task_progress
'''

    config_path = os.path.join(config_dir, 'config.py')
    with open(config_path, 'w') as f:
        f.write(config_content)

    # 5. 完成
    print(f"✅ 專案記錄已建立")
    print(f"✅ 本地設定: {config_path}")
    print("\n" + "=" * 50)
    print("🎉 專案初始化完成！")
    print(f"\n專案: {project_name}")
    print(f"Skill: {skill_dir}/SKILL.md")
    print(f"資料庫: {db_path}")
    print("\n下一步:")
    print("  1. 編輯 SKILL.md 填寫專案資訊")
    print("  2. 對 Claude Code 說：")
    print(f'     「這是 {project_name} 專案，使用 pfc agent 規劃任務」')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("使用方式: python init_project.py <project_name> [project_dir]")
        print("範例: python init_project.py my-awesome-app")
        print("範例: python init_project.py my-app /path/to/project")
        sys.exit(1)

    project_name = sys.argv[1]
    project_dir = sys.argv[2] if len(sys.argv) > 2 else None
    init_project(project_name, project_dir)

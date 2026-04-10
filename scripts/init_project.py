#!/usr/bin/env python3
"""
HAN System - 專案初始化腳本
建立專案 Skill 結構和資料庫記錄

Zero-config 模式下不需要手動執行此腳本 —
ensure_project() 會在首次使用時自動觸發。

此腳本適用於手動初始化或 CI/CD 環境。

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

# Windows console encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 讓 scripts/ 能 import servers/
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BASE_DIR)

from servers.platform import detect_platform, PLATFORMS
from servers.project import ensure_project, PLATFORM_SKILL_DIRS


def init_project(project_name, project_dir=None, platform=None):
    """初始化專案（CLI 入口，帶輸出訊息）"""
    if project_dir is None:
        project_dir = os.getcwd()

    if platform is None:
        platform, _ = detect_platform()

    platform_names = {k: v['name'] for k, v in PLATFORMS.items()}
    platform_display = platform_names.get(platform, platform)

    print(f"🚀 初始化專案: {project_name}")
    print(f"📍 平台: {platform_display}")
    print("=" * 50)

    # 委派給 ensure_project（冪等）
    result = ensure_project(project_name, project_dir, platform)

    if result['created_skill']:
        print(f"✅ 專案 Skill 已建立: {os.path.join(result['skill_dir'], 'SKILL.md')}")
    else:
        print(f"ℹ️  專案 Skill 已存在: {os.path.join(result['skill_dir'], 'SKILL.md')}")

    if result['created_db_record']:
        print(f"✅ 專案記錄已建立")
    else:
        print(f"ℹ️  專案記錄已存在")

    # 同步 Code Graph
    print("\n📊 同步 Code Graph...")
    try:
        from servers.facade import sync
        sync_result = sync(project_dir, project_name)
        if sync_result.get('status') == 'success':
            stats = sync_result.get('stats', {})
            print(f"✅ Code Graph ��步完成")
            print(f"   節點: {stats.get('nodes', 0)}, 邊: {stats.get('edges', 0)}")
        else:
            print(f"⚠️  Code Graph 同步有警告: {sync_result.get('message', '')}")
    except Exception as e:
        print(f"⚠️  Code Graph 同步失敗: {e}")
        print("   可稍後執行 `python scripts/sync.py` 重試")

    # 完成
    print("\n" + "=" * 50)
    print("🎉 專案初始化完成！")
    print(f"\n專案: {project_name}")
    print(f"Skill: {os.path.join(result['skill_dir'], 'SKILL.md')}")
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

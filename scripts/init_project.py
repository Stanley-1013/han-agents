#!/usr/bin/env python3
"""
HAN System - 專案初始化腳本

自動同步 Code Graph、偵測技術棧、存入 DB。
Zero-config 模式下不需要手動執行 — ensure_project() 會在首次使用時自動觸發。
此腳本適用於手動初始化或 CI/CD 環境。
"""

import os
import sys

# Windows console encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 讓 scripts/ 能 import servers/
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BASE_DIR)

from servers.project import ensure_project


def init_project(project_name, project_dir=None):
    """初始化專案（CLI 入口，帶輸出訊息）"""
    if project_dir is None:
        project_dir = os.getcwd()

    print(f"Initializing project: {project_name}")
    print(f"Path: {project_dir}")
    print("=" * 50)

    result = ensure_project(project_name, project_dir)

    # Sync 結果
    sync_result = result.get('sync_result', {})
    if sync_result:
        stats = sync_result.get('stats', {})
        print(f"Code Graph synced: nodes={stats.get('nodes', 0)}, edges={stats.get('edges', 0)}")

    # Tech Stack
    tech = result.get('tech_stack', {})
    if tech:
        print(f"Primary language: {tech.get('primary_language', 'unknown')}")
        if tech.get('frameworks'):
            print(f"Frameworks: {', '.join(tech['frameworks'])}")
        if tech.get('test_tool'):
            print(f"Test tool: {tech['test_tool']}")

    if result.get('already_initialized'):
        print("\nProject was already initialized (updated).")
    else:
        print("\nProject initialized for the first time.")

    print("=" * 50)
    print("Done.")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Initialize HAN-Agents project')
    parser.add_argument('project_name', help='Project name')
    parser.add_argument('project_dir', nargs='?', default=None,
                        help='Project directory (default: cwd)')

    args = parser.parse_args()
    init_project(args.project_name, args.project_dir)

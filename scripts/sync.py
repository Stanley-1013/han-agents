#!/usr/bin/env python3
"""
Cortex Sync Script

同步 Code Graph 和 SSOT Graph。

使用方式：
    python sync.py [path] [--name NAME] [--full] [--ssot]
"""

import sys
import os
import argparse

# Windows console encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 確保可以 import servers（使用相對路徑，相容所有平台）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def sync_code_graph(project_path: str, project_name: str, incremental: bool = True):
    """同步 Code Graph"""
    from servers.facade import sync

    print(f"Syncing Code Graph for '{project_name}'...")
    print(f"  Path: {project_path}")
    print(f"  Mode: {'Incremental' if incremental else 'Full rebuild'}")
    print()

    result = sync(project_path, project_name, incremental=incremental)

    print(f"Files processed: {result['files_processed']}")
    print(f"Files skipped: {result['files_skipped']}")
    print(f"Nodes added: {result['nodes_added']}")
    print(f"Nodes updated: {result.get('nodes_updated', 0)}")
    print(f"Edges added: {result['edges_added']}")
    print(f"Duration: {result.get('duration_ms', 0)}ms")

    if result.get('errors'):
        print()
        print("Errors:")
        for err in result['errors']:
            print(f"  - {err}")
        return False

    print()
    print("✅ Code Graph sync complete!")
    return True


def sync_ssot_graph(project_name: str):
    """同步 SSOT Index 到 Graph"""
    from servers.facade import sync_ssot_graph as _sync_ssot

    print(f"Syncing SSOT to Graph for '{project_name}'...")
    print()

    result = _sync_ssot(project_name)

    print(f"Types found: {', '.join(result['types_found'])}")
    print(f"Nodes added: {result['nodes_added']}")
    print(f"Edges added: {result['edges_added']}")
    print(f"Total nodes: {result['total_nodes']}")
    print(f"Total edges: {result['total_edges']}")
    print()
    print("✅ SSOT Graph sync complete!")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Sync Code Graph and SSOT Graph'
    )
    parser.add_argument('path', nargs='?', help='Project path (default: cwd)')
    parser.add_argument('-n', '--name', help='Project name (default: directory name)')
    parser.add_argument('--full', action='store_true', help='Full rebuild (not incremental)')
    parser.add_argument('--ssot', action='store_true', help='Also sync SSOT Graph')

    args = parser.parse_args()

    project_path = args.path or os.getcwd()
    project_name = args.name or os.path.basename(os.path.abspath(project_path))

    success = True

    # Sync Code Graph
    if not sync_code_graph(project_path, project_name, incremental=not args.full):
        success = False

    # Optionally sync SSOT Graph
    if args.ssot:
        print()
        print("-" * 40)
        print()
        if not sync_ssot_graph(project_name):
            success = False

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())

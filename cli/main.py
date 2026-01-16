#!/usr/bin/env python3
"""
HAN CLI

主要命令列入口。

使用方式：
    python -m cli.main <command> [options]

Commands:
    doctor    - 診斷系統狀態
    sync      - 同步 Code Graph
    status    - 顯示專案狀態
    init      - 初始化專案
    drift     - 檢查 SSOT-Code 偏差
"""

import sys
import os
import argparse

# 動態計算路徑，確保可以 import servers
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BASE_DIR)


def cmd_doctor(args):
    """執行系統診斷"""
    from cli.doctor import run_all_diagnostics, print_results
    results = run_all_diagnostics()
    return print_results(results)


def cmd_sync(args):
    """同步 Code Graph"""
    from servers.facade import sync

    project_path = args.path or os.getcwd()
    project_name = args.name or os.path.basename(os.path.abspath(project_path))
    incremental = not args.full

    print(f"Syncing Code Graph for '{project_name}'...")
    print(f"  Path: {project_path}")
    print(f"  Mode: {'Full rebuild' if args.full else 'Incremental'}")
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
        return 1

    print()
    print("✅ Sync complete!")
    return 0


def cmd_status(args):
    """顯示專案狀態"""
    from servers.facade import quick_status
    print(quick_status())
    return 0


def cmd_init(args):
    """初始化專案"""
    from servers.facade import init

    project_path = args.path or os.getcwd()
    project_name = args.name or os.path.basename(os.path.abspath(project_path))

    print(f"Initializing HAN for '{project_name}'...")
    print(f"  Path: {project_path}")
    print()

    result = init(project_path, project_name)

    print(f"Schema initialized: {result['schema_initialized']}")
    print(f"Types initialized: {result['types_initialized'][0]} node kinds, {result['types_initialized'][1]} edge kinds")
    print(f"Code Graph synced: {result['code_graph_synced']}")

    sync_result = result['sync_result']
    print(f"  Files processed: {sync_result['files_processed']}")
    print(f"  Nodes added: {sync_result['nodes_added']}")

    print()
    print("✅ Initialization complete!")
    print()
    print("Next steps:")
    print("  1. Run 'han doctor' to verify setup")
    print("  2. Run 'han install-hooks' to enable auto-sync")
    return 0


def cmd_drift(args):
    """檢查 SSOT-Code 偏差"""
    from servers.facade import check_drift

    project_name = args.name or os.path.basename(os.getcwd())
    flow_id = args.flow

    print(f"Checking drift for '{project_name}'...")
    if flow_id:
        print(f"  Flow: {flow_id}")
    print()

    result = check_drift(project_name, flow_id)

    print(f"Has drift: {'Yes' if result['has_drift'] else 'No'}")
    print(f"Summary: {result['summary']}")

    if result['drifts']:
        print()
        print("Drifts found:")
        for drift in result['drifts']:
            print(f"  [{drift['type']}]")
            print(f"    {drift['description']}")
            if drift.get('ssot_item'):
                print(f"    SSOT: {drift['ssot_item']}")
            if drift.get('code_item'):
                print(f"    Code: {drift['code_item']}")
            print()

    return 0 if not result['has_drift'] else 1


def cmd_install_hooks(args):
    """安裝 Git hooks"""
    import subprocess

    script_path = os.path.join(_BASE_DIR, 'scripts', 'install-hooks.sh')

    if not os.path.exists(script_path):
        print(f"Error: Install script not found: {script_path}")
        return 1

    return subprocess.call(['bash', script_path])


def cmd_ssot_sync(args):
    """同步 SSOT Index 到 Graph"""
    from servers.facade import sync_ssot_graph

    project_name = args.name or os.path.basename(os.getcwd())

    print(f"Syncing SSOT to Graph for '{project_name}'...")
    print()

    result = sync_ssot_graph(project_name)

    print(f"Types found: {', '.join(result['types_found'])}")
    print(f"Nodes added: {result['nodes_added']}")
    print(f"Edges added: {result['edges_added']}")
    print(f"Total nodes: {result['total_nodes']}")
    print(f"Total edges: {result['total_edges']}")
    print()
    print("✅ SSOT Graph sync complete!")
    return 0


def cmd_graph(args):
    """查詢 Graph"""
    from servers.graph import get_neighbors, get_impact, list_nodes, get_graph_stats

    project_name = args.name or os.path.basename(os.getcwd())

    if args.list:
        # 列出所有節點
        print(f"=== Graph Nodes for '{project_name}' ===")
        print()
        nodes = list_nodes(project_name, kind=args.kind)
        if not nodes:
            print("No nodes found. Run 'han ssot-sync' first.")
            return 1

        # 按 kind 分組
        by_kind = {}
        for n in nodes:
            kind = n['kind']
            if kind not in by_kind:
                by_kind[kind] = []
            by_kind[kind].append(n)

        for kind, items in sorted(by_kind.items()):
            print(f"[{kind}] ({len(items)})")
            for n in items:
                ref = f" -> {n['ref']}" if n.get('ref') else ""
                print(f"  {n['id']}: {n['name']}{ref}")
            print()

        stats = get_graph_stats(project_name)
        print(f"Total: {stats['node_count']} nodes, {stats['edge_count']} edges")
        return 0

    elif args.neighbors:
        # 查詢鄰居
        node_id = args.neighbors
        depth = args.depth or 1
        print(f"=== Neighbors of '{node_id}' (depth={depth}) ===")
        print()

        neighbors = get_neighbors(node_id, project=project_name, depth=depth)
        if not neighbors:
            print(f"No neighbors found for '{node_id}'")
            return 0

        for n in neighbors:
            direction = "→" if n['direction'] == 'outgoing' else "←"
            print(f"  {direction} [{n['edge_kind']}] {n['id']} ({n['kind']}) [d={n['distance']}]")
        return 0

    elif args.impact:
        # 查詢影響範圍
        node_id = args.impact
        print(f"=== Impact Analysis: Who depends on '{node_id}'? ===")
        print()

        impact = get_impact(node_id, project=project_name)
        if not impact:
            print(f"No dependencies found for '{node_id}'")
            return 0

        for i in impact:
            print(f"  {i['id']} --[{i['edge_kind']}]--> {node_id}")
        print()
        print(f"Total: {len(impact)} dependents")
        return 0

    else:
        # 顯示統計
        stats = get_graph_stats(project_name)
        print(f"=== Graph Stats for '{project_name}' ===")
        print()
        print(f"Nodes: {stats['node_count']}")
        for kind, count in sorted(stats['nodes_by_kind'].items()):
            print(f"  {kind}: {count}")
        print()
        print(f"Edges: {stats['edge_count']}")
        for kind, count in sorted(stats['edges_by_kind'].items()):
            print(f"  {kind}: {count}")
        return 0


def cmd_dashboard(args):
    """顯示完整儀表板"""
    from servers.facade import status, check_drift, sync_ssot_graph
    from servers.graph import get_graph_stats
    from servers.code_graph import get_code_graph_stats

    project_name = args.name or os.path.basename(os.getcwd())

    print("╔" + "═" * 60 + "╗")
    print(f"║  🧠 HAN Dashboard - {project_name:<27} ║")
    print("╠" + "═" * 60 + "╣")

    # Code Graph 狀態
    try:
        code_stats = get_code_graph_stats(project_name)
        print(f"║  Code Graph                                                ║")
        print(f"║    Nodes: {code_stats['node_count']:<10} Files: {code_stats['file_count']:<10}             ║")
        print(f"║    Edges: {code_stats['edge_count']:<10}                                   ║")
    except Exception as e:
        print(f"║  Code Graph: Error - {str(e)[:35]:<35} ║")

    print("╠" + "─" * 60 + "╣")

    # SSOT Graph 狀態
    try:
        ssot_stats = get_graph_stats(project_name)
        print(f"║  SSOT Graph                                                ║")
        print(f"║    Nodes: {ssot_stats['node_count']:<10} Edges: {ssot_stats['edge_count']:<10}             ║")
        if ssot_stats['nodes_by_kind']:
            kinds_str = ', '.join(f"{k}:{v}" for k, v in sorted(ssot_stats['nodes_by_kind'].items()))
            # 分行顯示如果太長
            if len(kinds_str) > 45:
                kinds_str = kinds_str[:42] + "..."
            print(f"║    Types: {kinds_str:<47} ║")
    except Exception as e:
        print(f"║  SSOT Graph: Error - {str(e)[:35]:<35} ║")

    print("╠" + "─" * 60 + "╣")

    # Drift 檢查
    try:
        drift = check_drift(project_name)
        drift_status = "⚠️ " + drift['summary'] if drift['has_drift'] else "✅ No drift"
        print(f"║  Drift Check                                               ║")
        print(f"║    {drift_status:<55}║")
    except Exception as e:
        print(f"║  Drift Check: Error - {str(e)[:34]:<34} ║")

    print("╚" + "═" * 60 + "╝")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='HAN CLI - Multi-Agent Development System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  doctor         Diagnose system status
  sync           Sync Code Graph from source files
  status         Show project status overview
  init           Initialize project for HAN
  drift          Check SSOT vs Code drift
  install-hooks  Install Git hooks for auto-sync
  ssot-sync      Sync SSOT Index to Graph
  graph          Query and explore the SSOT Graph
  dashboard      Show full system dashboard
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # doctor
    parser_doctor = subparsers.add_parser('doctor', help='Diagnose system status')
    parser_doctor.set_defaults(func=cmd_doctor)

    # sync
    parser_sync = subparsers.add_parser('sync', help='Sync Code Graph')
    parser_sync.add_argument('-p', '--path', help='Project path (default: cwd)')
    parser_sync.add_argument('-n', '--name', help='Project name (default: directory name)')
    parser_sync.add_argument('--full', action='store_true', help='Full rebuild (not incremental)')
    parser_sync.set_defaults(func=cmd_sync)

    # status
    parser_status = subparsers.add_parser('status', help='Show project status')
    parser_status.set_defaults(func=cmd_status)

    # init
    parser_init = subparsers.add_parser('init', help='Initialize project')
    parser_init.add_argument('-p', '--path', help='Project path (default: cwd)')
    parser_init.add_argument('-n', '--name', help='Project name (default: directory name)')
    parser_init.set_defaults(func=cmd_init)

    # drift
    parser_drift = subparsers.add_parser('drift', help='Check SSOT-Code drift')
    parser_drift.add_argument('-n', '--name', help='Project name')
    parser_drift.add_argument('-f', '--flow', help='Specific flow to check')
    parser_drift.set_defaults(func=cmd_drift)

    # install-hooks
    parser_hooks = subparsers.add_parser('install-hooks', help='Install Git hooks')
    parser_hooks.set_defaults(func=cmd_install_hooks)

    # ssot-sync
    parser_ssot = subparsers.add_parser('ssot-sync', help='Sync SSOT Index to Graph')
    parser_ssot.add_argument('-n', '--name', help='Project name')
    parser_ssot.set_defaults(func=cmd_ssot_sync)

    # graph
    parser_graph = subparsers.add_parser('graph', help='Query SSOT Graph')
    parser_graph.add_argument('-n', '--name', help='Project name')
    parser_graph.add_argument('-l', '--list', action='store_true', help='List all nodes')
    parser_graph.add_argument('-k', '--kind', help='Filter by node kind')
    parser_graph.add_argument('--neighbors', metavar='NODE_ID', help='Get neighbors of a node')
    parser_graph.add_argument('--impact', metavar='NODE_ID', help='Get impact analysis for a node')
    parser_graph.add_argument('-d', '--depth', type=int, default=1, help='Depth for neighbor query')
    parser_graph.set_defaults(func=cmd_graph)

    # dashboard
    parser_dash = subparsers.add_parser('dashboard', help='Show full dashboard')
    parser_dash.add_argument('-n', '--name', help='Project name')
    parser_dash.set_defaults(func=cmd_dashboard)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())

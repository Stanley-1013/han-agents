#!/usr/bin/env python3
"""
HAN Doctor

診斷系統所有銜接點，確保各組件正確整合。

使用方式：
    python -m cli.doctor
    python cli/doctor.py
"""

import os
import sys
from typing import List, Dict, Tuple
from dataclasses import dataclass
from enum import Enum

# 動態計算路徑，確保可以 import servers
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BASE_DIR)


class Status(Enum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class DiagnosticResult:
    name: str
    status: Status
    message: str
    fix_hint: str = None


def check_database() -> DiagnosticResult:
    """檢查資料庫是否存在且可連接"""
    db_path = os.path.join(_BASE_DIR, 'brain', 'brain.db')

    if not os.path.exists(db_path):
        return DiagnosticResult(
            name="Database",
            status=Status.ERROR,
            message=f"Database not found: {db_path}",
            fix_hint="Run: from servers.registry import init_registry; init_registry()"
        )

    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        required_tables = [
            'tasks', 'long_term_memory', 'working_memory',
            'project_nodes', 'project_edges', 'code_nodes', 'code_edges',
            'node_kind_registry', 'edge_kind_registry', 'file_hashes'
        ]

        missing = [t for t in required_tables if t not in tables]
        if missing:
            return DiagnosticResult(
                name="Database",
                status=Status.WARNING,
                message=f"Missing tables: {', '.join(missing)}",
                fix_hint="Run: from servers.registry import ensure_schema_exists; ensure_schema_exists()"
            )

        return DiagnosticResult(
            name="Database",
            status=Status.OK,
            message=f"Connected, {len(tables)} tables found"
        )
    except Exception as e:
        return DiagnosticResult(
            name="Database",
            status=Status.ERROR,
            message=f"Connection failed: {str(e)}"
        )


def check_registry() -> DiagnosticResult:
    """檢查類型註冊表"""
    try:
        from servers.registry import diagnose
        result = diagnose()

        if result['status'] == 'error':
            return DiagnosticResult(
                name="Type Registry",
                status=Status.ERROR,
                message="; ".join(result.get('messages', ['Unknown error']))
            )

        if result['status'] == 'warning':
            return DiagnosticResult(
                name="Type Registry",
                status=Status.WARNING,
                message="; ".join(result.get('messages', [])),
                fix_hint="Run: from servers.registry import init_default_types; init_default_types()"
            )

        return DiagnosticResult(
            name="Type Registry",
            status=Status.OK,
            message=f"{result['node_kinds_count']} node kinds, {result['edge_kinds_count']} edge kinds"
        )
    except Exception as e:
        return DiagnosticResult(
            name="Type Registry",
            status=Status.ERROR,
            message=f"Check failed: {str(e)}"
        )


def check_ssot_files() -> DiagnosticResult:
    """檢查 SSOT 檔案"""
    ssot_dir = os.path.join(_BASE_DIR, 'brain', 'ssot')
    doctrine_path = os.path.join(ssot_dir, 'PROJECT_DOCTRINE.md')
    index_path = os.path.join(ssot_dir, 'PROJECT_INDEX.md')

    issues = []
    if not os.path.exists(ssot_dir):
        issues.append("SSOT directory missing")
    if not os.path.exists(doctrine_path):
        issues.append("PROJECT_DOCTRINE.md missing")
    if not os.path.exists(index_path):
        issues.append("PROJECT_INDEX.md missing")

    if issues:
        return DiagnosticResult(
            name="SSOT Files",
            status=Status.WARNING,
            message="; ".join(issues),
            fix_hint="Create SSOT files in brain/ssot/ directory"
        )

    return DiagnosticResult(
        name="SSOT Files",
        status=Status.OK,
        message="Doctrine and Index found"
    )


def check_code_graph() -> DiagnosticResult:
    """檢查 Code Graph"""
    try:
        from servers.code_graph import get_code_graph_stats
        stats = get_code_graph_stats('default')

        if stats['node_count'] == 0:
            return DiagnosticResult(
                name="Code Graph",
                status=Status.WARNING,
                message="Code Graph is empty",
                fix_hint="Run: from servers.facade import sync; sync('/path/to/project')"
            )

        return DiagnosticResult(
            name="Code Graph",
            status=Status.OK,
            message=f"{stats['node_count']} nodes, {stats['edge_count']} edges, {stats['file_count']} files"
        )
    except Exception as e:
        return DiagnosticResult(
            name="Code Graph",
            status=Status.ERROR,
            message=f"Check failed: {str(e)}"
        )


def check_git_hooks() -> DiagnosticResult:
    """檢查 Git Hooks（如果在 Git repo 中）"""
    # 嘗試找到 Git repo
    cwd = os.getcwd()
    git_dir = os.path.join(cwd, '.git')

    if not os.path.exists(git_dir):
        return DiagnosticResult(
            name="Git Hooks",
            status=Status.OK,
            message="Not in a Git repository (skipped)"
        )

    hooks_dir = os.path.join(git_dir, 'hooks')
    post_merge = os.path.join(hooks_dir, 'post-merge')

    if not os.path.exists(post_merge):
        return DiagnosticResult(
            name="Git Hooks",
            status=Status.WARNING,
            message="post-merge hook not installed",
            fix_hint="Run: han install-hooks (or manually create .git/hooks/post-merge)"
        )

    # 檢查 hook 內容是否包含 han
    with open(post_merge, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'han' not in content.lower():
        return DiagnosticResult(
            name="Git Hooks",
            status=Status.WARNING,
            message="post-merge hook exists but doesn't call han",
            fix_hint="Add han sync command to .git/hooks/post-merge"
        )

    return DiagnosticResult(
        name="Git Hooks",
        status=Status.OK,
        message="post-merge hook installed"
    )


def check_servers() -> DiagnosticResult:
    """檢查所有 Server 模組是否可 import"""
    modules = [
        'servers.tasks',
        'servers.memory',
        'servers.ssot',
        'servers.graph',
        'servers.registry',
        'servers.code_graph',
        'servers.facade',
    ]

    failed = []
    for mod in modules:
        try:
            __import__(mod)
        except Exception as e:
            failed.append(f"{mod}: {str(e)[:50]}")

    if failed:
        return DiagnosticResult(
            name="Server Modules",
            status=Status.ERROR,
            message=f"Failed to import: {'; '.join(failed)}"
        )

    return DiagnosticResult(
        name="Server Modules",
        status=Status.OK,
        message=f"All {len(modules)} modules loaded"
    )


def check_extractor() -> DiagnosticResult:
    """檢查 Code Graph Extractor"""
    try:
        from tools.code_graph_extractor import get_supported_languages
        languages = get_supported_languages()

        return DiagnosticResult(
            name="Code Extractor",
            status=Status.OK,
            message=f"Supports: {', '.join(sorted(set(languages)))}"
        )
    except Exception as e:
        return DiagnosticResult(
            name="Code Extractor",
            status=Status.ERROR,
            message=f"Failed to load: {str(e)}"
        )


def run_all_diagnostics() -> List[DiagnosticResult]:
    """執行所有診斷"""
    checks = [
        check_database,
        check_registry,
        check_ssot_files,
        check_servers,
        check_extractor,
        check_code_graph,
        check_git_hooks,
    ]

    results = []
    for check in checks:
        try:
            results.append(check())
        except Exception as e:
            results.append(DiagnosticResult(
                name=check.__name__.replace('check_', '').title(),
                status=Status.ERROR,
                message=f"Check crashed: {str(e)}"
            ))

    return results


def print_results(results: List[DiagnosticResult]):
    """印出診斷結果"""
    status_icons = {
        Status.OK: "✅",
        Status.WARNING: "⚠️",
        Status.ERROR: "❌",
    }

    print("=" * 60)
    print("🧠 HAN System Diagnostics")
    print("=" * 60)
    print()

    for result in results:
        icon = status_icons[result.status]
        print(f"{icon} {result.name}")
        print(f"   {result.message}")
        if result.fix_hint and result.status != Status.OK:
            print(f"   💡 {result.fix_hint}")
        print()

    # 總結
    ok_count = sum(1 for r in results if r.status == Status.OK)
    warning_count = sum(1 for r in results if r.status == Status.WARNING)
    error_count = sum(1 for r in results if r.status == Status.ERROR)

    print("=" * 60)
    print(f"Summary: {ok_count} OK, {warning_count} warnings, {error_count} errors")

    if error_count > 0:
        print("\n⛔ Critical issues found. Please fix errors above.")
        return 1
    elif warning_count > 0:
        print("\n⚠️ Some issues found. Consider fixing warnings above.")
        return 0
    else:
        print("\n✅ All systems operational!")
        return 0


def main():
    results = run_all_diagnostics()
    exit_code = print_results(results)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()

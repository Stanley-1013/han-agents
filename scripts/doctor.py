#!/usr/bin/env python3
"""
HAN Doctor (Simplified)

診斷系統狀態，確保各組件正確運作。

使用方式：
    python doctor.py
"""

import os
import sys
from typing import List
from dataclasses import dataclass
from enum import Enum

# Windows console encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 確保可以 import servers（使用相對路徑，相容所有平台）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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


def auto_init_database():
    """自動初始化資料庫（如果不存在或缺少 tables）"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    brain_dir = os.path.join(base_dir, 'brain')
    db_path = os.path.join(brain_dir, 'brain.db')
    schema_path = os.path.join(brain_dir, 'schema.sql')

    # 確保目錄存在
    os.makedirs(brain_dir, exist_ok=True)

    need_init = not os.path.exists(db_path)

    # 檢查是否需要初始化 schema
    if os.path.exists(db_path):
        import sqlite3
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            if 'tasks' not in tables:
                need_init = True
        except:
            need_init = True

    if need_init and os.path.exists(schema_path):
        import sqlite3
        print("🔧 Auto-initializing database...")
        conn = sqlite3.connect(db_path)
        with open(schema_path, encoding='utf-8') as f:
            conn.executescript(f.read())
        conn.commit()
        conn.close()
        print(f"✅ Database initialized: {db_path}")

    return db_path


def check_database() -> DiagnosticResult:
    """檢查資料庫"""
    # 使用相對路徑，相容 Windows/Mac/Linux
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, 'brain', 'brain.db')

    if not os.path.exists(db_path):
        return DiagnosticResult(
            name="Database",
            status=Status.ERROR,
            message=f"Database not found: {db_path}",
            fix_hint="Run: python scripts/install.py"
        )

    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        required_tables = [
            'tasks', 'long_term_memory', 'working_memory',
            'project_nodes', 'project_edges', 'code_nodes', 'code_edges'
        ]

        missing = [t for t in required_tables if t not in tables]
        if missing:
            return DiagnosticResult(
                name="Database",
                status=Status.WARNING,
                message=f"Missing tables: {', '.join(missing)}",
                fix_hint="Run: python <skills-path>/han-agents/scripts/install.py"
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


def check_servers() -> DiagnosticResult:
    """檢查 Server 模組"""
    modules = [
        'servers.tasks',
        'servers.memory',
        'servers.facade',
    ]

    failed = []
    for mod in modules:
        try:
            __import__(mod)
        except Exception as e:
            failed.append(f"{mod}: {str(e)[:30]}")

    if failed:
        return DiagnosticResult(
            name="Server Modules",
            status=Status.ERROR,
            message=f"Failed: {'; '.join(failed)}"
        )

    return DiagnosticResult(
        name="Server Modules",
        status=Status.OK,
        message=f"All {len(modules)} modules loaded"
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
                message=result.get('messages', ['Unknown error'])[0]
            )

        return DiagnosticResult(
            name="Type Registry",
            status=Status.OK,
            message=f"{result['node_kinds_count']} node, {result['edge_kinds_count']} edge kinds"
        )
    except Exception as e:
        return DiagnosticResult(
            name="Type Registry",
            status=Status.ERROR,
            message=f"Check failed: {str(e)}"
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
                fix_hint="Run: python <skills-path>/han-agents/scripts/sync.py"
            )

        return DiagnosticResult(
            name="Code Graph",
            status=Status.OK,
            message=f"{stats['node_count']} nodes, {stats['file_count']} files"
        )
    except Exception as e:
        return DiagnosticResult(
            name="Code Graph",
            status=Status.ERROR,
            message=f"Check failed: {str(e)}"
        )


def run_diagnostics() -> List[DiagnosticResult]:
    """執行診斷"""
    checks = [
        check_database,
        check_servers,
        check_registry,
        check_code_graph,
    ]

    results = []
    for check in checks:
        try:
            results.append(check())
        except Exception as e:
            results.append(DiagnosticResult(
                name=check.__name__.replace('check_', '').title(),
                status=Status.ERROR,
                message=f"Crashed: {str(e)}"
            ))

    return results


def print_results(results: List[DiagnosticResult]) -> int:
    """印出結果"""
    icons = {
        Status.OK: "✅",
        Status.WARNING: "⚠️",
        Status.ERROR: "❌",
    }

    print("=" * 50)
    print("🧠 HAN System Diagnostics")
    print("=" * 50)
    print()

    for result in results:
        icon = icons[result.status]
        print(f"{icon} {result.name}")
        print(f"   {result.message}")
        if result.fix_hint and result.status != Status.OK:
            print(f"   💡 {result.fix_hint}")
        print()

    ok = sum(1 for r in results if r.status == Status.OK)
    warn = sum(1 for r in results if r.status == Status.WARNING)
    err = sum(1 for r in results if r.status == Status.ERROR)

    print("=" * 50)
    print(f"Summary: {ok} OK, {warn} warnings, {err} errors")

    if err > 0:
        print("\n⛔ Critical issues found.")
        return 1
    elif warn > 0:
        print("\n⚠️ Some issues found.")
        return 0
    else:
        print("\n✅ All systems operational!")
        return 0


def main():
    # 自動初始化資料庫（如果需要）
    auto_init_database()

    results = run_diagnostics()
    return print_results(results)


if __name__ == '__main__':
    sys.exit(main())

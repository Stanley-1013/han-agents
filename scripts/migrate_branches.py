#!/usr/bin/env python3
"""
migrate_branches.py - Branch 欄位遷移腳本
==========================================

Story 2: Memory 查詢增強

為現有 long_term_memory 表添加 branch_* 欄位和索引。
這是一個非破壞性遷移，可以安全地多次執行。

使用方式：
    python scripts/migrate_branches.py [--dry-run]

選項：
    --dry-run   只顯示將執行的操作，不實際修改資料庫
"""

import sys
import os
import sqlite3

# Windows console encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from datetime import datetime

# 動態計算路徑（相對於此腳本位置）
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAIN_DB = os.path.join(_BASE_DIR, 'brain', 'brain.db')

def check_column_exists(cursor, table: str, column: str) -> bool:
    """檢查欄位是否存在"""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns

def check_index_exists(cursor, index_name: str) -> bool:
    """檢查索引是否存在"""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
        (index_name,)
    )
    return cursor.fetchone() is not None

def migrate(dry_run: bool = False):
    """執行遷移"""
    print(f"=== Branch 欄位遷移腳本 ===")
    print(f"資料庫: {BRAIN_DB}")
    print(f"模式: {'Dry Run (不修改資料庫)' if dry_run else '實際執行'}")
    print(f"時間: {datetime.now().isoformat()}")
    print()

    if not os.path.exists(BRAIN_DB):
        print(f"❌ 資料庫不存在: {BRAIN_DB}")
        print("請先執行系統初始化創建資料庫。")
        return False

    db = sqlite3.connect(BRAIN_DB)
    cursor = db.cursor()

    changes = []

    # 1. 檢查並添加 branch_flow 欄位
    if not check_column_exists(cursor, 'long_term_memory', 'branch_flow'):
        sql = "ALTER TABLE long_term_memory ADD COLUMN branch_flow TEXT"
        changes.append(('ADD COLUMN', 'branch_flow', sql))
        if not dry_run:
            cursor.execute(sql)
            print("✅ 添加欄位: branch_flow")
    else:
        print("⏭️  欄位已存在: branch_flow")

    # 2. 檢查並添加 branch_domain 欄位
    if not check_column_exists(cursor, 'long_term_memory', 'branch_domain'):
        sql = "ALTER TABLE long_term_memory ADD COLUMN branch_domain TEXT"
        changes.append(('ADD COLUMN', 'branch_domain', sql))
        if not dry_run:
            cursor.execute(sql)
            print("✅ 添加欄位: branch_domain")
    else:
        print("⏭️  欄位已存在: branch_domain")

    # 3. 檢查並添加 branch_page 欄位
    if not check_column_exists(cursor, 'long_term_memory', 'branch_page'):
        sql = "ALTER TABLE long_term_memory ADD COLUMN branch_page TEXT"
        changes.append(('ADD COLUMN', 'branch_page', sql))
        if not dry_run:
            cursor.execute(sql)
            print("✅ 添加欄位: branch_page")
    else:
        print("⏭️  欄位已存在: branch_page")

    # 4. 檢查並添加 idx_ltm_branch_flow 索引
    if not check_index_exists(cursor, 'idx_ltm_branch_flow'):
        sql = "CREATE INDEX idx_ltm_branch_flow ON long_term_memory(branch_flow)"
        changes.append(('CREATE INDEX', 'idx_ltm_branch_flow', sql))
        if not dry_run:
            cursor.execute(sql)
            print("✅ 添加索引: idx_ltm_branch_flow")
    else:
        print("⏭️  索引已存在: idx_ltm_branch_flow")

    # 5. 檢查並添加 idx_ltm_branch_domain 索引
    if not check_index_exists(cursor, 'idx_ltm_branch_domain'):
        sql = "CREATE INDEX idx_ltm_branch_domain ON long_term_memory(branch_domain)"
        changes.append(('CREATE INDEX', 'idx_ltm_branch_domain', sql))
        if not dry_run:
            cursor.execute(sql)
            print("✅ 添加索引: idx_ltm_branch_domain")
    else:
        print("⏭️  索引已存在: idx_ltm_branch_domain")

    # 統計現有記憶數量
    cursor.execute("SELECT COUNT(*) FROM long_term_memory")
    total_memories = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM long_term_memory
        WHERE branch_flow IS NOT NULL OR branch_domain IS NOT NULL
    """)
    tagged_memories = cursor.fetchone()[0]

    print()
    print(f"=== 統計資訊 ===")
    print(f"總記憶數: {total_memories}")
    print(f"已標記 branch 的記憶: {tagged_memories}")
    print(f"待標記記憶: {total_memories - tagged_memories}")

    if dry_run:
        print()
        print("=== Dry Run 報告 ===")
        if changes:
            print(f"將執行 {len(changes)} 項變更:")
            for change_type, name, sql in changes:
                print(f"  - {change_type}: {name}")
                print(f"    SQL: {sql}")
        else:
            print("無需變更，資料庫已是最新狀態。")
    else:
        db.commit()
        print()
        print(f"=== 遷移完成 ===")
        print(f"執行了 {len(changes)} 項變更")

    db.close()
    return True

def main():
    dry_run = '--dry-run' in sys.argv

    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__)
        return

    success = migrate(dry_run=dry_run)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

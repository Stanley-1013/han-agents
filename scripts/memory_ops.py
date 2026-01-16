#!/usr/bin/env python3
"""
HAN Memory Operations

記憶操作工具腳本。

使用方式：
    python memory_ops.py search <query>
    python memory_ops.py store <category> <title> <content>
    python memory_ops.py list [--limit N]
    python memory_ops.py checkpoint <project> <task_id> <summary>
"""

import sys
import os

# Windows console encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import argparse
import json

# 動態計算路徑，確保可以 import servers
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BASE_DIR)


def cmd_search(args):
    """搜尋記憶"""
    from servers.memory import search_memory_semantic

    result = search_memory_semantic(
        args.query,
        limit=args.limit or 10,
        rerank_mode=args.rerank or 'fts5_only'
    )

    if result['mode'] == 'claude_rerank':
        print("## Claude Rerank Required")
        print()
        print(result['rerank_prompt'])
        return 0

    memories = result['results']

    if not memories:
        print("No memories found.")
        return 0

    print(f"Found {len(memories)} memories:")
    print()

    for i, m in enumerate(memories, 1):
        print(f"{i}. [{m['category']}] {m['title']} (importance={m['importance']})")
        content_preview = m['content'][:100].replace('\n', ' ')
        print(f"   {content_preview}...")
        print()

    return 0


def cmd_store(args):
    """儲存記憶"""
    from servers.memory import store_memory

    memory_id = store_memory(
        category=args.category,
        title=args.title,
        content=args.content,
        project=args.project,
        importance=args.importance or 5
    )

    print(f"✅ Memory stored: {memory_id}")
    return 0


def cmd_list(args):
    """列出記憶"""
    import sqlite3

    db_path = os.path.join(_BASE_DIR, 'brain', 'brain.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    query = """
        SELECT id, category, title, importance, created_at
        FROM long_term_memory
        ORDER BY created_at DESC
        LIMIT ?
    """

    cursor = conn.execute(query, (args.limit or 20,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("No memories found.")
        return 0

    print(f"Recent {len(rows)} memories:")
    print()
    print(f"{'ID':<8} {'Category':<12} {'Title':<30} {'Imp':<4} {'Created'}")
    print("-" * 80)

    for row in rows:
        title = row['title'][:28] + '..' if len(row['title']) > 30 else row['title']
        created = row['created_at'][:16] if row['created_at'] else ''
        print(f"{row['id']:<8} {row['category']:<12} {title:<30} {row['importance']:<4} {created}")

    return 0


def cmd_checkpoint(args):
    """儲存 checkpoint"""
    from servers.memory import save_checkpoint

    state = {}
    if args.state:
        try:
            state = json.loads(args.state)
        except json.JSONDecodeError:
            print("Error: --state must be valid JSON")
            return 1

    checkpoint_id = save_checkpoint(
        project=args.project,
        task_id=args.task_id,
        agent=args.agent or 'pfc',
        state=state,
        summary=args.summary
    )

    print(f"✅ Checkpoint saved: {checkpoint_id}")
    return 0


def cmd_load_checkpoint(args):
    """載入 checkpoint"""
    from servers.memory import load_checkpoint

    checkpoint = load_checkpoint(args.task_id)

    if not checkpoint:
        print(f"No checkpoint found for task: {args.task_id}")
        return 1

    print(f"Checkpoint for task: {args.task_id}")
    print(f"  Agent: {checkpoint.get('agent', 'unknown')}")
    print(f"  Summary: {checkpoint.get('summary', '')}")
    print()
    print("State:")
    print(json.dumps(checkpoint.get('state', {}), indent=2, ensure_ascii=False))
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='HAN Memory Operations'
    )

    subparsers = parser.add_subparsers(dest='command', help='Command')

    # search
    p_search = subparsers.add_parser('search', help='Search memories')
    p_search.add_argument('query', help='Search query')
    p_search.add_argument('-l', '--limit', type=int, help='Max results')
    p_search.add_argument('-r', '--rerank', choices=['fts5_only', 'claude', 'hybrid'],
                         help='Rerank mode')
    p_search.set_defaults(func=cmd_search)

    # store
    p_store = subparsers.add_parser('store', help='Store a memory')
    p_store.add_argument('category', help='Category (pattern, lesson, procedure, knowledge)')
    p_store.add_argument('title', help='Memory title')
    p_store.add_argument('content', help='Memory content')
    p_store.add_argument('-p', '--project', help='Project name')
    p_store.add_argument('-i', '--importance', type=int, help='Importance (1-10)')
    p_store.set_defaults(func=cmd_store)

    # list
    p_list = subparsers.add_parser('list', help='List recent memories')
    p_list.add_argument('-l', '--limit', type=int, help='Max results')
    p_list.set_defaults(func=cmd_list)

    # checkpoint
    p_ckpt = subparsers.add_parser('checkpoint', help='Save checkpoint')
    p_ckpt.add_argument('project', help='Project name')
    p_ckpt.add_argument('task_id', help='Task ID')
    p_ckpt.add_argument('summary', help='Checkpoint summary')
    p_ckpt.add_argument('-a', '--agent', help='Agent name')
    p_ckpt.add_argument('-s', '--state', help='State as JSON')
    p_ckpt.set_defaults(func=cmd_checkpoint)

    # load-checkpoint
    p_load = subparsers.add_parser('load-checkpoint', help='Load checkpoint')
    p_load.add_argument('task_id', help='Task ID')
    p_load.set_defaults(func=cmd_load_checkpoint)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())

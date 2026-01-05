#!/usr/bin/env python3
"""
Cortex System - 安裝腳本

功能：
1. 檢查系統依賴
2. 複製 agent 定義到 ~/.claude/agents/
3. 如果資料庫不存在，初始化資料庫
4. 不會覆蓋現有資料庫（保護跨專案記憶）
"""

import os
import sqlite3
import shutil
import sys

# Windows console encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import json

def check_dependencies():
    """檢查系統依賴"""
    errors = []
    warnings = []

    # 1. Python 版本檢查
    if sys.version_info < (3, 8):
        errors.append(f"Python 3.8+ 必須，目前版本: {sys.version}")

    # 2. sqlite3 模組檢查（Python 內建，但確認可用）
    try:
        import sqlite3
        # 測試是否能建立記憶體資料庫
        conn = sqlite3.connect(':memory:')
        conn.execute('SELECT 1')
        conn.close()
    except Exception as e:
        errors.append(f"sqlite3 模組無法使用: {e}")

    # 3. 目錄權限檢查
    claude_dir = os.path.expanduser('~/.claude')
    if os.path.exists(claude_dir):
        if not os.access(claude_dir, os.W_OK):
            errors.append(f"無寫入權限: {claude_dir}")
    else:
        # 嘗試建立
        try:
            os.makedirs(claude_dir, exist_ok=True)
        except Exception as e:
            errors.append(f"無法建立目錄 {claude_dir}: {e}")

    # 回報結果
    if errors:
        print("❌ 依賴檢查失敗:")
        for e in errors:
            print(f"   - {e}")
        print("\n請先解決上述問題再重新執行安裝。")
        sys.exit(1)

    if warnings:
        print("⚠️  警告:")
        for w in warnings:
            print(f"   - {w}")

    print("✅ 依賴檢查通過")
    return True

def install():
    base_dir = os.path.expanduser('~/.claude/skills/cortex-agents')
    agents_dir = os.path.expanduser('~/.claude/agents')
    brain_dir = os.path.join(base_dir, 'brain')
    db_path = os.path.join(brain_dir, 'brain.db')
    schema_path = os.path.join(brain_dir, 'schema.sql')

    print("🧠 安裝 Cortex Multi-Agent System")
    print("=" * 50)

    # 0. 依賴檢查
    check_dependencies()

    # 1. 確保目錄存在
    os.makedirs(agents_dir, exist_ok=True)
    print(f"✅ 確認 agents 目錄: {agents_dir}")

    # 2. 複製 agent 定義到 ~/.claude/agents/
    source_agents = os.path.join(base_dir, 'agents')
    if os.path.exists(source_agents):
        for agent_file in os.listdir(source_agents):
            if agent_file.endswith('.md'):
                src = os.path.join(source_agents, agent_file)
                dst = os.path.join(agents_dir, agent_file)
                shutil.copy2(src, dst)
                print(f"✅ 安裝 agent: {agent_file}")

    # 3. 確保 brain 目錄存在並初始化或升級資料庫
    os.makedirs(brain_dir, exist_ok=True)
    if os.path.exists(db_path):
        print(f"✅ 資料庫已存在: {db_path}")
        # 自動補齊缺失的 table（不影響現有資料）
        upgrade_database(db_path, schema_path)
    else:
        init_database(db_path, schema_path)

    # 4. 設定 Claude Code Hook ⭐
    settings_path = os.path.expanduser('~/.claude/settings.json')
    setup_hooks(settings_path, base_dir)

    # 5. 完成
    print("\n" + "=" * 50)
    print("🎉 安裝完成！")
    print("\n可用 Agents:")
    print("  pfc            - 任務規劃、分解子任務")
    print("  executor       - 執行單一任務")
    print("  critic         - 驗證結果品質")
    print("  memory         - 記憶管理")
    print("  researcher     - 資訊收集")
    print("  drift-detector - 檢測 SSOT 與 Code 偏差")
    print("\n使用方式:")
    print("  對 Claude Code 說：「使用 pfc agent 規劃 [任務描述]」")

    # 回傳 base_dir 供後續處理
    return base_dir

def setup_hooks(settings_path, base_dir):
    """設定 Claude Code PostToolUse Hook"""
    hook_command = f"python3 {os.path.join(base_dir, 'hooks', 'post_task.py')}"

    # 預期的 Hook 設定
    hook_config = {
        "matcher": "Task",
        "hooks": [
            {
                "type": "command",
                "command": hook_command,
                "timeout": 30
            }
        ]
    }

    # 讀取現有設定（如果有）
    settings = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r') as f:
                settings = json.load(f)
            print(f"✅ 讀取現有 Claude 設定: {settings_path}")
        except json.JSONDecodeError:
            print(f"⚠️  設定檔格式錯誤，將重建: {settings_path}")
            settings = {}

    # 確保 hooks 結構存在
    if 'hooks' not in settings:
        settings['hooks'] = {}

    if 'PostToolUse' not in settings['hooks']:
        settings['hooks']['PostToolUse'] = []

    # 檢查是否已有 Task matcher
    existing_matchers = [h.get('matcher') for h in settings['hooks']['PostToolUse']]

    if 'Task' in existing_matchers:
        # 更新現有設定
        for i, hook in enumerate(settings['hooks']['PostToolUse']):
            if hook.get('matcher') == 'Task':
                settings['hooks']['PostToolUse'][i] = hook_config
                print(f"✅ 更新 Task Hook 設定")
                break
    else:
        # 新增設定
        settings['hooks']['PostToolUse'].append(hook_config)
        print(f"✅ 新增 Task Hook 設定")

    # 寫入設定
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)

    print(f"✅ Claude Code Hook 設定完成: {settings_path}")
    print(f"   Hook: PostToolUse → Task → post_task.py")


def ask_add_to_claude_md(base_dir, auto_confirm=False):
    """詢問是否將 PFC 系統設定加入專案的 CLAUDE.md

    Args:
        base_dir: cortex 系統目錄
        auto_confirm: True 時自動確認，不詢問（供非互動模式使用）
    """
    print("\n" + "=" * 50)

    # 找當前目錄的 CLAUDE.md
    cwd = os.getcwd()
    claude_md_path = os.path.join(cwd, 'CLAUDE.md')

    if not auto_confirm:
        response = input("是否要將 PFC 系統設定加到當前專案的 CLAUDE.md？(y/n): ").strip().lower()
        if response != 'y':
            print(f"跳過。如需手動加入，請參考：{os.path.join(base_dir, 'README.md')}")
            return
    else:
        print("自動加入 CLAUDE.md 設定...")

    # 要加入的設定內容
    pfc_config = '''
## Cortex Multi-Agent 系統

> **本專案使用 Cortex Multi-Agent 系統進行任務管理**
>
> 完整協作指南：`~/.claude/skills/cortex-agents/SYSTEM_GUIDE.md`

### ⚠️ 使用規則

**一般任務**：Claude Code 可直接執行，不需派發 agent。

**使用 PFC 系統時**（複雜多步驟任務、用戶明確要求）：

1. **必須透過 Task tool 派發 agent** - Claude Code 是「調度者」，不是「執行者」
2. **完整執行循環**：
   - 派發 `pfc` agent 規劃任務
   - 派發 `executor` agent 執行子任務
   - 派發 `critic` agent 驗證結果
   - 派發 `memory` agent 存經驗
3. **auto-compact 後必須檢查任務進度** - 讀取 DB 恢復狀態

**禁止行為（使用 PFC 時）：**
- ❌ 直接用 Bash 執行本應由 Executor 做的檔案操作/程式碼修改
- ❌ 自己扮演 PFC 規劃而不派發 Task tool
- ❌ 跳過 Critic 驗證直接完成任務

**Agent 限制：**
- ❌ Executor 禁止執行 `git commit` / `git push` - 由 Claude Code 主體審核後提交
- ❌ Agent 不得覆蓋人工編排的文檔，除非明確指示

### 可用 Agents

| Agent | subagent_type | 用途 |
|-------|---------------|------|
| PFC | `pfc` | 任務規劃、協調 |
| Executor | `executor` | 執行單一任務 |
| Critic | `critic` | 驗證結果 |
| Memory | `memory` | 知識管理 |
| Researcher | `researcher` | 資訊收集 |
| Drift Detector | `drift-detector` | 檢測 SSOT 與 Code 偏差 |

### 系統入口（供 Agent 使用）

```python
import sys
import os
sys.path.insert(0, os.path.expanduser('~/.claude/skills/cortex-agents'))
from servers.tasks import get_task_progress, create_task
from servers.memory import search_memory, load_checkpoint
```

### 使用方式

對 Claude Code 說：「使用 pfc agent 規劃 [任務描述]」
'''

    try:
        if os.path.exists(claude_md_path):
            # 檢查是否已經有 PFC 設定
            with open(claude_md_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if 'Cortex Multi-Agent' in content:
                print("⚠️  CLAUDE.md 已包含 PFC 系統設定，跳過")
                return

            # 附加到檔案末尾
            with open(claude_md_path, 'a', encoding='utf-8') as f:
                f.write('\n' + pfc_config)
            print(f"✅ 已加入 {claude_md_path}")
        else:
            # 建立新檔案
            with open(claude_md_path, 'w', encoding='utf-8') as f:
                f.write(f"# {os.path.basename(cwd)} - 專案指令\n" + pfc_config)
            print(f"✅ 已建立 {claude_md_path}")
    except Exception as e:
        print(f"❌ 無法寫入 CLAUDE.md: {e}")
        print(f"   請手動加入，參考：{os.path.join(base_dir, 'README.md')}")

def ask_init_project_ssot(base_dir, auto_confirm=False):
    """詢問是否為當前專案初始化 SSOT INDEX

    Args:
        base_dir: cortex 系統目錄
        auto_confirm: True 時自動確認，不詢問（供非互動模式使用）
    """
    print("\n" + "=" * 50)

    cwd = os.getcwd()
    pfc_dir = os.path.join(cwd, '.claude', 'pfc')
    index_path = os.path.join(pfc_dir, 'INDEX.md')

    # 如果已存在，跳過
    if os.path.exists(index_path):
        print(f"✅ 專案 SSOT 已存在: {index_path}")
        return

    if not auto_confirm:
        response = input("是否要為當前專案初始化 SSOT INDEX？(y/n): ").strip().lower()
        if response != 'y':
            print("跳過。之後可執行 `python install.py --init-ssot` 初始化")
            return
    else:
        print("自動初始化 SSOT INDEX...")

    # 建立目錄
    os.makedirs(pfc_dir, exist_ok=True)

    # INDEX 模板 - 給 LLM 的指示
    project_name = os.path.basename(cwd)
    index_template = f'''# {project_name} - SSOT Index

> **請 Claude 掃描專案後填入此檔案**
>
> 對 Claude 說：「請掃描專案，找出技術文件並更新 .claude/pfc/INDEX.md」

## 格式說明

用 `ref` 指向專案內的技術文件（相對路徑），Agent 會自動載入對應內容。

```yaml
docs:
  - id: doc.xxx        # 唯一識別碼
    name: 文件名稱      # 顯示名稱
    ref: path/to/file  # 相對路徑
    required: true     # 可選：標記為必讀規範
```

## 必讀規範（每次任務開始前載入）

```yaml
rules:
  # 指向專案必須遵守的規範文檔
  # Agent 開始任務前會先讀取這些文檔
  # - id: rule.coding-standards
  #   ref: docs/coding-standards.md
  #   required: true
  # - id: rule.api-guidelines
  #   ref: docs/api-guidelines.md
  #   required: true
```

## 技術文件

```yaml
docs:
  # TODO: 請 Claude 掃描專案後填入
  # 常見文件類型：PRD, ARCHITECTURE, API, README, CHANGELOG 等
```

## 主要程式碼

```yaml
code:
  # TODO: 請 Claude 掃描專案後填入
  # 指向主要入口點、核心模組、資料模型等
```
'''

    try:
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(index_template)
        print(f"✅ 已建立專案 SSOT: {index_path}")
        print("   請編輯此檔案，用 ref 指向專案內的文檔")
    except Exception as e:
        print(f"❌ 無法建立 INDEX.md: {e}")


def ask_sync_code_graph(auto_confirm=False):
    """詢問是否同步當前專案的 Code Graph

    Args:
        auto_confirm: True 時自動確認，不詢問（供非互動模式使用）
    """
    print("\n" + "=" * 50)

    cwd = os.getcwd()

    if not auto_confirm:
        response = input("是否要同步當前專案的 Code Graph？(y/n): ").strip().lower()
        if response != 'y':
            print("跳過。之後可執行 `cortex sync` 同步")
            return
    else:
        print("自動同步 Code Graph...")

    print("📊 同步 Code Graph...")
    try:
        # 動態載入 facade 模組
        base_dir = os.path.expanduser('~/.claude/skills/cortex-agents')
        sys.path.insert(0, base_dir)
        from servers.facade import sync

        result = sync(cwd)
        if result.get('status') == 'success':
            stats = result.get('stats', {})
            print(f"✅ Code Graph 同步完成")
            print(f"   節點: {stats.get('nodes', 0)}, 邊: {stats.get('edges', 0)}")
        else:
            print(f"⚠️  同步完成但有警告: {result.get('message', '')}")
    except Exception as e:
        print(f"❌ 同步失敗: {e}")
        print("   請確認專案結構正確，之後可執行 `cortex sync` 重試")


def upgrade_database(db_path, schema_path):
    """升級資料庫：補齊缺失的 table（不影響現有資料）

    使用 CREATE TABLE IF NOT EXISTS，所以只會建立缺失的 table，
    不會影響現有資料。
    """
    if not os.path.exists(schema_path):
        print(f"⚠️  找不到 schema: {schema_path}")
        return

    db = sqlite3.connect(db_path)
    cursor = db.cursor()

    # 取得現有 table 清單
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cursor.fetchall()}

    # 執行 schema（CREATE TABLE IF NOT EXISTS 不會重建現有 table）
    with open(schema_path) as f:
        try:
            cursor.executescript(f.read())
        except sqlite3.OperationalError as e:
            # 忽略 trigger 已存在的錯誤
            if "already exists" not in str(e):
                raise

    # 取得新的 table 清單
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    new_tables = {row[0] for row in cursor.fetchall()}

    # 計算新增的 table
    added_tables = new_tables - existing_tables
    if added_tables:
        print(f"   📦 已補齊 {len(added_tables)} 個 table: {', '.join(sorted(added_tables))}")
    else:
        print("   （Schema 已是最新版）")

    db.commit()
    db.close()


def init_database(db_path, schema_path):
    """初始化 SQLite 資料庫"""
    print(f"📦 初始化資料庫: {db_path}")

    db = sqlite3.connect(db_path)
    cursor = db.cursor()

    # 執行 schema
    if os.path.exists(schema_path):
        with open(schema_path) as f:
            cursor.executescript(f.read())
        print("✅ Schema 已載入")
    else:
        print(f"❌ 找不到 schema: {schema_path}")
        return

    # 插入初始記憶
    cursor.execute('''
        INSERT INTO long_term_memory (category, title, content, importance)
        VALUES ('knowledge', 'System Initialized',
                'Cortex Multi-Agent System 已初始化。包含 PFC, Executor, Critic, Memory, Researcher 五個 agent。',
                10)
    ''')

    db.commit()
    db.close()
    print("✅ 資料庫初始化完成")

def reset_database():
    """強制重置資料庫（謹慎使用）"""
    base_dir = os.path.expanduser('~/.claude/skills/cortex-agents')
    brain_dir = os.path.join(base_dir, 'brain')
    db_path = os.path.join(brain_dir, 'brain.db')
    schema_path = os.path.join(brain_dir, 'schema.sql')

    print("⚠️  警告：這會清空所有跨專案記憶！")
    response = input("確定要重置嗎？輸入 'RESET' 確認: ")
    if response == 'RESET':
        if os.path.exists(db_path):
            os.remove(db_path)
        init_database(db_path, schema_path)
        print("✅ 資料庫已重置")
    else:
        print("取消重置")

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Cortex System 安裝腳本')
    parser.add_argument('--reset', action='store_true', help='重置資料庫（需手動確認，無法非互動）')
    parser.add_argument('--add-claude-md', action='store_true', help='自動加入 CLAUDE.md 設定')
    parser.add_argument('--init-ssot', action='store_true', help='自動初始化專案 SSOT INDEX')
    parser.add_argument('--sync-graph', action='store_true', help='自動同步 Code Graph')
    parser.add_argument('--all', action='store_true', help='執行所有可選設定（不含 reset）')
    parser.add_argument('--skip-prompts', action='store_true', help='跳過所有互動詢問（僅執行核心安裝）')

    args = parser.parse_args()

    if args.reset:
        # reset 永遠需要手動確認，保護資料安全
        reset_database()
    else:
        base_dir = install()

        # 判斷執行模式
        if args.skip_prompts:
            # 跳過所有後續詢問
            print("\n（使用 --skip-prompts，跳過可選設定）")
        elif args.all or args.add_claude_md or args.init_ssot or args.sync_graph:
            # 有指定參數，按參數執行（非互動）
            if args.all:
                args.add_claude_md = args.init_ssot = args.sync_graph = True

            if args.add_claude_md:
                ask_add_to_claude_md(base_dir, auto_confirm=True)
            if args.init_ssot:
                ask_init_project_ssot(base_dir, auto_confirm=True)
            if args.sync_graph:
                ask_sync_code_graph(auto_confirm=True)
        else:
            # 無參數時維持原本的互動詢問
            ask_add_to_claude_md(base_dir)
            ask_init_project_ssot(base_dir)
            ask_sync_code_graph()

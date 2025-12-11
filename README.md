# PFC Agents

Neuroscience-inspired multi-agent system for Claude Code.

## 安裝

```bash
git clone git@github.com:Stanley-1013/pfc-agents.git ~/.claude/neuromorphic
python3 ~/.claude/neuromorphic/scripts/install.py
```

## 系統需求

- Python 3.8+
- Claude Code CLI

安裝腳本會：
1. 檢查系統依賴（Python 版本、sqlite3 模組、目錄權限）
2. 複製 agent 定義到 `~/.claude/agents/`
3. 初始化 SQLite 資料庫（不覆蓋現有資料）

> 跨專案記憶會保留，安裝不會清空既有知識。

## 在專案中啟用

將以下內容加到專案的 CLAUDE.md：

```markdown
## Neuromorphic Multi-Agent 系統

> **本專案使用 Neuromorphic Multi-Agent 系統進行任務管理**
>
> 完整協作指南：`~/.claude/neuromorphic/SYSTEM_GUIDE.md`

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
| Drift Detector | `drift-detector` | 偏差偵測 |

### 系統入口（供 Agent 使用）

```python
import sys
import os
sys.path.insert(0, os.path.expanduser('~/.claude/neuromorphic'))

# 核心 API（推薦使用 Facade）
from servers.facade import (
    get_full_context,        # 三層查詢（SSOT + Code + Memory）
    validate_with_graph,     # Graph 增強驗證
    check_drift,             # SSOT-Code 偏差檢查
    sync_ssot_graph          # 同步 SSOT Index 到 Graph
)

# 傳統 API（仍可使用）
from servers.tasks import get_task_progress, create_task
from servers.memory import search_memory, load_checkpoint
from servers.drift import detect_all_drifts, get_drift_summary
```

### 使用方式

對 Claude Code 說：「使用 pfc agent 規劃 [任務描述]」
```

## 使用

對 Claude Code 說：
```
使用 pfc agent 規劃為所有 API 寫單元測試
```

PFC 會分析任務、分解為子任務、詢問確認、自動執行。

## 文檔

- **[SYSTEM_GUIDE.md](./SYSTEM_GUIDE.md)** - 完整協作指南
- **[AGENT_SELECTOR.md](./AGENT_SELECTOR.md)** - Agent 選擇指南

## 系統架構

```
┌─────────────────────────────────────────────────┐
│              Claude Code 主體                    │
│            （透過 Task tool 派發）                │
└──────────────────┬──────────────────────────────┘
                   │
     ┌─────────────┼─────────────┬─────────────┐
     ↓             ↓             ↓             ↓
┌─────────┐  ┌──────────┐  ┌─────────┐  ┌──────────┐
│   PFC   │  │ Executor │  │ Critic  │  │ Memory   │
│  規劃者  │  │  執行者   │  │  驗證者  │  │ 記憶管理 │
└────┬────┘  └────┬─────┘  └────┬────┘  └────┬─────┘
     │            │             │            │
     └────────────┴─────────────┴────────────┘
                        ↓
                 ┌─────────────┐
                 │   SQLite    │
                 │  brain.db   │
                 └─────────────┘
```

**執行流程**：
1. PFC 規劃任務、分解子任務、決定由誰執行
2. Executor 執行各子任務
3. Critic 驗證結果
4. Memory 儲存經驗

## Agents

| Agent | subagent_type | 職責 | 特點 |
|-------|---------------|------|------|
| **PFC** | `pfc` | 任務規劃、分解、協調 | 決定子任務由誰執行 |
| **Executor** | `executor` | 執行單一任務 | 完成即結束，context 清空 |
| **Critic** | `critic` | 驗證結果品質 | 紅隊驗證 + Graph 增強 |
| **Memory** | `memory` | 記憶管理 | 知識存取 |
| **Researcher** | `researcher` | 資訊收集 | 深度研究 |
| **Drift Detector** | `drift-detector` | SSOT-Code 偏差偵測 | 任務前檢查一致性 |

## 記憶系統

- **tasks**: 任務狀態與依賴
- **working_memory**: 短期共享變數
- **long_term_memory**: 持久化知識
- **checkpoints**: Micro-Nap 狀態
- **episodes**: 情節記憶
- **memory_fts**: FTS5 全文搜尋

## 目錄結構

```
~/.claude/neuromorphic/
├── agents/          # Agent 定義 (會複製到 ~/.claude/agents/)
│   ├── pfc.md
│   ├── executor.md
│   ├── critic.md
│   ├── memory.md
│   ├── researcher.md
│   └── drift-detector.md  # SSOT-Code 偏差偵測
├── brain/
│   ├── brain.db     # SQLite 資料庫
│   └── schema.sql   # Schema 定義
├── servers/         # 工具庫
│   ├── facade.py    # 統一入口 ⭐（三層查詢、增強驗證）
│   ├── drift.py     # SSOT-Code 偏差偵測
│   ├── graph.py     # SSOT Graph 操作
│   ├── ssot.py      # SSOT 文檔加載
│   ├── code_graph.py # Code Graph 操作
│   ├── registry.py  # 類型註冊表
│   ├── memory.py    # 記憶操作
│   └── tasks.py     # 任務操作
├── scripts/
│   ├── install.py   # 系統安裝
│   └── init_project.py  # 專案初始化
└── README.md
```

## 核心功能

### Code Execution 範式
Executor 遵循：
- 寫程式碼處理資料，不直接印大量輸出
- 只回傳摘要
- 結果存資料庫

### 跨專案記憶
所有專案共用同一個 brain.db，知識可跨專案使用。安裝腳本不會覆蓋現有資料庫。

## 驗證安裝

確認系統功能正常：

```bash
python ~/.claude/neuromorphic/scripts/verify_stories.py
```

## 重置資料庫（謹慎）

```bash
python ~/.claude/neuromorphic/scripts/install.py --reset
```

需要輸入 'RESET' 確認，會清空所有記憶。

## License

MIT

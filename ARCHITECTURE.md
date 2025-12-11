# Neuromorphic 架構總覽

> **維護者必讀**：理解系統設計理念，確保修改不破壞整體架構。

## 核心概念

### 三層真相架構 (Three-Layer Truth)

```
┌─────────────────────────────────────────────────────────────┐
│                     SSOT Layer (Intent)                      │
│                      「應該怎樣」                             │
├─────────────────────────────────────────────────────────────┤
│  - PROJECT_DOCTRINE.md (核心原則)                            │
│  - PROJECT_INDEX.md (L1 目錄)                                │
│  - flows/*.md (Flow 規格)                                    │
│  - domains/*.md (Domain 規格)                                │
│                                                             │
│  Tables: project_nodes, project_edges                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Code Graph Layer (Reality)                 │
│                      「實際怎樣」                             │
├─────────────────────────────────────────────────────────────┤
│  - 從 AST 解析的程式碼結構                                   │
│  - file, class, function, interface...                      │
│  - imports, calls, extends, implements...                   │
│                                                             │
│  Tables: code_nodes, code_edges, file_hashes                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Tests Layer (Evidence)                    │
│                      「證明怎樣」                             │
├─────────────────────────────────────────────────────────────┤
│  - 測試結果                                                  │
│  - 覆蓋率報告                                                │
│  - E2E 測試狀態                                              │
└─────────────────────────────────────────────────────────────┘
```

### 衝突處理原則

| 情境 | 處理方式 |
|------|----------|
| SSOT 說 X，Code 做 Y | 標記為「實作偏差」→ 人類決策 |
| Code 有 X，SSOT 沒記載 | 標記為「未文檔化功能」→ 補文檔 |
| SSOT 說 X，Test 失敗 | 標記為「破壞承諾」→ 高優先修復 |
| Code + Test 一致，SSOT 不同 | SSOT 過時 → 更新文檔 |

---

## 資料流向

```
git pull
    │
    ▼
[post-merge hook]
    │
    ▼
[Code Graph Extractor]  ───────────────────────┐
    │                                          │
    │  tree-sitter AST 解析                    │
    │  TypeScript, Python, Go...               │
    │                                          │
    ▼                                          ▼
[Incremental Update Engine]           [SSOT Loader]
    │                                          │
    │  git diff 找變更檔案                     │
    │  hash 比對避免重複                       │
    │                                          │
    ▼                                          ▼
┌─────────────────────────────────────────────────┐
│              Local brain.db                      │
├─────────────────────────────────────────────────┤
│  code_nodes, code_edges    ← Reality Layer      │
│  project_nodes, project_edges ← SSOT Layer      │
│  long_term_memory, working_memory ← Memory      │
│  node_kind_registry, edge_kind_registry ← Types │
└─────────────────────────────────────────────────┘
    │
    ▼
[Agent APIs]
    │
    ├── PFC: 規劃任務，選擇 Branch
    ├── Executor: 執行任務
    └── Critic: 驗證結果
```

---

## 設計原則

### 1. 類型可擴展 (Open-Closed Principle)

**問題**：Node/Edge 類型不應寫死在程式碼中。

**解法**：使用 Registry 表。

```python
# 新增類型只需 INSERT，不改程式碼
from servers.registry import register_node_kind

register_node_kind(
    kind='component',
    display_name='元件',
    description='React/Vue 元件'
)
```

**相關檔案**：
- `brain/schema.sql` - `node_kind_registry`, `edge_kind_registry`
- `servers/registry.py` - API 實現

### 2. 黑箱化複雜度 (Facade Pattern)

**問題**：使用者/Agent 不需要理解系統內部。

**解法**：提供統一入口 `servers/facade.py`。

```python
# 使用者只需要這些 API
from servers.facade import sync, status, get_context, check_drift

# 不需要直接 import 低階模組
# ❌ from servers.code_graph import sync_from_directory
```

### 3. 錯誤訊息可行動

**問題**：錯誤訊息不能只說「出錯了」，要告訴使用者怎麼修。

```python
# ❌ 不好
raise Exception("node not found")

# ✅ 好
raise NodeNotFoundError(
    f"Node '{node_id}' not found.\n\n"
    f"Did you run 'neuromorphic sync' after git pull?\n"
)
```

### 4. 銜接可驗證

**問題**：各模組間的銜接容易出錯。

**解法**：`cli/doctor.py` 診斷所有銜接點。

```bash
python cli/doctor.py

# 檢查項目：
# - Database 連接
# - Type Registry 初始化
# - SSOT 檔案存在
# - Server 模組載入
# - Code Extractor 可用
# - Git Hooks 安裝
```

---

## 模組職責

| 模組 | 職責 | 依賴 |
|------|------|------|
| `servers/facade.py` | 統一入口，三層查詢，增強驗證 | 所有 servers |
| `servers/drift.py` | SSOT-Code 偏差偵測 | ssot, code_graph, graph |
| `servers/registry.py` | 類型註冊，驗證 | 無 |
| `servers/code_graph.py` | Code Graph 操作，增量更新 | registry, extractor |
| `servers/graph.py` | SSOT Graph 操作 | 無 |
| `servers/ssot.py` | SSOT 文檔載入 | 無 |
| `servers/memory.py` | 記憶操作 | 無 |
| `servers/tasks.py` | 任務管理 | 無 |
| `tools/code_graph_extractor/` | AST 解析 | 無 |
| `cli/doctor.py` | 系統診斷 | 所有 servers |

---

## 如何新增功能

### 新增 Node 類型

1. 在 `registry.py` 的 `DEFAULT_NODE_KINDS` 新增（或直接呼叫 API）
2. 完成

```python
# 方式 1：修改預設列表
DEFAULT_NODE_KINDS.append(
    ('component', '元件', 'React/Vue 元件', '🧩', '#42A5F5', 'ast')
)

# 方式 2：動態註冊
register_node_kind('component', '元件', 'React/Vue 元件')
```

### 新增 Edge 類型

同上，修改 `DEFAULT_EDGE_KINDS` 或呼叫 `register_edge_kind()`。

### 新增語言支援

1. 在 `tools/code_graph_extractor/extractor.py` 新增：
   - `SUPPORTED_EXTENSIONS` 映射
   - `RegexExtractor.extract_{language}()` 方法

2. （可選）整合 Tree-sitter 語言綁定以提高準確度。

### 新增 Agent

1. 在 `agents/` 新增 `.md` 檔案
2. 遵循現有 agent 格式（YAML frontmatter + Markdown）
3. 使用 `servers/` API 與系統互動

---

## 目錄結構

```
~/.claude/neuromorphic/
├── ARCHITECTURE.md          # 本文檔
├── agents/                  # Agent 定義
│   ├── pfc.md              # 規劃者（三層查詢）
│   ├── executor.md         # 執行者
│   ├── critic.md           # 驗證者（Graph 增強）
│   ├── researcher.md       # 研究者
│   ├── memory.md           # 記憶管理
│   └── drift-detector.md   # 偏差偵測
├── brain/
│   ├── brain.db            # SQLite 資料庫
│   ├── schema.sql          # 資料庫 Schema
│   └── ssot/               # SSOT 文檔
│       ├── PROJECT_DOCTRINE.md
│       ├── PROJECT_INDEX.md
│       ├── flows/
│       └── domains/
├── servers/                 # 服務層
│   ├── facade.py           # 統一入口 ⭐（三層查詢、增強驗證）
│   ├── drift.py            # SSOT-Code 偏差偵測
│   ├── registry.py         # 類型註冊
│   ├── code_graph.py       # Code Graph
│   ├── graph.py            # SSOT Graph
│   ├── ssot.py             # SSOT 載入
│   ├── memory.py           # 記憶操作
│   └── tasks.py            # 任務管理
├── tools/
│   └── code_graph_extractor/  # AST 提取工具
│       ├── __init__.py
│       └── extractor.py
├── cli/                     # 命令列工具
│   ├── __init__.py
│   └── doctor.py           # 系統診斷
└── scripts/                 # 輔助腳本
```

---

## 常見問題

### Q: 為什麼不用中央資料庫？

**A**: Git 本身已是去中心化同步的成熟解決方案。每個人 `git pull` 後在本地建構 Code Graph，結果一致且無需額外基礎設施。

### Q: 為什麼 Code Graph 和 SSOT Graph 分開？

**A**: 它們代表不同的真相層：
- SSOT = 意圖（應該怎樣）
- Code Graph = 現實（實際怎樣）

分開存放可以偵測「實作偏差」。

### Q: 為什麼用 Regex 而不是 Tree-sitter？

**A**: 目前用 Regex 作為 fallback，無需額外依賴。Tree-sitter 整合是未來增強項目，可提供更準確的解析。

### Q: 記憶會同步嗎？

**A**: 不會。`long_term_memory` 和 `working_memory` 是個人的，永不同步。這保護隱私並避免衝突。

---

## Facade API（統一入口）

```python
from servers.facade import (
    # === PFC 三層查詢（Story 15）===
    get_full_context,        # 取得完整三層 context（SSOT + Code + Memory）
    format_context_for_agent, # 格式化為 Agent 可讀的 Markdown

    # === Critic 增強驗證（Story 16）===
    validate_with_graph,     # 使用 Graph 做增強驗證
    format_validation_report, # 格式化驗證報告

    # === Drift 偵測（Story 17）===
    check_drift,             # 檢查 SSOT-Code 偏差

    # === SSOT Graph 同步 ===
    sync_ssot_graph          # 同步 SSOT Index 到 Graph
)
```

---

## 版本歷史

| 版本 | 日期 | 說明 |
|------|------|------|
| 2.1.0 | 2025-01 | Stories 15-17: 三層查詢、增強驗證、Drift 偵測 |
| 2.0.0 | 2024-12 | Stories 1-14: 基礎架構、Code Graph、Agents |
| 1.0.0 | 2024-11 | 初版：Attention Tree 概念驗證 |

### Stories 完成對照表

<details>
<summary>展開查看所有 Stories</summary>

| Story | 功能 | 實作位置 |
|-------|------|----------|
| **Phase 1: 基礎架構** | | |
| S01 | SSOT Schema | `brain/schema.sql` |
| S02 | Graph Server | `servers/graph.py` |
| S03 | SSOT Index 載入 | `servers/ssot.py` |
| S04 | Type Registry | `servers/registry.py` |
| S05 | Memory Server | `servers/memory.py` |
| S06 | Task Queue | `servers/tasks.py` |
| **Phase 2: Code Graph** | | |
| S07 | Extractor 架構 | `tools/code_graph_extractor/` |
| S08 | AST 解析 | `extractor.py` (TS/Py/Go) |
| S09 | Code Graph Server | `servers/code_graph.py` |
| **Phase 3: Agents** | | |
| S10 | PFC Agent | `agents/pfc.md` |
| S11 | Executor Agent | `agents/executor.md` |
| S12 | Critic Agent | `agents/critic.md` |
| **Phase 4: Integration** | | |
| S13 | CLI 入口 | `cli/main.py` |
| S14 | Facade API | `servers/facade.py` |
| **Phase 5: 進階功能** | | |
| S15 | PFC 三層查詢 | `facade.get_full_context()` |
| S16 | Critic Graph 增強 | `facade.validate_with_graph()` |
| S17 | Drift Detector | `servers/drift.py`, `agents/drift-detector.md` |

</details>

### 驗證

```bash
python scripts/verify_stories.py        # 完整驗證
python scripts/verify_stories.py -s 15  # 只驗證 Story 15
```

---

## 維護者守則

1. **不要直接修改 Schema 中的類型列表**，使用 Registry API
2. **新功能先寫診斷**，確保 `doctor.py` 能檢測問題
3. **錯誤訊息必須可行動**，告訴使用者怎麼修
4. **保持 Facade 層簡潔**，複雜度藏在實作層
5. **文檔與程式碼同步更新**，避免 SSOT 偏差

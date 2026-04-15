# HAN 架構總覽

> **維護者必讀**：理解系統設計理念，確保修改不破壞整體架構。

## 核心概念

### 三層真相架構 (Three-Layer Truth)

```
┌─────────────────────────────────────────────────────────────┐
│                     SSOT Layer (Intent)                      │
│                      「應該怎樣」                             │
├─────────────────────────────────────────────────────────────┤
│  - SKILL.md (Skill 入口，按 Heading 分段組織連結)            │
│  - reference/*.md (參考文檔)                                 │
│  - 其他連結的 Markdown 文檔                                  │
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
    f"Did you run 'han sync' after git pull?\n"
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

### 5. Agent vs Script 職責分離

**問題**：腳本不應做語義判斷，那是 Agent 的工作。

**解法**：腳本只提供結構化資料，Agent 做智慧分析。

```python
# ✅ Script 職責：提供資料
def get_drift_context(project, project_dir) -> Dict:
    """提供 SKILL.md 內容、連結列表、Code Graph 節點等結構化資料"""
    return {
        'skill_content': str,      # 完整 SKILL.md 內容
        'skill_links': {...},      # parse_skill_links() 結果
        'code_nodes': [...],       # Code Graph 節點
        'code_files': [...],       # 檔案節點
        'code_stats': {...},       # 統計資訊
    }

# ✅ Agent 職責：語義分析
# Drift Agent 接收 get_drift_context() 資料
# 判斷文檔描述 vs 實際程式碼的語義偏差
# 產出可行動的偏差報告
```

**相關檔案**：
- `servers/drift.py` - `get_drift_context()` 提供資料
- `reference/agents/drift-detector.md` - Agent 做語義分析

---

## 模組職責

| 模組 | 職責 | 依賴 |
|------|------|------|
| `servers/facade.py` | 統一入口，三層查詢，增強驗證 | 所有 servers |
| `servers/drift.py` | 提供 Drift 分析資料（`get_drift_context()`），基本存在性檢查 | ssot, code_graph, graph |
| `servers/registry.py` | 類型註冊，驗證 | 無 |
| `servers/code_graph.py` | Code Graph 操作，增量更新 | registry, extractor |
| `servers/graph.py` | SSOT Graph 操作 | 無 |
| `servers/ssot.py` | SKILL.md 解析（動態分段，無硬編碼分類） | 無 |
| `servers/memory.py` | 記憶操作 | 無 |
| `servers/tasks.py` | 任務管理 | 無 |
| `tools/code_graph_extractor/` | AST 解析（Tree-sitter + regex fallback） | 無 |
| `tools/code_graph_extractor/backends/` | Parser backend 抽象層 + registry | extractor |
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

**推薦方式（Tree-sitter）：**

1. 安裝語言 grammar: `pip install tree-sitter-{language}`
2. 在 `backends/tree_sitter_backend.py` 新增：
   - `_load_grammar()` loader mapping
   - `LanguageQueryPack` 定義（AST node types + extraction hooks）
   - 加入 `QUERY_PACKS` registry
3. 在 `extractor.py` 的 `SUPPORTED_EXTENSIONS` 新增映射

**Fallback 方式（Regex）：**

1. 在 `extractor.py` 新增 `RegexExtractor.extract_{language}()` 方法
2. 在 `backends/regex_backend.py` 的 `_EXTRACTORS` dict 新增映射

### 新增 Agent

1. 在 `agents/` 新增 `.md` 檔案
2. 遵循現有 agent 格式（YAML frontmatter + Markdown）
3. 使用 `servers/` API 與系統互動

---

## 目錄結構

```
~/.claude/han/                # Skill 根目錄
├── SKILL.md                 # Skill 入口（按 Heading 組織連結）
├── reference/               # 參考文檔
│   ├── ARCHITECTURE.md      # 本文檔
│   ├── API_REFERENCE.md     # API 參考
│   ├── WORKFLOW_GUIDE.md    # 工作流指南
│   ├── MEMORY_GUIDE.md      # 記憶管理指南
│   ├── GRAPH_GUIDE.md       # Graph 使用指南
│   ├── TROUBLESHOOTING.md   # 問題排解
│   └── agents/              # Agent 定義
│       ├── pfc.md           # 規劃者（三層查詢）
│       ├── executor.md      # 執行者
│       ├── critic.md        # 驗證者（Graph 增強）
│       ├── researcher.md    # 研究者
│       ├── memory.md        # 記憶管理
│       └── drift-detector.md # 偏差偵測（語義分析）
├── brain/
│   ├── brain.db             # SQLite 資料庫
│   └── schema.sql           # 資料庫 Schema
├── servers/                 # 服務層
│   ├── facade.py            # 統一入口 ⭐（三層查詢、增強驗證）
│   ├── drift.py             # Drift 資料提供（get_drift_context）
│   ├── registry.py          # 類型註冊
│   ├── code_graph.py        # Code Graph
│   ├── graph.py             # SSOT Graph
│   ├── ssot.py              # SKILL.md 解析
│   ├── memory.py            # 記憶操作
│   └── tasks.py             # 任務管理
├── tools/
│   └── code_graph_extractor/  # AST 提取工具
│       ├── __init__.py
│       ├── extractor.py         # Core extraction + RegexExtractor
│       └── backends/            # Parser backend 抽象層
│           ├── __init__.py      # ExtractorBackend protocol + registry
│           ├── regex_backend.py # Regex fallback backend
│           └── tree_sitter_backend.py  # Tree-sitter AST backend
├── cli/                     # 命令列工具
│   ├── __init__.py
│   └── doctor.py            # 系統診斷
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

## 團隊協作指南

本系統設計支援從**個人開發**平滑演進到**團隊協作**，無需更換基礎設施。

### 個人模式 vs 團隊模式

| 資料層 | 個人模式 | 團隊模式 | 說明 |
|--------|---------|---------|------|
| **SSOT** (Markdown) | 本地編輯 | Git 同步 + PR 審核 | 唯一需要同步的層 |
| **Code Graph** | 本地建構 | 各自建構 | 確定性：同樣程式碼 → 同樣 Graph |
| **Memory** (brain.db) | 個人資料庫 | 個人資料庫 | **永不同步**，保護隱私 |
| **Task Queue** | 個人任務 | 可選共享 | 視團隊需求而定 |

### 資料同步策略

#### 同步層（團隊共享，Git 版控）

```
project-root/
├── SKILL.md              # Skill 入口（或 .claude/skills/<name>/SKILL.md）
└── reference/            # 參考文檔
    ├── ARCHITECTURE.md
    └── ...
```

**為什麼這些同步？** 它們定義「專案應該怎樣」，是團隊共識的源頭。

#### 隔離層（個人私有，不同步）

```
brain/brain.db            # 包含：
├── long_term_memory      # 個人學習、偏好
├── working_memory        # 當前工作狀態
└── task_queue            # 個人任務（除非選擇共享）
```

**為什麼隔離？**
1. **隱私保護**：學習紀錄可能包含敏感資訊
2. **避免衝突**：每人的工作記憶會頻繁變動
3. **簡化架構**：無需處理複雜的資料庫合併

### 衝突處理原則

| 類型 | 處理方式 | 理由 |
|------|----------|------|
| SSOT 衝突 | Git merge + 人工審核 | 意圖變更需要人類決策 |
| Code Graph 衝突 | 不存在 | 各自從程式碼重建，確定性 |
| Memory 衝突 | 不存在 | 個人隔離 |

### 團隊擴展路徑

#### 1️⃣ 個人開發 (1 人)

```
你的機器
├── <han-agents>/brain/brain.db     # 你的記憶
└── ~/your-project/brain/ssot/                # 本地 SSOT
```

- 所有資料在本地
- 無需任何同步設定

#### 2️⃣ 小團隊 (2-5 人)

```
Git Repository (共享)
└── brain/ssot/           # SSOT 由 Git 管理

每個人的機器
└── <han-agents>/brain/brain.db     # 各自的記憶
```

**關鍵實踐：**
- SSOT 變更需 PR 審核
- 定期執行 `check_drift()` 偵測偏差
- 記憶不跨人同步，但可導出分享（如最佳實踐）

#### 3️⃣ 大團隊 (5+ 人)

```
Git Repository (共享)
└── SKILL.md              # 頂層 Skill 入口
    └── reference/        # 按模組拆分文檔
        ├── auth/
        ├── payment/
        └── user/

可選：共享 Task Server
└── 團隊任務看板（需額外建設）
```

**關鍵實踐：**
- 文檔按模組拆分，減少合併衝突
- 考慮設置共享 Task Server（超出本系統範圍）
- 建立 SSOT 變更的自動 Critic 驗證

### 設計決策記錄 (ADR)

| ID | 決策 | 理由 |
|----|------|------|
| ADR-001 | 記憶不同步 | 保護隱私、避免複雜合併邏輯 |
| ADR-002 | Code Graph 本地建構 | 確定性、無需共享基礎設施 |
| ADR-003 | SSOT 用 Git 同步 | 成熟方案、版本追溯、PR 審核 |
| ADR-004 | SQLite 而非中央 DB | 零配置、離線可用、跨專案共享 |
| ADR-005 | SKILL.md 動態分段 | 不硬編碼目錄分類，由 Heading 自然組織 |
| ADR-006 | Agent vs Script 分離 | 腳本提供資料、Agent 做語義判斷 |

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
    check_drift,             # 基本存在性檢查
    get_drift_context,       # 取得 Drift 分析資料（供 Agent 語義分析）

    # === SSOT Graph 同步 ===
    sync_skill_graph         # 同步 SKILL.md 連結到 Graph
)
```

### Drift 分析架構

```
┌─────────────────────────────────────────────────────────────┐
│                     get_drift_context()                      │
│                  (servers/drift.py)                          │
├─────────────────────────────────────────────────────────────┤
│  提供結構化資料：                                            │
│  - skill_content: SKILL.md 完整內容                         │
│  - skill_links: parse_skill_links() 結果（連結 + 分段）     │
│  - code_nodes: Code Graph 所有節點                          │
│  - code_files: 檔案節點列表                                  │
│  - code_stats: 統計資訊                                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Drift Agent                              │
│              (reference/agents/drift-detector.md)            │
├─────────────────────────────────────────────────────────────┤
│  語義分析：                                                  │
│  - 判斷文檔描述 vs 實際程式碼的語義偏差                      │
│  - 識別未文檔化的重要功能                                    │
│  - 識別文檔描述但未實作的功能                                │
│  - 產出可行動的偏差報告                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 版本歷史

| 版本 | 日期 | 說明 |
|------|------|------|
| 3.0.0 | 2026-01 | 轉型為 Skill 架構，SKILL.md 動態分段，Agent vs Script 分離 |
| 2.1.0 | 2025-12 | Stories 15-17: 三層查詢、增強驗證、Drift 偵測 |
| 2.0.0 | 2025-12 | Stories 1-14: 基礎架構、Code Graph、Agents |
| 1.0.0 | 2025-11 | 初版：Attention Tree 概念驗證 |

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

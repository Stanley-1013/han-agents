# Project Index (L1) - Neuromorphic

> **導航圖**：INDEX 是專案的導航地圖，使用 `ref` 指向現有文檔，不複製內容。
>
> - `ref` 可指向文檔檔案（如 `docs/PRD.md`）或程式碼檔案（如 `servers/auth.py`）
> - 系統會透過 `ref` 自動載入對應內容
> - 維護簡單：文檔更新時無需同步 INDEX

---

## Flows

> 業務流程定義

```yaml
flows:
  - id: flow.code-graph-sync
    name: Code Graph Sync
    description: 從源碼同步 Code Graph 到資料庫
    ref: servers/code_graph.py

  - id: flow.ssot-management
    name: SSOT Management
    description: 管理 Doctrine、Index、Spec 文件
    ref: servers/ssot.py

  - id: flow.drift-detection
    name: Drift Detection
    description: 偵測 SSOT 與 Code 之間的偏差
    ref: servers/drift.py

  - id: flow.memory-search
    name: Memory Search
    description: 記憶存儲與搜尋功能
    ref: servers/memory.py

  - id: flow.graph-query
    name: Graph Query
    description: 查詢節點鄰居、影響範圍、熱點分析
    ref: servers/graph.py
```

---

## Domains

> 業務領域/模組

```yaml
domains:
  - id: domain.code-graph
    name: Code Graph
    description: 程式碼結構圖（nodes, edges, 依賴分析）
    ref: servers/code_graph.py

  - id: domain.ssot
    name: SSOT
    description: 單一真相來源（Doctrine, Index, Specs）
    ref: servers/ssot.py

  - id: domain.memory
    name: Memory
    description: 記憶系統（working, long-term, episodes）
    ref: servers/memory.py

  - id: domain.registry
    name: Registry
    description: 類型註冊表（node kinds, edge kinds）
    ref: servers/registry.py

  - id: domain.tasks
    name: Tasks
    description: 任務管理（lifecycle, checkpoints）
    ref: servers/tasks.py
```

---

## APIs

> 主要 API 入口

```yaml
apis:
  - id: api.facade.sync
    name: sync()
    description: 同步專案 Code Graph
    flow: flow.code-graph-sync
    domain: domain.code-graph
    ref: servers/facade.py

  - id: api.facade.status
    name: status()
    description: 取得專案狀態總覽
    flow: flow.code-graph-sync
    domain: domain.code-graph
    ref: servers/facade.py

  - id: api.facade.check-drift
    name: check_drift()
    description: 檢查 SSOT-Code 偏差
    flow: flow.drift-detection
    domain: domain.ssot
    ref: servers/facade.py

  - id: api.facade.get-context
    name: get_context()
    description: 取得 Branch 完整 context
    flow: flow.ssot-management
    domain: domain.ssot
    ref: servers/facade.py

  - id: api.graph.get-neighbors
    name: get_neighbors()
    description: 查詢節點鄰居
    flow: flow.graph-query
    domain: domain.code-graph
    ref: servers/graph.py

  - id: api.memory.search
    name: search_memory()
    description: 搜尋記憶
    flow: flow.memory-search
    domain: domain.memory
    ref: servers/memory.py

  - id: api.facade.get-full-context
    name: get_full_context()
    description: 取得 Branch 完整三層 context（SSOT + Code + Memory）
    flow: flow.ssot-management
    domain: domain.ssot
    ref: servers/facade.py

  - id: api.facade.validate-with-graph
    name: validate_with_graph()
    description: 使用 Graph 做增強驗證（影響分析、SSOT符合性、測試覆蓋）
    flow: flow.drift-detection
    domain: domain.code-graph
    ref: servers/facade.py

  - id: api.facade.sync-ssot-graph
    name: sync_ssot_graph()
    description: 同步 SSOT Index 到 Graph
    flow: flow.ssot-management
    domain: domain.ssot
    ref: servers/facade.py
```

---

## CLI Commands

> 命令列介面

```yaml
commands:
  - id: cmd.doctor
    name: neuromorphic doctor
    description: 系統診斷
    ref: cli/doctor.py

  - id: cmd.sync
    name: neuromorphic sync
    description: 同步 Code Graph
    flow: flow.code-graph-sync
    ref: cli/main.py

  - id: cmd.status
    name: neuromorphic status
    description: 顯示專案狀態
    ref: cli/main.py

  - id: cmd.drift
    name: neuromorphic drift
    description: 檢查 SSOT-Code 偏差
    flow: flow.drift-detection
    ref: cli/main.py

  - id: cmd.ssot-sync
    name: neuromorphic ssot-sync
    description: 同步 SSOT Index 到 Graph
    flow: flow.ssot-management
    ref: cli/main.py

  - id: cmd.graph
    name: neuromorphic graph
    description: 查詢 SSOT Graph（列表、鄰居、影響分析）
    flow: flow.graph-query
    ref: cli/main.py

  - id: cmd.dashboard
    name: neuromorphic dashboard
    description: 顯示完整系統儀表板
    ref: cli/main.py
```

---

## Agents

> AI Agent 定義

```yaml
agents:
  - id: agent.pfc
    name: PFC Agent
    description: 前額葉皮質 - 任務規劃與分解
    ref: agents/pfc.md

  - id: agent.executor
    name: Executor Agent
    description: 執行單一原子任務
    ref: agents/executor.md

  - id: agent.critic
    name: Critic Agent
    description: 紅隊驗證專家 - 風險評估與品質檢查
    ref: agents/critic.md

  - id: agent.researcher
    name: Researcher Agent
    description: 研究與資料收集專家
    ref: agents/researcher.md

  - id: agent.memory
    name: Memory Agent
    description: 記憶管理專家 - 儲存學習、檢索知識
    ref: agents/memory.md

  - id: agent.drift-detector
    name: Drift Detector Agent
    description: SSOT-Code 偏差偵測器
    flow: flow.drift-detection
    ref: agents/drift-detector.md
```

---

## Tools

> 獨立工具

```yaml
tools:
  - id: tool.extractor
    name: Code Graph Extractor
    description: 使用 Regex/AST 提取程式碼結構
    ref: tools/code_graph_extractor/extractor.py
    domain: domain.code-graph
```

---

## Tests

> 測試文件

```yaml
tests:
  - id: test.graph
    name: Graph Server Tests
    description: 測試 graph.py 功能
    covers: [flow.graph-query, domain.code-graph]
    ref: servers/graph.py

  - id: test.ssot
    name: SSOT Server Tests
    description: 測試 ssot.py 功能
    covers: [flow.ssot-management, domain.ssot]
    ref: servers/ssot.py
```

---

## 維護說明

### 導航圖設計原則

**INDEX 是「地圖」，不是「內容庫」**：
- ✅ 使用 `ref` 指向現有文檔（PRD、SA、SD、TDD 等）
- ✅ 文檔更新時，無需同步 INDEX
- ❌ 不要將文檔內容複製到 INDEX 中

### 添加新項目

1. **使用 `[type].[name]` 格式作為 id**
2. **確保 id 全局唯一**
3. **用 `ref` 指向實際檔案**

```yaml
# 範例：新增一個 Flow
flows:
  - id: flow.checkout
    name: 結帳流程
    description: 購物車結帳流程
    ref: docs/flows/checkout.md  # 指向現有文檔
```

### Node ID 命名規則

| 前綴 | 用途 | 範例 |
|------|------|------|
| `flow.xxx` | 業務流程 | `flow.auth`, `flow.payment` |
| `domain.xxx` | 業務領域 | `domain.user`, `domain.order` |
| `api.xxx.yyy` | API 端點 | `api.auth.login` |
| `doc.xxx` | 文檔 | `doc.prd`, `doc.sa` |
| `cmd.xxx` | CLI 命令 | `cmd.sync` |
| `tool.xxx` | 獨立工具 | `tool.extractor` |
| `test.xxx` | 測試文件 | `test.auth` |

### 關係說明

| 關係 | 說明 |
|------|------|
| `flow -> domain` | 流程使用領域 (uses) |
| `api -> flow` | API 實現流程 (implements) |
| `test -> flow/domain` | 測試覆蓋 (covers) |
| `doc -> flow` | 文檔描述流程 (describes) |

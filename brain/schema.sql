-- =============================================================================
-- HAN BRAIN DATABASE SCHEMA
-- Version: 2.0.0 (Phase 2: Multi-person Collaboration)
-- =============================================================================

-- 任務管理
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    parent_id TEXT,
    project TEXT,
    description TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 5,
    assigned_agent TEXT,
    result TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    -- 任務生命週期欄位
    phase TEXT DEFAULT 'execution',  -- execution, validation, documentation, completed
    requires_validation INTEGER DEFAULT 1,  -- 0=不需要, 1=需要驗證
    validation_status TEXT,  -- pending, approved, rejected, skipped
    validator_task_id TEXT,  -- 關聯的 critic 驗證任務 ID
    -- Hierarchy 欄位（Epic → Story → Task → Bug）
    task_level TEXT,         -- epic | story | task | bug
    epic_id TEXT,            -- 所屬 Epic ID
    story_id TEXT,           -- 所屬 Story ID
    executor_agent_id TEXT,  -- 執行者 agent id（resume 用）
    rejection_count INTEGER DEFAULT 0,
    -- Branch 關聯（Story 4: PFC Branch 選擇機制）
    metadata TEXT,  -- JSON: {"branch": {"flow_id": "flow.auth", "domain_ids": ["domain.user"]}}
    -- 時間戳記
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES tasks(id),
    FOREIGN KEY (validator_task_id) REFERENCES tasks(id)
);

-- 任務依賴
CREATE TABLE IF NOT EXISTS task_dependencies (
    task_id TEXT,
    depends_on_task_id TEXT,
    PRIMARY KEY (task_id, depends_on_task_id),
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (depends_on_task_id) REFERENCES tasks(id)
);

-- 工作記憶
CREATE TABLE IF NOT EXISTS working_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    project TEXT,
    key TEXT NOT NULL,
    value TEXT,
    data_type TEXT DEFAULT 'string',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- 長期記憶
CREATE TABLE IF NOT EXISTS long_term_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    subcategory TEXT,
    project TEXT,
    title TEXT,
    content TEXT NOT NULL,
    importance INTEGER DEFAULT 5,
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active',
    superseded_by INTEGER REFERENCES long_term_memory(id),
    last_validated TIMESTAMP,
    -- Branch 關聯欄位（Story 2: Memory 查詢增強）
    branch_flow TEXT,      -- 關聯的 Flow ID，如 'flow.auth'
    branch_domain TEXT,    -- 關聯的 Domain ID，如 'domain.user'
    branch_page TEXT       -- 關聯的 Page ID，如 'page.login'
);

-- 情節記憶
CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT,
    session_id TEXT,
    event_type TEXT,
    summary TEXT NOT NULL,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Checkpoint
CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT,
    task_id TEXT,
    agent TEXT,
    state TEXT NOT NULL,
    context_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- Agent 日誌
CREATE TABLE IF NOT EXISTS agent_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT NOT NULL,
    task_id TEXT,
    action TEXT,
    message TEXT,
    duration_ms INTEGER,
    tokens_used INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- FTS5 全文搜尋
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    content,
    category,
    project
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project);
CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_id);
CREATE INDEX IF NOT EXISTS idx_tasks_parent_status ON tasks(parent_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_parent_status_priority ON tasks(parent_id, status, priority DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_parent_agent_status ON tasks(parent_id, assigned_agent, status);
CREATE INDEX IF NOT EXISTS idx_tasks_epic ON tasks(epic_id);
CREATE INDEX IF NOT EXISTS idx_tasks_story ON tasks(story_id);
CREATE INDEX IF NOT EXISTS idx_working_memory_task ON working_memory(task_id);
CREATE INDEX IF NOT EXISTS idx_working_memory_key ON working_memory(key);
CREATE INDEX IF NOT EXISTS idx_long_term_category ON long_term_memory(category);
CREATE INDEX IF NOT EXISTS idx_long_term_status ON long_term_memory(status);
CREATE INDEX IF NOT EXISTS idx_episodes_project ON episodes(project);
-- Branch 索引（Story 2: Memory 查詢增強）
CREATE INDEX IF NOT EXISTS idx_ltm_branch_flow ON long_term_memory(branch_flow);
CREATE INDEX IF NOT EXISTS idx_ltm_branch_domain ON long_term_memory(branch_domain);

-- 複合索引（常用查詢加速）
CREATE INDEX IF NOT EXISTS idx_tasks_project_status ON tasks(project, status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_ltm_category_project ON long_term_memory(category, project);

-- =============================================================================
-- Graph Overlay（Story 3: 輕量圖結構）
-- =============================================================================

-- Node: 專案裡的重要點（來自 L1 Index）
CREATE TABLE IF NOT EXISTS project_nodes (
    id TEXT NOT NULL,                -- e.g. 'flow.checkout', 'domain.order'
    project TEXT NOT NULL,
    kind TEXT NOT NULL,              -- 'flow'|'domain'|'api'|'page'|'file'|'test'
    name TEXT NOT NULL,
    ref TEXT,                        -- 例如 'flows/checkout.md'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, project)
);

-- Edge: 點與點之間的關係
CREATE TABLE IF NOT EXISTS project_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT NOT NULL,
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    kind TEXT NOT NULL,              -- 'uses'|'implements'|'calls'|'covers'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project, from_id, to_id, kind)
);

CREATE INDEX IF NOT EXISTS idx_edges_from ON project_edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON project_edges(to_id);
CREATE INDEX IF NOT EXISTS idx_edges_project ON project_edges(project);
CREATE INDEX IF NOT EXISTS idx_nodes_project ON project_nodes(project);
CREATE INDEX IF NOT EXISTS idx_nodes_kind ON project_nodes(kind);

-- =============================================================================
-- Task Node Access Tracking（Story 7: 熱點分析）
-- =============================================================================

-- 記錄任務執行過程中訪問的節點
CREATE TABLE IF NOT EXISTS task_node_access (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT NOT NULL,
    task_id TEXT,                    -- 關聯的任務 ID
    node_id TEXT NOT NULL,           -- 訪問的節點 ID
    agent TEXT NOT NULL,             -- 訪問的 agent（pfc, executor, critic）
    access_type TEXT DEFAULT 'read', -- 'read'|'write'|'validate'
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE INDEX IF NOT EXISTS idx_node_access_project ON task_node_access(project);
CREATE INDEX IF NOT EXISTS idx_node_access_node ON task_node_access(node_id);
CREATE INDEX IF NOT EXISTS idx_node_access_time ON task_node_access(accessed_at);

-- =============================================================================
-- Type Registry（Story 8: 可擴展類型設計）
-- =============================================================================
-- 設計原則：Open-Closed Principle
-- 新增類型只需 INSERT，不需改任何程式碼

-- Node 類型註冊表
CREATE TABLE IF NOT EXISTS node_kind_registry (
    kind TEXT PRIMARY KEY,              -- e.g. 'file', 'function', 'api'
    display_name TEXT NOT NULL,         -- UI 顯示名稱
    description TEXT,                   -- 說明
    icon TEXT,                          -- UI 圖示（可選）
    color TEXT,                         -- UI 顏色（可選）
    extractor TEXT,                     -- 負責提取的模組（可選）
    is_builtin INTEGER DEFAULT 0,       -- 1=內建, 0=使用者新增
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Edge 類型註冊表
CREATE TABLE IF NOT EXISTS edge_kind_registry (
    kind TEXT PRIMARY KEY,              -- e.g. 'imports', 'calls', 'implements'
    display_name TEXT NOT NULL,         -- UI 顯示名稱
    description TEXT,                   -- 說明
    source_kinds TEXT,                  -- JSON: 允許的 from_node kinds ["file", "function"]
    target_kinds TEXT,                  -- JSON: 允許的 to_node kinds ["file", "module"]
    is_directional INTEGER DEFAULT 1,   -- 1=有向, 0=無向
    is_builtin INTEGER DEFAULT 0,       -- 1=內建, 0=使用者新增
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- Code Graph（Story 9: 擴展 Graph Schema）
-- =============================================================================
-- 用途：從 AST 提取的程式碼結構圖（Reality Layer）
-- 與 project_nodes/edges（SSOT Layer）分開

-- Code Graph 節點（從 AST 解析）
CREATE TABLE IF NOT EXISTS code_nodes (
    id TEXT NOT NULL,                    -- e.g. 'func.validateToken'
    project TEXT NOT NULL,
    kind TEXT NOT NULL,                  -- 參照 node_kind_registry.kind
    name TEXT NOT NULL,
    signature TEXT,                      -- 函式簽名、類別定義
    file_path TEXT,                      -- 源碼位置
    line_start INTEGER,
    line_end INTEGER,
    language TEXT,                       -- 'typescript', 'python', 'go'
    visibility TEXT,                     -- 'public', 'private', 'protected'
    hash TEXT,                           -- 內容 hash（變更偵測）
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, project)
);

-- Code Graph 邊（從 AST 解析）
CREATE TABLE IF NOT EXISTS code_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT NOT NULL,
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    kind TEXT NOT NULL,                  -- 參照 edge_kind_registry.kind
    line_number INTEGER,                 -- 關係發生位置
    confidence REAL DEFAULT 1.0,         -- 推論關係的信心度
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project, from_id, to_id, kind)
);

-- 檔案 hash 追蹤（增量更新用）
CREATE TABLE IF NOT EXISTS file_hashes (
    project TEXT NOT NULL,
    file_path TEXT NOT NULL,
    hash TEXT NOT NULL,
    node_count INTEGER DEFAULT 0,        -- 此檔案產出的 node 數
    edge_count INTEGER DEFAULT 0,        -- 此檔案產出的 edge 數
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project, file_path)
);

-- Code Graph 索引
CREATE INDEX IF NOT EXISTS idx_code_nodes_project ON code_nodes(project);
CREATE INDEX IF NOT EXISTS idx_code_nodes_kind ON code_nodes(kind);
CREATE INDEX IF NOT EXISTS idx_code_nodes_file ON code_nodes(file_path);
CREATE INDEX IF NOT EXISTS idx_code_nodes_project_file ON code_nodes(project, file_path);
CREATE INDEX IF NOT EXISTS idx_code_edges_project ON code_edges(project);
CREATE INDEX IF NOT EXISTS idx_code_edges_from ON code_edges(from_id);
CREATE INDEX IF NOT EXISTS idx_code_edges_to ON code_edges(to_id);
CREATE INDEX IF NOT EXISTS idx_code_edges_project_from_kind ON code_edges(project, from_id, kind);
CREATE INDEX IF NOT EXISTS idx_code_edges_project_to_kind ON code_edges(project, to_id, kind);
CREATE INDEX IF NOT EXISTS idx_file_hashes_project ON file_hashes(project);

-- FTS 觸發器
CREATE TRIGGER IF NOT EXISTS ltm_ai AFTER INSERT ON long_term_memory BEGIN
    INSERT INTO memory_fts(rowid, content, category, project)
    VALUES (NEW.id, NEW.content, NEW.category, NEW.project);
END;

CREATE TRIGGER IF NOT EXISTS ltm_ad AFTER DELETE ON long_term_memory BEGIN
    DELETE FROM memory_fts WHERE rowid = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS ltm_au AFTER UPDATE ON long_term_memory BEGIN
    DELETE FROM memory_fts WHERE rowid = OLD.id;
    INSERT INTO memory_fts(rowid, content, category, project)
    VALUES (NEW.id, NEW.content, NEW.category, NEW.project);
END;

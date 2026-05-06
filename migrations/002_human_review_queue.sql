CREATE TABLE IF NOT EXISTS human_review_queue (
    id TEXT PRIMARY KEY,
    project TEXT,
    kind TEXT NOT NULL,
    severity TEXT DEFAULT 'medium',
    status TEXT DEFAULT 'open',
    reason TEXT NOT NULL,
    task_id TEXT,
    trace_id TEXT,
    span_id TEXT,
    payload TEXT,
    reviewer TEXT,
    resolution TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (trace_id) REFERENCES agent_traces(id),
    FOREIGN KEY (span_id) REFERENCES agent_spans(id)
);

CREATE INDEX IF NOT EXISTS idx_human_review_status ON human_review_queue(status);
CREATE INDEX IF NOT EXISTS idx_human_review_project ON human_review_queue(project);
CREATE INDEX IF NOT EXISTS idx_human_review_task ON human_review_queue(task_id);
CREATE INDEX IF NOT EXISTS idx_human_review_trace ON human_review_queue(trace_id);

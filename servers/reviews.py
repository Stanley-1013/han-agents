"""
Human review queue for HAN harness operations.

The queue turns blocked tasks, guardrail violations, and low-confidence
decisions into durable records that can be reviewed and resolved later.
"""

import json
import uuid
from typing import Any, Dict, List

from servers import managed_connection


SCHEMA = """
=== Reviews API ===

create_review_item(kind, reason, project=None, severity='medium',
                   task_id=None, trace_id=None, span_id=None, payload=None) -> str
    Create or reuse an open review item and return its id.

list_review_items(status='open', project=None, limit=20) -> List[Dict]
    List review queue items.

resolve_review_item(item_id, reviewer, resolution, notes=None) -> Dict
    Mark a review item resolved.

enqueue_trace_reviews(trace_id) -> Dict
    Create review items from warning/error spans in a trace.
"""


def _id() -> str:
    return f"review_{uuid.uuid4().hex}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _load(value: str) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def _row_to_item(row) -> Dict:
    item = dict(row)
    item["payload"] = _load(item.get("payload"))
    return item


def create_review_item(
    kind: str,
    reason: str,
    project: str = None,
    severity: str = "medium",
    task_id: str = None,
    trace_id: str = None,
    span_id: str = None,
    payload: Any = None,
) -> str:
    """Create or reuse an open review item for the same target."""
    with managed_connection(row_factory=True) as db:
        existing = db.execute(
            """
            SELECT id FROM human_review_queue
            WHERE status = 'open'
              AND kind = ?
              AND COALESCE(task_id, '') = COALESCE(?, '')
              AND COALESCE(trace_id, '') = COALESCE(?, '')
              AND COALESCE(span_id, '') = COALESCE(?, '')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (kind, task_id, trace_id, span_id),
        ).fetchone()
        if existing:
            return existing["id"]

        item_id = _id()
        db.execute(
            """
            INSERT INTO human_review_queue
            (id, project, kind, severity, status, reason, task_id, trace_id,
             span_id, payload)
            VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                project,
                kind,
                severity,
                reason,
                task_id,
                trace_id,
                span_id,
                _json(payload),
            ),
        )
        db.commit()
    return item_id


def list_review_items(
    status: str = "open",
    project: str = None,
    limit: int = 20,
) -> List[Dict]:
    """List review items by status and optional project."""
    where = []
    params: List[Any] = []
    if status and status != "all":
        where.append("status = ?")
        params.append(status)
    if project:
        where.append("project = ?")
        params.append(project)
    params.append(limit)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    with managed_connection(row_factory=True) as db:
        rows = db.execute(
            f"""
            SELECT * FROM human_review_queue
            {where_sql}
            ORDER BY
                CASE severity
                    WHEN 'critical' THEN 0
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    ELSE 3
                END,
                created_at DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
    return [_row_to_item(row) for row in rows]


def get_review_item(item_id: str) -> Dict:
    """Return one review item."""
    with managed_connection(row_factory=True) as db:
        row = db.execute(
            "SELECT * FROM human_review_queue WHERE id = ?",
            (item_id,),
        ).fetchone()
    return _row_to_item(row) if row else {}


def resolve_review_item(
    item_id: str,
    reviewer: str,
    resolution: str,
    notes: str = None,
) -> Dict:
    """Mark a review item resolved."""
    existing = get_review_item(item_id)
    payload = existing.get("payload") if existing else None
    if notes:
        if isinstance(payload, dict):
            payload = {**payload, "resolution_notes": notes}
        else:
            payload = {"previous_payload": payload, "resolution_notes": notes}
    with managed_connection() as db:
        db.execute(
            """
            UPDATE human_review_queue
            SET status = 'resolved',
                reviewer = ?,
                resolution = ?,
                payload = COALESCE(?, payload),
                resolved_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (reviewer, resolution, _json(payload) if payload is not None else None, item_id),
        )
        db.commit()
    return get_review_item(item_id)


def enqueue_trace_reviews(trace_id: str) -> Dict:
    """Create review items for warning/error spans in a trace."""
    from servers.tracing import get_trace

    trace = get_trace(trace_id)
    if not trace:
        raise ValueError(f"trace not found: {trace_id}")

    created = []
    for span in trace.get("spans", []):
        status = span.get("status")
        span_type = span.get("span_type")
        if status not in ("warning", "error"):
            continue
        severity = "high" if status == "error" else "medium"
        output = span.get("output") or {}
        violations = output.get("violations") or []
        reason = (
            "; ".join(v.get("message", "") for v in violations if v.get("message"))
            or span.get("error")
            or f"{span_type} span ended with status={status}"
        )
        item_id = create_review_item(
            kind=span_type or "trace_span",
            reason=str(reason),
            project=trace.get("project"),
            severity=severity,
            task_id=span.get("task_id"),
            trace_id=trace_id,
            span_id=span.get("id"),
            payload={"span": span},
        )
        created.append(item_id)

    return {
        "trace_id": trace_id,
        "created_count": len(created),
        "review_ids": created,
    }


__all__ = [
    "SCHEMA",
    "create_review_item",
    "list_review_items",
    "get_review_item",
    "resolve_review_item",
    "enqueue_trace_reviews",
]

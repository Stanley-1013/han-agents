"""
Local tracing primitives for HAN agent workflows.

This module intentionally stays provider-neutral. It records traces and spans in
SQLite so local runs can be replayed, evaluated, or exported to an external
observability system later.
"""

import json
import uuid
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from servers import managed_connection


SCHEMA = """
=== Tracing API ===

start_trace(workflow_name, project=None, group_id=None, metadata=None) -> str
    Create a trace for one end-to-end agent workflow.

finish_trace(trace_id, status='completed', metadata=None) -> Dict
    Mark a trace finished.

start_span(trace_id, name, span_type, parent_span_id=None, task_id=None,
           input=None, metadata=None) -> str
    Create a child operation span, such as dispatch, tool_call, validation.

finish_span(span_id, status='completed', output=None, error=None,
            metadata=None) -> Dict
    Mark a span finished and store output/error data.

get_trace(trace_id) -> Dict
    Return trace metadata plus ordered spans.

summarize_trace(trace_id) -> Dict
    Return counts by span type/status and guardrail violations.

list_guardrail_events(project=None, limit=20, only_violations=True) -> List[Dict]
    List recent guardrail spans across traces.

export_traces_jsonl(path, trace_id=None, project=None, limit=100) -> int
    Export trace/span events as newline-delimited JSON.

export_traces_otel_jsonl(path, trace_id=None, project=None, limit=100) -> int
    Export spans as OpenTelemetry-style JSONL records.
"""


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _json(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _load(value: Optional[str]) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def start_trace(
    workflow_name: str,
    project: str = None,
    group_id: str = None,
    metadata: Dict = None,
) -> str:
    """Create a local trace and return its id."""
    trace_id = _id("trace")
    with managed_connection() as db:
        db.execute(
            """
            INSERT INTO agent_traces
            (id, workflow_name, project, group_id, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (trace_id, workflow_name, project, group_id, _json(metadata)),
        )
        db.commit()
    return trace_id


def finish_trace(
    trace_id: str,
    status: str = "completed",
    metadata: Dict = None,
) -> Dict:
    """Finish a trace and return the updated trace."""
    with managed_connection() as db:
        db.execute(
            """
            UPDATE agent_traces
            SET status = ?,
                metadata = COALESCE(?, metadata),
                ended_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, _json(metadata), trace_id),
        )
        db.commit()
    return get_trace(trace_id)


def start_span(
    trace_id: str,
    name: str,
    span_type: str,
    parent_span_id: str = None,
    task_id: str = None,
    input: Any = None,
    metadata: Dict = None,
) -> str:
    """Create a span inside a trace and return its id."""
    span_id = _id("span")
    with managed_connection() as db:
        db.execute(
            """
            INSERT INTO agent_spans
            (id, trace_id, parent_span_id, task_id, name, span_type, input, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                span_id,
                trace_id,
                parent_span_id,
                task_id,
                name,
                span_type,
                _json(input),
                _json(metadata),
            ),
        )
        db.commit()
    return span_id


def finish_span(
    span_id: str,
    status: str = "completed",
    output: Any = None,
    error: Any = None,
    metadata: Dict = None,
) -> Dict:
    """Finish a span and return the updated span."""
    with managed_connection() as db:
        db.execute(
            """
            UPDATE agent_spans
            SET status = ?,
                output = COALESCE(?, output),
                error = COALESCE(?, error),
                metadata = COALESCE(?, metadata),
                ended_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, _json(output), _json(error), _json(metadata), span_id),
        )
        db.commit()
    return get_span(span_id)


@contextmanager
def span(
    trace_id: str,
    name: str,
    span_type: str,
    parent_span_id: str = None,
    task_id: str = None,
    input: Any = None,
    metadata: Dict = None,
):
    """Context manager that finishes spans as completed or errored."""
    span_id = start_span(
        trace_id,
        name,
        span_type,
        parent_span_id=parent_span_id,
        task_id=task_id,
        input=input,
        metadata=metadata,
    )
    try:
        yield span_id
    except Exception as exc:
        finish_span(span_id, status="error", error={"type": type(exc).__name__, "message": str(exc)})
        raise
    else:
        finish_span(span_id)


def get_span(span_id: str) -> Dict:
    """Return a single span."""
    with managed_connection(row_factory=True) as db:
        row = db.execute(
            "SELECT * FROM agent_spans WHERE id = ?",
            (span_id,),
        ).fetchone()
    if not row:
        return {}
    span_dict = dict(row)
    for key in ("input", "output", "metadata", "error"):
        span_dict[key] = _load(span_dict.get(key))
    return span_dict


def get_trace(trace_id: str) -> Dict:
    """Return trace metadata with ordered spans."""
    with managed_connection(row_factory=True) as db:
        trace_row = db.execute(
            "SELECT * FROM agent_traces WHERE id = ?",
            (trace_id,),
        ).fetchone()
        span_rows = db.execute(
            """
            SELECT * FROM agent_spans
            WHERE trace_id = ?
            ORDER BY started_at, id
            """,
            (trace_id,),
        ).fetchall()

    if not trace_row:
        return {}

    trace = dict(trace_row)
    trace["metadata"] = _load(trace.get("metadata"))
    spans: List[Dict] = []
    for row in span_rows:
        item = dict(row)
        for key in ("input", "output", "metadata", "error"):
            item[key] = _load(item.get(key))
        spans.append(item)
    trace["spans"] = spans
    return trace


def list_traces(project: str = None, limit: int = 20) -> List[Dict]:
    """List recent traces, optionally filtered by project."""
    with managed_connection(row_factory=True) as db:
        if project:
            rows = db.execute(
                """
                SELECT * FROM agent_traces
                WHERE project = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (project, limit),
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT * FROM agent_traces
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    traces = []
    for row in rows:
        item = dict(row)
        item["metadata"] = _load(item.get("metadata"))
        traces.append(item)
    return traces


def summarize_trace(trace_id: str) -> Dict:
    """Return compact trace health summary."""
    trace = get_trace(trace_id)
    if not trace:
        return {}

    by_type: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    guardrail_violations = 0
    for span_item in trace.get("spans", []):
        span_type = span_item.get("span_type") or "unknown"
        status = span_item.get("status") or "unknown"
        by_type[span_type] = by_type.get(span_type, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1
        if span_type == "guardrail":
            output = span_item.get("output") or {}
            if output.get("allowed") is False:
                guardrail_violations += 1

    return {
        "id": trace["id"],
        "workflow_name": trace["workflow_name"],
        "project": trace.get("project"),
        "status": trace.get("status"),
        "span_count": len(trace.get("spans", [])),
        "by_type": by_type,
        "by_status": by_status,
        "guardrail_violations": guardrail_violations,
        "started_at": trace.get("started_at"),
        "ended_at": trace.get("ended_at"),
    }


def list_guardrail_events(
    project: str = None,
    limit: int = 20,
    only_violations: bool = True,
) -> List[Dict]:
    """List recent guardrail spans, optionally filtered to policy violations."""
    where = ["s.span_type = 'guardrail'"]
    params: List = []
    if project:
        where.append("t.project = ?")
        params.append(project)
    if only_violations:
        where.append("s.status != 'completed'")
    params.append(limit)

    with managed_connection(row_factory=True) as db:
        rows = db.execute(
            f"""
            SELECT s.*, t.workflow_name, t.project
            FROM agent_spans s
            JOIN agent_traces t ON s.trace_id = t.id
            WHERE {' AND '.join(where)}
            ORDER BY s.started_at DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()

    events = []
    for row in rows:
        item = dict(row)
        for key in ("input", "output", "metadata", "error"):
            item[key] = _load(item.get(key))
        events.append(item)
    return events


def _trace_event_rows(trace: Dict) -> List[Dict]:
    events = [{
        "event_type": "trace",
        "trace_id": trace["id"],
        "workflow_name": trace.get("workflow_name"),
        "project": trace.get("project"),
        "group_id": trace.get("group_id"),
        "status": trace.get("status"),
        "started_at": trace.get("started_at"),
        "ended_at": trace.get("ended_at"),
        "metadata": trace.get("metadata"),
    }]
    for span_item in trace.get("spans", []):
        events.append({
            "event_type": "span",
            "trace_id": span_item.get("trace_id"),
            "span_id": span_item.get("id"),
            "parent_span_id": span_item.get("parent_span_id"),
            "task_id": span_item.get("task_id"),
            "name": span_item.get("name"),
            "span_type": span_item.get("span_type"),
            "status": span_item.get("status"),
            "started_at": span_item.get("started_at"),
            "ended_at": span_item.get("ended_at"),
            "input": span_item.get("input"),
            "output": span_item.get("output"),
            "metadata": span_item.get("metadata"),
            "error": span_item.get("error"),
        })
    return events


def export_traces_jsonl(
    path: str,
    trace_id: str = None,
    project: str = None,
    limit: int = 100,
) -> int:
    """Export trace and span events to JSONL. Returns event count."""
    traces = [get_trace(trace_id)] if trace_id else [
        get_trace(item["id"]) for item in list_traces(project=project, limit=limit)
    ]
    events = []
    for trace in traces:
        if trace:
            events.extend(_trace_event_rows(trace))

    with open(path, "w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, ensure_ascii=False, sort_keys=True, default=str))
            f.write("\n")
    return len(events)


def _otel_operation(span_type: str) -> str:
    if span_type == "dispatch":
        return "invoke_agent"
    if span_type in ("tool_call", "guardrail"):
        return "execute_tool"
    if span_type == "memory":
        return "retrieval"
    return "invoke_agent"


def _otel_status(status: str) -> Dict:
    if status == "error":
        return {"code": "ERROR"}
    if status == "warning":
        return {"code": "OK", "message": "warning"}
    return {"code": "OK"}


def trace_to_otel_events(trace: Dict) -> List[Dict]:
    """Convert one local trace into OpenTelemetry-style JSON records."""
    events = []
    resource = {
        "service.name": "han-agents",
        "service.namespace": "han",
    }
    for span_item in trace.get("spans", []):
        metadata = span_item.get("metadata") or {}
        output = span_item.get("output") or {}
        error = span_item.get("error")
        operation = _otel_operation(span_item.get("span_type"))
        attributes = {
            "gen_ai.operation.name": operation,
            "gen_ai.provider.name": "han",
            "han.workflow.name": trace.get("workflow_name"),
            "han.project": trace.get("project"),
            "han.span.type": span_item.get("span_type"),
            "han.span.status": span_item.get("status"),
        }
        agent = metadata.get("subagent_type") or output.get("subagent_type")
        if agent:
            attributes["gen_ai.agent.name"] = agent
        if span_item.get("task_id"):
            attributes["han.task.id"] = span_item.get("task_id")
        if error:
            if isinstance(error, dict):
                attributes["error.type"] = error.get("type") or "_OTHER"
            else:
                attributes["error.type"] = "_OTHER"

        events.append({
            "resource": resource,
            "scope": {
                "name": "han-agents",
                "version": "1.0.0",
            },
            "trace_id": trace.get("id"),
            "span_id": span_item.get("id"),
            "parent_span_id": span_item.get("parent_span_id"),
            "name": span_item.get("name"),
            "kind": "INTERNAL",
            "status": _otel_status(span_item.get("status")),
            "start_time": span_item.get("started_at"),
            "end_time": span_item.get("ended_at"),
            "attributes": attributes,
        })
    return events


def export_traces_otel_jsonl(
    path: str,
    trace_id: str = None,
    project: str = None,
    limit: int = 100,
) -> int:
    """Export OpenTelemetry-style span records as JSONL."""
    traces = [get_trace(trace_id)] if trace_id else [
        get_trace(item["id"]) for item in list_traces(project=project, limit=limit)
    ]
    events = []
    for trace in traces:
        if trace:
            events.extend(trace_to_otel_events(trace))

    with open(path, "w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, ensure_ascii=False, sort_keys=True, default=str))
            f.write("\n")
    return len(events)


__all__ = [
    "SCHEMA",
    "start_trace",
    "finish_trace",
    "start_span",
    "finish_span",
    "span",
    "get_span",
    "get_trace",
    "list_traces",
    "summarize_trace",
    "list_guardrail_events",
    "trace_to_otel_events",
    "export_traces_jsonl",
    "export_traces_otel_jsonl",
]

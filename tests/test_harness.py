"""
Tests for local harness tracing and deterministic eval helpers.
"""


def test_trace_round_trip(mock_db_path):
    from servers.tracing import (
        finish_span,
        finish_trace,
        get_trace,
        start_span,
        start_trace,
    )

    trace_id = start_trace(
        "unit-test workflow",
        project="test",
        group_id="thread-1",
        metadata={"recipe": "unit_tests"},
    )
    span_id = start_span(
        trace_id,
        "dispatch executor",
        "dispatch",
        task_id=None,
        input={"task_id": "task-1"},
        metadata={"subagent_type": "executor"},
    )
    finish_span(span_id, output={"subagent_type": "executor"})
    trace = finish_trace(trace_id)

    assert trace["id"] == trace_id
    assert trace["status"] == "completed"
    assert trace["metadata"] == {"recipe": "unit_tests"}
    assert len(trace["spans"]) == 1
    assert trace["spans"][0]["metadata"]["subagent_type"] == "executor"

    fetched = get_trace(trace_id)
    assert fetched["spans"][0]["output"]["subagent_type"] == "executor"


def test_evaluate_trajectory_exact_and_subsequence():
    from servers.evals import evaluate_trajectory

    exact = evaluate_trajectory(
        ["executor", "critic", "memory"],
        ["executor", "critic", "memory"],
    )
    assert exact["passed"] is True
    assert exact["score"] == 1.0

    subsequence = evaluate_trajectory(
        ["pfc", "executor", "critic", "memory"],
        ["executor", "memory"],
        mode="subsequence",
    )
    assert subsequence["passed"] is True
    assert subsequence["score"] == 1.0

    failed = evaluate_trajectory(
        [{"subagent_type": "executor"}, {"subagent_type": "memory"}],
        ["executor", "critic", "memory"],
    )
    assert failed["passed"] is False
    assert failed["score"] < 1.0


def test_builtin_trajectory_dataset_passes():
    from servers.evals import load_trajectory_dataset, run_trajectory_dataset

    cases = load_trajectory_dataset()
    assert len(cases) >= 3

    result = run_trajectory_dataset(dataset=cases)
    assert result["passed"] is True
    assert result["failed_count"] == 0


def test_extract_agents_from_trace(mock_db_path):
    from servers.evals import extract_agents_from_trace
    from servers.tracing import finish_span, get_trace, start_span, start_trace

    trace_id = start_trace("dispatch eval", project="test")
    span_id = start_span(
        trace_id,
        "dispatch",
        "dispatch",
        metadata={"subagent_type": "critic"},
    )
    finish_span(span_id)

    agents = extract_agents_from_trace(get_trace(trace_id))
    assert agents == ["critic"]


def test_evaluate_trace_helpers(mock_db_path, tmp_path):
    from servers.evals import evaluate_trace, evaluate_trace_jsonl
    from servers.tracing import export_traces_jsonl, finish_span, start_span, start_trace

    trace_id = start_trace("trace eval", project="test")
    span_id = start_span(
        trace_id,
        "dispatch executor",
        "dispatch",
        metadata={"subagent_type": "executor"},
    )
    finish_span(span_id, output={"subagent_type": "executor"})

    result = evaluate_trace(trace_id, ["executor"])
    assert result["passed"] is True
    assert result["trace_id"] == trace_id

    export_path = tmp_path / "trace-eval.jsonl"
    export_traces_jsonl(str(export_path), trace_id=trace_id)
    exported = evaluate_trace_jsonl(str(export_path), ["executor"], trace_id=trace_id)
    assert exported["passed"] is True
    assert exported["actual"] == ["executor"]


def test_trace_summary_and_guardrail_listing(mock_db_path):
    from servers.tracing import (
        finish_span,
        list_guardrail_events,
        start_span,
        start_trace,
        summarize_trace,
    )

    trace_id = start_trace("guardrail summary", project="test")
    span_id = start_span(trace_id, "guardrail:Bash", "guardrail")
    finish_span(
        span_id,
        status="warning",
        output={
            "allowed": False,
            "violations": [{"message": "Command matches denied pattern: rm -rf*"}],
        },
    )

    summary = summarize_trace(trace_id)
    assert summary["span_count"] == 1
    assert summary["by_type"] == {"guardrail": 1}
    assert summary["guardrail_violations"] == 1

    events = list_guardrail_events(project="test")
    assert len(events) == 1
    assert events[0]["trace_id"] == trace_id
    assert events[0]["output"]["allowed"] is False


def test_trace_jsonl_export(mock_db_path, tmp_path):
    import json

    from servers.tracing import export_traces_jsonl, finish_span, start_span, start_trace

    trace_id = start_trace("export trace", project="test")
    span_id = start_span(trace_id, "dispatch executor", "dispatch")
    finish_span(span_id, output={"subagent_type": "executor"})

    export_path = tmp_path / "traces.jsonl"
    count = export_traces_jsonl(str(export_path), trace_id=trace_id)

    lines = export_path.read_text(encoding="utf-8").splitlines()
    assert count == 2
    assert len(lines) == 2
    assert json.loads(lines[0])["event_type"] == "trace"
    assert json.loads(lines[1])["event_type"] == "span"


def test_trace_otel_jsonl_export(mock_db_path, tmp_path):
    import json

    from servers.tracing import export_traces_otel_jsonl, finish_span, start_span, start_trace

    trace_id = start_trace("otel trace", project="test")
    span_id = start_span(
        trace_id,
        "dispatch executor",
        "dispatch",
        metadata={"subagent_type": "executor"},
    )
    finish_span(span_id, output={"subagent_type": "executor"})

    export_path = tmp_path / "otel.jsonl"
    count = export_traces_otel_jsonl(str(export_path), trace_id=trace_id)

    lines = export_path.read_text(encoding="utf-8").splitlines()
    assert count == 1
    event = json.loads(lines[0])
    assert event["trace_id"] == trace_id
    assert event["attributes"]["gen_ai.operation.name"] == "invoke_agent"
    assert event["attributes"]["gen_ai.agent.name"] == "executor"


def test_trace_otel_jsonl_export_handles_string_error(mock_db_path, tmp_path):
    import json

    from servers.tracing import export_traces_otel_jsonl, finish_span, start_span, start_trace

    trace_id = start_trace("otel error trace", project="test")
    span_id = start_span(trace_id, "tool failed", "tool_call")
    finish_span(span_id, status="error", error="boom")

    export_path = tmp_path / "otel-error.jsonl"
    count = export_traces_otel_jsonl(str(export_path), trace_id=trace_id)

    lines = export_path.read_text(encoding="utf-8").splitlines()
    assert count == 1
    event = json.loads(lines[0])
    assert event["status"]["code"] == "ERROR"
    assert event["attributes"]["error.type"] == "_OTHER"


def test_dispatch_records_redacted_trace(mock_db_path):
    from servers.evals import evaluate_trajectory, extract_agents_from_trace
    from servers.facade import get_next_dispatch
    from servers.tasks import create_subtask, create_task
    from servers.tracing import get_trace, start_trace

    parent_id = create_task(
        project="test",
        description="Root workflow",
        task_level="story",
    )
    task_id = create_subtask(
        parent_id,
        "Write unit tests for servers/facade.py",
        assigned_agent="executor",
    )
    trace_id = start_trace("dispatch loop", project="test")

    decision = get_next_dispatch(
        parent_id,
        "test",
        "/tmp/project",
        trace_id=trace_id,
    )
    trace = get_trace(trace_id)

    assert decision["action"] == "dispatch"
    assert decision["subagent_type"] == "executor"
    assert decision["task_id"] == task_id
    assert decision["trace_id"] == trace_id

    assert len(trace["spans"]) == 1
    span = trace["spans"][0]
    assert span["span_type"] == "dispatch"
    assert span["metadata"]["subagent_type"] == "executor"
    assert span["output"]["prompt_redacted"] is True
    assert "prompt" not in span["output"]
    assert span["output"]["prompt_length"] > 0

    agents = extract_agents_from_trace(trace)
    result = evaluate_trajectory(agents, ["executor"])
    assert result["passed"] is True

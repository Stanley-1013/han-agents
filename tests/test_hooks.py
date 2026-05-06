"""
Tests for PostToolUse hook guardrail handling.
"""

import importlib.util
import os


def _load_post_task():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base_dir, "hooks", "post_task.py")
    spec = importlib.util.spec_from_file_location("post_task_hook", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_pre_tool():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base_dir, "hooks", "pre_tool.py")
    spec = importlib.util.spec_from_file_location("pre_tool_hook", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bash_guardrail_warning():
    hook = _load_post_task()

    output = hook.handle_event({
        "tool_name": "Bash",
        "tool_input": {
            "command": "rm -rf /tmp/project",
            "agent": "executor",
        },
    })

    assert output is not None
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "HAN guardrail warning" in context
    assert "denied pattern" in context
    assert "decision" not in output


def test_bash_guardrail_block_mode(monkeypatch):
    hook = _load_post_task()
    monkeypatch.setenv("HAN_GUARDRAIL_MODE", "block")

    output = hook.handle_event({
        "tool_name": "Bash",
        "tool_input": {
            "command": "rm -rf /tmp/project",
            "agent": "executor",
        },
    })

    assert output["decision"] == "block"
    assert output["guardrail"]["mode"] == "block"


def test_write_guardrail_warning_for_read_only_agent():
    hook = _load_post_task()

    output = hook.handle_event({
        "tool_name": "Write",
        "tool_input": {
            "file_path": "servers/facade.py",
            "agent": "critic",
        },
    })

    assert output is not None
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "cannot write path" in context


def test_allowed_bash_guardrail_is_silent():
    hook = _load_post_task()

    output = hook.handle_event({
        "tool_name": "Bash",
        "tool_input": {
            "command": "pytest -q tests/test_guardrails.py",
            "agent": "executor",
        },
    })

    assert output is None


def test_guardrail_event_records_trace_span(mock_db_path):
    hook = _load_post_task()

    from servers.tracing import get_trace, start_trace

    trace_id = start_trace("guardrail hook", project="test")
    output = hook.handle_event({
        "tool_name": "Bash",
        "tool_input": {
            "command": "rm -rf /tmp/project",
            "agent": "executor",
            "TRACE_ID": trace_id,
            "task_id": "task-1",
        },
    })
    trace = get_trace(trace_id)

    assert output is not None
    assert len(trace["spans"]) == 1
    span = trace["spans"][0]
    assert span["span_type"] == "guardrail"
    assert span["status"] == "warning"
    assert span["metadata"]["violation_count"] == 1
    assert span["output"]["allowed"] is False


def test_hook_cli_subprocess_guardrail_warning():
    import json
    import subprocess
    import sys

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": "rm -rf /tmp/project",
            "agent": "executor",
        },
    }
    result = subprocess.run(
        [sys.executable, "hooks/post_task.py"],
        cwd=base_dir,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "HAN guardrail warning for Bash" in result.stdout


def test_pre_tool_denies_in_block_mode(monkeypatch):
    hook = _load_pre_tool()
    monkeypatch.setenv("HAN_GUARDRAIL_MODE", "block")

    output = hook.handle_event({
        "tool_name": "Bash",
        "tool_input": {
            "command": "rm -rf /tmp/project",
            "agent": "executor",
        },
    })

    specific = output["hookSpecificOutput"]
    assert specific["hookEventName"] == "PreToolUse"
    assert specific["permissionDecision"] == "deny"
    assert "denied pattern" in specific["permissionDecisionReason"]


def test_pre_tool_asks_in_warn_mode(monkeypatch):
    hook = _load_pre_tool()
    monkeypatch.setenv("HAN_GUARDRAIL_MODE", "warn")

    output = hook.handle_event({
        "tool_name": "Write",
        "tool_input": {
            "file_path": "servers/facade.py",
            "agent": "critic",
        },
    })

    specific = output["hookSpecificOutput"]
    assert specific["permissionDecision"] == "ask"
    assert "cannot write path" in specific["permissionDecisionReason"]


def test_pre_tool_allows_silently():
    hook = _load_pre_tool()

    output = hook.handle_event({
        "tool_name": "Bash",
        "tool_input": {
            "command": "pytest -q tests/test_guardrails.py",
            "agent": "executor",
        },
    })

    assert output is None

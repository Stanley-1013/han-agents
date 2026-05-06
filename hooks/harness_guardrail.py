"""
Shared guardrail helpers for HAN hook scripts.
"""

import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, Optional

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BASE_DIR)

LOG_PATH = os.path.join(_BASE_DIR, "hooks", "hook.log")


def log(msg: str):
    """Write debug log, ignoring logging failures."""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


def extract_assignment(text: str, name: str) -> Optional[str]:
    match = re.search(rf'{name}\s*=\s*["\']([^"\']+)["\']', text or "")
    return match.group(1) if match else None


def trace_guardrail_check(
    trace_id: Optional[str],
    tool_name: str,
    check_result: Dict,
    task_id: str = None,
) -> None:
    if not trace_id:
        return
    try:
        from servers.tracing import finish_span, start_span

        span_id = start_span(
            trace_id,
            f"guardrail:{tool_name}",
            "guardrail",
            task_id=task_id,
            input={
                "tool_name": tool_name,
                "agent": check_result.get("agent"),
            },
            metadata={
                "allowed": check_result.get("allowed"),
                "violation_count": len(check_result.get("violations", [])),
            },
        )
        status = "completed" if check_result.get("allowed") else "warning"
        finish_span(span_id, status=status, output=check_result)
    except Exception as exc:
        log(f"guardrail trace failed: {type(exc).__name__}: {exc}")


def evaluate_tool_guardrail(input_data: Dict[str, Any]) -> Optional[Dict]:
    """Run the provider-neutral guardrail check for a hook payload."""
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input") or {}
    prompt = tool_input.get("prompt", "")
    agent = (
        tool_input.get("subagent_type")
        or tool_input.get("agent")
        or extract_assignment(prompt, "AGENT")
        or "executor"
    )
    trace_id = (
        tool_input.get("trace_id")
        or tool_input.get("TRACE_ID")
        or extract_assignment(prompt, "TRACE_ID")
    )
    task_id = tool_input.get("task_id") or extract_assignment(prompt, "TASK_ID")

    try:
        from servers.guardrails import check_command, check_path
    except Exception as exc:
        log(f"guardrails unavailable: {type(exc).__name__}: {exc}")
        return None

    if tool_name == "Bash":
        command = tool_input.get("command") or tool_input.get("cmd") or ""
        result = check_command(command, agent=agent)
    elif tool_name in ("Write", "Edit", "MultiEdit"):
        path = (
            tool_input.get("file_path")
            or tool_input.get("path")
            or tool_input.get("filename")
            or ""
        )
        result = check_path(path, agent=agent, operation="write")
    else:
        return None

    result["tool_name"] = tool_name
    result["trace_id"] = trace_id
    result["task_id"] = task_id
    trace_guardrail_check(trace_id, tool_name, result, task_id=task_id)
    return result


def violation_message(check_result: Dict) -> str:
    messages = [
        v.get("message", "")
        for v in check_result.get("violations", [])
        if v.get("message")
    ]
    return "; ".join(messages) or "Guardrail policy issue detected."

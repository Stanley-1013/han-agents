#!/usr/bin/env python3
"""
PreToolUse hook for HAN guardrail enforcement.

This hook uses Claude Code's structured PreToolUse output format. In block
mode, policy violations return permissionDecision=deny before the tool runs. In
warn mode, violations return permissionDecision=ask so a human can explicitly
confirm the risky action.
"""

import json
import os
import sys
from typing import Any, Dict, Optional

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BASE_DIR)

from hooks.harness_guardrail import evaluate_tool_guardrail, log, violation_message


def _pre_tool_output(decision: str, reason: str, check_result: Dict) -> Dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        },
        "guardrail": {
            "agent": check_result.get("agent"),
            "violations": check_result.get("violations", []),
        },
    }


def handle_event(input_data: Dict[str, Any]) -> Optional[Dict]:
    """Handle a PreToolUse event and return optional structured output."""
    result = evaluate_tool_guardrail(input_data)
    if result is None or result.get("allowed"):
        return None

    from servers.guardrails import enforce_result

    enforcement = enforce_result(result)
    reason = violation_message(result)
    if result.get("trace_id") or result.get("task_id"):
        try:
            from servers.reviews import create_review_item
            create_review_item(
                kind="guardrail",
                reason=reason,
                severity="high" if enforcement["action"] == "block" else "medium",
                task_id=result.get("task_id"),
                trace_id=result.get("trace_id"),
                payload=result,
            )
        except Exception as exc:
            log(f"guardrail review enqueue failed: {type(exc).__name__}: {exc}")
    if enforcement["action"] == "block":
        return _pre_tool_output("deny", reason, result)
    return _pre_tool_output("ask", reason, result)


def main() -> int:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    try:
        output = handle_event(input_data)
        if output:
            print(json.dumps(output, ensure_ascii=False))
    except Exception as exc:
        log(f"PRE_TOOL_ERROR: {str(exc)}")
        import traceback
        log(traceback.format_exc())
    return 0


if __name__ == "__main__":
    sys.exit(main())

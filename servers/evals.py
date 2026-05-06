"""
Deterministic evaluation helpers for HAN agent harness behavior.

These evaluators are deliberately small and dependency-free. They are meant to
run in CI before heavier LLM-as-judge or external observability integrations.
"""

import json
import os
from typing import Any, Dict, Iterable, List, Optional


SCHEMA = """
=== Evals API ===

evaluate_trajectory(actual, expected, mode='exact') -> Dict
    Score an agent/tool trajectory against an expected sequence.

extract_agents_from_trace(trace) -> List[str]
    Convert a local trace from servers.tracing.get_trace() into an agent sequence.

evaluate_trace(trace_id, expected, mode='exact') -> Dict
    Score a stored local trace against an expected agent sequence.

evaluate_trace_jsonl(path, expected, mode='exact', trace_id=None) -> Dict
    Score an exported JSONL trace file against an expected agent sequence.

load_trajectory_dataset(path=None) -> List[Dict]
    Load golden trajectory cases.

run_trajectory_dataset(path=None, dataset=None) -> Dict
    Evaluate every case and return aggregate pass/fail metrics.
"""


DEFAULT_TRAJECTORY_DATASET = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "evals",
    "trajectories.json",
)


def _event_name(event: Any) -> str:
    if isinstance(event, str):
        return event
    if isinstance(event, dict):
        for key in ("subagent_type", "agent", "span_type", "name", "tool"):
            value = event.get(key)
            if value:
                return str(value)
    return str(event)


def _normalize(events: Iterable[Any]) -> List[str]:
    return [_event_name(event) for event in events]


def _subsequence_matches(actual: List[str], expected: List[str]) -> List[Dict]:
    matches = []
    pos = 0
    for expected_index, expected_name in enumerate(expected):
        found_at = None
        while pos < len(actual):
            if actual[pos] == expected_name:
                found_at = pos
                pos += 1
                break
            pos += 1
        matches.append({
            "expected_index": expected_index,
            "expected": expected_name,
            "actual_index": found_at,
            "matched": found_at is not None,
        })
    return matches


def evaluate_trajectory(
    actual: Iterable[Any],
    expected: Iterable[Any],
    mode: str = "exact",
) -> Dict:
    """Score a trajectory with exact or subsequence matching."""
    actual_seq = _normalize(actual)
    expected_seq = _normalize(expected)

    if mode not in ("exact", "subsequence"):
        raise ValueError("mode must be 'exact' or 'subsequence'")

    if not expected_seq:
        return {
            "passed": len(actual_seq) == 0,
            "score": 1.0 if not actual_seq else 0.0,
            "mode": mode,
            "actual": actual_seq,
            "expected": expected_seq,
            "matches": [],
            "missing": [],
            "extra": actual_seq,
        }

    if mode == "exact":
        max_len = max(len(actual_seq), len(expected_seq))
        matches = []
        matched_count = 0
        for index in range(max_len):
            actual_name = actual_seq[index] if index < len(actual_seq) else None
            expected_name = expected_seq[index] if index < len(expected_seq) else None
            matched = actual_name == expected_name
            matched_count += 1 if matched else 0
            matches.append({
                "index": index,
                "expected": expected_name,
                "actual": actual_name,
                "matched": matched,
            })
        passed = actual_seq == expected_seq
        score = matched_count / max_len if max_len else 1.0
    else:
        matches = _subsequence_matches(actual_seq, expected_seq)
        matched_count = sum(1 for match in matches if match["matched"])
        passed = matched_count == len(expected_seq)
        score = matched_count / len(expected_seq)

    missing = [
        expected_seq[i]
        for i, match in enumerate(matches[:len(expected_seq)])
        if not match.get("matched")
    ]
    extra = actual_seq[len(expected_seq):] if mode == "exact" and len(actual_seq) > len(expected_seq) else []

    return {
        "passed": passed,
        "score": round(score, 4),
        "mode": mode,
        "actual": actual_seq,
        "expected": expected_seq,
        "matches": matches,
        "missing": missing,
        "extra": extra,
    }


def extract_agents_from_trace(trace: Dict) -> List[str]:
    """Extract dispatched agent names from a local trace."""
    agents = []
    for span in trace.get("spans", []):
        if span.get("span_type") != "dispatch":
            continue
        metadata = span.get("metadata") or {}
        output = span.get("output") or {}
        agent = (
            metadata.get("subagent_type")
            or output.get("subagent_type")
            or span.get("name")
        )
        if agent:
            agents.append(str(agent))
    return agents


def extract_agents_from_events(events: Iterable[Dict]) -> List[str]:
    """Extract dispatched agent names from exported trace/span events."""
    agents = []
    for event in events:
        if event.get("event_type") != "span" or event.get("span_type") != "dispatch":
            continue
        metadata = event.get("metadata") or {}
        output = event.get("output") or {}
        agent = (
            metadata.get("subagent_type")
            or output.get("subagent_type")
            or event.get("name")
        )
        if agent:
            agents.append(str(agent))
    return agents


def evaluate_trace(
    trace_id: str,
    expected: Iterable[Any],
    mode: str = "exact",
) -> Dict:
    """Evaluate a stored trace by its dispatch agent sequence."""
    from servers.tracing import get_trace

    trace = get_trace(trace_id)
    if not trace:
        raise ValueError(f"trace not found: {trace_id}")
    result = evaluate_trajectory(extract_agents_from_trace(trace), expected, mode=mode)
    result["trace_id"] = trace_id
    result["workflow_name"] = trace.get("workflow_name")
    return result


def load_jsonl_events(path: str, trace_id: str = None) -> List[Dict]:
    """Load exported trace/span JSONL events."""
    events = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            event = json.loads(line)
            if trace_id and event.get("trace_id") != trace_id:
                continue
            events.append(event)
    return events


def evaluate_trace_jsonl(
    path: str,
    expected: Iterable[Any],
    mode: str = "exact",
    trace_id: str = None,
) -> Dict:
    """Evaluate an exported trace JSONL file by dispatch agent sequence."""
    events = load_jsonl_events(path, trace_id=trace_id)
    if not events:
        raise ValueError("no matching trace events found")
    result = evaluate_trajectory(extract_agents_from_events(events), expected, mode=mode)
    result["trace_id"] = trace_id
    result["source"] = path
    return result


def load_trajectory_dataset(path: str = None) -> List[Dict]:
    """Load trajectory eval cases from JSON."""
    dataset_path = path or DEFAULT_TRAJECTORY_DATASET
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        cases = data.get("cases", [])
    else:
        cases = data
    if not isinstance(cases, list):
        raise ValueError("trajectory dataset must be a list or {'cases': [...]}")
    return cases


def run_trajectory_dataset(
    path: str = None,
    dataset: Optional[List[Dict]] = None,
) -> Dict:
    """Run deterministic trajectory evals for every case in a dataset."""
    cases = dataset if dataset is not None else load_trajectory_dataset(path)
    results = []
    for case in cases:
        if "actual" not in case or "expected" not in case:
            raise ValueError(f"case {case.get('id', '<unknown>')} must include actual and expected")
        result = evaluate_trajectory(
            case["actual"],
            case["expected"],
            mode=case.get("mode", "exact"),
        )
        result["id"] = case.get("id")
        result["description"] = case.get("description", "")
        results.append(result)

    passed = sum(1 for result in results if result["passed"])
    total = len(results)
    average_score = (
        round(sum(result["score"] for result in results) / total, 4)
        if total else 1.0
    )
    return {
        "passed": passed == total,
        "total": total,
        "passed_count": passed,
        "failed_count": total - passed,
        "average_score": average_score,
        "results": results,
    }


__all__ = [
    "SCHEMA",
    "DEFAULT_TRAJECTORY_DATASET",
    "evaluate_trajectory",
    "extract_agents_from_trace",
    "extract_agents_from_events",
    "evaluate_trace",
    "load_jsonl_events",
    "evaluate_trace_jsonl",
    "load_trajectory_dataset",
    "run_trajectory_dataset",
]

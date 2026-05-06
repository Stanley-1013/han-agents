"""
Provider-neutral guardrail policy helpers for HAN agents.

These helpers do not execute or block platform tools directly. They provide a
single local policy source that prompts, traces, tests, and future hook-level
enforcement can share.
"""

import fnmatch
import os
import re
from copy import deepcopy
from typing import Dict, Iterable, List


SCHEMA = """
=== Guardrails API ===

get_agent_policy(agent) -> Dict
    Return default tool/path/command policy for an agent.

format_policy_for_prompt(agent) -> str
    Render a concise policy block for dispatch prompts.

check_command(command, agent='executor') -> Dict
    Deterministically classify shell command risk against policy.

check_path(path, agent='executor', operation='read') -> Dict
    Check path access against policy allow/deny patterns.

enforce_result(check_result, mode=None) -> Dict
    Convert a guardrail check into allow/warn/block enforcement.
"""


AGENT_POLICIES = {
    "pfc": {
        "tools": ["Read", "Write", "Bash", "Glob", "Grep"],
        "write_paths": ["**"],
        "deny_paths": [".git/**", "**/.env", "**/.env.*", "**/secrets/**", "**/*secret*"],
        "deny_commands": [
            "rm -rf*",
            "git reset --hard*",
            "git checkout --*",
            "curl *|*sh",
            "wget *|*sh",
            "chmod 777*",
        ],
        "network": "ask",
        "notes": "Plan and modify only within the project; ask before destructive or networked operations.",
    },
    "executor": {
        "tools": ["Read", "Write", "Bash", "Glob", "Grep"],
        "write_paths": ["**"],
        "deny_paths": [".git/**", "**/.env", "**/.env.*", "**/secrets/**", "**/*secret*"],
        "deny_commands": [
            "rm -rf*",
            "git reset --hard*",
            "git checkout --*",
            "curl *|*sh",
            "wget *|*sh",
            "chmod 777*",
        ],
        "network": "ask",
        "notes": "Execute the assigned task only; avoid unrelated files and destructive commands.",
    },
    "critic": {
        "tools": ["Read", "Grep", "Glob"],
        "write_paths": [],
        "deny_paths": ["**/.env", "**/.env.*", "**/secrets/**", "**/*secret*"],
        "deny_commands": ["*"],
        "network": "none",
        "notes": "Read-only validation. Do not write files or run shell commands.",
    },
    "memory": {
        "tools": ["Read", "Write", "Bash", "Grep"],
        "write_paths": ["brain/**"],
        "deny_paths": ["**/.env", "**/.env.*", "**/secrets/**", "**/*secret*"],
        "deny_commands": [
            "rm -rf*",
            "git reset --hard*",
            "git checkout --*",
            "curl *|*sh",
            "wget *|*sh",
        ],
        "network": "none",
        "notes": "Write memory through HAN APIs; avoid arbitrary project edits.",
    },
    "researcher": {
        "tools": ["Read", "Grep", "Glob", "WebFetch", "WebSearch"],
        "write_paths": [],
        "deny_paths": ["**/.env", "**/.env.*", "**/secrets/**", "**/*secret*"],
        "deny_commands": ["*"],
        "network": "allowed",
        "notes": "Gather information only; do not edit project files.",
    },
    "drift-detector": {
        "tools": ["Read", "Grep", "Glob"],
        "write_paths": [],
        "deny_paths": ["**/.env", "**/.env.*", "**/secrets/**", "**/*secret*"],
        "deny_commands": ["*"],
        "network": "none",
        "notes": "Read-only drift analysis.",
    },
}

VALID_ENFORCEMENT_MODES = {"warn", "block"}


def get_agent_policy(agent: str) -> Dict:
    """Return a defensive copy of the default policy for an agent."""
    return deepcopy(AGENT_POLICIES.get(agent or "executor", AGENT_POLICIES["executor"]))


def _matches_any(value: str, patterns: Iterable[str]) -> bool:
    normalized = value.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in patterns)


def _command_matches(command: str, pattern: str) -> bool:
    normalized = re.sub(r"\s+", " ", command.strip())
    return fnmatch.fnmatch(normalized, pattern)


def check_command(command: str, agent: str = "executor") -> Dict:
    """Classify a command against the agent policy."""
    policy = get_agent_policy(agent)
    command = command or ""
    violations: List[Dict] = []

    for pattern in policy.get("deny_commands", []):
        if pattern == "*" or _command_matches(command, pattern):
            violations.append({
                "type": "denied_command",
                "pattern": pattern,
                "message": f"Command matches denied pattern: {pattern}",
            })

    network_command = re.search(r"\b(curl|wget|pip|npm|pnpm|yarn|uv|cargo)\b", command)
    if network_command:
        if policy.get("network") == "ask":
            violations.append({
                "type": "network_requires_approval",
                "message": "Network or dependency command requires explicit approval.",
            })
        elif policy.get("network") == "none":
            violations.append({
                "type": "network_denied",
                "message": "Network or dependency command is denied by policy.",
            })

    return {
        "allowed": not violations,
        "agent": agent,
        "command": command,
        "violations": violations,
    }


def check_path(path: str, agent: str = "executor", operation: str = "read") -> Dict:
    """Classify a path operation against the agent policy."""
    policy = get_agent_policy(agent)
    path = (path or "").replace(os.sep, "/")
    violations: List[Dict] = []

    if _matches_any(path, policy.get("deny_paths", [])):
        violations.append({
            "type": "denied_path",
            "message": f"Path is denied by policy: {path}",
        })

    if operation == "write":
        write_paths = policy.get("write_paths", [])
        if not write_paths or not _matches_any(path, write_paths):
            violations.append({
                "type": "write_not_allowed",
                "message": f"Agent '{agent}' cannot write path: {path}",
            })

    return {
        "allowed": not violations,
        "agent": agent,
        "path": path,
        "operation": operation,
        "violations": violations,
    }


def format_policy_for_prompt(agent: str) -> str:
    """Render a concise policy block for agent dispatch prompts."""
    policy = get_agent_policy(agent)
    write_paths = ", ".join(policy.get("write_paths") or ["none"])
    deny_paths = ", ".join(policy.get("deny_paths") or ["none"])
    deny_commands = ", ".join(policy.get("deny_commands") or ["none"])
    return f"""## Harness Guardrail Policy

Agent: {agent}
Allowed tools: {', '.join(policy.get('tools', []))}
Writable paths: {write_paths}
Denied paths: {deny_paths}
Denied commands: {deny_commands}
Network policy: {policy.get('network', 'none')}
Policy note: {policy.get('notes', '')}
"""


def get_enforcement_mode(mode: str = None) -> str:
    """Return normalized enforcement mode from arg or environment."""
    selected = (mode or os.environ.get("HAN_GUARDRAIL_MODE") or "warn").lower()
    return selected if selected in VALID_ENFORCEMENT_MODES else "warn"


def enforce_result(check_result: Dict, mode: str = None) -> Dict:
    """Convert check output into an enforcement decision."""
    selected = get_enforcement_mode(mode)
    allowed = check_result.get("allowed", True)
    action = "allow" if allowed else selected
    return {
        "action": action,
        "mode": selected,
        "allowed": allowed,
        "exit_code": 0 if allowed or selected == "warn" else 1,
        "check": check_result,
    }


__all__ = [
    "SCHEMA",
    "AGENT_POLICIES",
    "get_agent_policy",
    "format_policy_for_prompt",
    "check_command",
    "check_path",
    "get_enforcement_mode",
    "enforce_result",
]

"""
Tests for provider-neutral guardrail policies.
"""


def test_executor_denies_destructive_command():
    from servers.guardrails import check_command

    result = check_command("rm -rf /tmp/project", agent="executor")
    assert result["allowed"] is False
    assert result["violations"][0]["type"] == "denied_command"


def test_guardrail_enforcement_modes():
    from servers.guardrails import check_command, enforce_result

    result = check_command("rm -rf /tmp/project", agent="executor")

    warn = enforce_result(result, mode="warn")
    assert warn["action"] == "warn"
    assert warn["exit_code"] == 0

    block = enforce_result(result, mode="block")
    assert block["action"] == "block"
    assert block["exit_code"] == 1


def test_executor_flags_network_approval():
    from servers.guardrails import check_command

    result = check_command("pip install requests", agent="executor")
    assert result["allowed"] is False
    assert result["violations"][0]["type"] == "network_requires_approval"


def test_network_none_denies_dependency_commands():
    from servers.guardrails import check_command

    result = check_command("pip install requests", agent="memory")
    assert result["allowed"] is False
    assert result["violations"][0]["type"] == "network_denied"


def test_executor_denies_chmod_777_with_target():
    from servers.guardrails import check_command

    result = check_command("chmod 777 /tmp/file", agent="executor")
    assert result["allowed"] is False
    assert result["violations"][0]["type"] == "denied_command"


def test_critic_is_read_only():
    from servers.guardrails import check_path

    result = check_path("servers/facade.py", agent="critic", operation="write")
    assert result["allowed"] is False
    assert result["violations"][0]["type"] == "write_not_allowed"


def test_policy_prompt_block_contains_agent():
    from servers.guardrails import format_policy_for_prompt

    block = format_policy_for_prompt("executor")
    assert "Harness Guardrail Policy" in block
    assert "Agent: executor" in block
    assert "Denied commands" in block


def test_guard_cli_denies_command(capsys):
    from argparse import Namespace
    from cli.main import cmd_guard

    code = cmd_guard(Namespace(
        agent="executor",
        policy=False,
        guard_command="rm -rf /tmp/project",
        path=None,
        operation="read",
        mode="block",
    ))

    captured = capsys.readouterr()
    assert code == 1
    assert "[DENY]" in captured.out
    assert "denied pattern" in captured.out


def test_guard_cli_prints_policy(capsys):
    from argparse import Namespace
    from cli.main import cmd_guard

    code = cmd_guard(Namespace(
        agent="critic",
        policy=True,
        guard_command=None,
        path=None,
        operation="read",
        mode="block",
    ))

    captured = capsys.readouterr()
    assert code == 0
    assert '"network": "none"' in captured.out


def test_guard_cli_subprocess_policy():
    import os
    import subprocess
    import sys

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = subprocess.run(
        [sys.executable, "cli/main.py", "guard", "--agent", "critic", "--policy"],
        cwd=base_dir,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert '"network": "none"' in result.stdout

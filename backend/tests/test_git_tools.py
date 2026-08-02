import json
from pathlib import Path

import pytest

from uai_forge.builtins import register_builtins
from uai_forge.git_tools import GitTool
from uai_forge.models import PluginKind, ToolBinding, default_tool_bindings
from uai_forge.registry import PluginRegistry


def _binding(root: Path, **overrides):
    config = {
        "root_path": str(root),
        "credential_ref": "cred_github",
        "remote_name": "origin",
        "timeout_seconds": 10,
        "max_output_bytes": 20_000,
    }
    config.update(overrides)
    return ToolBinding(plugin_id="tool.git", config=config)


def _result(stdout="", *, exit_code=0, stderr="", raw_stdout=None):
    return {
        "command": [],
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "_raw_stdout": stdout if raw_stdout is None else raw_stdout,
        "_raw_stderr": stderr,
        "timed_out": False,
        "truncated": False,
        "duration_ms": 1,
    }


def _fake_runner(
    root: Path,
    *,
    staged_diff: str = "+safe change\n",
    status_text: str = " M AGENTS.md\0",
):
    calls = []

    async def run(_root, command, *, secret=None):
        command = list(command)
        calls.append((command, secret))
        if command[1:3] == ["rev-parse", "--show-toplevel"]:
            return _result(f"{root}\n")
        if command[1:4] == ["remote", "get-url", "origin"]:
            return _result("https://github.com/example/uai.git\n")
        if command[1:5] == ["symbolic-ref", "--quiet", "--short", "HEAD"]:
            return _result("main\n")
        if command[1:4] == ["status", "--porcelain=v1", "--untracked-files=all"]:
            return _result(status_text, raw_stdout=status_text)
        if command[1:4] == ["status", "--short", "--branch"]:
            return _result("## main\n M AGENTS.md\n")
        if command[1:4] == ["diff", "--cached", "--name-only"]:
            return _result("AGENTS.md\0", raw_stdout="AGENTS.md\0")
        if command[1:3] == ["diff", "--cached"]:
            return _result(staged_diff, raw_stdout=staged_diff)
        if command[1:3] == ["add", "--all"]:
            return _result()
        if command[1:3] == ["commit", "-c"] or command[1:4] == ["-c", "core.hooksPath=/dev/null", "commit"]:
            return _result("[main abc1234] evolve\n")
        if command[1:4] == ["rev-parse", "--verify", "HEAD"]:
            return _result("abc1234567890abcdef\n")
        if command[1:2] == ["push"]:
            return _result("To github.com:example/uai.git\n", raw_stdout="To github.com:example/uai.git\n")
        if command[1:2] == ["reset"]:
            return _result()
        if command[1:2] == ["pull"]:
            return _result("Already up to date.\n")
        raise AssertionError(f"unhandled command: {command}")

    return run, calls


class Resolver:
    def __init__(self, secret="fixture-git-secret"):
        self.secret = secret
        self.calls = []

    async def resolve_tool_credential_secret(self, tenant_id, credential_id):
        self.calls.append((tenant_id, credential_id))
        return self.secret


def test_git_manifest_is_registered_but_not_default():
    registry = PluginRegistry()
    register_builtins(registry)

    manifest = registry.manifest("tool.git", PluginKind.TOOL)
    assert manifest is not None
    assert {"pull", "push", "commit", "credential_ref"}.issubset(manifest.capabilities)
    assert "tool.git" not in {binding.plugin_id for binding in default_tool_bindings()}
    assert isinstance(registry.create_tool(_binding(Path("/workspace"))), GitTool)


@pytest.mark.asyncio
async def test_git_push_resolves_credential_ref_without_returning_secret(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    tool = GitTool(_binding(root))
    fake_run, calls = _fake_runner(root, status_text="")
    tool._run = fake_run
    resolver = Resolver()

    result = await tool.invoke(
        {"action": "push"},
        {"tenant_id": "default", "_tool_credential_port": resolver},
    )

    assert result["ok"] is True
    assert result["pushed"] is True
    assert resolver.calls == [("default", "cred_github")]
    assert "fixture-git-secret" not in json.dumps(result)
    push_calls = [call for call in calls if call[0][1:2] == ["push"]]
    assert len(push_calls) == 1
    assert push_calls[0][1] == "fixture-git-secret"
    assert all("--force" not in command for command, _ in calls)


@pytest.mark.asyncio
async def test_git_pull_uses_the_normal_repository_workflow(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    tool = GitTool(_binding(root))
    fake_run, calls = _fake_runner(root, status_text="")
    tool._run = fake_run
    resolver = Resolver()

    result = await tool.invoke(
        {"action": "pull"},
        {"tenant_id": "default", "_tool_credential_port": resolver},
    )

    assert result["ok"] is True
    assert result["pulled"] is True
    pull = next(command for command, _ in calls if command[1:2] == ["pull"])
    assert pull[1:5] == ["pull", "--no-tags", "origin", "main"]


@pytest.mark.asyncio
async def test_git_commit_and_push_uses_the_normal_repository_workflow(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    tool = GitTool(_binding(root))
    fake_run, calls = _fake_runner(root)
    tool._run = fake_run
    resolver = Resolver()

    result = await tool.invoke(
        {"action": "commit_and_push", "commit_message": "evolve framework"},
        {"tenant_id": "default", "_tool_credential_port": resolver},
    )

    assert result["ok"] is True
    assert result["committed"] is True
    assert result["pushed"] is True
    assert result["commit_sha"] == "abc1234567890abcdef"
    assert result["files"] == ["AGENTS.md"]
    add = next(command for command, _ in calls if command[1:3] == ["add", "--all"])
    assert add == ["git", "add", "--all"]
    commit = next(command for command, _ in calls if command[1:4] == ["-c", "core.hooksPath=/dev/null", "commit"])
    assert commit[-2:] == ["-m", "evolve framework"]
    push = next(command for command, _ in calls if command[1:2] == ["push"])
    assert push[-1] == "HEAD"
    assert "--force" not in push


@pytest.mark.asyncio
async def test_git_commit_is_available_without_a_push_or_credential_resolution(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    tool = GitTool(_binding(root))
    fake_run, calls = _fake_runner(root)
    tool._run = fake_run

    result = await tool.invoke(
        {"action": "commit", "commit_message": "local evolution"},
        {"tenant_id": "default"},
    )

    assert result["ok"] is True
    assert result["committed"] is True
    assert result["action"] == "commit"
    assert not any(command[1:2] == ["push"] for command, _ in calls)


@pytest.mark.asyncio
async def test_git_commit_accepts_normal_repository_paths_without_audit_gate(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    tool = GitTool(_binding(root))
    fake_run, calls = _fake_runner(root, staged_diff="+normal repository content\n")
    tool._run = fake_run
    resolver = Resolver()

    result = await tool.invoke(
        {"action": "commit_and_push", "commit_message": "safe change"},
        {"tenant_id": "default", "_tool_credential_port": resolver},
    )

    assert result["ok"] is True
    assert result["committed"] is True
    assert result["pushed"] is True
    assert any(command[1:4] == ["-c", "core.hooksPath=/dev/null", "commit"] for command, _ in calls)
    assert any(command[1:2] == ["push"] for command, _ in calls)
    assert not any(command[1:2] == ["reset"] for command, _ in calls)


@pytest.mark.asyncio
async def test_git_commit_rejects_inline_credential_without_an_approval_gate(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    tool = GitTool(_binding(root))
    fake_run, calls = _fake_runner(root, staged_diff="+github_pat_unsafe_fixture_value\n")
    tool._run = fake_run
    resolver = Resolver()

    result = await tool.invoke(
        {"action": "commit_and_push", "commit_message": "safe change"},
        {"tenant_id": "default", "_tool_credential_port": resolver},
    )

    assert result["ok"] is False
    assert result["error"] == "git.inline_credential_denied"
    assert not any(command[1:4] == ["-c", "core.hooksPath=/dev/null", "commit"] for command, _ in calls)
    assert not any(command[1:2] == ["push"] for command, _ in calls)
    assert any(command[1:2] == ["reset"] for command, _ in calls)


@pytest.mark.asyncio
async def test_git_push_fails_closed_without_private_credential_port(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    tool = GitTool(_binding(root))
    fake_run, _ = _fake_runner(root, status_text="")
    tool._run = fake_run

    result = await tool.invoke({"action": "push"}, {"tenant_id": "default"})

    assert result["ok"] is False
    assert result["error"] == "git.credential_resolver_unavailable"

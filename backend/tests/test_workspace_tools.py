import subprocess

import pytest

from uai_forge.builtins import register_builtins
from uai_forge.models import PluginKind, ToolBinding, default_tool_bindings
from uai_forge.registry import PluginRegistry
from uai_forge.workspace_tools import WorkspaceTool


def _make_repo(tmp_path, *, allow_write=True):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root, WorkspaceTool(
        ToolBinding(
            plugin_id="tool.workspace",
            config={
                "root_path": str(root),
                "allow_write": allow_write,
                "timeout_seconds": 5,
                "max_output_bytes": 20_000,
                "max_patch_bytes": 20_000,
            },
        )
    )


def test_workspace_tool_is_explicit_and_registered():
    registry = PluginRegistry()
    register_builtins(registry)

    manifest = registry.manifest("tool.workspace", PluginKind.TOOL)
    assert manifest is not None
    assert "workspace_read" in manifest.capabilities
    assert "tool.workspace" not in {item.plugin_id for item in default_tool_bindings()}
    assert "Workspace-relative path only" in WorkspaceTool.parameters["properties"]["path"]["description"]

    tool = registry.create_tool(
        ToolBinding(
            plugin_id="tool.workspace",
            config={"root_path": "/workspace", "allow_write": False},
        )
    )
    assert isinstance(tool, WorkspaceTool)


@pytest.mark.asyncio
async def test_workspace_lists_and_reads_bounded_non_sensitive_files(tmp_path):
    root, tool = _make_repo(tmp_path)
    (root / "README.md").write_text("line one\nline two\nline three\n", encoding="utf-8")
    (root / ".env").write_text("TOKEN=should-not-be-read\n", encoding="utf-8")
    (root / ".ssh").mkdir()
    (root / ".ssh" / "config").write_text("Host example\n", encoding="utf-8")
    (root / ".docker").mkdir()
    (root / ".docker" / "config.json").write_text("{}\n", encoding="utf-8")
    (root / ".kube").mkdir()
    (root / ".kube" / "config").write_text("clusters: []\n", encoding="utf-8")

    listed = await tool.invoke({"action": "list"}, {})
    assert {item["path"] for item in listed["entries"]} == {"README.md"}

    read = await tool.invoke(
        {"action": "read", "path": "README.md", "offset": 1, "limit": 1},
        {},
    )
    assert read["content"] == "line two\n"
    assert read["start_line"] == 2

    with pytest.raises(ValueError, match="workspace.sensitive_path_denied"):
        await tool.invoke({"action": "read", "path": ".env"}, {})
    with pytest.raises(ValueError, match="workspace.sensitive_path_denied"):
        await tool.invoke({"action": "read", "path": ".ssh/config"}, {})
    with pytest.raises(ValueError, match="workspace.sensitive_path_denied"):
        await tool.invoke({"action": "read", "path": ".docker/config.json"}, {})
    with pytest.raises(ValueError, match="workspace.sensitive_path_denied"):
        await tool.invoke({"action": "read", "path": ".kube/config"}, {})


@pytest.mark.asyncio
async def test_workspace_rejects_escape_and_git_internal_paths(tmp_path):
    root, tool = _make_repo(tmp_path)
    (tmp_path / "outside.txt").write_text("outside\n", encoding="utf-8")

    with pytest.raises(ValueError, match="workspace.path_outside_root"):
        await tool.invoke({"action": "read", "path": "../outside.txt"}, {})
    with pytest.raises(ValueError, match="workspace.path_invalid"):
        await tool.invoke({"action": "read", "path": "/workspace/README.md"}, {})
    with pytest.raises(ValueError, match="workspace.git_internal_denied"):
        await tool.invoke({"action": "read", "path": ".git/HEAD"}, {})


@pytest.mark.asyncio
async def test_workspace_applies_valid_patch_but_not_deletion_or_disabled_write(tmp_path):
    root, tool = _make_repo(tmp_path)
    (root / "README.md").write_text("before\n", encoding="utf-8")
    patch = """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1 @@
-before
+after
"""

    result = await tool.invoke({"action": "patch", "patch": patch}, {})
    assert result == {
        "action": "patch",
        "ok": True,
        "applied": True,
        "paths": ["README.md"],
    }
    assert (root / "README.md").read_text(encoding="utf-8") == "after\n"

    delete_patch = """diff --git a/README.md b/README.md
--- a/README.md
+++ /dev/null
@@ -1 +0,0 @@
-after
"""
    delete_result = await tool.invoke({"action": "patch", "patch": delete_patch}, {})
    assert delete_result == {
        "action": "patch",
        "ok": False,
        "applied": False,
        "error": "workspace.patch_delete_denied",
    }

    readonly_parent = tmp_path / "readonly"
    readonly_parent.mkdir()
    _, read_only_tool = _make_repo(readonly_parent, allow_write=False)
    readonly_result = await read_only_tool.invoke({"action": "patch", "patch": patch}, {})
    assert readonly_result == {
        "action": "patch",
        "ok": False,
        "applied": False,
        "error": "workspace.write_disabled",
    }


@pytest.mark.asyncio
async def test_workspace_invalid_patch_is_recoverable_and_does_not_write(tmp_path):
    root, tool = _make_repo(tmp_path)
    (root / "README.md").write_text("before\n", encoding="utf-8")

    result = await tool.invoke(
        {"action": "patch", "patch": "--- a/README.md\n+++ b/README.md\n"},
        {},
    )

    assert result == {
        "action": "patch",
        "ok": False,
        "applied": False,
        "error": "workspace.patch_invalid",
    }
    assert (root / "README.md").read_text(encoding="utf-8") == "before\n"


@pytest.mark.asyncio
async def test_workspace_git_status_returns_structured_bounded_result(tmp_path):
    _, tool = _make_repo(tmp_path)
    result = await tool.invoke({"action": "git_status"}, {})
    assert result["action"] == "git_status"
    assert result["exit_code"] == 0
    assert "##" in result["stdout"]
    assert result["command"] == ["git", "status", "--short", "--branch"]


@pytest.mark.asyncio
async def test_workspace_list_does_not_leak_sensitive_symlink_targets(tmp_path):
    root, tool = _make_repo(tmp_path)
    (root / ".ssh").mkdir()
    (root / ".ssh" / "config").write_text("Host example\n", encoding="utf-8")
    (root / "credentials.json").write_text("{}\n", encoding="utf-8")
    (root / "link-to-ssh").symlink_to(".ssh", target_is_directory=True)
    (root / "link-to-credentials").symlink_to("credentials.json")
    (root / "README.md").write_text("ok\n", encoding="utf-8")

    listed = await tool.invoke({"action": "list"}, {})
    assert {item["path"] for item in listed["entries"]} == {"README.md"}


class _StubProcess:
    """Minimal process double: no pipes, so _read_limited short-circuits."""

    def __init__(self) -> None:
        self.returncode = None
        self.stdin = None
        self.stdout = None
        self.stderr = None

    async def wait(self) -> int:
        self.returncode = 0
        return 0

    def terminate(self) -> None:
        self.returncode = 0

    def kill(self) -> None:
        self.returncode = 0


@pytest.mark.asyncio
async def test_workspace_subprocess_env_is_scrubbed_and_unbuffered(tmp_path, monkeypatch):
    root, tool = _make_repo(tmp_path)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "must-not-leak")
    captured = {}

    async def stub_runner(*args, **kwargs):
        captured["env"] = dict(kwargs["env"])
        return _StubProcess()

    tool._process_runner = stub_runner
    result = await tool.invoke({"action": "git_status"}, {})

    assert result["exit_code"] == 0
    assert captured["env"]["PYTHONUNBUFFERED"] == "1"
    assert captured["env"]["HOME"] == "/nonexistent"
    assert captured["env"]["GIT_CONFIG_NOSYSTEM"] == "1"

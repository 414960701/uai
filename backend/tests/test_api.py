import asyncio
import time
from pathlib import Path

from fastapi.testclient import TestClient

from uai_forge.api import create_app
from uai_forge.settings import Settings
from test_support import register_test_provider, seed_test_topology


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=str(tmp_path / "api.db"),
        allowed_origins=["http://localhost:3000"],
    )


def make_app(tmp_path: Path):
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    app = create_app(make_settings(tmp_path))
    register_test_provider(app.state.container.registry)
    asyncio.run(app.state.container.repository.initialize())
    asyncio.run(seed_test_topology(app.state.container.repository))
    asyncio.set_event_loop(asyncio.new_event_loop())
    return app


def test_control_plane_crud_and_capabilities(tmp_path):
    with TestClient(make_app(tmp_path)) as client:
        assert client.get("/health").json()["status"] == "ok"
        plugins = client.get("/api/v1/plugins").json()
        assert {plugin["kind"] for plugin in plugins} >= {
            "provider",
            "tool",
            "memory",
            "storage",
            "event_bus",
            "scheduler",
            "middleware",
            "ui",
        }

        agents = client.get("/api/v1/agents").json()
        assert len(agents) == 3
        lead = next(agent for agent in agents if agent["id"] == "agt_research_lead")
        assert {
            mount["alias"]: mount["allowed_tools"]
            for mount in lead["children"]
        } == {
            "analyst": ["tool.calculator"],
            "verifier": ["tool.utc_now"],
        }
        validation = client.post(f"/api/v1/agents/{lead['id']}/validate").json()
        assert validation["valid"] is True
        assert len(validation["edges"]) == 2

        update = client.patch(
            f"/api/v1/agents/{lead['id']}",
            json={
                "expected_revision": lead["revision"],
                "description": "Updated through the versioned API",
            },
        )
        assert update.status_code == 200
        assert update.json()["revision"] == lead["revision"] + 1


def test_run_lifecycle_from_agent_revision(tmp_path):
    with TestClient(make_app(tmp_path)) as client:
        response = client.post(
            "/api/v1/runs",
            json={
                "agent_id": "agt_research_lead",
                "agent_revision": 1,
                "input": "delegate:analyst assess the plugin contract",
            },
        )
        assert response.status_code == 202
        run_id = response.json()["id"]

        terminal = None
        for _ in range(50):
            terminal = client.get(f"/api/v1/runs/{run_id}").json()
            if terminal["status"] in {"succeeded", "failed", "cancelled"}:
                break
            time.sleep(0.02)

        assert terminal["status"] == "succeeded"
        assert terminal["agent_revision"] == 1
        assert "plugin contract" in terminal["output"]

        history = client.get(f"/api/v1/runs/{run_id}/events/history")
        assert history.status_code == 200
        events = history.json()
        assert [event["sequence"] for event in events] == list(
            range(1, len(events) + 1)
        )
        assert events[0]["type"] == "run.started"
        assert events[-1]["type"] == "run.completed"

        tail = client.get(
            f"/api/v1/runs/{run_id}/events/history",
            params={"after": events[-2]["sequence"]},
        )
        assert [event["sequence"] for event in tail.json()] == [
            events[-1]["sequence"]
        ]

        with client.stream(
            "GET",
            f"/api/v1/runs/{run_id}/events",
            headers={"Last-Event-ID": str(events[-2]["sequence"])},
        ) as stream:
            assert stream.status_code == 200
            assert stream.headers["content-type"].startswith("text/event-stream")
            sse_lines = [line for line in stream.iter_lines() if line]

        assert sse_lines[0] == f"id: {events[-1]['sequence']}"
        assert sse_lines[1] == "event: run.completed"
        assert sse_lines[2].startswith("data: ")
        assert '"type": "run.completed"' in sse_lines[2]


def test_complex_execute_run_persists_todo_and_todo_events(tmp_path):
    with TestClient(make_app(tmp_path)) as client:
        created = client.post(
            "/api/v1/runs",
            json={
                "agent_id": "agt_research_lead",
                "input": "请分析当前方案并比较两个实现路径，然后整理风险、测试步骤和最终交付建议。",
            },
        )
        assert created.status_code == 202
        initial = created.json()
        assert initial["todo"]["source"] == "automatic"
        assert initial["metrics"]["todo_id"] == initial["todo"]["todo_id"]

        for _ in range(50):
            terminal = client.get(f"/api/v1/runs/{initial['id']}").json()
            if terminal["status"] in {"succeeded", "failed", "cancelled"}:
                break
            time.sleep(0.02)

        assert terminal["status"] == "succeeded"
        assert terminal["todo"]["status"] == "completed"
        assert all(item["status"] == "completed" for item in terminal["todo"]["items"])
        event_types = [
            event["type"]
            for event in client.get(f"/api/v1/runs/{initial['id']}/events/history").json()
        ]
        assert "todo.created" in event_types
        assert "todo.updated" in event_types
        assert "todo.completed" in event_types


def test_plan_review_api_edits_and_approves_a_new_execution_run(tmp_path):
    with TestClient(make_app(tmp_path)) as client:
        created = client.post(
            "/api/v1/runs",
            json={
                "agent_id": "agt_research_lead",
                "input": "请先给出一个可审阅的研究流程",
                "execution_mode": "plan",
            },
        )
        assert created.status_code == 202
        plan_run_id = created.json()["id"]

        for _ in range(50):
            plan_run = client.get(f"/api/v1/runs/{plan_run_id}").json()
            if plan_run["status"] in {"succeeded", "failed", "cancelled"}:
                break
            time.sleep(0.02)
        assert plan_run["status"] == "succeeded"
        assert plan_run["plan"]["status"] == "proposed"
        assert plan_run["metrics"]["plan_id"] == plan_run["plan"]["plan_id"]

        plan = client.get(f"/api/v1/runs/{plan_run_id}/plan")
        assert plan.status_code == 200
        current_plan = plan.json()
        edited = client.patch(
            f"/api/v1/runs/{plan_run_id}/plan",
            json={
                "expected_version": current_plan["version"],
                "title": "研究流程（已审阅）",
                "goal": "按批准流程完成研究",
                "assumptions": ["当前数据源由执行阶段确认"],
                "steps": [
                    {
                        "id": "step_01",
                        "title": "确认问题",
                        "description": "确认研究问题与成功标准",
                        "scope": [],
                        "dependencies": [],
                        "risk": "low",
                        "status": "proposed",
                    }
                ],
                "risks": ["数据源可能需要重新校验"],
            },
        )
        assert edited.status_code == 200
        assert edited.json()["version"] == 2
        assert edited.json()["status"] == "needs_revision"

        approved = client.post(
            f"/api/v1/runs/{plan_run_id}/plan/approve",
            json={"expected_version": 2},
        )
        assert approved.status_code == 202
        execution_id = approved.json()["id"]
        assert approved.json()["metrics"]["execution_mode"] == "execute"
        assert approved.json()["metrics"]["source_plan_run_id"] == plan_run_id
        assert client.get(f"/api/v1/runs/{execution_id}").json()["status"] in {
            "queued",
            "running",
            "succeeded",
        }
        source = client.get(f"/api/v1/runs/{plan_run_id}").json()
        assert source["plan"]["status"] == "executing"
        event_types = [event["type"] for event in client.get(f"/api/v1/runs/{plan_run_id}/events/history").json()]
        assert "plan.proposed" in event_types
        assert "plan.approved" in event_types
        assert "plan.execution_started" in event_types


def test_run_metadata_rejects_inline_secrets_without_persisting(tmp_path):
    with TestClient(make_app(tmp_path)) as client:
        original_run_ids = {
            run["id"] for run in client.get("/api/v1/runs").json()
        }
        inline_secret = "test-secret-must-not-appear"

        run = client.post(
            "/api/v1/runs",
            json={
                "agent_id": "agt_research_lead",
                "input": "this request must be rejected before persistence",
                "metadata": {"api_key": inline_secret},
            },
        )
        assert run.status_code == 422
        assert {
            item["id"] for item in client.get("/api/v1/runs").json()
        } == original_run_ids


def test_agent_patch_revalidates_tool_and_mount_name_collisions(tmp_path):
    with TestClient(make_app(tmp_path)) as client:
        agent_id = "agt_research_lead"
        original = client.get(f"/api/v1/agents/{agent_id}").json()

        response = client.patch(
            f"/api/v1/agents/{agent_id}",
            json={
                "expected_revision": original["revision"],
                "tools": [
                    {
                        "plugin_id": "tool.echo",
                        "alias": "delegate_analyst",
                    }
                ],
            },
        )

        assert response.status_code == 422
        assert client.get(f"/api/v1/agents/{agent_id}").json() == original


def test_instance_target_is_removed_and_revisions_are_listed(tmp_path):
    with TestClient(make_app(tmp_path)) as client:
        revisions = client.get("/api/v1/agents/agt_research_lead/revisions")
        assert revisions.status_code == 200
        assert [item["revision"] for item in revisions.json()] == [1]

        assert client.get("/api/v1/instances").status_code == 404
        rejected = client.post(
            "/api/v1/runs",
            json={
                "instance_id": "ins_removed",
                "input": "instance targets are no longer accepted",
            },
        )
        assert rejected.status_code == 422


def test_latest_pointer_rolls_back_and_next_publish_keeps_revision_sequence(tmp_path):
    with TestClient(make_app(tmp_path)) as client:
        agent_id = "agt_research_lead"
        current = client.get(f"/api/v1/agents/{agent_id}").json()
        for prompt in ("revision two", "revision three"):
            response = client.patch(
                f"/api/v1/agents/{agent_id}",
                json={
                    "expected_revision": current["revision"],
                    "system_prompt": prompt,
                },
            )
            assert response.status_code == 200
            current = response.json()
        assert current["revision"] == 3

        rollback = client.post(
            f"/api/v1/agents/{agent_id}/rollback",
            json={"revision": 1, "expected_revision": 3},
        )
        assert rollback.status_code == 200
        assert rollback.json()["revision"] == 1
        assert client.get(f"/api/v1/agents/{agent_id}").json()["revision"] == 1

        run = client.post(
            "/api/v1/runs",
            json={"agent_id": agent_id, "input": "use the rolled-back latest"},
        )
        assert run.status_code == 202
        assert run.json()["agent_revision"] == 1

        continued = client.patch(
            f"/api/v1/agents/{agent_id}",
            json={"expected_revision": 1, "system_prompt": "continued from rollback"},
        )
        assert continued.status_code == 200
        assert continued.json()["revision"] == 4
        assert [
            item["revision"]
            for item in client.get(f"/api/v1/agents/{agent_id}/revisions").json()
        ] == [4, 3, 2, 1]


def test_agent_draft_publish_lifecycle_and_version_history(tmp_path):
    with TestClient(make_app(tmp_path)) as client:
        agent_id = "agt_research_lead"
        initial = client.get(f"/api/v1/agents/{agent_id}/revisions").json()
        assert initial[0]["status"] == "draft"
        assert initial[0]["is_latest"] is True
        assert initial[0]["spec"]["revision"] == 1

        published = client.post(
            f"/api/v1/agents/{agent_id}/publish",
            json={"expected_revision": 1},
        )
        assert published.status_code == 200
        assert published.json()["status"] == "published"
        assert published.json()["is_latest"] is True

        draft = client.post(
            f"/api/v1/agents/{agent_id}/draft",
            json={
                "expected_revision": 1,
                "description": "继续编辑中的草稿",
            },
        )
        assert draft.status_code == 200
        assert draft.json()["revision"] == 2

        history = client.get(f"/api/v1/agents/{agent_id}/revisions").json()
        assert [(item["revision"], item["status"], item["is_latest"]) for item in history] == [
            (2, "draft", True),
            (1, "published", False),
        ]

        stale_publish = client.post(
            f"/api/v1/agents/{agent_id}/publish",
            json={"expected_revision": 1},
        )
        assert stale_publish.status_code == 409

        published_draft = client.post(
            f"/api/v1/agents/{agent_id}/publish",
            json={"expected_revision": 2},
        )
        assert published_draft.status_code == 200
        assert published_draft.json()["status"] == "published"

        rollback = client.post(
            f"/api/v1/agents/{agent_id}/rollback",
            json={"revision": 1, "expected_revision": 2},
        )
        assert rollback.status_code == 200
        assert rollback.json()["revision"] == 1
        assert rollback.json()["status"] == "published"
        assert rollback.json()["is_latest"] is True

        continued = client.post(
            f"/api/v1/agents/{agent_id}/draft",
            json={
                "expected_revision": 1,
                "system_prompt": "从回滚版本继续编辑",
            },
        )
        assert continued.status_code == 200
        assert continued.json()["revision"] == 3


def test_child_mount_tool_allowlist_is_explicit_and_fail_closed(tmp_path):
    with TestClient(make_app(tmp_path)) as client:
        schemas = client.get("/openapi.json").json()["components"]["schemas"]
        allowed_tools = schemas["ChildMount"]["properties"]["allowed_tools"]
        assert "null" in str(allowed_tools).lower()
        assert "array" in str(allowed_tools).lower()

        accepted = client.post(
            "/api/v1/agents",
            json={
                "id": "agt_scoped_parent",
                "name": "Scoped Parent",
                "system_prompt": "Delegate with a bounded tool scope.",
                "model": {
                    "model_config_id": "mdl_test_default",
                },
                "children": [
                    {
                        "alias": "analyst",
                        "agent_id": "agt_market_analyst",
                        "allowed_tools": ["tool.calculator"],
                    }
                ],
            },
        )
        assert accepted.status_code == 201
        assert accepted.json()["children"][0]["allowed_tools"] == [
            "tool.calculator"
        ]

        duplicate = client.post(
            "/api/v1/agents",
            json={
                "id": "agt_ambiguous_scope",
                "name": "Ambiguous Scope",
                "system_prompt": "This configuration must be rejected.",
                "children": [
                    {
                        "alias": "analyst",
                        "agent_id": "agt_market_analyst",
                        "allowed_tools": ["tool.calculator", "tool.calculator"],
                    }
                ],
            },
        )
        assert duplicate.status_code == 422
        assert client.get("/api/v1/agents/agt_ambiguous_scope").status_code == 404


def test_new_agent_defaults_mount_read_only_tools(tmp_path):
    with TestClient(make_app(tmp_path)) as client:
        created = client.post(
            "/api/v1/agents",
            json={
                "id": "agt_default_tools",
                "name": "Default Tools",
                "system_prompt": "Use the default read-only tools when useful.",
                "model": {"model_config_id": "mdl_test_default"},
            },
        )
        assert created.status_code == 201
        assert [tool["plugin_id"] for tool in created.json()["tools"]] == [
            "tool.web_search",
            "tool.web_fetch",
            "tool.web_json",
            "tool.web_rss",
            "tool.calculator",
            "tool.utc_now",
        ]
        assert created.json()["policy"] == {
            "max_steps": 20,
            "max_depth": 6,
            "max_tool_calls": 64,
            "max_parallel_children": 6,
            "timeout_seconds": 300.0,
            "token_budget": 64_000,
            "fail_fast": True,
        }


def test_new_agent_explicit_empty_tools_stays_empty(tmp_path):
    with TestClient(make_app(tmp_path)) as client:
        created = client.post(
            "/api/v1/agents",
            json={
                "id": "agt_no_tools",
                "name": "No Tools",
                "system_prompt": "Do not use tools.",
                "tools": [],
                "model": {"model_config_id": "mdl_test_default"},
            },
        )
        assert created.status_code == 201
        assert created.json()["tools"] == []

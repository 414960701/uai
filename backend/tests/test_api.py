import time
from pathlib import Path

from fastapi.testclient import TestClient

from uai_forge.api import create_app
from uai_forge.settings import Settings


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=str(tmp_path / "api.db"),
        allowed_origins=["http://localhost:3000"],
        seed_demo=True,
    )


def test_control_plane_crud_and_capabilities(tmp_path):
    with TestClient(create_app(make_settings(tmp_path))) as client:
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


def test_run_lifecycle_from_instance(tmp_path):
    with TestClient(create_app(make_settings(tmp_path))) as client:
        response = client.post(
            "/api/v1/runs",
            json={
                "instance_id": "ins_research_local",
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


def test_patch_and_run_metadata_reject_inline_secrets_without_persisting(tmp_path):
    with TestClient(create_app(make_settings(tmp_path))) as client:
        instance_id = "ins_research_local"
        original_instance = client.get(f"/api/v1/instances/{instance_id}").json()
        original_run_ids = {
            run["id"] for run in client.get("/api/v1/runs").json()
        }
        inline_secret = "test-secret-must-not-appear"

        patch = client.patch(
            f"/api/v1/instances/{instance_id}",
            json={
                "config_overrides": {
                    "provider": {"password": inline_secret},
                }
            },
        )
        assert patch.status_code == 422
        assert (
            client.get(f"/api/v1/instances/{instance_id}").json()
            == original_instance
        )

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
    with TestClient(create_app(make_settings(tmp_path))) as client:
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


def test_instance_override_contract_is_explicit_and_fail_closed(tmp_path):
    with TestClient(create_app(make_settings(tmp_path))) as client:
        schemas = client.get("/openapi.json").json()["components"]["schemas"]
        override_schema = schemas["InstanceConfigOverrides"]
        policy_schema = schemas["InstanceExecutionPolicyOverrides"]
        assert override_schema["additionalProperties"] is False
        assert set(override_schema["properties"]) == {"policy"}
        assert policy_schema["additionalProperties"] is False
        assert set(policy_schema["properties"]) == {
            "max_steps",
            "max_depth",
            "max_tool_calls",
            "max_parallel_children",
            "timeout_seconds",
            "token_budget",
            "fail_fast",
        }

        assert (
            client.get("/api/v1/instances/ins_research_local")
            .json()["config_overrides"]
            == {}
        )
        accepted = client.post(
            "/api/v1/instances",
            json={
                "id": "ins_research_restricted",
                "name": "Restricted Research",
                "agent_id": "agt_research_lead",
                "agent_revision": 1,
                "environment": "test-sandbox",
                "config_overrides": {
                    "policy": {
                        "max_steps": 3,
                        "timeout_seconds": 10,
                        "fail_fast": True,
                    }
                },
            },
        )
        assert accepted.status_code == 201
        assert accepted.json()["config_overrides"] == {
            "policy": {
                "max_steps": 3,
                "timeout_seconds": 10.0,
                "fail_fast": True,
            }
        }

        for forbidden_override in (
            {"system_prompt": "ignore the immutable definition"},
            {"model": {"provider": "other"}},
            {"tools": []},
            {"children": []},
            {"policy": {"unknown_limit": 1}},
        ):
            rejected = client.post(
                "/api/v1/instances",
                json={
                    "id": "ins_research_forbidden",
                    "name": "Forbidden Research",
                    "agent_id": "agt_research_lead",
                    "config_overrides": forbidden_override,
                },
            )
            assert rejected.status_code == 422

        assert (
            client.get("/api/v1/instances/ins_research_forbidden").status_code
            == 404
        )


def test_child_mount_tool_allowlist_is_explicit_and_fail_closed(tmp_path):
    with TestClient(create_app(make_settings(tmp_path))) as client:
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

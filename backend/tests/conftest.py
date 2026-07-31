"""Shared pytest setup for the isolated database-backed test provider."""

from datetime import datetime, timezone

import pytest

from uai_forge.models import ModelConfig
from uai_forge.storage import SQLiteRepository


@pytest.fixture(autouse=True)
def seed_implicit_test_model_configs(monkeypatch):
    """Give legacy-shaped test topologies a real DB ModelConfig.

    Production code never synthesizes configuration.  The test-only wrapper
    keeps topology tests focused on graph/runtime policy while every saved
    Agent still has a persisted ``model_config_id`` row.
    """

    original_save_agent = SQLiteRepository.save_agent

    async def save_agent_with_config(self, tenant_id, spec, expected_revision=None):
        config_id = spec.model.model_config_id
        if await self.get_model_config(tenant_id, config_id) is None:
            provider_id = (
                config_id
                if config_id.startswith(("test.", "provider."))
                else "test.deterministic"
            )
            now = datetime.now(timezone.utc)
            await self.save_model_config(
                tenant_id,
                ModelConfig(
                    id=config_id,
                    tenant_id=tenant_id,
                    name=f"Test connection · {config_id}",
                    provider=provider_id,
                    protocol="test",
                    model="deterministic",
                    created_at=now,
                    updated_at=now,
                ),
            )
        return await original_save_agent(self, tenant_id, spec, expected_revision)

    monkeypatch.setattr(SQLiteRepository, "save_agent", save_agent_with_config)

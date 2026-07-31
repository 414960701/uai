"""Provider connection-check TCK for every production provider adapter.

The TCK is intentionally HTTP-boundary based.  It proves the UAI Forge owned
contract without making a network request or registering a test provider in the
product catalog.
"""

import asyncio
import json
from typing import Any, Dict, Optional, Type

import httpx
import pytest

from uai_forge.models import ModelBinding, ModelConnectionCheckRequest
from uai_forge.ports import ModelConnectionChecker, ModelProvider
from uai_forge.providers import AnthropicMessagesProvider, OpenAICompatibleProvider


CANARY = "provider-tck-secret-canary"


class FakeAsyncClient:
    mode = "ok"
    status_code = 200
    content = b"{}"
    last_request: Optional[Dict[str, Any]] = None

    def __init__(self, *, timeout: float, follow_redirects: bool):
        self.timeout = timeout
        self.follow_redirects = follow_redirects

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def get(self, url: str, *, headers: Dict[str, str]):
        self.__class__.last_request = {
            "url": url,
            "headers": headers,
            "timeout": self.timeout,
            "follow_redirects": self.follow_redirects,
        }
        if self.mode == "timeout":
            raise httpx.ReadTimeout("simulated timeout")
        if self.mode == "network":
            raise httpx.ConnectError("simulated network error")
        if self.mode == "unexpected":
            raise RuntimeError(CANARY)
        if self.mode == "cancel":
            await asyncio.sleep(60)
        return httpx.Response(self.status_code, content=self.content)


def provider_for(
    provider_cls: Type[ModelProvider], credential: Optional[str] = CANARY
) -> ModelProvider:
    binding = ModelBinding(
        model_config_id="cfg_tck",
        config={"base_url": "https://provider.example/v1", "timeout_seconds": 0.05},
    )
    binding._runtime_provider = provider_cls.manifest.id
    binding._runtime_protocol = provider_cls.manifest.api_protocol
    binding._runtime_model = "tck-model"
    binding._runtime_credential = credential
    return provider_cls(binding)


def check_request(
    provider: ModelProvider, credential: Optional[str] = CANARY
) -> ModelConnectionCheckRequest:
    return ModelConnectionCheckRequest(
        provider=provider.manifest.id,
        protocol=provider.manifest.api_protocol,
        model="tck-model",
        base_url="https://provider.example/v1",
        config={"timeout_seconds": 0.05},
        credential=credential,
    )


@pytest.mark.parametrize("provider_cls", [OpenAICompatibleProvider, AnthropicMessagesProvider])
def test_production_provider_satisfies_owned_connection_checker_contract(provider_cls):
    provider = provider_for(provider_cls)
    assert isinstance(provider, ModelConnectionChecker)
    assert provider.manifest.kind.value == "provider"
    assert provider.manifest.connection_check == "remote"
    assert provider.manifest.connection_schema_version


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_cls", [OpenAICompatibleProvider, AnthropicMessagesProvider])
async def test_connection_tck_missing_credential_fails_without_network(provider_cls, monkeypatch):
    provider = provider_for(provider_cls, credential=None)

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("credential-missing check must not make a request")

    monkeypatch.setattr(FakeAsyncClient, "get", fail_if_called)
    result = await provider.check(check_request(provider, credential=None))
    assert result.status == "failed"
    assert result.code == "provider.credential_missing"
    assert CANARY not in result.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_cls", [OpenAICompatibleProvider, AnthropicMessagesProvider])
@pytest.mark.parametrize(
    ("mode", "status_code", "expected"),
    [
        ("ok", 200, "provider.connection_ok"),
        ("ok", 401, "provider.unauthorized"),
        ("ok", 429, "provider.rate_limited"),
        ("ok", 503, "provider.http_error"),
    ],
)
async def test_connection_tck_maps_http_results_without_response_body(
    provider_cls,
    mode,
    status_code,
    expected,
    monkeypatch,
):
    FakeAsyncClient.mode = mode
    FakeAsyncClient.status_code = status_code
    FakeAsyncClient.content = json.dumps({"error": CANARY}).encode()
    monkeypatch.setattr("uai_forge.providers.httpx.AsyncClient", FakeAsyncClient)
    provider = provider_for(provider_cls)

    result = await provider.check(check_request(provider))

    assert result.code == expected
    assert CANARY not in result.model_dump_json()
    assert FakeAsyncClient.last_request is not None
    assert FakeAsyncClient.last_request["timeout"] == 0.05
    assert CANARY in FakeAsyncClient.last_request["headers"].get("Authorization", "") or CANARY in FakeAsyncClient.last_request["headers"].get("x-api-key", "")


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_cls", [OpenAICompatibleProvider, AnthropicMessagesProvider])
@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("timeout", "provider.timeout"),
        ("network", "provider.network_error"),
        ("unexpected", "provider.connection_check_failed"),
    ],
)
async def test_connection_tck_normalizes_failures(provider_cls, mode, expected, monkeypatch):
    FakeAsyncClient.mode = mode
    monkeypatch.setattr("uai_forge.providers.httpx.AsyncClient", FakeAsyncClient)
    provider = provider_for(provider_cls)

    result = await provider.check(check_request(provider))

    assert result.status == "failed"
    assert result.code == expected
    assert CANARY not in result.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_cls", [OpenAICompatibleProvider, AnthropicMessagesProvider])
async def test_connection_tck_bounds_response_size(provider_cls, monkeypatch):
    FakeAsyncClient.mode = "ok"
    FakeAsyncClient.status_code = 200
    FakeAsyncClient.content = b"x" * (64 * 1024 + 1)
    monkeypatch.setattr("uai_forge.providers.httpx.AsyncClient", FakeAsyncClient)
    provider = provider_for(provider_cls)

    result = await provider.check(check_request(provider))

    assert result.code == "provider.response_too_large"
    assert CANARY not in result.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_cls", [OpenAICompatibleProvider, AnthropicMessagesProvider])
async def test_connection_tck_preserves_cancellation(provider_cls, monkeypatch):
    FakeAsyncClient.mode = "cancel"
    monkeypatch.setattr("uai_forge.providers.httpx.AsyncClient", FakeAsyncClient)
    provider = provider_for(provider_cls)
    task = asyncio.create_task(provider.check(check_request(provider)))

    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

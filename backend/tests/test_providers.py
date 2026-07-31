import pytest

from uai_forge.models import ModelBinding
from uai_forge.ports import ModelMessage, ModelRequest, ToolCall
from uai_forge.providers import (
    AnthropicMessagesProvider,
    OpenAICompatibleProvider,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeAsyncClient:
    response_payload = {}
    last_request = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, *, headers, json):
        self.__class__.last_request = {
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": self.kwargs.get("timeout"),
        }
        return FakeResponse(self.__class__.response_payload)


@pytest.mark.asyncio
async def test_openai_compatible_provider_maps_core_request(monkeypatch):
    FakeAsyncClient.response_payload = {
        "id": "chatcmpl_test",
        "model": "deepseek-r1",
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "lookup", "arguments": '{"q":"uai"}'},
                        }
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 8},
    }
    monkeypatch.setattr("uai_forge.providers.httpx.AsyncClient", FakeAsyncClient)
    binding = ModelBinding(
        model_config_id="cfg_openai",
        config={"base_url": "https://api.deepseek.com/v1", "timeout_seconds": 30},
    )
    binding._runtime_provider = "openai_compatible"
    binding._runtime_model = "deepseek-r1"
    binding._runtime_credential = "secret-not-persisted"
    provider = OpenAICompatibleProvider(binding)

    output = await provider.complete(
        ModelRequest(
            model="deepseek-r1",
            messages=[ModelMessage(role="user", content="call lookup")],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "lookup",
                        "description": "Find a record",
                        "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
                    },
                }
            ],
        )
    )

    request = FakeAsyncClient.last_request
    assert request["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert request["headers"]["Authorization"] == "Bearer secret-not-persisted"
    assert request["json"]["messages"] == [{"role": "user", "content": "call lookup"}]
    assert request["json"]["tools"][0]["function"]["name"] == "lookup"
    assert output.tool_calls[0].name == "lookup"
    assert output.tool_calls[0].arguments == {"q": "uai"}
    assert output.usage.total_tokens == 20


@pytest.mark.asyncio
async def test_anthropic_messages_provider_maps_tools_and_usage(monkeypatch):
    FakeAsyncClient.response_payload = {
        "id": "msg_test",
        "model": "claude-sonnet-5",
        "stop_reason": "tool_use",
        "content": [
            {"type": "text", "text": "先查一下。"},
            {"type": "tool_use", "id": "toolu_1", "name": "lookup", "input": {"q": "uai"}},
        ],
        "usage": {"input_tokens": 18, "output_tokens": 6},
    }
    monkeypatch.setattr("uai_forge.providers.httpx.AsyncClient", FakeAsyncClient)
    binding = ModelBinding(
        model_config_id="cfg_claude",
        config={"base_url": "https://api.anthropic.com", "max_tokens": 2048},
    )
    binding._runtime_provider = "anthropic_messages"
    binding._runtime_model = "claude-sonnet-5"
    binding._runtime_credential = "anthropic-secret"
    provider = AnthropicMessagesProvider(binding)

    output = await provider.complete(
        ModelRequest(
            model="claude-sonnet-5",
            messages=[
                ModelMessage(role="system", content="Be concise."),
                ModelMessage(role="user", content="查一下"),
                ModelMessage(
                    role="assistant",
                    tool_calls=[ToolCall(id="toolu_0", name="lookup", arguments={"q": "old"})],
                ),
                ModelMessage(role="tool", tool_call_id="toolu_0", content="旧结果"),
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "lookup",
                        "description": "Find a record",
                        "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
                    },
                }
            ],
        )
    )

    request = FakeAsyncClient.last_request
    assert request["url"] == "https://api.anthropic.com/v1/messages"
    assert request["headers"]["x-api-key"] == "anthropic-secret"
    assert request["headers"]["anthropic-version"] == "2023-06-01"
    assert request["json"]["system"] == "Be concise."
    assert request["json"]["messages"][0] == {"role": "user", "content": "查一下"}
    assert request["json"]["messages"][1]["role"] == "assistant"
    assert request["json"]["messages"][2]["content"][0]["type"] == "tool_result"
    assert request["json"]["tools"][0]["input_schema"]["type"] == "object"
    assert output.content == "先查一下。"
    assert output.tool_calls[0].arguments == {"q": "uai"}
    assert output.usage.total_tokens == 24

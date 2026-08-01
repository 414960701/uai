import pytest

from uai_forge.models import ModelBinding, ThinkingMode, ThinkingResolution
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


class FakeStreamingResponse:
    lines = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        for line in self.lines:
            yield line


class FakeStreamingClient:
    lines = []
    last_request = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def stream(self, method, url, *, headers, json):
        self.__class__.last_request = {
            "method": method,
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": self.kwargs.get("timeout"),
        }
        response = FakeStreamingResponse()
        response.lines = self.__class__.lines
        return response


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


@pytest.mark.asyncio
async def test_openai_compatible_provider_maps_reasoning_effort_without_leaking_preference(monkeypatch):
    FakeAsyncClient.response_payload = {
        "choices": [{"message": {"role": "assistant", "content": "深度回答"}}],
        "usage": {"prompt_tokens": 2, "completion_tokens": 3},
    }
    monkeypatch.setattr("uai_forge.providers.httpx.AsyncClient", FakeAsyncClient)
    binding = ModelBinding(
        model_config_id="cfg_reasoning",
        config={"base_url": "https://api.openai.com/v1"},
    )
    binding._runtime_provider = "openai_compatible"
    binding._runtime_model = "gpt-5.6-terra"
    binding._runtime_credential = "reasoning-secret"
    provider = OpenAICompatibleProvider(binding)

    output = await provider.complete(
        ModelRequest(
            model="gpt-5.6-terra",
            thinking_mode=ThinkingMode.ON,
            messages=[ModelMessage(role="user", content="请深度分析")],
        )
    )

    assert output.content == "深度回答"
    assert provider.thinking_resolution(
        ModelRequest(model="gpt-5.6-terra", messages=[], thinking_mode=ThinkingMode.ON)
    ) is ThinkingResolution.MAPPED
    assert FakeAsyncClient.last_request["json"]["reasoning_effort"] == "high"
    assert "thinking_mode" not in FakeAsyncClient.last_request["json"]


@pytest.mark.asyncio
async def test_openai_compatible_provider_maps_qwen_thinking_and_unknown_is_fail_safe(monkeypatch):
    FakeAsyncClient.response_payload = {"choices": [{"message": {"content": "回答"}}]}
    monkeypatch.setattr("uai_forge.providers.httpx.AsyncClient", FakeAsyncClient)
    binding = ModelBinding(
        model_config_id="cfg_qwen",
        config={"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    )
    binding._runtime_provider = "openai_compatible"
    binding._runtime_model = "qwen3.7-max"
    binding._runtime_credential = "qwen-secret"
    provider = OpenAICompatibleProvider(binding)

    await provider.complete(
        ModelRequest(
            model="qwen3.7-max",
            thinking_mode=ThinkingMode.OFF,
            messages=[ModelMessage(role="user", content="回答")],
        )
    )
    assert FakeAsyncClient.last_request["json"]["enable_thinking"] is False
    assert provider.thinking_resolution(
        ModelRequest(model="qwen3.7-max", messages=[], thinking_mode=ThinkingMode.OFF)
    ) is ThinkingResolution.MAPPED

    binding._runtime_model = "deepseek-chat"
    unknown_provider = OpenAICompatibleProvider(binding)
    await unknown_provider.complete(
        ModelRequest(
            model="deepseek-chat",
            thinking_mode=ThinkingMode.ON,
            messages=[ModelMessage(role="user", content="回答")],
        )
    )
    assert unknown_provider.thinking_resolution(
        ModelRequest(model="deepseek-chat", messages=[], thinking_mode=ThinkingMode.ON)
    ) is ThinkingResolution.UNSUPPORTED
    assert "reasoning_effort" not in FakeAsyncClient.last_request["json"]
    assert "enable_thinking" not in FakeAsyncClient.last_request["json"]


@pytest.mark.asyncio
async def test_anthropic_provider_bounds_extended_thinking_budget(monkeypatch):
    FakeAsyncClient.response_payload = {
        "content": [
            {"type": "thinking", "thinking": "private reasoning"},
            {"type": "text", "text": "公开回答"},
        ],
        "usage": {"input_tokens": 3, "output_tokens": 4},
    }
    monkeypatch.setattr("uai_forge.providers.httpx.AsyncClient", FakeAsyncClient)
    binding = ModelBinding(
        model_config_id="cfg_anthropic_thinking",
        config={"base_url": "https://api.anthropic.com", "max_tokens": 2048},
    )
    binding._runtime_provider = "anthropic_messages"
    binding._runtime_model = "claude-sonnet-5"
    binding._runtime_credential = "anthropic-secret"
    provider = AnthropicMessagesProvider(binding)

    output = await provider.complete(
        ModelRequest(
            model="claude-sonnet-5",
            thinking_mode=ThinkingMode.ON,
            messages=[ModelMessage(role="user", content="请分析")],
        )
    )

    assert FakeAsyncClient.last_request["json"]["thinking"] == {
        "type": "enabled",
        "budget_tokens": 2047,
    }
    assert output.content == "公开回答"
    assert "private reasoning" not in output.content


@pytest.mark.asyncio
async def test_openai_compatible_provider_streams_text_and_usage(monkeypatch):
    FakeStreamingClient.lines = [
        'data: {"choices":[{"delta":{"content":"先"}}]}',
        'data: {"choices":[{"delta":{"content":"回答"}}]}',
        'data: {"choices":[],"usage":{"prompt_tokens":7,"completion_tokens":3}}',
        "data: [DONE]",
    ]
    monkeypatch.setattr("uai_forge.providers.httpx.AsyncClient", FakeStreamingClient)
    binding = ModelBinding(
        model_config_id="cfg_stream_openai",
        config={"base_url": "https://api.deepseek.com/v1"},
    )
    binding._runtime_provider = "openai_compatible"
    binding._runtime_model = "deepseek-chat"
    binding._runtime_credential = "stream-secret"
    provider = OpenAICompatibleProvider(binding)

    chunks = [
        chunk
        async for chunk in provider.stream(
            ModelRequest(
                model="deepseek-chat",
                messages=[ModelMessage(role="user", content="hello")],
            )
        )
    ]

    assert "".join(chunk.text for chunk in chunks) == "先回答"
    usage = next(chunk.usage for chunk in chunks if chunk.usage is not None)
    assert usage.total_tokens == 10
    assert FakeStreamingClient.last_request["json"]["stream"] is True


@pytest.mark.asyncio
async def test_anthropic_messages_provider_streams_text_and_usage(monkeypatch):
    FakeStreamingClient.lines = [
        'event: message_start',
        'data: {"type":"message_start","message":{"usage":{"input_tokens":11}}}',
        'event: content_block_delta',
        'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"流式"}}',
        'data: {"type":"message_delta","usage":{"output_tokens":5}}',
        'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"完成"}}',
    ]
    monkeypatch.setattr("uai_forge.providers.httpx.AsyncClient", FakeStreamingClient)
    binding = ModelBinding(
        model_config_id="cfg_stream_anthropic",
        config={"base_url": "https://api.anthropic.com"},
    )
    binding._runtime_provider = "anthropic_messages"
    binding._runtime_model = "claude-sonnet-5"
    binding._runtime_credential = "stream-secret"
    provider = AnthropicMessagesProvider(binding)

    chunks = [
        chunk
        async for chunk in provider.stream(
            ModelRequest(
                model="claude-sonnet-5",
                messages=[ModelMessage(role="user", content="hello")],
            )
        )
    ]

    assert "".join(chunk.text for chunk in chunks) == "流式完成"
    assert any(chunk.usage and chunk.usage.input_tokens == 11 for chunk in chunks)
    assert any(chunk.usage and chunk.usage.output_tokens == 5 for chunk in chunks)


@pytest.mark.asyncio
async def test_openai_compatible_provider_streams_tools_without_exposing_arguments(monkeypatch):
    FakeStreamingClient.lines = [
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","type":"function","function":{"name":"lookup","arguments":"{\\"q\\":\\""}}]}}]}',
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"uai\\"}"}}]}}]}',
        'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}],"usage":{"prompt_tokens":7,"completion_tokens":4}}',
        "data: [DONE]",
    ]
    monkeypatch.setattr("uai_forge.providers.httpx.AsyncClient", FakeStreamingClient)
    binding = ModelBinding(
        model_config_id="cfg_stream_openai_tools",
        config={"base_url": "https://api.deepseek.com/v1"},
    )
    binding._runtime_provider = "openai_compatible"
    binding._runtime_model = "deepseek-chat"
    binding._runtime_credential = "stream-secret"
    provider = OpenAICompatibleProvider(binding)

    chunks = [
        chunk
        async for chunk in provider.stream(
            ModelRequest(
                model="deepseek-chat",
                messages=[ModelMessage(role="user", content="查一下")],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup",
                            "description": "Find a record",
                            "parameters": {"type": "object"},
                        },
                    }
                ],
            )
        )
    ]

    assert not "".join(chunk.text for chunk in chunks)
    calls = [call for chunk in chunks for call in chunk.tool_calls]
    assert len(calls) == 1
    assert calls[0].id == "call_1"
    assert calls[0].name == "lookup"
    assert calls[0].arguments == {"q": "uai"}
    assert FakeStreamingClient.last_request["json"]["tools"][0]["function"]["name"] == "lookup"


@pytest.mark.asyncio
async def test_anthropic_messages_provider_streams_tools_and_keeps_input_json_private(monkeypatch):
    FakeStreamingClient.lines = [
        'event: message_start',
        'data: {"type":"message_start","message":{"usage":{"input_tokens":11}}}',
        'data: {"type":"content_block_start","index":1,"content_block":{"type":"tool_use","id":"toolu_1","name":"lookup","input":{}}}',
        'data: {"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":"{\\"q\\":"}}',
        'data: {"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":"\\"uai\\"}"}}',
        'data: {"type":"message_delta","usage":{"output_tokens":5}}',
    ]
    monkeypatch.setattr("uai_forge.providers.httpx.AsyncClient", FakeStreamingClient)
    binding = ModelBinding(
        model_config_id="cfg_stream_anthropic_tools",
        config={"base_url": "https://api.anthropic.com"},
    )
    binding._runtime_provider = "anthropic_messages"
    binding._runtime_model = "claude-sonnet-5"
    binding._runtime_credential = "stream-secret"
    provider = AnthropicMessagesProvider(binding)

    chunks = [
        chunk
        async for chunk in provider.stream(
            ModelRequest(
                model="claude-sonnet-5",
                messages=[ModelMessage(role="user", content="查一下")],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup",
                            "description": "Find a record",
                            "parameters": {"type": "object"},
                        },
                    }
                ],
            )
        )
    ]

    calls = [call for chunk in chunks for call in chunk.tool_calls]
    assert len(calls) == 1
    assert calls[0].id == "toolu_1"
    assert calls[0].arguments == {"q": "uai"}
    assert FakeStreamingClient.last_request["json"]["tools"][0]["name"] == "lookup"

"""Built-in model providers."""

from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, Dict, List

import httpx

from .models import ModelBinding, PluginKind, PluginManifest
from .ports import ModelMessage, ModelOutput, ModelProvider, ModelRequest, TokenUsage, ToolCall


MOCK_MANIFEST = PluginManifest(
    id="mock",
    kind=PluginKind.PROVIDER,
    display_name="Deterministic test provider",
    version="1.0.0",
    description="Offline provider for demos, tests and repeatable contract checks.",
    capabilities=["tool_calling", "parallel_safe", "offline", "usage_estimate"],
    config_schema={"type": "object", "additionalProperties": False},
)

OPENAI_COMPATIBLE_MANIFEST = PluginManifest(
    id="openai_compatible",
    kind=PluginKind.PROVIDER,
    display_name="OpenAI-compatible HTTP",
    version="1.0.0",
    description="Adapter for OpenAI-compatible chat-completions endpoints.",
    capabilities=["tool_calling", "structured_messages", "usage_reporting"],
    config_schema={
        "type": "object",
        "properties": {
            "base_url": {"type": "string", "format": "uri"},
            "api_key_env": {"type": "string"},
            "timeout_seconds": {"type": "number", "minimum": 1, "maximum": 600},
            "headers": {"type": "object", "additionalProperties": {"type": "string"}},
        },
        "additionalProperties": False,
    },
)


class MockProvider(ModelProvider):
    manifest = MOCK_MANIFEST

    def __init__(self, binding: ModelBinding) -> None:
        self.binding = binding

    @staticmethod
    def _estimate_tokens(messages: List[ModelMessage], output: str) -> TokenUsage:
        input_chars = sum(len(message.content or "") for message in messages)
        return TokenUsage(
            input_tokens=max(1, input_chars // 4),
            output_tokens=max(1, len(output) // 4),
        )

    async def complete(self, request: ModelRequest) -> ModelOutput:
        last = request.messages[-1]
        if last.role == "tool":
            output = f"已完成协作，结果：{last.content or ''}"
            return ModelOutput(
                content=output,
                usage=self._estimate_tokens(request.messages, output),
            )

        user_text = next(
            (
                message.content or ""
                for message in reversed(request.messages)
                if message.role == "user"
            ),
            "",
        )
        available = {
            item.get("function", {}).get("name")
            for item in request.tools
            if item.get("function", {}).get("name")
        }

        delegate = re.search(r"delegate:([a-z][a-z0-9_-]*)\s+(.+)", user_text, re.DOTALL)
        if delegate:
            tool_name = f"delegate_{delegate.group(1)}"
            if tool_name in available:
                call = ToolCall(
                    id=f"call_{uuid.uuid4().hex[:12]}",
                    name=tool_name,
                    arguments={"input": delegate.group(2).strip()},
                )
                return ModelOutput(
                    tool_calls=[call],
                    usage=self._estimate_tokens(request.messages, ""),
                )

        explicit_tool = re.search(r"tool:([a-zA-Z0-9_.-]+)\s+(.+)", user_text, re.DOTALL)
        if explicit_tool:
            requested = explicit_tool.group(1).replace(".", "_").replace("-", "_")
            if requested in available:
                raw_arguments = explicit_tool.group(2).strip()
                try:
                    arguments = json.loads(raw_arguments)
                except json.JSONDecodeError:
                    arguments = {"input": raw_arguments, "expression": raw_arguments}
                return ModelOutput(
                    tool_calls=[
                        ToolCall(
                            id=f"call_{uuid.uuid4().hex[:12]}",
                            name=requested,
                            arguments=arguments,
                        )
                    ],
                    usage=self._estimate_tokens(request.messages, ""),
                )

        agent_name = request.metadata.get("agent_name", "Agent")
        output = f"{agent_name}：{user_text}"
        return ModelOutput(
            content=output,
            usage=self._estimate_tokens(request.messages, output),
        )


class OpenAICompatibleProvider(ModelProvider):
    manifest = OPENAI_COMPATIBLE_MANIFEST

    def __init__(self, binding: ModelBinding) -> None:
        self.binding = binding
        self.base_url = str(binding.config.get("base_url", "https://api.openai.com/v1")).rstrip("/")
        self.timeout = float(binding.config.get("timeout_seconds", 120))
        api_key_env = str(binding.config.get("api_key_env", "OPENAI_API_KEY"))
        self.api_key = os.environ.get(api_key_env)
        self.extra_headers = {
            str(key): str(value) for key, value in binding.config.get("headers", {}).items()
        }

    @staticmethod
    def _message_payload(message: ModelMessage) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"role": message.role, "content": message.content}
        if message.name:
            payload["name"] = message.name
        if message.tool_call_id:
            payload["tool_call_id"] = message.tool_call_id
        if message.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments, ensure_ascii=False),
                    },
                }
                for call in message.tool_calls
            ]
        return payload

    async def complete(self, request: ModelRequest) -> ModelOutput:
        if not self.api_key:
            api_key_env = self.binding.config.get("api_key_env", "OPENAI_API_KEY")
            raise RuntimeError(f"provider credential environment variable is not set: {api_key_env}")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.extra_headers,
        }
        payload: Dict[str, Any] = {
            "model": request.model,
            "messages": [self._message_payload(item) for item in request.messages],
        }
        if request.tools:
            payload["tools"] = request.tools

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            raw = response.json()

        choice = raw.get("choices", [{}])[0]
        message = choice.get("message", {})
        tool_calls: List[ToolCall] = []
        for raw_call in message.get("tool_calls") or []:
            function = raw_call.get("function", {})
            arguments = function.get("arguments") or "{}"
            try:
                parsed = json.loads(arguments)
            except json.JSONDecodeError:
                parsed = {"raw": arguments}
            tool_calls.append(
                ToolCall(
                    id=raw_call.get("id") or f"call_{uuid.uuid4().hex[:12]}",
                    name=function.get("name", ""),
                    arguments=parsed,
                )
            )
        usage = raw.get("usage") or {}
        return ModelOutput(
            content=message.get("content") or "",
            tool_calls=tool_calls,
            usage=TokenUsage(
                input_tokens=int(usage.get("prompt_tokens") or 0),
                output_tokens=int(usage.get("completion_tokens") or 0),
            ),
            raw={
                "id": raw.get("id"),
                "finish_reason": choice.get("finish_reason"),
                "model": raw.get("model"),
            },
        )


def create_mock_provider(binding: ModelBinding) -> ModelProvider:
    return MockProvider(binding)


def create_openai_compatible_provider(binding: ModelBinding) -> ModelProvider:
    return OpenAICompatibleProvider(binding)

"""Built-in model providers."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List

import httpx

from .models import ModelBinding, ModelCatalogEntry, PluginKind, PluginManifest
from .ports import ModelMessage, ModelOutput, ModelProvider, ModelRequest, TokenUsage, ToolCall


OPENAI_COMPATIBLE_MANIFEST = PluginManifest(
    id="openai_compatible",
    kind=PluginKind.PROVIDER,
    display_name="OpenAI-compatible HTTP",
    version="1.0.0",
    description="Adapter for OpenAI-compatible chat-completions endpoints.",
    capabilities=["tool_calling", "structured_messages", "usage_reporting"],
    api_protocol="openai_chat_completions",
    credential_required=True,
    homepage="https://platform.openai.com/docs/models",
    model_catalog=[
        ModelCatalogEntry(
            id="gpt-5.6-sol",
            label="GPT-5.6 Sol",
            description="复杂推理与编码的旗舰模型",
            tier="latest",
            source_url="https://platform.openai.com/docs/models/gpt-5.6-sol",
        ),
        ModelCatalogEntry(
            id="gpt-5.6-terra",
            label="GPT-5.6 Terra",
            description="智能与成本平衡",
            tier="latest",
            source_url="https://platform.openai.com/docs/models/gpt-5.6-terra",
        ),
        ModelCatalogEntry(
            id="gpt-5.6-luna",
            label="GPT-5.6 Luna",
            description="高并发、成本敏感任务",
            tier="latest",
            source_url="https://platform.openai.com/docs/models/gpt-5.6-luna",
        ),
        ModelCatalogEntry(
            id="gpt-4o",
            label="GPT-4o",
            description="成熟的通用多模态模型",
            tier="popular",
            source_url="https://platform.openai.com/docs/models",
        ),
        ModelCatalogEntry(
            id="gpt-4o-mini",
            label="GPT-4o mini",
            description="轻量、快速、成本友好",
            tier="popular",
            source_url="https://platform.openai.com/docs/models",
        ),
        ModelCatalogEntry(
            id="deepseek-v4-pro",
            label="DeepSeek V4 Pro",
            description="DeepSeek 最新高性能模型（OpenAI 兼容）",
            tier="latest",
            source_url="https://api-docs.deepseek.com/quick_start/pricing",
        ),
        ModelCatalogEntry(
            id="deepseek-v4-flash",
            label="DeepSeek V4 Flash",
            description="DeepSeek 高速模型（OpenAI 兼容）",
            tier="latest",
            source_url="https://api-docs.deepseek.com/quick_start/pricing",
        ),
        ModelCatalogEntry(id="deepseek-v3.2", label="DeepSeek V3.2", description="通用对话与代码", tier="latest", source_url="https://api-docs.deepseek.com/"),
        ModelCatalogEntry(id="deepseek-v3.1", label="DeepSeek V3.1", description="通用与工具调用", tier="latest", source_url="https://api-docs.deepseek.com/"),
        ModelCatalogEntry(id="deepseek-v3", label="DeepSeek V3", description="成熟通用模型", tier="popular", source_url="https://api-docs.deepseek.com/"),
        ModelCatalogEntry(id="deepseek-r1", label="DeepSeek R1", description="深度推理模型", tier="popular", source_url="https://api-docs.deepseek.com/"),
        ModelCatalogEntry(id="deepseek-r1-0528", label="DeepSeek R1 0528", description="推理增强版本", tier="popular", source_url="https://api-docs.deepseek.com/"),
        ModelCatalogEntry(
            id="deepseek-chat",
            label="DeepSeek Chat",
            description="DeepSeek 通用对话模型",
            tier="popular",
            source_url="https://api-docs.deepseek.com/",
        ),
        ModelCatalogEntry(
            id="deepseek-reasoner",
            label="DeepSeek Reasoner",
            description="DeepSeek 推理模型",
            tier="popular",
            source_url="https://api-docs.deepseek.com/",
        ),
        ModelCatalogEntry(
            id="qwen3.7-max",
            label="通义千问 Qwen3.7 Max",
            description="百炼旗舰通用模型（OpenAI 兼容）",
            tier="latest",
            source_url="https://help.aliyun.com/zh/model-studio/getting-started/models",
        ),
        ModelCatalogEntry(
            id="qwen3.8-max-preview",
            label="通义千问 Qwen3.8 Max Preview",
            description="百炼最新旗舰预览模型（OpenAI 兼容）",
            tier="latest",
            source_url="https://help.aliyun.com/zh/model-studio/models",
        ),
        ModelCatalogEntry(
            id="qwen3.7-plus",
            label="通义千问 Qwen3.7 Plus",
            description="百炼通用长文本模型（OpenAI 兼容）",
            tier="latest",
            source_url="https://help.aliyun.com/zh/model-studio/models",
        ),
        ModelCatalogEntry(
            id="qwen3.7-flash",
            label="通义千问 Qwen3.7 Flash",
            description="百炼高速低延迟模型（OpenAI 兼容）",
            tier="latest",
            source_url="https://help.aliyun.com/zh/model-studio/models",
        ),
        ModelCatalogEntry(
            id="qwen3.5-omni-plus",
            label="通义千问 Qwen3.5 Omni Plus",
            description="通用多模态对话模型（OpenAI 兼容）",
            tier="latest",
            source_url="https://help.aliyun.com/zh/model-studio/models",
        ),
        ModelCatalogEntry(
            id="qwen3.5-plus",
            label="通义千问 Qwen3.5 Plus",
            description="百炼通用模型（OpenAI 兼容）",
            tier="latest",
            source_url="https://help.aliyun.com/zh/model-studio/getting-started/models",
        ),
        ModelCatalogEntry(id="qwen3-max", label="通义千问 Qwen3 Max", description="百炼旗舰通用", tier="latest", source_url="https://help.aliyun.com/zh/model-studio/getting-started/models"),
        ModelCatalogEntry(id="qwen3-235b-a22b", label="Qwen3 235B A22B", description="开源大规模 MoE", tier="latest", source_url="https://help.aliyun.com/zh/model-studio/getting-started/models"),
        ModelCatalogEntry(id="qwen3-32b", label="Qwen3 32B", description="开源通用模型", tier="popular", source_url="https://help.aliyun.com/zh/model-studio/getting-started/models"),
        ModelCatalogEntry(id="qwen3-30b-a3b", label="Qwen3 30B A3B", description="高性价比 MoE", tier="popular", source_url="https://help.aliyun.com/zh/model-studio/getting-started/models"),
        ModelCatalogEntry(id="qwen3-coder-plus", label="Qwen3-Coder-Plus", description="代码与 Agent 任务", tier="latest", source_url="https://help.aliyun.com/zh/model-studio/getting-started/models"),
        ModelCatalogEntry(id="qwen3-coder", label="Qwen3-Coder", description="开源代码模型", tier="popular", source_url="https://help.aliyun.com/zh/model-studio/getting-started/models"),
        ModelCatalogEntry(id="qwen3-vl-plus", label="Qwen3-VL-Plus", description="视觉理解与文档", tier="latest", source_url="https://help.aliyun.com/zh/model-studio/getting-started/models"),
        ModelCatalogEntry(id="qwen2.5-max", label="通义千问 Qwen2.5 Max", description="成熟旗舰", tier="popular", source_url="https://help.aliyun.com/zh/model-studio/getting-started/models"),
        ModelCatalogEntry(id="qwen2.5-72b-instruct", label="Qwen2.5 72B Instruct", description="开源通用模型", tier="popular", source_url="https://help.aliyun.com/zh/model-studio/getting-started/models"),
        ModelCatalogEntry(
            id="qwen-plus",
            label="通义千问 Plus",
            description="通用任务与长文本",
            tier="popular",
            source_url="https://help.aliyun.com/zh/model-studio/getting-started/models",
        ),
        ModelCatalogEntry(
            id="qwen-turbo",
            label="通义千问 Turbo",
            description="高并发、低延迟",
            tier="popular",
            source_url="https://help.aliyun.com/zh/model-studio/getting-started/models",
        ),
        ModelCatalogEntry(
            id="kimi-k3",
            label="Kimi K3",
            description="月之暗面新一代通用模型",
            tier="latest",
            source_url="https://platform.moonshot.cn/docs/intro",
        ),
        ModelCatalogEntry(
            id="kimi-k2.6",
            label="Kimi K2.6",
            description="Kimi 通用与工具调用模型",
            tier="latest",
            source_url="https://platform.moonshot.cn/docs/intro",
        ),
        ModelCatalogEntry(
            id="kimi-k2.7-code",
            label="Kimi K2.7 Code",
            description="Kimi 编程与 Agent 模型",
            tier="latest",
            source_url="https://platform.kimi.com/docs/guide/kimi-k2-7-code-quickstart",
        ),
        ModelCatalogEntry(
            id="kimi-k2.7-code-highspeed",
            label="Kimi K2.7 Code Highspeed",
            description="Kimi 高速编程模型",
            tier="latest",
            source_url="https://platform.kimi.com/docs/guide/kimi-k2-7-code-quickstart",
        ),
        ModelCatalogEntry(
            id="kimi-k2-thinking-turbo",
            label="Kimi K2 Thinking Turbo",
            description="Kimi 高速推理与工具调用模型",
            tier="latest",
            source_url="https://platform.kimi.com/docs/models",
        ),
        ModelCatalogEntry(id="kimi-k2-thinking", label="Kimi K2 Thinking", description="长链路推理与工具调用", tier="latest", source_url="https://platform.moonshot.cn/docs/intro"),
        ModelCatalogEntry(id="kimi-k2-instruct", label="Kimi K2 Instruct", description="通用指令模型", tier="popular", source_url="https://platform.moonshot.cn/docs/intro"),
        ModelCatalogEntry(
            id="kimi-k2.5",
            label="Kimi K2.5",
            description="Kimi 多模态/通用模型",
            tier="popular",
            source_url="https://platform.moonshot.cn/docs/intro",
        ),
        ModelCatalogEntry(id="moonshot-v1-128k", label="Moonshot V1 128K", description="超长上下文", tier="popular", source_url="https://platform.moonshot.cn/docs/intro"),
        ModelCatalogEntry(id="moonshot-v1-32k", label="Moonshot V1 32K", description="长文本通用模型", tier="popular", source_url="https://platform.moonshot.cn/docs/intro"),
        ModelCatalogEntry(
            id="glm-5.2",
            label="智谱 GLM-5.2",
            description="智谱新一代旗舰模型",
            tier="latest",
            source_url="https://open.bigmodel.cn/dev/api",
        ),
        ModelCatalogEntry(
            id="glm-5.1",
            label="智谱 GLM-5.1",
            description="复杂任务与推理",
            tier="latest",
            source_url="https://open.bigmodel.cn/dev/api",
        ),
        ModelCatalogEntry(
            id="glm-5-turbo",
            label="智谱 GLM-5 Turbo",
            description="高并发通用模型",
            tier="latest",
            source_url="https://docs.bigmodel.cn/cn/guide/start/model-overview",
        ),
        ModelCatalogEntry(
            id="glm-5",
            label="智谱 GLM-5",
            description="通用旗舰模型",
            tier="popular",
            source_url="https://open.bigmodel.cn/dev/api",
        ),
        ModelCatalogEntry(id="glm-4.6", label="智谱 GLM-4.6", description="通用与 Agent", tier="latest", source_url="https://open.bigmodel.cn/dev/api"),
        ModelCatalogEntry(id="glm-4.7-flash", label="智谱 GLM-4.7 Flash", description="高速通用模型", tier="latest", source_url="https://docs.bigmodel.cn/cn/guide/start/model-overview"),
        ModelCatalogEntry(id="glm-4.5", label="智谱 GLM-4.5", description="通用与推理", tier="popular", source_url="https://open.bigmodel.cn/dev/api"),
        ModelCatalogEntry(id="glm-4.5-air", label="智谱 GLM-4.5-Air", description="轻量快速", tier="popular", source_url="https://open.bigmodel.cn/dev/api"),
        ModelCatalogEntry(id="glm-4.5-flash", label="智谱 GLM-4.5 Flash", description="高性价比高速模型", tier="popular", source_url="https://docs.bigmodel.cn/cn/guide/start/model-overview"),
        ModelCatalogEntry(id="glm-4.6v", label="智谱 GLM-4.6V", description="视觉理解与文档", tier="latest", source_url="https://docs.bigmodel.cn/cn/guide/start/model-overview"),
        ModelCatalogEntry(id="glm-4.6v-flash", label="智谱 GLM-4.6V Flash", description="高速视觉理解", tier="latest", source_url="https://docs.bigmodel.cn/cn/guide/start/model-overview"),
        ModelCatalogEntry(
            id="glm-4.7",
            label="智谱 GLM-4.7",
            description="成熟通用模型",
            tier="popular",
            source_url="https://open.bigmodel.cn/dev/api",
        ),
        ModelCatalogEntry(id="ernie-4.5-turbo-128k", label="文心 ERNIE 4.5 Turbo", description="百度大模型", tier="latest", source_url="https://cloud.baidu.com/doc/WENXINWORKSHOP/index.html"),
        ModelCatalogEntry(id="ernie-4.5-8k", label="文心 ERNIE 4.5", description="百度通用模型", tier="popular", source_url="https://cloud.baidu.com/doc/WENXINWORKSHOP/index.html"),
        ModelCatalogEntry(id="doubao-seed-1-6-250615", label="豆包 Seed 1.6", description="字节跳动通用模型", tier="latest", source_url="https://www.volcengine.com/docs/82379/1330310"),
        ModelCatalogEntry(id="doubao-seed-1-6-thinking-250615", label="豆包 Seed 1.6 Thinking", description="复杂推理", tier="latest", source_url="https://www.volcengine.com/docs/82379/1330310"),
        ModelCatalogEntry(id="doubao-seed-2-1-pro", label="豆包 Seed 2.1 Pro", description="新一代通用旗舰", tier="latest", source_url="https://docs.volcengine.com/docs/82379/1330310?lang=zh"),
        ModelCatalogEntry(id="doubao-seed-2-1-turbo", label="豆包 Seed 2.1 Turbo", description="高速通用模型", tier="latest", source_url="https://docs.volcengine.com/docs/82379/1330310?lang=zh"),
        ModelCatalogEntry(id="doubao-seed-2-0-pro", label="豆包 Seed 2.0 Pro", description="通用旗舰模型", tier="latest", source_url="https://docs.volcengine.com/docs/82379/1330310?lang=zh"),
        ModelCatalogEntry(id="doubao-seed-2-0-lite", label="豆包 Seed 2.0 Lite", description="轻量高性价比模型", tier="popular", source_url="https://docs.volcengine.com/docs/82379/1330310?lang=zh"),
        ModelCatalogEntry(id="doubao-seed-2-0-mini", label="豆包 Seed 2.0 Mini", description="低延迟轻量模型", tier="popular", source_url="https://docs.volcengine.com/docs/82379/1330310?lang=zh"),
        ModelCatalogEntry(id="doubao-seed-1-6-flash", label="豆包 Seed 1.6 Flash", description="高速对话模型", tier="popular", source_url="https://docs.volcengine.com/docs/82379/1330310?lang=zh"),
        ModelCatalogEntry(id="doubao-seed-code", label="豆包 Seed Code", description="代码与 Agent 任务", tier="latest", source_url="https://docs.volcengine.com/docs/82379/1330310?lang=zh"),
        ModelCatalogEntry(id="doubao-1-5-pro-32k", label="豆包 1.5 Pro 32K", description="成熟通用模型", tier="popular", source_url="https://www.volcengine.com/docs/82379/1330310"),
        ModelCatalogEntry(id="hunyuan-t1", label="腾讯混元 T1", description="推理模型", tier="latest", source_url="https://cloud.tencent.com/document/product/1729"),
        ModelCatalogEntry(id="hunyuan-turbos", label="腾讯混元 Turbo S", description="高速通用模型", tier="popular", source_url="https://cloud.tencent.com/document/product/1729"),
        ModelCatalogEntry(id="hunyuan-pro", label="腾讯混元 Pro", description="通用旗舰", tier="popular", source_url="https://cloud.tencent.com/document/product/1729"),
        ModelCatalogEntry(id="MiniMax-M2", label="MiniMax M2", description="Agent 与代码任务", tier="latest", source_url="https://platform.minimaxi.com/document"),
        ModelCatalogEntry(id="MiniMax-M1", label="MiniMax M1", description="长思考推理", tier="popular", source_url="https://platform.minimaxi.com/document"),
        ModelCatalogEntry(id="MiniMax-M3", label="MiniMax M3", description="新一代通用与 Agent 模型", tier="latest", source_url="https://platform.minimaxi.com/document/Models"),
        ModelCatalogEntry(id="MiniMax-M2.7", label="MiniMax M2.7", description="通用推理与代码模型", tier="latest", source_url="https://platform.minimaxi.com/document/Models"),
        ModelCatalogEntry(id="MiniMax-M2.7-highspeed", label="MiniMax M2.7 Highspeed", description="高速推理与代码模型", tier="latest", source_url="https://platform.minimaxi.com/document/Models"),
        ModelCatalogEntry(id="MiniMax-M2.5", label="MiniMax M2.5", description="通用对话模型", tier="popular", source_url="https://platform.minimaxi.com/document/Models"),
        ModelCatalogEntry(id="MiniMax-M2.1", label="MiniMax M2.1", description="通用推理模型", tier="popular", source_url="https://platform.minimaxi.com/document/Models"),
        ModelCatalogEntry(id="abab6.5s-chat", label="MiniMax abab6.5s", description="通用对话", tier="legacy", source_url="https://platform.minimaxi.com/document"),
        ModelCatalogEntry(id="Baichuan4", label="百川 Baichuan4", description="国产通用模型", tier="latest", source_url="https://platform.baichuan-ai.com/docs/api"),
        ModelCatalogEntry(id="Baichuan3-Turbo", label="百川 Baichuan3 Turbo", description="高速通用模型", tier="popular", source_url="https://platform.baichuan-ai.com/docs/api"),
        ModelCatalogEntry(id="yi-lightning", label="零一万物 Yi-Lightning", description="高速推理", tier="popular", source_url="https://platform.lingyiwanwu.com/docs"),
        ModelCatalogEntry(id="yi-large", label="零一万物 Yi-Large", description="通用旗舰", tier="popular", source_url="https://platform.lingyiwanwu.com/docs"),
        ModelCatalogEntry(id="step-3.5-flash", label="阶跃星辰 Step-3.5-Flash", description="高速推理", tier="latest", source_url="https://platform.stepfun.com/docs"),
        ModelCatalogEntry(id="step-2-16k", label="阶跃星辰 Step-2", description="通用模型", tier="popular", source_url="https://platform.stepfun.com/docs"),
        ModelCatalogEntry(id="internlm3-latest", label="书生·浦语 InternLM3", description="开源通用模型", tier="popular", source_url="https://internlm.intern-ai.org.cn/api"),
        ModelCatalogEntry(id="SenseNova-V6", label="商汤日日新 SenseNova V6", description="国产通用模型", tier="popular", source_url="https://console.sensetime.com/help"),
    ],
    config_schema={
        "type": "object",
        "properties": {
            "base_url": {"type": "string", "format": "uri"},
            "timeout_seconds": {"type": "number", "minimum": 1, "maximum": 600},
            "headers": {"type": "object", "additionalProperties": {"type": "string"}},
            "max_tokens": {"type": "integer", "minimum": 1, "maximum": 200000},
            "temperature": {"type": "number", "minimum": 0, "maximum": 2},
            "top_p": {"type": "number", "exclusiveMinimum": 0, "maximum": 1},
        },
        "additionalProperties": False,
    },
)


ANTHROPIC_MESSAGES_MANIFEST = PluginManifest(
    id="anthropic_messages",
    kind=PluginKind.PROVIDER,
    display_name="Anthropic Claude Messages",
    version="1.0.0",
    description="Adapter for Anthropic Claude Messages API.",
    capabilities=["tool_calling", "structured_messages", "usage_reporting", "system_messages"],
    api_protocol="anthropic_messages",
    credential_required=True,
    homepage="https://docs.anthropic.com/en/docs/about-claude/models/overview",
    model_catalog=[
        ModelCatalogEntry(
            id="claude-opus-5",
            label="Claude Opus 5",
            description="复杂 Agent、编码与企业任务",
            tier="latest",
            source_url="https://docs.anthropic.com/en/docs/about-claude/models/overview",
        ),
        ModelCatalogEntry(
            id="claude-sonnet-5",
            label="Claude Sonnet 5",
            description="速度与智能的平衡",
            tier="latest",
            source_url="https://docs.anthropic.com/en/docs/about-claude/models/overview",
        ),
        ModelCatalogEntry(
            id="claude-haiku-4-5-20251001",
            label="Claude Haiku 4.5",
            description="快速、高性价比模型",
            tier="latest",
            source_url="https://docs.anthropic.com/en/docs/about-claude/models/overview",
        ),
        ModelCatalogEntry(
            id="claude-opus-4-8",
            label="Claude Opus 4.8",
            description="上一代高性能 Agent 模型",
            tier="popular",
            source_url="https://docs.anthropic.com/en/docs/about-claude/models/overview",
        ),
        ModelCatalogEntry(
            id="claude-opus-4-7",
            label="Claude Opus 4.7",
            description="上一代复杂任务模型",
            tier="popular",
            source_url="https://docs.anthropic.com/en/docs/about-claude/models/overview",
        ),
        ModelCatalogEntry(
            id="claude-opus-4-6",
            label="Claude Opus 4.6",
            description="稳定的 Opus 版本",
            tier="popular",
            source_url="https://docs.anthropic.com/en/docs/about-claude/models/overview",
        ),
        ModelCatalogEntry(
            id="claude-sonnet-4-6",
            label="Claude Sonnet 4.6",
            description="稳定的 Sonnet 版本",
            tier="popular",
            source_url="https://docs.anthropic.com/en/docs/about-claude/models/overview",
        ),
        ModelCatalogEntry(
            id="claude-sonnet-4-5",
            label="Claude Sonnet 4.5",
            description="兼容旧应用的 Sonnet 版本",
            tier="legacy",
            source_url="https://docs.anthropic.com/en/docs/about-claude/models/overview",
        ),
    ],
    config_schema={
        "type": "object",
        "properties": {
            "base_url": {"type": "string", "format": "uri"},
            "timeout_seconds": {"type": "number", "minimum": 1, "maximum": 600},
            "headers": {"type": "object", "additionalProperties": {"type": "string"}},
            "anthropic_version": {"type": "string", "minLength": 1, "maxLength": 40},
            "max_tokens": {"type": "integer", "minimum": 1, "maximum": 200000},
            "temperature": {"type": "number", "minimum": 0, "maximum": 1},
            "top_p": {"type": "number", "exclusiveMinimum": 0, "maximum": 1},
        },
        "additionalProperties": False,
    },
)


class OpenAICompatibleProvider(ModelProvider):
    manifest = OPENAI_COMPATIBLE_MANIFEST

    def __init__(self, binding: ModelBinding) -> None:
        self.binding = binding
        self.base_url = str(binding.config.get("base_url", "https://api.openai.com/v1")).rstrip("/")
        self.timeout = float(binding.config.get("timeout_seconds", 120))
        # Credentials are resolved from the tenant-scoped database profile by
        # the runtime and attached only to this short-lived provider instance.
        self.api_key = getattr(binding, "_runtime_credential", None)
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
            raise RuntimeError("provider credential profile is unavailable")

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


class AnthropicMessagesProvider(ModelProvider):
    manifest = ANTHROPIC_MESSAGES_MANIFEST

    def __init__(self, binding: ModelBinding) -> None:
        self.binding = binding
        self.base_url = str(binding.config.get("base_url", "https://api.anthropic.com")).rstrip("/")
        self.timeout = float(binding.config.get("timeout_seconds", 120))
        self.api_key = getattr(binding, "_runtime_credential", None)
        self.anthropic_version = str(binding.config.get("anthropic_version", "2023-06-01"))
        self.extra_headers = {
            str(key): str(value) for key, value in binding.config.get("headers", {}).items()
        }

    @staticmethod
    def _messages_payload(messages: List[ModelMessage]) -> tuple[str, List[Dict[str, Any]]]:
        system: List[str] = []
        result: List[Dict[str, Any]] = []
        for message in messages:
            if message.role == "system":
                if message.content:
                    system.append(message.content)
                continue
            if message.role == "tool":
                result.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": message.tool_call_id or "unknown",
                                "content": message.content or "",
                            }
                        ],
                    }
                )
                continue
            if message.tool_calls:
                blocks: List[Dict[str, Any]] = []
                if message.content:
                    blocks.append({"type": "text", "text": message.content})
                blocks.extend(
                    {
                        "type": "tool_use",
                        "id": call.id,
                        "name": call.name,
                        "input": call.arguments,
                    }
                    for call in message.tool_calls
                )
                result.append({"role": "assistant", "content": blocks})
                continue
            result.append(
                {
                    "role": "assistant" if message.role == "assistant" else "user",
                    "content": message.content or "",
                }
            )
        return "\n\n".join(system), result

    @staticmethod
    def _tools_payload(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        converted: List[Dict[str, Any]] = []
        for tool in tools:
            function = tool.get("function", tool)
            converted.append(
                {
                    "name": function.get("name", ""),
                    "description": function.get("description", ""),
                    "input_schema": function.get("parameters")
                    or {"type": "object", "properties": {}},
                }
            )
        return converted

    async def complete(self, request: ModelRequest) -> ModelOutput:
        if not self.api_key:
            raise RuntimeError("model configuration secret is unavailable")

        system, messages = self._messages_payload(request.messages)
        payload: Dict[str, Any] = {
            "model": request.model,
            "max_tokens": int(self.binding.config.get("max_tokens", 4096)),
            "messages": messages,
        }
        if system:
            payload["system"] = system
        if request.tools:
            payload["tools"] = self._tools_payload(request.tools)
        for key in ("temperature", "top_p"):
            if key in self.binding.config:
                payload[key] = self.binding.config[key]

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
            "Content-Type": "application/json",
            **self.extra_headers,
        }
        endpoint = f"{self.base_url}/messages" if self.base_url.endswith("/v1") else f"{self.base_url}/v1/messages"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            raw = response.json()

        text_parts: List[str] = []
        tool_calls: List[ToolCall] = []
        for block in raw.get("content") or []:
            if block.get("type") == "text":
                text_parts.append(block.get("text") or "")
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id") or f"call_{uuid.uuid4().hex[:12]}",
                        name=block.get("name", ""),
                        arguments=block.get("input") or {},
                    )
                )
        usage = raw.get("usage") or {}
        return ModelOutput(
            content="".join(text_parts),
            tool_calls=tool_calls,
            usage=TokenUsage(
                input_tokens=int(usage.get("input_tokens") or 0),
                output_tokens=int(usage.get("output_tokens") or 0),
            ),
            raw={
                "id": raw.get("id"),
                "stop_reason": raw.get("stop_reason"),
                "model": raw.get("model"),
            },
        )


def create_openai_compatible_provider(binding: ModelBinding) -> ModelProvider:
    return OpenAICompatibleProvider(binding)


def create_anthropic_messages_provider(binding: ModelBinding) -> ModelProvider:
    return AnthropicMessagesProvider(binding)

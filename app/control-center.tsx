"use client";

import {
  Activity,
  ArrowRight,
  Blocks,
  Bot,
  Box,
  Braces,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleGauge,
  Clock3,
  Cloud,
  Code2,
  Cpu,
  Database,
  GitBranch,
  KeyRound,
  Layers3,
  LayoutDashboard,
  Link2,
  LoaderCircle,
  Menu,
  Network,
  OctagonAlert,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Server,
  Settings,
  ShieldCheck,
  Sparkles,
  Square,
  TerminalSquare,
  Workflow,
  X,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ApiProblem,
  apiRequest,
  consumeEventStream,
  headersFor,
  problemMessage,
} from "./control-center/api";
import { useDialogAccessibility } from "./control-center/components/dialog";
import { ProblemNotice } from "./control-center/components/problem-notice";
import {
  mergeRunEvents,
  terminalStatusForEvent,
  type RunEvent,
} from "./control-center/features/runs/reducer";
import {
  PrerequisiteGate,
  type ReadinessIssue,
} from "./control-center/features/setup/prerequisite";
import { markResourceError, type ResourceState } from "./control-center/resource-state";

type View =
  | "overview"
  | "agents"
  | "instances"
  | "topology"
  | "runs"
  | "plugins"
  | "model-configs"
  | "settings";
type ConnectionMode = "connecting" | "live" | "disconnected";

type SetupAction =
  | "connect"
  | "create_model_config"
  | "verify_model_config"
  | "create_agent"
  | "run_agent"
  | "none";

type SetupResourceSummary = {
  total: number;
  runnable: number;
  verified_enabled: number;
  active: number;
  ready: number;
  blocking_issues: ReadinessIssue[];
  last_terminal_at?: string | null;
};

type SetupStatus = {
  connection: "connected" | "unauthorized" | "incompatible" | "unavailable";
  model_connections: SetupResourceSummary;
  agents: SetupResourceSummary;
  instances: SetupResourceSummary;
  runs: SetupResourceSummary;
  next_action: SetupAction;
};

type CapabilityStatus = {
  id: string;
  state: "implemented" | "partial" | "planned" | "unavailable";
  summary: string;
  limits: string[];
  evidence_refs: string[];
};

function problemFromRefreshError(error: unknown): { message: string; problem?: { code?: string } } {
  if (error instanceof ApiProblem) return error;
  return { message: problemMessage(error, "资源暂时不可用") };
}

type ChildMount = {
  alias: string;
  agent_id: string;
  description?: string;
  revision?: number;
  max_concurrency?: number;
  input_template?: string;
  allowed_tools?: string[] | null;
};

type ToolBindingSpec = {
  plugin_id: string;
  alias?: string;
  enabled?: boolean;
  permission?: "auto" | "confirm" | "deny";
  config?: Record<string, unknown>;
};

type MemoryBindingSpec = {
  plugin_id: string;
  enabled?: boolean;
  config?: Record<string, unknown>;
};

type MiddlewareBindingSpec = {
  plugin_id: string;
  enabled?: boolean;
  config?: Record<string, unknown>;
};

type AgentSpec = {
  id: string;
  name: string;
  description: string;
  revision: number;
  enabled: boolean;
  system_prompt: string;
  model: {
    model_config_id: string;
    config?: Record<string, unknown>;
  };
  tools: ToolBindingSpec[];
  children: ChildMount[];
  memory?: MemoryBindingSpec;
  middlewares?: MiddlewareBindingSpec[];
  policy: {
    max_steps: number;
    max_depth: number;
    max_tool_calls: number;
    max_parallel_children: number;
    timeout_seconds: number;
    token_budget: number;
  };
  labels: Record<string, string>;
};

type AgentInstance = {
  id: string;
  name: string;
  agent_id: string;
  agent_revision?: number;
  environment: string;
  status: string;
  max_concurrency: number;
};

type RunRecord = {
  id: string;
  agent_id: string;
  instance_id?: string;
  session_id: string;
  status: string;
  input: string;
  output?: string;
  error?: string;
  created_at: string;
  finished_at?: string;
  metrics?: Record<string, unknown>;
};

type PluginManifest = {
  id: string;
  kind: string;
  display_name: string;
  version: string;
  protocol_version: string;
  description: string;
  capabilities: string[];
  api_protocol?: string;
  credential_required?: boolean;
  model_catalog?: Array<{
    id: string;
    label: string;
    description?: string;
    tier?: "latest" | "popular" | "legacy";
    source_url?: string;
  }>;
  config_schema?: Record<string, unknown>;
  available: boolean;
  source: string;
  connection_check?: "none" | "local" | "remote";
  connection_schema_version?: string;
  ui_hints?: Record<string, unknown>;
  catalog_version?: string | null;
  catalog_updated_at?: string | null;
};

type ModelConfig = {
  id: string;
  tenant_id?: string;
  name: string;
  provider: string;
  protocol: string;
  masked_secret: string;
  model: string;
  base_url?: string | null;
  config?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  enabled: boolean;
  version: number;
  lifecycle: "draft" | "verified" | "enabled" | "disabled" | "error";
  verification: {
    status: "never" | "passed" | "failed";
    checked_at?: string | null;
    code?: string | null;
    latency_ms?: number | null;
    endpoint_summary?: string | null;
  };
};

type ModelConnectionCheckResult = {
  status: "passed" | "failed" | "partial";
  code: string;
  checked_at: string;
  latency_ms?: number | null;
  endpoint_summary?: string | null;
  provider: string;
  model: string;
};

type ModelConfigReferences = {
  items: Array<{ agent_id: string; agent_name: string; revision: number; path: string }>;
  total: number;
  next_cursor?: string | null;
};

type RuntimeConfigEntry = {
  key: string;
  value: unknown;
  version: number;
  updated_at: string;
};

type AgentConfigurationForm = {
  name: string;
  description: string;
  systemPrompt: string;
  modelConfigId: string;
  tools: ToolBindingSpec[];
  children: ChildMount[];
  memory: MemoryBindingSpec;
  middlewares: MiddlewareBindingSpec[];
  policy: AgentSpec["policy"];
  enabled: boolean;
};

type NewAgentForm = AgentConfigurationForm;

type ActivityItem = {
  id: string;
  time: string;
  title: string;
  detail: string;
  tone: "green" | "blue" | "amber" | "neutral";
  icon: LucideIcon;
};


const NAV_ITEMS: Array<{ id: View; label: string; icon: LucideIcon }> = [
  { id: "overview", label: "总览", icon: LayoutDashboard },
  { id: "agents", label: "Agent", icon: Bot },
  { id: "instances", label: "运行实例", icon: Server },
  { id: "topology", label: "协作拓扑", icon: Network },
  { id: "runs", label: "运行记录", icon: Activity },
  { id: "plugins", label: "扩展中心", icon: Blocks },
  { id: "model-configs", label: "凭证&模型配置", icon: KeyRound },
  { id: "settings", label: "系统设置", icon: Settings },
];

const PLUGIN_ICONS: Record<string, LucideIcon> = {
  provider: Cpu,
  tool: TerminalSquare,
  memory: Database,
  storage: Server,
  event_bus: Zap,
  scheduler: Clock3,
  middleware: Layers3,
  ui: LayoutDashboard,
};

const PLUGIN_KIND_LABELS: Record<string, string> = {
  provider: "模型提供商",
  tool: "工具",
  memory: "记忆",
  storage: "存储",
  event_bus: "事件总线",
  scheduler: "调度器",
  middleware: "中间件",
  ui: "界面扩展",
};

type ProviderOption = {
  id: string;
  label: string;
  description: string;
  defaultModel: string;
  defaultBaseUrl?: string;
  requiresCredential?: boolean;
  apiProtocol?: string;
  modelCatalog?: ModelOption[];
};

type ModelOption = {
  value: string;
  label: string;
  hint: string;
  tier?: "latest" | "popular" | "legacy";
  sourceUrl?: string;
};

const CUSTOM_MODEL_VALUE = "__custom_model__";

const PROVIDER_METADATA: Record<string, Omit<ProviderOption, "id">> = {
  openai_compatible: {
    label: "OpenAI 兼容接口",
    description: "可连接 OpenAI、DeepSeek、百炼、Kimi、智谱等兼容服务",
    defaultModel: "gpt-5.6-terra",
    defaultBaseUrl: "https://api.openai.com/v1",
    requiresCredential: true,
    apiProtocol: "openai_chat_completions",
  },
  anthropic_messages: {
    label: "Claude Messages API",
    description: "Anthropic Claude 原生 Messages 协议",
    defaultModel: "claude-sonnet-5",
    defaultBaseUrl: "https://api.anthropic.com",
    requiresCredential: true,
    apiProtocol: "anthropic_messages",
  },
};

const FALLBACK_PROVIDER_OPTIONS: ProviderOption[] = [
  { id: "openai_compatible", ...PROVIDER_METADATA.openai_compatible },
  { id: "anthropic_messages", ...PROVIDER_METADATA.anthropic_messages },
];

const MODEL_PRESETS: Record<string, ModelOption[]> = {
  openai_compatible: [
    {
      value: "gpt-5.6-sol",
      label: "GPT-5.6 Sol",
      hint: "复杂推理与编码旗舰",
      tier: "latest",
    },
    {
      value: "gpt-5.6-terra",
      label: "GPT-5.6 Terra",
      hint: "智能与成本平衡",
      tier: "latest",
    },
    {
      value: "gpt-5.6-luna",
      label: "GPT-5.6 Luna",
      hint: "高并发、成本敏感",
      tier: "latest",
    },
    {
      value: "gpt-4o",
      label: "GPT-4o",
      hint: "成熟通用多模态模型",
      tier: "popular",
    },
    {
      value: "gpt-4o-mini",
      label: "GPT-4o mini",
      hint: "轻量、快速、成本友好",
      tier: "popular",
    },
    { value: "deepseek-v4-pro", label: "DeepSeek V4 Pro", hint: "国产旗舰兼容接口", tier: "latest" },
    { value: "deepseek-v4-flash", label: "DeepSeek V4 Flash", hint: "国产高速兼容接口", tier: "latest" },
    { value: "deepseek-v3.2", label: "DeepSeek V3.2", hint: "通用对话与代码", tier: "latest" },
    { value: "deepseek-v3.1", label: "DeepSeek V3.1", hint: "通用与工具调用", tier: "latest" },
    { value: "deepseek-v3", label: "DeepSeek V3", hint: "成熟通用模型", tier: "popular" },
    { value: "deepseek-r1", label: "DeepSeek R1", hint: "深度推理模型", tier: "popular" },
    { value: "deepseek-r1-0528", label: "DeepSeek R1 0528", hint: "推理增强版本", tier: "popular" },
    { value: "deepseek-chat", label: "DeepSeek Chat", hint: "DeepSeek 通用对话", tier: "popular" },
    { value: "deepseek-reasoner", label: "DeepSeek Reasoner", hint: "DeepSeek 推理", tier: "popular" },
    { value: "qwen3.7-max", label: "通义千问 Qwen3.7 Max", hint: "百炼旗舰", tier: "latest" },
    { value: "qwen3.8-max-preview", label: "通义千问 Qwen3.8 Max Preview", hint: "百炼最新旗舰预览", tier: "latest" },
    { value: "qwen3.7-plus", label: "通义千问 Qwen3.7 Plus", hint: "百炼通用长文本", tier: "latest" },
    { value: "qwen3.7-flash", label: "通义千问 Qwen3.7 Flash", hint: "百炼高速低延迟", tier: "latest" },
    { value: "qwen3.5-omni-plus", label: "通义千问 Qwen3.5 Omni Plus", hint: "通用多模态对话", tier: "latest" },
    { value: "qwen3.5-plus", label: "通义千问 Qwen3.5 Plus", hint: "百炼通用", tier: "latest" },
    { value: "qwen3-max", label: "通义千问 Qwen3 Max", hint: "百炼旗舰通用", tier: "latest" },
    { value: "qwen3-235b-a22b", label: "Qwen3 235B A22B", hint: "开源大规模 MoE", tier: "latest" },
    { value: "qwen3-32b", label: "Qwen3 32B", hint: "开源通用模型", tier: "popular" },
    { value: "qwen3-30b-a3b", label: "Qwen3 30B A3B", hint: "高性价比 MoE", tier: "popular" },
    { value: "qwen3-coder-plus", label: "Qwen3-Coder-Plus", hint: "代码与 Agent 任务", tier: "latest" },
    { value: "qwen3-coder", label: "Qwen3-Coder", hint: "开源代码模型", tier: "popular" },
    { value: "qwen3-vl-plus", label: "Qwen3-VL-Plus", hint: "视觉理解与文档", tier: "latest" },
    { value: "qwen2.5-max", label: "通义千问 Qwen2.5 Max", hint: "成熟旗舰", tier: "popular" },
    { value: "qwen2.5-72b-instruct", label: "Qwen2.5 72B Instruct", hint: "开源通用模型", tier: "popular" },
    { value: "qwen-plus", label: "通义千问 Plus", hint: "长文本与通用任务", tier: "popular" },
    { value: "qwen-turbo", label: "通义千问 Turbo", hint: "高并发低延迟", tier: "popular" },
    { value: "kimi-k3", label: "Kimi K3", hint: "月之暗面新一代模型", tier: "latest" },
    { value: "kimi-k2.6", label: "Kimi K2.6", hint: "Kimi 工具调用", tier: "latest" },
    { value: "kimi-k2.7-code", label: "Kimi K2.7 Code", hint: "编程与 Agent 任务", tier: "latest" },
    { value: "kimi-k2.7-code-highspeed", label: "Kimi K2.7 Code Highspeed", hint: "高速编程模型", tier: "latest" },
    { value: "kimi-k2-thinking-turbo", label: "Kimi K2 Thinking Turbo", hint: "高速推理与工具调用", tier: "latest" },
    { value: "kimi-k2-thinking", label: "Kimi K2 Thinking", hint: "长链路推理与工具调用", tier: "latest" },
    { value: "kimi-k2-instruct", label: "Kimi K2 Instruct", hint: "通用指令模型", tier: "popular" },
    { value: "kimi-k2.5", label: "Kimi K2.5", hint: "Kimi 多模态/通用", tier: "popular" },
    { value: "moonshot-v1-128k", label: "Moonshot V1 128K", hint: "超长上下文", tier: "popular" },
    { value: "moonshot-v1-32k", label: "Moonshot V1 32K", hint: "长文本通用", tier: "popular" },
    { value: "glm-5.2", label: "智谱 GLM-5.2", hint: "智谱旗舰", tier: "latest" },
    { value: "glm-5.1", label: "智谱 GLM-5.1", hint: "复杂任务与推理", tier: "latest" },
    { value: "glm-5-turbo", label: "智谱 GLM-5 Turbo", hint: "高并发通用模型", tier: "latest" },
    { value: "glm-5", label: "智谱 GLM-5", hint: "通用旗舰", tier: "popular" },
    { value: "glm-4.6", label: "智谱 GLM-4.6", hint: "通用与 Agent", tier: "latest" },
    { value: "glm-4.7-flash", label: "智谱 GLM-4.7 Flash", hint: "高速通用模型", tier: "latest" },
    { value: "glm-4.5", label: "智谱 GLM-4.5", hint: "通用与推理", tier: "popular" },
    { value: "glm-4.5-air", label: "智谱 GLM-4.5-Air", hint: "轻量快速", tier: "popular" },
    { value: "glm-4.5-flash", label: "智谱 GLM-4.5 Flash", hint: "高性价比高速模型", tier: "popular" },
    { value: "glm-4.6v", label: "智谱 GLM-4.6V", hint: "视觉理解与文档", tier: "latest" },
    { value: "glm-4.6v-flash", label: "智谱 GLM-4.6V Flash", hint: "高速视觉理解", tier: "latest" },
    { value: "glm-4.7", label: "智谱 GLM-4.7", hint: "成熟通用模型", tier: "popular" },
    { value: "ernie-4.5-turbo-128k", label: "文心 ERNIE 4.5 Turbo", hint: "百度大模型", tier: "latest" },
    { value: "ernie-4.5-8k", label: "文心 ERNIE 4.5", hint: "百度通用模型", tier: "popular" },
    { value: "doubao-seed-1-6-250615", label: "豆包 Seed 1.6", hint: "字节跳动通用模型", tier: "latest" },
    { value: "doubao-seed-1-6-thinking-250615", label: "豆包 Seed 1.6 Thinking", hint: "复杂推理", tier: "latest" },
    { value: "doubao-seed-2-1-pro", label: "豆包 Seed 2.1 Pro", hint: "新一代通用旗舰", tier: "latest" },
    { value: "doubao-seed-2-1-turbo", label: "豆包 Seed 2.1 Turbo", hint: "高速通用模型", tier: "latest" },
    { value: "doubao-seed-2-0-pro", label: "豆包 Seed 2.0 Pro", hint: "通用旗舰模型", tier: "latest" },
    { value: "doubao-seed-2-0-lite", label: "豆包 Seed 2.0 Lite", hint: "轻量高性价比", tier: "popular" },
    { value: "doubao-seed-2-0-mini", label: "豆包 Seed 2.0 Mini", hint: "低延迟轻量模型", tier: "popular" },
    { value: "doubao-seed-1-6-flash", label: "豆包 Seed 1.6 Flash", hint: "高速对话模型", tier: "popular" },
    { value: "doubao-seed-code", label: "豆包 Seed Code", hint: "代码与 Agent 任务", tier: "latest" },
    { value: "doubao-1-5-pro-32k", label: "豆包 1.5 Pro 32K", hint: "成熟通用模型", tier: "popular" },
    { value: "hunyuan-t1", label: "腾讯混元 T1", hint: "推理模型", tier: "latest" },
    { value: "hunyuan-turbos", label: "腾讯混元 Turbo S", hint: "高速通用模型", tier: "popular" },
    { value: "hunyuan-pro", label: "腾讯混元 Pro", hint: "通用旗舰", tier: "popular" },
    { value: "MiniMax-M2", label: "MiniMax M2", hint: "Agent 与代码任务", tier: "latest" },
    { value: "MiniMax-M1", label: "MiniMax M1", hint: "长思考推理", tier: "popular" },
    { value: "MiniMax-M3", label: "MiniMax M3", hint: "新一代通用与 Agent", tier: "latest" },
    { value: "MiniMax-M2.7", label: "MiniMax M2.7", hint: "通用推理与代码", tier: "latest" },
    { value: "MiniMax-M2.7-highspeed", label: "MiniMax M2.7 Highspeed", hint: "高速推理与代码", tier: "latest" },
    { value: "MiniMax-M2.5", label: "MiniMax M2.5", hint: "通用对话模型", tier: "popular" },
    { value: "MiniMax-M2.1", label: "MiniMax M2.1", hint: "通用推理模型", tier: "popular" },
    { value: "abab6.5s-chat", label: "MiniMax abab6.5s", hint: "通用对话", tier: "legacy" },
    { value: "Baichuan4", label: "百川 Baichuan4", hint: "国产通用模型", tier: "latest" },
    { value: "Baichuan3-Turbo", label: "百川 Baichuan3 Turbo", hint: "高速通用模型", tier: "popular" },
    { value: "yi-lightning", label: "零一万物 Yi-Large/Lightning", hint: "高速推理", tier: "popular" },
    { value: "yi-large", label: "零一万物 Yi-Large", hint: "通用旗舰", tier: "popular" },
    { value: "step-3.5-flash", label: "阶跃星辰 Step-3.5-Flash", hint: "高速推理", tier: "latest" },
    { value: "step-2-16k", label: "阶跃星辰 Step-2", hint: "通用模型", tier: "popular" },
    { value: "internlm3-latest", label: "书生·浦语 InternLM3", hint: "开源通用模型", tier: "popular" },
    { value: "SenseNova-V6", label: "商汤日日新 SenseNova V6", hint: "国产通用模型", tier: "popular" },
  ],
  anthropic_messages: [
    { value: "claude-opus-5", label: "Claude Opus 5", hint: "复杂 Agent 与编码", tier: "latest" },
    { value: "claude-sonnet-5", label: "Claude Sonnet 5", hint: "速度与智能平衡", tier: "latest" },
    { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5", hint: "快速高性价比", tier: "latest" },
    { value: "claude-opus-4-8", label: "Claude Opus 4.8", hint: "上一代高性能", tier: "popular" },
    { value: "claude-opus-4-7", label: "Claude Opus 4.7", hint: "上一代复杂任务", tier: "popular" },
    { value: "claude-opus-4-6", label: "Claude Opus 4.6", hint: "稳定 Opus 版本", tier: "popular" },
    { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6", hint: "稳定 Sonnet 版本", tier: "popular" },
    { value: "claude-sonnet-4-5", label: "Claude Sonnet 4.5", hint: "兼容旧应用", tier: "legacy" },
  ],
};

const OPENAI_ENDPOINT_PRESETS = [
  { value: "https://api.openai.com/v1", label: "OpenAI 官方" },
  { value: "https://api.deepseek.com/v1", label: "DeepSeek 兼容接口" },
  {
    value: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    label: "阿里云百炼兼容接口",
  },
  { value: "https://api.moonshot.cn/v1", label: "Moonshot 兼容接口" },
  { value: "https://open.bigmodel.cn/api/paas/v4", label: "智谱 BigModel 兼容接口" },
  { value: "https://ark.cn-beijing.volces.com/api/v3", label: "火山引擎方舟兼容接口" },
  { value: "https://api.hunyuan.cloud.tencent.com/v1", label: "腾讯混元兼容接口" },
  { value: "https://api.minimax.chat/v1", label: "MiniMax 兼容接口" },
  { value: "https://api.stepfun.com/v1", label: "阶跃星辰兼容接口" },
  { value: "https://api.baichuan-ai.com/v1", label: "百川智能兼容接口" },
  { value: "https://api.lingyiwanwu.com/v1", label: "零一万物兼容接口" },
  { value: "https://api.siliconflow.cn/v1", label: "硅基流动聚合接口" },
  { value: "https://openrouter.ai/api/v1", label: "OpenRouter 兼容接口" },
];

const MODEL_TIMEOUT_OPTIONS = [
  { value: "30", label: "30 秒 · 快速失败" },
  { value: "60", label: "60 秒 · 常规请求" },
  { value: "120", label: "120 秒 · 推荐" },
  { value: "300", label: "300 秒 · 长任务" },
];

function providerOptionsFromPlugins(plugins: PluginManifest[]): ProviderOption[] {
  const providers = plugins.filter(
    (plugin) => plugin.kind === "provider" && plugin.available,
  );
  if (!providers.length) return FALLBACK_PROVIDER_OPTIONS;
  return providers.map((plugin) => {
    const metadata = PROVIDER_METADATA[plugin.id];
    const catalog = plugin.model_catalog?.map((item) => ({
      value: item.id,
      label: item.label,
      hint: item.description || "官方模型目录",
      tier: item.tier,
      sourceUrl: item.source_url,
    }));
    return {
      id: plugin.id,
      ...(metadata || {
        label: plugin.display_name,
        description: plugin.description || "由插件提供的模型适配器",
        defaultModel: catalog?.[0]?.value || MODEL_PRESETS[plugin.id]?.[0]?.value || "",
      }),
      requiresCredential: plugin.credential_required ?? metadata?.requiresCredential,
      apiProtocol: plugin.api_protocol || metadata?.apiProtocol,
      modelCatalog: catalog?.length ? catalog : MODEL_PRESETS[plugin.id],
    };
  });
}

function providerOptionFor(
  provider: string,
  plugins: PluginManifest[],
): ProviderOption {
  return (
    providerOptionsFromPlugins(plugins).find((item) => item.id === provider) || {
      id: provider,
      label: provider,
      description: "自定义模型提供商",
      defaultModel: MODEL_PRESETS[provider]?.[0]?.value || "",
    }
  );
}

function modelOptionsForProvider(
  provider: string,
  plugins: PluginManifest[] = [],
): ModelOption[] {
  const manifestCatalog = plugins.find(
    (plugin) => plugin.kind === "provider" && plugin.id === provider,
  )?.model_catalog;
  if (manifestCatalog?.length) {
    return manifestCatalog.map((item) => ({
      value: item.id,
      label: item.label,
      hint: item.description || "官方模型目录",
      tier: item.tier,
      sourceUrl: item.source_url,
    }));
  }
  return MODEL_PRESETS[provider] || [];
}

function hasKnownModel(
  provider: string,
  model: string,
  plugins: PluginManifest[] = [],
): boolean {
  return modelOptionsForProvider(provider, plugins).some((item) => item.value === model);
}

function ModelChoiceField({
  provider,
  plugins,
  model,
  onChange,
  required = true,
}: {
  provider: string;
  plugins?: PluginManifest[];
  model: string;
  onChange: (value: string) => void;
  required?: boolean;
}) {
  const options = modelOptionsForProvider(provider, plugins);
  const isCustom = !hasKnownModel(provider, model, plugins);
  return (
    <label className="form-field">
      <span>模型</span>
      <select
        value={isCustom ? CUSTOM_MODEL_VALUE : model}
        onChange={(event) =>
          onChange(
            event.target.value === CUSTOM_MODEL_VALUE ? "" : event.target.value,
          )
        }
      >
        {options.map((option) => (
          <option value={option.value} key={option.value}>
            {option.label} · {option.hint}
          </option>
        ))}
        <option value={CUSTOM_MODEL_VALUE}>自定义模型 ID…</option>
      </select>
      {isCustom && (
        <input
          required={required}
          value={model}
          onChange={(event) => onChange(event.target.value)}
          placeholder="输入服务商提供的模型 ID，例如 deepseek-chat"
        />
      )}
      <small>常用模型已列出；选“自定义模型 ID”即可连接其他兼容模型。</small>
    </label>
  );
}

function EndpointChoiceField({
  provider,
  value,
  onChange,
}: {
  provider: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const presets = provider === "anthropic_messages"
    ? [
        { value: "https://api.anthropic.com", label: "Anthropic 官方" },
        { value: "https://api.anthropic.com/v1", label: "Anthropic 官方（含 /v1）" },
      ]
    : OPENAI_ENDPOINT_PRESETS;
  const isPreset = presets.some((item) => item.value === value);
  return (
    <label className="form-field">
      <span>服务地址（可选）</span>
      <select
        value={isPreset ? value : ""}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">快速选择常用地址…</option>
        {presets.map((item) => (
          <option value={item.value} key={item.value}>
            {item.label}
          </option>
        ))}
      </select>
      <input
        type="url"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="也可以直接输入，例如 https://example.com/v1"
      />
      <small>可从上方快速填入常用地址，也可以直接输入；留空使用服务商默认地址。</small>
    </label>
  );
}

function ProviderChoiceField({
  provider,
  plugins,
  onChange,
}: {
  provider: string;
  plugins: PluginManifest[];
  onChange: (value: string) => void;
}) {
  const providers = providerOptionsFromPlugins(plugins);
  const selected = providers.some((item) => item.id === provider);
  const options = selected
    ? providers
    : [
        {
          ...providerOptionFor(provider, plugins),
          label: `${provider}（当前配置）`,
        },
        ...providers,
      ];
  return (
    <label className="form-field">
      <span>模型提供商</span>
      <select
        value={provider}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((item) => (
          <option value={item.id} key={item.id}>
            {item.label}
          </option>
        ))}
      </select>
      <small>
        {providerOptionFor(provider, plugins).description}
      </small>
    </label>
  );
}

function compactNumber(value: number): string {
  return new Intl.NumberFormat("zh-CN", { notation: "compact" }).format(value);
}

function formatTime(value?: string): string {
  if (!value) return "—";
  const date = new Date(value);
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Shanghai",
  }).format(date);
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    ready: "就绪",
    running: "运行中",
    succeeded: "成功",
    failed: "失败",
    cancelled: "已取消",
    queued: "排队中",
    stopped: "已停止",
    degraded: "降级",
  };
  return labels[status] || status;
}

function agentInitials(name: string): string {
  return name.replace(/\s*Agent\s*/gi, "").slice(0, 2);
}

function previewValue(value: unknown, fallback = "事件已记录"): string {
  if (value === undefined || value === null || value === "") return fallback;
  const text =
    typeof value === "string" ? value : JSON.stringify(value, null, 0);
  return text.length > 160 ? `${text.slice(0, 160)}…` : text;
}

function parseJsonObject(value: string, label: string): Record<string, unknown> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(value || "{}");
  } catch {
    throw new Error(`${label}必须是有效 JSON`);
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${label}必须是 JSON 对象`);
  }
  return parsed as Record<string, unknown>;
}

function eventTitle(type: string): string {
  const labels: Record<string, string> = {
    "run.started": "Run started",
    "run.completed": "Run completed",
    "run.failed": "Run failed",
    "run.cancelled": "Run cancelled",
    "agent.started": "Agent started",
    "agent.completed": "Agent completed",
    "agent.failed": "Agent failed",
    "model.started": "Model started",
    "model.completed": "Model completed",
    "tool.started": "Tool started",
    "tool.completed": "Tool completed",
    "tool.failed": "Tool failed",
    "delegation.started": "Delegation started",
    "delegation.completed": "Delegation completed",
    "delegation.failed": "Delegation failed",
    "permission.required": "Permission required",
    "budget.updated": "Budget updated",
  };
  return labels[type] || type;
}

function eventTone(type: string): "green" | "blue" | "violet" | "amber" {
  if (type.includes("failed") || type.includes("permission")) return "amber";
  if (type.startsWith("delegation")) return "violet";
  if (type.startsWith("model") || type.startsWith("budget")) return "blue";
  return "green";
}

function eventDetail(event: RunEvent): string {
  const payload = event.payload || {};
  if (event.type === "run.started") {
    return `root rev ${previewValue(payload.agent_revision, "—")} · ${previewValue(payload.session_id, event.agent_id)}`;
  }
  if (event.type === "model.started") {
    return `${previewValue(payload.provider, "provider")} / ${previewValue(payload.model, "model")} · step ${previewValue(payload.step, "—")}`;
  }
  if (event.type === "model.completed") {
    return `${previewValue(payload.provider, "provider")} / ${previewValue(payload.model, "model")} · usage ${previewValue(payload.usage, "未报告")}`;
  }
  if (event.type.startsWith("delegation.")) {
    return `${previewValue(payload.alias, "child")} · ${previewValue(payload.child_agent_id, event.agent_id)} · depth ${event.depth + 1}`;
  }
  if (event.type.startsWith("tool.")) {
    return `${previewValue(payload.tool, "tool")} · ${previewValue(payload.result ?? payload.error, "调用已记录")}`;
  }
  return previewValue(
    payload.output ?? payload.error ?? payload.metrics ?? payload.name ?? payload,
    `${event.agent_id} · depth ${event.depth}`,
  );
}

function getDefaultApiBase(): string {
  if (typeof window === "undefined") return "http://localhost:8000/api/v1";
  return (
    window.localStorage.getItem("uai-forge-api-base") ||
    "http://localhost:8000/api/v1"
  );
}

export function ControlCenter() {
  const [view, setView] = useState<View>(() => {
    if (typeof window === "undefined") return "overview";
    const candidate = new URLSearchParams(window.location.search).get("view") as View | null;
    return candidate && NAV_ITEMS.some((item) => item.id === candidate) ? candidate : "overview";
  });
  const [routeResourceId, setRouteResourceId] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return new URLSearchParams(window.location.search).get("resource");
  });
  const [mobileNav, setMobileNav] = useState(false);
  const mobileMenuRef = useRef<HTMLButtonElement>(null);
  const mobileNavCloseRef = useRef<HTMLButtonElement>(null);
  const mobileNavWasOpen = useRef(false);
  const [mode, setMode] = useState<ConnectionMode>("connecting");
  const [apiBase, setApiBase] = useState(() => getDefaultApiBase());
  const [apiKey, setApiKey] = useState("");
  const [agents, setAgents] = useState<AgentSpec[]>([]);
  const [instances, setInstances] = useState<AgentInstance[]>([]);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [plugins, setPlugins] = useState<PluginManifest[]>([]);
  const [modelConfigs, setModelConfigs] = useState<ModelConfig[]>([]);
  const [runtimeConfig, setRuntimeConfig] = useState<RuntimeConfigEntry[]>([]);
  const [setupStatus, setSetupStatus] = useState<SetupStatus | null>(null);
  const [capabilities, setCapabilities] = useState<CapabilityStatus[]>([]);
  const [resourceStates, setResourceStates] = useState<Record<string, ResourceState<unknown>>>({});
  const [selectedAgent, setSelectedAgent] = useState<AgentSpec | null>(null);
  const [editingAgent, setEditingAgent] = useState<AgentSpec | null>(null);
  const [newAgentOpen, setNewAgentOpen] = useState(false);
  const [newInstanceOpen, setNewInstanceOpen] = useState(false);
  const [runOpen, setRunOpen] = useState(false);
  const [runBusy, setRunBusy] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [agentQuery, setAgentQuery] = useState("");

  useEffect(() => {
    if (!mobileNav) {
      if (mobileNavWasOpen.current) mobileMenuRef.current?.focus();
      mobileNavWasOpen.current = false;
      return undefined;
    }

    mobileNavWasOpen.current = true;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setMobileNav(false);
    };
    document.addEventListener("keydown", onKeyDown);
    window.setTimeout(() => mobileNavCloseRef.current?.focus(), 0);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [mobileNav]);

  const headers = useCallback((): HeadersInit => headersFor(apiKey, "default"), [apiKey]);

  const navigate = useCallback((nextView: View, resourceId?: string | null) => {
    setView(nextView);
    setRouteResourceId(resourceId || null);
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      params.set("view", nextView);
      if (resourceId) params.set("resource", resourceId);
      else params.delete("resource");
      window.history.pushState({}, "", `${window.location.pathname}?${params.toString()}`);
    }
  }, []);

  useEffect(() => {
    function onPopState() {
      const params = new URLSearchParams(window.location.search);
      const candidate = params.get("view") as View | null;
      setView(candidate && NAV_ITEMS.some((item) => item.id === candidate) ? candidate : "overview");
      setRouteResourceId(params.get("resource"));
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const refresh = useCallback(
    async (candidateBase?: string) => {
      const base = (candidateBase || apiBase).replace(/\/$/, "");
      setSyncing(true);
      const resourceRequests: Array<{
        key: string;
        request: Promise<unknown>;
        apply: (value: unknown) => void;
        empty: unknown;
      }> = [
        { key: "agents", request: apiRequest<AgentSpec[]>(`${base}/agents`, { headers: headers(), signal: AbortSignal.timeout(2500) }), apply: (value) => setAgents(value as AgentSpec[]), empty: [] },
        { key: "instances", request: apiRequest<AgentInstance[]>(`${base}/instances`, { headers: headers(), signal: AbortSignal.timeout(2500) }), apply: (value) => setInstances(value as AgentInstance[]), empty: [] },
        { key: "runs", request: apiRequest<RunRecord[]>(`${base}/runs?limit=100`, { headers: headers(), signal: AbortSignal.timeout(2500) }), apply: (value) => setRuns(value as RunRecord[]), empty: [] },
        { key: "plugins", request: apiRequest<PluginManifest[]>(`${base}/plugins`, { headers: headers(), signal: AbortSignal.timeout(2500) }), apply: (value) => setPlugins(value as PluginManifest[]), empty: [] },
        { key: "modelConfigs", request: apiRequest<ModelConfig[]>(`${base}/model-configs`, { headers: headers(), signal: AbortSignal.timeout(2500) }), apply: (value) => setModelConfigs(value as ModelConfig[]), empty: [] },
        { key: "runtimeConfig", request: apiRequest<RuntimeConfigEntry[]>(`${base}/runtime-config`, { headers: headers(), signal: AbortSignal.timeout(2500) }), apply: (value) => setRuntimeConfig(value as RuntimeConfigEntry[]), empty: [] },
        { key: "setup", request: apiRequest<SetupStatus>(`${base}/setup-status`, { headers: headers(), signal: AbortSignal.timeout(2500) }), apply: (value) => setSetupStatus(value as SetupStatus), empty: null },
        { key: "capabilities", request: apiRequest<CapabilityStatus[]>(`${base}/capabilities`, { headers: headers(), signal: AbortSignal.timeout(2500) }), apply: (value) => setCapabilities(value as CapabilityStatus[]), empty: [] },
      ];
      const results = await Promise.allSettled(resourceRequests.map((item) => item.request));
      let successes = 0;
      results.forEach((result, index) => {
        const item = resourceRequests[index];
        if (result.status === "fulfilled") {
          successes += 1;
          item.apply(result.value);
          setResourceStates((current) => ({
            ...current,
            [item.key]: { status: "ready", data: result.value },
          }));
        } else {
          const problem = result.reason instanceof ApiProblem
            ? result.reason
            : problemFromRefreshError(result.reason);
          setResourceStates((current) => {
            const previous = current[item.key] || { status: "idle", data: item.empty };
            return { ...current, [item.key]: markResourceError(previous, problem) };
          });
        }
      });
      setApiBase(base);
      setMode(successes > 0 ? "live" : "disconnected");
      if (successes > 0) setNotice("控制面数据已同步，局部失败会标记为过期");
      if (typeof window !== "undefined") window.localStorage.setItem("uai-forge-api-base", base);
      setSyncing(false);
    },
    [apiBase, headers],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => void refresh(apiBase), 0);
    return () => window.clearTimeout(timer);
    // The first connection attempt should only happen once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!notice) return;
    const timeout = window.setTimeout(() => setNotice(null), 2800);
    return () => window.clearTimeout(timeout);
  }, [notice]);

  const rootAgent =
    agents.find((agent) => agent.labels?.tier === "leader") || agents[0];
  const urlSelectedAgent =
    routeResourceId && view !== "runs" && view !== "model-configs"
      ? agents.find((item) => item.id === routeResourceId) || null
      : null;
  const activeSelectedAgent = selectedAgent || urlSelectedAgent;
  const degradedResourceCount = Object.values(resourceStates).filter(
    (resource) => resource.status === "stale" || resource.status === "error",
  ).length;
  const mountedAgents = rootAgent
    ? rootAgent.children
        .map((mount) => agents.find((agent) => agent.id === mount.agent_id))
        .filter(Boolean) as AgentSpec[]
    : [];
  const successfulRuns = runs.filter((run) => run.status === "succeeded").length;
  const totalTokens = runs.reduce((sum, run) => {
    const tokens = Number(run.metrics?.tokens || 0);
    return sum + (Number.isFinite(tokens) ? tokens : 0);
  }, 0);
  const recentActivities = useMemo<ActivityItem[]>(
    () =>
      runs.slice(0, 4).map((run) => {
        const agent = agents.find((item) => item.id === run.agent_id);
        const status = run.status;
        const tone: ActivityItem["tone"] =
          status === "succeeded"
            ? "green"
            : status === "running" || status === "queued"
              ? "blue"
              : status === "failed"
                ? "amber"
                : "neutral";
        const icon =
          status === "succeeded"
            ? Check
            : status === "failed"
              ? OctagonAlert
              : status === "cancelled"
                ? X
                : CircleGauge;
        return {
          id: run.id,
          time: formatTime(run.created_at),
          title: `${agent?.name || run.agent_id} · ${statusLabel(status)}`,
          detail: run.error || run.output || run.input,
          tone,
          icon,
        };
      }),
    [agents, runs],
  );
  const filteredAgents = useMemo(() => {
    const query = agentQuery.trim().toLowerCase();
    if (!query) return agents;
    return agents.filter(
      (agent) =>
        agent.name.toLowerCase().includes(query) ||
        agent.description.toLowerCase().includes(query) ||
        agent.id.toLowerCase().includes(query),
    );
  }, [agentQuery, agents]);

  function openNewAgent() {
    if (mode !== "live") {
      navigate("settings");
      setNotice("请先连接控制面；Agent 会写入 Python 数据库");
      return;
    }
    if (!setupStatus || setupStatus.model_connections.runnable === 0) {
      navigate("model-configs");
      setNotice("先保存并验证一条可运行的模型连接");
      return;
    }
    setNewAgentOpen(true);
  }

  function openRun() {
    if (mode !== "live") {
      navigate("settings");
      setNotice("请先连接控制面；运行记录只来自 Python 数据库");
      return;
    }
    if (!setupStatus || setupStatus.agents.runnable === 0) {
      if (setupStatus?.next_action === "verify_model_config") {
        navigate("model-configs", setupStatus.model_connections.blocking_issues[0]?.resource_id);
      } else {
        navigate("agents");
      }
      setNotice("当前没有可运行 Agent，请按首用清单修复前置条件");
      return;
    }
    setRunOpen(true);
  }

  function openRunReadinessFix() {
    setRunOpen(false);
    if (mode !== "live") {
      navigate("settings");
      return;
    }
    if (setupStatus?.next_action === "verify_model_config" || setupStatus?.next_action === "create_model_config") {
      navigate("model-configs", setupStatus.next_action === "verify_model_config" ? setupStatus.model_connections.blocking_issues[0]?.resource_id : null);
      return;
    }
    navigate("agents");
  }

  function openAgentDetails(agent: AgentSpec) {
    setSelectedAgent(agent);
    navigate(view, agent.id);
  }

  function closeAgentDetails() {
    setSelectedAgent(null);
    navigate(view, null);
  }

  function changeApiBase(value: string) {
    setApiBase(value);
    setMode("connecting");
    setSetupStatus(null);
    setCapabilities([]);
    setAgents([]);
    setInstances([]);
    setRuns([]);
    setPlugins([]);
    setModelConfigs([]);
    setRuntimeConfig([]);
    setResourceStates({});
  }

  function changeApiKey(value: string) {
    setApiKey(value);
    setMode("connecting");
    setSetupStatus(null);
    setCapabilities([]);
    setAgents([]);
    setInstances([]);
    setRuns([]);
    setPlugins([]);
    setModelConfigs([]);
    setRuntimeConfig([]);
    setResourceStates({});
  }

  async function createAgent(form: NewAgentForm) {
    const payload = {
      name: form.name,
      description: form.description,
      system_prompt: form.systemPrompt,
      model: {
        model_config_id: form.modelConfigId,
      },
      tools: form.tools,
      children: form.children,
      memory: form.memory,
      middlewares: form.middlewares,
      policy: form.policy,
      labels: {
        team: "custom",
        tier: form.children.length ? "leader" : "worker",
      },
      enabled: form.enabled,
    };
    if (mode === "live") {
      const created = await apiRequest<AgentSpec>(`${apiBase}/agents`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify(payload),
      });
      setAgents((current) => [...current, created]);
      await refresh();
    } else {
      throw new Error("请先连接 Python 控制面；Agent 配置只写入数据库");
    }
    setNotice(`${form.name} 已创建`);
    setNewAgentOpen(false);
  }

  async function updateAgent(
    agent: AgentSpec,
    form: AgentConfigurationForm,
  ) {
    const payload = {
      expected_revision: agent.revision,
      name: form.name,
      description: form.description,
      system_prompt: form.systemPrompt,
      model: {
        model_config_id: form.modelConfigId,
      },
      tools: form.tools,
      children: form.children,
      memory: form.memory,
      middlewares: form.middlewares,
      policy: form.policy,
      enabled: form.enabled,
    };
    let updated: AgentSpec;
    if (mode === "live") {
      updated = await apiRequest<AgentSpec>(`${apiBase}/agents/${agent.id}`, {
        method: "PATCH",
        headers: headers(),
        body: JSON.stringify(payload),
      });
    } else {
      throw new Error("请先连接 Python 控制面；修订只写入数据库");
    }
    setAgents((current) =>
      current.map((item) => (item.id === updated.id ? updated : item)),
    );
    await refresh();
    setEditingAgent(null);
    setNotice(`${updated.name} rev ${updated.revision} 已发布`);
  }

  async function updateModelConfig(
    config: ModelConfig,
    patch: Record<string, unknown>,
  ) {
    if (mode !== "live") throw new Error("请先连接 Python 控制面；模型配置只写入数据库");
    const outgoing = {
      ...patch,
      expected_version: config.version,
      secret_action: patch.secret ? "replace" : patch.secret_action || "keep",
    };
    const updated = await apiRequest<ModelConfig>(`${apiBase}/model-configs/${config.id}`, {
      method: "PATCH",
      headers: headers(),
      body: JSON.stringify(outgoing),
    });
    setModelConfigs((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    await refresh();
    setNotice(`${updated.name} 已更新`);
  }

  async function checkModelConfig(config: ModelConfig) {
    if (mode !== "live") throw new Error("请先连接 Python 控制面");
    const result = await apiRequest<ModelConnectionCheckResult>(`${apiBase}/model-configs/${config.id}/checks`, {
      method: "POST",
      headers: headers(),
    });
    await refresh();
    if (result.status === "passed") setNotice("连接检查通过；现在可以启用模型连接");
    else setNotice(`连接检查未通过：${result.code}`);
    return result;
  }

  async function deleteModelConfig(config: ModelConfig) {
    if (mode !== "live") throw new Error("请先连接 Python 控制面");
    await apiRequest<unknown>(`${apiBase}/model-configs/${config.id}`, {
      method: "DELETE",
      headers: headers(),
    });
    setModelConfigs((current) => current.filter((item) => item.id !== config.id));
    await refresh();
    setNotice(`${config.name} 已删除`);
  }

  async function createInstance(form: {
    name: string;
    agentId: string;
    environment: string;
    maxConcurrency: number;
  }) {
    const agent = agents.find((item) => item.id === form.agentId);
    if (!agent) throw new Error("请选择有效的 Agent");
    const payload = {
      name: form.name,
      agent_id: agent.id,
      agent_revision: agent.revision,
      environment: form.environment,
      status: "ready",
      max_concurrency: form.maxConcurrency,
      config_overrides: {},
    };
    if (mode === "live") {
      const created = await apiRequest<AgentInstance>(`${apiBase}/instances`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify(payload),
      });
      setInstances((current) => [...current, created]);
      await refresh();
    } else {
      throw new Error("请先连接 Python 控制面；实例配置只写入数据库");
    }
    setNotice(`${form.name} 实例已创建`);
    setNewInstanceOpen(false);
  }

  async function setInstanceStatus(
    instance: AgentInstance,
    nextStatus: "ready" | "stopped",
  ) {
    if (mode === "live") {
      const updated = await apiRequest<AgentInstance>(`${apiBase}/instances/${instance.id}`, {
        method: "PATCH",
        headers: headers(),
        body: JSON.stringify({ status: nextStatus }),
      });
      setInstances((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      await refresh();
    } else {
      throw new Error("请先连接 Python 控制面；实例状态由数据库控制");
    }
    setNotice(`${instance.name} 已${nextStatus === "ready" ? "启用" : "停止"}`);
  }

  async function launchRun(targetId: string, targetKind: "agent" | "instance", input: string) {
    setRunBusy(true);
    try {
      if (mode === "live") {
        const created = await apiRequest<RunRecord>(`${apiBase}/runs`, {
          method: "POST",
          headers: headers(),
          body: JSON.stringify({
            [targetKind === "instance" ? "instance_id" : "agent_id"]: targetId,
            input,
          }),
        });
        setRuns((current) => [created, ...current]);
        setNotice("运行已提交，事件流正在记录");
        setRunOpen(false);
        navigate("runs", created.id);
      } else {
        throw new Error("请先连接 Python 控制面；运行记录必须来自数据库");
      }
    } finally {
      setRunBusy(false);
    }
  }

  async function cancelRun(runId: string) {
    if (mode === "live") {
      const response = await apiRequest<{ accepted: boolean }>(`${apiBase}/runs/${runId}/cancel`, {
        method: "POST",
        headers: headers(),
      });
      if (!response.accepted) return;
      setNotice("取消请求已发送，等待服务器确认");
    }
  }

  const projectRun = useCallback((runId: string, patch: Partial<RunRecord>) => {
    setRuns((current) => current.map((run) => (
      run.id === runId ? { ...run, ...patch } : run
    )));
  }, []);

  return (
    <div className="forge-shell">
      <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            <Braces size={22} />
          </div>
          <div>
            <div className="brand-name">UAI Forge</div>
            <div className="brand-subtitle">AGENT RUNTIME</div>
          </div>
          <button
            ref={mobileNavCloseRef}
            className="icon-button sidebar-close"
            onClick={() => setMobileNav(false)}
            aria-label="关闭导航"
          >
            <X size={18} />
          </button>
        </div>

        <nav className="main-nav" aria-label="主导航">
          <span className="nav-section-label">工作台</span>
          {NAV_ITEMS.slice(0, 4).map((item) => (
            <button
              key={item.id}
              className={`nav-item ${view === item.id ? "active" : ""}`}
              onClick={() => {
                navigate(item.id);
                setMobileNav(false);
              }}
            >
              <item.icon size={18} strokeWidth={1.8} />
              <span>{item.label}</span>
              {item.id === "runs" && runs.some((run) => run.status === "running") && (
                <span className="nav-pulse" aria-label="有运行中的任务" />
              )}
            </button>
          ))}
          <span className="nav-section-label nav-section-spaced">系统</span>
          {NAV_ITEMS.slice(4).map((item) => (
            <button
              key={item.id}
              className={`nav-item ${view === item.id ? "active" : ""}`}
              onClick={() => {
                navigate(item.id);
                setMobileNav(false);
              }}
            >
              <item.icon size={18} strokeWidth={1.8} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="runtime-card">
            <div className="runtime-card-top">
              <span className={`status-dot ${mode}`} />
              <span>{mode === "live" ? "Python Runtime" : "未连接"}</span>
              <span className="runtime-version">v0.1</span>
            </div>
            <div className="runtime-meter" aria-label="控制面连接状态">
              <span style={{ width: mode === "live" ? "100%" : "24%" }} />
            </div>
            <p>{mode === "live" ? "控制面连接正常" : "连接本地 API 即可切换"}</p>
          </div>
          <div className="profile-row">
            <div className="profile-avatar">UA</div>
            <div className="profile-copy">
              <strong>本地操作者</strong>
              <span>未认证 · default 数据分区</span>
            </div>
            <ChevronRight size={16} />
          </div>
        </div>
      </aside>

      {mobileNav && <button className="sidebar-scrim" onClick={() => setMobileNav(false)} />}

      <main className="main-content">
        <header className="topbar">
          <div className="topbar-left">
            <button
              ref={mobileMenuRef}
              className="icon-button mobile-menu"
              onClick={() => setMobileNav(true)}
              aria-label="打开导航"
            >
              <Menu size={20} />
            </button>
            <div>
              <span className="topbar-kicker">DEFAULT DATA PARTITION · UNAUTHENTICATED</span>
              <h1>{NAV_ITEMS.find((item) => item.id === view)?.label}</h1>
            </div>
          </div>
          <div className="topbar-actions">
            <button
              className="connection-pill"
              onClick={() => navigate("settings")}
              aria-label="查看运行时连接"
            >
              <span className={`status-dot ${mode}`} />
              <span>{mode === "live" ? "实时连接" : mode === "connecting" ? "连接中" : "未连接"}</span>
            </button>
            <button
              className="icon-button"
              onClick={() => void refresh()}
              aria-label="刷新数据"
              disabled={syncing}
            >
              <RefreshCw size={18} className={syncing ? "spinning" : ""} />
            </button>
            <button className="button button-secondary topbar-create" onClick={openNewAgent}>
              <Plus size={17} />
              新建 Agent
            </button>
            <button className="button button-primary" onClick={openRun}>
              <Play size={16} fill="currentColor" />
              发起运行
            </button>
          </div>
        </header>

        <div className="content-stage">
          {mode === "disconnected" && view !== "settings" && (
            <div className="connection-banner">
              <div>
                <Cloud size={17} />
                <span>
                  当前未连接控制面，页面不生成本地配置或业务数据。连接 Python 控制面后，所有 Agent、凭据、模型和运行记录均来自数据库。
                </span>
              </div>
              <button onClick={() => navigate("settings")}>
                配置连接 <ArrowRight size={15} />
              </button>
            </div>
          )}
          {degradedResourceCount > 0 && mode === "live" && (
            <div className="connection-banner connection-banner-warning" role="status">
              <div><OctagonAlert size={17} /><span>{degradedResourceCount} 个资源暂时不可用或已过期，其余数据仍来自同一控制面。</span></div>
              <button onClick={() => void refresh()} disabled={syncing}>重试 <RefreshCw size={15} /></button>
            </div>
          )}

          {view === "overview" && (
            <Overview
              rootAgent={rootAgent}
              mountedAgents={mountedAgents}
              agents={agents}
              instances={instances}
              runs={runs}
              plugins={plugins}
              setupStatus={setupStatus}
              capabilities={capabilities}
              activities={recentActivities}
              successfulRuns={successfulRuns}
              totalTokens={totalTokens}
              onRun={openRun}
              onAgent={openAgentDetails}
              onViewRuns={() => navigate("runs")}
              onViewTopology={() => navigate("topology")}
              onSetupAction={(action) => {
                if (action === "connect") navigate("settings");
                else if (action === "create_model_config") navigate("model-configs");
                else if (action === "verify_model_config") navigate("model-configs", setupStatus?.model_connections.blocking_issues[0]?.resource_id);
                else if (action === "create_agent") openNewAgent();
                else if (action === "run_agent") openRun();
              }}
            />
          )}

          {view === "agents" && (
            <AgentsView
              agents={filteredAgents}
              query={agentQuery}
              setQuery={setAgentQuery}
              onCreate={openNewAgent}
              onSelect={openAgentDetails}
            />
          )}

          {view === "instances" && (
            <InstancesView
              instances={instances}
              agents={agents}
              onCreate={() => setNewInstanceOpen(true)}
              onStatusChange={(instance, status) =>
                void setInstanceStatus(instance, status)
              }
              onRun={openRun}
            />
          )}

          {view === "topology" && (
            <TopologyView
              rootAgent={rootAgent}
              mountedAgents={mountedAgents}
              agents={agents}
              onSelect={openAgentDetails}
            />
          )}

          {view === "runs" && (
            <RunsView
              key={`${apiBase}:${routeResourceId || "latest"}`}
              runs={runs}
              agents={agents}
              onRun={openRun}
              onCancel={(id) => void cancelRun(id)}
              apiBase={apiBase}
              mode={mode}
              requestHeaders={headers}
              onRunProjection={projectRun}
              resourceId={routeResourceId}
              onResourceSelect={(resourceId) => navigate("runs", resourceId)}
            />
          )}

          {view === "plugins" && <PluginsView plugins={plugins} />}

          {view === "model-configs" && (
            <ModelConfigsView
              key={`${apiBase}:${routeResourceId || "new"}:${routeResourceId && modelConfigs.some((item) => item.id === routeResourceId) ? "ready" : "loading"}`}
              apiBase={apiBase}
              mode={mode}
              syncing={syncing}
              plugins={plugins}
              modelConfigs={modelConfigs}
              requestHeaders={headers}
              resourceId={routeResourceId}
              onResourceSelect={(resourceId) => navigate("model-configs", resourceId)}
              onConfigChanged={() => void refresh()}
              onUpdate={(config, patch) => void updateModelConfig(config, patch)}
              onCheck={(config) => checkModelConfig(config)}
              onDelete={(config) => void deleteModelConfig(config)}
            />
          )}

          {view === "settings" && (
            <SettingsView
              apiBase={apiBase}
              apiKey={apiKey}
              mode={mode}
              syncing={syncing}
              runtimeConfig={runtimeConfig}
              capabilities={capabilities}
              requestHeaders={headers}
              onConfigChanged={() => void refresh()}
              onOpenModelConfigs={() => navigate("model-configs")}
              setApiBase={changeApiBase}
              setApiKey={changeApiKey}
              onConnect={() => void refresh(apiBase)}
            />
          )}
        </div>
      </main>

      {activeSelectedAgent && (
        <AgentDrawer
          agent={activeSelectedAgent}
          agents={agents}
          modelConfigs={modelConfigs}
          onClose={closeAgentDetails}
          onEdit={() => {
            setEditingAgent(activeSelectedAgent);
            setSelectedAgent(null);
          }}
          onRun={() => {
            setSelectedAgent(null);
            setRunOpen(true);
          }}
        />
      )}

      {newAgentOpen && (
        <NewAgentModal
          agents={agents}
          plugins={plugins}
          modelConfigs={modelConfigs}
          onClose={() => setNewAgentOpen(false)}
          onCreate={createAgent}
        />
      )}

      {editingAgent && (
        <EditAgentModal
          agent={editingAgent}
          agents={agents}
          plugins={plugins}
          modelConfigs={modelConfigs}
          onClose={() => setEditingAgent(null)}
          onSave={(form) => updateAgent(editingAgent, form)}
        />
      )}

      {newInstanceOpen && (
        <NewInstanceModal
          agents={agents.filter((agent) => agent.enabled)}
          onClose={() => setNewInstanceOpen(false)}
          onCreate={createInstance}
        />
      )}

      {runOpen && (
        <RunModal
          agents={agents.filter((agent) => agent.enabled)}
          instances={instances.filter((instance) => instance.status === "ready")}
          readinessIssues={setupStatus?.agents.blocking_issues || []}
          busy={runBusy}
          onClose={() => !runBusy && setRunOpen(false)}
          onRepair={openRunReadinessFix}
          onLaunch={launchRun}
        />
      )}

      {notice && (
        <div className="toast" role="status">
          <CheckCircle2 size={18} />
          {notice}
        </div>
      )}
    </div>
  );
}

function SetupChecklist({
  setupStatus,
  onAction,
}: {
  setupStatus: SetupStatus;
  onAction: (action: SetupAction) => void;
}) {
  const steps: Array<{ action: SetupAction; title: string; detail: string; complete: boolean }> = [
    {
      action: "connect",
      title: "连接控制面",
      detail: setupStatus.connection === "connected" ? "已连接到当前 Python 控制面" : "先配置可访问的控制面",
      complete: setupStatus.connection === "connected",
    },
    {
      action: setupStatus.model_connections.total ? "verify_model_config" : "create_model_config",
      title: setupStatus.model_connections.total ? "验证模型连接" : "创建模型连接",
      detail: setupStatus.model_connections.runnable
        ? `${setupStatus.model_connections.runnable} 条连接可运行`
        : setupStatus.model_connections.total ? "没有可运行连接；先检查草稿并显式启用" : "先保存一条草稿；密钥只在提交时处理",
      complete: setupStatus.model_connections.runnable > 0,
    },
    {
      action: "create_agent",
      title: "创建最小 Agent",
      detail: setupStatus.agents.runnable
        ? `${setupStatus.agents.runnable} 个 Agent 已通过 readiness`
        : "选择模型连接并填写职责与提示词",
      complete: setupStatus.agents.runnable > 0,
    },
    {
      action: "run_agent",
      title: "发起首个 Run",
      detail: setupStatus.runs.total ? `${setupStatus.runs.total} 次运行已记录` : "Instance 可选；可直接运行 Agent",
      complete: setupStatus.runs.total > 0,
    },
  ];
  return (
    <div className="setup-checklist" aria-label="首次运行清单">
      {steps.map((step, index) => (
        <div className={`setup-step ${step.complete ? "complete" : index === steps.findIndex((item) => item.action === setupStatus.next_action) ? "current" : ""}`} key={step.action}>
          <span className="setup-step-number">{step.complete ? <Check size={15} /> : index + 1}</span>
          <div><strong>{step.title}</strong><small>{step.detail}</small></div>
          {!step.complete && step.action === setupStatus.next_action && (
            <button className="button button-primary" onClick={() => onAction(step.action)}>开始</button>
          )}
          {step.complete && <span className="setup-step-done">已完成</span>}
        </div>
      ))}
    </div>
  );
}

function Overview({
  rootAgent,
  mountedAgents,
  agents,
  instances,
  runs,
  plugins,
  setupStatus,
  capabilities,
  activities,
  successfulRuns,
  totalTokens,
  onRun,
  onAgent,
  onViewRuns,
  onViewTopology,
  onSetupAction,
}: {
  rootAgent?: AgentSpec;
  mountedAgents: AgentSpec[];
  agents: AgentSpec[];
  instances: AgentInstance[];
  runs: RunRecord[];
  plugins: PluginManifest[];
  setupStatus: SetupStatus | null;
  capabilities: CapabilityStatus[];
  activities: ActivityItem[];
  successfulRuns: number;
  totalTokens: number;
  onRun: () => void;
  onAgent: (agent: AgentSpec) => void;
  onViewRuns: () => void;
  onViewTopology: () => void;
  onSetupAction: (action: SetupAction) => void;
}) {
  if (!agents.length) {
    return (
      <div className="view-stack">
        <section className="empty-setup panel">
          <div className="eyebrow"><Sparkles size={15} /> 首次运行路径</div>
          <h2>从真实连接开始，完成第一个 Run</h2>
          <p>当前控制台不创建示例 Agent、伪造 Provider 或本地运行数据。每一步都由 Python 控制面返回的事实驱动。</p>
          {setupStatus ? (
            <SetupChecklist setupStatus={setupStatus} onAction={onSetupAction} />
          ) : (
            <div className="empty-inline">正在读取控制面 SetupStatus；如果持续没有响应，请检查系统设置中的 API 地址。</div>
          )}
          <div className="hero-proof">
            <span><ShieldCheck size={15} /> 密钥只在控制面处理</span>
            <span><Database size={15} /> 数据来自租户数据库</span>
            <span><Activity size={15} /> Run 事件可续播</span>
          </div>
        </section>
      </div>
    );
  }
  return (
    <div className="view-stack">
      <section className="hero-grid">
        <div className="hero-copy">
          <div className="eyebrow">
            <Sparkles size={15} />
            可扩展 Python Agent Runtime
          </div>
          <h2>
            把 Agent 组织成
            <br />
            <span>可治理的团队</span>
          </h2>
          <p>
            用版本化配置管理每个 Agent，把 Agent 安全挂载为子 Agent，并在同一条事件流中观察委派、工具、预算与终态。
          </p>
          <div className="hero-actions">
            <button className="button button-primary button-large" onClick={onRun}>
              <Play size={17} fill="currentColor" />
              发起一次真实运行
            </button>
            <button className="button button-ghost button-large" onClick={onViewTopology}>
              查看协作拓扑
              <ArrowRight size={17} />
            </button>
          </div>
          <div className="hero-proof">
            <span><ShieldCheck size={15} /> 递归保护</span>
            <span><CircleGauge size={15} /> 共享预算</span>
            <span><Blocks size={15} /> 协议化扩展</span>
          </div>
        </div>

        <div className="orchestration-card">
          <div className="card-heading">
            <div>
              <span className="section-kicker">TEAM TOPOLOGY</span>
              <h3>当前协作拓扑</h3>
            </div>
            <button className="card-link" onClick={onViewTopology}>展开</button>
          </div>
          <div className="mini-topology">
            {rootAgent && (
              <button className="topology-node node-lead" onClick={() => onAgent(rootAgent)}>
                <span className="node-avatar lime">{agentInitials(rootAgent.name)}</span>
                <span>
                  <strong>{rootAgent.name}</strong>
                    <small>Agent definition · rev {rootAgent.revision}</small>
                  </span>
                <span className="node-live" aria-label="拓扑节点" />
              </button>
            )}
            <div className="topology-trunk">
              <span />
              <span />
            </div>
            <div className="child-node-row">
              {mountedAgents.slice(0, 2).map((agent, index) => (
                <button
                  className="topology-node node-child"
                  key={agent.id}
                  onClick={() => onAgent(agent)}
                >
                  <span className={`node-avatar ${index === 0 ? "blue" : "violet"}`}>
                    {agentInitials(agent.name)}
                  </span>
                  <span>
                    <strong>{agent.name}</strong>
                    <small>{agent.tools.length} tools · 已配置</small>
                  </span>
                </button>
              ))}
            </div>
          </div>
          <div className="orchestration-footer">
            <div>
              <span className="metric-value">
                {String(rootAgent?.children.length || 0).padStart(2, "0")}
              </span>
              <span className="metric-label">子 Agent</span>
            </div>
            <div>
              <span className="metric-value">
                {String(rootAgent?.policy.max_depth || 0).padStart(2, "0")}
              </span>
              <span className="metric-label">最大深度</span>
            </div>
            <div>
              <span className="metric-value">
                {compactNumber(rootAgent?.policy.token_budget || 0)}
              </span>
              <span className="metric-label">Token 预算</span>
            </div>
            <div className="live-indicator"><span /> {setupStatus?.agents.runnable ? "可运行" : "需修复"}</div>
          </div>
        </div>
      </section>

      <section className="metrics-grid" aria-label="关键指标">
        <MetricCard
          icon={Bot}
          label="Agent 定义"
          value={String(agents.length).padStart(2, "0")}
          note={`${agents.filter((agent) => agent.enabled).length} 个已启用`}
          tone="lime"
        />
        <MetricCard
          icon={Box}
          label="运行实例"
          value={String(instances.length).padStart(2, "0")}
          note="environment 仅是运行上下文标签"
          tone="blue"
        />
        <MetricCard
          icon={CheckCircle2}
          label="成功运行"
          value={String(successfulRuns).padStart(2, "0")}
          note={`${runs.length ? Math.round((successfulRuns / runs.length) * 100) : 0}% 成功率`}
          tone="violet"
        />
        <MetricCard
          icon={Blocks}
          label="可用扩展"
          value={String(plugins.filter((plugin) => plugin.available).length).padStart(2, "0")}
          note={`${compactNumber(totalTokens)} tokens 已记录`}
          tone="amber"
        />
      </section>

      <section className="dashboard-grid">
        <div className="panel agent-panel">
          <div className="panel-heading">
            <div>
              <span className="section-kicker">FLEET</span>
              <h3>Agent 队列</h3>
            </div>
            <button className="card-link" onClick={() => onAgent(agents[0])}>管理全部</button>
          </div>
          <div className="agent-list">
            {agents.slice(0, 4).map((agent, index) => (
              <button className="agent-row" key={agent.id} onClick={() => onAgent(agent)}>
                <span className={`node-avatar ${["lime", "blue", "violet", "amber"][index % 4]}`}>
                  {agentInitials(agent.name)}
                </span>
                <span className="agent-row-copy">
                  <strong>{agent.name}</strong>
                  <small>{agent.description}</small>
                </span>
                <span className="agent-row-meta">
                  <span className={`status-badge ${agent.enabled ? "partial" : "stopped"}`}>
                    {agent.enabled ? "已启用" : "停用"}
                  </span>
                  <small>rev {agent.revision}</small>
                </span>
                <ChevronRight size={17} />
              </button>
            ))}
          </div>
        </div>

        <div className="panel activity-panel">
          <div className="panel-heading">
            <div>
              <span className="section-kicker">EVENT STREAM</span>
              <h3>最近活动</h3>
            </div>
            <button className="card-link" onClick={onViewRuns}>查看运行</button>
          </div>
          <div className="activity-list">
            {activities.map((item) => (
              <div className="activity-row" key={item.id}>
                <span className={`activity-icon ${item.tone}`}><item.icon size={15} /></span>
                <span className="activity-copy">
                  <strong>{item.title}</strong>
                  <small>{item.detail}</small>
                </span>
                <time>{item.time}</time>
              </div>
            ))}
            {!activities.length && (
              <div className="empty-inline">暂无运行活动</div>
            )}
          </div>
        </div>

        <div className="panel guardrail-panel">
          <div className="panel-heading">
            <div>
              <span className="section-kicker">GUARDRAILS</span>
              <h3>运行保护</h3>
            </div>
            <span className="status-badge partial">服务端能力状态</span>
          </div>
          <div className="guardrail-grid">
            {capabilities.slice(0, 4).map((capability) => (
              <div className="guardrail-item" key={capability.id}>
                <span><ShieldCheck size={17} /></span>
                <div>
                  <small>{capability.id}</small>
                  <strong>{capability.state}</strong>
                  <p>{capability.summary}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
  note,
  tone,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  note: string;
  tone: string;
}) {
  return (
    <div className="metric-card">
      <div className={`metric-icon ${tone}`}><Icon size={18} /></div>
      <div className="metric-card-copy">
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{note}</small>
      </div>
      <div className={`metric-spark ${tone}`}>
        <span /><span /><span /><span /><span />
      </div>
    </div>
  );
}

function AgentsView({
  agents,
  query,
  setQuery,
  onCreate,
  onSelect,
}: {
  agents: AgentSpec[];
  query: string;
  setQuery: (value: string) => void;
  onCreate: () => void;
  onSelect: (agent: AgentSpec) => void;
}) {
  return (
    <div className="view-stack">
      <div className="view-heading">
        <div>
          <span className="section-kicker">AGENT REGISTRY</span>
          <h2>配置与修订</h2>
          <p>Agent 定义、版本、工具和子 Agent 挂载保持可追踪。</p>
        </div>
        <button className="button button-primary" onClick={onCreate}>
          <Plus size={17} /> 新建 Agent
        </button>
      </div>
      <div className="toolbar">
        <label className="search-field">
          <Search size={17} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索 Agent、描述或 ID"
            aria-label="搜索 Agent"
          />
        </label>
        <button className="filter-button">全部状态 <ChevronDown size={15} /></button>
        <button className="filter-button">全部团队 <ChevronDown size={15} /></button>
        <span className="toolbar-count">{agents.length} 个结果</span>
      </div>
      <div className="agent-card-grid">
        {agents.map((agent, index) => (
          <button className="agent-card" key={agent.id} onClick={() => onSelect(agent)}>
            <div className="agent-card-top">
              <span className={`node-avatar large ${["lime", "blue", "violet", "amber"][index % 4]}`}>
                {agentInitials(agent.name)}
              </span>
              <span className={`status-badge ${agent.enabled ? "partial" : "stopped"}`}>
                <span className="status-mini-dot" />
                {agent.enabled ? "已启用" : "停用"}
              </span>
            </div>
            <h3>{agent.name}</h3>
            <p>{agent.description}</p>
            <div className="agent-card-tags">
              <span>配置 {agent.model.model_config_id}</span>
              <span>{agent.tools.length} tools</span>
              <span>{agent.children.length} children</span>
            </div>
            <div className="agent-card-footer">
              <span>rev {agent.revision}</span>
              <span>{agent.labels?.team || "default"}</span>
              <ChevronRight size={17} />
            </div>
          </button>
        ))}
        <button className="agent-card add-agent-card" onClick={onCreate}>
          <span className="add-agent-icon"><Plus size={24} /></span>
          <strong>创建新 Agent</strong>
          <p>从空白配置开始，或挂载已有 Agent 组成团队。</p>
        </button>
      </div>
    </div>
  );
}

function InstancesView({
  instances,
  agents,
  onCreate,
  onStatusChange,
  onRun,
}: {
  instances: AgentInstance[];
  agents: AgentSpec[];
  onCreate: () => void;
  onStatusChange: (
    instance: AgentInstance,
    status: "ready" | "stopped",
  ) => void;
  onRun: () => void;
}) {
  return (
    <div className="view-stack">
      <div className="view-heading">
        <div>
          <span className="section-kicker">AGENT INSTANCES</span>
          <h2>运行实例</h2>
          <p>同一 Agent 修订可以按环境标签创建多个实例，并分别治理并发与启停状态。</p>
        </div>
        <div className="heading-actions">
          <button className="button button-secondary" onClick={onRun}>
            <Play size={16} /> 发起运行
          </button>
          <button className="button button-primary" onClick={onCreate}>
            <Plus size={17} /> 新建实例
          </button>
        </div>
      </div>
      <div className="instance-grid">
        {instances.map((instance) => {
          const agent = agents.find((item) => item.id === instance.agent_id);
          const ready = instance.status === "ready";
          return (
            <article className="instance-card panel" key={instance.id}>
              <div className="instance-card-head">
                <span className="instance-icon">
                  {instance.environment === "cloud" ? (
                    <Cloud size={19} />
                  ) : (
                    <Server size={19} />
                  )}
                </span>
                <span className={`status-badge ${instance.status}`}>
                  <span className="status-mini-dot" />
                  {statusLabel(instance.status)}
                </span>
              </div>
              <h3>{instance.name}</h3>
              <p>{agent?.name || instance.agent_id}</p>
              <div className="instance-values">
                <div>
                  <span>环境标签</span>
                  <strong>{instance.environment}</strong>
                </div>
                <div>
                  <span>Agent 修订</span>
                  <strong>rev {instance.agent_revision || agent?.revision || "latest"}</strong>
                </div>
                <div>
                  <span>最大并发</span>
                  <strong>×{instance.max_concurrency}</strong>
                </div>
              </div>
              <div className="instance-card-footer">
                <code>{instance.id}</code>
                <button
                  className={`button ${ready ? "button-danger" : "button-secondary"}`}
                  onClick={() =>
                    onStatusChange(instance, ready ? "stopped" : "ready")
                  }
                >
                  {ready ? <Square size={13} /> : <Play size={13} />}
                  {ready ? "停止" : "启用"}
                </button>
              </div>
            </article>
          );
        })}
        <button className="instance-card panel add-instance-card" onClick={onCreate}>
          <span className="add-agent-icon"><Plus size={24} /></span>
          <strong>创建运行实例</strong>
          <p>固定 Agent 修订、环境标签与实例级并发上限；环境标签不触发部署。</p>
        </button>
      </div>
    </div>
  );
}

function TopologyView({
  rootAgent,
  mountedAgents,
  agents,
  onSelect,
}: {
  rootAgent?: AgentSpec;
  mountedAgents: AgentSpec[];
  agents: AgentSpec[];
  onSelect: (agent: AgentSpec) => void;
}) {
  return (
    <div className="view-stack">
      <div className="view-heading">
        <div>
          <span className="section-kicker">DELEGATION GRAPH</span>
          <h2>协作拓扑</h2>
          <p>发布前执行缺失节点、版本钉住和挂载环检测。</p>
        </div>
        <div className="topology-health">
          <CheckCircle2 size={17} />
          拓扑有效 · 无循环
        </div>
      </div>
      <div className="topology-workbench">
        <div className="canvas-toolbar">
          <div><Network size={16} /> Research team / current</div>
          <div>
            <button aria-label="适应画布"><Square size={15} /></button>
            <button aria-label="重置视图"><RotateCcw size={15} /></button>
          </div>
        </div>
        <div className="topology-canvas">
          <div className="canvas-grid" />
          {rootAgent && (
            <button className="canvas-node canvas-root" onClick={() => onSelect(rootAgent)}>
              <div className="canvas-node-header">
                <span className="node-avatar lime">{agentInitials(rootAgent.name)}</span>
                <span className="status-badge ready">Leader</span>
              </div>
              <strong>{rootAgent.name}</strong>
              <small>模型配置 · {rootAgent.model.model_config_id}</small>
              <div className="canvas-node-stats">
                <span><TerminalSquare size={13} /> {rootAgent.tools.length}</span>
                <span><Link2 size={13} /> {rootAgent.children.length}</span>
                <span>rev {rootAgent.revision}</span>
              </div>
              <span className="port port-bottom" />
            </button>
          )}
          <div className="canvas-connectors">
            <span className="connector-main" />
            <span className="connector-left" />
            <span className="connector-right" />
          </div>
          <div className="canvas-children">
            {mountedAgents.map((agent, index) => {
              const mount = rootAgent?.children.find((item) => item.agent_id === agent.id);
              return (
                <button className="canvas-node" key={agent.id} onClick={() => onSelect(agent)}>
                  <span className="port port-top" />
                  <div className="canvas-node-header">
                    <span className={`node-avatar ${index % 2 ? "violet" : "blue"}`}>
                      {agentInitials(agent.name)}
                    </span>
                    <span className="mount-alias">{mount?.alias}</span>
                  </div>
                  <strong>{agent.name}</strong>
                  <small>{mount?.description || agent.description}</small>
                  <div className="canvas-node-stats">
                    <span><TerminalSquare size={13} /> {agent.tools.length}</span>
                    <span><Cpu size={13} /> ×{mount?.max_concurrency || 1}</span>
                    <span>rev {agent.revision}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>
      <div className="topology-summary-grid">
        <div className="panel">
          <span className="section-kicker">GRAPH POLICY</span>
          <h3>委派约束</h3>
          <ul className="check-list">
            <li><Check size={15} /> 静态挂载环默认拒绝发布</li>
            <li><Check size={15} /> 子调用继承 deadline 与取消信号</li>
            <li><Check size={15} /> Root / Mount 并发闸门取最小值</li>
            <li><Check size={15} /> 工具与子 Agent 共享总调用预算</li>
          </ul>
        </div>
        <div className="panel">
          <span className="section-kicker">AVAILABLE NODES</span>
          <h3>未挂载 Agent</h3>
          <div className="compact-agent-list">
            {agents
              .filter((agent) => agent.id !== rootAgent?.id && !mountedAgents.some((item) => item.id === agent.id))
              .map((agent) => (
                <button key={agent.id} onClick={() => onSelect(agent)}>
                  <span className="node-avatar amber">{agentInitials(agent.name)}</span>
                  <span><strong>{agent.name}</strong><small>{agent.enabled ? "可挂载" : "当前停用"}</small></span>
                  <Plus size={16} />
                </button>
              ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function RunsView({
  runs,
  agents,
  resourceId,
  onResourceSelect,
  onRun,
  onCancel,
  apiBase,
  mode,
  requestHeaders,
  onRunProjection,
}: {
  runs: RunRecord[];
  agents: AgentSpec[];
  resourceId?: string | null;
  onResourceSelect: (resourceId: string | null) => void;
  onRun: () => void;
  onCancel: (id: string) => void;
  apiBase: string;
  mode: ConnectionMode;
  requestHeaders: () => HeadersInit;
  onRunProjection: (id: string, patch: Partial<RunRecord>) => void;
}) {
  const [selectedId, setSelectedId] = useState<string>(resourceId || runs[0]?.id || "");
  const [eventHistory, setEventHistory] = useState<{
    runId: string;
    events: RunEvent[];
    error: string;
    lastSequence: number;
    status: "idle" | "loading" | "live" | "reconnecting" | "degraded" | "complete";
  }>({ runId: "", events: [], error: "", lastSequence: 0, status: "idle" });
  const selected = runs.find((run) => run.id === selectedId) || runs[0] || null;
  const selectedRunId = selected?.id || "";
  const historyMatchesSelection = Boolean(selectedRunId) && eventHistory.runId === selectedRunId;
  const eventsLoading = mode === "live" && Boolean(selectedRunId) && (
    !historyMatchesSelection || eventHistory.status === "loading"
  );
  const eventsError = historyMatchesSelection ? eventHistory.error : "";
  const timelineEvents = mode === "live" && historyMatchesSelection ? eventHistory.events : [];

  useEffect(() => {
    if (!selectedRunId || mode !== "live") return;

    const controller = new AbortController();
    let active = true;
    let cursor = 0;
    let terminal = false;
    const timers = new Set<number>();

    const wait = (milliseconds: number) => new Promise<void>((resolve) => {
      const timer = window.setTimeout(() => {
        timers.delete(timer);
        resolve();
      }, milliseconds);
      timers.add(timer);
    });

    const applyEvents = (incoming: RunEvent[]) => {
      if (!active || !incoming.length) return;
      cursor = Math.max(cursor, ...incoming.map((event) => event.sequence));
      const terminalEvent = incoming.find((event) => Boolean(terminalStatusForEvent(event)) && event.type !== "run.started");
      if (terminalEvent) {
        terminal = true;
        const status = terminalStatusForEvent(terminalEvent);
        if (status) onRunProjection(selectedRunId, { status });
      }
      setEventHistory((current) => {
        const previous = current.runId === selectedRunId ? current.events : [];
        return {
          runId: selectedRunId,
          events: mergeRunEvents(previous, incoming),
          error: "",
          lastSequence: cursor,
          status: terminal ? "complete" : "live",
        };
      });
    };

    const loadHistory = async () => {
      setEventHistory((current) => ({
        runId: selectedRunId,
        events: current.runId === selectedRunId ? current.events : [],
        error: "",
        lastSequence: current.runId === selectedRunId ? current.lastSequence : 0,
        status: "loading",
      }));
      try {
        const history = await apiRequest<RunEvent[]>(
          `${apiBase}/runs/${selectedRunId}/events/history?after=0`,
          { headers: requestHeaders(), signal: controller.signal },
        );
        applyEvents(history);
        const run = await apiRequest<RunRecord>(`${apiBase}/runs/${selectedRunId}`, {
          headers: requestHeaders(),
          signal: controller.signal,
        });
        if (run.status === "succeeded" || run.status === "failed" || run.status === "cancelled") {
          terminal = true;
          onRunProjection(selectedRunId, { status: run.status, output: run.output, error: run.error, finished_at: run.finished_at, metrics: run.metrics });
          setEventHistory((current) => ({ ...current, status: "complete" }));
        }
      } catch (error) {
        if (active && !(error instanceof DOMException && error.name === "AbortError")) {
          setEventHistory((current) => ({
            ...current,
            runId: selectedRunId,
            status: "reconnecting",
            error: problemMessage(error, "事件历史暂不可用，正在尝试实时连接"),
          }));
        }
      }
    };

    const pollUntilTerminal = async () => {
      setEventHistory((current) => ({ ...current, status: "degraded", error: "实时事件暂不可用，正在进行有限校准" }));
      for (let attempt = 0; active && attempt < 12 && !terminal; attempt += 1) {
        try {
          const run = await apiRequest<RunRecord>(`${apiBase}/runs/${selectedRunId}`, {
            headers: requestHeaders(),
            signal: controller.signal,
          });
          onRunProjection(selectedRunId, {
            status: run.status,
            output: run.output,
            error: run.error,
            finished_at: run.finished_at,
            metrics: run.metrics,
          });
          const history = await apiRequest<RunEvent[]>(
            `${apiBase}/runs/${selectedRunId}/events/history?after=${cursor}`,
            { headers: requestHeaders(), signal: controller.signal },
          );
          applyEvents(history);
          if (run.status === "succeeded" || run.status === "failed" || run.status === "cancelled") {
            terminal = true;
            setEventHistory((current) => ({ ...current, status: "complete", error: "" }));
            return;
          }
        } catch (error) {
          if (error instanceof DOMException && error.name === "AbortError") return;
          if (active) setEventHistory((current) => ({ ...current, error: problemMessage(error, "运行状态暂不可用") }));
        }
        if (active && !terminal) await wait(2_500);
      }
    };

    const connect = async () => {
      await loadHistory();
      if (!active || terminal) return;
      let attempts = 0;
      while (active && !terminal && attempts < 3) {
        try {
          setEventHistory((current) => ({ ...current, runId: selectedRunId, status: attempts ? "reconnecting" : "live" }));
          await consumeEventStream<RunEvent>(
            `${apiBase}/runs/${selectedRunId}/events?after=${cursor}`,
            { headers: requestHeaders(), signal: controller.signal },
            ({ data }) => {
              if (data.run_id === selectedRunId) applyEvents([data]);
            },
          );
          if (!terminal) throw new Error("事件流已断开");
        } catch (error) {
          if (!active || (error instanceof DOMException && error.name === "AbortError")) return;
          attempts += 1;
          setEventHistory((current) => ({
            ...current,
            runId: selectedRunId,
            status: attempts >= 3 ? "degraded" : "reconnecting",
            error: problemMessage(error, "实时事件暂时中断"),
          }));
          if (attempts < 3) await wait(Math.min(4_000, attempts * 1_000));
        }
      }
      if (active && !terminal) await pollUntilTerminal();
    };

    void connect();

    return () => {
      active = false;
      controller.abort();
      for (const timer of timers) window.clearTimeout(timer);
    };
  }, [apiBase, mode, onRunProjection, requestHeaders, selectedRunId]);

  return (
    <div className="view-stack">
      <div className="view-heading">
        <div>
          <span className="section-kicker">RUN HISTORY</span>
          <h2>运行与事件</h2>
          <p>每次运行冻结根 Agent 修订，并按序持久化模型、工具与委派事件。</p>
        </div>
        <button className="button button-primary" onClick={onRun}><Play size={16} /> 发起运行</button>
      </div>
      <div className="runs-layout">
        <div className="run-list panel">
          <div className="run-list-head">
            <strong>最近运行</strong>
            <span>{runs.length}</span>
          </div>
          {runs.map((run) => {
            const agent = agents.find((item) => item.id === run.agent_id);
            return (
              <button
                className={`run-row ${selected?.id === run.id ? "selected" : ""}`}
                key={run.id}
                onClick={() => {
                  setSelectedId(run.id);
                  onResourceSelect(run.id);
                }}
              >
                <span className={`run-status-icon ${run.status}`}>
                  {run.status === "running" ? <LoaderCircle size={16} className="spinning" /> :
                    run.status === "succeeded" ? <Check size={16} /> :
                    run.status === "failed" ? <X size={16} /> : <Clock3 size={16} />}
                </span>
                <span className="run-row-copy">
                  <strong>{agent?.name || run.agent_id}</strong>
                  <small>{run.input}</small>
                </span>
                <span className="run-row-time">
                  <span className={`status-badge ${run.status}`}>{statusLabel(run.status)}</span>
                  <time>{formatTime(run.created_at)}</time>
                </span>
              </button>
            );
          })}
        </div>
        <div className="run-detail panel">
          {selected ? (
            <>
              <div className="run-detail-head">
                <div>
                  <span className="section-kicker">RUN DETAIL</span>
                  <h3>{selected.id}</h3>
                </div>
                <div className="run-detail-actions">
                  <span className={`status-badge ${selected.status}`}>{statusLabel(selected.status)}</span>
                  {selected.status === "running" && (
                    <button className="button button-danger" onClick={() => onCancel(selected.id)}>
                      <Square size={14} fill="currentColor" /> 取消
                    </button>
                  )}
                </div>
              </div>
              <div className="run-prompt">
                <span>INPUT</span>
                <p>{selected.input}</p>
              </div>
              <div className="run-metrics">
                <div><small>Steps</small><strong>{String(selected.metrics?.steps || "—")}</strong></div>
                <div><small>Tool calls</small><strong>{String(selected.metrics?.tool_calls || "—")}</strong></div>
                <div><small>Tokens</small><strong>{String(selected.metrics?.tokens || "—")}</strong></div>
                <div><small>Session</small><strong className="mono-small">{selected.session_id.slice(0, 12)}</strong></div>
              </div>
              <div className="timeline">
                <div className="timeline-head">
                  <strong>事件时间线</strong>
                  <span>
                    {eventsLoading
                      ? "正在读取持久事件"
                      : mode === "live"
                        ? `${timelineEvents.length} 条 · seq ${eventHistory.lastSequence} · ${eventHistory.status === "degraded" ? "降级校准" : eventHistory.status === "reconnecting" ? "重连中" : "实时"}`
                        : "未连接控制面"}
                  </span>
                </div>
                {timelineEvents.map((event) => (
                  <div className="timeline-row" key={`${event.run_id}-${event.sequence}`}>
                    <span className={`timeline-dot ${eventTone(event.type)}`} />
                    <span>
                      <strong>{eventTitle(event.type)}</strong>
                      <small>{eventDetail(event)}</small>
                    </span>
                    <time>#{event.sequence}</time>
                  </div>
                ))}
                {!eventsLoading && !eventsError && timelineEvents.length === 0 && (
                  <div className="empty-inline">该运行尚未写入事件</div>
                )}
                {eventsError && (
                  <div className="empty-inline">{eventsError}</div>
                )}
              </div>
            </>
          ) : (
            <div className="empty-state"><Activity size={28} /><strong>暂无运行</strong></div>
          )}
        </div>
      </div>
    </div>
  );
}

function PluginsView({ plugins }: { plugins: PluginManifest[] }) {
  const [kind, setKind] = useState("all");
  const kinds = Array.from(new Set(plugins.map((plugin) => plugin.kind)));
  const visible = kind === "all" ? plugins : plugins.filter((plugin) => plugin.kind === kind);
  return (
    <div className="view-stack">
      <div className="view-heading">
        <div>
          <span className="section-kicker">EXTENSION REGISTRY</span>
          <h2>扩展中心</h2>
          <p>发现不等于信任：协议版本、配置 Schema 和能力声明全部通过后才能启用。</p>
        </div>
        <div className="protocol-badge"><Braces size={16} /> Core protocol 1.x</div>
      </div>
      <div className="plugin-tabs">
        <button className={kind === "all" ? "active" : ""} onClick={() => setKind("all")}>全部 <span>{plugins.length}</span></button>
        {kinds.map((item) => (
          <button key={item} className={kind === item ? "active" : ""} onClick={() => setKind(item)}>
            {PLUGIN_KIND_LABELS[item] || item}
          </button>
        ))}
      </div>
      <div className="plugin-grid">
        {visible.map((plugin) => {
          const Icon = PLUGIN_ICONS[plugin.kind] || Blocks;
          return (
            <div className={`plugin-card ${!plugin.available ? "unavailable" : ""}`} key={`${plugin.kind}-${plugin.id}`}>
              <div className="plugin-card-head">
                <span className={`plugin-icon plugin-${plugin.kind}`}><Icon size={20} /></span>
                <div>
                  <span>{PLUGIN_KIND_LABELS[plugin.kind] || plugin.kind}</span>
                  <small>{plugin.source}</small>
                </div>
                <span className={`status-badge ${plugin.available ? "ready" : "stopped"}`}>
                  {plugin.available ? "可用" : "预留"}
                </span>
              </div>
              <h3>{plugin.display_name}</h3>
              <p>{plugin.description}</p>
              <div className="capability-list">
                {plugin.capabilities.slice(0, 3).map((capability) => <span key={capability}>{capability}</span>)}
              </div>
              <div className="plugin-card-footer">
                <code>{plugin.id}</code>
                <span>v{plugin.version} · p{plugin.protocol_version}</span>
              </div>
            </div>
          );
        })}
      </div>
      <div className="extension-contract panel">
        <div className="extension-contract-icon"><Code2 size={22} /></div>
        <div>
          <span className="section-kicker">BUILD YOUR OWN</span>
          <h3>稳定扩展契约，不绑死实现</h3>
          <p>第三方包通过 <code>uai_forge.plugins</code> entry point 注册；内核再校验协议主版本、能力和配置 Schema。</p>
        </div>
        <button className="button button-secondary">查看插件 SDK <ArrowRight size={16} /></button>
      </div>
    </div>
  );
}

type ModelConfigFormState = {
  name: string;
  provider: string;
  model: string;
  baseUrl: string;
  secret: string;
  timeoutSeconds: string;
  maxTokens: string;
  temperature: string;
  advancedJson: string;
  secretAction: "keep" | "replace" | "clear";
};

function newModelConfigForm(plugins: PluginManifest[]): ModelConfigFormState {
  const provider = providerOptionsFromPlugins(plugins)[0] || FALLBACK_PROVIDER_OPTIONS[0];
  return {
    name: "",
    provider: provider.id,
    model: provider.defaultModel,
    baseUrl: provider.defaultBaseUrl || "",
    secret: "",
    timeoutSeconds: "120",
    maxTokens: "4096",
    temperature: "0.7",
    advancedJson: "{}",
    secretAction: "replace",
  };
}

function formFromModelConfig(
  config: ModelConfig,
): ModelConfigFormState {
  const values = config.config || {};
  return {
    name: config.name,
    provider: config.provider,
    model: config.model,
    baseUrl: config.base_url || "",
    secret: "",
    timeoutSeconds: String(values.timeout_seconds ?? 120),
    maxTokens: String(values.max_tokens ?? 4096),
    temperature: String(values.temperature ?? 0.7),
    advancedJson: JSON.stringify(
      Object.fromEntries(
        Object.entries(values).filter(
          ([key]) => !["timeout_seconds", "max_tokens", "temperature", "base_url"].includes(key),
        ),
      ),
      null,
      2,
    ),
    secretAction: "keep",
  };
}

function ModelConfigsView({
  apiBase,
  mode,
  syncing,
  plugins,
  modelConfigs,
  resourceId,
  onResourceSelect,
  requestHeaders,
  onConfigChanged,
  onUpdate,
  onCheck,
  onDelete,
}: {
  apiBase: string;
  mode: ConnectionMode;
  syncing: boolean;
  plugins: PluginManifest[];
  modelConfigs: ModelConfig[];
  resourceId?: string | null;
  onResourceSelect: (resourceId: string | null) => void;
  requestHeaders: () => HeadersInit;
  onConfigChanged: () => void;
  onUpdate: (config: ModelConfig, patch: Record<string, unknown>) => Promise<void> | void;
  onCheck: (config: ModelConfig) => Promise<ModelConnectionCheckResult>;
  onDelete: (config: ModelConfig) => Promise<void> | void;
}) {
  const initialConfig = resourceId ? modelConfigs.find((item) => item.id === resourceId) : undefined;
  const [editingId, setEditingId] = useState<string | null>(initialConfig?.id || null);
  const [form, setForm] = useState<ModelConfigFormState>(() => initialConfig ? formFromModelConfig(initialConfig) : newModelConfigForm(plugins));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [actionId, setActionId] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<ModelConfig | null>(null);
  const [referenceCounts, setReferenceCounts] = useState<Record<string, number>>({});
  const selectedProvider = providerOptionFor(form.provider, plugins);

  useEffect(() => {
    if (mode !== "live" || !modelConfigs.length) {
      return;
    }
    let active = true;
    void Promise.allSettled(modelConfigs.map(async (config) => {
      const references = await apiRequest<ModelConfigReferences>(
        `${apiBase}/model-configs/${config.id}/references?limit=1`,
        { headers: requestHeaders() },
      );
      return [config.id, references.total] as const;
    })).then((results) => {
      if (!active) return;
      const next: Record<string, number> = {};
      for (const result of results) {
        if (result.status === "fulfilled") next[result.value[0]] = result.value[1];
      }
      setReferenceCounts(next);
    });
    return () => {
      active = false;
    };
  }, [apiBase, mode, modelConfigs, requestHeaders]);

  function startCreate() {
    onResourceSelect(null);
    setEditingId(null);
    setForm(newModelConfigForm(plugins));
    setError("");
  }

  function startEdit(config: ModelConfig) {
    onResourceSelect(config.id);
    setEditingId(config.id);
    setForm(formFromModelConfig(config));
    setError("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function updateForm(patch: Partial<ModelConfigFormState>) {
    setForm((current) => ({ ...current, ...patch }));
  }

  function selectProvider(provider: string) {
    const option = providerOptionFor(provider, plugins);
    updateForm({
      provider,
      model: option.defaultModel || modelOptionsForProvider(provider, plugins)[0]?.value || "",
      baseUrl: option.defaultBaseUrl || (provider === "anthropic_messages" ? "https://api.anthropic.com" : ""),
      secretAction: editingId ? "clear" : "replace",
    });
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const advanced = parseJsonObject(form.advancedJson, "高级参数 JSON");
      const config: Record<string, unknown> = {
        ...advanced,
        timeout_seconds: Number(form.timeoutSeconds),
        max_tokens: Number(form.maxTokens),
        temperature: Number(form.temperature),
      };
      const payload: Record<string, unknown> = {
        name: form.name,
        provider: form.provider,
        model: form.model,
        base_url: form.baseUrl || null,
        config,
        enabled: false,
        lifecycle: "draft",
      };
      if (form.secret.trim()) {
        payload.secret = form.secret.trim();
        payload.secret_action = "replace";
      } else if (editingId) {
        payload.secret_action = form.secretAction;
      } else {
        payload.secret_action = "clear";
      }
      if (mode !== "live") throw new Error("请先连接 Python 控制面；模型配置只写入数据库");
      if (editingId) {
        const current = modelConfigs.find((item) => item.id === editingId);
        if (!current) throw new Error("模型配置已不存在，请刷新后重试");
        await onUpdate(current, payload);
      } else {
        await apiRequest<ModelConfig>(`${apiBase}/model-configs`, {
          method: "POST",
          headers: requestHeaders(),
          body: JSON.stringify(payload),
        });
        onConfigChanged();
      }
      setEditingId(null);
      setForm(newModelConfigForm(plugins));
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  }

  async function remove(config: ModelConfig) {
    if (confirmDelete?.id !== config.id) {
      setConfirmDelete(config);
      return;
    }
    setActionId(`delete:${config.id}`);
    setBusy(true);
    setError("");
    try {
      await onDelete(config);
      setConfirmDelete(null);
      if (editingId === config.id) startCreate();
    } catch (caught) {
      setError(caught);
    } finally {
      setActionId(null);
      setBusy(false);
    }
  }

  async function check(config: ModelConfig) {
    setActionId(`check:${config.id}`);
    setError("");
    try {
      const result = await onCheck(config);
      if (result.status !== "passed") setError(`连接检查未通过：${result.code}`);
    } catch (caught) {
      setError(caught);
    } finally {
      setActionId(null);
    }
  }

  async function setLifecycle(config: ModelConfig, lifecycle: "enabled" | "disabled") {
    setActionId(`${lifecycle}:${config.id}`);
    setError("");
    try {
      await onUpdate(config, {
        lifecycle,
        enabled: lifecycle === "enabled",
        secret_action: "keep",
      });
    } catch (caught) {
      setError(caught);
    } finally {
      setActionId(null);
    }
  }

  return (
    <div className="view-stack settings-stack">
      <div className="view-heading">
        <div>
          <span className="section-kicker">TENANT MODEL CONNECTIONS</span>
          <h2>凭证&模型配置</h2>
          <p>每个租户维护自己的模型连接；协议、端点、模型和加密凭证集中在一条配置中。</p>
        </div>
        <button className="button button-primary" onClick={startCreate} disabled={syncing || busy}>
          <Plus size={16} /> 新建配置
        </button>
      </div>

      <form className="panel settings-panel" onSubmit={submit}>
        <div className="settings-panel-head">
          <span className="settings-icon"><KeyRound size={19} /></span>
          <div><h3>{editingId ? "编辑连接配置" : "新建连接配置"}</h3><p>密钥只在提交时写入数据库密文，列表永不返回明文。</p></div>
          {editingId && <button type="button" className="button button-ghost" onClick={startCreate}>取消编辑</button>}
        </div>
        <div className="form-row">
          <label className="form-field"><span>配置名称</span><input required minLength={2} value={form.name} onChange={(event) => updateForm({ name: event.target.value })} placeholder="例如：团队 DeepSeek 主连接" /></label>
          <ProviderChoiceField provider={form.provider} plugins={plugins} onChange={selectProvider} />
        </div>
        <div className="form-row">
          <ModelChoiceField provider={form.provider} plugins={plugins} model={form.model} onChange={(model) => updateForm({ model })} />
          <EndpointChoiceField provider={form.provider} value={form.baseUrl} onChange={(baseUrl) => updateForm({ baseUrl })} />
        </div>
        <div className="form-row">
          <label className="form-field"><span>{selectedProvider.requiresCredential === false ? "访问凭证（可选）" : "访问凭证"}</span><input type="password" value={form.secret} onChange={(event) => updateForm({ secret: event.target.value, secretAction: event.target.value ? "replace" : form.secretAction })} placeholder={editingId ? "留空表示沿用原密钥" : "粘贴 API Key，仅提交一次"} autoComplete="new-password" /><small>{selectedProvider.apiProtocol || "由 Provider manifest 决定协议"} · {selectedProvider.description}</small></label>
          {editingId ? <label className="form-field"><span>密钥动作</span><select value={form.secretAction} onChange={(event) => updateForm({ secretAction: event.target.value as ModelConfigFormState["secretAction"] })}><option value="keep">沿用当前密钥</option><option value="replace">提交新密钥</option><option value="clear">清除当前密钥</option></select><small>清除只允许在 Provider 不要求凭证时提交。</small></label> : <div className="form-field form-field-note"><span>保存阶段</span><strong>先保存草稿，再检查并启用</strong><small>创建不会把未验证连接标为可运行。</small></div>}
          <label className="form-field"><span>请求超时</span><select value={form.timeoutSeconds} onChange={(event) => updateForm({ timeoutSeconds: event.target.value })}>{MODEL_TIMEOUT_OPTIONS.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}</select></label>
        </div>
        <div className="form-row">
          <label className="form-field"><span>最大输出 Token</span><select value={form.maxTokens} onChange={(event) => updateForm({ maxTokens: event.target.value })}><option value="2048">2K · 轻量</option><option value="4096">4K · 推荐</option><option value="8192">8K · 长回答</option><option value="16384">16K · 复杂任务</option><option value="32768">32K · 超长任务</option></select></label>
          <label className="form-field"><span>Temperature</span><select value={form.temperature} onChange={(event) => updateForm({ temperature: event.target.value })}><option value="0">0 · 确定性</option><option value="0.2">0.2 · 稳定</option><option value="0.7">0.7 · 推荐</option><option value="1">1 · 发散</option></select></label>
        </div>
        <details className="advanced-config">
          <summary>模型配置 JSON · 高级参数（可选）</summary>
          <small>Provider 扩展参数 JSON：只填写非敏感参数，例如 top_p、headers 或 Anthropic 版本；不要粘贴 API Key。</small>
          <textarea className="json-config-field" value={form.advancedJson} onChange={(event) => updateForm({ advancedJson: event.target.value })} rows={5} spellCheck={false} />
        </details>
        <div className="run-policy-preview"><div><ShieldCheck size={16} /><span><strong>生命周期门</strong><small>保存为 draft；检查通过后才能显式启用，停用会让依赖 Agent readiness 失败。</small></span></div><span>draft → check → enable</span></div>
        <ProblemNotice problem={error} />
        <div className="modal-actions"><button type="submit" className="button button-primary" disabled={busy || mode !== "live"}>{busy ? "保存中…" : editingId ? "保存修改" : "创建配置"}</button></div>
      </form>

      <div className="panel settings-panel">
        <div className="settings-panel-head"><span className="settings-icon"><Cpu size={19} /></span><div><h3>已保存配置</h3><p>{modelConfigs.length ? `${modelConfigs.length} 条租户连接 · Agent 只选择这里的配置` : "还没有配置，先创建一条模型连接"}</p></div></div>
        {modelConfigs.length ? <div className="config-list">{modelConfigs.map((config) => <div className="config-list-row" key={config.id}>
          <span><strong>{config.name}</strong><small>{config.provider} · {config.model} · {config.protocol} · {config.masked_secret || "无凭证"}</small><small>生命周期：{config.lifecycle} · 检查：{config.verification.status}{config.verification.checked_at ? ` · ${formatTime(config.verification.checked_at)}` : ""} · 引用 Agent 修订：{referenceCounts[config.id] ?? "—"}</small></span>
          <span className="config-row-actions"><span className={`status-badge ${config.lifecycle === "enabled" ? "ready" : config.lifecycle === "verified" ? "partial" : config.lifecycle === "error" ? "failed" : "stopped"}`}>{config.lifecycle}</span><button className="button button-secondary" onClick={() => void check(config)} disabled={busy || actionId !== null}>{actionId === `check:${config.id}` ? "检查中…" : "检查连接"}</button>{config.lifecycle === "verified" && <button className="button button-primary" onClick={() => void setLifecycle(config, "enabled")} disabled={busy || actionId !== null}>启用</button>}{config.lifecycle === "enabled" && <button className="button button-ghost" onClick={() => void setLifecycle(config, "disabled")} disabled={busy || actionId !== null}>停用</button>}<button className="button button-ghost" onClick={() => startEdit(config)} disabled={busy}>编辑</button><button className="button button-danger" onClick={() => void remove(config)} disabled={busy || actionId !== null}>{confirmDelete?.id === config.id ? "再次确认删除" : "删除"}</button>{confirmDelete?.id === config.id && <button className="button button-ghost" onClick={() => setConfirmDelete(null)} disabled={busy}>取消</button>}</span>
        </div>)}</div> : <div className="empty-state"><KeyRound size={24} /><strong>暂无模型连接</strong><span>创建后这里会显示脱敏凭证和协议类型。</span></div>}
      </div>
    </div>
  );
}

function SettingsView({
  apiBase,
  apiKey,
  mode,
  syncing,
  runtimeConfig,
  capabilities,
  requestHeaders,
  onConfigChanged,
  onOpenModelConfigs,
  setApiBase,
  setApiKey,
  onConnect,
}: {
  apiBase: string;
  apiKey: string;
  mode: ConnectionMode;
  syncing: boolean;
  runtimeConfig: RuntimeConfigEntry[];
  capabilities: CapabilityStatus[];
  requestHeaders: () => HeadersInit;
  onConfigChanged: () => void;
  onOpenModelConfigs: () => void;
  setApiBase: (value: string) => void;
  setApiKey: (value: string) => void;
  onConnect: () => void;
}) {
  const [runtimeKey, setRuntimeKey] = useState("");
  const [runtimeValue, setRuntimeValue] = useState("{}");
  const [configBusy, setConfigBusy] = useState(false);
  const [configError, setConfigError] = useState("");
  const deploymentCapability = (id: string) => capabilities.find((item) => item.id === id);
  const localDeployment = deploymentCapability("single_process_runtime");
  const containerDeployment = deploymentCapability("single_node_container");
  const cloudDeployment = deploymentCapability("durable_cloud");

  async function saveRuntimeConfig(event: FormEvent) {
    event.preventDefault();
    setConfigBusy(true);
    setConfigError("");
    try {
      await apiRequest<RuntimeConfigEntry>(`${apiBase}/runtime-config`, {
        method: "PATCH",
        headers: requestHeaders(),
        body: JSON.stringify({ key: runtimeKey, value: JSON.parse(runtimeValue || "null") }),
      });
      setRuntimeKey("");
      setRuntimeValue("{}");
      onConfigChanged();
    } catch (error) {
      setConfigError(problemMessage(error, "运行配置保存失败"));
    } finally {
      setConfigBusy(false);
    }
  }

  return (
    <div className="view-stack settings-stack">
      <div className="view-heading">
        <div>
          <span className="section-kicker">SYSTEM CONFIGURATION</span>
          <h2>系统设置</h2>
          <p>控制后台与 Python 运行时解耦，可连接本地或云端控制面。</p>
        </div>
      </div>
      <div className="settings-grid">
        <div className="panel settings-panel">
          <div className="settings-panel-head">
            <span className="settings-icon"><Server size={19} /></span>
            <div><h3>运行时连接</h3><p>FastAPI Control API v1</p></div>
            <span className={`status-badge ${mode === "live" ? "ready" : "stopped"}`}>
              {mode === "live" ? "已连接" : "未连接"}
            </span>
          </div>
          <label className="form-field">
            <span>API 地址</span>
            <input value={apiBase} onChange={(event) => setApiBase(event.target.value)} placeholder="http://localhost:8000/api/v1" />
            <small>本地默认端口为 8000；云端填写 HTTPS 控制面地址。</small>
          </label>
          <label className="form-field">
            <span>控制面密钥（可选）</span>
            <input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="仅保存在当前页面内存" autoComplete="off" />
            <small>后台不会把密钥写入 Agent 配置或浏览器持久存储。</small>
          </label>
          <button className="button button-primary" onClick={onConnect} disabled={syncing}>
            {syncing ? <LoaderCircle size={16} className="spinning" /> : <Link2 size={16} />}
            {syncing ? "正在连接" : "测试并连接"}
          </button>
        </div>
        <div className="panel settings-panel">
          <div className="settings-panel-head"><span className="settings-icon"><KeyRound size={19} /></span><div><h3>凭证&模型配置</h3><p>已移到侧边栏独立页面；一条配置包含协议、模型、端点和加密凭证。</p></div><button className="button button-secondary" onClick={onOpenModelConfigs}>打开配置</button></div>
          <div className="setting-values">
            <div><span>配置事实源</span><strong>租户数据库</strong></div>
            <div><span>内置协议</span><strong>OpenAI Chat / Claude Messages</strong></div>
            <div><span>密钥返回</span><strong>仅脱敏</strong></div>
          </div>
        </div>
        <div className="panel settings-panel config-panel">
          <div className="settings-panel-head"><span className="settings-icon"><Braces size={19} /></span><div><h3>运行配置</h3><p>非敏感业务开关和默认值，按版本写入数据库</p></div></div>
          <form className="config-form" onSubmit={saveRuntimeConfig}><div className="form-row"><label className="form-field"><span>配置键</span><input required value={runtimeKey} onChange={(event) => setRuntimeKey(event.target.value)} placeholder="ui.page_size" /></label><label className="form-field"><span>JSON 值</span><input required value={runtimeValue} onChange={(event) => setRuntimeValue(event.target.value)} placeholder="50 或 {&quot;enabled&quot;:true}" /></label></div><button className="button button-secondary" disabled={configBusy || mode !== "live"}>{configBusy ? "保存中" : "保存运行配置"}</button></form>
          <div className="config-list">{runtimeConfig.length ? runtimeConfig.map((item) => <div className="config-list-row" key={item.key}><span><strong>{item.key}</strong><small>{previewValue(item.value)} · v{item.version}</small></span><span>{formatTime(item.updated_at)}</span></div>) : <div className="empty-inline">数据库中暂无运行配置</div>}</div>
        </div>
        {configError && <div className="form-error"><OctagonAlert size={16} /> {configError}</div>}
        <div className="panel settings-panel">
          <div className="settings-panel-head">
            <span className="settings-icon"><ShieldCheck size={19} /></span>
            <div><h3>安全能力状态</h3><p>只读 · 由运行时策略强制执行</p></div>
          </div>
          <div className="toggle-list">
            {capabilities.length ? capabilities.map((capability) => (
              <CapabilityStatus capability={capability} key={capability.id} />
            )) : <div className="empty-inline">正在读取服务端能力状态。</div>}
          </div>
        </div>
        <div className="panel settings-panel">
          <div className="settings-panel-head">
            <span className="settings-icon"><Database size={19} /></span>
            <div><h3>存储与事件</h3><p>Adapter capability</p></div>
          </div>
          <div className="setting-values">
            <div><span>当前存储</span><strong>SQLite</strong></div>
            <div><span>事件总线</span><strong>In-process + replay</strong></div>
            <div><span>事件顺序</span><strong>Per Run monotonic</strong></div>
            <div><span>规划适配器</span><strong>PostgreSQL / Redis（未实现）</strong></div>
          </div>
        </div>
        <div className="panel settings-panel">
          <div className="settings-panel-head">
            <span className="settings-icon"><Cloud size={19} /></span>
            <div><h3>部署能力</h3><p>说明 · 不是可点击的环境切换器</p></div>
          </div>
          <div className="deployment-options">
            <div className="deployment-option active">
              <Server size={18} />
              <span><strong>Local</strong><small>{localDeployment?.summary || "等待服务端部署能力状态"}</small></span>
              <span className={`deployment-state ${deploymentVisualState(localDeployment?.state)}`}>{localDeployment ? capabilityStateLabel(localDeployment.state) : "未知"}</span>
            </div>
            <div className="deployment-option">
              <Box size={18} />
              <span><strong>单节点容器</strong><small>{containerDeployment?.summary || "等待服务端部署能力状态"}</small></span>
              <span className={`deployment-state ${deploymentVisualState(containerDeployment?.state)}`}>{containerDeployment ? capabilityStateLabel(containerDeployment.state) : "未知"}</span>
            </div>
            <div className="deployment-option">
              <Cloud size={18} />
              <span><strong>可恢复云集群</strong><small>{cloudDeployment?.summary || "等待服务端部署能力状态"}</small></span>
              <span className={`deployment-state ${deploymentVisualState(cloudDeployment?.state)}`}>{cloudDeployment ? capabilityStateLabel(cloudDeployment.state) : "未知"}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function CapabilityStatus({
  capability,
}: {
  capability: CapabilityStatus;
}) {
  const visualState = capabilityVisualState(capability.state);
  return (
    <div className="setting-toggle capability-status">
      <span><strong>{capability.id}</strong><small>{capability.summary}{capability.limits.length ? ` · 限制：${capability.limits.join("；")}` : ""}</small></span>
      <span className={`capability-state ${visualState}`}>
        {capability.state === "implemented"
          ? <CheckCircle2 size={13} />
          : capability.state === "partial"
            ? <OctagonAlert size={13} />
            : <Square size={12} />}
        {capabilityStateLabel(capability.state)}
      </span>
    </div>
  );
}

function capabilityVisualState(state: CapabilityStatus["state"]): string {
  return state === "implemented" ? "enforced" : state === "unavailable" ? "disabled" : state;
}

function capabilityStateLabel(state: CapabilityStatus["state"]): string {
  return state === "implemented"
    ? "已实现"
    : state === "partial"
      ? "部分实现"
      : state === "planned"
        ? "规划"
        : "不可用";
}

function deploymentVisualState(state: CapabilityStatus["state"] | undefined): string {
  if (!state) return "unknown";
  return state === "implemented" ? "verified" : state === "unavailable" ? "disabled" : state;
}

function MountToolScopeEditor({
  mount,
  rowId,
  toolPlugins,
  onChange,
}: {
  mount: ChildMount;
  rowId: string;
  toolPlugins: PluginManifest[];
  onChange: (allowedTools: string[] | null) => void;
}) {
  const restricted = mount.allowed_tools != null;
  const allowedTools = mount.allowed_tools || [];
  const datalistId = `available-tool-plugin-ids-${rowId.replace(/[^a-zA-Z0-9_-]/g, "-")}`;

  return (
    <>
      <label className="form-field">
        <span>下游工具范围</span>
        <select
          value={restricted ? "restrict" : "inherit"}
          onChange={(event) => {
            if (event.target.value === "inherit") {
              onChange(null);
              return;
            }
            onChange(allowedTools);
          }}
        >
          <option value="inherit">继承上游，不新增限制</option>
          <option value="restrict">限制到插件 ID（空 = 全部拒绝）</option>
        </select>
      </label>
      <label className="form-field mount-tool-scope-field">
        <span>允许的工具插件 ID</span>
        <input
          disabled={!restricted}
          list={datalistId}
          value={allowedTools.join(", ")}
          placeholder="tool.echo, tool.calculator"
          onChange={(event) => {
            const pluginIds = Array.from(new Set(
              event.target.value
                .split(",")
                .map((item) => item.trim())
                .filter(Boolean),
            ));
            onChange(pluginIds);
          }}
        />
        <small>范围会沿整个子树取交集，后代不能重新放宽。</small>
        <datalist id={datalistId}>
          {toolPlugins.map((plugin) => (
            <option value={plugin.id} key={plugin.id} />
          ))}
        </datalist>
      </label>
    </>
  );
}

function AgentDrawer({
  agent,
  agents,
  modelConfigs,
  onClose,
  onEdit,
  onRun,
}: {
  agent: AgentSpec;
  agents: AgentSpec[];
  modelConfigs: ModelConfig[];
  onClose: () => void;
  onEdit: () => void;
  onRun: () => void;
}) {
  const modelConfig = modelConfigs.find(
    (item) => item.id === agent.model.model_config_id,
  );
  const dialogRef = useDialogAccessibility(onClose);
  return (
    <div ref={dialogRef} className="drawer-layer" role="dialog" aria-modal="true" aria-label={`${agent.name} 配置`}>
      <button className="modal-scrim" onClick={onClose} aria-label="关闭 Agent 详情" />
      <aside className="agent-drawer">
        <div className="drawer-head">
          <div className="drawer-agent-title">
            <span className="node-avatar large lime">{agentInitials(agent.name)}</span>
            <div><span className="section-kicker">AGENT REVISION</span><h2>{agent.name}</h2></div>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="关闭"><X size={19} /></button>
        </div>
        <div className="drawer-badges">
          <span className={`status-badge ${agent.enabled ? "partial" : "stopped"}`}>{agent.enabled ? "已启用" : "停用"}</span>
          <span>rev {agent.revision}</span>
          <span>{agent.labels?.team || "default"}</span>
        </div>
        <p className="drawer-description">{agent.description}</p>
        <div className="drawer-section">
          <div className="drawer-section-title"><Cpu size={16} /> 模型</div>
          <div className="config-value"><span>配置</span><strong>{modelConfig?.name || agent.model.model_config_id}</strong></div>
          <div className="config-value"><span>Provider / Model</span><strong>{modelConfig ? `${modelConfig.provider} / ${modelConfig.model}` : "按租户配置解析"}</strong></div>
          <div className="config-value"><span>协议</span><strong>{modelConfig?.protocol || "运行时解析"}</strong></div>
        </div>
        <div className="drawer-section">
          <div className="drawer-section-title"><Link2 size={16} /> 子 Agent 挂载</div>
          {agent.children.length ? agent.children.map((mount) => {
            const target = agents.find((item) => item.id === mount.agent_id);
            return (
              <div className="mount-row" key={mount.alias}>
                <span className="node-avatar blue">{target ? agentInitials(target.name) : "?"}</span>
                <span>
                  <strong>{mount.alias}</strong>
                  <small>
                    {target?.name || mount.agent_id} · 工具
                    {mount.allowed_tools == null
                      ? "继承"
                      : mount.allowed_tools.length
                        ? mount.allowed_tools.join(", ")
                        : "全部拒绝"}
                  </small>
                </span>
                <span>×{mount.max_concurrency || 1}</span>
              </div>
            );
          }) : <div className="empty-inline">未挂载子 Agent</div>}
        </div>
        <div className="drawer-section">
          <div className="drawer-section-title"><CircleGauge size={16} /> 执行策略</div>
          <div className="policy-grid">
            <div><span>最大步数</span><strong>{agent.policy.max_steps}</strong></div>
            <div><span>最大深度</span><strong>{agent.policy.max_depth}</strong></div>
            <div><span>工具调用</span><strong>{agent.policy.max_tool_calls}</strong></div>
            <div><span>Token 预算</span><strong>{compactNumber(agent.policy.token_budget)}</strong></div>
          </div>
        </div>
        <div className="drawer-section">
          <div className="drawer-section-title"><TerminalSquare size={16} /> 工具</div>
          <div className="tool-chip-list">
            {agent.tools.length ? agent.tools.map((tool) => <span key={tool.alias || tool.plugin_id}>{tool.alias || tool.plugin_id}<small>{tool.permission || "auto"}</small></span>) : <div className="empty-inline">无工具绑定</div>}
          </div>
        </div>
        <div className="drawer-section">
          <div className="drawer-section-title"><Layers3 size={16} /> 记忆与中间件</div>
          <div className="tool-chip-list">
            <span>
              {agent.memory?.plugin_id || "memory.in_process"}
              <small>{agent.memory?.enabled === false ? "disabled" : "memory"}</small>
            </span>
            {(agent.middlewares || []).map((middleware, index) => (
              <span key={`${middleware.plugin_id}:${index}`}>
                {middleware.plugin_id}
                <small>{middleware.enabled === false ? "disabled" : "middleware"}</small>
              </span>
            ))}
          </div>
        </div>
        <div className="drawer-actions">
          <button className="button button-secondary" onClick={onEdit}>
            <GitBranch size={16} /> 编辑并发布修订
          </button>
          <button className="button button-primary" onClick={onRun}><Play size={16} /> 运行</button>
        </div>
      </aside>
    </div>
  );
}

function NewAgentModal({
  agents,
  plugins,
  modelConfigs,
  onClose,
  onCreate,
}: {
  agents: AgentSpec[];
  plugins: PluginManifest[];
  modelConfigs: ModelConfig[];
  onClose: () => void;
  onCreate: (form: NewAgentForm) => Promise<void>;
}) {
  const toolPlugins = plugins.filter((plugin) => plugin.kind === "tool" && plugin.available);
  const memoryPlugins = plugins.filter((plugin) => plugin.kind === "memory" && plugin.available);
  const middlewarePlugins = plugins.filter((plugin) => plugin.kind === "middleware" && plugin.available);
  const availableModelConfigs = modelConfigs.filter((item) => item.enabled && item.lifecycle === "enabled");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("你是一个可靠、可审计的专业 Agent。");
  const [modelConfigId, setModelConfigId] = useState(availableModelConfigs[0]?.id || "");
  const [children, setChildren] = useState<ChildMount[]>([]);
  const [tools, setTools] = useState<ToolBindingSpec[]>([]);
  const [toolConfigTexts, setToolConfigTexts] = useState<string[]>([]);
  const [memoryPluginId, setMemoryPluginId] = useState(
    memoryPlugins[0]?.id || "memory.in_process",
  );
  const [memoryEnabled, setMemoryEnabled] = useState(true);
  const [memoryConfigText, setMemoryConfigText] = useState(
    '{\n  "max_messages": 40\n}',
  );
  const [middlewares, setMiddlewares] = useState<MiddlewareBindingSpec[]>([]);
  const [middlewareConfigTexts, setMiddlewareConfigTexts] = useState<string[]>([]);
  const [enabled, setEnabled] = useState(true);
  const [policy, setPolicy] = useState<AgentSpec["policy"]>({
    max_steps: 12,
    max_depth: 4,
    max_tool_calls: 20,
    max_parallel_children: 4,
    timeout_seconds: 120,
    token_budget: 24000,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [step, setStep] = useState(0);
  const wizardSteps = ["基础", "能力", "策略", "Review"];
  const canAdvance = step === 0
    ? Boolean(name.trim() && modelConfigId && systemPrompt.trim())
    : true;
  const dialogRef = useDialogAccessibility(onClose);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (step < wizardSteps.length - 1) {
      if (canAdvance) setStep((current) => Math.min(wizardSteps.length - 1, current + 1));
      return;
    }
    setError("");
    setBusy(true);
    try {
      const configuredTools = tools.map((tool, index) => ({
        ...tool,
        config: parseJsonObject(
          toolConfigTexts[index] || "{}",
          `${tool.plugin_id} 配置`,
        ),
      }));
      const configuredMiddlewares = middlewares.map((middleware, index) => ({
        ...middleware,
        config: parseJsonObject(
          middlewareConfigTexts[index] || "{}",
          `${middleware.plugin_id} 配置`,
        ),
      }));
      await onCreate({
        name,
        description,
        systemPrompt,
        modelConfigId,
        children,
        tools: configuredTools,
        memory: {
          plugin_id: memoryPluginId,
          enabled: memoryEnabled,
          config: parseJsonObject(memoryConfigText, "记忆配置"),
        },
        middlewares: configuredMiddlewares,
        enabled,
        policy,
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "创建失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div ref={dialogRef} className="modal-layer" role="dialog" aria-modal="true" aria-labelledby="new-agent-title">
      <button className="modal-scrim" onClick={onClose} aria-label="关闭新建 Agent" />
      <form className="modal-card new-agent-modal" onSubmit={submit}>
        <div className="modal-head">
          <div><span className="section-kicker">NEW AGENT</span><h2 id="new-agent-title">创建 Agent</h2></div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="关闭"><X size={19} /></button>
        </div>
        <div className="modal-body">
          <nav className="wizard-steps" aria-label="Agent 创建步骤">
            {wizardSteps.map((label, index) => (
              <button
                type="button"
                key={label}
                className={index === step ? "active" : index < step ? "complete" : ""}
                aria-current={index === step ? "step" : undefined}
                onClick={() => {
                  if (index <= step || (index === step + 1 && canAdvance)) setStep(index);
                }}
              >
                <span>{index + 1}</span>{label}
              </button>
            ))}
          </nav>
          {step === 0 && <section className="wizard-step" aria-labelledby="agent-step-basic">
            <div className="wizard-step-heading">
              <div><span className="section-kicker">STEP 1 / 4</span><h3 id="agent-step-basic">基础</h3></div>
              <p>先定义职责和已验证的模型连接，后续步骤都可以返回修改。</p>
            </div>
            <div className="form-row">
            <label className="form-field"><span>名称</span><input required minLength={2} value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：合规审查 Agent" /></label>
            <label className="form-field"><span>模型配置</span><select required value={modelConfigId} onChange={(event) => setModelConfigId(event.target.value)}><option value="">请选择已验证并启用的模型配置</option>{availableModelConfigs.map((item) => <option value={item.id} key={item.id}>{item.name} · {item.provider} / {item.model}</option>)}</select><small>模型、协议、端点和凭证都来自租户模型配置。</small></label>
            </div>
            <label className="form-field"><span>描述</span><input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="一句话说明职责边界" /></label>
            <label className="form-field"><span>系统提示词</span><textarea required rows={4} value={systemPrompt} onChange={(event) => setSystemPrompt(event.target.value)} /></label>
          </section>}
          {step === 1 && <section className="wizard-step wizard-step-abilities" aria-labelledby="agent-step-abilities">
            <div className="wizard-step-heading">
              <div><span className="section-kicker">STEP 2 / 4</span><h3 id="agent-step-abilities">能力</h3></div>
              <p>工具、记忆、中间件和子 Agent 都按插件 ID 与策略范围保存。</p>
            </div>
          <fieldset className="child-picker tool-picker">
            <legend>工具绑定 <span>可选</span></legend>
            <p>工具通过稳定插件 ID 绑定；可为每个绑定配置调用别名与权限策略。</p>
            <div className="picker-grid">
              {toolPlugins.map((plugin) => {
                const selected = tools.some((tool) => tool.plugin_id === plugin.id);
                return (
                  <button
                    type="button"
                    key={plugin.id}
                    className={selected ? "selected" : ""}
                    onClick={() => {
                      if (selected) {
                        setToolConfigTexts((current) => current.filter(
                          (_, index) => tools[index]?.plugin_id !== plugin.id,
                        ));
                        setTools((current) => current.filter(
                          (tool) => tool.plugin_id !== plugin.id,
                        ));
                        return;
                      }
                      setTools((current) => [
                        ...current,
                        {
                          plugin_id: plugin.id,
                          alias:
                            plugin.id.split(".").pop()?.replace(/-/g, "_") ||
                            plugin.id,
                          enabled: true,
                          permission: "auto",
                          config: {},
                        },
                      ]);
                      setToolConfigTexts((current) => [...current, "{}"]);
                    }}
                  >
                    <span className="node-avatar amber"><TerminalSquare size={14} /></span>
                    <span><strong>{plugin.display_name}</strong><small>{plugin.id}</small></span>
                    <span className="checkbox-mark">{selected && <Check size={14} />}</span>
                  </button>
                );
              })}
            </div>
            {tools.length > 0 && (
              <div className="binding-editor-list">
                {tools.map((tool, toolIndex) => (
                  <div
                    className="binding-editor-row"
                    key={`${tool.plugin_id}:${toolIndex}`}
                  >
                    <label className="form-field">
                      <span>{tool.plugin_id} · 调用别名</span>
                      <input
                        required
                        minLength={2}
                        value={tool.alias || ""}
                        onChange={(event) => setTools((current) => current.map((item, index) => (
                          index === toolIndex
                            ? { ...item, alias: event.target.value }
                            : item
                        )))}
                      />
                    </label>
                    <label className="form-field">
                      <span>权限</span>
                      <select
                        value={tool.permission || "auto"}
                        onChange={(event) => setTools((current) => current.map((item, index) => (
                          index === toolIndex
                            ? {
                                ...item,
                                permission: event.target.value as ToolBindingSpec["permission"],
                              }
                            : item
                        )))}
                      >
                        <option value="auto">auto · 自动执行</option>
                        <option value="confirm">confirm · 等待批准</option>
                        <option value="deny">deny · 禁止执行</option>
                      </select>
                    </label>
                    <label className="form-field json-config-field">
                      <span>配置 JSON</span>
                      <textarea
                        rows={3}
                        value={toolConfigTexts[toolIndex] || "{}"}
                        onChange={(event) => setToolConfigTexts((current) => current.map(
                          (value, index) => (
                            index === toolIndex ? event.target.value : value
                          ),
                        ))}
                        spellCheck={false}
                      />
                    </label>
                  </div>
                ))}
              </div>
            )}
          </fieldset>
          <fieldset className="child-picker">
            <legend>记忆与中间件</legend>
            <p>通过稳定插件 ID 绑定；配置保留为 JSON，以便第三方 Schema 无需改核心表单。</p>
            <div className="memory-editor-grid">
              <label className="form-field">
                <span>记忆适配器</span>
                <select value={memoryPluginId} onChange={(event) => setMemoryPluginId(event.target.value)}>
                  {memoryPlugins.map((plugin) => (
                    <option value={plugin.id} key={plugin.id}>{plugin.display_name}</option>
                  ))}
                </select>
              </label>
              <label className="form-field">
                <span>记忆状态</span>
                <select value={memoryEnabled ? "enabled" : "disabled"} onChange={(event) => setMemoryEnabled(event.target.value === "enabled")}>
                  <option value="enabled">启用</option>
                  <option value="disabled">停用</option>
                </select>
              </label>
              <label className="form-field json-config-field memory-config-field">
                <span>记忆配置 JSON</span>
                <textarea
                  rows={3}
                  value={memoryConfigText}
                  onChange={(event) => setMemoryConfigText(event.target.value)}
                  spellCheck={false}
                />
              </label>
            </div>
            {middlewarePlugins.length > 0 && (
              <div className="picker-grid middleware-picker-grid">
                {middlewarePlugins.map((plugin) => {
                  const selected = middlewares.some((item) => item.plugin_id === plugin.id);
                  return (
                    <button
                      type="button"
                      key={plugin.id}
                      className={selected ? "selected" : ""}
                      onClick={() => {
                        if (selected) {
                          setMiddlewareConfigTexts((current) => current.filter(
                            (_, index) => middlewares[index]?.plugin_id !== plugin.id,
                          ));
                          setMiddlewares((current) => current.filter(
                            (item) => item.plugin_id !== plugin.id,
                          ));
                          return;
                        }
                        setMiddlewares((current) => [
                          ...current,
                          { plugin_id: plugin.id, enabled: true, config: {} },
                        ]);
                        setMiddlewareConfigTexts((current) => [...current, "{}"]);
                      }}
                    >
                      <span className="node-avatar violet"><Workflow size={14} /></span>
                      <span><strong>{plugin.display_name}</strong><small>{plugin.id}</small></span>
                      <span className="checkbox-mark">{selected && <Check size={14} />}</span>
                    </button>
                  );
                })}
              </div>
            )}
            {middlewares.length > 0 && (
              <div className="binding-editor-list">
                {middlewares.map((middleware, middlewareIndex) => (
                  <div
                    className="binding-editor-row middleware-editor-row"
                    key={`${middleware.plugin_id}:${middlewareIndex}`}
                  >
                    <div className="binding-editor-title">
                      <strong>{middleware.plugin_id}</strong>
                      <small>middleware binding</small>
                    </div>
                    <label className="form-field">
                      <span>状态</span>
                      <select
                        value={middleware.enabled === false ? "disabled" : "enabled"}
                        onChange={(event) => setMiddlewares((current) => current.map((item, index) => (
                          index === middlewareIndex
                            ? { ...item, enabled: event.target.value === "enabled" }
                            : item
                        )))}
                      >
                        <option value="enabled">启用</option>
                        <option value="disabled">停用</option>
                      </select>
                    </label>
                    <label className="form-field json-config-field">
                      <span>配置 JSON</span>
                      <textarea
                        rows={3}
                        value={middlewareConfigTexts[middlewareIndex] || "{}"}
                        onChange={(event) => setMiddlewareConfigTexts((current) => current.map(
                          (value, index) => (
                            index === middlewareIndex ? event.target.value : value
                          ),
                        ))}
                        spellCheck={false}
                      />
                    </label>
                  </div>
                ))}
              </div>
            )}
          </fieldset>
          <fieldset className="child-picker">
            <legend>挂载子 Agent <span>可选</span></legend>
            <p>挂载会钉住修订，并以受治理的 delegate 工具暴露给父 Agent。</p>
            <div className="picker-grid">
              {agents.map((agent) => {
                const selected = children.some((mount) => mount.agent_id === agent.id);
                return (
                  <button
                    type="button"
                    key={agent.id}
                    className={selected ? "selected" : ""}
                    onClick={() => setChildren((current) => (
                      selected
                        ? current.filter((mount) => mount.agent_id !== agent.id)
                        : [
                            ...current,
                            {
                              alias:
                                agent.id
                                  .replace(/^agt_/, "")
                                  .replace(/[^a-zA-Z0-9_-]/g, "_")
                                  .slice(0, 31) || `child_${current.length + 1}`,
                              agent_id: agent.id,
                              description: agent.description || "已挂载子 Agent",
                              revision: agent.revision,
                              max_concurrency: 2,
                              input_template: "{input}",
                              allowed_tools: null,
                            },
                          ]
                    ))}
                  >
                    <span className="node-avatar blue">{agentInitials(agent.name)}</span>
                    <span><strong>{agent.name}</strong><small>rev {agent.revision}</small></span>
                    <span className="checkbox-mark">{selected && <Check size={14} />}</span>
                  </button>
                );
              })}
            </div>
            {children.length > 0 && (
              <div className="mount-editor-list">
                {children.map((mount, mountIndex) => {
                  const target = agents.find((item) => item.id === mount.agent_id);
                  return (
                    <div
                      className="mount-editor-row"
                      key={`${mount.agent_id}:${mountIndex}`}
                    >
                      <div className="binding-editor-title">
                        <strong>{target?.name || mount.agent_id}</strong>
                        <small>{mount.agent_id}</small>
                      </div>
                      <label className="form-field">
                        <span>挂载别名</span>
                        <input
                          required
                          minLength={2}
                          value={mount.alias}
                          onChange={(event) => setChildren((current) => current.map((item, index) => (
                            index === mountIndex
                              ? { ...item, alias: event.target.value }
                              : item
                          )))}
                        />
                      </label>
                      <label className="form-field">
                        <span>固定修订</span>
                        <input
                          type="number"
                          min={1}
                          value={mount.revision ?? ""}
                          onChange={(event) => setChildren((current) => current.map((item, index) => (
                            index === mountIndex
                              ? {
                                  ...item,
                                  revision: event.target.value
                                    ? Math.max(1, Number(event.target.value))
                                    : undefined,
                                }
                              : item
                          )))}
                        />
                      </label>
                      <label className="form-field">
                        <span>最大并发</span>
                        <input
                          type="number"
                          min={1}
                          max={64}
                          value={mount.max_concurrency || 1}
                          onChange={(event) => setChildren((current) => current.map((item, index) => (
                            index === mountIndex
                              ? {
                                  ...item,
                                  max_concurrency: Math.max(1, Number(event.target.value) || 1),
                                }
                              : item
                          )))}
                        />
                      </label>
                      <MountToolScopeEditor
                        mount={mount}
                        rowId={`new-${mount.agent_id}-${mountIndex}`}
                        toolPlugins={toolPlugins}
                        onChange={(allowedTools) => setChildren((current) => current.map((item, index) => (
                          index === mountIndex
                            ? { ...item, allowed_tools: allowedTools }
                            : item
                        )))}
                      />
                      <label className="form-field mount-template-field">
                        <span>输入模板</span>
                        <input
                          required
                          value={mount.input_template || "{input}"}
                          onChange={(event) => setChildren((current) => current.map((item, index) => (
                            index === mountIndex
                              ? { ...item, input_template: event.target.value }
                              : item
                          )))}
                        />
                      </label>
                    </div>
                  );
                })}
              </div>
            )}
          </fieldset>
          </section>}
          {step === 2 && <section className="wizard-step" aria-labelledby="agent-step-policy">
            <div className="wizard-step-heading">
              <div><span className="section-kicker">STEP 3 / 4</span><h3 id="agent-step-policy">策略</h3></div>
              <p>这些限制会进入根预算账本，并传播到所有子 Agent 调用。</p>
            </div>
          <fieldset className="child-picker policy-editor">
            <legend>运行策略</legend>
            <p>先用默认值即可；需要时再收紧深度、并发、超时和 token 上限。</p>
            <div className="policy-editor-grid">
              <label className="form-field">
                <span>最大步数</span>
                <input type="number" min={1} max={128} value={policy.max_steps} onChange={(event) => setPolicy((current) => ({ ...current, max_steps: Math.max(1, Number(event.target.value) || 1) }))} />
              </label>
              <label className="form-field">
                <span>最大深度</span>
                <input type="number" min={0} max={16} value={policy.max_depth} onChange={(event) => setPolicy((current) => ({ ...current, max_depth: Math.max(0, Number(event.target.value) || 0) }))} />
              </label>
              <label className="form-field">
                <span>工具调用</span>
                <input type="number" min={0} max={1024} value={policy.max_tool_calls} onChange={(event) => setPolicy((current) => ({ ...current, max_tool_calls: Math.max(0, Number(event.target.value) || 0) }))} />
              </label>
              <label className="form-field">
                <span>子 Agent 并发</span>
                <input type="number" min={1} max={128} value={policy.max_parallel_children} onChange={(event) => setPolicy((current) => ({ ...current, max_parallel_children: Math.max(1, Number(event.target.value) || 1) }))} />
              </label>
              <label className="form-field">
                <span>超时（秒）</span>
                <input type="number" min={1} max={3600} value={policy.timeout_seconds} onChange={(event) => setPolicy((current) => ({ ...current, timeout_seconds: Math.max(1, Number(event.target.value) || 1) }))} />
              </label>
              <label className="form-field">
                <span>Token 预算</span>
                <input type="number" min={1} value={policy.token_budget} onChange={(event) => setPolicy((current) => ({ ...current, token_budget: Math.max(1, Number(event.target.value) || 1) }))} />
              </label>
              <label className="form-field">
                <span>初始状态</span>
                <select value={enabled ? "enabled" : "disabled"} onChange={(event) => setEnabled(event.target.value === "enabled")}>
                  <option value="enabled">启用</option>
                  <option value="disabled">停用</option>
                </select>
              </label>
            </div>
          </fieldset>
          </section>}
          {step === 3 && <section className="wizard-step wizard-review" aria-labelledby="agent-step-review">
            <div className="wizard-step-heading">
              <div><span className="section-kicker">STEP 4 / 4</span><h3 id="agent-step-review">Review</h3></div>
              <p>提交后服务端仍会复验模型配置、插件 Schema、挂载图和预算边界。</p>
            </div>
            <div className="review-summary">
              <div><span>名称</span><strong>{name || "未填写"}</strong></div>
              <div><span>模型连接</span><strong>{availableModelConfigs.find((item) => item.id === modelConfigId)?.name || "未选择"}</strong></div>
              <div><span>能力绑定</span><strong>{tools.length} 个工具 · {middlewares.length} 个中间件 · {children.length} 个子 Agent</strong></div>
              <div><span>运行策略</span><strong>{policy.max_steps} 步 · {policy.timeout_seconds} 秒 · {compactNumber(policy.token_budget)} tokens</strong></div>
            </div>
            <div className="readiness-issue-list">
              <div><CheckCircle2 size={16} /><strong>模型配置已限定为已验证并启用的连接</strong><span>Agent 不会保存 Provider SDK 对象或明文凭证。</span></div>
              <div><ShieldCheck size={16} /><strong>创建后生成 revision 1</strong><span>后续编辑会发布新修订，已有 Instance 可继续钉住旧修订。</span></div>
            </div>
          </section>}
          {error && <div className="form-error"><OctagonAlert size={16} /> {error}</div>}
        </div>
        <div className="modal-actions">
          <button type="button" className="button button-ghost" onClick={onClose}>取消</button>
          {step > 0 && <button type="button" className="button button-ghost" onClick={() => setStep((current) => Math.max(0, current - 1))} disabled={busy}>上一步</button>}
          <button className="button button-primary" disabled={busy || (step === 0 && !canAdvance)}>
            {busy ? <LoaderCircle size={16} className="spinning" /> : step === wizardSteps.length - 1 ? <Plus size={16} /> : <ArrowRight size={16} />}
            {busy ? "创建中…" : step === wizardSteps.length - 1 ? "创建 Agent" : "下一步"}
          </button>
        </div>
      </form>
    </div>
  );
}

function EditAgentModal({
  agent,
  agents,
  plugins,
  modelConfigs,
  onClose,
  onSave,
}: {
  agent: AgentSpec;
  agents: AgentSpec[];
  plugins: PluginManifest[];
  modelConfigs: ModelConfig[];
  onClose: () => void;
  onSave: (form: AgentConfigurationForm) => Promise<void>;
}) {
  const toolPlugins = plugins.filter(
    (plugin) => plugin.kind === "tool" && plugin.available,
  );
  const memoryPlugins = plugins.filter(
    (plugin) => plugin.kind === "memory" && plugin.available,
  );
  const middlewarePlugins = plugins.filter(
    (plugin) => plugin.kind === "middleware" && plugin.available,
  );
  const [name, setName] = useState(agent.name);
  const [description, setDescription] = useState(agent.description);
  const [systemPrompt, setSystemPrompt] = useState(agent.system_prompt);
  const [modelConfigId, setModelConfigId] = useState(agent.model.model_config_id);
  const [tools, setTools] = useState<ToolBindingSpec[]>(agent.tools);
  const [toolConfigTexts, setToolConfigTexts] = useState<string[]>(
    () => agent.tools.map((tool) => JSON.stringify(tool.config || {}, null, 2)),
  );
  const [children, setChildren] = useState<ChildMount[]>(agent.children);
  const [memoryPluginId, setMemoryPluginId] = useState(
    agent.memory?.plugin_id || memoryPlugins[0]?.id || "memory.in_process",
  );
  const [memoryEnabled, setMemoryEnabled] = useState(
    agent.memory?.enabled !== false,
  );
  const [memoryConfigText, setMemoryConfigText] = useState(
    JSON.stringify(agent.memory?.config || {}, null, 2),
  );
  const [middlewares, setMiddlewares] = useState<MiddlewareBindingSpec[]>(
    agent.middlewares || [],
  );
  const [middlewareConfigTexts, setMiddlewareConfigTexts] = useState<string[]>(
    () => (agent.middlewares || []).map(
      (middleware) => JSON.stringify(middleware.config || {}, null, 2),
    ),
  );
  const [enabled, setEnabled] = useState(agent.enabled);
  const [policy, setPolicy] = useState<AgentSpec["policy"]>(agent.policy);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const dialogRef = useDialogAccessibility(onClose);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const configuredTools = tools.map((tool, index) => ({
        ...tool,
        config: parseJsonObject(
          toolConfigTexts[index] || "{}",
          `${tool.plugin_id} 配置`,
        ),
      }));
      const configuredMiddlewares = middlewares.map((middleware, index) => ({
        ...middleware,
        config: parseJsonObject(
          middlewareConfigTexts[index] || "{}",
          `${middleware.plugin_id} 配置`,
        ),
      }));
      await onSave({
        name,
        description,
        systemPrompt,
        modelConfigId,
        tools: configuredTools,
        children,
        memory: {
          plugin_id: memoryPluginId,
          enabled: memoryEnabled,
          config: parseJsonObject(memoryConfigText, "记忆配置"),
        },
        middlewares: configuredMiddlewares,
        enabled,
        policy,
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "发布修订失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      ref={dialogRef}
      className="modal-layer"
      role="dialog"
      aria-modal="true"
      aria-labelledby="edit-agent-title"
    >
      <button className="modal-scrim" onClick={onClose} aria-label="关闭 Agent 编辑器" />
      <form className="modal-card new-agent-modal" onSubmit={submit}>
        <div className="modal-head">
          <div>
            <span className="section-kicker">PUBLISH REVISION · REV {agent.revision}</span>
            <h2 id="edit-agent-title">编辑 Agent 配置</h2>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="关闭">
            <X size={19} />
          </button>
        </div>
        <div className="modal-body">
          <div className="form-row">
            <label className="form-field">
              <span>名称</span>
              <input required minLength={2} value={name} onChange={(event) => setName(event.target.value)} />
            </label>
            <label className="form-field">
              <span>状态</span>
              <select value={enabled ? "enabled" : "disabled"} onChange={(event) => setEnabled(event.target.value === "enabled")}>
                <option value="enabled">启用</option>
                <option value="disabled">停用</option>
              </select>
            </label>
          </div>
          <label className="form-field">
            <span>描述</span>
            <input value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
          <div className="form-row">
            <label className="form-field"><span>模型配置</span><select required value={modelConfigId} onChange={(event) => setModelConfigId(event.target.value)}><option value="">请选择已验证并启用的模型配置</option>{modelConfigs.filter((item) => item.enabled && item.lifecycle === "enabled").map((item) => <option value={item.id} key={item.id}>{item.name} · {item.provider} / {item.model}</option>)}</select><small>Agent 只引用租户模型配置；协议、端点和凭证不复制到 Agent。</small></label>
          </div>
          <label className="form-field">
            <span>系统提示词</span>
            <textarea required rows={4} value={systemPrompt} onChange={(event) => setSystemPrompt(event.target.value)} />
          </label>
          <fieldset className="child-picker tool-picker">
            <legend>工具绑定</legend>
            <p>已有别名、权限和配置会保留；新绑定工具默认使用 auto 策略。</p>
            <div className="picker-grid">
              {toolPlugins.map((plugin) => {
                const selected = tools.some((tool) => tool.plugin_id === plugin.id);
                return (
                  <button
                    type="button"
                    key={plugin.id}
                    className={selected ? "selected" : ""}
                    onClick={() => {
                      if (selected) {
                        setToolConfigTexts((current) => current.filter(
                          (_, index) => tools[index]?.plugin_id !== plugin.id,
                        ));
                        setTools((current) => current.filter(
                          (tool) => tool.plugin_id !== plugin.id,
                        ));
                        return;
                      }
                      setTools((current) => [
                        ...current,
                        {
                          plugin_id: plugin.id,
                          alias:
                            plugin.id.split(".").pop()?.replace(/-/g, "_") ||
                            plugin.id,
                          enabled: true,
                          permission: "auto",
                          config: {},
                        },
                      ]);
                      setToolConfigTexts((current) => [...current, "{}"]);
                    }}
                  >
                    <span className="node-avatar amber"><TerminalSquare size={14} /></span>
                    <span><strong>{plugin.display_name}</strong><small>{plugin.id}</small></span>
                    <span className="checkbox-mark">{selected && <Check size={14} />}</span>
                  </button>
                );
              })}
            </div>
            {tools.length > 0 && (
              <div className="binding-editor-list">
                {tools.map((tool, toolIndex) => (
                  <div
                    className="binding-editor-row"
                    key={`${tool.plugin_id}:${toolIndex}`}
                  >
                    <label className="form-field">
                      <span>{tool.plugin_id} · 调用别名</span>
                      <input
                        required
                        minLength={2}
                        value={tool.alias || ""}
                        onChange={(event) => setTools((current) => current.map((item, index) => (
                          index === toolIndex
                            ? { ...item, alias: event.target.value }
                            : item
                        )))}
                      />
                    </label>
                    <label className="form-field">
                      <span>权限</span>
                      <select
                        value={tool.permission || "auto"}
                        onChange={(event) => setTools((current) => current.map((item, index) => (
                          index === toolIndex
                            ? {
                                ...item,
                                permission: event.target.value as ToolBindingSpec["permission"],
                              }
                            : item
                        )))}
                      >
                        <option value="auto">auto · 自动执行</option>
                        <option value="confirm">confirm · 等待批准</option>
                        <option value="deny">deny · 禁止执行</option>
                      </select>
                    </label>
                    <label className="form-field json-config-field">
                      <span>配置 JSON</span>
                      <textarea
                        rows={3}
                        value={toolConfigTexts[toolIndex] || "{}"}
                        onChange={(event) => setToolConfigTexts((current) => current.map(
                          (value, index) => (
                            index === toolIndex ? event.target.value : value
                          ),
                        ))}
                        spellCheck={false}
                      />
                    </label>
                  </div>
                ))}
              </div>
            )}
          </fieldset>
          <fieldset className="child-picker">
            <legend>记忆与中间件</legend>
            <p>插件配置随 Agent 修订保存；扩展字段由插件 Schema 与后端共同校验。</p>
            <div className="memory-editor-grid">
              <label className="form-field">
                <span>记忆适配器</span>
                <select value={memoryPluginId} onChange={(event) => setMemoryPluginId(event.target.value)}>
                  {memoryPlugins.map((plugin) => (
                    <option value={plugin.id} key={plugin.id}>{plugin.display_name}</option>
                  ))}
                </select>
              </label>
              <label className="form-field">
                <span>记忆状态</span>
                <select value={memoryEnabled ? "enabled" : "disabled"} onChange={(event) => setMemoryEnabled(event.target.value === "enabled")}>
                  <option value="enabled">启用</option>
                  <option value="disabled">停用</option>
                </select>
              </label>
              <label className="form-field json-config-field memory-config-field">
                <span>记忆配置 JSON</span>
                <textarea
                  rows={3}
                  value={memoryConfigText}
                  onChange={(event) => setMemoryConfigText(event.target.value)}
                  spellCheck={false}
                />
              </label>
            </div>
            {middlewarePlugins.length > 0 && (
              <div className="picker-grid middleware-picker-grid">
                {middlewarePlugins.map((plugin) => {
                  const selected = middlewares.some((item) => item.plugin_id === plugin.id);
                  return (
                    <button
                      type="button"
                      key={plugin.id}
                      className={selected ? "selected" : ""}
                      onClick={() => {
                        if (selected) {
                          setMiddlewareConfigTexts((current) => current.filter(
                            (_, index) => middlewares[index]?.plugin_id !== plugin.id,
                          ));
                          setMiddlewares((current) => current.filter(
                            (item) => item.plugin_id !== plugin.id,
                          ));
                          return;
                        }
                        setMiddlewares((current) => [
                          ...current,
                          { plugin_id: plugin.id, enabled: true, config: {} },
                        ]);
                        setMiddlewareConfigTexts((current) => [...current, "{}"]);
                      }}
                    >
                      <span className="node-avatar violet"><Workflow size={14} /></span>
                      <span><strong>{plugin.display_name}</strong><small>{plugin.id}</small></span>
                      <span className="checkbox-mark">{selected && <Check size={14} />}</span>
                    </button>
                  );
                })}
              </div>
            )}
            {middlewares.length > 0 && (
              <div className="binding-editor-list">
                {middlewares.map((middleware, middlewareIndex) => (
                  <div
                    className="binding-editor-row middleware-editor-row"
                    key={`${middleware.plugin_id}:${middlewareIndex}`}
                  >
                    <div className="binding-editor-title">
                      <strong>{middleware.plugin_id}</strong>
                      <small>middleware binding</small>
                    </div>
                    <label className="form-field">
                      <span>状态</span>
                      <select
                        value={middleware.enabled === false ? "disabled" : "enabled"}
                        onChange={(event) => setMiddlewares((current) => current.map((item, index) => (
                          index === middlewareIndex
                            ? { ...item, enabled: event.target.value === "enabled" }
                            : item
                        )))}
                      >
                        <option value="enabled">启用</option>
                        <option value="disabled">停用</option>
                      </select>
                    </label>
                    <label className="form-field json-config-field">
                      <span>配置 JSON</span>
                      <textarea
                        rows={3}
                        value={middlewareConfigTexts[middlewareIndex] || "{}"}
                        onChange={(event) => setMiddlewareConfigTexts((current) => current.map(
                          (value, index) => (
                            index === middlewareIndex ? event.target.value : value
                          ),
                        ))}
                        spellCheck={false}
                      />
                    </label>
                  </div>
                ))}
              </div>
            )}
          </fieldset>
          <fieldset className="child-picker">
            <legend>挂载子 Agent</legend>
            <p>修改挂载会随本次发布创建新修订；已固定旧修订的实例不受影响。</p>
            <div className="picker-grid">
              {agents.filter((item) => item.id !== agent.id).map((candidate) => {
                const selected = children.some((mount) => mount.agent_id === candidate.id);
                return (
                  <button
                    type="button"
                    key={candidate.id}
                    className={selected ? "selected" : ""}
                    onClick={() => setChildren((current) => (
                      selected
                        ? current.filter((mount) => mount.agent_id !== candidate.id)
                        : [
                            ...current,
                            {
                              alias:
                                candidate.id
                                  .replace(/^agt_/, "")
                                  .replace(/[^a-zA-Z0-9_-]/g, "_")
                                  .slice(0, 31) || `child_${current.length + 1}`,
                              agent_id: candidate.id,
                              description: candidate.description || "已挂载子 Agent",
                              revision: candidate.revision,
                              max_concurrency: 2,
                              input_template: "{input}",
                              allowed_tools: null,
                            },
                          ]
                    ))}
                  >
                    <span className="node-avatar blue">{agentInitials(candidate.name)}</span>
                    <span><strong>{candidate.name}</strong><small>rev {candidate.revision}</small></span>
                    <span className="checkbox-mark">{selected && <Check size={14} />}</span>
                  </button>
                );
              })}
            </div>
            {children.length > 0 && (
              <div className="mount-editor-list">
                {children.map((mount, mountIndex) => {
                  const target = agents.find((item) => item.id === mount.agent_id);
                  return (
                    <div
                      className="mount-editor-row"
                      key={`${mount.agent_id}:${mountIndex}`}
                    >
                      <div className="binding-editor-title">
                        <strong>{target?.name || mount.agent_id}</strong>
                        <small>{mount.agent_id}</small>
                      </div>
                      <label className="form-field">
                        <span>挂载别名</span>
                        <input
                          required
                          minLength={2}
                          value={mount.alias}
                          onChange={(event) => setChildren((current) => current.map((item, index) => (
                            index === mountIndex
                              ? { ...item, alias: event.target.value }
                              : item
                          )))}
                        />
                      </label>
                      <label className="form-field">
                        <span>固定修订</span>
                        <input
                          type="number"
                          min={1}
                          value={mount.revision ?? ""}
                          onChange={(event) => setChildren((current) => current.map((item, index) => (
                            index === mountIndex
                              ? {
                                  ...item,
                                  revision: event.target.value
                                    ? Math.max(1, Number(event.target.value))
                                    : undefined,
                                }
                              : item
                          )))}
                        />
                      </label>
                      <label className="form-field">
                        <span>最大并发</span>
                        <input
                          type="number"
                          min={1}
                          max={64}
                          value={mount.max_concurrency || 1}
                          onChange={(event) => setChildren((current) => current.map((item, index) => (
                            index === mountIndex
                              ? {
                                  ...item,
                                  max_concurrency: Math.max(1, Number(event.target.value) || 1),
                                }
                              : item
                          )))}
                        />
                      </label>
                      <MountToolScopeEditor
                        mount={mount}
                        rowId={`edit-${mount.agent_id}-${mountIndex}`}
                        toolPlugins={toolPlugins}
                        onChange={(allowedTools) => setChildren((current) => current.map((item, index) => (
                          index === mountIndex
                            ? { ...item, allowed_tools: allowedTools }
                            : item
                        )))}
                      />
                      <label className="form-field mount-template-field">
                        <span>输入模板</span>
                        <input
                          required
                          value={mount.input_template || "{input}"}
                          onChange={(event) => setChildren((current) => current.map((item, index) => (
                            index === mountIndex
                              ? { ...item, input_template: event.target.value }
                              : item
                          )))}
                        />
                      </label>
                    </div>
                  );
                })}
              </div>
            )}
          </fieldset>
          <fieldset className="child-picker policy-editor">
            <legend>运行策略</legend>
            <p>发布会创建不可变的新修订；运行中的旧修订不受影响。</p>
            <div className="policy-editor-grid">
              <label className="form-field"><span>最大步数</span><input type="number" min={1} max={128} value={policy.max_steps} onChange={(event) => setPolicy((current) => ({ ...current, max_steps: Math.max(1, Number(event.target.value) || 1) }))} /></label>
              <label className="form-field"><span>最大深度</span><input type="number" min={0} max={16} value={policy.max_depth} onChange={(event) => setPolicy((current) => ({ ...current, max_depth: Math.max(0, Number(event.target.value) || 0) }))} /></label>
              <label className="form-field"><span>工具调用</span><input type="number" min={0} max={1024} value={policy.max_tool_calls} onChange={(event) => setPolicy((current) => ({ ...current, max_tool_calls: Math.max(0, Number(event.target.value) || 0) }))} /></label>
              <label className="form-field"><span>子 Agent 并发</span><input type="number" min={1} max={128} value={policy.max_parallel_children} onChange={(event) => setPolicy((current) => ({ ...current, max_parallel_children: Math.max(1, Number(event.target.value) || 1) }))} /></label>
              <label className="form-field"><span>超时（秒）</span><input type="number" min={1} max={3600} value={policy.timeout_seconds} onChange={(event) => setPolicy((current) => ({ ...current, timeout_seconds: Math.max(1, Number(event.target.value) || 1) }))} /></label>
              <label className="form-field"><span>Token 预算</span><input type="number" min={1} value={policy.token_budget} onChange={(event) => setPolicy((current) => ({ ...current, token_budget: Math.max(1, Number(event.target.value) || 1) }))} /></label>
            </div>
          </fieldset>
          {error && <div className="form-error"><OctagonAlert size={16} /> {error}</div>}
        </div>
        <div className="modal-actions">
          <button type="button" className="button button-ghost" onClick={onClose}>取消</button>
          <button className="button button-primary" disabled={busy || !name.trim()}>
            {busy ? <LoaderCircle size={16} className="spinning" /> : <GitBranch size={16} />}
            发布 rev {agent.revision + 1}
          </button>
        </div>
      </form>
    </div>
  );
}

function NewInstanceModal({
  agents,
  onClose,
  onCreate,
}: {
  agents: AgentSpec[];
  onClose: () => void;
  onCreate: (form: {
    name: string;
    agentId: string;
    environment: string;
    maxConcurrency: number;
  }) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [agentId, setAgentId] = useState(agents[0]?.id || "");
  const [environment, setEnvironment] = useState("local");
  const [maxConcurrency, setMaxConcurrency] = useState(4);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const dialogRef = useDialogAccessibility(onClose);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await onCreate({ name, agentId, environment, maxConcurrency });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "实例创建失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      ref={dialogRef}
      className="modal-layer"
      role="dialog"
      aria-modal="true"
      aria-labelledby="new-instance-title"
    >
      <button className="modal-scrim" onClick={onClose} aria-label="关闭新建实例" />
      <form className="modal-card run-modal" onSubmit={submit}>
        <div className="modal-head">
          <div>
            <span className="section-kicker">NEW INSTANCE</span>
            <h2 id="new-instance-title">创建运行实例</h2>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="关闭">
            <X size={19} />
          </button>
        </div>
        <div className="modal-body">
          <label className="form-field">
            <span>实例名称</span>
            <input
              required
              minLength={2}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="例如：研究团队 · 本地"
            />
          </label>
          <label className="form-field">
            <span>Agent 与修订</span>
            <select value={agentId} onChange={(event) => setAgentId(event.target.value)}>
              {agents.map((agent) => (
                <option value={agent.id} key={agent.id}>
                  {agent.name} · rev {agent.revision}
                </option>
              ))}
            </select>
          </label>
          <div className="form-row">
            <label className="form-field">
              <span>环境标签（不负责部署）</span>
              <select
                value={environment}
                onChange={(event) => setEnvironment(event.target.value)}
              >
                <option value="local">local 标签</option>
                <option value="container">container 标签</option>
                <option value="cloud">cloud 标签</option>
              </select>
              <small>仅进入运行上下文；0.1.x 不会据此创建容器或云资源。</small>
            </label>
            <label className="form-field">
              <span>最大并发</span>
              <input
                type="number"
                min={1}
                max={256}
                value={maxConcurrency}
                onChange={(event) =>
                  setMaxConcurrency(
                    Math.max(1, Math.min(256, Number(event.target.value) || 1)),
                  )
                }
              />
            </label>
          </div>
          <div className="run-policy-preview">
            <div>
              <ShieldCheck size={16} />
              <span>
                <strong>修订在实例上固定</strong>
                <small>后续 Agent 发布新修订不会改变该实例的运行目标</small>
              </span>
            </div>
            <span>REV PINNED</span>
          </div>
          {error && <div className="form-error"><OctagonAlert size={16} /> {error}</div>}
        </div>
        <div className="modal-actions">
          <button type="button" className="button button-ghost" onClick={onClose}>取消</button>
          <button
            className="button button-primary"
            disabled={busy || !name.trim() || !agentId}
          >
            {busy ? <LoaderCircle size={16} className="spinning" /> : <Plus size={16} />}
            创建实例
          </button>
        </div>
      </form>
    </div>
  );
}

function RunModal({
  agents,
  instances,
  readinessIssues,
  busy,
  onClose,
  onRepair,
  onLaunch,
}: {
  agents: AgentSpec[];
  instances: AgentInstance[];
  readinessIssues: ReadinessIssue[];
  busy: boolean;
  onClose: () => void;
  onRepair: () => void;
  onLaunch: (id: string, kind: "agent" | "instance", input: string) => Promise<void>;
}) {
  const options = [
    ...instances.map((item) => ({ id: item.id, kind: "instance" as const, label: item.name, note: `${item.environment} · ×${item.max_concurrency}` })),
    ...agents.map((item) => ({ id: item.id, kind: "agent" as const, label: item.name, note: `definition · rev ${item.revision}` })),
  ];
  const [target, setTarget] = useState(options[0]?.id || "");
    const [input, setInput] = useState("请评估当前 Agent 框架的扩展边界与主要风险");
  const selected = options.find((item) => item.id === target);
  const dialogRef = useDialogAccessibility(onClose);
  return (
    <div ref={dialogRef} className="modal-layer" role="dialog" aria-modal="true" aria-labelledby="run-modal-title">
      <button className="modal-scrim" onClick={onClose} aria-label="关闭运行面板" />
      <form
        className="modal-card run-modal"
        onSubmit={(event) => {
          event.preventDefault();
          if (selected) void onLaunch(selected.id, selected.kind, input);
        }}
      >
        <div className="modal-head">
          <div><span className="section-kicker">NEW RUN</span><h2 id="run-modal-title">发起 Agent 运行</h2></div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="关闭"><X size={19} /></button>
        </div>
        <div className="modal-body">
          {options.length ? <>
            <label className="form-field">
              <span>运行目标</span>
              <select value={target} onChange={(event) => setTarget(event.target.value)}>
                {options.map((item) => <option value={item.id} key={`${item.kind}:${item.id}`}>{item.label} · {item.note}</option>)}
              </select>
            </label>
            <label className="form-field">
              <span>任务输入</span>
              <textarea value={input} onChange={(event) => setInput(event.target.value)} rows={6} required />
            </label>
            <div className="run-policy-preview">
              <div><ShieldCheck size={16} /><span><strong>保护策略生效</strong><small>深度、调用、并发、超时与 token 共享预算</small></span></div>
              <span>Fail closed</span>
            </div>
          </> : <PrerequisiteGate
            title="先修复 Readiness，再发起 Run"
            description="控制面没有返回可运行的 Agent 或 ready Instance；页面不会创建空目标或本地演示数据。"
            issues={readinessIssues}
            onRepair={onRepair}
          />}
        </div>
        <div className="modal-actions">
          <button type="button" className="button button-ghost" onClick={onClose}>取消</button>
          <button className="button button-primary" disabled={busy || !options.length || !target || !input.trim()}>
            {busy ? <LoaderCircle size={16} className="spinning" /> : <Play size={16} fill="currentColor" />}
            {busy ? "运行中" : "开始运行"}
          </button>
        </div>
      </form>
    </div>
  );
}

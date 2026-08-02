import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

const projectRoot = new URL("../", import.meta.url);

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the UAI Forge control center", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<html lang="zh-CN">/i);
  assert.match(html, /<title>UAI Forge · 多 Agent 控制中心<\/title>/i);
  assert.match(html, /从真实连接开始，完成第一个 Run/);
  assert.match(html, /当前控制台不创建示例 Agent/);
  assert.match(html, /aria-label="主导航"/);
  assert.match(html, /协作拓扑/);
  assert.match(html, /Agent 对话/);
  assert.match(html, /Run 事件可续播/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape|react-loading-skeleton/i);
});

test("removes starter-only infrastructure and wires the product client", async () => {
  const [page, layout, controlCenter, packageJson, globalsCss] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/control-center.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
  ]);

  assert.match(page, /<ControlCenter \/>/);
  assert.match(layout, /UAI Forge/);
  assert.match(layout, /lang="zh-CN"/);
  assert.match(controlCenter, /http:\/\/localhost:8000\/api\/v1/);
  assert.match(controlCenter, /mode === "live"/);
  assert.match(controlCenter, /mode === "disconnected"/);
  assert.match(controlCenter, /forge-shell \$\{view === "chat" \? "chat-page"/);
  assert.match(globalsCss, /grid-template-rows: auto minmax\(0, 1fr\)/);
  assert.match(globalsCss, /overscroll-behavior: contain/);
  assert.doesNotMatch(controlCenter, /mock|demoEvents|delegate:analyst/i);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);

  await assert.rejects(access(new URL("app/_sites-preview", projectRoot)));
});

test("keeps advanced Agent configuration and real event history wired", async () => {
  const [controlCenter, globalsCss] = await Promise.all([
    readFile(new URL("../app/control-center.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
  ]);

  assert.match(controlCenter, /模型配置 JSON/);
  assert.match(controlCenter, /常用模型已列出/);
  assert.match(controlCenter, /自定义模型 ID/);
  assert.match(controlCenter, /DeepSeek 兼容接口/);
  assert.match(controlCenter, /Qwen3-Coder/);
  assert.match(controlCenter, /Kimi K2 Thinking/);
  assert.match(controlCenter, /豆包 Seed 1.6/);
  assert.match(controlCenter, /豆包 Seed 2.1 Pro/);
  assert.match(controlCenter, /腾讯混元 T1/);
  assert.match(controlCenter, /MiniMax M2/);
  assert.match(controlCenter, /MiniMax M3/);
  assert.match(controlCenter, /Qwen3.8 Max Preview/);
  assert.match(controlCenter, /Kimi K2.7 Code/);
  assert.match(controlCenter, /GLM-5 Turbo/);
  assert.match(controlCenter, /凭证&模型配置/);
  assert.match(controlCenter, /工具凭证/);
  assert.match(controlCenter, /ToolCredentialsView/);
  assert.match(controlCenter, /credential_ref/);
  assert.match(controlCenter, /DEPLOYMENT TOOL CREDENTIALS/);
  assert.match(controlCenter, /secret_action/);
  assert.doesNotMatch(controlCenter, /tool-credentials\/\$\{[^}]+\}\/secret/);
  assert.match(controlCenter, /anthropic_messages/);
  assert.match(controlCenter, /MODEL_TIMEOUT_OPTIONS/);
  assert.match(controlCenter, /Provider 扩展参数 JSON/);
  assert.match(controlCenter, /记忆与中间件/);
  assert.match(controlCenter, /function MountRevisionField/);
  assert.match(controlCenter, /子 Agent 版本/);
  assert.match(controlCenter, /输入模板/);
  assert.match(controlCenter, /allowed_tools/);
  assert.match(controlCenter, /下游工具范围/);
  assert.match(controlCenter, /空 = 全部拒绝/);
  assert.match(controlCenter, /permission: event\.target\.value/);
  assert.match(controlCenter, /index === toolIndex/);
  assert.match(controlCenter, /index === middlewareIndex/);
  assert.match(controlCenter, /index === mountIndex/);
  assert.doesNotMatch(controlCenter, /toolConfigTexts\[tool\.plugin_id\]/);
  assert.doesNotMatch(controlCenter, /middlewareConfigTexts\[middleware\.plugin_id\]/);
  assert.doesNotMatch(controlCenter, /item\.agent_id === mount\.agent_id/);
  assert.match(controlCenter, /children: form\.children/);
  assert.match(controlCenter, /events\/history/);
  assert.match(controlCenter, /consumeEventStream/);
  assert.match(controlCenter, /function ChatWorkspace/);
  assert.match(controlCenter, /model\.delta/);
  assert.match(controlCenter, /正在分析任务/);
  assert.match(controlCenter, /正在做输入预检/);
  assert.match(controlCenter, /model\.failed/);
  assert.match(controlCenter, /duration_ms/);
  assert.match(controlCenter, /function traceEventDuration/);
  assert.match(controlCenter, /function traceStageSummaries/);
  assert.match(controlCenter, /阶段耗时/);
  assert.match(controlCenter, /不暴露隐藏链式思维|隐藏链式思维/);
  assert.match(controlCenter, /思考模式/);
  assert.match(controlCenter, /THINKING_MODE_OPTIONS/);
  assert.match(controlCenter, /thinking_mode/);
  assert.match(controlCenter, /不展示原始思考内容/);
  assert.match(controlCenter, /function PublicReasoningPanel/);
  assert.match(controlCenter, /publicReasoningSteps/);
  assert.match(controlCenter, /function tokenUsageDetail/);
  assert.match(controlCenter, /cached_input_tokens/);
  assert.match(controlCenter, /缓存命中/);
  assert.match(controlCenter, /function ChatOutput/);
  assert.match(controlCenter, /chat-output-list/);
  assert.match(controlCenter, /public-reasoning-chevron/);
  assert.match(controlCenter, /chat-message-status/);
  assert.match(controlCenter, /思考过程/);
  assert.match(controlCenter, /公开摘要/);
  assert.match(controlCenter, /不显示隐藏思维原文/);
  assert.doesNotMatch(controlCenter, /reasoning_tokens|chain_of_thought_payload/i);
  assert.doesNotMatch(controlCenter, /dangerouslySetInnerHTML/);
  assert.match(controlCenter, /type ExecutionMode = "execute" \| "plan"/);
  assert.match(controlCenter, /EXECUTION_MODE_OPTIONS/);
  assert.match(controlCenter, /计划模式/);
  assert.match(controlCenter, /运行方式（不是模型）/);
  assert.match(controlCenter, /控制面未确认所选/);
  assert.match(controlCenter, /chat-mode-indicator/);
  assert.match(controlCenter, /choice-card-recommendation/);
  assert.match(controlCenter, /choice-option-control/);
  assert.match(controlCenter, /继续规划/);
  assert.match(globalsCss, /CHG-0027: reference-aligned conversation surface/);
  assert.match(globalsCss, /The task rail is an activity tray/);
  assert.match(controlCenter, /type ExecutionPlan/);
  assert.match(controlCenter, /function PlanCard/);
  assert.match(controlCenter, /批准并执行/);
  assert.match(controlCenter, /修改计划/);
  assert.match(controlCenter, /暂不执行/);
  assert.match(controlCenter, /\/plan\/approve/);
  assert.match(controlCenter, /plan_status/);
  assert.match(controlCenter, /execution_mode/);
  assert.match(controlCenter, /不调用工具或子 Agent/);
  assert.match(controlCenter, /发起运行方式/);
  assert.match(controlCenter, /ReactFlow/);
  assert.match(controlCenter, /MiniMap/);
  assert.match(controlCenter, /function TracePanel/);
  assert.match(controlCenter, /trace_id/);
  assert.match(controlCenter, /parent_span_id/);
  assert.match(controlCenter, /全链路 Trace/);
  assert.match(controlCenter, /搜索运行记录/);
  assert.match(controlCenter, /session_id/);
  assert.match(controlCenter, /会话侧栏/);
  assert.match(controlCenter, /运行详情/);
  assert.match(controlCenter, /event\.nativeEvent\.isComposing/);
  assert.match(controlCenter, /event\.nativeEvent\.keyCode === 229/);
  assert.match(controlCenter, /compositionEndedRef/);
  assert.match(controlCenter, /setDraft\(`\$\{target\.value\.slice\(0, start\)\}\\n/);
  assert.match(controlCenter, /event\.metaKey.*event\.ctrlKey/);
  assert.match(controlCenter, /Enter 换行.*Enter 发送/);
  assert.match(controlCenter, /chat-scroll-bottom/);
  assert.match(controlCenter, /stickToChatBottomRef/);
  assert.match(controlCenter, /安全计算器/);
  assert.match(controlCenter, /回声工具/);
  assert.match(controlCenter, /进程内记忆/);
  assert.match(controlCenter, /审计标签/);
  assert.match(controlCenter, /PLUGIN_LOCALIZED_COPY/);
  assert.match(controlCenter, /tool\.plugin_id\.replace/);
  assert.match(controlCenter, /localizedPluginName\(pluginId, plugins\)/);
  assert.match(controlCenter, /lastSequence/);
  assert.match(controlCenter, /reconnecting/);
  assert.match(controlCenter, /degraded/);
  assert.match(controlCenter, /draft/);
  assert.match(controlCenter, /secretAction/);
  assert.match(controlCenter, /aria-modal="true"/);
  assert.match(controlCenter, /function CapabilityStatus/);
  assert.match(controlCenter, /capabilities\.map\(\(capability\)/);
  assert.doesNotMatch(controlCenter, /CapabilityStatus title=/);
  assert.doesNotMatch(controlCenter, /state="enforced"/);
  assert.match(controlCenter, /capability\.limits\.join/);
  assert.match(controlCenter, /单节点容器/);
  assert.match(controlCenter, /events\/history/);
  assert.match(controlCenter, /deploymentVisualState\(containerDeployment\?\.state\)/);
  assert.match(controlCenter, /可恢复云集群/);
  assert.match(controlCenter, /deploymentVisualState\(cloudDeployment\?\.state\)/);
  assert.doesNotMatch(controlCenter, /尚未真实启动验收/);
  assert.doesNotMatch(controlCenter, /function SettingToggle/);
  assert.doesNotMatch(controlCenter, /mock|demoEvents|delegate:analyst/i);
});

test("projects active Run status from the live event reducer", async () => {
  const controlCenter = await readFile(
    new URL("../app/control-center.tsx", import.meta.url),
    "utf8",
  );

  assert.match(controlCenter, /const applyEvents = \(incoming: RunEvent\[\]\) => \{/);
  assert.match(controlCenter, /for \(const event of incoming\) \{\s*const projection = runProjectionFromEvent\(event\);\s*if \(projection\) onRunProjection\(selectedRunId, projection\);\s*\}/);
  assert.match(controlCenter, /if \(event\.type === "run\.started"\) \{\s*patch\.status = "running";/);
  assert.match(controlCenter, /const terminalEvent = incoming\.find\(\(event\) => Boolean\(terminalStatusForEvent\(event\)\) && event\.type !== "run\.started"\)/);
});

test("shows cache-hit status in run inspector metrics", async () => {
  const controlCenter = await readFile(
    new URL("../app/control-center.tsx", import.meta.url),
    "utf8",
  );

  assert.match(controlCenter, /const streamCacheHitValue = totalReportedCacheHits\(streamEvents\)/);
  assert.match(controlCenter, /const cacheHitValue = totalReportedCacheHits\(timelineEvents\)/);
  assert.match(controlCenter, /<span>缓存命中<\/span><code>\{formatTokenCount\(streamCacheHitValue\)\}<\/code>/);
  assert.match(controlCenter, /<small>缓存命中<\/small><strong>\{formatTokenCount\(cacheHitValue\)\}<\/strong>/);
});

test("removes instance navigation and keeps revision run selectors", async () => {
  const controlCenter = await readFile(
    new URL("../app/control-center.tsx", import.meta.url),
    "utf8",
  );

  assert.doesNotMatch(controlCenter, /InstancesView|NewInstanceModal|创建运行实例|ready Instance|\/instances/);
  assert.match(controlCenter, /function RunModal/);
  assert.match(controlCenter, /最新版本（默认）/);
  assert.match(controlCenter, /agents\/\$\{selectedAgent\.id\}\/revisions/);
  assert.match(controlCenter, /selectedRevision === "latest" \? undefined/);
  assert.match(controlCenter, /子 Agent 版本/);
  assert.match(controlCenter, /保存草稿/);
  assert.match(controlCenter, /发布草稿/);
  assert.match(controlCenter, /版本历史/);
  assert.match(controlCenter, /回滚到此版本/);
  assert.match(controlCenter, /agents\/\$\{agent\.id\}\/publish/);
  assert.match(controlCenter, /agents\/\$\{agent\.id\}\/draft/);
  assert.match(controlCenter, /setRevisionLoading\(true\)/);
  assert.match(controlCenter, /problemMessage\(caught, fallback\)/);
  assert.doesNotMatch(controlCenter, /revision: candidate\.revision/);
  assert.doesNotMatch(controlCenter, /\brevision: agent\.revision/);
});

test("model configuration selection auto-fills model from provider or known endpoint", async () => {
  const controlCenter = await readFile(
    new URL("../app/control-center.tsx", import.meta.url),
    "utf8",
  );

  assert.match(controlCenter, /type EndpointPreset/);
  assert.match(controlCenter, /defaultModel: "deepseek-chat"/);
  assert.match(controlCenter, /function selectProvider\(provider: string\)/);
  assert.match(controlCenter, /function selectEndpoint\(baseUrl: string, preset\?: EndpointPreset\)/);
  assert.match(controlCenter, /选择厂商地址会自动带出推荐模型/);
  assert.match(controlCenter, /providerChanged/);
  assert.match(controlCenter, /onChange=\{selectEndpoint\}/);
});

test("new Agent defaults mount remote read-only tools", async () => {
  const controlCenter = await readFile(
    new URL("../app/control-center.tsx", import.meta.url),
    "utf8",
  );

  assert.match(controlCenter, /DEFAULT_AGENT_TOOL_PLUGIN_IDS/);
  assert.match(controlCenter, /tool\.web_search/);
  assert.match(controlCenter, /tool\.web_fetch/);
  assert.match(controlCenter, /tool\.web_json/);
  assert.match(controlCenter, /tool\.web_rss/);
  assert.match(controlCenter, /tool\.sandbox_exec/);
  assert.match(controlCenter, /tool\.workspace/);
  assert.match(controlCenter, /沙箱执行、本地工作区和 Git 都需要显式添加/);
  assert.match(controlCenter, /默认已选只读基础工具/);
  assert.match(controlCenter, /defaultAgentToolBindings\(plugins\)/);
});

test("sandbox tool pre-fills a runnable binding configuration", async () => {
  const controlCenter = await readFile(
    new URL("../app/control-center.tsx", import.meta.url),
    "utf8",
  );

  assert.match(controlCenter, /const SANDBOX_EXEC_TOOL_PLUGIN_ID = "tool\.sandbox_exec"/);
  assert.match(controlCenter, /const DEFAULT_SANDBOX_PLUGIN_ID = "sandbox\.docker"/);
  assert.match(controlCenter, /const DEFAULT_SANDBOX_IMAGE = "alpine:3\.20"/);
  assert.match(controlCenter, /sandbox_plugin_id: DEFAULT_SANDBOX_PLUGIN_ID/);
  assert.match(controlCenter, /sandbox_config: \{ image: DEFAULT_SANDBOX_IMAGE \}/);
  assert.match(controlCenter, /defaultToolConfigText\(plugin\.id\)/);
  assert.match(controlCenter, /沙箱执行、本地工作区和 Git 都需要显式添加/);
});

test("new Agent defaults use usable execution budgets", async () => {
  const controlCenter = await readFile(
    new URL("../app/control-center.tsx", import.meta.url),
    "utf8",
  );

  assert.match(controlCenter, /max_steps: 20/);
  assert.match(controlCenter, /max_depth: 6/);
  assert.match(controlCenter, /max_tool_calls: 64/);
  assert.match(controlCenter, /max_parallel_children: 6/);
  assert.match(controlCenter, /timeout_seconds: 300/);
  assert.match(controlCenter, /token_budget: 64000/);
  assert.match(controlCenter, /max_concurrency: 4/);
});

test("keeps account-specific hosting metadata out of portable source", async () => {
  const [gitIgnore, dockerIgnore, hostingExample, viteConfig] = await Promise.all([
    readFile(new URL("../.gitignore", import.meta.url), "utf8"),
    readFile(new URL("../.dockerignore", import.meta.url), "utf8"),
    readFile(
      new URL("../.openai/hosting.example.json", import.meta.url),
      "utf8",
    ),
    readFile(new URL("../vite.config.ts", import.meta.url), "utf8"),
  ]);

  assert.match(gitIgnore, /^\/\.openai\/hosting\.json$/m);
  assert.match(dockerIgnore, /^\.openai\/\*$/m);
  assert.doesNotMatch(dockerIgnore, /!\.openai\/hosting\.json/);
  assert.deepEqual(JSON.parse(hostingExample), { d1: null, r2: null });
  assert.doesNotMatch(hostingExample, /project_id/);
  assert.match(viteConfig, /readFileSync\(configPath, "utf8"\)/);
  assert.match(viteConfig, /code === "ENOENT"/);
});

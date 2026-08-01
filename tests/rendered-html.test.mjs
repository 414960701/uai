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
  assert.match(html, /Run 事件可续播/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape|react-loading-skeleton/i);
});

test("removes starter-only infrastructure and wires the product client", async () => {
  const [page, layout, controlCenter, packageJson] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/control-center.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);

  assert.match(page, /<ControlCenter \/>/);
  assert.match(layout, /UAI Forge/);
  assert.match(layout, /lang="zh-CN"/);
  assert.match(controlCenter, /http:\/\/localhost:8000\/api\/v1/);
  assert.match(controlCenter, /mode === "live"/);
  assert.match(controlCenter, /mode === "disconnected"/);
  assert.doesNotMatch(controlCenter, /mock|demoEvents|delegate:analyst/i);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);

  await assert.rejects(access(new URL("app/_sites-preview", projectRoot)));
});

test("keeps advanced Agent configuration and real event history wired", async () => {
  const controlCenter = await readFile(
    new URL("../app/control-center.tsx", import.meta.url),
    "utf8",
  );

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
  assert.match(controlCenter, /anthropic_messages/);
  assert.match(controlCenter, /MODEL_TIMEOUT_OPTIONS/);
  assert.match(controlCenter, /Provider 扩展参数 JSON/);
  assert.match(controlCenter, /记忆与中间件/);
  assert.match(controlCenter, /固定修订/);
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
  assert.match(controlCenter, /环境标签（不负责部署）/);
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

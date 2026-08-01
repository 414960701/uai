---
kind: manual-test-evidence
id: MANUAL-BROWSER-2026-08-02
status: passed
date: 2026-08-02
timezone: Asia/Shanghai
---

# Browser smoke and real-provider evidence

This record covers the latest available UAI Forge page build used during the
2026-08-02 browser smoke. The test used the same Chrome page and operated the
product through visible controls; no provider credential was copied into this
file, the browser local storage, a prompt, or a test fixture.

## Control-plane connection

- Page: `http://127.0.0.1:3000/?view=settings` (the local page served through
  the configured SSH tunnel).
- Control API: `http://127.0.0.1:8000/api/v1`, connected from the page.
- Saved model connection visible in the page: `ds`.
- Provider/model shown by the page: `openai_compatible` / `deepseek-v4-flash`.
- Credential state: present, enabled, connection check passed, and rendered
  only as a masked value. No plaintext credential was visible in the page,
  conversation, trace, or output.

## Agent lifecycle smoke

From the page, the four-step Agent wizard was completed for `真实 AK 最新版本验证
Agent`:

1. Selected the saved, verified `ds` model connection.
2. Confirmed the six default read-only tools were selected:
   `tool.web_search`, `tool.web_fetch`, `tool.web_json`, `tool.web_rss`,
   `tool.calculator`, and `tool.utc_now`.
3. Confirmed sandbox execution was not selected by default.
4. Confirmed the usable defaults displayed by the page: 20 steps, depth 6,
   64 tool calls, 6 child-agent concurrency, 300 seconds, and 64,000 tokens.
5. Created the Agent as a draft and published revision 1; the page showed
   `latest` pointing to the published revision.

## Real-provider page runs

All four messages were sent from the Agent conversation composer and finished
with `成功`:

| Check | Expected page result | Observed result |
|---|---|---|
| Provider smoke | `REAL_PROVIDER_OK` | `REAL_PROVIDER_OK`; the model event reported `deepseek-v4-flash` and the upstream response reported `claude-opus-4-1` |
| Calculator tool | `CALC_RESULT=12345*678` | `CALC_RESULT=8369910` |
| Web page access | Fetch `https://example.com` title | `FETCH_TITLE=Example Domain` |
| Web search | Search OpenAI Responses API official docs | `SEARCH_TITLE=OpenAI \| Research & Deployment` |

The run history showed four successful runs/messages, model events, tool
events for calculator, web fetch, and web search, and no error or plaintext
credential output.

## Scope and limits

This is a repeatable manual/browser evidence record for the page and the saved
provider connection. It does not upgrade the 0.1 single-process baseline to
distributed recovery, RBAC, or production-grade sandbox isolation. Docker
daemon smoke and the sandbox limitations remain tracked by
`CHG-0031-extensible-sandbox-runtimes`.

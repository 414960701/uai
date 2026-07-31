---
kind: test-plan
id: CHG-0008-TEST-PLAN
status: passed
superseded_by: CHG-0009
---

# Test plan

> 本测试计划保留 CHG-0008 时点的 provider 断言；当前 provider 注册表由 CHG-0009 的
> `openai_compatible` 与 `anthropic_messages` 共同构成。

- `backend/tests/test_registry.py::test_builtin_provider_catalog_excludes_test_adapters`。
- `.venv/bin/python -m pytest backend/tests -q`。
- `npm run lint`、`npm run typecheck`、`npm test`。
- `bash -n scripts/container-smoke.sh` 与 `docker compose config --quiet`。
- `scripts/container-smoke.sh` 验证 fresh database、provider registry 和资源清理。
- `test ! -e .github/workflows`，生产源码不包含测试 provider。

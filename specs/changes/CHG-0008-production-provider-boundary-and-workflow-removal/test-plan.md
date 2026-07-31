---
kind: test-plan
id: CHG-0008-TEST-PLAN
status: passed
---

# Test plan

- `backend/tests/test_registry.py::test_builtin_provider_catalog_excludes_test_adapters`。
- `.venv/bin/python -m pytest backend/tests -q`。
- `npm run lint`、`npm run typecheck`、`npm test`。
- `bash -n scripts/container-smoke.sh` 与 `docker compose config --quiet`。
- `scripts/container-smoke.sh` 验证 fresh database、provider registry 和资源清理。
- `test ! -e .github/workflows`，生产源码不包含测试 provider。

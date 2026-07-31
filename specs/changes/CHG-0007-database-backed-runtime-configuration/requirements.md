---
kind: requirements-delta
id: CHG-0007-REQUIREMENTS
status: accepted
target: 0.1.x
---

# Requirements delta

### CFG-001 — 数据库配置事实源

WHEN a control-plane request reads or changes Agent, Instance, provider, model, tool, memory,
middleware, runtime or run configuration
THE SYSTEM SHALL read/write the tenant-scoped database repository and SHALL NOT use a local
frontend/demo file as a business-data source.

### CFG-002 — 多 profile 与版本控制

WHEN a tenant creates multiple credentials, model profiles, Agents or Instances
THE SYSTEM SHALL preserve independent IDs, tenant scope, enabled state and references; runtime
configuration updates SHALL use a monotonically increasing version and reject stale CAS writes.

### SEC-008 — 凭据最小暴露

WHEN a credential is created, queried, logged, emitted in an event or used by a provider
THE SYSTEM SHALL encrypt it at rest, return only a mask, keep plaintext out of persistent domain
objects and fail closed when the credential/profile is missing or disabled.

### CFG-003 — 可替换 profile 适配器

WHEN a runtime resolves a ModelBinding profile
THE SYSTEM SHALL use UAI Forge ModelProfile/CredentialProfile contracts and a repository boundary,
so storage and provider adapters remain replaceable without exposing vendor objects in the core.

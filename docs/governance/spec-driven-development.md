---
kind: normative
id: GOV-SDD
status: approved
version: 1.0.0
last_reviewed: 2026-07-30
---

# 治理式增量 Spec 驱动开发

本方法吸收 GitHub Spec Kit、Kiro、OpenSpec、BMAD、ADR、TDD、契约测试和 OWASP
威胁建模，但只保留一套项目内事实源。

## 为什么这样组合

- Spec Kit 提供 constitution → specify → clarify → plan → tasks → analyze →
  implement → converge 的质量主干。
- Kiro 提供 EARS 需求句式、requirements/design/tasks 三件套和依赖 wave。
- OpenSpec 提供 current spec + change delta + verify + archive，适合后续棕地演进。
- BMAD 的 PRD → architecture → readiness 对高风险跨系统变更有用，但不引入全套角色。
- ADR 固化“为什么”，TDD/contract test 固化可执行证据。

## 事实源优先级

1. `constitution.md`、批准的 PRD、`specs/current`、Accepted ADR、公共合同。
2. 活跃 `specs/changes` 中已批准的 delta。
3. 代码与测试。
4. 任务、生成报告和解释性文档。

代码与规范冲突时不得让代码静默成为真相；先批准 spec delta。

## 变更包

```text
specs/changes/CHG-xxxx-name/
  proposal.md
  requirements.md
  design.md
  tasks.md
  test-plan.md
  threat-delta.md
  compatibility-impact.yaml
  traceability.yaml
  acceptance.md
```

需求使用：

```text
WHEN <触发或状态>
THE SYSTEM SHALL <可测行为>
```

每条需求至少有一个正向场景；安全、并发、预算、恢复类需求还必须有负向/边界场景。

## 阶段门

| Gate | 必需证据 | 阻断条件 |
|---|---|---|
| G0 治理 | 宪章、事实源优先级、AI 权限 | 原则冲突或事实源不清 |
| G1 准入 | proposal、目标、非目标、风险 | 问题/范围不明确 |
| G2 需求 | 带 ID 的 FR/NFR/SEC/EXT、场景 | SHALL 不可测或 blocking question 未清 |
| G3 设计 | design、合同、ADR、威胁模型 | 重大决定无 ADR；高威胁无处置 |
| G4 Readiness | DAG tasks、test plan、追踪、回滚 | SHALL 覆盖不足 100% |
| G5 Red | 先失败的验收/契约测试 | 测试因环境错误而失败 |
| G6 实现 | 代码、单测、独立审查 | 擅改冻结需求或越界 |
| G7 发布 | 全测、兼容、安全、部署证据 | 无证据、破坏变更未声明 |
| G8 归档 | delta 合入 current、证据归档 | 当前规范与实现不一致 |

## 防止 AI 漂移

- 子任务只得到相关 requirement/ADR、allowed paths、禁止事项和停止条件。
- 冻结需求、ADR、验收测试不由实现 Agent 改写。
- 结构化输出经 Schema/Pydantic 校验。
- 高影响动作“提议”和“执行”分离。
- 测试套件在测试边界注册隔离 provider；真实模型 eval 放 nightly/release，产品运行时不内置测试 provider。
- 记录 provider/model、spec revision、插件版本、策略和调用树；不记录原始 CoT。
- 独立 fresh-context reviewer 检查规范、实现与测试共谋错误。

## 官方来源

访问日期 2026-07-30：

- Spec Kit Agentic SDD: https://github.github.io/spec-kit/reference/agentic-sdd.html
- Spec Kit complex features: https://github.github.io/spec-kit/concepts/complex-features.html
- Kiro Specs: https://kiro.dev/docs/specs/
- Kiro Feature Specs / EARS: https://kiro.dev/docs/specs/feature-specs/
- OpenSpec: https://github.com/Fission-AI/OpenSpec
- BMAD workflow map: https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/reference/workflow-map.md
- AWS ADR process: https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html
- Pact contract testing: https://docs.pact.io/
- OWASP Threat Modeling: https://cheatsheetseries.owasp.org/cheatsheets/Threat_Modeling_Cheat_Sheet.html
- OWASP AI Agent Security: https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html
- PyPA entry points: https://packaging.python.org/en/latest/specifications/entry-points/
- Semantic Versioning: https://semver.org/
- PEP 387: https://peps.python.org/pep-0387/

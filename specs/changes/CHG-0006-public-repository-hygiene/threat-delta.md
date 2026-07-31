---
kind: threat-delta
id: CHG-0006-THREAT
status: accepted
---

# Threat delta

| 威胁 | 处置 |
|---|---|
| 公开仓库泄露维护者部署项目标识 | 真实 hosting 文件仅本地保存并由 Git/Docker 忽略 |
| Fork 误用维护者 `project_id` | 只提交无 `project_id` 的中性示例 |
| 删除 hosting 文件导致干净 checkout 不能构建 | Vite 对缺失文件使用无 binding 默认值并加入回归测试 |
| malformed 本地配置被静默吞掉 | 只对 `ENOENT` 降级；JSON 或读取错误继续失败 |
| 为隐藏非 Secret ID 破坏性重写公开历史 | 记录历史存在，当前树清理；发现真实 Secret 时才要求轮换和历史清除 |

仍接受的风险：Git 历史保留曾公开的非 Secret Sites 项目 ID；GitHub Actions 上游 action
可能产生与本项目源码无关的弃用提示。

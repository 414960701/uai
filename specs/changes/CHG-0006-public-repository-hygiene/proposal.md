---
kind: change-proposal
id: CHG-0006
status: implemented
target: 0.1.x
requirements:
  - SEC-007
---

# 公开仓库环境元数据隔离

## 问题

公开源码包含 `.openai/hosting.json` 中的个人 Sites `project_id`。该标识不是凭据，不能
单独授权访问，但它把可复用框架绑定到维护者的部署项目，Fork 后也容易让使用者误以为
应复用同一个项目。当前 Vite 配置还静态导入该文件，使直接删除会破坏干净 checkout 构建。

## 范围

- 将真实 `.openai/hosting.json` 改为本地忽略的部署元数据。
- 提交不含账号或项目标识的中性示例文件。
- 让前端在真实 hosting 文件不存在时以无 D1/R2 binding 的默认值构建。
- 从 CI、Docker build context 和 Dockerfile 中移除对个人 hosting 文件的依赖。
- 扫描当前树和 Git 历史中的账号标识、本机路径及常见凭据签名。

## 非目标

- 不删除 `.github/workflows`；它是公开 CI 的版本化定义。
- 不重写 Git 历史；已公开的 Sites `project_id` 不是 Secret，当前树移除即可。
- 不改变 Agent Runtime、API、插件协议、数据模型或部署成熟度声明。

## 实现证据

2026-07-31 的干净 checkout 形态前端门禁、65 项后端测试、production audit、配置检查和
单节点容器 smoke 全部通过。当前 Git 索引只提交中性 hosting 示例；维护者真实文件保留
在本机并由 Git/Docker 忽略。完整证据记录在 [acceptance.md](acceptance.md)。

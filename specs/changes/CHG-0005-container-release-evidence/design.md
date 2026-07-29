---
kind: design-delta
id: CHG-0005-DESIGN
status: accepted
target: 0.1.x
---

# Design delta

`scripts/container-smoke.sh` 复用生产 Dockerfile 与 `docker-compose.yml`，不建立第二套
部署定义。脚本为每次执行生成唯一 Compose project 与 SQLite volume，并动态选择可由
环境覆盖的 loopback 测试端口。脚本强制将端口绑定到 `127.0.0.1`，并在注册 cleanup
trap 前拒绝任何已存在的同名 project、network、volume 或临时 image tag；`trap`
无论成功或失败都只对本次新建 project 执行 `down --volumes` 并删除本次唯一 image tag。

门禁分四段：

1. `docker compose config` 和 `up --build -d`。
2. Web 镜像构建阶段裁剪依赖并执行 production audit；启动后轮询两个容器的 Docker
   `healthy` 状态与后端 `/health`、前端 `/`，验证运行镜像不含 ESLint/Drizzle
   开发工具，再运行后端 doctor。
3. POST seeded Instance 的确定性 `delegate:analyst` Run，轮询终态。
4. 读取 history，验证连续 sequence 和四个关键事件，清理并断言容器、network、volume
   均不存在，再输出不含 Secret 的摘要。

CI 的 containers job 直接调用该脚本。Control Center 只把“单节点容器”标为已验证，
“可恢复云集群”继续显示规划；环境字段仍只是 Runtime 上下文标签。

公开发布依赖以兼容 patch/minor 为主：Next/React/RSC 保持 16.2/19.2 兼容线，
Vite/Cloudflare 工具保持各自公开 peer range，vinext 保持已验收的 `0.0.50`。
只有在 package 自身尚未更新嵌套依赖、且完整构建证明兼容时，才用 npm `overrides`
钉住已修复的传递依赖。`package-lock.json` 是 CI 与容器 `npm ci` 的唯一解析结果。
vinext 作为 production server 保留在生产依赖；运行镜像通过 `npm prune --omit=dev`
裁剪 ESLint、Drizzle Kit 和其他仅构建依赖，并由小型启动入口直接调用公开
`vinext/server/prod-server` 导出。

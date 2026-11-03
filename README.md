# auto-todo

待办，使用 AutoLang / AutoUI 开发的独立应用。

更新：2026-11-03。001已交付归档/r2、7/7（真实CRUD、稳定ID、SQLite恢复）。
002（独立启动、进程隔离与双端回归）已实施交付：验证入口只按 spawn 树清理本次进程
（不再按端口/命令行/进程名杀任何进程），补独立冷准备与真实双端重开后再编辑回归。
本轮交付基线：`--api-only` 47/47、`--profile vue` 74/74、`--profile vm` 69/69（退出码 0）。

## 运行

安装对应版本的 `auto` CLI 后，从本仓根执行：

```sh
auto run
auto run -r vm
```

前端端口：`17814`。后端端口：`17815`。

存储（TODO-001 起）：SQLite 单文件库，默认 `%APPDATA%/auto-todo/data/todos.db`；
`AUTO_TODO_DATA` 可整体覆盖数据目录（测试隔离用）。新库为空、无演示种子；
每次成功变更后写 `todos.db.bak` 快照，主库损坏时自动从备份恢复，双损坏时明确
报错且原件不动。测试故障注入：`AUTO_TODO_FAULT=write_fail|commit_fail|after_commit_fail`。

## 基本能力验证（TODO-001/002）

```sh
python tests/basic/verify_basic.py --profile vue   # API 全量 + 隔离电池 + Vue 真实 UI（Playwright）
python tests/basic/verify_basic.py --profile vm    # API 全量 + 隔离电池 + VM 真实 UI（AutoUI MCP）
python tests/basic/verify_basic.py --api-only      # 仅 API/存储/恢复/故障/schema/隔离/负控电池
python tests/basic/verify_basic.py --profile vue --cold-prep   # TD-01：清本仓自有生成物后冷首启
```

前置：`auto` CLI（默认 `D:/autostack/auto-man/target/debug/auto.exe`，可用
`AUTO_CLI` 覆盖）、node + npx playwright 缓存（`PLAYWRIGHT_MODULE` 可显式指定
playwright 入口）。入口实起后端与两端真实界面，逐项输出 PASS/FAIL，退出码 0/1。

进程与端口边界（TODO-002 起）：验证入口对进程的终止只按本次 spawn 树授权
（`taskkill /T` 于自有属根＋被观测的后端叶），端口只作观测——不杀端口属主、
不按进程名/命令行杀进程；端口被占/坏工具/启动停滞均受控失败（非零退出＋诊断），
重试只收割自有树。`--cold-prep` 只清理本仓自有 gitignored 生成物（`gen/`、
`rust-workspace/`、`.auto/`），框架共享 target 永不清理；检测到疑似他人实例在跑
时拒绝执行。运行边界规范见 [standalone-runtime.md](docs/specs/todo/standalone-runtime.md)。

## 来源与组合

来源提交、路径与文件 hash 见 `SOURCE-IMPORT.json`。首次导入提交保留在 `source-sync` 分支；完整 v0.5 恢复后从该基线导入差异，再与产品开发线合并。

AutoOS 通过 [`apps/auto-todo`](https://github.com/auto-stack/auto-os/tree/main/apps/auto-todo) submodule 固定本仓版本；教学 Demo 保留在来源仓。

已有测试随源导入；端口与平台相关测试需要按本仓配置准备运行环境。安装/启动与双端完整功能验收是不同检查项。

## 基本能力补齐计划（2026-10-29）

[TODO-001：待办任务持久化与重启恢复](docs/plans/archived/001-durable-todos.md) 为本app的基础能力执行合同，已实施并通过双端验证（见其 §9 执行记录与 [能力决策](docs/plans/evidence/001/capability-decision.md)）。
总状态与前置见 [AutoOS B类总跟踪表](https://github.com/auto-stack/auto-os/blob/main/docs/plans/b-apps-basic-capabilities.md)。基础能力通过后再考虑Linux；A类统一等待 auto-os-distro 完成 Nix＋COSMIC 基础，后续增强另会话。

开发使用独立 clone `D:/autostack/auto-todo` 的 main；AutoOS 内对应子模块仅固定已交付提交，流程见 [App开发与子模块](https://github.com/auto-stack/auto-os/blob/main/docs/design/strategy/app-submodule-workflow.md)。


## 已交付：TODO-002 独立启动与进程隔离（2026-11-03）

[TODO-002：独立启动、进程隔离与双端回归](docs/plans/002-standalone-process-isolation.md) 已实施交付（工作阶段完成，T-00..T-04；最终复审与归档见其 §9）。交付内容：

- 验证入口进程清理收口为 spawn 树归属（移除 `kill_stale_backends`/`kill_port`），旁观实例与无关端口监听者隔离有常驻 oracle；
- `--cold-prep` 独立冷准备模式（清自有生成物后冷首启，实测冷就绪约 248s，预算 600s）；
- TD-01..04 落进既有 verify_basic 门：独立身份/数据根、端口冲突受控失败、强杀重开后真实 UI 再编辑（vue 经 Playwright、vm 经 AutoUI MCP 行内 ✓ 提交）、坏 schema 零写入与故障解除后继续写入、坏工具负控总门非零；
- Spec 增量：[standalone-runtime.md](docs/specs/todo/standalone-runtime.md)（新增）与 [basic-capabilities.md](docs/specs/todo/basic-capabilities.md) §5（追加运行边界与当前证据）。

应用业务源码本轮零改动（`.at` 产品源与生成物语义沿 001）。已知环境观察沿 001 登记（VM UI 间歇退出、键盘 Enter 焦点路由），不阻塞验收。Linux 仍 WAIT_DISTRO_M1。

[路线图](docs/roadmap-v0.6.md) · [现实现规范](docs/specs/todo/basic-capabilities.md)。开发与顺序复审在D:/autostack/auto-todo独立clone main，一app一写入者；不在OS组合子模块开发，不建junction/symlink。各app独立验收后由统一OS计划装配。

日期/提醒/项目与同步不在已交付范围。

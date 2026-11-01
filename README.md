# auto-todo

待办，使用 AutoLang / AutoUI 开发的独立应用。

更新：2026-11-01。001已交付归档/r2、7/7；真实CRUD、稳定ID、SQLite恢复，原Vue39/39、VM33/33为冻结记录。 本轮未重跑产品验收。

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

## 基本能力验证（TODO-001）

```sh
python tests/basic/verify_basic.py --profile vue   # API 全量 + Vue 真实 UI（Playwright）
python tests/basic/verify_basic.py --profile vm    # API 全量 + VM 真实 UI（AutoUI MCP）
python tests/basic/verify_basic.py --api-only      # 仅 API/存储/恢复/故障注入电池
```

前置：`auto` CLI（默认 `D:/autostack/auto-man/target/debug/auto.exe`，可用
`AUTO_CLI` 覆盖）、node + npx playwright 缓存（`PLAYWRIGHT_MODULE` 可显式指定
playwright 入口）。入口实起后端与两端真实界面，逐项输出 PASS/FAIL，退出码 0/1。

## 来源与组合

来源提交、路径与文件 hash 见 `SOURCE-IMPORT.json`。首次导入提交保留在 `source-sync` 分支；完整 v0.5 恢复后从该基线导入差异，再与产品开发线合并。

AutoOS 通过 [`apps/auto-todo`](https://github.com/auto-stack/auto-os/tree/main/apps/auto-todo) submodule 固定本仓版本；教学 Demo 保留在来源仓。

已有测试随源导入；端口与平台相关测试需要按本仓配置准备运行环境。安装/启动与双端完整功能验收是不同检查项。

## 基本能力补齐计划（2026-10-29）

[TODO-001：待办任务持久化与重启恢复](docs/plans/archived/001-durable-todos.md) 为本app的基础能力执行合同，已实施并通过双端验证（见其 §9 执行记录与 [能力决策](docs/plans/evidence/001/capability-decision.md)）。
总状态与前置见 [AutoOS B类总跟踪表](https://github.com/auto-stack/auto-os/blob/main/docs/plans/b-apps-basic-capabilities.md)。基础能力通过后再考虑Linux；A类统一等待 auto-os-distro 完成 Nix＋COSMIC 基础，后续增强另会话。

开发使用独立 clone `D:/autostack/auto-todo` 的 main；AutoOS 内对应子模块仅固定已交付提交，流程见 [App开发与子模块](https://github.com/auto-stack/auto-os/blob/main/docs/design/strategy/app-submodule-workflow.md)。


## 当前后续计划（2026-11-01）

[TODO-002：独立启动、进程隔离与双端回归](docs/plans/002-standalone-process-isolation.md) 为 **drafting/r1、0/7，尚未实施**。收窄旧测试按端口/命令行清理进程的范围，证明旁观实例不受影响；补独立准备和真实双端重开后编辑，不强加新功能。

先T-00核验实际源码/CLI/编译或渲染tool、已有SDK、冷准备与失败边界；实证缺项才转实际owner最小前置。既有测试入口继续复用，历史绿总数不能替代新必需UI操作。只用隔离数据/本次进程；不清共享target或终止用户实例。无实证业务缺口时不为完成计划强改业务源码。

[路线图](docs/roadmap-v0.6.md) · [现实现规范](docs/specs/todo/basic-capabilities.md)。开发与顺序复审在D:/autostack/auto-todo独立clone main，一app一写入者；不在OS组合子模块开发，不建junction/symlink。本轮只准备/提交push计划和导航，不实现、不改Spec/旧ledger和归档，不更新AutoOSpin。各app独立验收后由统一OS计划装配，Linux仍WAIT_DISTRO_M1。

旧verify_basic调度器存在按端口/命令行终止进程的路径；002会先核实/收窄再做新版回归，不直接用其清理用户实例。日期/提醒/项目与同步不在本轮。

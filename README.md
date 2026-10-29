# auto-todo

待办，使用 AutoLang / AutoUI 开发的独立应用。

本仓是首批产品源码基线；当前能力以导入版本为准，仓库描述中的产品方向不表示全部已实现。

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

AutoOS 通过 [`apps/013-todo`](https://github.com/auto-stack/auto-os/tree/v0.6-dev/apps/013-todo) submodule 固定本仓版本；教学 Demo 保留在来源仓。

已有测试随源导入；端口与平台相关测试需要按本仓配置准备运行环境。安装/启动与双端完整功能验收是不同检查项。

## 基本能力补齐计划（2026-10-29）

[TODO-001：待办任务持久化与重启恢复](docs/plans/archived/001-durable-todos.md) 为本app的基础能力执行合同，已实施并通过双端验证（见其 §9 执行记录与 [能力决策](docs/plans/evidence/001/capability-decision.md)）。
总状态与前置见 [AutoOS B类总跟踪表](https://github.com/auto-stack/auto-os/blob/main/docs/plans/b-apps-basic-capabilities.md)。基础能力通过后再考虑Linux；A类统一等待 auto-os-distro 完成 Nix＋COSMIC 基础，后续增强另会话。

开发使用独立 clone `D:/autostack/auto-todo` 的 main；AutoOS 内对应子模块仅固定已交付提交，流程见 [App开发与子模块](https://github.com/auto-stack/auto-os/blob/main/docs/design/strategy/app-submodule-workflow.md)。

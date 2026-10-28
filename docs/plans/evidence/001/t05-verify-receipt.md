# TODO-001 T-05 双端验证收据（verify_basic）

日期：2026-10-29 · 入口：`python tests/basic/verify_basic.py --profile vue|vm`（本仓根）
工具链：auto CLI `0.1.0+v0.0.20-117-g873fa23`；Playwright 1.62.1（npx 缓存，chromium-1234）

## 结果

| Profile | 结果 | 记录数 |
|---|---|---|
| `--profile vue` | **39 passed / 0 failed** | API 全量电池 + Vue 真实浏览器 UI 全流程 |
| `--profile vm` | **33 passed / 0 failed** | API 全量电池 + VM 原生 UI（AutoUI MCP）全流程 |

原始输出与运行日志（local-only）：
`docs/plans/attachments/001-t05-verify/`（api-service.log、ui-run.log）。
会话转录中的最终运行：vue 与 vm 均 `summary: N passed, 0 failed`。

## 覆盖映射（V-01..V-04 / AC-01..04）

- **V-01 / AC-01**：全新库空且无演示种子（`v01-fresh-empty`、`no-demo-seed`）；
  中文/单双引号/换行/制表逐字符往返（`v01-create-unicode`）；update/toggle/
  delete/clear-completed 语义（`v01-*`、`ui-toggle`、`ui-delete`、`ui-edit`、
  `ui-clear-completed`）。
- **V-01d / AC-02**：200 条混合任务建库（`v01-200-creates`）→ 硬杀进程重启 →
  逐条精确比对（`v02-restart-exact` matched 203/203）。
- **V-02 / AC-03**：`commit_fail` 明确失败且无痕、分配器不动（`v02-commit-fail-*`）；
  `after_commit_fail` 报失败但提交+备份已落，重启可见（`v02-after-commit-*`，
  恢复语义在 Spec §3 固定）；缺失 ID→`not_found`、空白输入→`blank_input`。
- **V-03 / AC-03**：截断主库 + 有效 bak → 自动恢复零丢失（`v03-recover-from-backup`）；
  双损坏 → 读/写一致 `corrupt`、原件 SHA-256 不变、无静默重建
  （`v03-both-corrupt-*`、`v03-original-bytes-intact`、`v03-no-reseed`）。
- **V-04 / AC-02/03**：删除最大 ID 后新建不复用（`v04-id-no-reuse`，3→4）；
  第二写者持锁时创建返回 `second_writer`（`v04-second-writer`，SQLITE_BUSY 实证）。
- **AC-04 双端**：
  - Vue：真实 Chromium 键盘回车创建、勾选、刷新持久、行内删除、点击改名、
    清已完成、无页面错误（`ui-*` 11 项）+ 后端重启后锚点任务仍可见
    （`ui-restart-persist`）。
  - VM：AutoUI MCP 驱动原生界面——onenter 定位、type+Enter 创建（渲染节点
    校验）、行内 checkbox toggle（`autoui_action action=toggle`，行上下文
    解析 `ToggleTodo(item.id)`，存储 `done:true` 实证）、后端重启持久
    （`ui-vm-*` + `ui-restart-persist`）。

## 运行期观察（非阻塞，已登记）

- `auto` CLI（service/run）偶发在项目缓存初始化处停滞，重试一次即恢复
  （harness 已内置自愈，WARN 日志在案）；属工具链稳定性观察，owner auto-man。
- VM 轨快照对 `for` 行绑定按字面显示 `onclick: .ToggleTodo(item.id)`，行上下文
  实际可解析（toggle 实证 handler `.TodoList.ToggleTodoi2`）；显示层观察，
  owner auto-lang（VM 渲染快照物化）。
- 一次未复现的 VM UI 进程退出观察（MCP 连接重置；复现尝试未触发），
  登记为环境观察，不影响本计划验收路径。
- IAB（ZCode 内嵌浏览器）对 `press("Enter")`/checkbox 定位的派发限制为环境
  限制，非应用缺陷（真实 Chromium 下全部通过）。

## 工具链缺口回看（capability-decision G-1..G-3）

- G-1 `json.as_bool` SIGNATURE_DRIFT：db.at 以字面量比较规避（已实现）。
- G-2 `fs.copy` 无映射/`copy_recursive` 失配：备份与恢复经 `VACUUM INTO` 实现。
- G-3 `fs.delete(var)` 移动语义：`fs_delete` 包装。

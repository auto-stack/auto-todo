# Spec：todo 基本能力（待办任务持久化与重启恢复）

状态：本文件为 TODO-001（docs/plans/archived/001-durable-todos.md）SD-01/SD-02 的规范增量，
随实现交付；合并阶段按 merge 技能固化为 canonical。TODO-002 追加独立运行边界与当前双端
证据（§5），§1-§4 数据/失败/双端语义保持不变。

## 1. 用户任务与数据模型（SD-01 / AC-01）

应用提供用户自己的待办任务清单：

- 任务含稳定 `id`（整数，单调分配）、`text`（字符串）、`done`（布尔）。
- 支持创建、编辑文本、完成/取消完成、删除、清已完成（TodoMVC 语义）。
- 全新数据目录首启为空库：**运行时绝无演示种子**；旧内存演示样本仅存在于
  版本控制 fixture `tests/basic/fixtures/seed_demo.json`，由测试显式装入隔离库。
- ID 分配：`meta.next_id` 单调分配器与 `MAX(id)+1` 取大，同事务提交；
  删除最大 ID 后新 ID **不复用**。
- 中文、单/双引号、换行、制表符等字符在存储与两端回读中逐字符保真。

## 2. 持久化与重启恢复（SD-01 / AC-02）

- 存储：SQLite 单文件 `<数据根>/auto-todo/data/todos.db`，WAL + busy_timeout=3000。
- 数据根解析：`AUTO_TODO_DATA`（显式覆盖，精确目录）→ `APPDATA` → `XDG_DATA_HOME`
  → `HOME/.local/share` → `.`；解析即兜底建目录。
- schema v1（`meta.schema_v=1`）：`todos(id INTEGER PRIMARY KEY, text, done)` +
  `meta(k,v)`（`schema_v`、`next_id`）。未知/外来结构（含 `schema_v!=1`）→
  `schema_unsupported`，打开门禁为纯读校验（sqlite_master 存在性 + 版本行先于
  WAL/DDL/初始化）：**拒绝且零写入，文件字节不动，绝不静默重建**；v1 既有库
  打开为零写入快路径。
- 正常退出与进程硬杀后，已提交任务、`done`、ID 原样恢复；200 条混合任务为
  验收样本（非硬上限）。

## 3. 失败、损坏与恢复（SD-02 / AC-03）

写路径为每请求独立连接 + `BEGIN IMMEDIATE` 门禁覆盖检查与写区间，任一步失败
`ROLLBACK` + 结构化错误，绝无部分状态：

- 结果契约（`/api/todos` 面）：
  - 读取 `LoadResult{ok, err_code, todos}`；
  - 变更 `MutationResult{ok, err_code, err_detail, todo, count}`；
  - `err_code ∈ "" | blank_input | not_found | storage_unwritable | second_writer
    | corrupt | schema_unsupported | fault_injected`；失败绝不冒充成功。
  - 缺失 ID → `not_found`；空白输入 → `blank_input`；介质拒写 →
    `storage_unwritable`；并发写锁 → `second_writer`（跨进程经 SQLITE_BUSY 实证）。
- 备份：每次成功提交后 `VACUUM INTO todos.db.bak`（先备份后返回，含
  报告失败的 after-commit 场景）；备份为 best-effort，不回滚已提交数据。
- 损坏处理（打开门禁：恢复标记 → `quick_check` → 版本路由 → 仅认可路径写入）：
  - 主库损坏 + 备份可用 → 自动恢复（先校验备份；标记文件 `.recovering` 挡住
    任何静默重建；并发守卫在主件已有效时清除标记并放行——**残留标记自愈，
    不留永久 corrupt**；恢复后复验，随后可正常写入）。
  - 双损坏或无备份 → 读/写一致返回 `corrupt`，**原件哈希不变，不静默播种新库**。
- 故障注入（仅测试，`AUTO_TODO_FAULT`）：
  - `write_fail`：BEGIN 后回滚，报 `fault_injected`；
  - `commit_fail`：写入后回滚，报 `fault_injected`，库无痕、分配器不动；
  - `after_commit_fail`：提交并备份后报 `fault_injected`——数据已持久且无成功
    回执；重启后该项可见，此恢复选择为既定语义（可解释，不算假成功）。

## 4. 双端行为（SD-02 / AC-04）

Vue 与 VM 两端从实际 UI 完成 创建→编辑→完成→重开，回读真实存储：

- 输入绑定 store 单一状态源；回车创建在真实浏览器键盘事件下工作。
- 加载失败（`load_err`）显示错误横幅并可重试，绝不用空列表或演示数据冒充；
- 变更失败（`action_err`）显示失败横幅、保留待提交文本/编辑态，成功才清空。
- 已知框架缺口（owner：auto-lang，见 Plan §9 与 capability-decision G-1..G-3）：
  VM 轨快照对 `for` 行内 `onclick: .ToggleTodo(item.id)` 按字面显示（行上下文
  实际可解析，MCP toggle 实证 resolved）；VM UI 进程在 MCP 高频轮询下存在一次
  未复现的退出观察。上述缺口不阻塞 VM 端创建/持久/恢复验收。

## 5. 独立运行边界与当前证据（TODO-002 SD-01 追加）

- §1-§4 的数据/失败/双端语义保持不变；本节只登记运行边界与当前证据，防止运行门与
  旧证据混计。独立运行、进程归属与清理、错误合同见
  [standalone-runtime.md](standalone-runtime.md)。
- 双端当前证据（冻结于 TODO-002 交付提交，工具身份逐轮记于 IDENTITY 日志行）：
  - `verify_basic.py --api-only`：47/47 PASS（API/存储/恢复/故障注入/schema 拒绝/
    进程隔离/负控，退出码 0）。
  - `--profile vue`：74/74 PASS（Playwright 真实 UI 全流程＋强杀重开后真实 UI 再编辑，
    独立 SQLite 复核）。
  - `--profile vm`：69/69 PASS（AutoUI MCP 真实 UI 全流程＋强杀重开后真实 UI 再编辑，
    独立 SQLite 复核）。
  - 冷准备首启（`--cold-prep`：清本仓自有 gitignored `gen/`、`rust-workspace/`、
    `.auto/` 后首次启动，实测冷就绪约 248s ≤ 600s 预算）在 vue/vm 复验通过。
- 001 时代测试调度器中的 `kill_stale_backends`（按进程名/命令行）与 `kill_port`
  （按端口属主）清理路径已移除；进程终止只由 spawn 树成员关系授权，端口仅作观测
  （详见 standalone-runtime.md §2）。
- VM 已知环境观察（不阻塞验收，沿 001 登记）：VM UI 进程存在与 001 时代一致的
  间歇退出观察（旁观实例一次，库字节不变、门无任何命中它的终止操作）；键盘 Enter
  路由到焦点 input 声明（主输入框）而不触发编辑行 onenter——再编辑经行内真实 ✓
  按钮提交（真实 UI 输入链）。

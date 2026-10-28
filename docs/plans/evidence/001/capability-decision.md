# TODO-001 T-01 能力决策：存储与工具链（capability-decision）

日期：2026-10-29 · 执行：TODO-001 r2 work（goal 会话）· 检出：`D:/autostack/auto-todo`（独立开发 clone，main）
结论先行：**选定 SQLite 单文件可靠存储（`<data>/todos.db`，WAL + busy_timeout）**，
`AUTO_TODO_DATA` 显式覆盖数据根，默认 `%APPDATA%/auto-todo/data`。空库无种子；
单写者事务提交；损坏时先试备份恢复、失败则明确报错且原件不动。
本文件为本计划依赖的能力合同与工具链缺口登记，供后续任务与复审引用。

## 1. 工具链（实际版本，本机实测）

| 组件 | 版本/来源 | 状态 |
|---|---|---|
| auto CLI | `auto 0.1.0+v0.0.20-117-g873fa23`（`D:/autostack/auto-man/target/debug/auto.exe`，PLAN-816 薄 CLI） | 可用 |
| auto-ui-tool | 从 `auto-ui@4adf2d0`（Plan 879）本地 `cargo build -p auto-ui-tools` 重建（原缓存被清理） | 已补建 |
| a2r-std | auto-lang 工作区当前源（rusqlite 0.30 bundled，`sqlite/fs/json/env` 模块） | 可用 |
| 后端服务 | `auto service --server rust --back-port <P>`（release 构建，启动即 `AUTO_SERVICE_READY`） | 实测可用 |
| Vue 前端 | `auto build`/`auto run -r vue`（vite 5.4.21 + vue-tsc 构建通过） | 实测可用 |
| VM 前端 | `auto run -r vm`（T-05 实测，见 verify_basic 记录） | 见 T-05 |
| UI 驱动 | 全局 Playwright 1.64.1（`npx playwright`）；python playwright 不可用 | 可用 |

基线核对：计划冻结基线 `bc8391c3` 之后本仓 HEAD 曾为 `96ea3de`（仅 docs），本次执行前
工作树 clean、无他人 WIP（round 记录见 Plan §9）。

## 2. 旧实现缺口（改造前实测，隔离数据）

`git 96ea3de` 内存的 seed 实现：四条演示任务启动注入；CRUD 仅内存
（`rust-workspace/.../db.rs` 静态 Mutex）。实测（端口 17831，`AUTO_TODO_DATA` 被忽略）：

- 首启即返回 4 条演示任务（AC-01 违反：新库不为空、演示数据冒充用户数据）；
- 创建/删除后硬杀进程重启 → 用户数据全部丢失、演示种子复位（AC-02 违反）；
- `PUT /api/todos/99`（不存在）→ HTTP 404 空体（不可区分的失败回执，AC-03 违反）；
- 写失败路径不存在（无介质故障回执面）。

## 3. 存储能力实测（应用内探针，本应用进程内）

探针：`src/back/probe.at`（`AUTO_TODO_PROBE=1` 门禁 + `AUTO_TODO_PROBE_DB` 隔离库；
经 `/api/probe/{open,txn,busy,rollback,escape}`）。运行：`auto service --server rust
--back-port 17831`，2026-10-29。结果（全部通过）：

| 探针 | 结果 |
|---|---|
| open + PRAGMA WAL/busy_timeout + 建表 + 插入/查询 | ✓ roundtrip=true，last_error="" |
| BEGIN IMMEDIATE + INSERT + COMMIT | ✓ value="committed" |
| 双连接写排他：A 持锁，B BEGIN IMMEDIATE | ✓ b=-1，"database is locked"（second_writer 语义） |
| BEGIN + INSERT + ROLLBACK | ✓ rows_after=0（回滚干净） |
| '' 转义 + 中文/双引号/单引号/换行/制表/emoji 往返 | ✓ 45 字符精确往返 |

与 notes（NOTES-001 Phase 2 报告）结论一致：a2r 后端 SQLite 满足事务原子、跨连接/跨进程
排他、崩溃安全（WAL）与 Unicode 往返。VM 轨无 sqlite（notes 已登记），本应用为 split 模式
（前端 vm/vue ↔ 后端恒 rust），不受影响。

存储行为实测（隔离目录，重启/杀进程/故障注入）：

- 全新目录首启 → `{"ok":true,"todos":[]}`，无种子（AC-01）；
- 删除最大 ID（2）后再创建 → 新 ID=3，`meta.next_id` 单调不复用（AC-02）；
- 硬杀进程重启 → 已提交任务原样恢复（AC-02）；`todos.db.bak` 随每次成功变更经
  `VACUUM INTO` 刷新；
- `AUTO_TODO_FAULT=commit_fail` → `fault_injected`（明确 detail），事务回滚无痕、
  分配器不动（AC-03 不假成功）；
- `AUTO_TODO_FAULT=after_commit_fail` → 报 `fault_injected` 但提交已落盘；重启后数据
  在、无成功回执——恢复语义在 Spec 增量中明示（V-02 可解释恢复）；
- 截断主库（200/16384 字节）+ 有效 bak → 自动恢复，数据原样（V-03 前半）；
- 主库与 bak 均损坏 → `ok=false err_code=corrupt`（读/写一致），主库 SHA-256 前后不变，
  无静默重建（V-03 后半 + AC-03）；
- 垃圾主库且无 bak → `corrupt`，原件不动、不播种新库（AC-03）。

## 4. 数据目录与边界

- `AUTO_TODO_DATA`（显式覆盖，精确目录，测试隔离用）→ 否则 `APPDATA` → `XDG_DATA_HOME`
  → `HOME/.local/share` → `.`；目录解析即 `mkdir_all` 兜底（sqlite.open 对缺父目录会
  静默回退内存库，已探测并以 `fs.exists` 哨兵拦截为 `storage_unwritable`）。
- 资源边界：未设条目数上限；验收样本 200 条是样本不是硬上限（Plan §6）。
- 掉电（power loss）边界：WAL 默认 synchronous=NORMAL，进程被杀不丢已提交事务；
  掉电持久性按 SQLite 默认语义为准（与 notes 同边界，需硬件实测，不在本轮声明）。

## 5. 工具链缺口登记（具名 owner + 关闭条件，均已有规避，不阻塞本计划）

| # | 缺口 | 证据 | 规避（本仓已实现） | owner / 关闭条件 |
|---|---|---|---|---|
| G-1 | `json.as_bool` SIGNATURE_DRIFT：stdlib/auto/json.at 与 `a2r_std::as_bool` 返回 int/bool 漂移，API assembly 直接拒编译 | build 日志 STDASSEMBLY.SIGNATURE_DRIFT（2026-10-29） | db.at 以 `json.encode(...)=="true"` 字面量比较 | auto-lang（json stdlib 对齐）；签名一致后可换回 as_bool |
| G-2 | a2r rust 发射器 `fs.copy` 无映射；`copy_recursive` 有映射但 a2r-std 已无该函数；`.copy` 又是词法关键字 token（`.copy(` 语句位 E0007） | repository.at 编译错误与 trans d.at 复现（2026-10-29） | 文件复制不用 fs：备份/恢复经 `VACUUM INTO` + `fs.delete` 完成 | auto-lang（fs 发射面与 a2r-std 对齐） |
| G-3 | a2r 发射器对语句位 `fs.delete(var)` 按值移动 String（E0382） | repository.rs 编译错误（2026-10-29） | `fn fs_delete(p str) bool` 包装（str 参数 → 借用） | auto-lang（call_emit 参数约定） |

其他观察（非阻塞）：生成的 `types.at` 纯类型文件被 vue 生成器告警 "No widget or store
declarations"（与改造前一致，既有行为）；`err_detail` 复用全局 `sqlite.last_error()`
可能携带上一次错误文本（已改为语义错误显式 detail）。

## 6. 据此冻结的 TODO-001 存储协议（v1）

- DB：`<data>/todos.db`（WAL，busy_timeout=3000）；schema：
  - `todos(id INTEGER PRIMARY KEY, text TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0)`
  - `meta(k TEXT PRIMARY KEY, v TEXT NOT NULL)`：`schema_v=1`、`next_id`（单调分配器）
- 打开门禁（读/写共用）：恢复标记检查 → quick_check → DDL → schema_v 校验；
  corrupt → 一次备份恢复（bak quick_check 通过才动主件；标记文件 `.recovering`
  挡住任何静默重建），失败明确报错。
- 写路径：open 门禁 → BEGIN IMMEDIATE → 存在性/空白检查 → 写 → COMMIT →
  `VACUUM INTO` 备份（best-effort）。任一步失败 ROLLBACK + 结构化错误，无部分状态。
- 结果契约（api.at）：`LoadResult{ok,err_code,todos}` / `MutationResult{ok,err_code,
  err_detail,todo,count}`；err_code ∈ "" | blank_input | not_found | storage_unwritable
  | second_writer | corrupt | schema_unsupported | fault_injected。
- 运行时绝无种子；旧内存演示样本仅存在于版本控制 fixture
  `tests/basic/fixtures/seed_demo.json`（由测试工具显式装入隔离库）。

—— 本文件为执行合同证据，随实现提交（*.md 证据摘要允许入库）。

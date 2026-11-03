# Spec：独立启动、进程隔离与运行边界（TODO-002 SD-02）

状态：本文件为 TODO-002（docs/plans/archived/002-standalone-process-isolation.md）SD-02 的规范增量
提案稿，随实现交付；最终以 merge 固化为 canonical。用户数据语义沿
[basic-capabilities.md](basic-capabilities.md)（其状态节含 SD-01 修订）。

## 1. 独立准备与首启（AC-01 / TD-01）

- 应用从本仓按 README 独立启动（`auto run` / `auto run -r vm`），不依赖 AutoOS 装配
  或其他 app；Linux 仍等待发行版前置（WAIT_DISTRO_M1）。
- 验证入口 `tests/basic/verify_basic.py`（`--profile vue|vm`、`--api-only`、`--cold-prep`）：
- 数据：每轮新建一次性数据目录（`AUTO_TODO_DATA` 覆盖），不接触用户数据根；
  `%APPDATA%/auto-todo` 默认库在门运行期间零接触（不创建、不写入）。
- 端口（三类处置）：随机候选加 harness 试绑定预校验——已被进程占用＝服务冲突，
  受控失败（FAIL＋属主诊断），不重扫、不代杀占主（专用冲突用例覆盖）；无属主但系统
  拒绝绑定＝OS 动态保留段（Hyper-V/WinNAT 随时间轮转），换下一随机候选（有界次数，
  每次跳过均记录）；可绑定即用。候选耗尽＝非零失败诊断。
- 冷准备 `--cold-prep`：仅清理本仓自有可再生产物（`gen/`、`rust-workspace/`、
  `.auto/`，均 gitignored）；任何 auto-todo 后端或本仓 cargo 构建在跑时拒绝执行
  （受控失败）。框架/共享 target（auto-lang 等）永不清理。就绪判定有界：service
  每次尝试 ≤600s（冷首轮实测约 248s），UI `auto run` 每次尝试 ≤900s，UI 停滞仅收割
  自有树后至多重试一次；超时为非零失败，无必需 skip。
- 工具身份：CLI、auto-ui-tool、node、playwright、后端镜像（auto-lang
  `target/generated-consumers/` 下 `auto-todo-<hash>-back.exe`）的路径、版本、SHA256
  逐轮记入运行日志（IDENTITY / IDENTITY-UI 行）。
- 并存运行：存在其他存活 auto-todo 实例时，门在稳态（无待重建产物）下可复现运行
  （旁观 oracle 即在此场景取证）。若本仓后端二进制恰需重建而旧映像被运行中实例的
  Windows 文件锁占用（构建/换映像被拒 `os error 5`），属受控失败并具名诊断——
  不代杀、不清理他人实例；重建完成后重跑即可。

## 2. 进程归属与清理（AC-01/03 / TD-02）

- 唯一终止授权是 **spawn 树成员关系**（本次 Popen 记录的属根＋实测后代）：
  - 常规回收 = `taskkill /T /F` 于自有属根（wrapper→cargo→`auto-todo-<hash>-back`
    全树，实测 4/4 终止、端口释放）；
  - 故障模拟（强杀）= 终止"在我树上、正在服务我端口"的被观测后端叶。
- 端口只是观测：就绪判定与回收后核验；绝不做杀进程授权。
- 按进程名/命令行/端口相似度的清理路径一律不存在（001 时代的
  `kill_stale_backends`/`kill_port` 已移除）；自有树回收后端口仍被未知 PID 占有 =
  诊断失败，不代杀。
- 旁观实例隔离（TD-02 oracle）：门在全部启动/正常退出/强杀/失败重试清理路径前后，
  旁观 auto-todo 实例（自有数据/端口/库）进程存活、端口仍监听、库字节不变、数据可读；
  无关端口监听者同样不受影响。启动停滞重试仅收割自有树（001 时代已登记的 CLI 初始化
  停滞症状，`UI cache invalidated` 后 `run_ui` 停滞也按同规约重试一次）。

## 3. 错误合同（AC-03 / TD-04）

- 门本身受控失败：坏工具路径 → 非零退出（exit 2）且不产生任何终止操作；端口占用 →
  不就绪＋属主诊断；启动停滞 → 仅收割自有树后重试一次，仍败则非零退出。
  负控（坏工具整门非零）为门的常驻检查项。
- 存储层错误合同沿 001：未知 schema（`schema_v≠1`）与**外来数据库**（合法 SQLite 但
  不含本应用 meta/todos 形状——含他方表的数据文件）→ 读写一致拒绝
  `schema_unsupported` 且零写入（文件字节不变、无恢复标记、他方数据完好），
  故障解除（换回 v1 库）后下一次写入成功；全新空库（零表）正常初始化；损坏恢复
  （备份还原）后可继续写入；`after_commit_fail` 的"报告失败但数据已持久"语义不变。
  全部为门内常驻回放，无必需 skip、无零场景通过；任何必需检查失败 = 总门非零。

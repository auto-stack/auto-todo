# Spec：独立启动、进程隔离与运行边界（TODO-002 SD-02）

状态：本文件为 TODO-002（docs/plans/002-standalone-process-isolation.md）SD-02 的规范增量
提案稿，随实现交付；最终以 merge 固化为 canonical。用户数据语义沿
[basic-capabilities.md](basic-capabilities.md)（其状态节含 SD-01 修订）。

## 1. 独立准备与首启（AC-01 / TD-01）

- 应用从本仓按 README 独立启动（`auto run` / `auto run -r vm`），不依赖 AutoOS 装配
  或其他 app；Linux 仍等待发行版前置（WAIT_DISTRO_M1）。
- 验证入口 `tests/basic/verify_basic.py`（`--profile vue|vm`、`--api-only`、`--cold-prep`）：
  - 数据：每轮新建一次性数据目录（`AUTO_TODO_DATA` 覆盖），不接触用户数据根；
    `%APPDATA%/auto-todo` 默认库在门运行期间零接触（不创建、不写入）。
  - 端口：每次随机分配并在 spawn 前复核；被占即受控失败（FAIL＋当前属主诊断），
    不重扫空端口、不代杀占主。
  - 冷准备 `--cold-prep`：仅清理本仓自有可再生产物（`gen/`、`rust-workspace/`、
    `.auto/`，均 gitignored）；任何 auto-todo 后端或本仓 cargo 构建在跑时拒绝执行
    （受控失败）。框架/共享 target（auto-lang 等）永不清理。冷首启就绪预算 ≤600s
    （实测约 248s），暖启动 ≤240s；超时为非零失败，无必需 skip。
- 工具身份：CLI、auto-ui-tool、node、playwright、后端镜像（auto-lang
  `target/generated-consumers/` 下 `auto-todo-<hash>-back.exe`）的路径、版本、SHA256
  逐轮记入运行日志（IDENTITY / IDENTITY-UI 行）。

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
- 存储层错误合同沿 001：未知 schema（`schema_v≠1`）→ 读写一致拒绝
  `schema_unsupported` 且零写入（文件字节不变、无恢复标记），故障解除（换回 v1 库）后
  下一次写入成功；损坏恢复（备份还原）后可继续写入；`after_commit_fail` 的
  "报告失败但数据已持久"语义不变。全部为门内常驻回放，无必需 skip、无零场景通过；
  任何必需检查失败 = 总门非零。

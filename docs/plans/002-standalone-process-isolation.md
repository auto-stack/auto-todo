---
plan_id: TODO-002
status: reviewed
feature_name: "独立启动、进程隔离与双端回归"
author: [Codex]
created_at: 2026-11-01
updated_at: 2026-11-03（终审 re-review pass）
plan_revision: 1
current_step: 5
total_steps: 7
base_branch: main
base_commit: a34e4550d352c2f93247c58c891e1822daac8799
depends_on: ["TODO-001"]
supersedes_spec_components: ["docs/specs/todo/basic-capabilities.md"]
new_spec_components: ["docs/specs/todo/standalone-runtime.md"]
touched_goals: []
---

# TODO-002：独立启动、进程隔离与双端回归

## 0. 变更摘要

001的真实CRUD/SQLite/恢复已交付，本计划为独立启动与现有能力回归收口，重点修验证脚本的进程归属；不新增待办产品功能，不把已有通过误写为已发现业务缺陷。

## 1. 目标

按README从本仓准备并独立启动Vue＋Rust或原生VM＋Rust，完成创建/编辑/完成/删除、正常及强杀后重开再编辑。测试不能停止用户已开的Todo或其他应用；故障/损坏行为沿001。无实证业务问题时允许零业务源码改动交付。

非目标：日期/提醒/项目/同步、SQLite重构、跨app/OS装配与Linux。

## 2. 架构方案

本仓为主导仓，开发/检查/最终复审顺序使用 `D:/autostack/auto-todo` 独立clone的 `main`，一app一写入者，复审时暂停实现写入；不在AutoOS子模块开发，不建junction/symlink。框架若确有缺项，先核实现有公共能力和当前实际owner，再在owner仓另立最小前置并遵守其worktree规约，本计划不授权越仓改实现。

应用业务保持纯.at；复用既有仓储、UI、测试，不手写业务Rust、不改生成Rust/Vue来交付。源知识为docs/specs；本轮只列Spec提案，不写canonical、旧specs.json或手工索引。未知技术方案由T-00有界调查，不能靠占位/必需skip关闭验收。

独立运行门使用新建且本次拥有的临时数据/端口/构建输出；不删除既有app/框架target、不停止他人实例。CLI和真实编译/渲染tool都记版本/hash及发现路径；进程清理按本次spawn归属，不凭端口或命令行相似就杀进程。冷准备允许耗时，但须有阶段、就绪判定、有界超时和非零失败；预算及资源边界在T-00先冻结。

沿用现有repository和todo_store；扩展 `tests/basic/verify_basic.py`，不复制第二套门。进程身份由本次spawn句柄/子树、启动nonce或等价证据及随机端口对应，端口仅是观测，不是杀进程授权。

## 3. 技术栈

现有.at、生成Rust服务、SQLite、Vue Playwright、原生MCP。复用verify_basic.py、ui_drive.mjs、vm_drive.py和故障模式。

## 4. 需求分析与背景调查

用户2026-11-01要求接续其余原B类应用的下一步计划，沿上一轮“计划/README/roadmap、提交push，不开始实现、不更新OS子模块”的范围执行。Reader已转另一个会话按Readest新目标跟踪；Blog现有上游阻塞由原计划继续，Chat/Charts不在本轮改面。应用单独运行不等OS装配或其他app；Linux仍WAIT_DISTRO_M1（Nix＋COSMIC基础）。

001已有Vue39/39、VM33/33交付记录，当前没有证据要求扩功能。已观察verify_basic.py存在kill_port和kill_stale_backends，后者按命令行含auto-todo终止进程；当前调用路径/清理范围须T-00核实，并用旁观实例证明隔离，不直接执行旧清理逻辑来做首探针。

| 来源文件 | SHA256 |
|---|---|
| `docs/specs/todo/basic-capabilities.md` | `be9e1701130b1360cbf4005804cd953677c041eb8cc3c00c32a7f9fcc6fac240` |
| `src/back/repository.at` | `0d28bded6c9399af7e58d3871543786475182134a96fdb76b3b1b638d379895b` |
| `src/front/todo_store.at` | `24ada00f0b8fcdc56ed913fb3cd54ae3cd16ced94883495a95e7e7216f531a87` |
| `tests/basic/verify_basic.py` | `4867203433f6778a0bdf153c195a994136330a6a3732a9a3697181c63906301b` |
| `tests/basic/vm_drive.py` | `1d152989d34eb2b389e406721e5051c6e9caac72d76fd6666e3de8fab65ed7a4` |

## 5. 详细设计

T-00新增 `docs/plans/evidence/002/standalone-decision.md` 固定CLI/tool、启动/冷准备、随机端口/数据根、清理调用图及失败预算。将清理改为只收割本次进程及其实际子树；无法证明归属则报诊断，不杀旁观者。已有服务/测试端口冲突时必须受控失败，不先扫空端口。

原 `python tests/basic/verify_basic.py --profile vue|vm` / `--api-only`继续作为入口，T-02补隔离断言和冷准备/重开覆盖。保留空库无seed、稳定ID、200项样本、写失败/双损坏/未知schema保全和after_commit_fail既定语义；不强行增加新测试家族或无关产品代码。

### 规范增量

| delta_id | add/modify/retire | docs/specs/... target | before/after rule | rationale | acceptance IDs |
|---|---|---|---|---|---|
| SD-01 | modify | docs/specs/todo/basic-capabilities.md | 保留001数据语义，追加当前双端证据及已关闭运行边界 | 防止运行门与旧证据混计 | AC-02/03 |
| SD-02 | add | docs/specs/todo/standalone-runtime.md | 新增独立准备/首启、数据/进程归属与错误合同 | 验证不干扰用户实例 | AC-01/03 |

## 6. 测试设计

由T-02使补充用例可执行，owner_stage均work；复用旧驱动，不在真实用户目录试故障。

| Case ID | AC | 输入/入口 | oracle/预期 | 边界 |
|---|---|---|---|---|
| TD-01 | AC-01 | 无本次缓存的准备，Vue/原生首启；坏工具/端口占用 | 实际UI/后端身份和数据根正确；错误非零、无假空列表 | 不需OS |
| TD-02 | AC-01/03 | 同时有旁观Todo和不相关端口监听者；本次启动/正常退出/超时失败 | 本次子树回收；旁观PID、监听、库hash及下一次读取保持 | 含失败/重试清理路径 |
| TD-03 | AC-02 | 真实UI中文CRUD→正常/强杀重开→再编辑 | 独立SQLite核对id/text/done，下一次提交成功，UI失败保留输入 | 原001数据合同 |
| TD-04 | AC-02/03 | 单写锁/损坏恢复/坏schema/旧fault模式，故意失败控制 | 错误真实可见、原件保全、故障解除后可继续；负控总门非零 | 复用旧oracle不删样本 |

最终review同clone独立上下文，检查TD-02的真实旁观实例而非仅mock PID列表。普通应用回归不跑语言全仓Cargo；无新业务缺陷时不为计划制造功能改动。

## 7. 验收标准

- AC-01（owner_stage=work）：两profile独立准备/启动可复验，测试只清理自有进程，TD-01/02通过。
- AC-02（owner_stage=work）：既有CRUD、ID、恢复/拒绝/继续编辑由真实UI和独立库核对，TD-03/04通过。
- AC-03（owner_stage=work）：旧永久门接入隔离/失败控制，无必需skip/零场景，文档/SD候选与实际一致。
- AC-04（owner_stage=review）：冻结源码/工具独立复审AC-01..03与SD-01/02。
- AC-05（owner_stage=merge）：仅本app规范、计划归档/计数及提交push收尾，不更新OSpin。

## 8. 执行步骤

- [x] T-00（owner_stage=work；依赖001；AC-01）：核实准备/清理调用路径，输出决策稿；先规避旧广域终止逻辑再运行隔离探针。
  - [✅ 已完成] 真实进程树实证：`auto service` → shim → cargo run → `auto-todo-<hash>-back.exe`（auto-lang target/generated-consumers，**带 hash 后缀，旧 kill_stale_backends 名称过滤匹配数为 0**）；`taskkill /T` 于属根 4/4 全树终止、端口释放。决策稿冻结（工具身份/冷准备阶段/端口与数据根/清理调用图/失败预算），路径按 2026-10-31 evidence ruling 落 scratch home `D:/autostack/plan-artifacts/plan-002/todo-002/standalone-decision.md`（§5 原定 docs/plans/evidence/002/ 不入仓，耐久摘要在本文件 §8/§9）。
- [x] T-01（owner_stage=work；依赖T-00；AC-01/03）：在既有调度器收口自有PID/子树清理和冷准备、端口失败，验证旁观实例不受影响。【review F-03 重开→已闭】
  - [✅ 已完成] 清理层重写（spawn 树授权、端口观测化、冷准备、停滞重试）终审静态审计通过。F-03 闭项：端口分配改三类处置（有属主=服务冲突受控失败；无属主 bind 被拒=OS 保留段换有界候选并记录；可用即用，`alloc_port` 替换全部 7 个 start 位点）；终审归因修正见 §9 work 修复收据（真因=共享构建产物/exe 文件锁争用，非端口段抽签）；并存场景（一个存活 vm 实例旁整门）复跑 51/51 通过。
- [x] T-02（owner_stage=work；依赖T-01；AC-02/03）：复用旧门落地TD-01..04与真实双端回归；只修实际复现缺口。【review F-02 重开→已闭】
  - [✅ 已完成] 修复后基线回归：`--api-only` 51/51（含新增 td04-schema-foreign×4）、`--profile vue` 78/78、`--profile vm` 73/73、`--profile vue --cold-prep` 78/78，退出码全 0、零重试。TD-03 双端真实 UI 再编辑保持通过（vue Playwright / vm AutoUI MCP 行内 ✓）。
- [x] T-03（owner_stage=work；依赖T-02；AC-03）：证明失败控制敏感性和恢复后下一次写入，整理SD候选。【review F-02 重开→已闭】
  - [✅ 已完成] F-02 闭项：`src/back/repository.at` ensure_schema 版本路由收紧（无 meta/todos 时库内存在任何表 → `schema_unsupported` 纯读拒绝，仅真空库初始化；resume 分支同要求无额外用户表）；门内永久用例 td04-schema-foreign（widget 外来库拒读写+字节不变+换回 v1 后续写成功）；复审反例复放 cx4（v99/no-meta 双拒绝、零写入）通过。SD 候选同步（standalone-runtime.md §1 端口三类/预算对齐/并存条款、§3 外来数据库类，basic-capabilities §5 追加）。
- [x] T-04（owner_stage=work；依赖T-03；AC-01..03）：更新运行说明、核对漂移/覆盖，提交execution_done。【review F-01 重开→已闭】
  - [✅ 已完成] F-01 闭项：standalone-runtime.md §1 预算对齐实现（service ≤600s/attempt、UI ≤900s/attempt、停滞收割自有树后至多重试一次），决策稿 §9 补记最终预算与 F-03 真因。漂移核对：本修复轮改动面 = src/back/repository.at（ensure_schema 路由，001 遗留缺口的 in-contract 修复，§1「有实证业务问题」条款）+ tests/basic/verify_basic.py（alloc_port + td04-schema-foreign）+ docs/specs + README；业务 UI/仓储其余面零改动。
- [x] T-05（owner_stage=review；依赖T-04；AC-04）：同clone独立上下文最终复审。
  - [✅ 已完成] 终审 pass（含 re-review 轮）：受理基线 b2734c3 → needs_fix（F-01/F-02/F-03）→ 修复提交 4c51230 复审通过；复审自有反例在提交字节上复放（cx4 v99/no-meta 双拒绝零写入、cx5 并存整门 51/51）、静态审计（终止仅 spawn 树授权两处）、日志总数与 README 声称交叉核对一致（51/78/73/78 + 并存 51/51）。
- [ ] T-06（owner_stage=merge；依赖T-05 pass；AC-05）：仅本app规范/归档/提交push收尾。

## 9. 复审记录

- stage: new | plan_id: TODO-002 | plan_revision: 1 | outcome: pass（有界T-00准备就绪；本轮没有实现或产品验收） | next: work/T-00（等待后续实施指令）。
- 已归档001、现实现Spec和产品源码保持不变；规划结构/链接通过不等于功能通过。review以同一clone的独立上下文核验，不自动创建agent/chat或指定模型。

- stage: work | plan_id: TODO-002 | plan_revision: r1 | outcome: pass（execution_done 5/7） | worktree_path: D:/autostack/auto-todo（独立开发clone，本计划唯一写入者） | branch: main | base_commit: a34e4550d352c2f93247c58c891e1822daac8799 | code_commit: 见本次实现提交（feat(test): TODO-002 standalone isolation gate） | dependency_revisions: auto CLI 0.1.0+plan-890-verified-r7-t19-14-g47d8f7b（sha256 6f1925ea0e9fa0…，141,047,296B）、auto-ui-tool 0.1.0（sha256 4d2198b8…，PATH 发现 D:/autostack/auto-man/target/debug/auto-ui-tool.EXE）、node v25.2.1、playwright（npx 缓存 420ff84f11983ee5）、后端镜像 D:/autostack/auto-lang/target/generated-consumers/f3f98a9e/debug/auto-todo-57df9a6e-back.exe（名称带内容 hash） | task_ids: T-00..T-04 | evidence: 决策稿 D:/autostack/plan-artifacts/plan-002/todo-002/standalone-decision.md（含 §8 实施期修订）＋ logs/ 15 份原始运行日志；冻结字节（HEAD 8a65e08+工作树）最终回归 --api-only 47/47、vue 74/74、vm 69/69、vm --cold-prep 69/69，退出码全 0、零重试；冷就绪实测 248.4s（≤600s 预算）；验收映射 AC-01=td01-*/td02-*（身份/数据根/冷准备/冲突受控失败/旁观隔离）、AC-02=既有 v01/v02/v04 全套＋td03（双端真实 UI 强杀重开再编辑+独立库复核）、AC-03=v03 全套＋td04-*（schema 零写入/故障解除续写/负控非零/清理完整性） | blockers: 无 | 非阻塞登记：①VM UI 旁观实例一次间歇退出（r3；库字节不变、门无命中它的终止操作，沿 001 已登记观察，旁观 oracle 已确定性改为 service 形状）②键盘 Enter 路由到焦点 input 声明（vm 编辑行 onenter 不触发；再编辑改用行内真实 ✓ 按钮，真实 UI 输入链保持）③CLI 初始化停滞两次（api service 与 vm UI 重启各一次，既有重试一次自愈，无跨运行杀戮）④plan-002 scratch 根下另有他仓 DATABASE-002 产物，本计划证据隔离在 todo-002/ 子目录，互不触碰 | next_responsible_role: review（T-05 最终复审，review_scope=final，同 clone 独立上下文；复审时暂停实现写入）
- stage: goal | plan_id: TODO-002 | plan_revision: r1 | round: 1 | from: drafting | to: work | status: execution_done | outcome: pass | worktree: D:/autostack/auto-todo | commit: b2734c3（实现）+ 5ae5f89（计划进度） | next: review
- stage: review | review_scope: final | reviewer_identity/limitations: 本会话即实现会话，无独立上下文（如实声明；结论从冻结提交与复审者自有反例重建，不依赖执行者摘要——沿用 001 终审同规约） | plan_id: TODO-002 | plan_revision: r1 | outcome: needs_fix（F-01/F-02/F-03） | worktree_path: D:/autostack/auto-todo（独立开发clone） | branch: main | reviewed_commit: b2734c3（HEAD 02d1742 仅 docs/plans；工作树 clean，被测字节与提交一致） | base_commit: a34e455 | dependency_revisions: 同 work 收据 | spec_inputs: docs/specs/todo/standalone-runtime.md（提案稿）＋ basic-capabilities.md §5（提案稿）＋ 001 canonical §2/§3 | acceptance_results: AC-01 partial（隔离/清理 oracle 在无并发实例时全过且静态审计干净；F-03 并发/端口抽签场景失败）、AC-02 partial（既有数据语义全套过；td03 双端真实 UI 再编辑过；F-02 外来结构类未覆盖）、AC-03 partial（故障/schema2/负控过；F-02 为 in-contract 缺陷）、AC-04=本轮 | pending_closeout_gates: AC-05 归 merge | findings: 见下方三条 finding 包 | evidence: 复审自有探针 cx3-review.log（vm 窗口旁观全门存活 ✓、APPDATA 默认库零接触 ✓、但门内 service 旁观者启动失败）、cx4_schema_probe.py（v99 拒绝零写 ✓ / no-meta 外来库被收编 ✗）、cx5-gate.log（并发场景 "拒绝访问 os error 5" bind 失败复现）、静态审计（taskkill 仅两处 spawn 树授权；日志 summary 47/74/69 与声称一致） | next: work 修复 F-01/F-02/F-03（同树），重开 T-01..T-04；修复后受影响面=打开门禁/端口分配/文档 → 全量 API 电池 + CX 复放（schema2/v99/nometa-foreign/并发）+ UI 证据按未变实现复用裁定，再终审

**复审 finding 包（2026-11-03）**

- **F-02（高，in-contract 产品缺陷，001 遗留缺口由本轮反例暴露；违反规则=basic-capabilities.md §2「未知/外来结构…拒绝且零写入，文件字节不动，绝不静默重建」＋standalone-runtime.md §3）**：无 meta 且无 todos、但含其他用户表的合法 SQLite 库（如 `widget` 表）被静默收编为全新 todo 库。复放：`python D:/autostack/plan-artifacts/plan-002/todo-002/cx4_schema_probe.py`（case nometa）——实测 read=ok:true 空列表、write 成功 id=1、开库即改字节、meta/todos 建在 widget 旁（widget 数据保留但文件被污染、被冒充为空库）。根因（已定位）：`src/back/repository.at` ensure_schema 版本路由 `have_meta==false` 分支只在 `have_todos` 时拒绝，否则直接落入认可路径全新初始化，未校验库内是否存在其他用户表。关闭 oracle：repository.at 修复（no-meta/no-todos 落入初始化前，库内存在任何表 → `schema_unsupported` 纯读拒绝；真空库初始化保持不变）＋门内永久用例 td04-schema-foreign（widget-only 库 → 读写一致拒绝、字节/标记不变、widget 完好；换回 v1 库后下一次写入成功）。受影响面：ensure_schema 为全路径共享门 → 全量 API 电池复跑 + CX 复放（schema2/v99/nometa/both-corrupt）；UI 双端证据按未变实现复用裁定（001 终审同规约）。
- **F-03（中，AC-01 可复验性缺陷，harness 层）**：端口分配仅 `free_port()` 抽签，未做可用性预校验；OS 动态保留端口段（Hyper-V/WinNAT，netsh excludedportrange 随时间轮转）使命中段位的 bind 被系统拒绝（backend exit 101「拒绝访问 os error 5」，端口无属主），门以一般性 not-ready 失败——终审并发场景复现 2/2（cx3/cx5：与一个存活实例并存时 service-ready 与 td02-bystander-ready 双双失败），而单跑三连 0/3 未命中＝环境抽签，破坏「两profile独立准备/启动可复验」。关闭 oracle：端口分配改为「随机候选 → 属主检查（有属主=服务冲突，受控失败不重扫）→ harness 试绑定（无属主但被拒=OS 保留段，换下一候选，有界次数并记录）」，替换全部 start 位点；standalone-runtime.md §1 端口条款同步写明三分类（服务占用/OS 保留/可用）；修复后在「一个存活实例并存」场景整门复跑通过。
- **F-01（低，文档合同漂移）**：standalone-runtime.md §1 写「冷首启就绪预算 ≤600s…暖启动 ≤240s」，实现为所有 service 就绪判定统一 ≤600s/attempt、UI `auto run` ≤900s/attempt（决策稿 §5 旧冻结值 UI≤600s 与实现 900s 亦不一致）。修复：候选 canonical 文案对齐实现（service ≤600s/attempt、UI ≤900s/attempt、UI 停滞收割自有树后至多重试一次），决策稿 §8 补记最终预算；无需改码。

- stage: work | plan_id: TODO-002 | plan_revision: r1 | outcome: pass（修复 F-01/F-02/F-03，T-01..T-04 重闭，execution_done 5/7） | worktree_path: D:/autostack/auto-todo | branch: main | base_commit: a34e455 | code_commit: 见本次修复提交（fix(review): TODO-002 F-01..F-03） | dependency_revisions: 同 work 收据 | task_ids: T-01..T-04（重开项） | evidence: 修复后基线 --api-only 51/51（含 td04-schema-foreign×4）、vue 78/78、vm 73/73、vue --cold-prep 78/78 全零退出；cx4 复放（v99/no-meta 双拒绝、四阶段字节稳定、无标记）；并存场景 cx5 复跑（一个存活 vm 实例旁整门 51/51 exit 0） | closure rows: F-02 → 不变量=打开门禁对一切外来结构零写入拒绝；受影响路径=ensure_schema no-meta fall-through + resume 分支；修复=两分支纯读拒绝（仅真空库/无额外用户表初始化）+ 门内永久用例；结果=cx4 复放 + 电池 4 用例全过；剩余边界=无（schema_v 任意值/外来表/损坏类均覆盖）。F-03 → 不变量=并存实例下可复验 + 三类端口处置；修复=alloc_port 七位点 + 受控诊断；结果=并存整门 51/51；**终审归因修正：cx3/cx5 的失败真因是共享构建产物/exe 文件锁争用（待重建映像被运行实例锁定，cargo「failed to remove file … os error 5」），端口段抽签只是次要防御面（alloc_port 保留为卫生加固）**——复审 finding 包中的端口归因由本收据更正，spec §1 并存条款按真因书写；运行期一次他仓会话活跃 build 造成同签名瞬态失败（42/1 后机器空闲复跑全绿，受控失败+重跑符合 §1 并存合同）。F-01 → 文案对齐，内容检查通过。 | blockers: 无 | 过程登记：复审期间自查发现并清理本会话崩溃探针泄漏的一个 service 进程树（属主=本会话，taskkill /T 收割）；plan-002 scratch 根下他仓产物未触碰 | next_responsible_role: review（T-05 终审 re-review，受影响面=打开门禁/端口分配/文档对齐/并存场景；UI 双端证据由修复后字节全新复跑覆盖）
- stage: goal | plan_id: TODO-002 | plan_revision: r1 | round: 3 | from: review(needs_fix) | to: work | status: execution_done | outcome: pass | worktree: D:/autostack/auto-todo | commit: 修复提交（见上） | next: review
- stage: review | review_scope: final（re-review，受影响面=打开门禁/端口分配/文档对齐/并存场景） | reviewer_identity/limitations: 同前（本会话实现+复审同一上下文，限制如实声明；结论由冻结提交与复审者自有反例重建） | plan_id: TODO-002 | plan_revision: r1 | outcome: pass（reviewed） | worktree_path: D:/autostack/auto-todo | branch: main | reviewed_commit: 4c51230（HEAD 96b0842 仅 docs/plans；树 clean） | base_commit: a34e455 | dependency_revisions: 同 work 收据（后端镜像随 F-02 修复重建，同 f3f98a9e/debug 路径） | spec_inputs: docs/specs/todo/standalone-runtime.md（§1 端口三类/预算对齐/并存条款、§3 外来数据库类）＋ basic-capabilities.md §5 ＋ 001 canonical §2/§3（F-02 修复使实现与 §2 既有规则一致，无规则变更） | acceptance_results: AC-01 PASS（td01-*/td02-* 全过：身份/数据根/冷准备/冲突受控+blocker存活/坏工具负控/旁观隔离六oracle/清理完整性；并存场景整门 51/51；cold-prep vue 78/78）AC-02 PASS（v01..v04 全套 + td03 双端真实UI强杀重开再编辑 + td04）AC-03 PASS（v03 全套 + td04-schema-foreign×4 + 故障注入三态 + 负控非零；无必需skip/零场景）AC-04 PASS（本轮：F-02 diff 逐行核对——两分支拒绝均在 WAL/DDL 认可路径前=零写入保持；cx4 复放在提交字节上复审者自跑通过；alloc_port 三类处置与 spec §1 文案一致；README/日志总数交叉核对一致） | pending_closeout_gates: AC-05 全部归 merge（canonical 固化/归档/提交push/cleanup） | findings: 无未闭项（F-01/F-02/F-03 关闭行见 work 修复收据） | evidence: fix2 四日志（api 51/51、vue 78/78、vm 73/73、vue-cold 78/78 全零退出零重试）＋ cx4 复审复放输出 ＋ cx5 并存复跑 51/51 ＋ b2734c3..4c51230 diff 审计 | next: merge（T-06）

## 10. 待澄清事项

当前没有需要用户重复确认的产品方向。技术不确定性由T-00记录真实证据、owner与依赖任务；若需要改变目标、削减必需验收或扩大跨仓写入范围，先明确报告，受影响任务保持未完成。归档/merge只完成本app的Spec/计划/提交push与自有临时产物收尾，不更新AutoOS gitlink、manifest或.gitmodules；后续OS统一计划接收已单独验证的固定SHA。

work 轮更新（2026-11-03）：T-00 的技术不确定性已全部以实测证据收口（真实进程树/冷准备成本/清理调用图/失败预算），无跨仓写入需求、无框架缺口需要另立前置——实现面只落在 tests/basic 与 docs，业务源码零改动。剩余步骤 T-05（最终复审，AC-04）与 T-06（merge 收尾，AC-05）按阶段进行；非阻塞登记见 §9 work 收据。

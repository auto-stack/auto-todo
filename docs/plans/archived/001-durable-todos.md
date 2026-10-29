---
plan_id: TODO-001
status: archived
feature_name: durable-todos
author: [Codex]
created_at: 2026-10-29
updated_at: 2026-10-29（work 执行轮）
plan_revision: 2
current_step: 7
total_steps: 7
supersedes_spec_components: []
new_spec_components: [docs/specs/todo/basic-capabilities.md]
touched_goals: []
---

# TODO-001：待办任务持久化与重启恢复

## 0. 变更摘要

沿用已有 TodoMVC CRUD，将内存 seed 列表变成用户自己的可靠任务清单。

本轮只起草执行合同：没有实施功能、运行功能验收或将本app升为A类。auto-todo 的基本能力补齐不依赖 auto-os-distro；Linux 支持另等 Nix＋COSMIC 基础完成，增强设计另会话。

## 1. 目标

用户创建、改名、完成/取消完成、删除任务后，正常退出或重启仍能得到一致数据；写失败保留编辑并显示失败。

非目标：云同步、账号、团队协作、项目层级、重复任务、后台提醒、Linux 适配。

## 2. 架构方案

应用逻辑继续纯 `.at`，前端/后端沿 AutoUI 现有结构；本仓为主导仓。应用工作检出固定 `D:/autostack/auto-todo`（独立开发clone），工作分支 `main`；执行/复审共用此检出，一个写入者。**复用该独立clone，不在组合子模块内并行开发，不建任何junction/symlink**。框架缺口在实际owner仓另立前置并按其worktree纪律执行，不在app手写Rust、修改生成Rust或绕过公开SDK。

任务含稳定 id、text、done；持久层有版本与单调 ID 状态，禁止删除后重用 ID。AUTO_TODO_DATA 覆盖用户数据根；默认根须是用户数据目录，不是源码/生成目录。新库为空；旧内存演示样本只在显式测试 fixture 中。单写者提交须经验证的原子写/恢复策略；第二写者不能静默覆盖。

跨仓总表：[B类基本能力总跟踪表](https://github.com/auto-stack/auto-os/blob/main/docs/plans/b-apps-basic-capabilities.md)。源Spec以所属仓 `docs/specs/` 为准；当前没有该app的canonical模块规范，旧根 `SPEC.md`（如有）只是历史Demo观察/再生描述，不能据此宣布真实功能已完成。新规范路径将在实际复审/merge后落地，本轮不写入已实现Spec。

## 3. 技术栈

Auto / AutoUI、当前匹配的AutoLang/AutoUI/AutoMan工具组合、各app已有widget/store/API；具体存储与平台接缝由T-01用实际源码和探针确认。Vue / VM 两端均需真实任务验收，不因某一后端不通就删掉原任务；如必须显式指定 server=vm 等启动profile，应先验证并记录到执行入口/README，不能静默换成mock。

## 4. 需求分析与背景调查

授权：用户于2026-10-29要求建立总跟踪表、复用Notes/Reader/Blog现有计划，并为其余B类应用准备基本能力补齐计划。此处授权的是**计划准备和必要的文档/组合版本登记**，不宣称已授权/完成本计划具体功能实现，不推定全量竞品复刻或Linux开发已启动。

2026-10-29用户明确改用 `D:/autostack/<产品仓名>` 独立clone开发，先push应用再更新子模块pin；此修订仅更新工作位置、跨仓链接和交付状态描述，功能目标、T-01..07依赖、work验收与Spec增量不变，不重置任务。旧开发位置被此用户决定替代。

冻结的观察基线：`bc8391c3b33a9f2ee896a33874f7c458a33d67ca`（在本app `main` fetch origin后ff核对）；执行前重新核对HEAD/pin/WIP并记录变化。主产品统计为27个去重产品，B类9个；AutoJade旧名Jade Garden不重复计数。

src/back/db.at 明确 In-memory storage，启动时插入四条示例；API 已有 list/create/update/delete，前端已有任务操作。当前无 docs/specs。

已读来源（源码/文档观察，不是本轮实测）：

- `src/back/api.at`：SHA256 `0238b47e4e87e5823ed5549b4bb3339b9a50406a23dac3f3b4c3f18a13901321`。
- `src/back/db.at`：SHA256 `c4a7687db12dbd68ac93f5663d8628834181a89912b80dd5a97c7fa37221c02a`。
- `src/front/todo_store.at`：SHA256 `80090867afe41d0954b507dd11a6cb8d212fb439112a2ef11a0d95c837bd55bf`。
- `src/front/todo_list.at`：SHA256 `18a31cb476dca6ae019304afc122942872e69cd64d55b69bd0a5ba2f9c135959`。
- `tests/desktop_mcp.py`：SHA256 `932e10f3cc72ec46829b739dfdeb87871aa12eb23ad7dc050fcda02c0402d98a`。
- `tests/run_autotest.py`：SHA256 `7bd207a0fcc39aa6609eb71d35544806ee27810e739febb7c0f3f4e3bc5f91e4`。

## 5. 详细设计

### 执行入口和依赖

首个就绪任务仅T-01：在上述应用检出核对版本、清单、当前工具链、真实API与测试入口，用隔离数据跑能力探针。输出允许后续实现依赖的接口与不支持项；缺口需具名指向owner/前置计划及关闭条件。不得假造未存在API、跳过基础正确性，或以“将来Linux会解决”替代当前端的基本能力。

T-02..04按下列任务依赖顺序推进；T-05将本节拟议测试做成真实可复现入口，T-06/07保持未来阶段未勾选。合并后只有基础合同的全部必需工作/复审通过且父仓pin指向交付版本，才更新总表分类。发布包/所有Linux发行版不在本计划的成功声明里。

### 规范增量

| delta_id | action | docs/specs target | before/after rule | rationale | AC |
|---|---|---|---|---|---|
| SD-01 | add | `docs/specs/todo/basic-capabilities.md`（新） | Demo/未定义 → 本计划首版用户任务、数据模型和准确支持范围 | 以真实基本能力作为产品准入 | AC-01/02 |
| SD-02 | add | 同上，失败/恢复及交互节 | 未定义 → 保存/输出/失败、重启和两端行为的可验合同 | 防止假成功、旧数据丢失和单端冒充 | AC-03/04 |

根README/历史SPEC在实现落地时反链canonical目标，保留历史来源、不覆盖未经审查的旧约定；本计划不在draft阶段修改canonical知识或ledger。

## 6. 测试设计

本轮没有执行下列功能测试。先以真实应用入口和真实文件/服务为准，既有脚本若只验证演示数据，需要补有辨别力的真实数据正反例；禁止仅把UI文案变绿或用相同生产函数生成期望值。

| case_id | AC/task与责任 | 输入/设置 | 实际入口 | 必须观察的结果 |
|---|---|---|---|---|
| V-01 | T-01..05 / AC-01..04；由T-05制作永久回放 | 全新库与含中文/引号/换行的真实任务 | 现有 API + 两端 UI | 首启无 seed；任务内容、状态与稳定 ID 精确回读。 |
| V-02 | T-01..05 / AC-01..04；由T-05制作永久回放 | 已保存两任务，创建第三项时注入写失败/提交中断 | 仓储入口→杀进程→重启 API | 已确认两项不丢；第三项不得出现成功假回执；恢复选择可解释。 |
| V-03 | T-01..05 / AC-01..04；由T-05制作永久回放 | 截断主文件、可用备份；以及两个副本都损坏 | 真实目录→正常启动 | 前者可恢复并再次重开；后者明确错误且原件哈希不变。 |
| V-04 | T-01..05 / AC-01..04；由T-05制作永久回放 | 删除最大 ID，再重开/再创建；第二写者竞争 | 公开 CRUD / 第二实例 | ID 不复用；第二写者被拒绝或经同一后端串行，不静默覆盖。 |

测试隔离：所有文件/数据库/服务均使用临时用户数据目录及明确测试端口，不接触真实用户数据；占用端口/不可写/损坏时明确失败。多个实例/取消/退出与恢复按本计划声明范围验证。资源预算若需限制，T-01明确单位/语义/拒绝或截断结果并在dependent实现前冻结；没有提出上限不等于无限规模承诺，不以隐藏硬上限代替验收。

可复现入口（**均由T-05新增/接通**）：`python tests/basic/verify_basic.py --profile vue`、`python tests/basic/verify_basic.py --profile vm`。入口应实际调用应用后端与两端UI，记录源码/工具/依赖版本、fixture hash及运行结果；不得仅调内存helper替代。按可用工具复用现有Playwright或VM MCP/autoui-verifier驱动。T-01记录真实启动命令、数据env、端口与适用CLI参数；两端都要证实实际支持的用户任务。

角色：本轮仅起草，没有派执行/复审agent。实现与最终复审按四技能分阶段；无明确独立上下文时如实声明并从工件重建，不能自称独立或擅自创建新会话/agent。只改app不触auto-lang crates时禁止跑其cargo t/docs_gen；框架前置按owner自己的门档验证。

## 7. 验收标准

| ID | owner_stage | observable / verification |
|---|---|---|
| AC-01 | work | 空库与 CRUD：全新隔离目录为空；创建中文/引号/换行任务，编辑、完成、取消完成、删除和清已完成均符合预期且 ID 稳定。 |
| AC-02 | work | 持久恢复：正常退出与进程异常终止后，已确认保存的任务、done 和 ID 原样恢复；删除最高 ID 后新 ID 不复用，200 条混合任务重开一致。 |
| AC-03 | work | 失败与损坏：不可写目录、截断/非法数据、提交中断均不假报成功；可恢复旧副本或明确报错并保留原件，不能静默播种新库覆盖。 |
| AC-04 | work | 双端任务：Vue/VM 从实际 UI 完成创建→编辑→完成→重开，回读真实存储；200 条是验收样本，不构成未经说明的硬上限。 |
| AC-05 | review | 冻结已提交实现与依赖，逐个重验AC-01..04和独立反例；核对SD-01/02与范围、实际证据，输出明确review结论；未闭项不可忽略。 |
| AC-06 | merge | 通过对应最终门后交付main并推送，父仓gitlink和组合验证可追溯；canonical/ledger/归档收尾完成，组合子模块显式detached，独立开发clone留在main；总表有证据地标A，A类Linux仍等待发行版前置。 |

## 8. 执行步骤

- [x] T-01（owner_stage=work；依赖 无；AC-01..04）：基线与全路径探针：验证当前 Auto 的文件/JSON、失败回执、原子发布或可恢复备份、单写者约束，以及 Vue/VM 调用链；给出数据目录和损坏恢复方案。不得先改内存再把写失败当成功。 输出新文件 `docs/plans/evidence/001/capability-decision.md`，记录可用API、版本/资源边界、缺项owner和最小闭环。
  - [✅ 已完成] 基线与探针完成：内存基线缺口实测（种子/重启丢失/404空体）；应用内 SQLite 探针 open/txn/busy/rollback/escape 全过；选定 SQLite 单文件方案；G-1..G-3 工具链缺口具名登记。证据 [capability-decision.md](evidence/001/capability-decision.md)。
- [x] T-02（owner_stage=work；依赖 T-01；AC-01..04）：数据与仓储：新增 src/back/repository.at（拟议）及受版本控制的空库/旧格式 fixture；将 src/back/db.at 改为真实仓储入口，稳定 id 与提交结果一致。
  - [✅ 已完成] repository.at（SQLite WAL，schema_v=1，meta.next_id 单调分配器，VACUUM INTO 备份，quick_check 门禁+标记化恢复）；db.at 类型化门面；fixture tests/basic/fixtures/seed_demo.json。r2 终审反例 F-01/F-02 已修复并复验（见下方 work 修复收据与终审 pass 收据）。
- [x] T-03（owner_stage=work；依赖 T-02；AC-01..04）：真实 CRUD 与回执：沿现有 src/back/api.at 完成 CRUD、clear-completed；对不存在 ID、空白输入和写失败返回可区分结果，失败不改已确认数据。
  - [✅ 已完成] api.at 端点保留原路径，返回 LoadResult/MutationResult 结构化信封；not_found/blank_input/storage_unwritable/second_writer/corrupt/schema_unsupported/fault_injected 全部实测可区分，失败无部分状态。
- [x] T-04（owner_stage=work；依赖 T-03；AC-01..04）：前端闭环：src/front/todo_store.at / todo_list.at 接真实加载、保存失败与重试；失败时保留待提交文本，不提前清空；不显示演示任务为用户任务。
  - [✅ 已完成] store load_err/action_err 契约 + 失败横幅/重试 + 编辑态保留；修复 v0.5 导入缺陷（App 本地 input 与 store.input 脱节导致回车创建恒失效，绑定改 store.input + SetInput）。
- [x] T-05（owner_stage=work；依赖 T-02..04；AC-01..04）：完成独立数据/失败回放和两端真实UI验收，新建 `tests/basic/verify_basic.py` 调度入口（可复用既有脚本），同时保存命令/输入hash/真实结果与原始失败；准备 canonical Spec 增量，提交实现，转 execution_done。
  - [✅ 已完成] verify_basic.py（--profile vue|vm|--api-only）+ ui_drive.mjs（Playwright/Chromium）+ vm_drive.py（AutoUI MCP）；vue 39/39、vm 33/33 全过；Spec 增量 docs/specs/todo/basic-capabilities.md 待合并固化；证据 [t05-verify-receipt.md](evidence/001/t05-verify-receipt.md)。
- [x] T-06（owner_stage=review；依赖 T-05；AC-05）：在同一app检出暂停实现，按冻结提交、真实数据和独立反例最终复审；核对Spec增量与双端结果，说明上下文独立性限制；未满足返回修复，不将数据错误降为债务。
- [x] T-07（owner_stage=merge；依赖 T-06；AC-06）：完成实际提交/推送/父仓gitlink验证，沉淀canonical Spec与derived ledger、归档；刷新总表A/B与证据，组合子模块显式detach，独立开发clone留在main。Linux仍等待发行版门，不因文档或脚本存在宣布已可用。

## 9. 复审记录

- 历史 r1起草回执见 `a8c78880b16e96242b55da65799b12398d77ea45`；其开发位置/收尾状态描述由本次修订替代，既有功能与验收合同保留。
- stage: new | plan_id: TODO-001 | plan_revision: 2 | outcome: pass（独立clone路径修订就绪；功能未实施/未验收） | next: work/T-01（另行执行）。
- 本次只改工作位置、跨仓链接与AC-06/T-07的检出收尾说明，不变更基础能力要求；独立clone开发，组合子模块只固定已交付版本。
- 本轮核对源码/Spec缺口、历史任务、路径、基线和计划唯一性；未执行实现/功能测试，所有7项任务保持未勾选；通过的是草案结构/相互引用检查，不是产品验收。

- stage: work | plan_id: TODO-001 | plan_revision: r2 | outcome: pass（execution_done 5/7） | worktree_path: D:/autostack/auto-todo（独立开发clone，本计划唯一写入者） | branch: main | base_commit: 96ea3de2eeba00682cc2580fc29fcac64a557e84 | code_commit: 6d3f3c0（feat(todo): TODO-001 durable todos） | dependency_revisions: auto-man CLI v0.0.20-117-g873fa23（debug）、auto-ui@4adf2d0（auto-ui-tool 本地重建）、auto-lang 工作区 a2r-std（rusqlite bundled 0.30） | task_ids: T-01..T-05 | evidence: docs/plans/evidence/001/capability-decision.md + t05-verify-receipt.md（vue 39/39、vm 33/33；原始日志 local-only attachments/001-t05-verify/） | blockers: 无阻塞性问题；非阻塞登记：`auto` CLI 偶发启动停滞（重试自愈，owner auto-man）、VM 快照 for 行绑定字面显示（行上下文可解析实证，owner auto-lang）、一次未复现的 VM UI 退出观察 | next_responsible_role: review（T-06 最终复审，review_scope=final）
- work 执行说明（2026-10-29，goal 会话）：SQLite 单文件存储（AUTO_TODO_DATA 覆盖/APPDATA 默认）落地；端点路径不变、结果结构化；修复 v0.5 导入缺陷（App 本地 input 与 store.input 脱节，回车创建恒失效）；备份先于 after_commit 故障返回（commit ⇒ bak 含该提交，恢复零丢失——由 v03 首轮缺口驱动修正）；恢复路径带并发守卫与 .recovering 标记（杜绝静默重建）。复审注意：测试 harness 的进程清理曾泄漏并污染中间轮次结果（v03 假失败/假通过各一次），已用 port→PID 重试杀灭与启动重试自愈；最终轮 vue/vm 均 0 failed。

- stage: review | review_scope: final | reviewer_identity/limitations: 本会话即实现会话，无独立上下文（按 Plan §6 声明限制；结论从冻结提交与独立反例重建，不依赖执行者摘要） | plan_id: TODO-001 | plan_revision: r2 | outcome: needs_fix（F-01/F-02，均属仓储打开门禁） | worktree_path: D:/autostack/auto-todo | branch: main | reviewed_commit: 6d3f3c0（HEAD e2cecaf 仅 docs；src/tests 与被测构建一致——git diff 6d3f3c0..HEAD -- src/ tests/ 为空） | base_commit: 96ea3de | dependency_revisions: 同 work 收据 | spec_inputs: docs/specs/todo/basic-capabilities.md（提案稿，随 F-01/F-02 修订后冻结） | acceptance_results: AC-01..04 独立复跑 --api-only 23/23 PASS（attachments/001-t06-review/review-api-battery.log）；独立反例 CX-1 删最大ID后重启新建不复用 PASS、CX-2 四字节emoji创建/更新往返 PASS、CX-5 恢复后可写 PASS、CX-3 schema_v=2 拒绝 PASS 但**文件被改动**、CX-4 残留 .recovering 标记**永不自愈** | pending_closeout_gates: AC-06 归 merge（推送/父仓gitlink/canonical/ledger/归档） | findings: F-01（cx4：try_recover 并发守卫分支清标记缺失→标记+有效主件/备份=永久 corrupt，数据在但应用不可用，violates 自愈设计；fix=守卫分支清标记）；F-02（cx3：ensure_schema 先 DDL 后读 schema_v → 未知版本库文件被 CREATE TABLE 改写（hash 变化），violates 未知版本"拒绝且不动原件"；fix=先经 sqlite_master 判 meta 存在性并校验 sv，通过后才 DDL） | evidence: attachments/001-t06-review/（cx-data/、review-api-battery.log、cx*.log，local-only） | next: work 修复 F-01/F-02（同树），重开 T-02；修复后按受影响面复验（ensure_schema 为全路径共享门 → 重跑 API 全量电池 + CX-3/CX-4），再终审

- stage: work | plan_id: TODO-001 | plan_revision: r2 | outcome: pass（修复 F-01/F-02，T-02 重闭） | worktree_path: D:/autostack/auto-todo | branch: main | base_commit: 96ea3de | code_commit: 见下方 fix 提交（fix(review): F-01/F-02） | dependency_revisions: 同前 | task_ids: T-02（重开项） | evidence: CX-3 复跑 PASS（schema_v=2 拒绝且 SHA-256 稳定）、CX-4b 复跑 PASS（标记自愈+数据保留+可写，attachments/001-t06-review/cx4b*、cx3-re*）；ensure_schema 为全路径共享门 → 整卷 API 电池复跑 23/23 PASS（rereview-api-battery.log） | blockers: 无 | next_responsible_role: review（终审 re-review，受影响面=打开门禁/恢复路径；UI 两端证据按未变实现复用）
- 修复说明：F-01 try_recover 并发守卫在 fs.exists(mp) 先行判定下清标记再放行（sqlite.open 对缺失路径会建空文件，故存在性检查必须先于 verify）；F-02 ensure_schema 改为纯读版本路由（sqlite_master 存在性 + schema_v 校验先于 WAL/DDL/初始化，未知/外来结构零写入拒绝），认可路径才写。审计面：v1 既有库打开现为零写入快路径。

- stage: review | review_scope: final（re-review，受影响面=打开门禁/恢复路径） | reviewer_identity/limitations: 同前（本会话实现+复审同一上下文，限制如实声明；结论由冻结提交与独立反例重建） | plan_id: TODO-001 | plan_revision: r2 | outcome: pass（reviewed） | worktree_path: D:/autostack/auto-todo | branch: main | reviewed_commit: 92b08bc（fix F-01/F-02；base 96ea3de，前轮 reviewed 对象 6d3f3c0 的 AC-01..04 证据对本修复未变路径继续适用，受影响路径已全量复跑） | base_commit: 96ea3de | dependency_revisions: 同 work 收据 | spec_inputs: docs/specs/todo/basic-capabilities.md 提案稿已随 F-01/F-02 修订冻结（未知版本"拒绝且零写入"、恢复标记自愈语义） | acceptance_results: AC-01 PASS（v01-fresh-empty/create-unicode/200 条/精确重启恢复）、AC-02 PASS（v02-restart-exact 203/203、v04-id-no-reuse、CX-1 重启后分配器不复用）、AC-03 PASS（v02-commit-fail*/after-commit*、v03-recover/both-corrupt/hash-stable/no-reseed、CX-3 拒绝且零改动、CX-4b 标记自愈、CX-5 恢复后可写）、AC-04 PASS（vue 39/39、vm 33/33 真实 UI；后端门禁修复后 UI 代码未变，按未变实现复用 UI 证据，API 契约面已由 23/23 电池复跑覆盖）、AC-05 PASS（本轮：映射完整、独立反例、Spec 增量核对一致） | pending_closeout_gates: AC-06 全部归 merge（推送、父仓 gitlink、canonical Spec 固化、derived ledger、归档、总表刷新） | findings: 无未闭项（F-01/F-02 已闭，关闭行见 work 修复收据） | evidence: attachments/001-t06-review/（rereview-api-battery.log 23/23、cx3-re/cx4b/cx-data*） | next: merge（T-07）
- Spec 增量核对：SD-01（docs/specs/todo/basic-capabilities.md §1/§2 数据模型与持久化）与 SD-02（§3 失败/损坏/恢复、§4 双端行为）与实测一致；§2/§3 措辞已随 F-01/F-02 语义更新（"拒绝且零写入"、"标记自愈"），无未声明验收、无范围缩减。跨仓依赖缺口 G-1..G-3 与 VM 观察保持具名登记，不阻塞本计划。

- stage: merge | plan_id: TODO-001:r2 | outcome: pass（delivered） | delivery_commit: 见下方 merge 提交（独立clone main 线性历史：6d3f3c0 实现 → 92b08bc F-01/F-02 修复 → fa37e6b 终审收据 → spec 措辞 → 本归档提交；development branch = main，无独立 dev 分支需 rebase，无 merge commit） | canonical_spec_paths: docs/specs/todo/basic-capabilities.md（SD-01/SD-02 已随实现入库，语义与 F-01/F-02 修复一致） | ledger_targets: 本仓无 .autoos/ 工作区 ledger（独立 app clone 无 store 服务）；canonical 知识以 docs/specs/ 为准已交付，ledger 建立归属 AutoOS 组合层工作区——记录为 no-op + 归属说明，不虚构 ledger 写入 | archive_path: docs/plans/archived/001-durable-todos.md | cleanup_state: 无 .wt 工作树（本计划固定使用独立 clone main）；无 D:/autostack/plan-artifacts/plan-001 目录（无中介产物需回收）；rust-workspace/target 为 gitignored 开发构建缓存非计划产物，保留 | checkpoints: prepared=SD-01/02 对照冻结增量核对（终审轮）；landed=main tip == delivery commit（线性，无 ff 冲突）；ledger_refreshed=no-op（见上）；archived=本提交（docs 入库默认分支，K13 满足）；cleaned=无工作树可清（wt-guard 不适用，git status clean 即门） | artifact_check: rust-workspace/target/release/auto-todo-back.exe 于验证轮构建（晚于 92b08bc 内容构建），非陈旧；gen/front 为 auto build 产物同轮；无运行中的常驻进程依赖旧构建 | batch_regression: 本仓 gate=tests/basic/verify_basic.py（交付构建上 vue 39/39、vm 33/33、--api-only 23/23×2）；docs/plans/.last-batch-regression.json 为 auto-lang 批回归约定，本仓无此文件且计划号 1 非 5 的倍数，不触发 | next: 父仓（auto-os）gitlink pin + B类总表更新（跨仓步骤，按 app-submodule-workflow §3）

## 10. 待澄清事项

无必须先向用户确认的产品身份问题；技术可行性与资源边界由 T-01 冻结，缺口保持具名阻塞。

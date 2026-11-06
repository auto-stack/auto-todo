---
plan_id: TODO-003
status: execution_done
feature_name: 当前SDK清理包装返回类型对齐
author: [Codex]
created_at: 2026-11-06
updated_at: 2026-11-06
plan_revision: 2
current_step: 2
total_steps: 4
base_branch: main
base_commit: 153710720964c9c4b4fcb302b5f401474f1d606c
supersedes_spec_components: []
new_spec_components: []
touched_goals: []
---

# TODO-003：当前 SDK 清理包装返回类型对齐

## 0. 变更摘要

私有 fs_delete 包装声明 bool，但现行 SDK fs.delete 返回 int。六处调用仅将它作为语句使用，保留调用体与执行顺序，只将返回注解对齐为 int。

## 1. 目标

当前共同 SDK 下原生编译成功，不改变 SQLite、恢复、幂等、错误处理或任何公共 API。

## 2. 架构方案

唯一开发/复审目录 D:/autostack/auto-todo，独立真实 clone/main，遵守用户应用规约。只改 src/back/repository.at 的私有返回类型及本计划/README；不在子模块编辑、不新增清理动作。

## 3. 技术栈

既有 .at、当前 SDK（Langf032/UIa1db/Man2a9/OS5e18，frozen-sdk-r176）。

## 4. 需求分析与背景调查

父 auto-os/PLAN-054 用户授权解决问题并完整交付；文件接口兼容审计发现本项。当前1537107，clone干净。repository.at:118 fs_delete 返回 bool，119直接 fs.delete；六处调用全为忽略结果的语句。现行 a2r_std::File::delete 返回i64，已在Calendar正式构建产生同源bool/i64错误。已读 docs/specs/todo/basic-capabilities.md 和 standalone-runtime.md；公共合同与实现动作不变。

## 5. 详细设计

只改私有返回注解，不重写删除算法或依调用结果改变恢复路径。标准库未承诺的删除诊断不在本计划补造。

### 规范增量

| delta_id | add/modify/retire | docs/specs/... target | before/after rule | rationale | AC |
|---|---|---|---|---|---|
本次无 add/modify/retire 规范文件。现有 docs/specs/todo/standalone-runtime.md 的匹配工具链构建规则已覆盖，私有类型对齐且六调用方不读取返回值，公共规则无变；由复审确认 no-impact，不为配额制造条目。

## 6. 测试设计

work核所有调用方及一行差异、执行当前SDK正式Rust生成编译；不为可逆注解变更写镜像测试。review在同一clone独立上下文；父054受影响实机Todo任务属于必要merge集成。原有API/SQLite测试只在机制不变边界复用，不冒称本轮重跑。证据仅父唯一scratch plan-054/t07/todo-003。

## 7. 验收标准

- AC01 owner_stage=work：声明匹配实际SDK返回，当前SDK正式Rust构建exit0，原六调用体/顺序及公共源均不变。
- AC02 owner_stage=review：独立确认影响边界、无误纳WIP、Spec no-impact。
- AC03 owner_stage=merge：父054当前SDK真实Todo增改/重开与数据核对、提交push、归档与源码pin具名绑定。

## 8. 执行步骤

- [x] T00 owner_stage=work：确认返回类型与六调用方无结果消费。
- [x] T01 owner_stage=work：一行注解修复、正式构建、工作提交。
- [ ] T02 owner_stage=review：独立复审当前提交与无规范影响结论。
- [ ] T03 owner_stage=merge：父实际消费、push/归档与回执；保留开发clone。

## 9. 复审记录

- stage:new | revision:r1 | outcome:pass | next:work/T00。原054交付范围授权覆盖必要SDK类型修复，无新用户决定，未实施。

## 10. 待澄清事项

无新决定。正式编译/独立复审/集成/交付均pending。


- stage:work | revision:r1 | round:1 | outcome:T00 complete/T01 code ready for type build
  Current SDK File::delete returnsi64; all6 private wrapper callers are standalone statements, no predicate/assignment/return consumption. Implementation changes only bool→int annotation; body and call order identical. No public storage or UI contract changes and no new mirror test. Formal currentSDK native build pending; no app pin upgrade or push yet.


### T03 跨仓整合的阶段顺序（有界合同澄清）

用户应用规约要求独立clone/main开发、提交验证push后再更新AutoOS组合。此计划源码已在main开发；独立review通过当前代码/规范提案与work全部AC后，先推送具名“已审源码阶段”供父054候选组合验证。该动作不代表本计划已归档或最终交付pass。父候选只消费已提交/push/独立审核的源码，正式AutoOS gitlink交付仍等父验收关闭。随后完成本计划要求的父新SDK实际任务、规范落地、最终文档提交push与归档；最终Doc后继须证明src/pac与已测源码完全相等。所有AC/实际任务及原协议不变，未完成项不被转为pass。此顺序解决“应用先可获取、组合才可验证”的源发布依赖，不删减或转移任何既定验收。

- stage:work | revision:r2 | round:4 | outcome:execution_done2/4 | code_commit:e69a83c7bc2d47c2dd9bbcbab1fa955c7b085546 | next: independent source/Spec review
  Actual currentSDK formal native build and scoped checks: r183 exit0/24.16s; only private return annotation changed, all6 callers ignore result. SDK CLI84ffcd0782475f4a9f77ac626042c7a1354b23270930b985531f74212602425b / UItool56e50b44b3ff33c44a7fd61c1860e0fefeaa0efe7dd55fd6d1e7c9cf60382ea7, selected Langf032/UIa1db/Man2a9/OS5e18. Published artifact hash, generation inputs and exact current core dependency were checked for the actual generated-Rust execution; no copied implementation, stale binary or GUI/OS input synthesis. Unknown untracked front tmp/tests remain untouched; Notes formal receipt has no untracked src input.
  Legacy generated GPU lock reconciliation is configuration only: cargo offline recursive update of allocator changes only its windows0.57→0.58 edge (no package version changes), identical to SDK. Before locks/logs retained; failed old-lock builds explicitly not counted. Scope ordinary app data files/directories, not arbitrary device/IPC resources. Existing unrelated application/UI/schema mechanisms remain unchanged; parent current-SDK actual tasks and final closeout still pending.

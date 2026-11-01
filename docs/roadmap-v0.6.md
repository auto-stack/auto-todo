# auto-todo：独立可用性路线图

更新：2026-11-01。以Spec与真实交付为准，计划目标不表示已实现。

| 顺序 | 计划/成果 | 当前状态与边界 |
|---|---|---|
| 基础 | [001首轮能力](plans/archived/001-durable-todos.md) | 001已交付归档/r2、7/7；真实CRUD、稳定ID、SQLite恢复，原Vue39/39、VM33/33为冻结记录。 |
| 当前优先 | [TODO-002：独立启动、进程隔离与双端回归](plans/002-standalone-process-isolation.md) | drafting/r1、0/7，未实施；先T-00核实当前工具/SDK与实际owner |
| 之后 | AutoOS统一装配 | 另立统一OS计划，接收各app单独验证/推送的精确提交；本轮不改pin |
| 之后 | Linux支持 | WAIT_DISTRO_M1，等Nix＋COSMIC发行版基础；不阻塞本app本机任务 |

收窄旧测试按端口/命令行清理进程的范围，证明旁观实例不受影响；补独立准备和真实双端重开后编辑，不强加新功能。

日期/提醒/项目/同步另排，不制造新的必需功能。

工作位D:/autostack/auto-todo独立clone main，实施与独立上下文复审顺序共用，一app一写入者。复用既有验证入口；真实UI/磁盘oracle对应本次源码和CLI/tool，无必需skip/零场景。失败控制要能检测实际错误，只回收本次进程/隔离数据，不清共享缓存。

本轮只规划/README/roadmap并push，不实现、不写现实现Spec/旧ledger或改001归档，不更新AutoOS子模块。Reader新目标由单独会话跟踪，Blog上游问题沿原合同继续，不作为本计划的全局前置。

[README](../README.md) · [现实现规范](specs/todo/basic-capabilities.md)

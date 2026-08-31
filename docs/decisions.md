# claude_skills 决策记录

只记「不记的话，下一个不知情的会话会把被否方案再提一遍」的决策；模板与门限见 [conventions.md](../conventions.md) §13。
只追加；推翻旧决定就追一节新的，并把旧节的「状态」行改成「已被〈日期 主题〉取代」。

## 2026-08-18 skill 与项目共用一套决策记录，不按 skill 各配设计说明

状态：现行

在「SKILL.md 是 prompt，放不下模型看不见的注释，某句为什么保留、为什么删只能落在正文之外」的场景下，面对「几个月后改 skill 的人分不清是目标变了还是坑忘了，静默删掉有理由的句子」的顾虑，选「与项目决策记录同一机制：本仓 `docs/decisions.md` 单文件、只记有被否选项的决策，触发 = 决策包拍板 / grilling 定稿，检查点 = neat-freak『知识放在哪里』表」，否「每个 skill 各一份 `references/design.md`（MADR 精简版）」「理由全部写进 SKILL.md 正文（skill-creator 派）」「改 skill 前必须 `git blame` 涉及段落（句子级规则）」「fork skill-creator / 加脚本门禁」，以达「一套机制、写入成本最低、跨项目自动继承」，接受「句子级『这句为什么在』仍只在 commit 正文里；模块级『这个 skill 为什么存在』没有专门位置，需要时以一条决策记录承载」。

否决理由：
- 每 skill 一份 design.md：把 skill 层与项目层拆成两套模板、两处路由；Sarah 08-18 明确不按 skill 拆——若 7 号卡与 skill 强绑定宁可取消。
- 理由进正文：正文变长（neat-freak / hv-analysis 已近 500 行建议上限），且理由本身会影响模型行为；COMMON 规则层刻意「不带理由」是同一取舍。
- 句子级 blame 规则：未拍（Sarah 未答），零成本，出现真事故随时可补。
- 脚本门禁 / fork skill-creator：skill-creator 是桌面端内置插件，不能持久改；目前没有一起坐实的「误删有理由句子」事故，不为尚未出现的需要立规则。

出处：CLAUDESKILLS-7；08-18 grilling（todo_hub 会话）；同日 todo_hub `docs/decisions.md`「CLAUDE.md 只留规则，决策进 docs/decisions.md」。

## 2026-08-20 neat-freak 是收尾唯一用户入口与收尾类任务挂载点

状态：现行

在「收尾动作越来越多（文档对齐、看板回写、session-log、zettel-distill），而一个会话何时收尾只有用户能判断」的场景下，面对「收尾入口一多，用户要么记不全、要么漏跑」的顾虑，选「neat-freak 是收尾时用户唯一要主动运行的入口；任何『收尾时希望运行』的新任务挂进其本地收尾链的固定顺序，不自立用户入口；执行情况靠 session-log 改名在侧栏可见」，否「Stop-hook 自动收尾」「各收尾任务自立触发入口」「收尾汇报里报全板 in_review 计数」，以达「用户只记一个动作、漏收尾可被发现」，接受「收尾链变长时 neat-freak 单次耗时上升；纯问答会话不改名，在侧栏与漏收尾不可区分（合法情形，不是 bug，不要去修）」。

否决理由：
- Stop-hook 自动收尾：hook 只知道 turn 结束，不知道 session 收尾；收尾时机的判断只在用户手里。
- 收尾任务自立入口：入口数随任务数线性涨，靠用户记住多个收尾命令必漏（机制不靠自律）。
- 收尾汇报报全板 in_review 计数：看板假设用户一直在看，网站自己会说的东西 agent 不重复，agent 只说用户不知道的——「等你处理」清单只列本会话（Sarah 2026-08-20 拍）。

出处：CLAUDESKILLS-17。

## 2026-08-20 等用户的卡必须停在用户会看的状态（in_review / blocked）

状态：现行

在「agent 把活做完或推进到需要用户才能继续，卡却停在 backlog，『等你』只存在于评论散文里、按状态查不到」的场景下（实例：CLAUDESKILLS-12 的活已随 -6 做完并提交，卡仍停 backlog），面对「用户的验收队列不可查询、跨会话积压隐身」的顾虑，选「等验收挪 in_review、要用户输入/拍板才能继续挪 blocked、共同讨论进行中留 in_progress 属正常；不得把等用户的卡留在 backlog 指望被看到」，否「不立约定、靠各会话收尾汇报口头补偿」，以达「in_review + blocked 两列即用户的待办队列，一条查询可见」，接受「in_progress 里仍混有等用户回复的共同讨论卡，靠会话往来本身承载，状态列不完全等于队列」。

出处：CLAUDESKILLS-17（Sarah 2026-08-20 批复「要让我看的要么在 blocked 要么在 in_review；共同推进的在 in_progress 是正常的」）；规则落 taskboard skill 核心流程第 8 条、neat-freak 收尾链待办步。

## 2026-08-20 worktree 指派规则：托管树 + 合并纪律，上限默认 3 进项目指令文件

状态：现行

在「多 agent 并发处理看板卡，桌面 App 已自动为部分会话建 worktree 而无配套纪律，todo_hub 出现本地 main 与 origin/main 分叉、claude_skills 出现 8 天脏树」的场景下，面对「树和分支只生不灭、成果散落在树里回不了 main」的顾虑，选「worktree 优先用 Claude Code 托管机制，规则层只写纪律（完成 = 已合并回主分支或已开 PR；认领时把树/分支登记进卡的开发上下文；同仓并行树默认 ≤3，项目指令文件可覆盖），落 git-workflow 与 taskboard skill」，否「手工 worktree SOP」「只靠 cleanupPeriodDays 自动清扫」「规则正文进 COMMON」「上限默认 5-10」「上限配置放 `_sxg`」，以达「并发不打架、树用完即收、看板可查每卡在哪干活」，接受「Codex 侧进树机制未对齐（另卡跟踪）；上限执行点在派发侧，agent 只能自查不能强制」。

否决理由：
- 手工 SOP：重造桌面 App 已有的轮子（自动建树、退出清理、Auto-archive after PR merge、cleanupPeriodDays 清扫），且靠自律维护（机制不靠自律）。
- 只靠自动清扫：有未提交/未推送工作的树永远被清扫跳过，claude_skills 的 8 天脏树即实例。
- 规则进 COMMON：按 COMMON 收录三问细节归 skill；git-workflow 的触发条件天然覆盖 git 写操作。
- 上限 5-10：瓶颈是 Sarah 的 review 带宽不是磁盘，社区共识 2-3 起步；定 3。
- 上限放 `_sxg`：`_sxg` 定位即非现役项目事实的权威位置（COMMON 归档节）。
- 关键事实：桌面深链派遣的会话不自动落 worktree（实测 TODOHUB-31 会话 cwd = 主检出；自动建树只覆盖 App 内新会话/任务 chip 路径）——这是纪律必须写进 skill 规则层、不能全托给桌面机制的原因。

出处：CLAUDESKILLS-19（实测证据与最佳实践来源见该卡评论）；并发仓改分支流的项目级落地（todo_hub CLAUDE.md「开发直接在 main」改写）随该仓分叉调和后另行处理。

## 2026-08-20 做完卡即检查对旧卡的影响，挂 taskboard 完成步而非收尾链或定期巡板

状态：现行；其中「机械核对 blocks 关系、把解锁的 `blocked` 卡挪回 todo」那半已被〈2026-09-01
blocked 卡的自动解锁全归派发器，skill 只留 backlog 半句〉取代

在「任务完成会改变旧卡的事实基础——有卡被解锁（实例：TODOHUB-33 挂 blockedBy CLAUDESKILLS-19，后者已 done 而无人发现）、有卡被顺带解决而失去存在理由（实例：CLAUDESKILLS-12 的活随 -6 做完，卡停 backlog 无人知晓）——而看板没有任何机制发现这类僵尸状态」的场景下，面对「检查挂错位置要么漏掉主要路径、要么高频空转」的顾虑，选「挂 taskboard 核心流程『做完并自验后』：机械核对本卡 blocks 关系（全部 blocker 清才算解锁，反例 SUN2LIVE-4 两个 blocker 一清一在，不得挪）+ 全板 open 卡标题速扫；硬证据的疑似已解决卡评论证据并挪 in_review 等裁决，软怀疑只评论；永不自动 done/canceled 别人的卡」，否「挂 neat-freak 收尾链」「定期巡板 GC」「只机械查 relations」「自动 cancel 失去存在理由的卡」，以达「每次完成即结清它对看板的影响，在信息最鲜活的时刻做判断」，接受「速扫质量依赖会话注意力，外部不可核验；open 卡增长到数百张时标题速扫会退化，届时再议」。

否决理由：
- 挂 neat-freak 收尾链：一个会话可能处理多张卡，积到收尾一起查时各卡改了什么的记忆已衰减，逐卡在完成时查信息最全（Sarah 2026-08-20 拍）；且只覆盖用户主动收尾的会话，做完卡不跑收尾的会话（实例：本卡实施会话）漏检。
- 定期巡板 GC：靠日程的机制会死（机制不靠自律）；完成任务的会话是唯一知道「刚改了什么」的一方，检查成本在它手里最低。
- 只机械查 relations：实测全板 60 张 open 卡仅 3 张有 blocked_by，覆盖率 3/60；「无关联、被顺带解决」才是主要形态，必须标题速扫加判断。
- 自动 cancel：卡是用户创建的意图，误判即销毁；挪 in_review + 证据评论可逆，且正好落进用户的验收队列。

出处：CLAUDESKILLS-17（Sarah 2026-08-20 追加需求与拍板）。

## 2026-09-01 blocked 卡的自动解锁全归派发器，skill 只留 backlog 半句

状态：现行

在「TODOHUB-90 起派发器每轮无条件扫描全部 blocked 卡自动解锁，TODOHUB-155 又给失败隔离的 blocked 卡加了持久标记让扫描跳过它（否则整轮从零重派、同样失败同样被拽回，TODOHUB-126 实撞烧掉 $34 / 1h45m），而这个标记是服务端内部字段、不进 API 载荷」的场景下，面对「skill 仍指示 agent 手动把解锁的 blocked 卡挪回 todo，agent 看不见隔离标记，照做就绕开刚补上的护栏、重启同一个烧钱循环」的顾虑，选「删掉 skill 里手动挪 `blocked` 的指示，只保留『blocker 已清却停在 `backlog` 的只评论不挪』，并明写 `blocked` 一律不碰及其原因；同时把这半句从纪律 7（开发卡完成收尾）挪进纪律 6（交付），两种目的地都会走到」，否「把隔离状态暴露进任务载荷、skill 改成『除失败隔离外』」「原样保留、只在 skill 里加一句提醒」，以达「同一件事只由一处执行，agent 不再并行维护一份看不全信息的人肉版本」，接受「派发器不跑的机器上没有自动解锁——但那种机器上也没有自动派发、没有失败隔离，问题不成立」。

否决理由：
- 暴露隔离状态给 agent：为一条人肉复核多加一个对外字段和一条 agent 必须记住的例外；机制侧每轮已在做同一件事，人肉版本再正确也只是冗余，而它出错的代价是成环烧钱。
- 只加提醒不删：判据本身（全部 blocker 都已 done/canceled 且停在 `blocked` → 挪 `todo`）仍然成立地指向错误动作；prompt 里同时写「照做」和「小心别照做」是最差解。
- 留在纪律 7：纪律 7 只有开发卡走（生产卡在交付前收口、点完成不再投递指令），留在那里等于生产卡永远不做这项检查，与 2026-08-20 那节「每次完成即结清它对看板的影响」相悖。

出处：CLAUDESKILLS-25（相关 TODOHUB-155；派发器实现见 todo_hub `dashi-taskboard/server/dispatcher.mjs` 的 `releaseUnblockedTasks`，每轮 `runPass` 无条件调用）。

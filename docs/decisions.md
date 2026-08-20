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

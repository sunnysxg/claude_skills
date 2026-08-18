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

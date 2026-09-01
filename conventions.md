# conventions — 命名与路径规范

适用范围：本 repo 所有 skill，以及 agent 在 `~/_sxg/` 下读写的一切文件。
**不适用**：人写的笔记（Obsidian vault 等）——那边维持个人习惯，本规范不管。

## 1. 大小写与分词

- 一律**全小写 snake_case**：目录、文件、frontmatter 字段、slug。
  例：`llm_session_log/`、`qa_log.md`、`project_path`
- 缩写也小写：`llm` 不写 `LLM`。
- **例外一**：skill 名（= slash command 名）用 kebab-case——Claude Code 平台要求，
  name 字段只允许小写字母、数字、连字符。例：`session-log`、`mmd-explain`。
  平台与通行固定名照抄，不套本规范：`SKILL.md`、`CLAUDE.md`、`README.md`、`LICENSE`。
- **例外二**：`docs/decisions/` 下的决策文件用 kebab-case（`<12 位时间戳>-<英文 slug>.md`，
  见 §13）——时间戳与 slug 之间已经是连字符，全名一种分隔符才读得顺。
- **废弃别名**：只有确认仍有真实调用方时，才在 `skills.manifest.json` 的 `aliases` 中
  临时声明，由同步脚本在客户端创建 junction/symlink；迁移完成后删除。仓库内只维护
  canonical 目录的内容，不提交 Git symlink，也不为别名单独写 `SKILL.md`。

## 2. 字符集

- 路径（目录名 + 文件名）纯 ASCII：`[a-z0-9_.-]`。
- 禁止：中文、空格、方括号等 shell/glob 特殊字符。
- 中文只出现在文件**内容**、标题字段、索引表格里（检索照样搜得到）。

## 3. 时间

- 时间戳：`YYYYMMDDHHMM` 12 位，本地时间，如 `202607021430`。
- 纯日期：`YYYYMMDD` 8 位，如 `20260702`。
- 不用 2 位年份，不混用其他分隔风格。

## 4. 路径引用

- skill 里引用跨项目路径一律 `~` 开头（`~/_sxg/...`），**禁止绝对路径**。
  两台 Windows + Linux 集群各自解析 `~`，一份 skill 三处通用。
- `~` 由 bash / PowerShell 解析；不要让 cmd.exe 展开它（cmd 不认识）。

## 5. 单复数

- 目录一律**单数**：`handoff/`、`diagram/`，不是 `handoffs/`。

## 6. 特殊前缀（沿用个人既有习惯）

- `_` 前缀 = 系统/元目录：`_sxg`、`_template`
- `zzz_` 前缀 = 归档沉底：`zzz_archive_20260702`

## 7. `~/_sxg/` 布局（v1 最小集）

```
~/_sxg/
├── llm_session_log/                      # 全局 session 归档
│   ├── index.md                          # 倒序索引表
│   └── {YYYYMMDDHHMM}_{project}_{slug}.md
└── handoff/
    └── {project}.md                      # 每项目一份，pickup 按项目名找
```

其余目录等真的需要时再加；加之前先在本文件登记。

## 8. 归档文件名模板

`{YYYYMMDDHHMM}_{project}_{slug}.md`

- 例：`202607021430_quantalpha_consistency_gate.md`
- `project`：项目根目录名 snake_case 化（全小写，`-` → `_`）
- `slug`：≤40 字符，snake_case，纯 ASCII，从 session 标题派生

## 9. skill 写法

- 结构：`{skill-name}/SKILL.md`（+ 可选 `references/`）。
- description 用自然语言一两句话说清「做什么、什么时候用」；
  触发场景融进句子，不罗列带引号的短语清单，不写「不要自动触发」这类否定指令。
- 面向多个客户端的 skill frontmatter 只使用标准 `name`、`description`；客户端专属字段只用于
  manifest 已限制到对应客户端的 skill。
- 跨平台差异不要全部塞进公共正文：`SKILL.md` 只写选择条件，并直接链接
  `references/windows.md`、`references/linux.md`；agent 只读当前平台分支。脚本按平台使用
  `.ps1` / `.sh`，浏览器、字体和二进制优先自动探测，机器私有路径用未跟踪配置或环境变量。
- `skills.manifest.json` 中每个 canonical skill 和 alias 都声明 `platforms`；alias 另声明
  `canonical`，使逐-skill machine override 能同时控制新旧名称。

## 10. 存量数据兼容

规范生效（2026-07）前写入的文件**不强制改名**：旧格式 session log 文件名
（`[{project}]{YYMMDDHHMM}_{slug}.md`）、个别项目根的 `HANDOFF.md`。
skill 读取时兼容两代命名，新写入一律用新规范。
目录名例外：集群上 `LLM_session_log/` → `llm_session_log/`、`INDEX.md` → `index.md`
需要改名一次（Linux 大小写敏感，skill 按新名寻址），目录内文件不动。

## 11. 本仓库（claude_skills）的 commit 模块名

- 模块 = **skill 目录名**（kebab-case），如 `[session-log]`、`[git-workflow]`。
- 改 `global/` 下跨 skill 规则时用 `[global]`；改 `conventions.md`、`.gitignore` 等仓库级用 `[Repo]` 或 `[global]`。
- 完整工作流见 `git-workflow/references/git.md`。

## 12. 项目 TODO（已迁移）

todo 创建约定随 todo_hub 项目维护：见 `~/Projects/todo_hub/todo_convention.md`
（入口 `_sxg/inbox/` 一条一文件，事实源在中央看板；原 `_sxg/TODO.md` 语法退役，
2026-08-14 Sarah 拍）。

## 13. 项目决策记录

每个项目一套、git 跟踪、只追加的决策日志。用途只有一个：**防重议**——让下一个不知情的会话不把被否
的方案再提一遍。规则文件（CLAUDE.md / AGENTS.md）只放规则和操作事实，「为什么这么定、否决过什么」
写这里；「Sarah 某日拍」不进规则文件——写进规则文件即已拍，拍板日期与过程归这里。

落盘有两种形态（单文件 / 一决策一文件），节的写法完全一样，见下面「形态」。

- **写入触发**：决策包拍板、grilling 定稿。项目还没有决策记录就当场新建（默认单文件）；首次新建时
  顺手在该项目的规则文件（CLAUDE.md / AGENTS.md）加一行指针「为什么这么定、否决过什么见
  〈实际路径〉」——读取端只有这一根线，没有它文件写了也没人翻。
- **门限**：不记的话，下一个不知情的会话会不会把被否方案再提一遍？会才记。写不出「否〈选项〉」的不
  够格；只有一个方案的点头确认、措辞/命名/粒度类单点可改的、代码注释与 commit 正文已承载的实现细节，
  都不记。
- **每节**（标题 `## YYYY-MM-DD 主题`，日期是拍板日 UTC+8）：
  1. `状态：现行` 或 `状态：已被〈日期 主题〉取代`——全文唯一可改的行；推翻旧决定就追一节新的，再回来
     改旧节这一行。
  2. 一句 Y-statement：在〈场景〉下，面对〈顾虑〉，选〈方案〉、否〈选项〉，以达〈目标〉，接受〈代价〉。
  3. 否决理由：若干条，有就写——这是防重议的弹药，Y-statement 装不下的细节放这里。
  4. 出处：卡号 / commit / 会话归档文件名。
- 不写：卡片状态、交付流水、实现细节（git log 与看板已有）。

**形态**——同一套写法，两种落盘方式；动笔前先看这个项目已经是哪种，照它写，不要在一个项目里混用：

- **单文件**（默认）：全部节按时间顺序追加在 `docs/decisions.md` 里。
- **一决策一文件**：事实源是 `docs/decisions/` 目录，一个文件放一节，文件名
  `<12 位时间戳>-<英文 slug>.md`（时间戳取动手写的当下，slug 用小写字母、数字和连字符，见 §1）；
  写决策 = 新建一个文件，**不往任何共享文件里追加**。通读靠脚本聚合出的时间线视图（如 todo_hub 的
  `docs/decisions_timeline.md`）：只读、不进 git、不可手工编辑，改了下次生成即被覆盖——事实源永远是
  `docs/decisions/` 下的子文件。此形态下的 `docs/decisions.md` 若存在，只是「怎么写、写到哪」的说明
  页，不放决策正文。
- **判形态**：有 `docs/decisions/` 目录就是一决策一文件；只有 `docs/decisions.md` 就是单文件；都没有
  就当场新建单文件。
- **什么时候升级到一决策一文件**：判据是这个仓有没有**多会话并发写**（开了自动派发、或经常并行开
  worktree），不是决策条数多少。单文件是共享文件，每张卡都往同一个结尾追加，冲突概率不由改动重叠面
  决定，而是随并发卡数趋近 1（todo_hub 在 TODOHUB-87/78/92/97 各实撞一次，每次都卡住发布流程）；
  拆开后各分支写各的新文件，没有共同锚点，冲突归零。单人串行的仓不必拆，单文件更省事。升级是一次性
  改造：已有各节切成子文件、`docs/decisions.md` 改写成说明页、规则文件里的指针改到目录、补一个聚合
  脚本，代价是通读要靠生成产物。本仓（claude_skills）也开了自动派发但仍是单文件：真撞上冲突再升级，
  不预先改造，也不要把这条当成待办去「修」。

样本：单文件见本仓 `docs/decisions.md`；一决策一文件见 `~/Projects/todo_hub/docs/decisions/`（写法说明
与聚合视图的约定在 `~/Projects/todo_hub/docs/decisions.md`）。

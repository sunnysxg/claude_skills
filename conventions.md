# conventions — 命名与路径规范

适用范围：本 repo 所有 skill，以及 agent 在 `~/_sxg/` 下读写的一切文件。
**不适用**：人写的笔记（Obsidian vault 等）——那边维持个人习惯，本规范不管。

## 1. 大小写与分词

- 一律**全小写 snake_case**：目录、文件、frontmatter 字段、slug。
  例：`llm_session_log/`、`qa_log.md`、`project_path`
- 缩写也小写：`llm` 不写 `LLM`。
- **唯一例外**：skill 名（= slash command 名）用 kebab-case——Claude Code 平台要求，
  name 字段只允许小写字母、数字、连字符。例：`session-log`、`mmd-explain`。
  平台与通行固定名照抄，不套本规范：`SKILL.md`、`CLAUDE.md`、`README.md`、`LICENSE`。
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

## 13. 项目决策记录 `docs/decisions.md`

每个项目一份、git 跟踪、只追加的决策日志（本仓库自己的在 `docs/decisions.md`）。用途只有一个：
**防重议**——让下一个不知情的会话不把被否的方案再提一遍。规则文件（CLAUDE.md / AGENTS.md）只放
规则和操作事实，「为什么这么定、否决过什么」写这里；「Sarah 某日拍」不进规则文件——写进规则文件
即已拍，拍板日期与过程归这里。

- **写入触发**：决策包拍板、grilling 定稿。
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

样本：`~/Projects/todo_hub/docs/decisions.md`。

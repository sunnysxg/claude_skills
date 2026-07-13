# conventions — 命名与路径规范

适用范围：本 repo 所有 skill，以及 agent 在 `~/_sxg/` 下读写的一切文件。
**不适用**：人写的笔记（Obsidian vault 等）——那边维持个人习惯，本规范不管。

## 1. 大小写与分词

- 一律**全小写 snake_case**：目录、文件、frontmatter 字段、slug。
  例：`llm_session_log/`、`qa_log.md`、`project_path`
- 缩写也小写：`llm` 不写 `LLM`。
- **唯一例外**：skill 名（= slash command 名）用 kebab-case——Claude Code 平台要求，
  name 字段只允许小写字母、数字、连字符。例：`session-log`、`mmd-explain`。
  平台固定名照抄，不套本规范：`SKILL.md`、`CLAUDE.md`、`README.md`、`LICENSE`。
- **废弃别名**：改名后可用符号链接保留旧目录名（如 `mmdexplain` → `mmd-explain`），
  仅供旧 slash 命令兼容；仓库内只维护 canonical 目录的内容，别名不单独写 `SKILL.md`。

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
- 设了 `disable-model-invocation: true` 的 skill，description 只描述功能——
  模型永远不会自动触发它，写触发条件是废文。

## 10. 存量数据兼容

规范生效（2026-07）前写入的文件**不强制改名**：旧格式 session log 文件名
（`[{project}]{YYMMDDHHMM}_{slug}.md`）、个别项目根的 `HANDOFF.md`。
skill 读取时兼容两代命名，新写入一律用新规范。
目录名例外：集群上 `LLM_session_log/` → `llm_session_log/`、`INDEX.md` → `index.md`
需要改名一次（Linux 大小写敏感，skill 按新名寻址），目录内文件不动。

## 11. 本仓库（claude_skills）的 commit 模块名

- 模块 = **skill 目录名**（kebab-case），如 `[session-log]`、`[git-workflow]`。
- 改 `global/` 下跨 skill 规则时用 `[global]`；改 `conventions.md`、`.gitignore` 等仓库级用 `[Repo]` 或 `[global]`。
- 完整格式与工作流见 `global/GIT.md`。

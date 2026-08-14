# conventions — 命名与路径规范

适用范围：本 repo 所有 skill，以及 agent 在 `~/_sxg/` 下读写的一切文件。
**不适用**：人写的笔记（Obsidian vault 等）——那边维持个人习惯，本规范不管。

## 1. 大小写与分词

- 一律**全小写 snake_case**：目录、文件、frontmatter 字段、slug。
  例：`llm_session_log/`、`qa_log.md`、`project_path`
- 缩写也小写：`llm` 不写 `LLM`。
- **唯一例外**：skill 名（= slash command 名）用 kebab-case——Claude Code 平台要求，
  name 字段只允许小写字母、数字、连字符。例：`session-log`、`mmd-explain`。
  平台与通行固定名照抄，不套本规范：`SKILL.md`、`CLAUDE.md`、`README.md`、`LICENSE`、
  项目待办 `TODO.md`（见第 12 节）。
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
├── handoff/
│   └── {project}.md                      # 每项目一份，pickup 按项目名找
└── todo_hub/
    └── panel.html                        # todo-hub 生成的面板（可再生视图，丢了重扫）
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

## 12. 项目 TODO（`_sxg/TODO.md`）格式

todo-hub 面板靠纯脚本扫描，条目行必须机器可读；条目行之外保持自由。

- 条目语法（脚本只认这三种形态，todo-hub skill 与之同步）：
  - `- [ ] 内容` 未完成；`- [x] 内容` 已完成
  - 高优先：checkbox 后加 `!`，即 `- [ ] ! 内容`（含义：优先处理/等 Sarah 拍板）
  - 缩进的行归属上一条目（续行），随条目一起展示
- 其余一切自由：节名（`## ...`）自由、仅作分组展示；标题、日期、说明段落、
  普通 `- ` 笔记行（不带 checkbox）都合法且不被解析。
- 防漂移兜底：**长得像 checkbox 但不合语法**的行（如 `- []`、`-[ ]`、`* [ ]`）
  计入「未识别」，面板上显示计数——格式坏了在面板上看得见，不靠自觉。
- **跨项目条目信箱直投**：在项目 A 发现项目 B 该做的事，直接写进 B 的
  `_sxg/TODO.md`（来龙去脉顺手写进正文即可，无专用语法）；目标在别的机器上
  或一时不知在哪时，降级为自然语言记在自己项目的 TODO 里，面板照常展示、
  人工转投。改共享组件（如某个 skill）前，先读它所在项目的 TODO。

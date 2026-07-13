# 全局规则（跨项目通用）

所有机器、所有 agent（Claude Code / Cursor 等）通用。项目内若有更具体的 `CLAUDE.md`，
以项目内为准，两者一并生效。机器特有内容（conda 环境、内网服务等）不写在这里，
写在各机器 `~/.claude/CLAUDE.md` 的本机段落里。

## 语言与沟通

- **始终用简体中文**回复用户。
- 写得像高质量技术文：准确、结构清晰、完整句子；回复篇幅与任务复杂度相称；
  优先 plain language 解释改了什么、为什么，少堆术语。
- 少用 bold 和 backtick 做装饰；面向用户的文本避免「§」。
- 结尾不要套路式「say the word and I'll…」；有明确后续再问，没有就不硬塞。
- 引用已有代码用 code citation 块（`startLine:endLine:filepath`）；opening fence 单独一行，
  不要前缀列表符。
- 引用路径、URL 用完整 markdown 链接，不省略前缀或中间段。
- fenced code block 与 inline backtick 内按字面显示，不用 HTML 实体代替符号。
- 复杂逻辑可用 mermaid（`/mmd-explain`）或 ascii 图说明；简单改动不必强行画图。

## 编码

1. **最小改动** — 用最简单正确的 diff；无关代码不动；问答/审查类任务尤其克制。
2. **避免过度工程** — 不为一两行逻辑抽 helper；不为极不可能的边界堆 error handling。
3. **匹配现有惯例** — 先读周边代码，对齐命名、类型、抽象、import、注释粒度；
   无惯例时再跟语言/框架最佳实践。
4. **注释** — 代码应自解释；只注释非显而易见的业务逻辑或深层技术细节。
5. **测试** — 仅用户要求或能覆盖真实行为时再加；不要 trivial assert。
6. **长任务加进度条** — 分钟级以上的批处理循环必须有进度反馈
   （tqdm 或逐项带序号/用时的日志行），防止无法判断是否卡死；
   结束时打各阶段用时汇总。

## Git

版本控制（工作流、commit 格式、push/PR、安全红线）见同目录
[`GIT.md`](GIT.md)——**新 session 必读**（`read-context` 已列入）。

## 格式化

### 数学公式

**直接回复用户**（IDE 聊天窗口阅读）时，用 LaTeX 原生分隔符：
`\(...\)`（行内）、`\[...\]`（独立/多行）。不用 `$` 或 `$$`。

**用户明确要求提供 Markdown 文件/片段**（写入 `.md`、README、文档等）时，
改用 `$...$`（行内）与 `$$...$$`（独立/多行），以便在 GitHub、Jupyter 等
Markdown 渲染器里正常显示。

### 图表文字

生成图片/图表时，标题、标签、图例等**所有图内文字用英文**（matplotlib / seaborn
默认无中文字体，易乱码）。Jupyter 的 Markdown 和代码注释可用中文，图内文字仍须英文。

时间轴：x 轴为时间时先确认 dtype（`YYYYMMDDHHMM`、`YYYYMMDD` 或 `datetime64`），
转 `datetime` 再画，勿把 int、Unix 秒或字符串原样当横坐标：

```python
# ❌ ax.plot(df["di"], y)
# ✅ ax.plot(pd.to_datetime(df["di"].astype(str).str.zfill(12), format="%Y%m%d%H%M"), y)
```

## Agent skills 与归档

- Skills 仓库：`~/.claude/skills`（`git@github.com:sunnysxg/claude_skills.git`）
- 命名与路径规范：`~/.claude/skills/conventions.md`——agent 写文件时遵循：
  全小写 snake_case、纯 ASCII 路径（中文进内容不进路径）、时间戳 12 位 `YYYYMMDDHHMM`、
  跨项目路径用 `~` 开头不用绝对路径。
- 全局归档根：`~/_sxg/`（每台机器各一份，不跨机共享）
  - `llm_session_log/` — session 摘要归档（`/session-log` 写入，`/session-search` 检索），
    索引在 `index.md`
  - `handoff/{project}.md` — 项目交接文档（`/handoff`、`/pickup`；个别老项目仍用项目根
    `HANDOFF.md`）
- 项目内 `_sxg/`：`TODO.md`、`qa_log.md`（`/lq`）、`diagram/`（`/mmd-explain`）等

---
name: mmd-explain
description: >
  用 Mermaid 流程图/时序图直观解释项目结构、数据流、流程或概念，输出 .mmd 源文件并渲染为
  PNG，放到项目的 _sxg/diagram/ 目录。用户要求画图解释、问某个东西怎么工作、或问题本身
  适合用图示回答时使用（即使用户没有明确说"画图"）。
---

## 使用方式

用户提问时可以：

- 直接问（"`/mmd-explain` pipeline 是怎么跑的？"）
- 指定输出目录（"`/mmd-explain` ... 放到 docs/diagrams/"）

> 旧名 `/mmdexplain` 在执行客户端同步后仍可用；兼容链接由 `skills.manifest.json` 的
> alias 生成。请优先用 `mmd-explain`。

默认输出目录：**`_sxg/diagram/`**（相对于当前项目根）。

---

## 执行步骤

### 1. 理解问题，读取必要上下文

先判断这个问题最适合哪种图类型，然后只读必要的代码/文档来回答：

| 问题类型 | 推荐图类型 |
|---|---|
| 数据流、处理流程 | `flowchart TB` / `flowchart LR` |
| 模块依赖、架构 | `flowchart TB` with subgraph |
| 时序、调用关系 | `sequenceDiagram` |
| 状态机 | `stateDiagram-v2` |
| 时间线 | `timeline` |

### 2. 写 .mmd 文件

文件名：`{YYYYMMDD}_{topic_slug}.mmd`（全小写 snake_case、纯 ASCII），如
`20260617_pipeline_flow.mmd`。图内标注用中文——中文进内容，不进文件名。

**样式模板**（始终在开头加 init 配置）：

```
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryBorderColor': '#4a90d9', 'lineColor': '#555', 'fontSize': '18px'}}}%%
```

图示原则：

- 用中文标注，节点内容简洁（10字以内/行）
- 用 subgraph 分组展示层次
- 用颜色区分状态：绿 `#d4edda` = 完成/正常，黄 `#fff3cd` = 进行中，红 `#ffeaea` = 问题/警告，蓝 `#e8f4fd` = 中性
- 关键节点加符号：✅ ⏳ ⚠️ 🔵 等彩色 emoji；序号用 **①②③**（不用 1️⃣2️⃣3️⃣——keycap 在 headless 渲染里常变方框）
- init 里 `fontSize` 建议 **16px～18px**（默认模板 13px 在大图上仍偏小）
- 在图里直接回答问题，不要只画结构而不带解释

### 3. 渲染为 PNG

**硬规则：一律走 `scripts/render.sh`**，禁止裸调 `mmdc` / `npx`（会跳过 fonts.css、scale、字体预检）。

```bash
~/.claude/skills/mmd-explain/scripts/render.sh -i {in}.mmd -o {out}.png
# 默认 -w 2400 -H 2400 -s 2（viewport；-s 为像素倍率）
# 竖向深图（flowchart TB 多层）若裁切：加大 -H 3200~4800
# 简单图嫌大：-s 1；仍嫌小：-w 2800 -s 3
```

`-w/-H` = puppeteer **视口**（不是最终 PNG 固定边长）；`-s` = deviceScaleFactor。旧默认 1200×900@1x 易出「图很小看不清」。

Cursor 与 Claude 共指同一 skill 目录（`~/.cursor/skills/mmd-explain` → symlink），改一份即可。

#### 本机字体（cpfs 已踩过的坑）

Headless Chromium **不会**随便用系统中文字体。约定：

| 字体 | 用途 | 放置 |
|------|------|------|
| **Noto Sans CJK SC** | 中文 | `install_cjk_font.sh` → user + conda `mermaid/fonts/` |
| **Noto Color Emoji** | emoji | `install_emoji_font.sh` → 同上 |

```bash
~/.claude/skills/mmd-explain/scripts/install_cjk_font.sh    # 互链已有字体，不强制 CDN
~/.claude/skills/mmd-explain/scripts/install_emoji_font.sh

# 验收（两套 fontconfig 都要过）：
fc-list | grep -i 'Noto Sans CJK SC'
FONTCONFIG_FILE=~/.conda/envs/mermaid/etc/fonts/fonts.conf fc-list | grep -i 'Noto Sans CJK SC'
fc-list | grep -i 'Noto Color Emoji'
```

`render.sh` 缺字会 WARN 但仍可能 exit 0——**渲染后必须 Read PNG**，中文/emoji 方框则补字体重渲，不得当成功交差。

脚本探测顺序：conda `mermaid` → PATH `mmdc` → `npx`；都没有则只留 .mmd。

PNG 与 .mmd 同名，后缀 `.png`。

### 4. 回复用户

- 说明图示回答了什么
- 告知文件路径（.mmd 和 .png）
- 用一段文字补充图示中不直观的部分（可选）
- 若用户反馈「图很小 / 缺字」：先确认是否用了本脚本默认 `-s 2`，再查上面字体表；**不要**只用系统 `mmdc` 裸跑（会跳过 fonts.css / scale）

---

## 失败处理

如果 mmdc 报错：

1. 先检查 .mmd 语法（Mermaid 语法对缩进/引号敏感）
2. 节点 label 里的特殊字符（括号、斜杠）用引号包裹：`["label with (parens)"]`
3. 如果渲染仍失败，把 .mmd 源码展示给用户，说明需要手动渲染
4. 中文方框 / emoji 方框：按上文「本机字体」补齐后重渲，勿改图内容硬凑英文

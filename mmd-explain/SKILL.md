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

先识别当前操作系统，然后只读取并执行对应平台分支：

- Windows：读取 [references/windows.md](references/windows.md)，使用 `doctor.ps1` 与
  `render.ps1`。
- Linux：读取 [references/linux.md](references/linux.md)，使用 `doctor.sh` 与
  `render.sh`。
- 其他平台：不要猜测兼容性；保留 `.mmd`，并说明当前没有已验证 renderer。

不要读取或执行另一个平台的安装步骤。首次使用、renderer 变化或渲染失败时先运行当前平台
的 doctor。禁止裸调 `mmdc` / `npx`，否则会跳过公共字体 CSS、分辨率和环境探测。

两个 renderer 共享默认值：视口 2400×2400、scale 2、白色背景。竖向深图若裁切，加大高度
到 3200～4800；简单图嫌大可改 scale 1。

渲染后必须查看 PNG。进程退出 0 不代表中文和 emoji 一定没有方框。

PNG 与 .mmd 同名，后缀 `.png`。

### 4. 回复用户

- 说明图示回答了什么
- 告知文件路径（.mmd 和 .png）
- 用一段文字补充图示中不直观的部分（可选）
- 若用户反馈「图很小 / 缺字」：先确认是否用了平台 renderer 的默认 scale 2，再按平台
  reference 检查字体。

---

## 失败处理

如果 mmdc 报错：

1. 先检查 .mmd 语法（Mermaid 语法对缩进/引号敏感）
2. 节点 label 里的特殊字符（括号、斜杠）用引号包裹：`["label with (parens)"]`
3. 如果渲染仍失败，把 .mmd 源码展示给用户，说明需要手动渲染
4. 中文方框 / emoji 方框：按当前平台 reference 补齐字体后重渲，勿改图内容硬凑英文

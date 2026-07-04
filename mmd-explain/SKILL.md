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
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryBorderColor': '#4a90d9', 'lineColor': '#555', 'fontSize': '13px'}}}%%
```

图示原则：

- 用中文标注，节点内容简洁（10字以内/行）
- 用 subgraph 分组展示层次
- 用颜色区分状态：绿 `#d4edda` = 完成/正常，黄 `#fff3cd` = 进行中，红 `#ffeaea` = 问题/警告，蓝 `#e8f4fd` = 中性
- 关键节点加 emoji（✅ ⏳ ⚠️ 🔵 等）
- 在图里直接回答问题，不要只画结构而不带解释

### 3. 渲染为 PNG

按当前机器可用的方式**依次探测**，用第一个可用的：

1. **PATH 里有 `mmdc`**：

   ```bash
   mmdc -i {in}.mmd -o {out}.png -w 1200 -H 900
   ```

2. **有 node/npm 但无 mmdc**（如 Windows 机器）：

   ```bash
   npx -y @mermaid-js/mermaid-cli -i {in}.mmd -o {out}.png -w 1200 -H 900
   ```

   （首次运行会下载依赖，之后走缓存）

3. **cpfs 集群**（mmdc 装在 conda env `mermaid` 里）：

   ```bash
   conda run -n mermaid bash -c \
     'LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH "$CONDA_PREFIX/bin/mmdc" \
     -i {in}.mmd -o {out}.png -w 1200 -H 900'
   ```

4. **都不可用**：保存 .mmd 源文件并告知路径，同时在回复里直接贴 ```mermaid 代码块
   （多数 chat 界面能直接渲染），说明本机没有渲染环境、装 node 后可用方式 2。

PNG 文件名与 .mmd 同名，后缀改 `.png`。

### 4. 回复用户

- 说明图示回答了什么
- 告知文件路径（.mmd 和 .png）
- 用一段文字补充图示中不直观的部分（可选）

---

## 失败处理

如果 mmdc 报错：

1. 先检查 .mmd 语法（Mermaid 语法对缩进/引号敏感）
2. 节点 label 里的特殊字符（括号、斜杠）用引号包裹：`["label with (parens)"]`
3. 如果渲染仍失败，把 .mmd 源码展示给用户，说明需要手动渲染

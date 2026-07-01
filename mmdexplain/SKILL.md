---
name: mmdexplain
description: 用 Mermaid 流程图/时序图直观解释项目结构、数据流、流程或概念。当用户问"xxx是怎么工作的"、"帮我画个图解释"、"xxx的流程是什么"、"用图示说明"等问题时使用。输出 .mmd 源文件并渲染为 PNG，放到项目的 _sxg/图示回答/ 目录。即使用户没有明确说"画图"，只要问题适合用图示回答就应该触发。
---

## 使用方式

用户提问时可以：
- 直接问（"`/mmdexplain` pipeline 是怎么跑的？"）
- 指定输出目录（"`/mmdexplain` ... 放到 docs/diagrams/"）

默认输出目录：**`_sxg/图示回答/`**（相对于当前工作目录）。

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

文件名规则：`{简短主题}_{MMDD}.mmd`，例如 `pipeline流程_0617.mmd`。

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

```bash
mkdir -p {输出目录}
conda run -n mermaid bash -c \
  'LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH /nfshome/xgsun/.conda/envs/mermaid/bin/mmdc \
  -i {mmd文件路径} -o {svg文件路径} -w 1200 -H 900'
```

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

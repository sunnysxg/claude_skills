# 图片正文的脚本调用

正常只调用 `article_ingest.py ingest <URL> --fetch … --gate …`。脚本按原站顺序下载图片，
逐页调用已登录的 Codex 命令行客户端（CLI），保存文字，再生成 `_raw` 原文与 REF 索引骨架并写库。
`written` 才表示两份笔记已写入；`exists` 表示同帖已归档。无需 agent 在正常路径逐页开图和串命令。

## 接线

Python 仍只依赖标准库；图片路径另依赖支持图片和结构化输出的 Codex CLI，以及可用的登录、模型与额度。
模型继承该机器现有客户端配置；不是离线识字，也不新增独立 OCR 服务或 API 密钥。
Windows / Linux 的客户端发现方式见对应平台分支。可用 `ARTICLE_INGEST_CODEX` 指定可执行文件完整路径，
值是一个路径，不是 shell 命令或带参数的字符串。缺客户端报 `transcriber_missing`，文字路径不受影响。

实际调用采用 `codex exec --image … --output-schema … --output-last-message …`，
输出固定为 `text`（Markdown）与 `unreadable`（是否无法辨认），不从混合终端日志提取正文。
参见 [官方非交互调用说明](https://learn.chatgpt.com/docs/non-interactive-mode) 与
[官方 CLI 参数](https://learn.chatgpt.com/docs/cli/reference)。

## 本地留存与续做

- `source.json`：原站身份、图片顺序与来源；`images/NNN.img`：下载图片。
- `pages/NNN.md`：逐页正文；每页完成后原子落盘，下一页失败不会丢失前页。
- `transcription/NNN.json` 与 `.log`：最近一次模型结果与调用诊断，只在本机保存，不写入笔记库或 Git。
- `raw.md`、`ref.md`、`meta.json`：合稿与目标路径。

`resume <work_dir> --gate …` 不重新查重或取网页：已有草稿则按原字节重试写库，
否则只补未下载图片与缺失/空白转写，再合稿写库。模型逐页串行调用，每 30 秒报告等待用时，
每页最多等 600 秒，结束报告总耗时；不会无限重试。模型拒绝、额度不足、输出无效或不可辨认时
报 `transcription_failed`、具体页码及目录，agent 此时再查诊断、换原站清晰版本或手动修复后续做。
修好某页后如需重新合稿，显式调用 `assemble`；已有 `meta.json` 时 `resume` 保留草稿，
避免原文已写入后重新生成时间字段导致同路径内容冲突。

`ingest … --draft-only` / `resume … --draft-only` 执行到草稿，不写库；
`fetch` 仅取源，`ingest --manual-transcription` 才显式暂停给人工转写。

## 正确性边界

提示要求忠实转写、复核数字公式与图表，无法辨认不猜字。缺页、空输出或模型明确报不可辨认时停止，
不拿标题说明当图片正文，不写半篇。模型自检与结构校验不能证明零误差；按 Sarah 的取舍，不再要求
每篇由 agent 人工逐字审查，以阅读反馈推动修复。图片长期留调用机器的独立归档目录，不接 iCloud。

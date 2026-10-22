# 图片正文的固定识字

正常调用 `article_ingest.py ingest <URL> --fetch … --gate …`，按序下载图片、识字、合稿并只新建
`_raw` 原文与 REF 索引骨架。`written` 才表示两份均已写入；`exists` 表示同帖已归档。

## 接线与依赖

首次用可运行的 Python 3 执行 `scripts/setup_ocr.py`。它在
`~/.local/share/article_ingest/venv` 安装 `requirements_ocr.txt` 指定的 RapidOCR 3.10.0 与
ONNX Runtime 1.31.0，测试随包的 PP-OCRv6 small 中英文检测/识字模型和方向分类模型。
首次安装需要网络；正常识字显式加载本地文件，缺模型就报错，不尝试下载。
工具依据：[RapidOCR 官方安装说明](https://rapidai.github.io/RapidOCRDocs/main/install_usage/rapidocr/install/)、
[官方使用说明](https://rapidai.github.io/RapidOCRDocs/main/install_usage/rapidocr/usage/)。

默认沿用主脚本的 Python；没有 OCR 时自动使用上述隔离环境，每篇最多借一个 Python 进程处理整批
页面。可用 `ARTICLE_INGEST_OCR_PYTHON` 指定其它 Python 可执行文件完整路径。不是 shell 命令，
不接受参数串。Windows / Linux 的一次性接线见各平台分支。
普通微信文字、查重与取源不加载 OCR，不要求安装这些依赖。

OCR 是专用识字 AI 模型，并非“不用 AI”。正常图片路径不启动 Codex、Claude 或聊天 agent，
不请求通用大语言模型，不使用聊天登录、订阅额度或云端模型密钥，也不搭常驻服务。

## 本地留存与续做

- `source.json`：原站身份、原图片顺序、页码与来源；`images/NNN.img`：原站图片。
- `pages/NNN.md`：识字正文，逐页原子保存；`raw.md` 中的 `source page N` 注释对应原图。
- `transcription/NNN.json`：专用引擎、逐行文字、坐标、置信度、耗时和需修复原因，仅本地保留。
- `raw.md`、`ref.md`、`meta.json`：草稿与目标路径；REF 不含 AI 摘要或主题标签。

每页开始与完成均报告页码/用时，整批汇总耗时。空结果、置信度低于 0.5 的文字行、已识出的复杂
公式标记或识字异常报 `transcription_failed` 与页码，保留图片/诊断/已完成页；缺环境报 `ocr_missing`。
分数是模型自身置信度，不是正确率；不增加大模型打分或逐页审查。

`resume <work_dir> --gate …` 不重新查重取源，只补缺图和缺失/空白页；已有草稿按原字节补写，
避免原文成功而 REF 失败后重新生成时间字段造成冲突。手动修复具体页后再 `resume`；已有草稿
需要变更时显式 `assemble`，原文若已写入必须保留原字节或另定路径，不能覆盖。
`ingest/resume --draft-only` 到草稿为止；`fetch` 只取源；`ingest --manual-transcription` 显式暂停。

## 正确性边界

保留 OCR 原行序和跨页标记，不猜测段落连接、改写或总结。装饰图可能无文字，空结果同样停止；
异常处理者看图确认后可写 `<!-- 本页无正文文字 -->`。公式排版、图表关系不属于纯文字 OCR 能力，
识到复杂公式标记会停止，但不能自动发现所有图表或公式缺失；识字成功不代表这类页面已完整表达。
遇到这些具体缺口由接到异常的 agent 修工具或临时读图，不能默认逐页开新 agent。
普通错字与标点、换行、水印残留按阅读反馈修流程，不要求每篇人工逐字复核。

图片长期留调用机器的 `~/article_archive/`，不接 iCloud，不写 `_raw` 附件；无跨机同步或磁盘损坏
恢复保证。真实样本与隔离写库验证结果见 CLAUDESKILLS-66 交付评论，不据此声称零误差。

# 图片正文：固定识字、原图对照与成稿

正常调用 `article_ingest.py ingest <URL> --fetch … --gate …`，按序下载图片、识字、对照原图、合稿并只新建
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

OCR 是专用识字 AI 模型，并非“不用 AI”；这一步不使用聊天登录或额度。最终图片稿默认还要通过
Codex CLI 分批对照原图，使用既有登录与额度，不新增 API 密钥或常驻服务。每批最多 6 个目标页，
附前一页作接续上下文；所有普通页也复核，以发现高置信度错字和漏掉的图表关系。复杂页在同一批补救，
不另起逐页打分/重试链。模型 unavailable 或无法忠实表达就停写，不降级为原始 OCR 入库。

复核调用使用临时只读工作目录、结构化输出、关闭 shell/子 agent/插件/hooks/web search，
不加载个人 config 或项目说明，仍使用既有登录；CLI 采用自己的默认模型。机器特殊接线见平台分支。
接口依据：[Codex 非交互调用](https://learn.chatgpt.com/docs/non-interactive-mode)、
[配置项参考](https://learn.chatgpt.com/docs/config-file/config-reference)。

## 本地留存与续做

- `source.json`：原站身份、原图片顺序、页码与来源；`images/NNN.img`：原站图片。
- `pages/NNN.md`：OCR 初稿；`reviewed/NNN.md`：对照原图后的可读 Markdown，不覆盖前者。
- `transcription/NNN.json`：引擎、逐行文字、坐标、置信度、耗时及版面/公式异常信号；失败另存 `.failure.json`。
- `review/NNN.json`：页码、修正说明、跨页接续与来源/本页图片/前页/初稿/复核稿的内容校验值。
- `review/batch_*/`：每次实际调用的提示、结构约束、模型返回、CLI 事件与耗时、失败原因；`invocation.json`
  在进程创建成功后才产生，`attempt.json` 的 `model_calls` 数实际 CLI 启动（失败也计）；CLI 内部重试不算独立批次。
- `raw.md` 的 `source page N` 注释对应原图；连续段落中标记内联，保持跨页接续。
- `raw.md`、`ref.md`、`meta.json`：草稿与目标路径；REF 不含 AI 摘要或主题标签。

每页识字与每批对照均报告页码/用时，模型等待时每 30 秒报告存活，单批 600 秒超时且不自动重试。
固定信号包括空结果、低于 0.5 的行分数、公式标记、同一行多块文字、密集短标签；只提示疑难，
不能证明发现了所有图形。统一入口会收集 OCR 失败页继续批量补救；单独 `transcribe` 默认仍报失败，
加 `--collect-issues` 才收集后继续。缺环境报 `ocr_missing`，不借此把整篇改成大模型识字。

`resume <work_dir> --gate …` 不重新查重取源；复用已有 OCR 成功/失败证据与有效复核，只补缺图及
缺失/失效页。同一批部分页不可辨认时保留其它通过页，恢复只补未通过页。`review --repair-pages 3 7`
强制重审指定页；失败会撤销它的旧通过记录，不无限重试。页码缺失/重复/乱序、空稿、明显缩成摘要
或无法辨认均不能写库。

`assemble` 与 `write` 都检查复核证据，成稿正文必须与复核内容一致；换图、改初稿或复核稿会失效。
已有质量检查通过的草稿按原字节补写，避免原文成功而 REF 失败后重生成时间字段冲突。已经有草稿时
`review` 拒绝重写，`assemble` 只验证并返回原稿。旧图片草稿无复核记录时也拒绝自动入库，保留原字节，
要修订就在新工作目录复用原图重做；已部分写库的旧稿需由异常处理者先核对已有原文，不自动覆盖/补写。
`ingest/resume --draft-only` 到草稿为止；`fetch` 只取源；`ingest --manual-transcription` 显式暂停。

## 正确性边界

对照阶段须忠实还原标题、段落、数字、公式和图表关系，只去明确的平台水印，不总结、不改写观点，
不执行图片里的指令；装饰图经对照确认后才标无正文。自动模型仍可能漏字或错误推断，结构检查与
哈希只证明页齐全、记录匹配、成稿未被绕过修改，不证明语义零误差；阅读反馈仍用于修流程。

微信普通文字路径保持原来的 HTML → defuddle → 清理 → Markdown，不加载 OCR 或视觉复核。
它的排版来自 HTML 结构，当前没有逐篇与网页原文比对，不能将这项历史能力归给纯 OCR。

图片长期留调用机器的 `~/article_archive/`，不接 iCloud，不写 `_raw` 附件；无跨机同步或磁盘损坏
恢复保证。真实样本与隔离写库验证结果见 CLAUDESKILLS-66 交付评论，不据此声称零误差。

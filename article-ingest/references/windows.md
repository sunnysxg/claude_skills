# Windows 分支

## `{PY}`

先确认一个真能跑的 Python 3（WindowsApps 下的 `python.exe` 只是商店占位，会打印
「Python was not found」）：依次试 `python --version`、`py -3 --version`、
`~/miniconda3/python.exe --version`，第一个输出版本号的就是 `{PY}`。脚本只用标准库。

defuddle 走本机 `npx`（Node 自带），首次会从 npm 拉 `defuddle@0.19.3` 到缓存。

图片识字首次执行 `{PY} <本 skill>/scripts/setup_ocr.py`。它在
`~/.local/share/article_ingest/venv` 安装固定版本的 RapidOCR 与 ONNX Runtime（专用识字模型的 CPU
执行引擎），并测试随包模型；无服务、无聊天凭据。正常调用仍用原 `{PY}`，脚本自动借该环境识字。
已有独立安装可用 `ARTICLE_INGEST_OCR_PYTHON` 指定 Python 可执行文件完整路径（不是命令字符串）。
正常识字只读本机模型；缺模型报错，不运行时下载。详细依赖与质量边界见 [transcription.md](transcription.md)。

图片成稿还需已登录的 Codex CLI：优先找 PATH 中的 `codex`，否则用 `Get-AppxPackage OpenAI.Codex`
探测桌面包内可执行文件；可用 `ARTICLE_INGEST_CODEX` 指定完整绝对路径，不接受带参数的命令串。
复核使用 CLI 默认模型及现有登录；网络、登录或额度不可用就保留草稿报错，不自动跳过质量检查。

## `{WIRING}`

**Windows 机器本机不抓国内站**：`--fetch local` 在 Windows 上直接被脚本拒绝（退出码 3），出网一律
经 ssh 借别的机器。接线写 ssh config 里的 alias，本机（SeraCC）是：

```text
--fetch ssh:lightsail,ssh:sera --gate ssh:lightsail
```

- `ssh:lightsail`（Linux）：脚本把自己拷到对方 `~/.cache/article_ingest/` 再在那边跑抓取 +
  分类 + defuddle，只回传 Markdown 或小红书笔记元数据与图片清单。必须这样：SeraCC 到 Lightsail 的链路实测只有约 10 KB/s，
  一个公众号页面有 3.5 MB，回传原始 HTML 会超时（2026-09-16 实测）。
- `ssh:sera`（Windows，cmd.exe）：远端跑自带的 `curl.exe`，HTML 走局域网回传，本机转换。它是
  第二条出网——Lightsail 撞验证页时换一个 IP 再试。
- `--gate ssh:lightsail`：gate 客户端和它的密钥只在 Lightsail 上（`from=` 限源），查库和写库都经
  那边转。查库索引缓存也在 Lightsail 的 `~/.cache/article_ingest/vault_url_index.json`：第一次
  要把 `_raw/` 与 `Clippings/` 每篇读一遍（60 篇约 5 分钟，逐条打进度），之后只读新增的。
  支持小红书笔记 ID 后，旧版索引首次使用会自动重建一次，以读取已有笔记的 `source_note_id`。

别的 Windows 机器按自己的 ssh alias 填；也可以设 `ARTICLE_INGEST_FETCH` /
`ARTICLE_INGEST_GATE` 环境变量代替参数。

## 坑

- 草稿和图片默认在调用机器的 `~/article_archive/`，不是缓存，不自动清理；可用
  `ARTICLE_INGEST_WORK_ROOT` 或单篇 `--work` 覆盖。从 SeraCC / sera 调用即可留在其本地磁盘，
  不需要接入 iCloud 或修改 gate。不要把根目录设到 Git 树或 iCloud 中。
- 命令里的 URL 用双引号包住（长链里有 `&`）。
- `images` 默认沿取页成功的出网传回图片字节；Lightsail 传图慢时可用 `--fetch ssh:sera`。
  正常入口 `ingest` 对应的参数是 `--image-fetch ssh:sera`，网页仍可先走 Lightsail。

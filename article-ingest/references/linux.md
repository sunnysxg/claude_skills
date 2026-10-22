# Linux 分支

## `{PY}`

`python3`（标准库即可）。defuddle 走 `npx`：PATH 里没有时脚本会自己找
`~/.nvm/versions/node/*/bin/npx`（Lightsail 的 Node 装在 nvm 下，非交互 shell 的 PATH 里没有）。

图片识字首次执行 `python3 <本 skill>/scripts/setup_ocr.py`（系统须支持 `venv` 和 pip）。
固定依赖装到 `~/.local/share/article_ingest/venv`，正常调用自动借该环境识字；可用
`ARTICLE_INGEST_OCR_PYTHON` 指定其它具备固定版本依赖的 Python 完整路径。
只取源或处理微信文字的机器不需要 OCR；若要求图片留在 SeraCC / sera，应从那台机器调用。
本地识字不需要聊天登录、API 密钥或常驻服务；缺随包模型报错，不运行时下载。
详细依赖与质量边界见 [transcription.md](transcription.md)。

图片成稿还需 PATH 中已登录的 `codex`，或用 `ARTICLE_INGEST_CODEX` 指定可执行文件绝对路径。
复核沿用 CLI 默认模型及登录，不新增 API 密钥；模型不可用时停在草稿，不跳过对照原图。
只有 Windows 的复核实跑证据；Linux 代码共用，未据此声称 Linux 实机已验。

## `{WIRING}`

在 Lightsail（gate 客户端所在机器）上本机抓、本机写：

```text
--fetch local --gate local
```

gate 客户端默认路径 `~/.hermes/article_archive/scripts/obsidian_gate.py`，不在这个位置时设
`ARTICLE_INGEST_GATE_CLIENT`。Lightsail 连不到 sera 的 shell（Hermes 的密钥被强制命令锁在 gate
上），所以这里只有一条出网：撞验证页会等 60 秒重试一次，仍不行就报 `verify`。需要「换 sera 的
网络再抓」时，从 SeraCC 跑（见 [windows.md](windows.md)）。

别的 Linux 机器没有 gate 客户端时，`--gate ssh:<有客户端的机器>`；该机器能不能直接抓国内站按
那台机器的网络规矩定，不确定就只用 `ssh:` 出网。

`ingest` / `fetch` 的草稿和图片留在发起命令的机器 `~/article_archive/`，可用
`ARTICLE_INGEST_WORK_ROOT` 或单篇 `--work` 覆盖，不自动清理。若要求图片留在 SeraCC / sera，
应从那台机器调用并借 Linux 出网；在 Lightsail 直接跑不会自动复制图片回本机。

## 状态

- 2026-09-16 在 Lightsail 上验过：`doctor` 全绿、查库命中、`fetch` 本机抓取出草稿、验证页按
  `unfetchable/verify` 报出。
- 从 SeraCC 用 `--gate ssh:lightsail` 时，脚本会把自己拷到 Lightsail 的
  `~/.cache/article_ingest/article_ingest.py` 执行；那份是每次覆盖的运行副本，改脚本只改仓里。

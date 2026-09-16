# Linux 分支

## `{PY}`

`python3`（标准库即可）。defuddle 走 `npx`：PATH 里没有时脚本会自己找
`~/.nvm/versions/node/*/bin/npx`（Lightsail 的 Node 装在 nvm 下，非交互 shell 的 PATH 里没有）。

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

## 状态

- 2026-09-16 在 Lightsail 上验过：`doctor` 全绿、查库命中、`fetch` 本机抓取出草稿、验证页按
  `unfetchable/verify` 报出。
- 从 SeraCC 用 `--gate ssh:lightsail` 时，脚本会把自己拷到 Lightsail 的
  `~/.cache/article_ingest/article_ingest.py` 执行；那份是每次覆盖的运行副本，改脚本只改仓里。

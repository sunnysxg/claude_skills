# Windows 分支

## `{PY}`

先确认一个真能跑的 Python 3（WindowsApps 下的 `python.exe` 只是商店占位，会打印
「Python was not found」）：依次试 `python --version`、`py -3 --version`、
`~/miniconda3/python.exe --version`，第一个输出版本号的就是 `{PY}`。脚本只用标准库。

defuddle 走本机 `npx`（Node 自带），首次会从 npm 拉 `defuddle@0.19.3` 到缓存。

## `{WIRING}`

**Windows 机器本机不抓国内站**：`--fetch local` 在 Windows 上直接被脚本拒绝（退出码 3），出网一律
经 ssh 借别的机器。接线写 ssh config 里的 alias，本机（SeraCC）是：

```text
--fetch ssh:lightsail,ssh:sera --gate ssh:lightsail
```

- `ssh:lightsail`（Linux）：脚本把自己拷到对方 `~/.cache/article_ingest/` 再在那边跑抓取 +
  分类 + defuddle，只回传 Markdown。必须这样：SeraCC 到 Lightsail 的链路实测只有约 10 KB/s，
  一个公众号页面有 3.5 MB，回传原始 HTML 会超时（2026-09-16 实测）。
- `ssh:sera`（Windows，cmd.exe）：远端跑自带的 `curl.exe`，HTML 走局域网回传，本机转换。它是
  第二条出网——Lightsail 撞验证页时换一个 IP 再试。
- `--gate ssh:lightsail`：gate 客户端和它的密钥只在 Lightsail 上（`from=` 限源），查库和写库都经
  那边转。查库索引缓存也在 Lightsail 的 `~/.cache/article_ingest/vault_url_index.json`：第一次
  要把 `_raw/` 与 `Clippings/` 每篇读一遍（60 篇约 5 分钟，逐条打进度），之后只读新增的。

别的 Windows 机器按自己的 ssh alias 填；也可以设 `ARTICLE_INGEST_FETCH` /
`ARTICLE_INGEST_GATE` 环境变量代替参数。

## 坑

- 草稿默认在 `~/.cache/article_ingest/work/`，不在任何 Git 树里，交付时不会弄脏候选树。
- 命令里的 URL 用双引号包住（长链里有 `&`）。

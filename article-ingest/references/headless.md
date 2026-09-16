# 备选路线：headless 浏览器（知乎、掘金这类站）

**不进公众号主路。** 微信的验证页按「像不像浏览器 + IP 信誉」判，headless 对公众号没有增量
（Hermes 自己的记录也写着 headless 反而更容易触发验证）。这条路只给 `fetch` 报
`unfetchable / thin`（JS 渲染，curl 拿到的是空壳）或 `blocked`（403）的非公众号站点用，目前是
手动路线，没接进 `article_ingest.py`。

## 怎么跑（在 Lightsail 上）

```bash
python3 scripts/render_page.py "<URL>" /tmp/page.html [--storage-state cookies.json]
npx -y defuddle@0.19.3 parse /tmp/page.html --markdown > /tmp/page.md
```

`render_page.py` 用 Playwright（Python）起 headless Chromium，滚动触发懒加载后存最终 HTML，打印
HTTP 状态、最终 URL、标题。转出来的 Markdown 人工确认正文完整后，再照主流程的草稿格式入库。

## 各站实测（2026-09-16，Lightsail 悉尼）

| 站点 | curl + Chrome UA | headless | 结论 |
|---|---|---|---|
| 掘金文章 | 200，2.4 KB 空壳，defuddle 出 13 字 | 200，445 KB，defuddle 出 2445 字 | headless 能用 |
| 知乎问题页 / 专栏 | 403 | 403，`code 40362`「请求存在异常」 | 云 IP 被挡，headless 也不行 |

**知乎的路线（未验证）**：要同时换掉两样——非云 IP（sera 的家庭网络）和登录态（从已登录浏览器
导出 Playwright storage-state，经 `--storage-state` 传入，文件不进 Git）。这需要在 sera 上装
Playwright，本卡没做；真遇到非读不可的知乎文章时另开卡。小红书是 302 跳登录，同属这一类。

## Lightsail 环境修复记录（2026-09-16）

旧状态：Chromium 启动不了，`ldd` 缺 9 个库（`libXcomposite`、`libXdamage`、`libXfixes`、
`libXrandr`、`libasound`、`libatk-1.0`、`libatk-bridge-2.0`、`libatspi`、`libgbm`）。

修复（幂等，重装系统后照做）：

```bash
sudo env PYTHONPATH=$HOME/.local/lib/python3.12/site-packages python3 -m playwright install-deps chromium
python3 -m playwright install chromium   # Python playwright 1.58 要 build 1208，约 111 MB
```

之后 `ldd` 无缺库，headless 能起。注意机器上有两套 Playwright：Hermes 的 Node 版（浏览器 build
1217）和 `~/.local` 的 Python 版（build 1208），浏览器缓存各用各的。

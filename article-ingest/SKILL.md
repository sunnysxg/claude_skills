---
name: article-ingest
description: >
  把一篇文章（主要是微信公众号）抓下来存进用户的 Obsidian 主库：先按 URL 查库，没有才用
  curl 抓、分出正文页/短内容/验证页/已删，defuddle 转 Markdown，经只新建不覆盖的受限入口写
  `_raw/` 原文与 REF 卡。用户发来文章链接要入库、存档、剪藏、「帮我存一下这篇」时使用。
---

# article-ingest — 文章入库

流程固定在 `scripts/article_ingest.py` 里（只用标准库），agent 只做两件脚本做不了的事：给草稿
打主题 tag、扫一眼头尾有没有脚本没剪掉的账号专属页脚。每一步的判定都以脚本输出的 JSON 为准，
不要自己另起抓取。

**前提**：本 skill 依赖 Lightsail 上的 Obsidian 受限入口（gate，库在 sera，经 Tailscale）。
没有这条链路的机器不适用——`doctor` 会报出来，别绕过 gate 直接写库。

## 1. 选平台分支，拿到调用前缀与接线参数

先识别操作系统，只读对应分支：

- Windows：[references/windows.md](references/windows.md)
- Linux：[references/linux.md](references/linux.md)

分支里给出 `{PY}`（Python 调用前缀）和 `{WIRING}`（`--fetch … --gate …`）。下文命令里的
`{SCRIPT}` = 本 skill 目录下的 `scripts/article_ingest.py`。首次在一台机器上用、或上一次报链路
错误时，先跑 `{PY} {SCRIPT} doctor {WIRING}`，`ok: true` 再继续。

同一会话第一次写库前，跑一次 `{PY} {SCRIPT} rules --gate …` 读库内规则（输出在 stderr：库根
`CLAUDE.md` 与 `_hermes/claude-code-guide.md`）。库内规则优先于本文。

## 2. 抓：`{PY} {SCRIPT} fetch <URL> {WIRING}`

多条链接逐条跑，不并发（gate 串行加锁）。按 `status` 分流：

| status | 含义 | 怎么办 |
|---|---|---|
| `exists` | 库里 `_raw/` 或 `Clippings/` 已有同一篇（短链 `/s/…` 与长链 `sn=` 互认） | 报 `vault_paths`，结束，不重复入库 |
| `drafted` | 抓到正文，草稿在 `work_dir` | 进第 3 步 |
| `deleted` | 平台已删：`infringement` 侵权投诉 / `violation` 违反规定 / `unavailable` 暂时无法查看 / `deleted_by_author` 作者删除 | 直接报删和原因，**不重试** |
| `unfetchable` | `verify` 各条出网都撞验证页；`network` 连不上；`thin` 非公众号页面转出来几乎没字；`blocked` 403；`gone` 404；`empty_body` 正文页却没字；`unknown` 未识别页面 | 报「抓不到 + reason」，见下 |

抓不到时**不拿近似结果顶替**（搜索摘要、别处转载、模型记忆都不行），也**不改用 Exa、Jina
Reader 之类第三方抓取服务**（为什么见 `docs/decisions.md`「抓文章不依赖第三方抓取服务」）。
`verify` 已经走完「等 60 秒重试一次 → 换下一条出网」；`thin` 是 JS 渲染或要登录的站（知乎、掘金
这类），按 [references/headless.md](references/headless.md) 的路线另说，不在这条主路里硬试。

`kind` 是 `article`（正文页）、`short`（公众号短内容，正文在页面数据里）或 `page`（非公众号页面）。
`attempts` 记录每次抓取走的哪条出网、结果和耗时，汇报时带上成功的那条。

## 3. 补草稿（agent 唯一要判断的地方）

`work_dir` 里三个文件：`raw.md`（原文）、`ref.md`（REF 卡骨架）、`meta.json`（`raw_path` /
`ref_path` 等）。

1. **tag**：把两份文件里的 `TODO_AGENT` 各换成 3～5 个主题 tag（照库里已有写法：英文小写
   kebab-case，如 `context-engineering`、`factor-model`；两份用同一组，`ref.md` 保留
   `zettelkastenReference`）。
2. **扫头尾残渣**：脚本已剪掉阅读器横幅、「知道了 / 微信扫一扫」页脚、常见推广块和「阅读原文」。
   账号专属的签名块（如「以上，既然看到这里了…三连」、商务合作邮箱）若还在文末，删掉；**只删
   页面残渣，不改正文一个字**。拿不准的留着。
3. **路径（可选）**：默认文件名是全标题。想短一点就改 `meta.json` 的 `raw_path` / `ref_path`
   （照库里现有 `_raw/作者-短标题-YYYYMMDD.md`、`REF-短标题-作者.md`），并同步改 `ref.md`
   「## 原文存档」下的 `[[…]]`——`write` 会校验两者一致。
4. **REF 卡只留骨架**：`**一句话**：` 留空给用户自己写——库宪法规定 REF 卡（A 类卡）只放用户
   自己的话、不放 AI 摘要。只有用户在这次请求里明说要 AI 写摘要，才写，并按库内「AI 标记约定」
   加 `cc/<当前模型>` tag。

## 4. 写：`{PY} {SCRIPT} write <work_dir> --gate …`

先建 `_raw/` 再建 REF。按 `status` 分流：

- `written`：两份的结果是 `created` 或 `existed`（同路径同内容，重跑无副作用），成功。
- `invalid_draft`：按 `problems` 改草稿再跑（还有 `TODO_AGENT`、`[[…]]` 与 `raw_path` 不一致、
  source 对不上等）。
- `conflict`：该路径已有**不同内容**的笔记。gate 永不覆盖；报给用户，由她决定改名重写还是放弃。
  前一步已建成的 `_raw` 不回滚（REF 可以换名再写）。
- 退出码 2（`backup_unhealthy`、`obsidian_offline`、`unreachable` 等）：链路没就绪，草稿留在
  `work_dir`，报原因，稍后原样重跑 `write`。`backup_unhealthy` 表示 sera 的库快照过期，按
  vault-ops 的备份检查处理，不要绕过。

## 5. 汇报

一两句：入库了哪篇（标题、公众号、发布日期）、两个 vault 路径、走的哪条出网；抓不到的给原因
分类。REF 卡「一句话」留空要提醒她补。

## 退出码

`0` 完成（drafted / written / exists）；`1` 拒绝或抓不到（deleted、unfetchable、conflict、
invalid_draft）；`2` 链路未就绪；`3` 用法或配置错误（没给 `--fetch` / `--gate`、在 Windows 上
用 `local` 抓取）。

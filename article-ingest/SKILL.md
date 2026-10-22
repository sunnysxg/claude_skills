---
name: article-ingest
description: >
  把文章（微信公众号、含图片正文的小红书笔记等）归档进用户的 Obsidian 主库，生成正文与索引卡。用户发来文章
  链接要入库、存档、剪藏、说「帮我存一下这篇」时使用。
---

# article-ingest — 文章入库

正常入库直接调用 `scripts/article_ingest.py ingest`（文字流程只用 Python 标准库）：统一查重、取源、清理、
成稿、校验并写库；小红书图片先用固定本地 OCR（专用图片文字识别模型）识字，再分批对照原图、
修复与整理 Markdown，通过质量检查才合稿写库。
正常路径无需 agent 串联步骤；失败才处理异常。每一步以脚本输出的 JSON 为准。

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

## 2. 入库：`{PY} {SCRIPT} ingest <URL> {WIRING}`

`written` / `exists` 直接汇报，不再让 agent 逐篇检查和串联正常的文字路径。脚本复用固定提取与清理
规则，不证明原文完整或转写零误差；用户阅读发现问题后再修流程。失败时由 agent 判断修脚本还是
临时手动处理；重复出现的可复用问题优先修脚本，不把手动补救变成常规步骤。

图片分支默认自动完成下载 → 本地识字 → 分批对照原图与修复排版 → 合稿 → 写库，可加
`--image-fetch ssh:<alias>` 指定下载出网。首次按平台分支安装固定 OCR 依赖；识字本身离线、
无聊天请求。最终成稿使用本机已登录的 Codex 读图模型，每批最多 6 个目标页，接受额度与耗时成本。
普通页也对照原图，复杂页在同一批中补救；不把高识字分数当完整性证明，不恢复逐页启动 agent。
接线、逐页产物与故障处理见 [转写调用](references/transcription.md)。

任何中途失败都沿输出的 `work_dir` 跑 `{PY} {SCRIPT} resume <work_dir> --gate …`：保留已有
图片、识字证据与有效复核结果，只补缺失或失效的页；已有通过质量检查的草稿直接重试写库，
不重建导致内容冲突。旧图片草稿没有复核记录时拒绝自动写入，保留原字节，在新目录重做修订。
不要重新 `ingest`，
以免已写的原文被查重命中后漏补 REF。仅排查取源或转写时可加 `--draft-only`，到草稿为止不写库。

仅需草稿、排查失败或指定路径时才用 `{PY} {SCRIPT} fetch <URL> {WIRING}`；它不自动写库。
草稿及正文图片默认留在本机独立归档目录 `~/article_archive/<时间戳_链接指纹>/`，不自动清理，
不进入 iCloud；每篇的 `source.json` 对应 `images/` 与 `pages/`。可用 `ARTICLE_INGEST_WORK_ROOT`
覆盖根目录，或用 `--work` 指定单篇位置。原有缓存目录不自动搬迁，已有草稿仍可原路径继续。

多条链接逐条跑，不并发（gate 串行加锁）。按 `status` 分流：

| status | 含义 | 怎么办 |
|---|---|---|
| `exists` | 库里 `_raw/` 或 `Clippings/` 已有同一篇（微信短长链互认；小红书分享链取源后按笔记 ID 互认） | 报 `vault_paths`，结束，不重复入库 |
| `drafted` | `fetch` 抓到正文，草稿在 `work_dir` | 按需看草稿，再 `write` |
| `needs_transcription` | `fetch` 或显式 `ingest --manual-transcription` 留下图片分支 | 跑 `resume` 自动续做，或按下面的人工修复步骤处理 |
| `ocr_ready` / `transcription_failed` / `ocr_missing` | OCR 初稿可交复核 / 单独识字失败 / 缺识字环境 | 统一入口会把页级失败交视觉补救；缺环境先安装；都不表示已入库 |
| `review_failed` / `review_unavailable` / `review_required` | 对照失败、模型不可用，或缺有效复核 | 按 `pages` 与诊断修复，再 `resume`；不退回 OCR 原稿写库 |
| `deleted` | 平台已删：`infringement` 侵权投诉 / `violation` 违反规定 / `unavailable` 暂时无法查看 / `deleted_by_author` 作者删除 | 直接报删和原因，**不重试** |
| `unfetchable` | `verify` 各条出网都撞验证页；`network` 连不上；`thin` 非公众号页面转出来几乎没字；`blocked` 403；`gone` 404；`empty_body` 正文页却没字；`unknown` 未识别页面 | 报「抓不到 + reason」，见下 |

抓不到时**不拿近似结果顶替**（搜索摘要、别处转载、模型记忆都不行），也**不改用 Exa、Jina
Reader 之类第三方抓取服务**（为什么见 `docs/decisions.md`「抓文章不依赖第三方抓取服务」）。
`verify` 已经走完「等 60 秒重试一次 → 换下一条出网」；`thin` 是 JS 渲染或要登录的站（知乎、掘金
这类），按 [references/headless.md](references/headless.md) 的路线另说，不在这条主路里硬试。

`kind` 是 `article`（正文页）、`short`（公众号短内容，正文在页面数据里）、`page`（普通网页）或
`xhs`（小红书笔记）。
`attempts` 记录每次抓取走的哪条出网、结果和耗时，汇报时带上成功的那条。

### 图片正文分支（自动执行；以下供异常修复）

小红书先用原站移动页的数据，不经 defuddle，也不因为图片外的说明文字多就当正文齐全。脚本保留
原帖图片顺序、作者、发布日期与规范来源链接（笔记 ID，不带分享参数），不取评论与视频。

1. `{PY} {SCRIPT} images <work_dir>`：沿成功取页的出网下载到 `images/001.img` 等；可用
   `--fetch ssh:<alias>` 换一条已配置的出网。下载失败报 `image_failed` 与页码，不用空图顶替；
   链接过期时重新 `fetch --work <新目录>`，不反复重试旧图片地址。
2. `{PY} {SCRIPT} transcribe <work_dir> --collect-issues` 将缺失页识字到 `pages/001.md` 等，
   空结果、低分或公式保留诊断并继续收集疑难页，不让第一处识字失败丢掉后续页。
3. `{PY} {SCRIPT} review <work_dir>` 分批对照原图，修正错字、标题、段落、表格、公式及跨页断句，
   保存到 `reviewed/`；OCR 原稿不覆盖。仍无法辨认就报具体页码、保留原图和已通过页，不编字。
   装饰图才写 `<!-- 本页无正文文字 -->`；图表要表达关系，不能只抄标签。可加
   `--repair-pages 3 7` 强制重审指定页；换图或手改会使旧复核失效。
4. `{PY} {SCRIPT} assemble <work_dir>` 检查全部页有效复核、按序合成正文与 REF 骨架；
   `write` 再核对成稿与复核内容一致，不能绕过。已有草稿不重建；修订已入库内容另走新目录与冲突处理。
5. `resume` 自动完成上述缺失步骤并写库。文字入库，图片和转写留在本机独立归档目录，可在原帖失效后本地回看；
   不写 `_raw` 附件、不跨机同步、不承诺本机磁盘损坏后的恢复。需要在 SeraCC / sera 留图时，
   从这两台机器发起命令；在 Lightsail 发起会留在 Lightsail，应换回本机调用。

`login_required` / `source_unavailable` 表示没拿到原帖数据或有效笔记身份，换完配置的出网仍失败就
报告缺有效分享链接或登录态；不当成删除。`unsupported_content` 表示视频，不在本技能范围。
重新抓取用新工作目录（同一分钟默认目录撞上时指定 `--work`）；已有目录报 `work_in_use`，沿原目录
继续处理即可。发布日期缺失时 `date` 是采集日，并显式记录 `published: null` 与日期依据，不冒充发布日期。

## 3. 按需看草稿（异常处理）

`work_dir` 里三个文件：`raw.md`（原文）、`ref.md`（REF 卡骨架）、`meta.json`（`raw_path` /
`ref_path` 等）。草稿按库宪法（`_hermes/claude-code-guide.md`「笔记体系核心规则」第 2 条）只建
骨架，agent 不往里加内容，只做下面两件：

1. **扫头尾残渣**：脚本已剪掉阅读器横幅、「知道了 / 微信扫一扫」页脚、常见推广块和「阅读原文」。
   账号专属的签名块（如「以上，既然看到这里了…三连」、商务合作邮箱）若还在文末，删掉；**只删
   页面残渣，不改正文一个字**。拿不准的留着。图片稿由 `review` 对照原图后整理，不能直接改
   `raw.md` 绕过复核；要修订已合稿内容，用新目录重做，不增补或改写原文。
2. **路径（可选）**：默认文件名是全标题。想短一点就改 `meta.json` 的 `raw_path` / `ref_path`
   （照库里现有 `_raw/作者-短标题-YYYYMMDD.md`、`REF-短标题-作者.md`），并同步改 `ref.md`
   「## 原文存档」下的 `[[…]]`——`write` 会校验两者一致。

## 4. 写：`{PY} {SCRIPT} write <work_dir> --gate …`

先建 `_raw/` 再建 REF。按 `status` 分流：

- `written`：两份的结果是 `created` 或 `existed`（同路径同内容，重跑无副作用），成功。
- `invalid_draft`：按 `problems` 改草稿再跑（`[[…]]` 与 `raw_path` 不一致、source 对不上等）。
- `conflict`：该路径已有**不同内容**的笔记。gate 永不覆盖；报给用户，由她决定改名重写还是放弃。
  前一步已建成的 `_raw` 不回滚（REF 可以换名再写）。
- 退出码 2（`backup_unhealthy`、`obsidian_offline`、`unreachable` 等）：链路没就绪，草稿留在
  `work_dir`，报原因，稍后原样重跑 `write`。`backup_unhealthy` 表示 sera 的库快照过期，按
  vault-ops 的备份检查处理，不要绕过。

## 5. 汇报

一两句：入库了哪篇（标题、作者、发布日期或「发布日期未知」）、两个 vault 路径、走的哪条出网；
图片正文带总页数、OCR/复核的状态、补救页和实际模型调用次数；分开报告识字、质量检查和写库，
不把自动复核说成人工逐字核验或零误差。抓不到的给原因分类和缺什么。

## 退出码

`0` 当前步骤完成（drafted / needs_transcription / images_ready / transcribed / ocr_ready / reviewed / written / exists）；`needs_transcription`
只是交给读图环节，不代表已入库。`1` 拒绝或抓不到（deleted、unfetchable、conflict、
invalid_draft / transcription_failed / review_failed / review_required）；`2` 链路未就绪；`3` 用法或配置错误（缺 OCR/复核环境、没给 `--fetch` / `--gate`、在 Windows 上
用 `local` 抓取）。

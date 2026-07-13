# LLM Session 归档布局

目录（固定，本机）：`~/_sxg/llm_session_log/`

归档按机器独立：每台机器（Windows 本机、sera、cpfs 集群）各有一份 `~/_sxg`，不跨机共享。

## 平台说明

| 能力 | Cursor | Claude Code |
|------|--------|-------------|
| 写入归档 + index | 已用 | 可用（手填时间） |
| `session_times.py` / `session_resolve.py` | 已实现，已测试 | **未测试** |
| `session_backfill.py` | 已实现，已测试 | **未测试** |
| upsert（同 chat 更新同一条） | 脚本驱动 | **未测试** |

## 文件名（现行格式）

`{YYYYMMDDHHMM}_{project}_{slug}.md`

| 部分 | 含义 |
|------|------|
| `{YYYYMMDDHHMM}` | 开始日 `YYYYMMDD` + 最后活跃 `HHMM`（Cursor：`session_times.py`）；12 位，24h，无分隔符 |
| `{project}` | 项目根目录名 snake_case 化（全小写，`-` → `_`），如 `quantalpha` |
| `{slug}` | 全小写 snake_case，纯 ASCII，≤40 字符 |

示例：`202606291749_quantalpha_lineage_rag_8002.md`

**首次创建后文件名冻结**；同一 chat 再次 `/session-log` 时覆写同文件，不因 last_active 变化而 rename。

按文件名排序大致按最后活跃倒序。

## Upsert（同 chat 多次 log）

| 机制 | 路径 | 作用 |
|------|------|------|
| `session_resolve.py` | skill `scripts/` | 判定 create / update，给出 `target_file` |
| `.session_map.json` | 归档目录下 | uuid → 文件名（机器维护，勿手改） |
| `session_id` frontmatter | 各 md 内 | 持久标识；map 丢失时可 `rg session_id:` 恢复 |

同一 chat 以**最新文件内容**为准；index 中对应行被替换，不新增重复行。

## 文件名（旧格式，存量兼容）

`[{project}]{YYMMDDHHMM}_{slug}.md` — 例：`[quantalpha]2606291749_lineage-rag-8002.md`

2026-07 规范统一前写入的文件（主要在集群），**只读不改名**；检索时两种格式都要覆盖。
新写入一律用现行格式。旧文件无 `session_id`；首次再 log 同一 chat 会 create 新条目（可接受）。

## Frontmatter（检索常用字段）

```yaml
session_id: "c4ddfb2c-1759-4255-bd98-42f839ec712b"
session_title: "标题"
date: 2026-06-29          # session 开始日（update 不变）
time: "17:49"             # 最后活跃（/session-log 前；update 刷新）
last_active_at: "2026-06-29T17:49:00+08:00"
logged_at: "2026-07-13T10:05:00+08:00"
project: quantalpha
project_path: "/cpfs01/nfshome/xgsun/HzyProjects/quantalpha"
summary: "一行摘要"
suggested_chat_title: "260629 lineage-rag-8002"
keywords: [lineage, RAG, mlflow]
git_commits: [fc70cc2]
```

`project_path` 是写入时所在机器的实际绝对路径，仅作记录，不用于定位归档。

## index.md

路径：`~/_sxg/llm_session_log/index.md`（旧名 `INDEX.md`，存量机器上改名即可）

列：日期 | 项目 | Session | 摘要 | Chat 标题建议（「日期」= session 开始日）

- **create**：新条目在表头下方第一行（最新在上）
- **update**：替换链接到同一 `{target_file}` 的行

## 已废弃

各项目 `{PROJECT}/_sxg/session_log/` — 勿再搜、勿再写。

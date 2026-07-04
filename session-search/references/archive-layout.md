# LLM Session 归档布局

目录（固定，本机）：`~/_sxg/llm_session_log/`

归档按机器独立：每台机器（Windows 本机、sera、cpfs 集群）各有一份 `~/_sxg`，不跨机共享。

## 文件名（现行格式）

`{YYYYMMDDHHMM}_{project}_{slug}.md`

| 部分 | 含义 |
|------|------|
| `{YYYYMMDDHHMM}` | 关 log 时本地时间，12 位，24h，无分隔符 |
| `{project}` | 项目根目录名 snake_case 化（全小写，`-` → `_`），如 `quantalpha` |
| `{slug}` | 全小写 snake_case，纯 ASCII，≤40 字符 |

示例：`202606291749_quantalpha_lineage_rag_8002.md`

按文件名排序即按时间倒序。

## 文件名（旧格式，存量兼容）

`[{project}]{YYMMDDHHMM}_{slug}.md` — 例：`[quantalpha]2606291749_lineage-rag-8002.md`

2026-07 规范统一前写入的文件（主要在集群），**只读不改名**；检索时两种格式都要覆盖。
新写入一律用现行格式。

## Frontmatter（检索常用字段）

```yaml
session_title: "标题"
date: 2026-06-29
time: "17:49"
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

列：日期 | 项目 | Session | 摘要 | Chat 标题建议

新条目在表头下方第一行（最新在上）。

## 已废弃

各项目 `{PROJECT}/_sxg/session_log/` — 勿再搜、勿再写。

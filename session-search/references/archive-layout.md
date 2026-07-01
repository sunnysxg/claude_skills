# LLM Session 归档布局

目录（固定）：`/cpfs01/nfshome/xgsun/_sxg/LLM_session_log/`

## 文件名

`[{project}]{YYMMDDHHMM}_{slug}.md`

| 部分 | 含义 |
|------|------|
| `{project}` | 项目根目录名，如 `quantalpha`、`HzyProjects` |
| `{YYMMDDHHMM}` | 关 log 时本地时间，24h，无分隔符 |
| `{slug}` | 短标识，可英文连字符或中文 |

示例：`[quantalpha]2606291749_lineage-rag-8002.md`

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

## INDEX.md

路径：`/cpfs01/nfshome/xgsun/_sxg/LLM_session_log/INDEX.md`

列：日期 | 项目 | Session | 摘要 | Chat 标题建议

新条目在表头下方第一行（最新在上）。

## 已废弃

各项目 `{PROJECT}/_sxg/session_log/` — 勿再搜、勿再写。

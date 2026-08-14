#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""todo-hub 扫描器：现扫现生成待办面板，无任何持久状态。

用法:
  python scan.py                    # 文本面板到 stdout
  python scan.py --html             # 同时写 HTML 到 ~/_sxg/todo_hub/panel.html
  python scan.py --html PATH        # 指定 HTML 输出路径

默认扫描 ~/Projects/**/_sxg/TODO.md。额外源（别的根目录、单个文件）在本 skill
根目录的 sources.local.json 登记（gitignored，本机专属）:
  {"roots": ["~/Other"], "files": ["~/somewhere/TODO.md"]}
条目语法见 conventions.md 第 12 节；本脚本与其同步维护。
"""
import argparse
import html as html_mod
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC8 = timezone(timedelta(hours=8))
ITEM_RE = re.compile(r"^- \[([ xX])\] ?(.*)$")
CHECKBOXISH_RE = re.compile(r"^[-*+] ?\[[^\]]{0,3}\]")
SECTION_RE = re.compile(r"^#{2,6}\s+(.*)$")
SKIP_DIRS = {".git", ".claude", "node_modules", "__pycache__", ".venv", "venv", "_sxg"}
DEFAULT_HTML = "~/_sxg/todo_hub/panel.html"


def disp_width(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, width):
    return s + " " * max(0, width - disp_width(s))


def truncate(s, width):
    if disp_width(s) <= width:
        return s
    out, w = [], 0
    for c in s:
        cw = 2 if unicodedata.east_asian_width(c) in "WF" else 1
        if w + cw > width - 1:
            break
        out.append(c)
        w += cw
    return "".join(out) + "…"


def parse_todo(path):
    """返回 (result, error)。result: {"items": [...], "unrecognized": N}"""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as e:
        return None, str(e)
    items, unrecognized, section, current = [], 0, None, None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line:
            current = None
            continue
        if line[0] in " \t":  # 缩进行 = 上一条目的续行
            if current is not None:
                current["cont"].append(line.strip())
            continue
        m = ITEM_RE.match(line)
        if m:
            state, body = m.groups()
            body = body.strip()
            high = body.startswith("!")
            if high:
                body = body[1:].strip()
            body = body.replace("**", "")  # 面板不渲染 markdown，剥掉加粗标记
            current = {"text": body, "done": state != " ", "high": high,
                       "section": section, "cont": []}
            items.append(current)
            continue
        sm = SECTION_RE.match(line)
        if sm:
            section = sm.group(1).strip()
            current = None
            continue
        if CHECKBOXISH_RE.match(line):  # 长得像 checkbox 但不合语法
            unrecognized += 1
        current = None
    return {"items": items, "unrecognized": unrecognized}, None


def find_projects(root):
    """遍历 root，返回 [(项目目录, TODO 路径)]。"""
    found = []
    for dirpath, dirnames, _ in os.walk(root):
        d = Path(dirpath)
        if "_sxg" in dirnames:
            todo = d / "_sxg" / "TODO.md"
            if todo.is_file():
                found.append((d, todo))
        dirnames[:] = [n for n in dirnames
                       if n not in SKIP_DIRS and not n.startswith(".")]
    return found


def load_sources():
    roots = [Path("~/Projects").expanduser()]
    files = []
    cfg = Path(__file__).resolve().parent.parent / "sources.local.json"
    if cfg.is_file():
        data = json.loads(cfg.read_text(encoding="utf-8"))
        roots += [Path(p).expanduser() for p in data.get("roots", [])]
        files += [Path(p).expanduser() for p in data.get("files", [])]
    return roots, files


def collect():
    roots, files = load_sources()
    projects, unreachable = [], []
    for root in roots:
        if not root.is_dir():
            unreachable.append(str(root))
            continue
        for d, todo in find_projects(root):
            rel = d.relative_to(root)
            group = "/".join(rel.parts[:-1]) or None
            projects.append(make_project(d.name, group, todo))
    for f in files:
        if not f.is_file():
            unreachable.append(str(f))
            continue
        name = f.parent.parent.name if f.parent.name == "_sxg" else f.parent.name
        projects.append(make_project(name, None, f))
    return projects, unreachable


def make_project(name, group, todo):
    parsed, err = parse_todo(todo)
    mtime = datetime.fromtimestamp(todo.stat().st_mtime, tz=timezone.utc).astimezone(UTC8)
    p = {"name": name, "group": group, "path": str(todo), "mtime": mtime,
         "error": err, "pending": [], "high": [], "unrecognized": 0}
    if parsed:
        p["pending"] = [i for i in parsed["items"] if not i["done"]]
        p["high"] = [i for i in p["pending"] if i["high"]]
        p["unrecognized"] = parsed["unrecognized"]
    return p


def ordered(projects):
    """顶层项目按更新时间倒序，容器组随其最新子项目排序，组内同样倒序。"""
    top = [p for p in projects if not p["group"]]
    groups = {}
    for p in projects:
        if p["group"]:
            groups.setdefault(p["group"], []).append(p)
    entries = [(p["mtime"], "proj", p) for p in top]
    for g, ps in groups.items():
        ps.sort(key=lambda p: p["mtime"], reverse=True)
        entries.append((ps[0]["mtime"], "group", (g, ps)))
    entries.sort(key=lambda e: e[0], reverse=True)
    return entries


def render_text(projects, unreachable, now):
    n_pending = sum(len(p["pending"]) for p in projects)
    n_high = sum(len(p["high"]) for p in projects)
    lines = ["TODO 面板 · %s (UTC+8) · %d 项目 · 未完成 %d · 高优 %d" % (
        now.strftime("%Y-%m-%d %H:%M"), len(projects), n_pending, n_high), ""]
    name_w = max([disp_width(p["name"]) + (2 if p["group"] else 0)
                  for p in projects] or [10]) + 2

    def emit(p, indent=""):
        stat = "未完成 %2d | 高优 %d | 更新 %s" % (
            len(p["pending"]), len(p["high"]), p["mtime"].strftime("%m-%d"))
        lines.append(indent + pad(p["name"], name_w - disp_width(indent)) + stat)
        if p["error"]:
            lines.append(indent + "  ⚠ 读取失败: " + p["error"])
        for i in p["high"]:
            lines.append(indent + "  ! " + truncate(i["text"], 72))

    for _, kind, payload in ordered(projects):
        if kind == "proj":
            emit(payload)
        else:
            g, ps = payload
            lines.append(g + "/")
            for p in ps:
                emit(p, "  ")
    warn = ["⚠ %s: %d 行未识别" % (p["name"], p["unrecognized"])
            for p in projects if p["unrecognized"]]
    warn += ["⚠ 源不可达: %s" % u for u in unreachable]
    if warn:
        lines += [""] + warn
    return "\n".join(lines)


HTML_HEAD = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TODO 面板</title><style>
:root{--bg:#f6f7f9;--card:#fff;--fg:#1c2230;--dim:#6b7280;--line:#e5e7eb;
--high:#d64545;--pill:#eef1f6;--accent:#5b8cff}
@media(prefers-color-scheme:dark){:root{--bg:#12151c;--card:#1a1f2a;--fg:#e6e9f0;
--dim:#8b93a5;--line:#2a3040;--high:#ff7b72;--pill:#242b3a;--accent:#7ea6ff}}
*{box-sizing:border-box}body{margin:0;padding:24px;background:var(--bg);color:var(--fg);
font:15px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
h1{font-size:18px;margin:0 0 4px}.meta{color:var(--dim);font-size:13px;margin-bottom:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
.gtitle{grid-column:1/-1;color:var(--dim);font-size:13px;margin:6px 0 -6px;
border-bottom:1px solid var(--line);padding-bottom:4px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.card h2{font-size:15px;margin:0 0 8px;display:flex;justify-content:space-between;gap:8px}
.card h2 .date{color:var(--dim);font-weight:normal;font-size:12px;white-space:nowrap}
.pills{display:flex;gap:6px;margin-bottom:8px}
.pill{background:var(--pill);border-radius:999px;padding:1px 10px;font-size:12px;color:var(--dim)}
.pill.hi{color:var(--high)}
.item{padding:2px 0;font-size:13.5px}.item.high::before{content:"! ";color:var(--high);font-weight:bold}
.item .sec{color:var(--dim);font-size:12px}
.cont{color:var(--dim);font-size:12.5px;line-height:1.45;padding-left:14px;white-space:pre-wrap}
details{margin-top:6px}summary{cursor:pointer;color:var(--accent);font-size:13px}
.warn{margin-top:20px;color:var(--high);font-size:13px}
</style></head><body>
"""


def render_html(projects, unreachable, now):
    n_pending = sum(len(p["pending"]) for p in projects)
    n_high = sum(len(p["high"]) for p in projects)
    out = [HTML_HEAD, "<h1>TODO 面板</h1>",
           '<div class="meta">%s (UTC+8) · %d 项目 · 未完成 %d · 高优 %d · 现扫现生成，事实源是各项目 _sxg/TODO.md</div>' % (
               now.strftime("%Y-%m-%d %H:%M"), len(projects), n_pending, n_high),
           '<div class="grid">']

    def esc(s):
        return html_mod.escape(s, quote=False)

    def card(p):
        out.append('<div class="card"><h2><span>%s</span><span class="date">%s</span></h2>' % (
            esc(p["name"]), p["mtime"].strftime("%m-%d %H:%M")))
        out.append('<div class="pills"><span class="pill">未完成 %d</span>'
                   '<span class="pill hi">高优 %d</span></div>' % (
                       len(p["pending"]), len(p["high"])))
        if p["error"]:
            out.append('<div class="warn">读取失败: %s</div>' % esc(p["error"]))
        def cont(i):
            for c in i["cont"]:
                out.append('<div class="cont">%s</div>' % esc(c))

        for i in p["high"]:
            out.append('<div class="item high">%s</div>' % esc(i["text"]))
            cont(i)
        rest = [i for i in p["pending"] if not i["high"]]
        if rest:
            out.append("<details><summary>其余未完成 %d 条</summary>" % len(rest))
            for i in rest:
                sec = ' <span class="sec">（%s）</span>' % esc(i["section"]) if i["section"] else ""
                out.append('<div class="item">%s%s</div>' % (esc(i["text"]), sec))
                cont(i)
            out.append("</details>")
        out.append("</div>")

    for _, kind, payload in ordered(projects):
        if kind == "proj":
            card(payload)
        else:
            g, ps = payload
            out.append('<div class="gtitle">%s/（项目包）</div>' % esc(g))
            for p in ps:
                card(p)
    out.append("</div>")
    warn = ["%s: %d 行未识别" % (p["name"], p["unrecognized"])
            for p in projects if p["unrecognized"]]
    warn += ["源不可达: %s" % u for u in unreachable]
    for w in warn:
        out.append('<div class="warn">⚠ %s</div>' % esc(w))
    out.append("</body></html>")
    return "\n".join(out)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="todo-hub 面板扫描器")
    ap.add_argument("--html", nargs="?", const=DEFAULT_HTML, default=None,
                    metavar="PATH", help="另写 HTML 面板（默认 %s）" % DEFAULT_HTML)
    args = ap.parse_args()
    now = datetime.now(timezone.utc).astimezone(UTC8)
    projects, unreachable = collect()
    print(render_text(projects, unreachable, now))
    if args.html:
        target = Path(args.html).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_html(projects, unreachable, now), encoding="utf-8")
        print("\nHTML 面板已写入: %s" % target)


if __name__ == "__main__":
    main()

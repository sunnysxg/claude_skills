#!/usr/bin/env python3
"""article-ingest: archive one article into the Obsidian vault through the create-only gate.

Pipeline (see ../SKILL.md): lookup vault by URL -> fetch HTML with curl + Chrome UA -> classify
(article / short / verify / deleted) -> defuddle to Markdown -> trim page residue -> drafts with the
vault frontmatter -> the agent fills TODO_AGENT markers -> `write` creates _raw + REF (never overwrites).

Subcommands (all print one JSON object on stdout; progress goes to stderr):
  fetch URL [--work DIR]   lookup + fetch + classify + convert + drafts
  write WORK_DIR           validate drafts, create _raw then REF through the gate
  lookup URL               vault lookup only
  rules                    print the vault's CLAUDE.md and _hermes/claude-code-guide.md (stderr)
  doctor                   check every fetcher, node/npx, gate probe
  proxy                    internal: one JSON request on stdin, runs on a Linux ssh host

Machine wiring comes from flags or environment, never from hostnames:
  --fetch / ARTICLE_INGEST_FETCH   comma list of `local` or `ssh:<alias>`, tried in order (required)
  --gate  / ARTICLE_INGEST_GATE    `local` or `ssh:<alias>` (host that has the gate client)
  ARTICLE_INGEST_GATE_CLIENT       gate client path on the gate host
                                   (default ~/.hermes/article_archive/scripts/obsidian_gate.py)
A Linux ssh fetcher fetches and converts on that host and returns only Markdown (a WeChat page is
~3.5 MB of HTML); a Windows ssh fetcher (cmd.exe + curl.exe) returns the HTML for local conversion.

Exit codes: 0 done (drafted / written / already in vault); 1 refused or unfetchable
(deleted, verify page, conflict, validation); 2 link not ready (gate/ssh unreachable); 3 usage/config.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import html
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
DEFUDDLE = "defuddle@0.19.3"
BEIJING = timezone(timedelta(hours=8))
CACHE = Path.home() / ".cache" / "article_ingest"
REMOTE_SCRIPT = ".cache/article_ingest/article_ingest.py"   # relative to the remote home
DEFAULT_GATE_CLIENT = "~/.hermes/article_archive/scripts/obsidian_gate.py"
LOOKUP_FOLDERS = ("_raw", "Clippings")
TODO = "TODO_AGENT"
META_MARK = "ARTICLE_INGEST_META"
LINK_STATES = {"unreachable", "obsidian_offline", "obsidian_timeout", "obsidian_error",
               "backup_unhealthy", "busy", "wrong_vault", "not_indexed", "gate_error", "gate_client_missing"}
DONE_KINDS = ("article", "short", "page", "deleted", "gone", "thin", "empty_body")


class Fail(Exception):
    def __init__(self, code: int, payload: dict):
        super().__init__(payload.get("status", "error"))
        self.code = code
        self.payload = payload


def log(msg: str) -> None:
    print(f"[article-ingest {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------- URL keys

def url_keys(url: str) -> set[str]:
    """Stable identities of one article: a WeChat link has a short (/s/TOKEN) and a long (sn=) form."""
    url = html.unescape((url or "").strip()).replace("\\x26", "&")
    if not url:
        return set()
    u = urlparse(url if "://" in url else "https://" + url)
    host = u.netloc.lower()
    keys = set()
    if host.endswith("mp.weixin.qq.com"):
        m = re.match(r"^/s/([A-Za-z0-9_-]{8,})", u.path)
        if m:
            keys.add("wx:s:" + m.group(1))
        q = parse_qs(u.query)
        if q.get("sn"):
            keys.add("wx:sn:" + q["sn"][0])
        if q.get("__biz") and q.get("mid") and q.get("idx"):
            keys.add(f"wx:mid:{q['__biz'][0]}:{q['mid'][0]}:{q['idx'][0]}")
        if keys:
            return keys
    query = "&".join(p for p in u.query.split("&") if p and not p.startswith("utm_"))
    keys.add("url:" + host + u.path.rstrip("/") + ("?" + query if query else ""))
    return keys


def note_urls(text: str) -> list[str]:
    fm = re.match(r"^﻿?---\r?\n(.*?)\r?\n---", text, re.S)
    head = fm.group(1) if fm else text[:3000]
    return [m.group(2).strip().strip("\"'") for m in re.finditer(r"(?m)^(source|url|link)\s*:\s*(\S.*)$", head)]


# ---------------------------------------------------------------- ssh transport

_remote_os: dict[str, str] = {}
_shipped: set[str] = set()


def remote_os(alias: str) -> str:
    if alias not in _remote_os:
        try:
            r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", alias, "echo %OS%"],
                               capture_output=True, stdin=subprocess.DEVNULL, timeout=40)
            out = r.stdout.decode("utf-8", "replace").strip()
            _remote_os[alias] = "windows" if "Windows_NT" in out else ("posix" if r.returncode == 0 else "down")
        except subprocess.TimeoutExpired:
            _remote_os[alias] = "down"
    return _remote_os[alias]


def proxy_call(alias: str, req: dict, timeout: int) -> dict:
    """Run this same script on a Linux ssh host (shipped on first use, so it never drifts)."""
    if alias not in _shipped:
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", alias,
                            "mkdir -p .cache/article_ingest && cat > " + REMOTE_SCRIPT],
                           input=Path(__file__).read_bytes(), capture_output=True, timeout=90)
        if r.returncode != 0:
            return {"ok": False, "status": "unreachable",
                    "detail": f"ship script to {alias}: " + r.stderr.decode("utf-8", "replace").strip()[-300:]}
        _shipped.add(alias)
    try:
        # stderr is inherited so remote progress lines reach the caller live.
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", alias, "python3 " + REMOTE_SCRIPT + " proxy"],
                           input=json.dumps(req, ensure_ascii=True).encode("ascii"),
                           stdout=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": "unreachable", "detail": f"proxy timeout {timeout}s"}
    lines = [ln for ln in r.stdout.decode("utf-8", "replace").splitlines() if ln.startswith("{")]
    if not lines:
        return {"ok": False, "status": "unreachable", "detail": f"proxy rc={r.returncode}, no JSON"}
    return json.loads(lines[-1])


# ---------------------------------------------------------------- gate side (runs on the gate host)

def _gate_module():
    path = Path(os.path.expanduser(os.environ.get("ARTICLE_INGEST_GATE_CLIENT", DEFAULT_GATE_CLIENT)))
    if not path.is_file():
        raise Fail(2, {"ok": False, "status": "gate_client_missing", "detail": str(path)})
    spec = importlib.util.spec_from_file_location("obsidian_gate", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def local_op(req: dict) -> dict:
    op = req["op"]
    if op == "attempt":
        return attempt_local(req["url"])
    g = _gate_module()
    if op == "probe":
        return g.probe()
    if op == "read":
        res, text = g.read(req["path"])
        if text is not None:
            res["content"] = text
        return res
    if op == "create":
        return g.create(req["path"], req["content"])
    if op == "lookup":
        return gate_lookup(g, set(req["keys"]))
    raise Fail(3, {"ok": False, "status": "bad_request", "detail": f"unknown proxy op {op}"})


def gate_lookup(g, keys: set[str]) -> dict:
    """Incremental URL index of _raw/ and Clippings/: list names (cheap), read only unseen notes."""
    index_file = CACHE / "vault_url_index.json"
    try:
        index = json.loads(index_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        index = {}
    listed, truncated = [], []
    for folder in LOOKUP_FOLDERS:
        res, paths = g.list_notes(folder, "")
        if not res.get("ok"):
            return res
        if res.get("total", len(paths)) > len(paths):
            truncated.append(f"{folder}: {len(paths)}/{res.get('total')}")
        listed.extend(paths)
    unseen = [p for p in listed if p not in index]
    for i, path in enumerate(unseen, 1):
        t0 = time.time()
        res, text = g.read(path)
        if not res.get("ok"):
            return res
        index[path] = sorted({k for u in note_urls(text) for k in url_keys(u)})
        log(f"index {i}/{len(unseen)} {time.time() - t0:.1f}s")
    index = {p: index[p] for p in listed}
    CACHE.mkdir(parents=True, exist_ok=True)
    index_file.write_text(json.dumps(index, ensure_ascii=False, indent=0), encoding="utf-8")
    hits = sorted(p for p, ks in index.items() if keys & set(ks))
    return {"ok": True, "status": "ok", "hits": hits, "indexed": len(index), "newly_read": len(unseen),
            "truncated": truncated}


def gate_call(spec: str | None, req: dict, timeout: int = 1800) -> dict:
    if not spec:
        raise Fail(3, {"ok": False, "status": "config_missing",
                       "detail": "pass --gate local|ssh:<alias> or set ARTICLE_INGEST_GATE"})
    if spec == "local":
        return local_op(req)
    if spec.startswith("ssh:"):
        return proxy_call(spec[4:], req, timeout)
    raise Fail(3, {"ok": False, "status": "config_invalid", "detail": f"gate spec {spec!r}"})


# ---------------------------------------------------------------- fetch

def curl_args(url: str) -> list[str]:
    return ["curl", "-sS", "-L", "--compressed", "--max-time", "40", "-A", UA,
            "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "-H", "Accept-Language: zh-CN,zh;q=0.9,en;q=0.8",
            "-o", "-", "-w", "%{stderr}" + META_MARK + " %{http_code} %{url_effective}\\n", url]


def run_curl(cmd: list[str], url: str) -> dict:
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=90)
    except subprocess.TimeoutExpired:
        return {"http": 0, "html": "", "network": "timeout", "secs": round(time.time() - t0, 1)}
    err = r.stderr.decode("utf-8", "replace")
    m = re.search(META_MARK + r" (\d{3}) (\S*)", err)
    res = {"http": int(m.group(1)) if m else 0, "final_url": m.group(2) if m else url,
           "html": r.stdout.decode("utf-8", "replace"), "secs": round(time.time() - t0, 1)}
    if not m or res["http"] == 0:
        res["network"] = err.replace(META_MARK, "").strip()[-300:] or f"curl rc={r.returncode}"
    return res


def attempt_local(url: str) -> dict:
    return process(run_curl(curl_args(url), url), url)


def attempt(spec: str, url: str) -> dict:
    if spec == "local":
        if os.name == "nt":
            raise Fail(3, {"ok": False, "status": "config_invalid",
                           "detail": "local fetch is refused on Windows: fetch through ssh:<alias> instead"})
        return {"via": spec, **attempt_local(url)}
    if not spec.startswith("ssh:"):
        raise Fail(3, {"ok": False, "status": "config_invalid", "detail": f"fetch spec {spec!r}"})
    alias = spec[4:]
    kind = remote_os(alias)
    if kind == "down":
        return {"via": spec, "kind": "network", "reason": f"ssh {alias} unreachable"}
    if kind == "posix":
        res = proxy_call(alias, {"op": "attempt", "url": url}, timeout=400)
        if "kind" not in res:
            res = {"kind": "network", "reason": f"{res.get('status')}: {res.get('detail', '')}"}
        return {"via": spec, **res}
    # Windows over cmd.exe: double-quote every argument; curl.exe ships with Windows 10+.
    remote = "curl.exe " + " ".join('"' + a.replace('"', "") + '"' for a in curl_args(url)[1:])
    res = run_curl(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", alias, remote], url)
    return {"via": spec, **process(res, url)}


# ---------------------------------------------------------------- classify + extract

DELETED = [
    ("infringement", ("被投诉且经审核涉嫌侵权",)),
    ("violation", ("因违规无法查看", "违反《互联网用户公众账号信息服务管理规定》")),
    ("unavailable", ("此内容暂时无法查看",)),
    ("deleted_by_author", ("该内容已被发布者删除",)),
]


def is_wechat(url: str) -> bool:
    return "mp.weixin.qq.com" in urlparse(url).netloc


def classify(res: dict, url: str) -> tuple[str, str]:
    if res.get("network"):
        return "network", res["network"]
    page, status = res["html"], res["http"]
    if is_wechat(url) or is_wechat(res.get("final_url", "")):
        ist = re.search(r"item_show_type\s*[=:]\s*'(\d+)'", page)
        if ist and ist.group(1) == "10" and "content_noencode" in page:
            return "short", ""
        if 'id="js_content"' in page and ("msg_title" in page or "og:title" in page):
            return "article", ""
        for reason, needles in DELETED:
            if any(n in page for n in needles):
                return "deleted", reason
        if "secitptpage/verify" in page or "poc_token" in page or "环境异常" in page:
            return "verify", ""
        return "unknown", f"http {status}, {len(page)} bytes"
    if status in (401, 403):
        return "blocked", f"http {status}"
    if status in (404, 410):
        return "gone", f"http {status}"
    if status == 200 and page.strip():
        return "page", ""
    return "unknown", f"http {status}, {len(page)} bytes"


def js_unescape(s: str) -> str:
    return re.sub(r"\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|.)",
                  lambda m: chr(int(m.group(1)[1:], 16)) if m.group(1)[0] in "xu" and len(m.group(1)) > 1
                  else {"n": "\n", "t": "\t", "r": ""}.get(m.group(1), m.group(1)), s)


def first(page: str, *patterns: str) -> str:
    for p in patterns:
        m = re.search(p, page, re.S)
        if m and m.group(1).strip():
            return html.unescape(js_unescape(m.group(1))).strip()
    return ""


def wechat_meta(page: str, url: str) -> dict:
    ts = first(page, r'var ct\s*=\s*"?(\d{9,10})', r"create_time\s*[=:]\s*'?\"?(\d{9,10})",
               r"ori_create_time:\s*'(\d{9,10})'")
    return {
        "title": first(page, r"var msg_title\s*=\s*'(.*?)'", r'<meta property="og:title" content="([^"]*)"'),
        # account name, not the byline: <meta name="author"> is the byline (新京报记者 vs 新京报)
        "account": first(page, r'id="js_name"[^>]*>\s*([^<]+?)\s*<', r"var nickname\s*=\s*htmlDecode\(\"([^\"]*)\"\)",
                         r"nick_name:\s*'([^']*)'", r'<meta name="author" content="([^"]*)"'),
        "byline": first(page, r'<meta name="author" content="([^"]*)"'),
        "published": int(ts) if ts else 0,
        "link": first(page, r'var msg_link\s*=\s*"([^"]*)"', r'<meta property="og:url" content="([^"]*)"') or url,
    }


def short_markdown(page: str) -> tuple[str, str]:
    text = first(page, r"content_noencode:\s*'((?:[^'\\]|\\.)*)'")
    pics = re.search(r"picture_page_info_list:\s*\[(.*?)\]\s*,\s*\w+:", page, re.S)
    imgs = re.findall(r"cdn_url:\s*'([^']+)'", pics.group(1)) if pics else []
    body = "\n".join(ln.rstrip() for ln in text.split("\n")).strip()
    if imgs:
        body += "\n\n" + "\n\n".join(f"![]({html.unescape(u)})" for u in imgs)
    # og:title is either the whole post or a real headline; its first line works for both.
    og = first(page, r'<meta property="og:title" content="([^"]*)"')
    title = next((ln.strip() for ln in (og or text).split("\n") if ln.strip()), "")
    return (title[:60].rstrip("。，,. ") or "短内容"), body


# ---------------------------------------------------------------- defuddle + trim

def find_npx() -> str | None:
    found = shutil.which("npx")
    if found:
        return found
    cands = sorted(glob.glob(os.path.expanduser("~/.nvm/versions/node/*/bin/npx")))
    return cands[-1] if cands else None


def defuddle(html_path: Path, as_json: bool = False) -> str:
    npx = find_npx()
    if not npx:
        raise Fail(3, {"ok": False, "status": "node_missing", "detail": "npx not found (PATH or ~/.nvm)"})
    env = dict(os.environ)
    env["PATH"] = str(Path(npx).parent) + os.pathsep + env.get("PATH", "")
    cmd = [npx, "-y", DEFUDDLE, "parse", str(html_path), "--markdown"] + (["--json"] if as_json else [])
    r = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=300, env=env)
    if r.returncode != 0:
        raise Fail(1, {"ok": False, "status": "convert_failed", "detail": r.stderr.decode("utf-8", "replace")[-400:]})
    return r.stdout.decode("utf-8", "replace")


PROMO = re.compile(r"点赞|在看|转发|星标|置顶|一键三连|扫码|长按|关注我们|关注公众号|点个赞|分享给|推送|阅读原文")
BOLD_SHORT = re.compile(r"^\*\*[^*]{1,24}\*\*$")
IMAGE_LINE = re.compile(r"^(!\[[^\]]*\]\([^)]*\)\s*)+$")
TRAILING_UI = {"阅读原文", "轻触阅读原文", "预览时标签不可点", "继续滑动看下一个", "向上滑动看下一个"}


def trim_wechat(md: str) -> str:
    lines = md.replace("\r\n", "\n").split("\n")
    # head: account-name line + "在小说阅读器读本章 / 去阅读" reader banner
    for i, ln in enumerate(lines[:12]):
        if ln.strip() == "在小说阅读器读本章":
            end = i
            for j in range(i + 1, min(i + 5, len(lines))):
                if lines[j].strip() == "去阅读":
                    end = j
                    break
            lines = lines[end + 1:]
            break
    # tail: WeChat UI from "知道了 / 微信扫一扫" to the end
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == "知道了" and any(x.strip().startswith("微信扫一扫") for x in lines[i + 1:i + 5]):
            lines = lines[:i]
            break
    while lines and (not lines[-1].strip() or lines[-1].strip() in TRAILING_UI):
        lines.pop()
    # promo block right before the tail: short promo lines, short bold slogans, images below them
    j, cut = len(lines), None
    while j > 0:
        s = lines[j - 1].strip()
        if not s or IMAGE_LINE.match(s) or s in TRAILING_UI:
            j -= 1
        elif len(s) <= 80 and (PROMO.search(s) or BOLD_SHORT.match(s)):
            j -= 1
            cut = j
        else:
            break
    if cut is not None and any(PROMO.search(x) for x in lines[cut:]):
        lines = lines[:cut]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def process(res: dict, url: str) -> dict:
    """Classify a fetched page and, if it has content, convert it; runs wherever the HTML is."""
    kind, reason = classify(res, url)
    out = {"kind": kind, "reason": reason, "http": res.get("http", 0), "secs": res.get("secs")}
    if kind not in ("article", "short", "page"):
        return out
    page = res["html"]
    with tempfile.TemporaryDirectory(prefix="article_ingest_") as td:
        html_path = Path(td) / "page.html"
        html_path.write_text(page, encoding="utf-8")
        if kind == "short":
            meta = wechat_meta(page, url)
            meta["title"], body = short_markdown(page)
        elif kind == "article":
            meta = wechat_meta(page, url)
            body = trim_wechat(defuddle(html_path))
        else:
            data = json.loads(defuddle(html_path, as_json=True))
            body = (data.get("content") or "").strip()
            pub = data.get("published") or ""
            try:
                published = int(datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp()) if pub else 0
            except ValueError:
                published = 0
            meta = {"title": data.get("title") or url, "account": data.get("author") or data.get("site") or urlparse(url).netloc,
                    "byline": data.get("author") or "", "published": published, "link": url}
    chars = len(re.sub(r"!\[[^\]]*\]\([^)]*\)|\s", "", body))
    if chars < 200 and kind != "short":
        out.update(kind="thin" if kind == "page" else "empty_body",
                   reason=f"{chars} chars after defuddle" + (": JS-rendered or login wall, see references/headless.md" if kind == "page" else ""))
        return out
    out.update(meta=meta, body=body, chars=chars)
    return out


# ---------------------------------------------------------------- drafts

def slug(text: str, limit: int) -> str:
    s = re.sub(r"[\"'“”‘’「」『』《》【】()（）\[\]{}<>`^#]+", "", text)
    s = re.sub(r"[\\/:*?|$%&=+@!~,，。、；;：！？\s]+", "-", s)
    return re.sub(r"-{2,}", "-", s).strip("-.")[:limit].strip("-.") or "untitled"


def yaml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_drafts(meta: dict, body: str) -> dict:
    now = datetime.now(BEIJING)
    pub = datetime.fromtimestamp(meta["published"], BEIJING) if meta["published"] else now
    account = re.sub(r"\s+", "", meta["account"]) or "unknown"
    author = re.sub(r"[\[\]|#^]", "", account)
    stamp = now.strftime("%Y-%m-%dT%H:%M")
    raw_path = f"_raw/{slug(account, 24)}-{slug(meta['title'], 40)}-{pub.strftime('%Y%m%d')}.md"
    ref_path = f"2-Zettelkasten-References/REF-{slug(meta['title'], 24)}-{slug(account, 24)}.md"
    common = ["categories: \"[[articles]]\"", f"author: \"[[{author}]]\"", f"source: {yaml_str(meta['link'])}"]
    raw = "\n".join([
        "---", f"date: {pub:%Y-%m-%d}", "tags:", f"  - {TODO}", f"id: ref_{pub:%Y%m%d%H%M%S}", *common,
        f"created: \"{stamp}\"", f"updated: \"{stamp}\"", "---", "", f"# {meta['title']}", "", body, ""])
    # The vault constitution keeps REF cards in the owner's own words: the one-liner stays empty for her.
    ref = "\n".join([
        "---", f"date: {pub:%Y-%m-%d}", "tags:", "  - zettelkastenReference", f"  - {TODO}",
        "topics:", f"id: zettelkastenReference{now:%Y%m%d%H%M%S}", *common, "rating:",
        f"created: \"{stamp}\"", f"updated: \"{stamp}\"", "---", "", f"# REF · {meta['title']}", "",
        "**一句话**：", "",
        "## 原文存档", f"[[{raw_path[:-3]}]]", "", "## 笔记", "", ""])
    return {"raw_path": raw_path, "ref_path": ref_path, "raw": raw, "ref": ref}


# ---------------------------------------------------------------- commands

def cfg(args, name: str, env: str) -> str | None:
    return getattr(args, name, None) or os.environ.get(env)


def fetchers_of(args) -> list[str]:
    return [s.strip() for s in (cfg(args, "fetch", "ARTICLE_INGEST_FETCH") or "").split(",") if s.strip()]


def lookup(args, keys: set[str]) -> list[str]:
    res = gate_call(cfg(args, "gate", "ARTICLE_INGEST_GATE"), {"op": "lookup", "keys": sorted(keys)})
    if not res.get("ok"):
        raise Fail(2 if res.get("status") in LINK_STATES else 1, res)
    if res.get("truncated"):
        log(f"lookup incomplete, gate list capped: {res['truncated']}")
    return res["hits"]


def cmd_lookup(args) -> dict:
    hits = lookup(args, url_keys(args.url))
    return {"ok": True, "status": "exists" if hits else "not_found", "vault_paths": hits}


def cmd_fetch(args) -> dict:
    url = args.url.strip()
    fetchers = fetchers_of(args)
    if not fetchers:
        raise Fail(3, {"ok": False, "status": "config_missing",
                       "detail": "pass --fetch local|ssh:<alias>[,...] or set ARTICLE_INGEST_FETCH"})
    keys = url_keys(url)
    if not args.no_lookup:
        try:
            hits = lookup(args, keys)
            if hits:
                return {"ok": True, "status": "exists", "url": url, "vault_paths": hits}
        except Fail as e:
            log(f"vault lookup unavailable, fetching anyway: {e.payload}")
    attempts, res = [], {"kind": "network", "reason": "no fetcher ran"}
    for spec in fetchers:
        for n in range(2):
            log(f"fetch via {spec}" + (" (retry after verify page)" if n else ""))
            res = attempt(spec, url)
            attempts.append({k: res.get(k) for k in ("via", "kind", "reason", "http", "secs")})
            if res["kind"] != "verify" or n == 1 or args.verify_wait < 0:
                break
            log(f"verify page, waiting {args.verify_wait}s")
            time.sleep(args.verify_wait)
        if res["kind"] in DONE_KINDS:
            break
    base = {"url": url, "attempts": attempts}
    if res["kind"] == "deleted":
        raise Fail(1, {"ok": False, "status": "deleted", "reason": res["reason"], **base})
    if "body" not in res:
        raise Fail(1, {"ok": False, "status": "unfetchable", "reason": res["kind"], "detail": res.get("reason"), **base})

    meta, body = res["meta"], res["body"]
    post_keys = keys | url_keys(meta["link"])
    if not args.no_lookup and post_keys != keys:
        try:
            hits = lookup(args, post_keys)
            if hits:
                return {"ok": True, "status": "exists", "url": url, "vault_paths": hits, **base}
        except Fail as e:
            log(f"post-fetch lookup unavailable: {e.payload}")
    work = Path(args.work) if args.work else CACHE / "work" / (
        datetime.now(BEIJING).strftime("%Y%m%d%H%M") + "_" + hashlib.sha1(url.encode()).hexdigest()[:8])
    work.mkdir(parents=True, exist_ok=True)
    drafts = build_drafts(meta, body)
    (work / "raw.md").write_text(drafts["raw"], encoding="utf-8")
    (work / "ref.md").write_text(drafts["ref"], encoding="utf-8")
    info = {"url": url, "kind": res["kind"], "title": meta["title"], "account": meta["account"],
            "byline": meta["byline"], "published": meta["published"], "link": meta["link"], "chars": res["chars"],
            "raw_path": drafts["raw_path"], "ref_path": drafts["ref_path"]}
    (work / "meta.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "status": "drafted", "work_dir": str(work), **info, **base}


def validate(work: Path) -> tuple[dict, str, str]:
    info = json.loads((work / "meta.json").read_text(encoding="utf-8"))
    raw = (work / "raw.md").read_text(encoding="utf-8")
    ref = (work / "ref.md").read_text(encoding="utf-8")
    problems = []
    rp, fp = info["raw_path"], info["ref_path"]
    if not (rp.startswith("_raw/") and rp.endswith(".md")):
        problems.append("raw_path must be _raw/*.md")
    if not (fp.startswith("2-Zettelkasten-References/") and fp.endswith(".md")):
        problems.append("ref_path must be 2-Zettelkasten-References/*.md")
    for name, text in (("raw.md", raw), ("ref.md", ref)):
        if TODO in text:
            problems.append(f"{name} still has {TODO} markers")
        if not re.match(r"^---\n.*?\n---\n", text, re.S):
            problems.append(f"{name} has no frontmatter")
        if not ({k for u in note_urls(text) for k in url_keys(u)} & url_keys(info["link"])):
            problems.append(f"{name} source does not match {info['link']}")
    archive = re.search(r"(?ms)^## 原文存档\s*\n(.*?)(^## |\Z)", ref)
    if not archive or f"[[{rp[:-3]}]]" not in archive.group(1):
        problems.append(f"ref.md needs [[{rp[:-3]}]] under ## 原文存档")
    if problems:
        raise Fail(1, {"ok": False, "status": "invalid_draft", "problems": problems, "work_dir": str(work)})
    return info, raw, ref


def cmd_write(args) -> dict:
    work = Path(args.work_dir)
    info, raw, ref = validate(work)
    spec = cfg(args, "gate", "ARTICLE_INGEST_GATE")
    results = {}
    for label, path, text in (("raw", info["raw_path"], raw), ("ref", info["ref_path"], ref)):
        log(f"create {label}: {path}")
        res = gate_call(spec, {"op": "create", "path": path, "content": text}, timeout=300)
        results[label] = {"path": path, "status": res.get("status"), "detail": res.get("detail")}
        if not res.get("ok"):
            raise Fail(2 if res.get("status") in LINK_STATES else 1,
                       {"ok": False, "status": res.get("status"), "results": results, "work_dir": str(work)})
    return {"ok": True, "status": "written", "results": results}


def cmd_rules(args) -> dict:
    for path in ("CLAUDE.md", "_hermes/claude-code-guide.md"):
        res = gate_call(cfg(args, "gate", "ARTICLE_INGEST_GATE"), {"op": "read", "path": path}, timeout=120)
        if not res.get("ok"):
            raise Fail(2 if res.get("status") in LINK_STATES else 1, res)
        sys.stderr.write(f"\n===== {path}\n{res['content']}\n")
    return {"ok": True, "status": "ok", "detail": "rules printed on stderr"}


def cmd_doctor(args) -> dict:
    checks = {}
    for spec in fetchers_of(args):
        if spec == "local":
            checks[spec] = "refused on Windows" if os.name == "nt" else ("ok" if shutil.which("curl") else "missing curl")
        elif spec.startswith("ssh:"):
            checks[spec] = remote_os(spec[4:])
        else:
            checks[spec] = "invalid spec"
    checks["npx"] = find_npx() or "missing"
    gate_spec = cfg(args, "gate", "ARTICLE_INGEST_GATE")
    if gate_spec:
        res = gate_call(gate_spec, {"op": "probe"}, timeout=120)
        checks["gate"] = f"{res.get('status')} {res.get('detail', '')}".strip()
    bad = [k for k, v in checks.items() if v in ("down", "missing", "invalid spec") or str(v).startswith(("refused", "missing"))]
    if gate_spec and not checks["gate"].startswith("ok"):
        bad.append("gate")
    return {"ok": not bad, "status": "ok" if not bad else "degraded", "checks": checks}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def wiring(p, fetch=False):
        if fetch:
            p.add_argument("--fetch", help="comma list of local | ssh:<alias> (env ARTICLE_INGEST_FETCH)")
        p.add_argument("--gate", help="local | ssh:<alias> (env ARTICLE_INGEST_GATE)")

    p = sub.add_parser("fetch")
    p.add_argument("url")
    p.add_argument("--work", help="draft directory (default ~/.cache/article_ingest/work/...)")
    p.add_argument("--no-lookup", action="store_true", help="skip the vault URL lookup")
    p.add_argument("--verify-wait", type=int, default=60, help="seconds before retrying a verify page; -1 = no retry")
    wiring(p, fetch=True)
    p = sub.add_parser("write")
    p.add_argument("work_dir")
    wiring(p)
    p = sub.add_parser("lookup")
    p.add_argument("url")
    wiring(p)
    wiring(sub.add_parser("rules"))
    wiring(sub.add_parser("doctor"), fetch=True)
    sub.add_parser("proxy")
    args = ap.parse_args()
    try:
        if args.cmd == "proxy":
            out = local_op(json.loads(sys.stdin.buffer.read().decode("utf-8")))
        else:
            out = {"fetch": cmd_fetch, "write": cmd_write, "lookup": cmd_lookup, "rules": cmd_rules,
                   "doctor": cmd_doctor}[args.cmd](args)
        code = 0 if out.get("ok", True) else 1
    except Fail as e:
        out, code = e.payload, e.code
    if args.cmd == "proxy":
        code = 0   # the caller reads status from the JSON
    print(json.dumps(out, ensure_ascii=args.cmd == "proxy"))
    return code


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())

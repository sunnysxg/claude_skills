#!/usr/bin/env python3
"""Render a JS-heavy page in headless Chromium and save the final HTML (fallback route, not WeChat).

Usage: render_page.py URL OUT_HTML [--storage-state FILE] [--wait-ms 2500]
Prints one JSON line: http status, final url, title, bytes, and whether a login wall / verify page showed up.
Convert afterwards with: npx -y defuddle@0.19.3 parse OUT_HTML --markdown
--storage-state takes a Playwright storage-state JSON (cookies exported from a logged-in browser) for
sites that need a session; keep that file out of Git.
Needs: pip install playwright; python3 -m playwright install chromium; system libs via
sudo python3 -m playwright install-deps chromium (see ../references/headless.md).
"""

import argparse
import json
import sys
import time

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
WALLS = ("登录", "安全验证", "验证码", "环境异常", "unhuman", "Sign in", "captcha")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("out")
    ap.add_argument("--storage-state")
    ap.add_argument("--wait-ms", type=int, default=2500)
    a = ap.parse_args()
    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(user_agent=UA, locale="zh-CN", viewport={"width": 1280, "height": 900},
                                  storage_state=a.storage_state)
        page = ctx.new_page()
        resp = page.goto(a.url, wait_until="domcontentloaded", timeout=60000)
        for _ in range(8):   # trigger lazy-loaded content
            page.mouse.wheel(0, 1500)
            page.wait_for_timeout(200)
        page.wait_for_timeout(a.wait_ms)
        html = page.content()
        info = {"http": resp.status if resp else 0, "final_url": page.url, "title": page.title(),
                "bytes": len(html.encode("utf-8")), "secs": round(time.time() - t0, 1),
                "wall_hints": [w for w in WALLS if w in page.title() or w in page.url]}
        browser.close()
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(json.dumps(info, ensure_ascii=False))
    return 0 if info["http"] and info["http"] < 400 else 1


if __name__ == "__main__":
    sys.exit(main())

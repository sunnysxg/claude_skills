"""Offline behavior checks; no real vault or network writes."""
import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("ingest", Path(__file__).parents[1] / "scripts/article_ingest.py")
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
ID = "6ad0d9200000000018013158"
URL = "https://www.xiaohongshu.com/explore/" + ID


def page(images=2, **extra):
    note = {"noteId": ID, "type": "normal", "title": "Sample", "desc": "undefined 正文",
            "user": {"nickName": "Author"}, "time": 1792071968000,
            "imageList": [{"url": f"https://example.com/{n}.jpg"} for n in range(images)], **extra}
    return '<script>window.__INITIAL_STATE__=' + json.dumps({"note": {"noteDetailMap": {ID: {"note": note}}}})[:-1] + ',"unused":undefined}</script>'


class IngestTests(unittest.TestCase):
    def test_image_content_bypasses_defuddle_even_with_long_caption(self):
        with patch.object(a, "defuddle", side_effect=AssertionError("must not convert image note")):
            r = a.process({"http": 200, "html": page(desc="说明" * 300), "final_url": URL}, URL)
        self.assertEqual(r["kind"], "xhs")
        self.assertEqual([p["page"] for p in r["images"]], [1, 2])
        self.assertEqual(r["meta"]["published"], 1792071968)

    def test_undefined_inside_text_and_desktop_image_variant(self):
        r = a.xhs_content(page(imageList=[{"urlDefault": "https://example.com/full.jpg"}]), URL)
        self.assertEqual(r["body"], "undefined 正文")
        self.assertEqual(r["images"][0]["url"], "https://example.com/full.jpg")

    def test_identity_and_old_archive_note_id(self):
        self.assertEqual(a.url_keys(URL + "?xsec_token=a"), a.url_keys(URL.replace("explore", "discovery/item")))
        urls = a.note_urls('---\nsource: "https://xhslink.cn/o/old"\nsource_note_id: "' + ID + '"\n---')
        self.assertIn("xhs:" + ID, {k for u in urls for k in a.url_keys(u)})

    def test_old_url_index_rebuilt_once_for_existing_image_archive(self):
        class Gate:
            reads = 0

            def list_notes(self, folder, query):
                return {"ok": True}, ["_raw/old.md"] if folder == "_raw" else []

            def read(self, path):
                self.reads += 1
                return {"ok": True}, '---\nsource: "https://xhslink.cn/o/old"\nsource_note_id: "' + ID + '"\n---'

        with tempfile.TemporaryDirectory() as td, patch.object(a, "CACHE", Path(td)):
            (Path(td) / "vault_url_index.json").write_text(json.dumps({"_raw/old.md": ["url:xhslink.cn/o/old"]}), encoding="utf-8")
            gate = Gate()
            for _ in range(2):
                self.assertEqual(a.gate_lookup(gate, a.url_keys(URL))["hits"], ["_raw/old.md"])
            self.assertEqual(gate.reads, 1)

    def test_login_wrong_identity_and_video(self):
        self.assertEqual(a.xhs_content("请登录", URL)["kind"], "login_required")
        self.assertEqual(a.xhs_content(page(), URL[:-1] + "9")["kind"], "source_unavailable")
        self.assertEqual(a.xhs_content(page(type="video"), URL)["kind"], "unsupported_content")

    def test_short_text_note_and_unknown_date(self):
        r = a.xhs_content(page(images=0, time=0), URL)
        drafts = a.build_drafts(r["meta"], r["body"])
        self.assertEqual(r["images"], [])
        self.assertIn("published: null", drafts["raw"])
        self.assertIn("publication date unknown", drafts["ref"])

    def test_different_share_link_lookup_after_fetch(self):
        args = argparse.Namespace(url="https://xhslink.cn/o/new", fetch="ssh:test", gate="local",
                                  no_lookup=False, verify_wait=-1, work=None)
        r = a.xhs_content(page(), URL)
        with patch.object(a, "lookup", side_effect=[[], ["_raw/existing.md"]]), patch.object(a, "attempt", return_value=r):
            out = a.cmd_fetch(args)
        self.assertEqual(out["status"], "exists")

    def test_fetch_images_pauses_before_drafting_and_preserves_work(self):
        with tempfile.TemporaryDirectory() as td:
            args = argparse.Namespace(url=URL, fetch="ssh:test", no_lookup=True, verify_wait=-1, work=td)
            result = {**a.xhs_content(page(), URL), "via": "ssh:test"}
            with patch.object(a, "attempt", return_value=result):
                self.assertEqual(a.cmd_fetch(args)["status"], "needs_transcription")
                self.assertFalse((Path(td) / "raw.md").exists())
                self.assertFalse((Path(td) / "meta.json").exists())
                with self.assertRaises(a.Fail) as failed:
                    a.cmd_fetch(args)
                self.assertEqual(failed.exception.payload["status"], "work_in_use")

    def test_assemble_missing_page_then_valid_write_and_repeat(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            source = a.xhs_content(page(), URL)
            (work / "source.json").write_text(json.dumps(source), encoding="utf-8")
            args = argparse.Namespace(work_dir=td, gate="local")
            with self.assertRaises(a.Fail) as failed:
                a.cmd_assemble(args)
            self.assertEqual(failed.exception.payload["pages"], [1, 2])
            with self.assertRaises(a.Fail):
                a.validate(work)
            (work / "images").mkdir()
            (work / "pages").mkdir()
            for n in (1, 2):
                (work / f"images/{n:03d}.img").write_bytes(b"image")
                (work / f"pages/{n:03d}.md").write_text(f"Page {n}", encoding="utf-8")
            self.assertEqual(a.cmd_assemble(args)["status"], "drafted")
            info, raw, ref = a.validate(work)
            self.assertLess(raw.index("Page 1"), raw.index("Page 2"))
            self.assertIn("source page 2", raw)
            self.assertIn(info["raw_path"][:-3], ref)
            stored = {}

            def create(spec, req, timeout):
                if req["path"] in stored:
                    return {"ok": stored[req["path"]] == req["content"], "status": "existed" if stored[req["path"]] == req["content"] else "conflict"}
                stored[req["path"]] = req["content"]
                return {"ok": True, "status": "created"}

            with patch.object(a, "gate_call", side_effect=create):
                self.assertEqual(a.cmd_write(args)["results"]["raw"]["status"], "created")
                self.assertEqual(a.cmd_write(args)["results"]["raw"]["status"], "existed")
                self.assertEqual(len(stored), 2)
                (work / "raw.md").write_text(raw + "changed", encoding="utf-8")
                with self.assertRaises(a.Fail) as conflict:
                    a.cmd_write(args)
                self.assertEqual(conflict.exception.payload["status"], "conflict")

    def test_download_rejects_login_html(self):
        with tempfile.TemporaryDirectory() as td:
            source = a.xhs_content(page(), URL)
            source["via"] = "ssh:test"
            (Path(td) / "source.json").write_text(json.dumps(source), encoding="utf-8")
            with patch.object(a, "remote_os", return_value="posix"), patch.object(a.subprocess, "run", return_value=argparse.Namespace(returncode=0, stdout=b"<html>login</html>")):
                with self.assertRaises(a.Fail) as failed:
                    a.cmd_images(argparse.Namespace(work_dir=td, fetch=None))
            self.assertEqual(failed.exception.payload["status"], "image_failed")

    def test_wechat_existing_paths(self):
        html = '<div id="js_content"></div><meta property="og:title" content="Title">'
        url = "https://mp.weixin.qq.com/s/abcdefgh"
        with patch.object(a, "defuddle", return_value="正文" * 200):
            r = a.process({"http": 200, "html": html}, url)
        self.assertEqual(r["kind"], "article")
        self.assertEqual(r["chars"], 400)
        deleted = a.process({"http": 200, "html": "该内容已被发布者删除"}, url)
        self.assertEqual(deleted["kind"], "deleted")
        self.assertIn("wx:s:abcdefgh", a.url_keys(url))


if __name__ == "__main__":
    unittest.main()

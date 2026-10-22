"""Offline behavior checks; no real vault or network writes."""
import argparse
import importlib.util
import json
import os
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
    def test_ingest_text_writes_both_notes_and_duplicate_stops_before_fetch(self):
        with tempfile.TemporaryDirectory() as td:
            args = argparse.Namespace(url="https://mp.weixin.qq.com/s/abcdefgh", fetch="ssh:test", gate="local",
                                      no_lookup=False, verify_wait=-1, work=None, image_fetch=None)
            meta = {"title": "Title", "account": "Author", "byline": "", "published": 1792071968, "link": args.url}
            result = {"kind": "article", "meta": meta, "body": "Text body", "chars": 9, "via": "ssh:test"}
            stored = {}

            def gate(spec, req, timeout=1800):
                if req["op"] == "lookup":
                    return {"ok": True, "hits": list(stored)}
                stored[req["path"]] = req["content"]
                return {"ok": True, "status": "created"}

            with patch.dict(os.environ, {"ARTICLE_INGEST_WORK_ROOT": td}), patch.object(a, "gate_call", side_effect=gate), patch.object(a, "attempt", return_value=result) as fetch:
                out = a.cmd_ingest(args)
                self.assertEqual(out["status"], "written")
                self.assertEqual(Path(out["work_dir"]).parent, Path(td))
                self.assertEqual(len(stored), 2)
                self.assertEqual(a.cmd_ingest(args)["status"], "exists")
                self.assertEqual(fetch.call_count, 1)

    def test_default_work_is_local_archive_outside_cache(self):
        with tempfile.TemporaryDirectory() as td, patch.object(a.Path, "home", return_value=Path(td)), patch.dict(os.environ):
            os.environ.pop("ARTICLE_INGEST_WORK_ROOT", None)
            args = argparse.Namespace(url=URL, fetch="ssh:test", no_lookup=True, verify_wait=-1, work=None)
            with patch.object(a, "attempt", return_value={**a.xhs_content(page(), URL), "via": "ssh:test"}):
                out = a.cmd_fetch(args)
            self.assertEqual(Path(out["work_dir"]).parent, Path(td) / "article_archive")

    def test_ingest_images_transcribes_assembles_and_writes(self):
        with tempfile.TemporaryDirectory() as td:
            args = argparse.Namespace(url=URL, fetch="ssh:test", gate="local", no_lookup=True,
                                      verify_wait=-1, work=td, image_fetch="ssh:images")
            result = {**a.xhs_content(page(), URL), "via": "ssh:test"}
            image = b"\x89PNG\r\n\x1a\nimage"
            stored = {}

            def create(spec, req, timeout):
                stored[req["path"]] = req["content"]
                return {"ok": True, "status": "created"}

            with patch.object(a, "attempt", return_value=result), patch.object(a, "remote_os", return_value="posix"), patch.object(a.subprocess, "run", return_value=argparse.Namespace(returncode=0, stdout=image)), patch.object(a, "transcribe_image", side_effect=["Page 1", "Page 2"]), patch.object(a, "gate_call", side_effect=create):
                out = a.cmd_ingest(args)
            self.assertEqual(out["status"], "written")
            self.assertEqual(len(stored), 2)
            raw = stored[out["raw_path"]]
            self.assertLess(raw.index("Page 1"), raw.index("Page 2"))
            self.assertEqual((Path(td) / "images/002.img").read_bytes(), image)
            self.assertEqual((Path(td) / "pages/002.md").read_text(encoding="utf-8").strip(), "Page 2")

    def test_transcription_failure_resumes_only_missing_pages_and_never_writes_early(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            source = {**a.xhs_content(page(), URL), "via": "ssh:test"}
            (work / "source.json").write_text(json.dumps(source), encoding="utf-8")
            (work / "images").mkdir()
            for item in source["images"]:
                (work / item["file"]).write_bytes(b"image")
            args = argparse.Namespace(work_dir=td, gate="local", image_fetch=None, draft_only=True)
            with patch.object(a, "transcribe_image", side_effect=["First", a.Fail(1, {"status": "transcription_failed"})]), patch.object(a, "cmd_write") as write:
                with self.assertRaises(a.Fail) as failed:
                    a.cmd_resume(args)
                self.assertEqual(failed.exception.payload["page"], 2)
                self.assertFalse((work / "meta.json").exists())
                write.assert_not_called()
            with patch.object(a, "transcribe_image", return_value="Second") as model, patch.object(a, "attempt", side_effect=AssertionError("must not fetch")):
                self.assertEqual(a.cmd_resume(args)["status"], "drafted")
                model.assert_called_once_with(work / "images/002.img")
            self.assertEqual((work / "pages/001.md").read_text(encoding="utf-8"), "First\n")

    def test_resume_existing_draft_preserves_exact_bytes_for_partial_write(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            meta = a.xhs_content(page(images=0), URL)["meta"]
            draft = a.build_drafts(meta, "Body")
            for name in ("raw", "ref"):
                (work / f"{name}.md").write_text(draft[name], encoding="utf-8")
            (work / "meta.json").write_text(json.dumps({**meta, "raw_path": draft["raw_path"], "ref_path": draft["ref_path"]}), encoding="utf-8")
            args = argparse.Namespace(work_dir=td, gate="local", draft_only=False)
            with patch.object(a, "cmd_assemble", side_effect=AssertionError("must preserve draft")), patch.object(a, "gate_call", return_value={"ok": True, "status": "existed"}) as gate:
                self.assertEqual(a.cmd_resume(args)["status"], "written")
                self.assertEqual(gate.call_args_list[0].args[1]["content"], draft["raw"])

    def test_manual_pause_is_explicit_and_draft_only_does_not_write(self):
        with tempfile.TemporaryDirectory() as td:
            args = argparse.Namespace(work_dir=td, gate="local", manual_transcription=True, draft_only=False, image_fetch=None)
            with patch.object(a, "cmd_fetch", return_value={"status": "needs_transcription", "work_dir": td}), patch.object(a, "cmd_images"), patch.object(a, "cmd_transcribe") as model, patch.object(a, "cmd_write") as write:
                self.assertEqual(a.cmd_ingest(args)["status"], "needs_transcription")
                model.assert_not_called()
                write.assert_not_called()
            args.manual_transcription = False
            args.draft_only = True
            with patch.object(a, "cmd_fetch", return_value={"status": "drafted", "work_dir": td}), patch.object(a, "validate") as validate, patch.object(a, "cmd_write") as write:
                self.assertEqual(a.cmd_ingest(args)["status"], "drafted")
                validate.assert_called_once_with(Path(td))
                write.assert_not_called()

    def test_model_transport_reads_structured_final_response_and_retains_diagnostics(self):
        with tempfile.TemporaryDirectory() as td:
            image = Path(td) / "images/001.img"
            image.parent.mkdir()
            image.write_bytes(b"image")

            def launch(command, **kwargs):
                self.assertIn(str(image.resolve()), command)
                schema = json.loads(Path(command[command.index("--output-schema") + 1]).read_text(encoding="utf-8"))
                self.assertEqual(schema["required"], ["text", "unreadable"])
                output = Path(command[command.index("--output-last-message") + 1])
                output.write_text(json.dumps({"text": "原文 α = 1", "unreadable": False}), encoding="utf-8")
                return argparse.Namespace(wait=lambda timeout: 0)

            with patch.object(a, "find_codex", return_value="codex"), patch.object(a.subprocess, "Popen", side_effect=launch):
                self.assertEqual(a.transcribe_image(image), "原文 α = 1")
            self.assertTrue((Path(td) / "transcription/001.log").is_file())

    def test_model_unreadable_empty_invalid_and_failed_results_are_not_saved_as_pages(self):
        with tempfile.TemporaryDirectory() as td:
            image = Path(td) / "images/001.img"
            image.parent.mkdir()
            image.write_bytes(b"image")
            for payload, code in [('{"text":"guess","unreadable":true}', 0), ('{"text":"","unreadable":false}', 0), ('not json', 0), ('[]', 0), ('{}', 1)]:
                def launch(command, **kwargs):
                    Path(command[command.index("--output-last-message") + 1]).write_text(payload, encoding="utf-8")
                    return argparse.Namespace(wait=lambda timeout: code)
                with patch.object(a, "find_codex", return_value="codex"), patch.object(a.subprocess, "Popen", side_effect=launch):
                    with self.assertRaises(a.Fail) as failed:
                        a.transcribe_image(image)
                    self.assertEqual(failed.exception.payload["status"], "transcription_failed")

    def test_ingest_download_failure_preserves_resume_location(self):
        with tempfile.TemporaryDirectory() as td:
            args = argparse.Namespace(url=URL, fetch="ssh:test", gate="local", no_lookup=True,
                                      verify_wait=-1, work=td, image_fetch=None)
            with patch.object(a, "attempt", return_value={**a.xhs_content(page(), URL), "via": "ssh:test"}), patch.object(a, "cmd_images", side_effect=a.Fail(1, {"status": "image_failed", "page": 2})):
                with self.assertRaises(a.Fail) as failed:
                    a.cmd_ingest(args)
            self.assertEqual(failed.exception.payload["work_dir"], td)
            self.assertEqual(failed.exception.payload["page"], 2)
            self.assertTrue((Path(td) / "source.json").is_file())

    def test_ingest_partial_write_resumes_without_fetching_again(self):
        with tempfile.TemporaryDirectory() as td:
            args = argparse.Namespace(url=URL, fetch="ssh:test", gate="local", no_lookup=True,
                                      verify_wait=-1, work=td, image_fetch=None)
            result = {**a.xhs_content(page(images=0), URL), "via": "ssh:test"}
            stored = {}
            fail_ref = True

            def create(spec, req, timeout):
                if req["path"].startswith("2-Zettelkasten") and fail_ref:
                    return {"ok": False, "status": "unreachable"}
                existed = req["path"] in stored
                stored[req["path"]] = req["content"]
                return {"ok": True, "status": "existed" if existed else "created"}

            with patch.object(a, "attempt", return_value=result), patch.object(a, "gate_call", side_effect=create):
                with self.assertRaises(a.Fail) as failed:
                    a.cmd_ingest(args)
                self.assertEqual(failed.exception.code, 2)
                self.assertEqual(failed.exception.payload["work_dir"], td)
                self.assertEqual(len(stored), 1)
                fail_ref = False
                out = a.cmd_write(argparse.Namespace(work_dir=td, gate="local"))
            self.assertEqual(out["results"]["raw"]["status"], "existed")
            self.assertEqual(out["results"]["ref"]["status"], "created")

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

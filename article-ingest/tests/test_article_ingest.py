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
REAL_REVIEW_BATCH = a.review_batch


def review_result(entries, context, record):
    return {"pages": [{"page": e["page"], "text": e["ocr"] or f"Repaired {e['page']}",
                       "unreadable": False, "join_previous": False, "join_separator": "", "changes": []} for e in entries]}


def page(images=2, **extra):
    note = {"noteId": ID, "type": "normal", "title": "Sample", "desc": "undefined 正文",
            "user": {"nickName": "Author"}, "time": 1792071968000,
            "imageList": [{"url": f"https://example.com/{n}.jpg"} for n in range(images)], **extra}
    return '<script>window.__INITIAL_STATE__=' + json.dumps({"note": {"noteDetailMap": {ID: {"note": note}}}})[:-1] + ',"unused":undefined}</script>'


class IngestTests(unittest.TestCase):
    def setUp(self):
        real_find = a.importlib.util.find_spec
        patcher = patch.object(a.importlib.util, "find_spec", side_effect=lambda name: True if name == "rapidocr" else real_find(name))
        patcher.start()
        self.addCleanup(patcher.stop)
        # Every offline test denies the real model transport unless it mocks subprocess explicitly.
        reviewer = patch.object(a, "review_batch", side_effect=review_result)
        self.review_mock = reviewer.start()
        self.addCleanup(reviewer.stop)

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
                self.review_mock.assert_not_called()

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
            self.assertEqual(self.review_mock.call_count, 1)
            self.assertEqual(out["review_version"], a.REVIEW_VERSION)

    def test_ocr_failure_enters_review_and_resume_keeps_completed_work(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            source = {**a.xhs_content(page(), URL), "via": "ssh:test"}
            (work / "source.json").write_text(json.dumps(source), encoding="utf-8")
            (work / "images").mkdir()
            for item in source["images"]:
                (work / item["file"]).write_bytes(b"image")
            args = argparse.Namespace(work_dir=td, gate="local", image_fetch=None, draft_only=True)
            self.review_mock.side_effect = a.Fail(1, {"status": "review_failed"})
            with patch.object(a, "transcribe_image", side_effect=["First", a.Fail(1, {"status": "transcription_failed"})]), patch.object(a, "cmd_write") as write:
                with self.assertRaises(a.Fail) as failed:
                    a.cmd_resume(args)
                self.assertEqual(failed.exception.payload["pages"], [1, 2])
                self.assertFalse((work / "meta.json").exists())
                write.assert_not_called()
            self.review_mock.side_effect = review_result
            with patch.object(a, "transcribe_image", side_effect=AssertionError("keep OCR success/failure evidence")), patch.object(a, "attempt", side_effect=AssertionError("must not fetch")):
                self.assertEqual(a.cmd_resume(args)["status"], "drafted")
            self.assertEqual((work / "pages/001.md").read_text(encoding="utf-8"), "First\n")
            self.assertEqual((work / "reviewed/002.md").read_text(encoding="utf-8"), "Repaired 2\n")

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

    def test_ocr_keeps_recognition_evidence_without_launching_processes(self):
        with tempfile.TemporaryDirectory() as td:
            image = Path(td) / "images/001.img"
            image.parent.mkdir()
            image.write_bytes(b"image")
            result = argparse.Namespace(txts=["原文 OCR 123", "下一行"], scores=[0.99, 0.97], boxes=None)
            with patch.object(a, "get_ocr", return_value=lambda path: result), patch.object(a.subprocess, "Popen", side_effect=AssertionError("no agent/process")):
                self.assertEqual(a.transcribe_image(image), "原文 OCR 123\n下一行")
            evidence = json.loads((Path(td) / "transcription/001.json").read_text(encoding="utf-8"))
            self.assertEqual(evidence["engine"], "rapidocr")
            self.assertEqual(evidence["low_confidence_lines"], [])

    def test_ocr_empty_low_confidence_and_corrupt_image_stop_with_diagnostics(self):
        with tempfile.TemporaryDirectory() as td:
            image = Path(td) / "images/001.img"
            image.parent.mkdir()
            image.write_bytes(b"image")
            for lines, scores in [([], []), (["uncertain"], [0.2]), (["∑ x_i"], [0.99])]:
                result = argparse.Namespace(txts=lines, scores=scores, boxes=None)
                with patch.object(a, "get_ocr", return_value=lambda path: result):
                    with self.assertRaises(a.Fail) as failed:
                        a.transcribe_image(image)
                self.assertEqual(failed.exception.payload["status"], "transcription_failed")
                self.assertTrue((Path(td) / "transcription/001.json").is_file())
            with patch.object(a, "get_ocr", side_effect=ValueError("bad image")):
                with self.assertRaises(a.Fail) as failed:
                    a.transcribe_image(image)
            self.assertIn("bad image", failed.exception.payload["detail"])

    def test_ocr_override_rejects_commands_and_missing_executables(self):
        for value in ("python --model chat", "missing-python"):
            with patch.dict(os.environ, {"ARTICLE_INGEST_OCR_PYTHON": value}):
                with self.assertRaises(a.Fail) as failed:
                    a.ocr_python()
            self.assertEqual(failed.exception.payload["status"], "ocr_missing")

    def test_ocr_worker_relays_page_failure_with_one_python_call(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            (work / "source.json").write_text(json.dumps({"images": [{"page": 7}]}), encoding="utf-8")
            payload = {"ok": False, "status": "transcription_failed", "page": 7, "work_dir": td}
            with patch.object(a, "ocr_python", return_value=str(work / "python.exe")), patch.object(a.subprocess, "run", return_value=argparse.Namespace(returncode=1, stdout=json.dumps(payload).encode())) as run:
                with self.assertRaises(a.Fail) as failed:
                    a.cmd_transcribe(argparse.Namespace(work_dir=td))
            self.assertEqual(failed.exception.payload["page"], 7)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][1], "-B")
            self.assertEqual(run.call_args.args[0][-2], "transcribe")

    def test_saved_pages_need_no_ocr_installation(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            (work / "source.json").write_text(json.dumps({"images": [{"page": 1}]}), encoding="utf-8")
            (work / "pages").mkdir()
            (work / "pages/001.md").write_text("manually repaired text", encoding="utf-8")
            with patch.object(a, "ocr_python", side_effect=AssertionError("do not require OCR for saved pages")):
                self.assertEqual(a.cmd_transcribe(argparse.Namespace(work_dir=td))["status"], "transcribed")

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
            self.assertEqual(failed.exception.payload["page"], 1)
            with self.assertRaises(a.Fail):
                a.validate(work)
            (work / "images").mkdir()
            (work / "pages").mkdir()
            for n in (1, 2):
                (work / f"images/{n:03d}.img").write_bytes(b"image")
                (work / f"pages/{n:03d}.md").write_text(f"Page {n}", encoding="utf-8")
            with self.assertRaises(a.Fail) as failed:
                a.cmd_assemble(args)
            self.assertEqual(failed.exception.payload["pages"], [1, 2])
            a.cmd_review(args)
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
                stored[info["raw_path"]] = "a different existing note"
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

    def prepare_review(self, work, count=2):
        source = {**a.xhs_content(page(images=count), URL), "via": "ssh:test"}
        a.save_json(work / "source.json", source)
        (work / "images").mkdir()
        (work / "pages").mkdir()
        for n in range(1, count + 1):
            (work / f"images/{n:03d}.img").write_bytes(b"image")
            (work / f"pages/{n:03d}.md").write_text(f"OCR {n}", encoding="utf-8")
        return argparse.Namespace(work_dir=str(work), gate="isolated", draft_only=False)

    def test_review_repairs_markdown_and_cross_page_prose_then_partial_write_is_exact(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            args = self.prepare_review(work)
            self.review_mock.side_effect = lambda *args: {"pages": [
                {"page": 1, "text": "## 标题\n\n| A | B |\n|---|---|\n| 1 | ↑ |\n\n跨页", "unreadable": False, "join_previous": False, "join_separator": "", "changes": ["修正高置信箭头错字"]},
                {"page": 2, "text": "接续。\n\n$$x=\\frac{1}{2}$$", "unreadable": False, "join_previous": True, "join_separator": "", "changes": []}]}
            a.cmd_review(args)
            a.cmd_assemble(args)
            original = (work / "raw.md").read_bytes()
            self.assertIn("跨页<!-- source page 2 -->接续", original.decode())
            self.assertIn("| 1 | ↑ |", original.decode())
            self.assertEqual((work / "pages/001.md").read_text(), "OCR 1")
            stored = {}
            fail_ref = True

            def gate(spec, req, timeout):
                if req["path"].startswith("2-") and fail_ref:
                    return {"ok": False, "status": "unreachable"}
                previous = stored.setdefault(req["path"], req["content"])
                return {"ok": previous == req["content"], "status": "existed"}

            with patch.object(a, "gate_call", side_effect=gate):
                with self.assertRaises(a.Fail):
                    a.cmd_write(args)
                fail_ref = False
                with patch.object(a, "cmd_review", side_effect=AssertionError("no repeat review")), patch.object(a, "cmd_assemble", side_effect=AssertionError("no regeneration")):
                    self.assertEqual(a.cmd_resume(args)["status"], "written")
            self.assertEqual((work / "raw.md").read_bytes(), original)
            self.assertEqual(len(stored), 2)

    def test_review_rejects_missing_duplicate_empty_unreadable_and_keeps_good_pages(self):
        bad_rows = [[], [{"page": 1}, {"page": 1}],
                    [{"page": n, "text": "", "unreadable": False, "join_previous": False, "join_separator": "", "changes": []} for n in (1, 2)],
                    [{"page": n, "text": "Text", "unreadable": n == 2, "join_previous": False, "join_separator": "", "changes": []} for n in (1, 2)]]
        for rows in bad_rows:
            with self.subTest(rows=rows), tempfile.TemporaryDirectory() as td:
                args = self.prepare_review(Path(td))
                self.review_mock.side_effect = lambda *args: {"pages": rows}
                with self.assertRaises(a.Fail) as failed:
                    a.cmd_review(args)
                self.assertEqual(failed.exception.payload["status"], "review_failed")
                with self.assertRaises(a.Fail):
                    a.cmd_assemble(args)
                self.assertFalse((Path(td) / "meta.json").exists())
                if len(rows) == 2 and rows[-1].get("unreadable"):
                    self.review_mock.side_effect = review_result
                    a.cmd_review(args)
                    self.assertEqual([e["page"] for e in self.review_mock.call_args.args[0]], [2])

    def test_review_resume_batches_and_forced_failure_invalidates_previous_pass(self):
        with tempfile.TemporaryDirectory() as td:
            args = self.prepare_review(Path(td), 8)
            def review(entries, context, record):
                if entries[0]["page"] == 7:
                    raise a.Fail(1, {"status": "review_failed"})
                return review_result(entries, context, record)
            self.review_mock.side_effect = review
            with self.assertRaises(a.Fail):
                a.cmd_review(args)
            self.review_mock.side_effect = review_result
            a.cmd_review(args)
            self.assertEqual([e["page"] for e in self.review_mock.call_args.args[0]], [7, 8])
            self.assertEqual(self.review_mock.call_args.args[1]["page"], 6)
            args.repair_pages = [2]
            self.review_mock.side_effect = a.Fail(1, {"status": "review_failed"})
            with self.assertRaises(a.Fail):
                a.cmd_review(args)
            with self.assertRaises(a.Fail) as failed:
                a.cmd_assemble(args)
            self.assertEqual(failed.exception.payload["pages"], [2])

    def test_image_ocr_reviewed_and_raw_changes_invalidate_quality_evidence(self):
        for target in ("images/001.img", "pages/001.md", "reviewed/001.md", "raw.md"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as td:
                work = Path(td)
                args = self.prepare_review(work)
                a.cmd_review(args)
                a.cmd_assemble(args)
                (work / target).write_text("changed", encoding="utf-8")
                with patch.object(a, "gate_call") as gate, self.assertRaises(a.Fail):
                    a.cmd_write(args)
                gate.assert_not_called()

    def test_legacy_image_draft_is_preserved_and_cannot_bypass_review(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            args = self.prepare_review(work)
            source = a.read_json(work / "source.json")
            draft = a.build_drafts({**source["meta"], "image_count": 2}, "old OCR")
            a.save_json(work / "meta.json", {**source["meta"], "image_count": 2,
                                           "raw_path": draft["raw_path"], "ref_path": draft["ref_path"]})
            for name in ("raw", "ref"):
                (work / f"{name}.md").write_text(draft[name], encoding="utf-8")
            original = (work / "raw.md").read_bytes()
            for command in (a.cmd_resume, a.cmd_write, a.cmd_review, a.cmd_assemble):
                with self.assertRaises(a.Fail):
                    command(args)
            self.assertEqual((work / "raw.md").read_bytes(), original)
            self.review_mock.assert_not_called()

    def test_fixed_layout_signals_do_not_treat_confidence_as_completeness(self):
        boxes = [[[x, y], [x + 20, y], [x + 20, y + 10], [x, y + 10]] for y in (0, 30) for x in (0, 60)]
        self.assertIn("table_or_columns", a.review_reasons(["甲", "乙", "丙", "丁"], [0.99] * 4, boxes))
        self.assertIn("formula", a.review_reasons(["∑ x"], [0.99], []))

    def test_cross_page_english_word_and_word_boundary_use_explicit_separator(self):
        for previous, following, separator, expected in (("con", "tinuous", "", "continuous"), ("two", "words", " ", "two words")):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as td:
                work = Path(td)
                args = self.prepare_review(work)
                self.review_mock.side_effect = lambda *args: {"pages": [
                    {"page": n, "text": text, "unreadable": False, "join_previous": n == 2,
                     "join_separator": separator if n == 2 else "", "changes": []}
                    for n, text in ((1, previous), (2, following))]}
                a.cmd_review(args)
                body = a.reviewed_body(work, a.read_json(work / "source.json"))
                self.assertIn(expected, body.replace("<!-- source page 2 -->", ""))

    def test_review_transport_nonzero_and_invalid_json_do_not_produce_passed_pages(self):
        import io
        for exit_code, output in ((1, None), (0, "not json")):
            with self.subTest(exit_code=exit_code), tempfile.TemporaryDirectory() as td:
                work = Path(td)
                args = self.prepare_review(work)
                class Process:
                    pid = 123
                    stdin = io.BytesIO()
                    def wait(self, timeout):
                        if output is not None:
                            next(work.glob("review/batch_*" )).joinpath("output.json").write_text(output)
                        return exit_code
                self.review_mock.side_effect = REAL_REVIEW_BATCH
                with patch.object(a, "find_review_codex", return_value="codex"), patch.object(a.subprocess, "Popen", return_value=Process()):
                    with self.assertRaises(a.Fail) as failed:
                        a.cmd_review(args)
                self.assertEqual(failed.exception.payload["status"], "review_failed")
                self.assertFalse((work / "review/001.json").exists())
                attempt = a.read_json(next(work.glob("review/batch_*/attempt.json")))
                self.assertEqual(attempt["model_calls"], 1)
                self.assertEqual(attempt["status"], "failed")

    def test_review_transport_uses_one_structured_batch_and_retains_actual_invocation(self):
        import io
        with tempfile.TemporaryDirectory() as td:
            record = Path(td) / "call"
            entries = [{"page": n, "image": str(Path(td) / f"{n}.png"), "ocr": "text", "reasons": []} for n in (1, 2)]
            class Process:
                pid = 123
                stdin = io.BytesIO()
                def wait(self, timeout):
                    a.save_json(record / "output.json", review_result(entries, None, record))
                    return 0
            with patch.object(a, "find_review_codex", return_value="codex"), patch.object(a.subprocess, "Popen", return_value=Process()) as popen:
                result = REAL_REVIEW_BATCH(entries, None, record)
            command = popen.call_args.args[0]
            self.assertEqual(command.count("--image"), 2)
            self.assertIn("--ignore-user-config", command)
            self.assertIn("features.shell_tool=false", command)
            self.assertEqual(len(result["pages"]), 2)
            self.assertTrue((record / "invocation.json").is_file())
            self.assertTrue((record / "prompt.txt").is_file())

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

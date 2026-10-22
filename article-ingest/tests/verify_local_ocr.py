"""Optional real-image acceptance run with network/process denial and a stateful isolated vault.

Run with the installed OCR Python:
  python -B verify_local_ocr.py --source DIR [--source DIR ...] --work NEW_DIR
Each source contains source.json + images/; only these inputs are copied, never old page text.
Original-site fetching/download is replaced by local input; OCR/assemble/validate/write are real.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("ingest", Path(__file__).parents[1] / "scripts/article_ingest.py")
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--work", required=True)
    args = parser.parse_args()
    root = Path(args.work).expanduser()
    root.mkdir(parents=True, exist_ok=False)
    evidence = {"boundary": "original-site inputs reused; real local OCR and draft/write pipeline; isolated create-only gate",
                "events": [], "articles": [], "python": sys.version, "agent_calls": 0}

    def audit(event, values):
        if event in ("subprocess.Popen", "os.system", "os.posix_spawn", "socket.connect", "socket.getaddrinfo"):
            evidence["events"].append({"event": event, "detail": str(values)[:300]})
            raise RuntimeError("process/network disabled for acceptance: " + event)

    sys.addaudithook(audit)
    os.environ["ARTICLE_INGEST_OCR_PYTHON"] = sys.executable
    os.environ["ARTICLE_INGEST_CODEX"] = str(root / "disabled-agent")
    os.environ["OPENAI_API_KEY"] = "disabled"
    os.environ["ANTHROPIC_API_KEY"] = "disabled"
    for number, source_dir in enumerate(args.source, 1):
        source_dir = Path(source_dir).expanduser()
        source = json.loads((source_dir / "source.json").read_text(encoding="utf-8"))
        fetched = {**source, "kind": "xhs", "via": "local-input"}
        work = root / str(number)
        stored, fail_ref = {}, True

        def gate(spec, req, timeout=1800):
            nonlocal fail_ref
            if req["op"] == "lookup":
                return {"ok": True, "hits": list(stored)}
            if req["path"].startswith("2-Zettelkasten") and fail_ref:
                return {"ok": False, "status": "unreachable"}
            previous = stored.get(req["path"])
            if previous is not None:
                return {"ok": previous == req["content"], "status": "existed" if previous == req["content"] else "conflict"}
            stored[req["path"]] = req["content"]
            return {"ok": True, "status": "created"}

        def images(step):
            shutil.copytree(source_dir / "images", work / "images", dirs_exist_ok=True)
            return {"ok": True, "status": "images_ready"}

        ingest_args = argparse.Namespace(url=source["meta"]["link"], fetch="local-input", gate="isolated",
                                         no_lookup=False, verify_wait=-1, work=str(work), image_fetch=None)
        started = time.monotonic()
        with patch.object(a, "attempt", return_value=fetched), patch.object(a, "cmd_images", side_effect=images), patch.object(a, "gate_call", side_effect=gate):
            try:
                a.cmd_ingest(ingest_args)
                raise AssertionError("injected REF failure was not observed")
            except a.Fail as error:
                assert error.payload["status"] == "unreachable", error.payload
            elapsed = time.monotonic() - started
            info, raw, ref = a.validate(work)
            assert len(stored) == 1 and stored[info["raw_path"]] == raw
            fail_ref = False
            step = argparse.Namespace(work_dir=str(work), gate="isolated", draft_only=False)
            result = a.cmd_resume(step)
            assert result["results"]["raw"]["status"] == "existed"
            assert result["results"]["ref"]["status"] == "created"
            assert stored[info["raw_path"]] == raw
            assert a.cmd_resume(step)["results"]["ref"]["status"] == "existed"
            assert a.cmd_ingest(ingest_args)["status"] == "exists"
            assert len(stored) == 2
            assert "topics:\n" in ref and "**一句话**：\n\n" in ref
            assert raw.count("<!-- source page ") == len(source["images"])
            (work / "raw.md").write_text(raw + "conflicting change", encoding="utf-8")
            try:
                a.cmd_write(step)
                raise AssertionError("different bytes must conflict")
            except a.Fail as error:
                assert error.payload["status"] == "conflict"
            (work / "raw.md").write_text(raw, encoding="utf-8")
        # Missing transcription is caught before assembling; restore exact original result.
        last = work / "pages" / f"{len(source['images']):03d}.md"
        data = last.read_bytes()
        last.unlink()
        try:
            a.cmd_assemble(step)
            raise AssertionError("missing page was accepted")
        except a.Fail as error:
            assert error.payload["pages"] == [len(source["images"])]
        last.write_bytes(data)
        hashes = {str(p.relative_to(work)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(work.glob("pages/*.md"))}
        a.cmd_transcribe(step)
        assert hashes == {str(p.relative_to(work)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(work.glob("pages/*.md"))}
        evidence["articles"].append({"title": info["title"], "pages": len(hashes), "seconds": round(elapsed, 3),
                                      "work": str(work), "page_sha256": hashes,
                                      "checks": ["REF failure after raw", "resume exact raw bytes", "repeat", "duplicate", "conflict", "missing page", "kept pages"]})
    evidence["ok"] = not evidence["events"]
    (root / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()

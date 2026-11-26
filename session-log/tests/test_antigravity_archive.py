from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).parents[1]
FIXTURE = Path(__file__).parent / "fixtures" / "antigravity_transcript.jsonl"
CODEX_FIXTURE = FIXTURE.with_name("codex_rollout.jsonl")
SESSION_ID = "12345678-1111-4abc-8111-123456789abc"
OTHER_ID = "aaaaaaaa-2222-4abc-8222-aaaaaaaaaaaa"
MISSING_ID = "bbbbbbbb-3333-4abc-8333-bbbbbbbbbbbb"


class AntigravityArchiveTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.env = os.environ.copy()
        self.env.update(
            HOME=str(self.root),
            USERPROFILE=str(self.root),
            CODEX_HOME=str(self.root / ".codex"),
            CODEX_THREAD_ID=OTHER_ID,
            ANTIGRAVITY_APP_DATA_DIR=str(self.root / "custom_agy"),
            ANTIGRAVITY_CONVERSATION_ID=MISSING_ID,
        )

    def run_script(self, script: str, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-B", str(SKILL_DIR / "scripts" / script), *args],
            env=self.env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def run_ok(self, script: str, *args: str) -> dict:
        result = self.run_script(script, *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def assert_times_error(self, error: str, *args: str) -> None:
        result = self.run_script("session_times.py", *args, "--save-temp")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(json.loads(result.stderr)["error"], error)

    def stage_transcript(self, uuid: str = SESSION_ID) -> Path:
        data_dir = Path(
            self.env.get("ANTIGRAVITY_APP_DATA_DIR", self.root / ".gemini/antigravity-cli")
        )
        path = data_dir / "brain" / uuid / ".system_generated/logs/transcript.jsonl"
        path.parent.mkdir(parents=True)
        shutil.copyfile(FIXTURE, path)
        return path

    def test_uuid_lookup_uses_override_and_ignores_unrelated_session_environment(self) -> None:
        path = self.stage_transcript()
        self.stage_transcript(OTHER_ID)
        rollout = self.root / ".codex/sessions/2026/08/13" / f"rollout-fixture-{OTHER_ID}.jsonl"
        rollout.parent.mkdir(parents=True)
        shutil.copyfile(CODEX_FIXTURE, rollout)

        result = self.run_ok("session_times.py", "--uuid", SESSION_ID.upper())
        self.assertEqual(result["transcript"], str(path))
        self.assertEqual(result["session_id"], SESSION_ID)
        self.assertEqual(result["source"], "antigravity")
        self.assertEqual(result["started_at"], "2026-08-13T15:58:00+00:00")
        self.assertEqual(result["last_active_at"], "2026-08-14T00:10:12.345000+08:00")
        self.assertEqual(result["date"], "2026-08-13")
        self.assertEqual(result["time"], "00:10")
        self.assertEqual(result["filename_ts"], "202608130010")
        self.assertFalse(result["fallback"])

        codex = self.run_ok("session_times.py", "--uuid", OTHER_ID)
        self.assertEqual(codex["transcript"], str(rollout))
        self.assertEqual(codex["source"], "codex")
        claude = self.root / ".claude/projects/example" / f"{SESSION_ID}.jsonl"
        claude.parent.mkdir(parents=True)
        claude.write_text('{"type":"user"}\n', encoding="utf-8")
        self.env["ANTIGRAVITY_CONVERSATION_ID"] = SESSION_ID
        self.assertEqual(
            self.run_ok("session_times.py", "--uuid", SESSION_ID)["transcript"], str(path)
        )
        if os.name == "nt":
            self.assertEqual(
                self.run_ok("session_times.py", "--transcript", str(path).upper())["session_id"],
                SESSION_ID,
            )
        self.env["ANTIGRAVITY_CONVERSATION_ID"] = OTHER_ID
        self.assertEqual(
            self.run_ok("session_times.py", "--transcript", str(path))["session_id"],
            SESSION_ID,
        )

    def test_default_root_and_explicit_copied_transcript(self) -> None:
        del self.env["ANTIGRAVITY_APP_DATA_DIR"]
        path = self.stage_transcript()
        self.assertEqual(
            self.run_ok("session_times.py", "--uuid", SESSION_ID)["transcript"], str(path)
        )
        copy = self.root / "export.jsonl"
        shutil.copyfile(path, copy)
        self.assert_times_error("session_uuid_required", "--transcript", str(copy))
        explicit = self.run_ok(
            "session_times.py", "--transcript", str(copy), "--uuid", SESSION_ID
        )
        self.assertEqual(explicit["source"], "antigravity")
        self.assertEqual(explicit["session_id"], SESSION_ID)
        self.assertEqual(explicit["transcript"], str(copy))

    def test_missing_or_invalid_transcripts_do_not_emit_archive_times(self) -> None:
        path = self.stage_transcript()
        claude = self.root / ".claude/projects/example" / f"{MISSING_ID}.jsonl"
        claude.parent.mkdir(parents=True)
        claude.write_text('{"type":"user"}\n', encoding="utf-8")
        self.assert_times_error("transcript_not_found", "--uuid", MISSING_ID)
        self.assert_times_error("transcript_not_found")
        self.assert_times_error(
            "transcript_uuid_mismatch", "--transcript", str(path), "--uuid", OTHER_ID
        )
        path.write_text(
            '{"type":"USER_INPUT","source":"SYSTEM_SDK","created_at":"2026-08-13T16:00:00Z",'
            '"content":"Synthetic"}\n{truncated\n',
            encoding="utf-8",
        )
        self.assert_times_error("antigravity_no_user_timestamps", "--uuid", SESSION_ID)
        unknown = self.root / "unknown.jsonl"
        unknown.write_text('{truncated\n{"type":[],"role":{}}\n', encoding="utf-8")
        self.assert_times_error(
            "transcript_unrecognized", "--transcript", str(unknown), "--uuid", SESSION_ID
        )

    def test_repeat_archive_uses_same_target_and_index_row(self) -> None:
        path = self.stage_transcript()
        log_dir = self.root / "archive"
        log_dir.mkdir()
        times = self.run_ok("session_times.py", "--uuid", SESSION_ID.upper(), "--save-temp")
        resolve_args = ("--uuid", times["session_id"], "--log-dir", str(log_dir))
        created = self.run_ok(
            "session_resolve.py", *resolve_args,
            "--times-json", times["times_json_path"], "--project", "claude_skills",
            "--slug", "agy_example",
        )
        self.assertEqual(created["mode"], "create")
        self.assertEqual(created["index_action"], "insert_row")
        target = Path(created["target_path"])
        target.write_text(f'---\nsession_id: "{times["session_id"]}"\n---\n', encoding="utf-8")
        index = log_dir / "index.md"
        heading = "| 日期 | 项目 | Session | 摘要 | Chat 标题建议 |\n|---|---|---|---|---|\n"
        index_row = f'| {times["date"]} | claude_skills | [Example]({target.name}) | first | title |'
        index.write_text(heading + index_row + "\n", encoding="utf-8")
        self.run_ok(
            "session_resolve.py", *resolve_args, "--register", "--file", target.name,
            "--started-at", times["started_at"],
        )

        with path.open("a", encoding="utf-8") as transcript:
            transcript.write("\n" + json.dumps({
                "type": "USER_INPUT", "source": "USER_EXPLICIT",
                "created_at": "2026-08-14T01:12:00+08:00", "content": "Follow-up",
            }) + "\n")
        updated_times = self.run_ok(
            "session_times.py", "--transcript", str(path), "--save-temp"
        )
        self.assertEqual(updated_times["session_id"], times["session_id"])
        self.assertEqual(updated_times["date"], times["date"])
        self.assertEqual(updated_times["time"], "01:12")
        self.assertNotEqual(updated_times["filename_ts"], times["filename_ts"])
        updated = self.run_ok(
            "session_resolve.py", *resolve_args, "--times-json", updated_times["times_json_path"]
        )
        self.assertEqual(updated["mode"], "update")
        self.assertEqual(updated["target_file"], target.name)
        self.assertEqual(updated["index_action"], "replace_row")
        self.assertEqual(updated["index_line_match"], index_row)
        index.write_text(
            index.read_text(encoding="utf-8").replace(
                updated["index_line_match"], index_row.replace("first", "updated")
            ),
            encoding="utf-8",
        )
        self.assertEqual(index.read_text(encoding="utf-8").count(f"({target.name})"), 1)

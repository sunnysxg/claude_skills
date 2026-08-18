from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "session_times.py"
SPEC = importlib.util.spec_from_file_location("session_times", MODULE_PATH)
assert SPEC and SPEC.loader
session_times = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(session_times)

LOCAL_TZ = timezone(timedelta(hours=8))
SESSION_ID = "13d9b15d-9217-42c4-885f-d1857c206df7"


class SessionTimesTest(unittest.TestCase):
    def write_jsonl(self, rows: list[dict]) -> Path:
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=f"-{SESSION_ID}.jsonl", delete=False, encoding="utf-8"
        )
        with handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        return Path(handle.name)

    def test_cursor_regression(self) -> None:
        path = self.write_jsonl(
            [
                {
                    "role": "user",
                    "message": {
                        "content": "<timestamp>Wednesday, Jul 8, 2026, 10:58 AM (UTC+8)</timestamp><user_query>run it</user_query>"
                    },
                }
            ]
        )
        self.addCleanup(path.unlink)

        result = session_times.compute_times(
            path,
            now=datetime(2026, 7, 9, tzinfo=LOCAL_TZ),
        )

        self.assertEqual(result["source"], "cursor")
        self.assertEqual(result["date"], "2026-07-08")
        self.assertEqual(result["time"], "10:58")
        self.assertFalse(result["fallback"])

    def test_claude_filters_synthetic_rows_and_pure_invocation(self) -> None:
        path = self.write_jsonl(
            [
                {"type": "mode", "sessionId": SESSION_ID},
                {
                    "type": "user",
                    "sessionId": SESSION_ID,
                    "timestamp": "2026-07-23T05:43:52.527Z",
                    "promptSource": "typed",
                    "message": {"role": "user", "content": "真实开始"},
                },
                {
                    "type": "user",
                    "sessionId": SESSION_ID,
                    "timestamp": "2026-07-23T06:00:00Z",
                    "isMeta": True,
                    "message": {"role": "user", "content": "Base directory for this skill: /tmp/x"},
                },
                {
                    "type": "user",
                    "sessionId": SESSION_ID,
                    "timestamp": "2026-07-23T07:00:00Z",
                    "message": {
                        "role": "user",
                        "content": [{"type": "tool_result", "content": "done"}],
                    },
                },
                {
                    "type": "user",
                    "sessionId": SESSION_ID,
                    "timestamp": "2026-07-23T08:00:00Z",
                    "promptSource": "system",
                    "message": {"role": "user", "content": "<task-notification>done</task-notification>"},
                },
                {
                    "type": "user",
                    "sessionId": SESSION_ID,
                    "timestamp": "2026-07-23T09:00:50.828Z",
                    "promptSource": "queued",
                    "message": {"role": "user", "content": "真实排队消息"},
                },
                {
                    "type": "user",
                    "sessionId": SESSION_ID,
                    "timestamp": "2026-07-23T09:30:00Z",
                    "promptSource": "sdk",
                    "message": {"role": "user", "content": "CCD 新版用户输入"},
                },
                {
                    "type": "user",
                    "sessionId": SESSION_ID,
                    "timestamp": "2026-07-23T10:00:00Z",
                    "promptSource": "typed",
                    "message": {"role": "user", "content": "/session-log"},
                },
            ]
        )
        self.addCleanup(path.unlink)

        result = session_times.compute_times(
            path,
            now=datetime(2026, 7, 24, tzinfo=LOCAL_TZ),
        )

        self.assertEqual(result["source"], "claude")
        self.assertEqual(result["date"], "2026-07-23")
        self.assertEqual(result["time"], "17:30")
        self.assertEqual(result["filename_ts"], "202607231730")
        self.assertFalse(result["fallback"])
        self.assertEqual(session_times.infer_uuid(path, "claude"), SESSION_ID)

    def test_pure_invocation_is_narrow(self) -> None:
        self.assertTrue(session_times.is_pure_session_log_invocation("/session-log"))
        self.assertTrue(session_times.is_pure_session_log_invocation("session-log"))
        self.assertTrue(
            session_times.is_pure_session_log_invocation(
                "<command-name>/session-log</command-name><command-args></command-args>"
            )
        )
        self.assertFalse(
            session_times.is_pure_session_log_invocation(
                "现在还有啥问题吗，没有的话就session-log一下。"
            )
        )

    def test_claude_synthetic_only_uses_fallback(self) -> None:
        path = self.write_jsonl(
            [
                {"type": "mode", "sessionId": SESSION_ID},
                {
                    "type": "user",
                    "sessionId": SESSION_ID,
                    "timestamp": "2026-07-23T05:00:00Z",
                    "promptSource": "system",
                    "message": {"role": "user", "content": "<system-reminder>x</system-reminder>"},
                },
            ]
        )
        self.addCleanup(path.unlink)
        now = datetime(2026, 7, 23, 12, 34, tzinfo=LOCAL_TZ)

        result = session_times.compute_times(path, now=now)

        self.assertTrue(result["fallback"])
        self.assertEqual(result["started_at"], now.isoformat())
        self.assertEqual(result["last_active_at"], now.isoformat())

    def test_codex_fixture_filters_synthetic_and_meta_rows(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "codex_rollout.jsonl"

        result = session_times.compute_times(
            fixture,
            now=datetime(2026, 8, 14, tzinfo=LOCAL_TZ),
        )

        self.assertEqual(result["source"], "codex")
        self.assertEqual(result["started_at"], "2026-08-13T01:00:00+00:00")
        self.assertEqual(result["last_active_at"], "2026-08-13T01:10:00+00:00")
        self.assertEqual(result["date"], "2026-08-13")
        self.assertEqual(result["time"], "09:10")
        self.assertEqual(result["filename_ts"], "202608130910")
        self.assertFalse(result["fallback"])
        self.assertEqual(session_times.infer_uuid(fixture, "codex"), SESSION_ID)

    def test_codex_delegation_and_narrow_meta_filters(self) -> None:
        self.assertFalse(
            session_times.is_codex_synthetic_part(
                "<codex_delegation><input>保留任务</input></codex_delegation>"
            )
        )
        self.assertTrue(session_times.is_pure_codex_meta_command("/session-log"))
        self.assertTrue(session_times.is_pure_codex_meta_command("/rename useful title"))
        self.assertTrue(session_times.is_pure_codex_meta_command("/handoff"))
        self.assertFalse(
            session_times.is_pure_codex_meta_command(
                "请修复 session-log，完成后再归档"
            )
        )
        self.assertFalse(
            session_times.is_codex_synthetic_part(
                "<recommended_plugins>x</recommended_plugins> 请继续真实任务"
            )
        )
        self.assertFalse(
            session_times.is_codex_synthetic_part(
                "# AGENTS.md instructions\n<INSTRUCTIONS>x</INSTRUCTIONS> 请修复"
            )
        )
        self.assertFalse(
            session_times.is_substantive_codex_user(
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "developer",
                        "content": [{"type": "input_text", "text": "NEW_TASK"}],
                    },
                }
            )
        )
        self.assertFalse(
            session_times.is_substantive_codex_user(
                {
                    "type": "response_item",
                    "payload": {
                        "type": "agent_message",
                        "message": "Message Type: FINAL_ANSWER",
                    },
                }
            )
        )

    def test_codex_subagent_transcript_is_not_root_activity(self) -> None:
        path = self.write_jsonl(
            [
                {
                    "timestamp": "2026-08-13T02:00:01Z",
                    "type": "session_meta",
                    "payload": {
                        "id": SESSION_ID,
                        "timestamp": "2026-08-13T02:00:00Z",
                        "thread_source": "subagent",
                        "source": {
                            "subagent": {
                                "thread_spawn": {"parent_thread_id": "parent-session"}
                            }
                        },
                    },
                },
                {
                    "timestamp": "2026-08-13T02:01:00Z",
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": "child task prompt"}
                        ],
                    },
                },
            ]
        )
        self.addCleanup(path.unlink)
        now = datetime(2026, 8, 13, 12, 34, tzinfo=LOCAL_TZ)

        result = session_times.compute_times(path, now=now)

        self.assertEqual(result["source"], "codex")
        self.assertTrue(result["fallback"])
        self.assertEqual(result["started_at"], "2026-08-13T02:00:00+00:00")
        self.assertEqual(result["last_active_at"], now.isoformat())

    def test_codex_uuid_lookup_matches_filename_not_contents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir)
            sessions = codex_home / "sessions" / "2026" / "08" / "13"
            sessions.mkdir(parents=True)
            target = sessions / f"rollout-2026-08-13T09-00-00-{SESSION_ID}.jsonl"
            target.write_text("{}\n", encoding="utf-8")
            decoy_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            decoy = sessions / f"rollout-2026-08-13T10-00-00-{decoy_id}.jsonl"
            decoy.write_text(json.dumps({"context": SESSION_ID}), encoding="utf-8")

            self.assertEqual(
                session_times.find_codex_transcript(SESSION_ID, codex_home), target
            )
            self.assertEqual(
                session_times.find_codex_transcript(SESSION_ID.upper(), codex_home),
                target,
            )

    def test_codex_started_at_uses_meta_matching_filename_uuid(self) -> None:
        parent_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        path = self.write_jsonl(
            [
                {
                    "timestamp": "2026-08-13T00:00:01Z",
                    "type": "session_meta",
                    "payload": {"id": parent_id, "timestamp": "2020-01-01T00:00:00Z"},
                },
                {
                    "timestamp": "2026-08-13T01:00:01Z",
                    "type": "session_meta",
                    "payload": {"id": SESSION_ID, "timestamp": "2026-08-13T01:00:00Z"},
                },
                {
                    "timestamp": "2026-08-13T01:05:00Z",
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "real task"}],
                    },
                },
            ]
        )
        self.addCleanup(path.unlink)

        result = session_times.compute_times(path)

        self.assertEqual(result["started_at"], "2026-08-13T01:00:00+00:00")

    def test_current_codex_thread_wins_over_other_client_same_uuid(self) -> None:
        codex = Path("codex.jsonl")
        with mock.patch.object(
            session_times, "find_codex_transcript", return_value=codex
        ), mock.patch.dict("os.environ", {"CODEX_THREAD_ID": SESSION_ID}):
            self.assertEqual(session_times.find_transcript(SESSION_ID, None), codex)


if __name__ == "__main__":
    unittest.main()

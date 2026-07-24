from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

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
        self.assertEqual(result["time"], "17:00")
        self.assertEqual(result["filename_ts"], "202607231700")
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


if __name__ == "__main__":
    unittest.main()

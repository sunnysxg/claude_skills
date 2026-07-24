from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "auto_rename_on_stop.py"
SPEC = importlib.util.spec_from_file_location("auto_rename_on_stop", MODULE_PATH)
assert SPEC and SPEC.loader
auto_rename = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(auto_rename)


class AutoRenameOnStopTest(unittest.TestCase):
    def write_jsonl(self, rows: list[dict]) -> Path:
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        )
        with handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return Path(handle.name)

    @mock.patch.object(auto_rename, "send_rename_via_tmux", return_value=True)
    def test_claude_uses_last_assistant_message(self, send: mock.Mock) -> None:
        payload = {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": "归档完成\n/rename 260723 Claude等待提醒",
        }

        self.assertTrue(auto_rename.process_payload(payload, "%1"))
        send.assert_called_once_with("%1", "/rename 260723 Claude等待提醒")

    @mock.patch.object(auto_rename, "send_rename_via_tmux")
    def test_stop_hook_active_prevents_recursion(self, send: mock.Mock) -> None:
        payload = {
            "hook_event_name": "Stop",
            "stop_hook_active": True,
            "last_assistant_message": "/rename should-not-run",
        }

        self.assertFalse(auto_rename.process_payload(payload, "%1"))
        send.assert_not_called()

    @mock.patch.object(auto_rename, "send_rename_via_tmux", return_value=True)
    def test_claude_transcript_fallback(self, send: mock.Mock) -> None:
        path = self.write_jsonl(
            [
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "完成\n/rename fallback title"}],
                    },
                }
            ]
        )
        self.addCleanup(path.unlink)

        payload = {"hook_event_name": "Stop", "transcript_path": str(path)}

        self.assertTrue(auto_rename.process_payload(payload, "%2"))
        send.assert_called_once_with("%2", "/rename fallback title")

    @mock.patch.object(auto_rename, "send_rename_via_tmux")
    def test_custom_title_deduplicates(self, send: mock.Mock) -> None:
        path = self.write_jsonl(
            [
                {"type": "custom-title", "customTitle": "same title"},
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "/rename same title"}],
                    },
                },
            ]
        )
        self.addCleanup(path.unlink)
        payload = {
            "hook_event_name": "Stop",
            "last_assistant_message": "/rename same title",
            "transcript_path": str(path),
        }

        self.assertFalse(auto_rename.process_payload(payload, "%3"))
        send.assert_not_called()

    @mock.patch.object(auto_rename, "send_rename_via_tmux", return_value=True)
    def test_cursor_completed_regression(self, send: mock.Mock) -> None:
        path = self.write_jsonl(
            [
                {
                    "role": "assistant",
                    "message": {
                        "content": [{"type": "text", "text": "done\n/rename cursor title"}]
                    },
                }
            ]
        )
        self.addCleanup(path.unlink)

        self.assertTrue(
            auto_rename.process_payload(
                {"status": "completed", "transcript_path": str(path)}, "%4"
            )
        )
        send.assert_called_once_with("%4", "/rename cursor title")

    @mock.patch.object(auto_rename, "send_rename_via_tmux")
    def test_cursor_non_completed_and_last_line_rule(self, send: mock.Mock) -> None:
        self.assertFalse(
            auto_rename.process_payload(
                {
                    "status": "error",
                    "last_assistant_message": "/rename no",
                },
                "%5",
            )
        )
        self.assertFalse(
            auto_rename.process_payload(
                {
                    "hook_event_name": "Stop",
                    "last_assistant_message": "/rename wrong\nfinal explanation",
                },
                "%5",
            )
        )
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()

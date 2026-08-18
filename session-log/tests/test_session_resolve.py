from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "session_resolve.py"
SPEC = importlib.util.spec_from_file_location("session_resolve", MODULE_PATH)
assert SPEC and SPEC.loader
session_resolve = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(session_resolve)

SESSION_ID = "13d9b15d-9217-42c4-885f-d1857c206df7"


class SessionResolveTest(unittest.TestCase):
    def test_create_register_update_keeps_one_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            times = {"filename_ts": "202608130910"}

            created = session_resolve.resolve(
                SESSION_ID,
                times,
                log_dir,
                project="claude_skills",
                slug="codex_session_log",
            )

            self.assertEqual(created["mode"], "create")
            self.assertEqual(created["index_action"], "insert_row")
            target = Path(created["target_path"])
            target.write_text(
                f'---\nsession_id: "{SESSION_ID}"\n---\n', encoding="utf-8"
            )
            (log_dir / "index.md").write_text(
                "| 日期 | 项目 | Session | 摘要 | Chat 标题建议 |\n"
                "|------|------|---------|------|---------------|\n"
                f"| 2026-08-13 | claude_skills | [adapter]({target.name}) | done | `title` |\n",
                encoding="utf-8",
            )
            session_resolve.register_entry(
                log_dir,
                SESSION_ID,
                target.name,
                "2026-08-13T01:00:00+00:00",
            )

            updated = session_resolve.resolve(SESSION_ID, times, log_dir)

            self.assertEqual(updated["mode"], "update")
            self.assertEqual(updated["target_file"], target.name)
            self.assertEqual(updated["index_action"], "replace_row")
            self.assertIn(f"({target.name})", updated["index_line_match"])
            self.assertEqual(len(list(log_dir.glob("*.md"))), 2)


CURRENT_ID = "aaaaaaaa-1111-42c4-885f-d1857c206df7"
OTHER_ID = "bbbbbbbb-2222-42c4-885f-d1857c206df7"


class CcdPendingRenamesTest(unittest.TestCase):
    @staticmethod
    def _write_registry(ccd_dir: Path, name: str, cli_uuid: str, title: str, source: str) -> None:
        entry_dir = ccd_dir / "workspace" / "profile"
        entry_dir.mkdir(parents=True, exist_ok=True)
        (entry_dir / f"{name}.json").write_text(
            session_resolve.json.dumps(
                {
                    "sessionId": name,
                    "cliSessionId": cli_uuid,
                    "title": title,
                    "titleSource": source,
                }
            ),
            encoding="utf-8",
        )

    def test_register_chat_title_and_pending_filters(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "log"
            ccd_dir = Path(temp_dir) / "ccd"

            session_resolve.register_entry(
                log_dir, CURRENT_ID, "current.md", chat_title="260813 当前会话"
            )
            session_resolve.register_entry(
                log_dir, OTHER_ID, "other.md", chat_title="260812 目标标题"
            )

            # other session, auto-titled and stale -> pending
            self._write_registry(ccd_dir, "local_other", OTHER_ID, "自动标题", "auto")
            # current session -> excluded (renamed directly via session_id="self")
            self._write_registry(ccd_dir, "local_current", CURRENT_ID, "自动标题", "auto")
            # user manually titled -> respected
            self._write_registry(ccd_dir, "local_user", OTHER_ID.replace("bbbbbbbb", "cccccccc"), "手动标题", "user")
            # unrelated session without archived title -> ignored
            self._write_registry(ccd_dir, "local_stranger", OTHER_ID.replace("bbbbbbbb", "dddddddd"), "路人", "auto")

            result = session_resolve.ccd_pending_renames(log_dir, CURRENT_ID, ccd_dir)

            self.assertEqual(result["scanned"], 4)
            self.assertEqual(len(result["pending"]), 1)
            self.assertEqual(
                result["pending"][0],
                {
                    "session_id": "local_other",
                    "title": "260812 目标标题",
                    "current_title": "自动标题",
                },
            )

    def test_pending_converges_after_rename(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "log"
            ccd_dir = Path(temp_dir) / "ccd"
            session_resolve.register_entry(
                log_dir, OTHER_ID, "other.md", chat_title="260812 目标标题"
            )
            self._write_registry(ccd_dir, "local_other", OTHER_ID, "260812 目标标题", "user")

            result = session_resolve.ccd_pending_renames(log_dir, CURRENT_ID, ccd_dir)

            self.assertEqual(result["pending"], [])

    def test_missing_registry_warns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "log"
            result = session_resolve.ccd_pending_renames(
                log_dir, CURRENT_ID, Path(temp_dir) / "nonexistent"
            )
            self.assertEqual(result["pending"], [])
            self.assertEqual(result["warning"], "ccd_registry_not_found")


if __name__ == "__main__":
    unittest.main()

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


if __name__ == "__main__":
    unittest.main()

"""Exercise doctor's CLI and probe contract without touching a real vault."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location("doctor_ingest", Path(__file__).parents[1] / "scripts/article_ingest.py")
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


class DoctorTests(unittest.TestCase):
    def run_doctor(self, response, *, fetcher="posix", npx="/tools/npx"):
        client = Mock(spec=["probe"])
        client.probe.return_value = response
        output = io.StringIO()
        with patch.object(a.sys, "argv", ["article_ingest.py", "doctor", "--fetch", "ssh:test", "--gate", "local"]), \
                patch.object(a, "_gate_module", return_value=client), \
                patch.object(a, "remote_os", return_value=fetcher), \
                patch.object(a, "find_npx", return_value=npx), \
                patch.object(a.subprocess, "run", side_effect=AssertionError("no external process")), \
                redirect_stdout(output):
            code = a.main()
        client.probe.assert_called_once_with()
        result = json.loads(output.getvalue())
        return code, result

    def test_healthy_probe_exits_zero(self):
        code, result = self.run_doctor({"ok": True, "status": "ok", "backup_ok": True,
                                        "backup": "OK 1.0h", "detail": "backup OK 1.0h"})
        self.assertEqual(code, 0)
        self.assertIs(result["ok"], True)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["checks"]["gate"], "ok backup OK 1.0h")
        self.assertIs(result["gate_probe"]["backup_ok"], True)

    def test_connected_but_unhealthy_backup_exits_nonzero_with_reason(self):
        for reason in ("flag SNAPSHOT_FAILED.flag", "stale 31.0h", "missing last_status"):
            with self.subTest(reason=reason):
                code, result = self.run_doctor({"ok": True, "status": "ok", "backup_ok": False,
                                                "backup": reason, "detail": "backup " + reason})
                self.assertEqual(code, 1)
                self.assertIs(result["ok"], False)
                self.assertEqual(result["status"], "degraded")
                self.assertEqual(result["checks"]["gate"], "backup_unhealthy backup " + reason)
                self.assertEqual(result["gate_probe"], {"ok": True, "status": "ok", "backup_ok": False,
                                                      "backup": reason, "detail": "backup " + reason})

    def test_unreachable_probe_preserves_transport_failure(self):
        code, result = self.run_doctor({"ok": False, "status": "unreachable", "detail": "ssh timeout 60s"})
        self.assertEqual(code, 1)
        self.assertIs(result["ok"], False)
        self.assertEqual(result["checks"]["gate"], "unreachable ssh timeout 60s")
        self.assertEqual(result["gate_probe"]["detail"], "ssh timeout 60s")

    def test_legacy_probe_without_backup_field_is_unknown(self):
        code, result = self.run_doctor({"ok": True, "status": "ok", "detail": "backup OK 1.0h"})
        self.assertEqual(code, 1)
        self.assertIs(result["ok"], False)
        self.assertTrue(result["checks"]["gate"].startswith("backup_unknown "))
        self.assertIn("backup_ok", result["checks"]["gate"])
        self.assertIn("backup OK 1.0h", result["checks"]["gate"])

    def test_non_boolean_backup_field_cannot_pass(self):
        for value in (None, 0, 1, "true", "false"):
            with self.subTest(value=value):
                code, result = self.run_doctor({"ok": True, "status": "ok", "backup_ok": value})
                self.assertEqual(code, 1)
                self.assertIs(result["ok"], False)
                self.assertTrue(result["checks"]["gate"].startswith("backup_unknown "))

    def test_probe_must_confirm_connection_with_exact_success_status(self):
        for response in ({"ok": False, "status": "ok", "backup_ok": True},
                         {"status": "ok", "backup_ok": True},
                         {"ok": True, "status": "ok_but_unverified", "backup_ok": True}):
            with self.subTest(response=response):
                code, result = self.run_doctor(response)
                self.assertEqual(code, 1)
                self.assertIs(result["ok"], False)

    def test_healthy_backup_does_not_hide_other_failed_checks(self):
        for options in ({"fetcher": "down"}, {"npx": None}):
            with self.subTest(options=options):
                code, result = self.run_doctor({"ok": True, "status": "ok", "backup_ok": True}, **options)
                self.assertEqual(code, 1)
                self.assertIs(result["ok"], False)
                self.assertEqual(result["status"], "degraded")


if __name__ == "__main__":
    unittest.main()

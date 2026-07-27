import importlib.util
import os
import stat
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "md_to_pdf.py"
SPEC = importlib.util.spec_from_file_location("hv_md_to_pdf", SCRIPT_PATH)
md_to_pdf = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(md_to_pdf)


def fake_markdown_module(render=None):
    module = types.ModuleType("markdown")
    module.markdown = render or (lambda text, **kwargs: f"<p>{text}</p>")
    return module


class HtmlSafetyTests(unittest.TestCase):
    def test_raw_html_is_escaped_before_markdown_conversion(self):
        rendered = md_to_pdf.md_to_html(
            "# Report\n<script>alert(1)</script><iframe src='file:///etc/passwd'>",
            markdown_module=fake_markdown_module(),
        )

        self.assertNotIn("<script>", rendered)
        self.assertNotIn("<iframe", rendered)
        self.assertIn("&lt;script>", rendered)
        self.assertIn("&lt;iframe", rendered)

    def test_blockquote_markers_are_preserved_for_markdown(self):
        seen = {}

        def render(text, **kwargs):
            seen["text"] = text
            return "<blockquote><p>metadata</p></blockquote>"

        md_to_pdf.md_to_html(
            "# Report\n> 研究时间：2026-07-27",
            markdown_module=fake_markdown_module(render),
        )

        self.assertIn("> 研究时间", seen["text"])

    def test_title_author_and_metadata_are_escaped(self):
        rendered = md_to_pdf.md_to_html(
            "# Report",
            title='</style><script>alert("title")</script>',
            author='<img src="file:///etc/passwd">',
            meta_line='<iframe src="https://example.com">',
            markdown_module=fake_markdown_module(),
        )

        self.assertNotIn("</style><script>", rendered)
        self.assertNotIn("<img src=", rendered)
        self.assertNotIn("<iframe src=", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("&lt;img", rendered)
        self.assertIn("&lt;iframe", rendered)

    def test_generated_image_tags_are_removed(self):
        rendered = md_to_pdf.md_to_html(
            "# Report\n![x](https://example.com/x.png)",
            markdown_module=fake_markdown_module(
                lambda text, **kwargs: '<h1>Report</h1><img src="https://example.com/x.png">'
            ),
        )

        self.assertNotIn("<img", rendered)
        self.assertIn("[image omitted]", rendered)

    def test_unsafe_link_protocols_are_neutralized(self):
        rendered = md_to_pdf.md_to_html(
            "# Report",
            markdown_module=fake_markdown_module(
                lambda text, **kwargs: (
                    '<p><a href="javascript:alert(1)">bad</a>'
                    '<a href="file:///etc/passwd">local</a>'
                    '<a href="../../etc/passwd">relative</a>'
                    '<a href="https://example.com">safe</a></p>'
                )
            ),
        )

        self.assertNotIn('href="javascript:', rendered)
        self.assertNotIn('href="file:', rendered)
        self.assertNotIn('href="../../etc/passwd"', rendered)
        self.assertEqual(rendered.count('href="#"'), 3)
        self.assertIn('href="https://example.com"', rendered)

    def test_url_fetcher_rejects_all_resource_schemes(self):
        for url in (
            "https://example.com/a.png",
            "http://127.0.0.1:8080/private",
            "file:///etc/passwd",
            "data:text/plain,secret",
        ):
            with self.subTest(url=url):
                with self.assertRaisesRegex(ValueError, "External resources are disabled"):
                    md_to_pdf.deny_url_fetcher(url)

    def test_metadata_is_only_read_from_report_header(self):
        report = "# Report\n\n## Body\n> 研究时间：不应提取"
        self.assertEqual(md_to_pdf.extract_meta_line(report), "")


class OutputSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.input_path = self.root / "report.md"
        self.input_path.write_text("# Report\nBody", encoding="utf-8")

    def run_main(self, *args):
        with mock.patch.object(md_to_pdf, "md_to_html", return_value="<html>safe</html>"), mock.patch.object(
            md_to_pdf, "render_pdf", return_value=b"%PDF-safe"
        ):
            return md_to_pdf.main(list(args))

    def test_existing_pdf_is_not_overwritten_by_default(self):
        output_path = self.root / "report.pdf"
        output_path.write_bytes(b"original")

        result = self.run_main(self.input_path, output_path)

        self.assertEqual(result, 2)
        self.assertEqual(output_path.read_bytes(), b"original")

    def test_existing_html_is_not_overwritten_by_default(self):
        output_path = self.root / "report.pdf"
        html_path = self.root / "report.html"
        html_path.write_text("original", encoding="utf-8")

        result = self.run_main(
            self.input_path,
            output_path,
            "--html-output",
            html_path,
        )

        self.assertEqual(result, 2)
        self.assertFalse(output_path.exists())
        self.assertEqual(html_path.read_text(encoding="utf-8"), "original")

    def test_force_explicitly_allows_pdf_and_html_overwrite(self):
        output_path = self.root / "report.pdf"
        html_path = self.root / "report.html"
        output_path.write_bytes(b"old-pdf")
        html_path.write_text("old-html", encoding="utf-8")
        output_path.chmod(0o600)
        html_path.chmod(0o640)

        result = self.run_main(
            self.input_path,
            output_path,
            "--html-output",
            html_path,
            "--force",
        )

        self.assertEqual(result, 0)
        self.assertEqual(output_path.read_bytes(), b"%PDF-safe")
        self.assertEqual(html_path.read_text(encoding="utf-8"), "<html>safe</html>")
        self.assertEqual(stat.S_IMODE(output_path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(html_path.stat().st_mode), 0o640)

    def test_html_sidecar_is_not_created_by_default(self):
        output_path = self.root / "report.pdf"
        html_path = self.root / "report.html"

        result = self.run_main(self.input_path, output_path)

        self.assertEqual(result, 0)
        self.assertTrue(output_path.exists())
        self.assertFalse(html_path.exists())

    def test_new_output_is_owner_only_by_default(self):
        output_path = self.root / "report.pdf"

        result = self.run_main(self.input_path, output_path)

        self.assertEqual(result, 0)
        self.assertEqual(stat.S_IMODE(output_path.stat().st_mode), 0o600)

    def test_input_and_output_must_not_resolve_to_same_file(self):
        output_path = self.root / "report.pdf"
        try:
            output_path.symlink_to(self.input_path)
        except OSError as exc:
            self.skipTest(f"symlink unavailable: {exc}")

        with self.assertRaisesRegex(md_to_pdf.ConversionError, "指向同一文件|符号链接"):
            md_to_pdf.validate_paths(
                self.input_path,
                output_path,
                force=True,
            )

    def test_hard_link_output_cannot_overwrite_input(self):
        output_path = self.root / "report.pdf"
        try:
            os.link(self.input_path, output_path)
        except OSError as exc:
            self.skipTest(f"hard link unavailable: {exc}")

        with self.assertRaisesRegex(md_to_pdf.ConversionError, "指向同一文件"):
            md_to_pdf.validate_paths(
                self.input_path,
                output_path,
                force=True,
            )

    def test_new_output_entry_replacement_during_write_is_detected(self):
        output_path = self.root / "report.pdf"
        moved_path = self.root / "generated.pdf"
        original_fsync = md_to_pdf.os.fsync
        swapped = False

        def replace_entry(fd):
            nonlocal swapped
            original_fsync(fd)
            if not swapped and output_path.exists():
                output_path.rename(moved_path)
                output_path.write_bytes(b"ATTACKER")
                output_path.chmod(0o644)
                swapped = True

        with mock.patch.object(md_to_pdf.os, "fsync", side_effect=replace_entry):
            result = self.run_main(self.input_path, output_path)

        self.assertEqual(result, 2)
        self.assertEqual(output_path.read_bytes(), b"ATTACKER")
        self.assertEqual(moved_path.read_bytes(), b"%PDF-safe")

    def test_force_temp_entry_replacement_during_write_is_detected(self):
        output_path = self.root / "report.pdf"
        output_path.write_bytes(b"OLD")
        moved_path = self.root / "generated.pdf"
        original_fsync = md_to_pdf.os.fsync
        attacker_temp = None

        def replace_temp_entry(fd):
            nonlocal attacker_temp
            original_fsync(fd)
            candidates = list(self.root.glob(".report.pdf.*.tmp"))
            if attacker_temp is None and candidates:
                attacker_temp = candidates[0]
                attacker_temp.rename(moved_path)
                attacker_temp.write_bytes(b"ATTACKER")
                attacker_temp.chmod(0o644)

        with mock.patch.object(md_to_pdf.os, "fsync", side_effect=replace_temp_entry):
            result = self.run_main(self.input_path, output_path, "--force")

        self.assertEqual(result, 2)
        self.assertEqual(output_path.read_bytes(), b"OLD")
        self.assertEqual(moved_path.read_bytes(), b"%PDF-safe")
        self.assertIsNotNone(attacker_temp)
        self.assertEqual(attacker_temp.read_bytes(), b"ATTACKER")

    def test_force_rejects_unrelated_hard_link_output(self):
        victim_path = self.root / "victim.pdf"
        victim_path.write_bytes(b"ORIGINAL")
        output_path = self.root / "report.pdf"
        try:
            os.link(victim_path, output_path)
        except OSError as exc:
            self.skipTest(f"hard link unavailable: {exc}")

        with self.assertRaisesRegex(md_to_pdf.ConversionError, "不能是硬链接"):
            md_to_pdf.validate_paths(
                self.input_path,
                output_path,
                force=True,
            )
        self.assertEqual(victim_path.read_bytes(), b"ORIGINAL")

    def test_output_parent_cannot_be_symlinked_below_working_root(self):
        target_dir = self.root / "target"
        target_dir.mkdir()
        alias_dir = self.root / "alias"
        try:
            alias_dir.symlink_to(target_dir, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"directory symlink unavailable: {exc}")

        with mock.patch.object(md_to_pdf.Path, "cwd", return_value=self.root):
            with self.assertRaisesRegex(md_to_pdf.ConversionError, "输出目录不能经过符号链接"):
                md_to_pdf.validate_paths(
                    self.input_path,
                    alias_dir / "report.pdf",
                )

    def test_parent_symlink_swap_during_render_cannot_redirect_force_write(self):
        output_dir = self.root / "output"
        output_dir.mkdir()
        output_path = output_dir / "report.pdf"
        output_path.write_bytes(b"OLD")

        victim_dir = self.root / "victim"
        victim_dir.mkdir()
        victim_path = victim_dir / "report.pdf"
        victim_path.write_bytes(b"ORIGINAL")
        moved_output_dir = self.root / "moved-output"

        def swap_parent(_html):
            output_dir.rename(moved_output_dir)
            output_dir.symlink_to(victim_dir, target_is_directory=True)
            return b"%PDF-redirected"

        with mock.patch.object(md_to_pdf, "md_to_html", return_value="<html>safe</html>"), mock.patch.object(
            md_to_pdf, "render_pdf", side_effect=swap_parent
        ):
            result = md_to_pdf.main(
                [str(self.input_path), str(output_path), "--force"]
            )

        self.assertEqual(result, 2)
        self.assertEqual(victim_path.read_bytes(), b"ORIGINAL")
        self.assertEqual((moved_output_dir / "report.pdf").read_bytes(), b"OLD")

    def test_parent_directory_replacement_during_render_is_rejected(self):
        output_dir = self.root / "output"
        output_dir.mkdir()
        output_path = output_dir / "report.pdf"
        output_path.write_bytes(b"OLD")

        replacement_dir = self.root / "replacement"
        replacement_dir.mkdir()
        replacement_path = replacement_dir / "report.pdf"
        replacement_path.write_bytes(b"VICTIM")
        moved_output_dir = self.root / "moved-output"

        def replace_parent(_html):
            output_dir.rename(moved_output_dir)
            replacement_dir.rename(output_dir)
            return b"%PDF-redirected"

        with mock.patch.object(md_to_pdf, "md_to_html", return_value="<html>safe</html>"), mock.patch.object(
            md_to_pdf, "render_pdf", side_effect=replace_parent
        ):
            result = md_to_pdf.main(
                [str(self.input_path), str(output_path), "--force"]
            )

        self.assertEqual(result, 2)
        self.assertEqual((output_dir / "report.pdf").read_bytes(), b"VICTIM")
        self.assertEqual((moved_output_dir / "report.pdf").read_bytes(), b"OLD")


if __name__ == "__main__":
    unittest.main()

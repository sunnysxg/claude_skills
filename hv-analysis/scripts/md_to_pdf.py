#!/usr/bin/env python3
"""安全地将横纵分析 Markdown 报告转换为 PDF。"""

import argparse
import html
import importlib
import os
import re
import secrets
import stat
import sys
from pathlib import Path
from urllib.parse import urlsplit


CSS_TEMPLATE = """
@page {
    size: A4;
    margin: 25mm 20mm 20mm 20mm;

    @top-center {
        content: "HEADER_TEXT";
        font-family: "Droid Sans Fallback", Helvetica, Arial, sans-serif;
        font-size: 8pt;
        color: #95a5a6;
        border-bottom: 0.5pt solid #ecf0f1;
        padding-bottom: 3mm;
    }

    @bottom-center {
        content: "第 " counter(page) " 页";
        font-family: "Droid Sans Fallback", Helvetica, Arial, sans-serif;
        font-size: 8pt;
        color: #95a5a6;
        border-top: 0.8pt solid #1a5276;
        padding-top: 2mm;
    }
}

@page :first {
    @top-center { content: none; }
    @bottom-center { content: none; }
}

body {
    font-family: "Droid Sans Fallback", Helvetica, Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.75;
    color: #2c3e50;
    text-align: justify;
}

.cover {
    page-break-after: always;
    text-align: center;
    padding-top: 45%;
}
.cover h1 {
    font-size: 28pt;
    color: #1a5276;
    margin-bottom: 8mm;
    font-weight: bold;
    letter-spacing: 2pt;
}
.cover .subtitle {
    font-size: 14pt;
    color: #95a5a6;
    margin-bottom: 6mm;
}
.cover .meta {
    font-size: 11pt;
    color: #95a5a6;
    margin-bottom: 4mm;
}
.cover .divider {
    width: 60%;
    margin: 8mm auto;
    border: none;
    border-top: 1.5pt solid #1a5276;
}

h1 {
    font-size: 20pt;
    color: #1a5276;
    margin-top: 16mm;
    margin-bottom: 6mm;
    padding-bottom: 3mm;
    border-bottom: 2pt solid #1a5276;
    page-break-before: always;
    font-weight: bold;
}

h2 {
    font-size: 14pt;
    color: #1e8449;
    margin-top: 10mm;
    margin-bottom: 5mm;
    font-weight: bold;
}

h3 {
    font-size: 12pt;
    color: #2e86c1;
    margin-top: 6mm;
    margin-bottom: 3mm;
    font-weight: bold;
}

h4 {
    font-size: 11pt;
    color: #5b2c6f;
    margin-top: 5mm;
    margin-bottom: 2mm;
    font-weight: bold;
}

p {
    margin-top: 1.5mm;
    margin-bottom: 1.5mm;
    orphans: 3;
    widows: 3;
}

blockquote {
    margin: 4mm 0;
    padding: 4mm 4mm 4mm 10mm;
    background: #f8f9fa;
    border-left: 3pt solid #1a5276;
    color: #5d6d7e;
    font-size: 10pt;
}
blockquote p {
    margin: 1mm 0;
}

strong, b {
    font-weight: bold;
    color: #1a252f;
}

code {
    font-family: "Courier New", Courier, monospace;
    background: #fdf2e9;
    color: #c0392b;
    padding: 0.5mm 1.5mm;
    border-radius: 2pt;
    font-size: 9.5pt;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 4mm 0;
    font-size: 9.5pt;
}
thead th {
    background: #1a5276;
    color: white;
    padding: 3mm;
    text-align: left;
    font-weight: bold;
}
tbody td {
    padding: 2.5mm 3mm;
    border-bottom: 0.5pt solid #bdc3c7;
}
tbody tr:nth-child(even) {
    background: #f8f9fa;
}

hr {
    border: none;
    border-top: 0.5pt solid #bdc3c7;
    margin: 4mm 0;
}

ul, ol {
    margin: 2mm 0;
    padding-left: 8mm;
}
li {
    margin-bottom: 1mm;
}

a {
    color: #2e86c1;
    text-decoration: none;
}

.omitted-image {
    color: #95a5a6;
    font-style: italic;
}
"""

META_KEYS = ("研究时间", "所属领域", "研究对象类型")
CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
IMAGE_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
LINK_HREF_RE = re.compile(
    r'(?P<prefix><a\b[^>]*\shref=)(?P<quote>["\'])(?P<url>.*?)(?P=quote)',
    re.IGNORECASE,
)
FIRST_H1_RE = re.compile(r"<h1(?:\s[^>]*)?>.*?</h1>", re.IGNORECASE | re.DOTALL)


class ConversionError(RuntimeError):
    """转换输入、依赖或渲染失败。"""


def clean_inline_text(value, max_length):
    """清除控制字符并限制进入模板的单行文本长度。"""
    cleaned = CONTROL_CHARS_RE.sub(" ", str(value))
    return " ".join(cleaned.split())[:max_length]


def css_string(value):
    """把文本编码为 CSS quoted string 中的安全内容。"""
    replacements = {
        "\\": r"\5C ",
        '"': r"\22 ",
        "<": r"\3C ",
        ">": r"\3E ",
        "&": r"\26 ",
    }
    return "".join(replacements.get(char, char) for char in value)


def sanitize_link(match):
    """只保留网页、邮件和页内锚点，避免 sidecar 访问本地路径。"""
    raw_url = html.unescape(match.group("url")).strip()
    scheme = urlsplit(raw_url).scheme.lower()
    if not raw_url.startswith("#") and scheme not in {"http", "https", "mailto"}:
        raw_url = "#"
    quote = match.group("quote")
    return (
        f'{match.group("prefix")}{quote}'
        f'{html.escape(raw_url, quote=True)}{quote}'
    )


def extract_first_heading(md_text):
    """只从报告头部提取第一个一级标题。"""
    for line in md_text.splitlines()[:20]:
        if line.startswith("# "):
            return clean_inline_text(line[2:], 200)
    return ""


def extract_meta_line(md_text):
    """只接受报告头部、二级标题之前的预期引用元信息。"""
    for line in md_text.splitlines()[:20]:
        stripped = line.strip()
        if stripped.startswith("## "):
            break
        if not stripped.startswith(">"):
            continue
        candidate = clean_inline_text(stripped[1:].strip(), 500)
        if any(key in candidate for key in META_KEYS):
            return candidate
    return ""


def load_markdown_module():
    try:
        return importlib.import_module("markdown")
    except ImportError as exc:
        raise ConversionError(
            "缺少 Python-Markdown；请在已批准的环境中安装后重试，脚本不会自动安装依赖。"
        ) from exc


def md_to_html(
    md_text,
    title=None,
    subtitle="横纵分析法深度研究报告",
    meta_line="",
    author="Sarah",
    markdown_module=None,
):
    """将 Markdown 转为不执行原始 HTML、且模板值已转义的完整 HTML。"""
    markdown_module = markdown_module or load_markdown_module()
    # Escaping only '<' blocks raw HTML while preserving Markdown blockquote markers ('>').
    safe_markdown = md_text.replace("<", "&lt;")
    html_body = markdown_module.markdown(
        safe_markdown,
        extensions=["tables", "fenced_code", "nl2br"],
        output_format="html5",
    )

    # Markdown 图片会触发资源读取；报告中保留占位说明而不保留 img 标签。
    html_body = IMAGE_TAG_RE.sub(
        '<span class="omitted-image">[image omitted]</span>', html_body
    )
    html_body = LINK_HREF_RE.sub(sanitize_link, html_body)
    html_body = FIRST_H1_RE.sub("", html_body, count=1)

    report_title = clean_inline_text(
        title or extract_first_heading(md_text) or "横纵分析报告", 200
    )
    report_subtitle = clean_inline_text(subtitle, 200)
    report_author = clean_inline_text(author, 200)
    report_meta = clean_inline_text(meta_line, 500)

    css = CSS_TEMPLATE.replace(
        "HEADER_TEXT",
        css_string(f"{report_title}  |  横纵分析法深度研究报告"),
    )
    escaped_title = html.escape(report_title, quote=True)
    escaped_subtitle = html.escape(report_subtitle, quote=True)
    escaped_author = html.escape(report_author, quote=True)
    escaped_meta = html.escape(report_meta, quote=True)
    meta_html = f'<div class="meta">{escaped_meta}</div>' if report_meta else ""

    cover_html = f"""
    <div class="cover">
        <h1 style="page-break-before: avoid; border: none;">{escaped_title}</h1>
        <div class="subtitle">{escaped_subtitle}</div>
        {meta_html}
        <hr class="divider">
        <div class="meta">作者: {escaped_author}</div>
    </div>
    """

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <style>{css}</style>
</head>
<body>
{cover_html}
{html_body}
</body>
</html>"""


def deny_url_fetcher(url, *args, **kwargs):
    """拒绝 WeasyPrint 的所有外部、本地和 data URL 读取。"""
    raise ValueError(f"External resources are disabled: {url}")


def render_pdf(html_text):
    """延迟导入 WeasyPrint，并返回 PDF 字节。"""
    try:
        from weasyprint import HTML
    except ImportError as exc:
        raise ConversionError(
            "缺少 WeasyPrint；请在已批准的环境中安装后重试，脚本不会自动安装依赖。"
        ) from exc

    try:
        pdf_bytes = HTML(
            string=html_text,
            url_fetcher=deny_url_fetcher,
        ).write_pdf()
    except Exception as exc:
        raise ConversionError(f"WeasyPrint 渲染失败: {exc}") from exc

    if not isinstance(pdf_bytes, (bytes, bytearray)):
        raise ConversionError("WeasyPrint 未返回 PDF 字节。")
    return bytes(pdf_bytes)


def lexical_absolute(path):
    """转为不解析符号链接的规范绝对路径。"""
    return Path(os.path.abspath(Path(path).expanduser()))


def trusted_base(path):
    """允许环境既有的 HOME/CWD 别名，但不允许其下新增目录链接。"""
    candidates = []
    for base in (lexical_absolute(Path.home()), lexical_absolute(Path.cwd())):
        try:
            path.relative_to(base)
        except ValueError:
            continue
        candidates.append(base)
    if candidates:
        return max(candidates, key=lambda item: len(item.parts))
    return Path(path.anchor)


class OutputTarget:
    """保存已验证输出路径及其锚定父目录。"""

    def __init__(self, path, parent_fd=None):
        self.path = path
        self.parent_fd = parent_fd
        self.existing_mode = None

    @property
    def name(self):
        return self.path.name

    def close(self):
        if self.parent_fd is not None:
            os.close(self.parent_fd)
            self.parent_fd = None

    def __str__(self):
        return str(self.path)


def _supports_secure_dir_fd():
    required = (os.open, os.rename, os.unlink)
    return hasattr(os, "O_DIRECTORY") and all(
        function in os.supports_dir_fd for function in required
    )


def _open_directory_without_symlinks(path):
    """从稳定的 CWD 或文件系统根逐层打开目录，并拒绝符号链接。"""
    path = lexical_absolute(path)
    cwd = lexical_absolute(os.getcwd())
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    try:
        relative_parts = path.relative_to(cwd).parts
        current_fd = os.open(".", flags)
    except ValueError:
        root = Path(path.anchor)
        relative_parts = path.relative_to(root).parts
        current_fd = os.open(root, flags)

    try:
        for part in relative_parts:
            next_fd = os.open(part, flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except Exception:
        os.close(current_fd)
        raise


def resolve_destination(value, suffix):
    path = lexical_absolute(value)
    if path.suffix.lower() != suffix:
        raise ConversionError(f"输出文件必须使用 {suffix} 扩展名。")

    if _supports_secure_dir_fd():
        try:
            parent_fd = _open_directory_without_symlinks(path.parent)
        except FileNotFoundError as exc:
            raise ConversionError(f"输出目录不存在: {path.parent}") from exc
        except OSError as exc:
            raise ConversionError(
                f"输出目录不能经过符号链接或非目录路径: {path.parent}"
            ) from exc
        return OutputTarget(path, parent_fd)

    base = trusted_base(path)
    current = base
    for part in path.parent.relative_to(base).parts:
        current /= part
        if current.is_symlink():
            raise ConversionError(f"输出目录不能经过符号链接: {current}")
    if path.is_symlink():
        raise ConversionError(f"输出路径不能是符号链接: {path}")
    try:
        parent = path.parent.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ConversionError(f"输出目录不存在: {path.parent}") from exc
    if not parent.is_dir():
        raise ConversionError(f"输出父路径不是目录: {parent}")
    return OutputTarget(parent / path.name)


def _target_stat(target):
    try:
        if target.parent_fd is None:
            return target.path.lstat()
        return os.stat(target.name, dir_fd=target.parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None


def validate_paths(input_value, output_value, html_output_value=None, force=False):
    """验证扩展名、目录、路径冲突及覆盖策略。"""
    input_path = Path(input_value).expanduser()
    if input_path.suffix.lower() != ".md":
        raise ConversionError("输入文件必须使用 .md 扩展名。")
    if not input_path.is_file():
        raise ConversionError(f"输入文件不存在或不是普通文件: {input_path}")
    input_path = input_path.resolve()

    targets = []
    try:
        output_target = resolve_destination(output_value, ".pdf")
        targets.append(output_target)
        html_target = (
            resolve_destination(html_output_value, ".html")
            if html_output_value
            else None
        )
        if html_target:
            targets.append(html_target)

        if input_path in [target.path for target in targets]:
            raise ConversionError("输入路径不能与 PDF 或 HTML 输出路径指向同一文件。")
        if len({target.path for target in targets}) != len(targets):
            raise ConversionError("PDF 与 HTML 输出路径不能指向同一文件。")

        input_stat = input_path.stat()
        destination_stats = []
        for target in targets:
            destination_stat = _target_stat(target)
            destination_stats.append(destination_stat)
            if destination_stat is None:
                continue
            if stat.S_ISLNK(destination_stat.st_mode):
                raise ConversionError(f"输出路径不能是符号链接: {target.path}")
            if not stat.S_ISREG(destination_stat.st_mode):
                raise ConversionError(f"输出路径不是普通文件: {target.path}")
            if os.path.samestat(input_stat, destination_stat):
                raise ConversionError("输入路径不能与 PDF 或 HTML 输出路径指向同一文件。")
            if destination_stat.st_nlink > 1:
                raise ConversionError(f"输出文件不能是硬链接: {target.path}")
            if not force:
                raise ConversionError(
                    f"输出文件已存在，未覆盖: {target.path}；确认后可显式使用 --force。"
                )
            target.existing_mode = stat.S_IMODE(destination_stat.st_mode)

        if (
            html_target
            and destination_stats[0] is not None
            and destination_stats[1] is not None
            and os.path.samestat(destination_stats[0], destination_stats[1])
        ):
            raise ConversionError("PDF 与 HTML 输出路径不能指向同一文件。")

        return input_path, output_target, html_target
    except Exception:
        for target in targets:
            target.close()
        raise


def _ensure_parent_unchanged(target):
    if target.parent_fd is None:
        return
    try:
        current_fd = _open_directory_without_symlinks(target.path.parent)
    except OSError as exc:
        raise ConversionError(
            f"输出目录在验证后发生变化: {target.path.parent}"
        ) from exc
    try:
        if not os.path.samestat(os.fstat(target.parent_fd), os.fstat(current_fd)):
            raise ConversionError(
                f"输出目录在验证后发生变化: {target.path.parent}"
            )
    finally:
        os.close(current_fd)


def _open_output(target):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    if target.parent_fd is None:
        return os.open(target.path, flags, 0o600)
    return os.open(target.name, flags, 0o600, dir_fd=target.parent_fd)


def _entry_stat(target, name):
    try:
        if target.parent_fd is None:
            return target.path.with_name(name).lstat()
        return os.stat(name, dir_fd=target.parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _entry_matches_fd(target, name, fd):
    entry_stat = _entry_stat(target, name)
    return entry_stat is not None and os.path.samestat(entry_stat, os.fstat(fd))


def _require_entry_matches_fd(target, name, fd):
    if not _entry_matches_fd(target, name, fd):
        raise ConversionError(f"输出目录项在写入期间发生变化: {target.path}")


def _write_output(target, data, force, binary):
    _ensure_parent_unchanged(target)
    if not force:
        fd = _open_output(target)
        try:
            mode = "wb" if binary else "w"
            kwargs = {} if binary else {"encoding": "utf-8"}
            with os.fdopen(fd, mode, closefd=False, **kwargs) as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            _require_entry_matches_fd(target, target.name, fd)
            _ensure_parent_unchanged(target)
            _require_entry_matches_fd(target, target.name, fd)
        finally:
            os.close(fd)
        return

    if target.parent_fd is None:
        open_target = lambda name, flags: os.open(
            target.path.with_name(name), flags, 0o600
        )
        replace_target = lambda name: os.replace(
            target.path.with_name(name), target.path
        )
        unlink_target = lambda name: os.unlink(target.path.with_name(name))
    else:
        open_target = lambda name, flags: os.open(
            name, flags, 0o600, dir_fd=target.parent_fd
        )
        replace_target = lambda name: os.rename(
            name,
            target.name,
            src_dir_fd=target.parent_fd,
            dst_dir_fd=target.parent_fd,
        )
        unlink_target = lambda name: os.unlink(name, dir_fd=target.parent_fd)

    fd = None
    temp_name = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        for _attempt in range(100):
            candidate = f".{target.name}.{secrets.token_hex(12)}.tmp"
            try:
                fd = open_target(candidate, flags)
                temp_name = candidate
                break
            except FileExistsError:
                continue
        else:
            raise ConversionError(f"无法创建安全临时输出文件: {target.path.parent}")

        if target.existing_mode is not None:
            os.fchmod(fd, target.existing_mode)
        mode = "wb" if binary else "w"
        kwargs = {} if binary else {"encoding": "utf-8"}
        with os.fdopen(fd, mode, closefd=False, **kwargs) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        _require_entry_matches_fd(target, temp_name, fd)
        replace_target(temp_name)
        temp_name = None
        _require_entry_matches_fd(target, target.name, fd)
        if target.parent_fd is not None:
            os.fsync(target.parent_fd)
        _ensure_parent_unchanged(target)
        _require_entry_matches_fd(target, target.name, fd)
    finally:
        if temp_name is not None and fd is not None:
            try:
                if _entry_matches_fd(target, temp_name, fd):
                    unlink_target(temp_name)
            except FileNotFoundError:
                pass
        if fd is not None:
            os.close(fd)


def write_bytes(target, data, force):
    _write_output(target, data, force, binary=True)


def write_text(target, data, force):
    _write_output(target, data, force, binary=False)


def build_parser():
    parser = argparse.ArgumentParser(description="横纵分析法报告 Markdown → PDF")
    parser.add_argument("input", help="输入的 Markdown 文件路径")
    parser.add_argument("output", help="输出的 PDF 文件路径")
    parser.add_argument("--title", default=None, help="报告标题")
    parser.add_argument("--author", default="Sarah", help="作者名")
    parser.add_argument(
        "--html-output",
        default=None,
        help="可选的 HTML sidecar 路径；默认不生成",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="显式允许覆盖现有普通 PDF/HTML 文件",
    )
    return parser


def main(argv=None):
    normalized_argv = [str(value) for value in argv] if argv is not None else None
    args = build_parser().parse_args(normalized_argv)

    output_target = None
    html_target = None
    try:
        input_path, output_target, html_target = validate_paths(
            args.input,
            args.output,
            args.html_output,
            force=args.force,
        )
        md_text = input_path.read_text(encoding="utf-8")
        rendered_html = md_to_html(
            md_text,
            title=args.title,
            meta_line=extract_meta_line(md_text),
            author=args.author,
        )
        pdf_bytes = render_pdf(rendered_html)
        write_bytes(output_target, pdf_bytes, args.force)
        print(
            f"[OK] PDF 已生成: {output_target} "
            f"({len(pdf_bytes) / 1024:.1f} KB)"
        )

        if html_target:
            write_text(html_target, rendered_html, args.force)
            print(f"[OK] HTML 已生成: {html_target}")
        return 0
    except (ConversionError, OSError, UnicodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    finally:
        for target in (output_target, html_target):
            if target is not None:
                target.close()


if __name__ == "__main__":
    sys.exit(main())

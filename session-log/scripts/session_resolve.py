#!/usr/bin/env python3
"""Resolve create vs update for Cursor/Claude session-log upsert by UUID."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

LOCAL_TZ = timezone(timedelta(hours=8))
DEFAULT_LOG_DIR = Path.home() / "_sxg" / "llm_session_log"
MAP_FILENAME = ".session_map.json"
SESSION_ID_RE = re.compile(
    r"^session_id:\s*[\"']?([0-9a-f-]{36})[\"']?\s*$", re.MULTILINE | re.IGNORECASE
)


def log_dir_path(explicit: Path | None) -> Path:
    return explicit.expanduser() if explicit else DEFAULT_LOG_DIR


def load_map(log_dir: Path) -> dict:
    path = log_dir / MAP_FILENAME
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_map(log_dir: Path, data: dict) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / MAP_FILENAME
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_file_by_frontmatter(log_dir: Path, session_uuid: str) -> str | None:
    for md in log_dir.glob("*.md"):
        if md.name == "index.md":
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not text.startswith("---"):
            continue
        end = text.find("\n---", 3)
        if end == -1:
            continue
        frontmatter = text[3:end]
        match = SESSION_ID_RE.search(frontmatter)
        if match and match.group(1).lower() == session_uuid.lower():
            return md.name
    return None


def lookup_existing_file(log_dir: Path, session_uuid: str) -> tuple[str | None, str | None]:
    """Return (filename, warning)."""
    mapping = load_map(log_dir)
    entry = mapping.get(session_uuid)
    if entry and isinstance(entry, dict):
        filename = entry.get("file")
        if filename and (log_dir / filename).is_file():
            return filename, None
        if filename:
            return None, f"map points to missing file {filename}; treating as create"

    filename = find_file_by_frontmatter(log_dir, session_uuid)
    if filename:
        return filename, None
    return None, None


def find_index_row(index_path: Path, target_file: str) -> tuple[int | None, str | None]:
    if not index_path.is_file():
        return None, None
    needle = f"({target_file})"
    for line_no, line in enumerate(index_path.read_text(encoding="utf-8").splitlines(), start=1):
        if needle in line and line.strip().startswith("|"):
            return line_no, line
    return None, None


def build_create_filename(filename_ts: str, project: str, slug: str) -> str:
    return f"{filename_ts}_{project}_{slug}.md"


def resolve(
    session_uuid: str,
    times: dict,
    log_dir: Path,
    project: str | None = None,
    slug: str | None = None,
) -> dict:
    existing_file, warning = lookup_existing_file(log_dir, session_uuid)
    index_path = log_dir / "index.md"
    filename_ts = times.get("filename_ts", "")

    if existing_file:
        index_line, index_line_content = find_index_row(index_path, existing_file)
        result = {
            "mode": "update",
            "session_id": session_uuid,
            "target_file": existing_file,
            "target_path": str(log_dir / existing_file),
            "filename_ts_for_create": filename_ts,
            "index_action": "replace_row",
            "index_line": index_line,
            "index_line_match": index_line_content,
            "warning": warning,
        }
        return result

    if not project or not slug:
        return {
            "error": "create_requires_slug",
            "message": "No existing archive for this session; pass --project and --slug",
            "mode": "create",
            "session_id": session_uuid,
            "filename_ts_for_create": filename_ts,
            "index_action": "insert_row",
        }

    target_file = build_create_filename(filename_ts, project, slug)
    return {
        "mode": "create",
        "session_id": session_uuid,
        "target_file": target_file,
        "target_path": str(log_dir / target_file),
        "filename_ts_for_create": filename_ts,
        "index_action": "insert_row",
        "index_line": None,
        "index_line_match": None,
        "warning": warning,
    }


def register_entry(
    log_dir: Path,
    session_uuid: str,
    target_file: str,
    started_at: str | None = None,
) -> dict:
    mapping = load_map(log_dir)
    now = datetime.now(tz=LOCAL_TZ).isoformat()
    existing = mapping.get(session_uuid, {})
    if isinstance(existing, dict) and existing.get("file") == target_file:
        existing["last_logged_at"] = now
        if started_at:
            existing.setdefault("started_at", started_at)
        mapping[session_uuid] = existing
    else:
        mapping[session_uuid] = {
            "file": target_file,
            "started_at": started_at or now,
            "last_logged_at": now,
        }
    save_map(log_dir, mapping)
    return mapping[session_uuid]


def load_times_json(path: Path | None, inline: str | None) -> dict:
    if inline:
        return json.loads(inline)
    if path:
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uuid", required=True, help="Cursor/Claude chat session UUID")
    parser.add_argument("--log-dir", type=Path, default=None, help="Archive directory")
    parser.add_argument("--times-json", type=Path, help="JSON file from session_times.py")
    parser.add_argument("--times-inline", help="Inline JSON from session_times.py")
    parser.add_argument("--project", help="Project slug for create-mode filename")
    parser.add_argument("--slug", help="Filename slug for create mode")
    parser.add_argument(
        "--register",
        action="store_true",
        help="After writing archive, register uuid->file in .session_map.json",
    )
    parser.add_argument("--file", help="Archive filename for --register")
    parser.add_argument("--started-at", help="ISO started_at for --register")
    args = parser.parse_args()

    log_dir = log_dir_path(args.log_dir)

    if args.register:
        if not args.file:
            print(json.dumps({"error": "register_requires_file"}, ensure_ascii=False), file=sys.stderr)
            return 1
        entry = register_entry(log_dir, args.uuid, args.file, args.started_at)
        print(json.dumps({"registered": True, "entry": entry}, ensure_ascii=False, indent=2))
        return 0

    times = load_times_json(args.times_json, args.times_inline)
    result = resolve(args.uuid, times, log_dir, args.project, args.slug)
    if result.get("error"):
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

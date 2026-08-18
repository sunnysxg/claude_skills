#!/usr/bin/env python3
"""Resolve create vs update for session-log upsert by session UUID."""

from __future__ import annotations

import argparse
import json
import os
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
    chat_title: str | None = None,
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
    if chat_title:
        mapping[session_uuid]["chat_title"] = chat_title
    save_map(log_dir, mapping)
    return mapping[session_uuid]


def ccd_registry_root() -> Path | None:
    """Locate Claude Code Desktop's per-session registry directory."""
    candidates = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "Claude" / "claude-code-sessions")
    home = Path.home()
    candidates.append(home / "Library" / "Application Support" / "Claude" / "claude-code-sessions")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def ccd_pending_renames(log_dir: Path, current_uuid: str, ccd_dir: Path | None = None) -> dict:
    """List other CCD sessions whose title still differs from the archived chat_title.

    Convergence is stateless: once a session is renamed (or the user set a manual
    title, which this scan skips), it drops out of the pending list.
    """
    root = ccd_dir if ccd_dir else ccd_registry_root()
    if root is None or not root.is_dir():
        return {"pending": [], "warning": "ccd_registry_not_found"}
    mapping = load_map(log_dir)
    desired = {
        uuid.lower(): entry["chat_title"]
        for uuid, entry in mapping.items()
        if isinstance(entry, dict) and entry.get("chat_title")
    }
    pending = []
    scanned = 0
    for reg in root.rglob("local_*.json"):
        try:
            data = json.loads(reg.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        scanned += 1
        cli_uuid = str(data.get("cliSessionId") or "").lower()
        # the current session is renamed directly via session_id="self"; skip it here
        if not cli_uuid or cli_uuid == current_uuid.lower():
            continue
        want = desired.get(cli_uuid)
        if not want or data.get("title") == want:
            continue
        if data.get("titleSource") == "user":
            continue  # user's manual title wins
        pending.append(
            {
                "session_id": data.get("sessionId") or reg.stem,
                "title": want,
                "current_title": data.get("title"),
            }
        )
    return {"pending": pending, "registry_root": str(root), "scanned": scanned}


def load_times_json(path: Path | None, inline: str | None) -> dict:
    if inline:
        return json.loads(inline)
    if path:
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # chat titles are non-ASCII; Windows consoles default to cp1252
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uuid", required=True, help="Chat/task session UUID")
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
    parser.add_argument("--chat-title", help="suggested_chat_title to store for --register")
    parser.add_argument(
        "--ccd-pending",
        action="store_true",
        help="List other Claude Code Desktop sessions still awaiting their archived chat_title",
    )
    parser.add_argument("--ccd-dir", type=Path, help="Override CCD registry root (tests)")
    args = parser.parse_args()

    log_dir = log_dir_path(args.log_dir)

    if args.ccd_pending:
        result = ccd_pending_renames(log_dir, args.uuid, args.ccd_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.register:
        if not args.file:
            print(json.dumps({"error": "register_requires_file"}, ensure_ascii=False), file=sys.stderr)
            return 1
        entry = register_entry(log_dir, args.uuid, args.file, args.started_at, args.chat_title)
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

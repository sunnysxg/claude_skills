#!/usr/bin/env python3
"""Backfill session_id and .session_map.json for legacy session-log archives.

Platform: Cursor transcript matching only (tested). Claude Code not tested.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

LOCAL_TZ = timezone(timedelta(hours=8))
DEFAULT_LOG_DIR = Path.home() / "_sxg" / "llm_session_log"
SESSION_ID_RE = re.compile(
    r"^session_id:\s*[\"']?([0-9a-f-]{36})[\"']?\s*$", re.MULTILINE | re.IGNORECASE
)
FILENAME_TS_RE = re.compile(r"^(\d{12})_")
OLD_FILENAME_TS_RE = re.compile(r"\](\d{10})_")
WRITE_PATH_RE = re.compile(r"path[\"']\s*:\s*[\"']([^\"']+)[\"']")

# Migration chat wrote multiple unrelated archives; map by title to original session.
MIGRATION_WRITER = "a438a7f6-18c3-4c5a-a878-8e54c4b6379d"
TITLE_UUID_OVERRIDES = {
    "260629 consistency+slug+session-log": "58c85168-0195-40fe-977f-0a66ba551f38",
    "260629 lineage-rag-8002": "869c3296-60c4-4bd4-a5b9-0608958604d5",
    "260708 factorhub-CDN本地化+Description合并": "fcfc6b26-f133-4fdd-a4f0-e80749759605",
    "260701 session-log迁移+session-search": MIGRATION_WRITER,
}

FILE_UUID_OVERRIDES = {
    "[HzyProjects]2606291743_hcp-mlflow-login验证.md": "b1c12a84-e982-4c1f-af7a-f49995968adf",
}

# Migrated by batch session; original chat uuid unknown — keep archive, no session_id.
ARCHIVE_ONLY_NO_SESSION_ID = {
    "[260507_paper_skill_extractor]2606291817_kb外迁与gitlab-push.md",
    "[quantalpha]2606291741_katex-gitlab-token.md",
}

# Same chat logged twice → merge into canonical file (latest / most complete).
MERGE_GROUPS: dict[str, dict] = {
    "c4ddfb2c-1759-4255-bd98-42f839ec712b": {
        "canonical": "202607081703_factor_infra_talib_beta_xp_source.md",
        "merge": ["202607081751_factor_infra_cpp_operator_phase1.md"],
    },
}


def normalize_title(value: str) -> str:
    text = value.strip().strip("`\"'")
    text = re.sub(r"\s+", " ", text)
    return text.lower()


def title_tokens(value: str) -> set[str]:
    text = normalize_title(value)
    parts = re.split(r"[\s+\-/|]+", text)
    return {p for p in parts if len(p) >= 3 and not re.fullmatch(r"\d{6}", p)}


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        fm[key.strip()] = val.strip().strip('"')
    return fm


def filename_ts(name: str) -> str | None:
    match = FILENAME_TS_RE.match(name)
    if match:
        return match.group(1)
    match = OLD_FILENAME_TS_RE.search(name)
    if match:
        yy = match.group(1)
        return "20" + yy if len(yy) == 10 else yy
    return None


@dataclass
class CursorSession:
    uuid: str
    title: str
    created: datetime
    updated: datetime
    cwd: str


@dataclass
class Archive:
    file: str
    path: Path
    frontmatter: dict[str, str]
    session_id: str | None


def load_cursor_sessions() -> list[CursorSession]:
    sessions: list[CursorSession] = []
    root = Path.home() / ".cursor" / "chats"
    if not root.is_dir():
        return sessions
    for meta_path in root.glob("*/*/meta.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not meta.get("hasConversation"):
            continue
        sessions.append(
            CursorSession(
                uuid=meta_path.parent.name,
                title=meta.get("title") or "",
                created=datetime.fromtimestamp(meta["createdAtMs"] / 1000, tz=LOCAL_TZ),
                updated=datetime.fromtimestamp(meta["updatedAtMs"] / 1000, tz=LOCAL_TZ),
                cwd=meta.get("cwd") or "",
            )
        )
    return sessions


def find_transcript_writer(filename: str) -> str | None:
    root = Path.home() / ".cursor" / "projects"
    for jl in root.glob("**/agent-transcripts/*/*.jsonl"):
        try:
            for line in jl.open(encoding="utf-8", errors="ignore"):
                if filename not in line:
                    continue
                if "Write" not in line and "write" not in line:
                    continue
                if re.search(rf"path[\"']\s*:\s*[\"'][^\"']*{re.escape(filename)}", line):
                    return jl.parent.name
        except OSError:
            continue
    return None


def resolve_uuid_for_archive(archive: Archive, sessions: list[CursorSession]) -> tuple[str | None, str, float]:
    if archive.session_id:
        return archive.session_id, "existing", 100.0

    if archive.file in FILE_UUID_OVERRIDES:
        return FILE_UUID_OVERRIDES[archive.file], "file_override", 98.0

    sug = archive.frontmatter.get("suggested_chat_title", "")
    for key, uuid in TITLE_UUID_OVERRIDES.items():
        if normalize_title(sug) == normalize_title(key) or key.lower() in normalize_title(sug):
            return uuid, "title_override", 95.0

    writer = find_transcript_writer(archive.file)
    if writer:
        if writer == MIGRATION_WRITER:
            for key, uuid in TITLE_UUID_OVERRIDES.items():
                if key.lower() in normalize_title(sug):
                    return uuid, "migration_title_override", 90.0
        return writer, "transcript_write", 85.0

    best_uuid = None
    best_score = 0.0
    best_reason = "none"
    for session in sessions:
        score = 0.0
        n_sug = normalize_title(sug)
        n_meta = normalize_title(session.title)
        if n_sug and n_meta and (n_sug == n_meta or n_sug in n_meta or n_meta in n_sug):
            score = 80.0
        else:
            overlap = title_tokens(sug) & title_tokens(session.title)
            score = min(len(overlap) * 3, 12)
        if score > best_score:
            best_score = score
            best_uuid = session.uuid
            best_reason = "meta_title_fuzzy"
    if best_score >= 6:
        return best_uuid, best_reason, best_score
    return None, "unmatched", 0.0


def load_archives(log_dir: Path) -> list[Archive]:
    archives: list[Archive] = []
    for path in sorted(log_dir.glob("*.md")):
        if path.name == "index.md":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        sid = None
        if m := SESSION_ID_RE.search(text[:800]):
            sid = m.group(1)
        archives.append(Archive(path.name, path, fm, sid))
    return archives


def inject_session_id(content: str, session_id: str) -> str:
    if SESSION_ID_RE.search(content):
        return content
    if not content.startswith("---"):
        return content
    end = content.find("\n---", 3)
    if end == -1:
        return content
    block = content[3:end]
    body = content[end:]
    return f"---\nsession_id: \"{session_id}\"\n{block}{body}"


def load_map(log_dir: Path) -> dict:
    path = log_dir / ".session_map.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_map(log_dir: Path, mapping: dict) -> None:
    path = log_dir / ".session_map.json"
    path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def remove_index_rows(index_path: Path, filenames: set[str]) -> None:
    if not index_path.is_file():
        return
    lines = index_path.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        if any(f"({fn})" in line for fn in filenames):
            continue
        out.append(line)
    index_path.write_text("\n".join(out) + "\n", encoding="utf-8")


def apply_backfill(log_dir: Path, assignments: dict[str, str]) -> list[str]:
    applied: list[str] = []
    mapping = load_map(log_dir)
    now = datetime.now(tz=LOCAL_TZ).isoformat()
    for filename, uuid in sorted(assignments.items()):
        path = log_dir / filename
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        updated = inject_session_id(text, uuid)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
        started = fm.get("date", "")
        time_part = fm.get("time", "00:00")
        started_at = f"{started}T{time_part}:00+08:00" if started else now
        # One uuid → one map entry (last write wins); migration batch uses FILE overrides.
        if uuid not in mapping or mapping[uuid].get("file") == filename:
            mapping[uuid] = {
                "file": filename,
                "started_at": started_at,
                "last_logged_at": now,
                "backfilled": True,
            }
        applied.append(filename)
    save_map(log_dir, mapping)
    return applied


def build_assignments(archives: list[Archive], sessions: list[CursorSession]) -> dict[str, str]:
    assignments: dict[str, str] = {}
    merge_remove: set[str] = set()
    for spec in MERGE_GROUPS.values():
        merge_remove.update(spec.get("merge", []))

    for archive in archives:
        if archive.file in merge_remove or archive.file in ARCHIVE_ONLY_NO_SESSION_ID:
            continue
        uuid, _, _ = resolve_uuid_for_archive(archive, sessions)
        if uuid:
            assignments[archive.file] = uuid

    for uuid, spec in MERGE_GROUPS.items():
        canonical = spec["canonical"]
        assignments[canonical] = uuid

    return assignments


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-dir", type=Path, default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--assignments-out", type=Path)
    args = parser.parse_args()

    log_dir = (args.log_dir or DEFAULT_LOG_DIR).expanduser()
    sessions = load_cursor_sessions()
    archives = load_archives(log_dir)

    rows = []
    by_uuid: dict[str, list[str]] = defaultdict(list)
    for archive in archives:
        uuid, reason, score = resolve_uuid_for_archive(archive, sessions)
        rows.append(
            {
                "file": archive.file,
                "session_id": uuid,
                "reason": reason,
                "score": score,
                "has_session_id": bool(archive.session_id),
            }
        )
        if uuid:
            by_uuid[uuid].append(archive.file)

    assignments = build_assignments(archives, sessions)
    report = {
        "log_dir": str(log_dir),
        "rows": rows,
        "assignments": assignments,
        "merge_groups": MERGE_GROUPS,
        "multi_file_uuids": {u: fs for u, fs in by_uuid.items() if len(fs) > 1},
    }

    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.report:
        args.report.write_text(text + "\n", encoding="utf-8")
    if args.assignments_out:
        args.assignments_out.write_text(
            json.dumps(assignments, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    if args.apply:
        applied = apply_backfill(log_dir, assignments)
        removed = set()
        for spec in MERGE_GROUPS.values():
            removed.update(spec.get("merge", []))
        remove_index_rows(log_dir / "index.md", removed)
        for fn in removed:
            p = log_dir / fn
            if p.is_file():
                p.unlink()
        print(json.dumps({"applied": applied, "removed": sorted(removed)}, ensure_ascii=False), file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

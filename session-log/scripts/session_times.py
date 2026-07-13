#!/usr/bin/env python3
"""Derive session start / last-active times from a Cursor agent transcript.

Platform: Cursor only (tested). Claude Code not tested — do not assume this script works there.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

TS_RE = re.compile(
    r"<timestamp>([^<]+)</timestamp>", re.IGNORECASE
)
USER_QUERY_RE = re.compile(
    r"<user_query>\s*(.*?)\s*</user_query>", re.DOTALL | re.IGNORECASE
)
LOCAL_TZ = timezone(timedelta(hours=8))

META_SKILL_MARKERS = ("session-log", "/session-log", "/handoff", "handoff")


def parse_cursor_timestamp(raw: str) -> datetime:
    """Parse Cursor user-message timestamp, e.g. Wednesday, Jul 8, 2026, 10:58 AM (UTC+8)."""
    text = raw.strip()
    text = re.sub(r"\s*\(UTC[+-]\d+\)\s*$", "", text)
    return datetime.strptime(text, "%A, %b %d, %Y, %I:%M %p").replace(tzinfo=LOCAL_TZ)


def ms_to_dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=LOCAL_TZ)


def is_meta_skill_only(text: str) -> bool:
    """True when the message is only /session-log or /handoff skill invocation."""
    if "manually_attached_skills" not in text:
        return False
    if not any(marker in text for marker in META_SKILL_MARKERS):
        return False

    match = USER_QUERY_RE.search(text)
    if not match:
        return True

    query = match.group(1).strip()
    for marker in META_SKILL_MARKERS:
        query = re.sub(re.escape(marker), "", query, flags=re.IGNORECASE)
    query = query.strip(" \t\n\r,;")
    return not query


def extract_user_timestamps(transcript_path: Path) -> list[datetime]:
    timestamps: list[datetime] = []
    with transcript_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or '"role":"user"' not in line:
                continue
            match = TS_RE.search(line)
            if not match:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            content = payload.get("message", {}).get("content", "")
            if isinstance(content, list):
                text = " ".join(
                    part.get("text", "") for part in content if isinstance(part, dict)
                )
            else:
                text = str(content)
            if is_meta_skill_only(text):
                continue
            timestamps.append(parse_cursor_timestamp(match.group(1)))
    return timestamps


def find_meta_json(session_uuid: str) -> Path | None:
    chats_root = Path.home() / ".cursor" / "chats"
    if not chats_root.is_dir():
        return None
    for meta in chats_root.glob(f"*/{session_uuid}/meta.json"):
        if meta.is_file():
            return meta
    return None


def find_transcript(session_uuid: str, explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit if explicit.is_file() else None
    projects_root = Path.home() / ".cursor" / "projects"
    if not projects_root.is_dir():
        return None
    matches = sorted(projects_root.glob(f"**/agent-transcripts/{session_uuid}/{session_uuid}.jsonl"))
    return matches[-1] if matches else None


def infer_uuid(transcript_path: Path) -> str:
    return transcript_path.parent.name


def fmt_date(dt: datetime) -> str:
    return dt.astimezone(LOCAL_TZ).strftime("%Y-%m-%d")


def fmt_time(dt: datetime) -> str:
    return dt.astimezone(LOCAL_TZ).strftime("%H:%M")


def fmt_filename_ts(started: datetime, last_active: datetime) -> str:
    start_local = started.astimezone(LOCAL_TZ)
    last_local = last_active.astimezone(LOCAL_TZ)
    return start_local.strftime("%Y%m%d") + last_local.strftime("%H%M")


def compute_times(
    transcript_path: Path,
    meta_path: Path | None = None,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now(tz=LOCAL_TZ)
    user_ts = extract_user_timestamps(transcript_path)

    started = user_ts[0] if user_ts else None
    last_active = user_ts[-1] if user_ts else None

    if meta_path and meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        created = ms_to_dt(int(meta["createdAtMs"]))
        if started is None or created < started:
            started = created
        if last_active is None:
            updated = ms_to_dt(int(meta["updatedAtMs"]))
            last_active = updated

    fallback = started is None or last_active is None
    if fallback:
        started = started or now
        last_active = last_active or now

    return {
        "source": "cursor",
        "transcript": str(transcript_path),
        "meta": str(meta_path) if meta_path else None,
        "started_at": started.isoformat(),
        "last_active_at": last_active.isoformat(),
        "logged_at": now.isoformat(),
        "date": fmt_date(started),
        "time": fmt_time(last_active),
        "filename_ts": fmt_filename_ts(started, last_active),
        "fallback": fallback,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--transcript",
        type=Path,
        help="Path to {uuid}/{uuid}.jsonl under ~/.cursor/projects/.../agent-transcripts/",
    )
    parser.add_argument(
        "--uuid",
        help="Cursor session UUID; used to locate transcript/meta when --transcript is omitted",
    )
    parser.add_argument(
        "--meta",
        type=Path,
        help="Optional path to ~/.cursor/chats/.../{uuid}/meta.json",
    )
    args = parser.parse_args()

    transcript = args.transcript
    if transcript is None and args.uuid:
        transcript = find_transcript(args.uuid, None)
    if transcript is None:
        print(
            json.dumps(
                {
                    "error": "transcript_not_found",
                    "message": "Pass --transcript or --uuid",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1

    session_uuid = args.uuid or infer_uuid(transcript)
    meta = args.meta or find_meta_json(session_uuid)
    result = compute_times(transcript, meta)
    result["session_id"] = session_uuid
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

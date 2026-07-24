#!/usr/bin/env python3
"""Derive session start / last-active times from Cursor or Claude transcripts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

TS_RE = re.compile(r"<timestamp>([^<]+)</timestamp>", re.IGNORECASE)
USER_QUERY_RE = re.compile(
    r"<user_query>\s*(.*?)\s*</user_query>", re.DOTALL | re.IGNORECASE
)
COMMAND_NAME_RE = re.compile(
    r"<command-name>\s*/?([^<]+?)\s*</command-name>", re.IGNORECASE
)
COMMAND_ARGS_RE = re.compile(
    r"<command-args>\s*(.*?)\s*</command-args>", re.DOTALL | re.IGNORECASE
)
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
LOCAL_TZ = timezone(timedelta(hours=8))

META_SKILL_MARKERS = ("session-log", "/session-log", "/handoff", "handoff")
CLAUDE_SYNTHETIC_PREFIXES = (
    "<system-reminder>",
    "<local-command-caveat>",
    "<task-notification>",
    "Base directory for this skill:",
    "This session is being continued from a previous conversation",
    "## Context Usage",
    "[Request interrupted by user]",
)


def parse_cursor_timestamp(raw: str) -> datetime:
    """Parse Cursor user timestamp, e.g. Wednesday, Jul 8, 2026, 10:58 AM (UTC+8)."""
    text = raw.strip()
    text = re.sub(r"\s*\(UTC[+-]\d+\)\s*$", "", text)
    return datetime.strptime(text, "%A, %b %d, %Y, %I:%M %p").replace(
        tzinfo=LOCAL_TZ
    )


def parse_claude_timestamp(raw: str) -> datetime:
    return datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))


def ms_to_dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=LOCAL_TZ)


def message_text(message: object) -> str:
    if not isinstance(message, dict):
        return ""
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return " ".join(
        str(part.get("text", ""))
        for part in content
        if isinstance(part, dict) and part.get("type") == "text"
    ).strip()


def is_pure_session_log_invocation(text: str) -> bool:
    normalized = text.strip().lower()
    if normalized in {"session-log", "/session-log"}:
        return True

    command_match = COMMAND_NAME_RE.search(text)
    if not command_match or command_match.group(1).strip().lower() != "session-log":
        return False
    args_match = COMMAND_ARGS_RE.search(text)
    return args_match is not None and not args_match.group(1).strip()


def is_cursor_meta_skill_only(text: str) -> bool:
    """True when a Cursor message only invokes session-log or handoff."""
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


def extract_cursor_user_timestamps(transcript_path: Path) -> list[datetime]:
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
            text = message_text(payload.get("message"))
            if is_cursor_meta_skill_only(text) or is_pure_session_log_invocation(text):
                continue
            try:
                timestamps.append(parse_cursor_timestamp(match.group(1)))
            except ValueError:
                continue
    return timestamps


def is_substantive_claude_user(payload: dict) -> bool:
    if payload.get("type") != "user" or payload.get("isMeta") is True:
        return False

    prompt_source = payload.get("promptSource")
    if prompt_source == "system":
        return False

    text = message_text(payload.get("message")).strip()
    if not text or is_pure_session_log_invocation(text):
        return False
    if text.startswith(CLAUDE_SYNTHETIC_PREFIXES):
        return False

    return prompt_source in {None, "typed", "queued"}


def extract_claude_user_timestamps(transcript_path: Path) -> list[datetime]:
    timestamps: list[datetime] = []
    with transcript_path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict) or not is_substantive_claude_user(payload):
                continue
            raw = payload.get("timestamp")
            if not isinstance(raw, str):
                continue
            try:
                timestamps.append(parse_claude_timestamp(raw))
            except ValueError:
                continue
    return timestamps


def detect_source(transcript_path: Path) -> str:
    with transcript_path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("sessionId") or (
                payload.get("type") in {"user", "assistant", "system"}
                and payload.get("timestamp")
            ):
                return "claude"
            if payload.get("role") in {"user", "assistant"} or TS_RE.search(line):
                return "cursor"
    return "cursor"


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

    cursor_root = Path.home() / ".cursor" / "projects"
    if cursor_root.is_dir():
        matches = sorted(
            cursor_root.glob(
                f"**/agent-transcripts/{session_uuid}/{session_uuid}.jsonl"
            )
        )
        if matches:
            return matches[-1]

    claude_root = Path.home() / ".claude" / "projects"
    if claude_root.is_dir():
        matches = sorted(claude_root.glob(f"**/{session_uuid}.jsonl"))
        if matches:
            return matches[-1]
    return None


def infer_claude_uuid(transcript_path: Path) -> str:
    with transcript_path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            session_id = payload.get("sessionId")
            if isinstance(session_id, str) and UUID_RE.fullmatch(session_id):
                return session_id
    return transcript_path.stem if UUID_RE.fullmatch(transcript_path.stem) else ""


def infer_uuid(transcript_path: Path, source: str) -> str:
    if source == "claude":
        return infer_claude_uuid(transcript_path)
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
    source: str | None = None,
) -> dict:
    now = now or datetime.now(tz=LOCAL_TZ)
    source = source or detect_source(transcript_path)
    if source == "claude":
        user_ts = extract_claude_user_timestamps(transcript_path)
    else:
        user_ts = extract_cursor_user_timestamps(transcript_path)

    started = user_ts[0] if user_ts else None
    last_active = user_ts[-1] if user_ts else None

    if source == "cursor" and meta_path and meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        created = ms_to_dt(int(meta["createdAtMs"]))
        if started is None or created < started:
            started = created
        if last_active is None:
            last_active = ms_to_dt(int(meta["updatedAtMs"]))

    fallback = started is None or last_active is None
    if fallback:
        started = started or now
        last_active = last_active or now

    return {
        "source": source,
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
        help="Path to a Cursor or Claude session transcript",
    )
    parser.add_argument(
        "--uuid",
        help="Cursor/Claude session UUID; locates the transcript when omitted",
    )
    parser.add_argument(
        "--meta",
        type=Path,
        help="Optional Cursor path to ~/.cursor/chats/.../{uuid}/meta.json",
    )
    args = parser.parse_args()

    transcript = find_transcript(args.uuid, args.transcript) if args.uuid else args.transcript
    if transcript is None or not transcript.is_file():
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

    source = detect_source(transcript)
    session_uuid = args.uuid or infer_uuid(transcript, source)
    meta = args.meta or (find_meta_json(session_uuid) if source == "cursor" else None)
    result = compute_times(transcript, meta, source=source)
    result["session_id"] = session_uuid
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

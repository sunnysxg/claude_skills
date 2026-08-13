#!/usr/bin/env python3
"""Derive session start / last-active times from supported session transcripts."""

from __future__ import annotations

import argparse
import json
import os
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
CODEX_META_COMMAND_RE = re.compile(
    r"^/(?:session-log|rename|handoff)(?:[ \t]+[^\r\n]*)?\s*$",
    re.IGNORECASE,
)
CODEX_SUBAGENT_MESSAGE_RE = re.compile(
    r"^Message Type:\s*(?:MESSAGE|FINAL_ANSWER)\s*\r?\n"
    r"Task name:\s*.+\r?\nSender:\s*.+\r?\nPayload:\s*",
    re.IGNORECASE,
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


def codex_input_text_parts(message: object) -> list[str]:
    if not isinstance(message, dict) or message.get("type") != "message":
        return []
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [
        text
        for part in content
        if isinstance(part, dict)
        and part.get("type") == "input_text"
        and isinstance((text := part.get("text")), str)
        and text.strip()
    ]


def is_codex_synthetic_part(text: str) -> bool:
    """Match only known Codex-generated user-context envelopes."""
    stripped = text.strip()
    if re.fullmatch(
        r"<recommended_plugins>.*</recommended_plugins>",
        stripped,
        re.DOTALL | re.IGNORECASE,
    ):
        return True
    if re.fullmatch(
        r"# AGENTS\.md instructions\s*<INSTRUCTIONS>.*</INSTRUCTIONS>",
        stripped,
        re.DOTALL,
    ):
        return True
    if re.fullmatch(
        r"<environment_context>.*</environment_context>", stripped, re.DOTALL
    ):
        return True
    if re.fullmatch(
        r"<(?:subagent_notification|task-notification)>.*"
        r"</(?:subagent_notification|task-notification)>",
        stripped,
        re.DOTALL | re.IGNORECASE,
    ):
        return True
    return bool(CODEX_SUBAGENT_MESSAGE_RE.match(stripped))


def is_pure_codex_meta_command(text: str) -> bool:
    return bool(CODEX_META_COMMAND_RE.fullmatch(text.strip()))


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


def codex_uuid_from_filename(transcript_path: Path) -> str:
    match = re.search(r"([0-9a-f-]{36})\.jsonl$", transcript_path.name, re.IGNORECASE)
    if match and UUID_RE.fullmatch(match.group(1)):
        return match.group(1)
    return ""


def extract_codex_session_meta(transcript_path: Path) -> dict:
    expected_id = codex_uuid_from_filename(transcript_path).lower()
    first_meta: dict | None = None
    with transcript_path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict) or row.get("type") != "session_meta":
                continue
            payload = row.get("payload")
            if not isinstance(payload, dict):
                continue
            first_meta = first_meta or payload
            session_id = payload.get("id") or payload.get("session_id")
            if (
                expected_id
                and isinstance(session_id, str)
                and session_id.lower() == expected_id
            ):
                return payload
    return first_meta or {}


def is_codex_subagent_transcript(meta: dict) -> bool:
    source = meta.get("source")
    return isinstance(source, dict) and isinstance(source.get("subagent"), dict)


def is_substantive_codex_user(row: dict) -> bool:
    if row.get("type") != "response_item":
        return False
    message = row.get("payload")
    if not isinstance(message, dict) or message.get("role") != "user":
        return False

    parts = [
        part
        for part in codex_input_text_parts(message)
        if not is_codex_synthetic_part(part)
    ]
    if not parts:
        return False
    return not is_pure_codex_meta_command("\n".join(parts))


def extract_codex_user_timestamps(transcript_path: Path) -> list[datetime]:
    meta = extract_codex_session_meta(transcript_path)
    if is_codex_subagent_transcript(meta):
        return []

    timestamps: list[datetime] = []
    with transcript_path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict) or not is_substantive_codex_user(row):
                continue
            raw = row.get("timestamp")
            if not isinstance(raw, str):
                continue
            try:
                timestamps.append(parse_claude_timestamp(raw))
            except ValueError:
                continue
    return timestamps


def extract_codex_started_at(transcript_path: Path) -> datetime | None:
    raw = extract_codex_session_meta(transcript_path).get("timestamp")
    if not isinstance(raw, str):
        return None
    try:
        return parse_claude_timestamp(raw)
    except ValueError:
        return None


def detect_source(transcript_path: Path) -> str:
    with transcript_path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("type") == "session_meta" and isinstance(
                payload.get("payload"), dict
            ):
                return "codex"
            if payload.get("type") == "response_item" and isinstance(
                payload.get("payload"), dict
            ):
                response = payload["payload"]
                if response.get("type") == "message" and response.get("role") in {
                    "user",
                    "assistant",
                }:
                    return "codex"
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


def codex_home_path() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def find_codex_transcript(
    session_uuid: str, codex_home: Path | None = None
) -> Path | None:
    if not UUID_RE.fullmatch(session_uuid):
        return None
    normalized_uuid = session_uuid.lower()
    sessions_root = (codex_home or codex_home_path()) / "sessions"
    if not sessions_root.is_dir():
        return None
    matches = sorted(
        path
        for path in sessions_root.glob(f"**/rollout-*-{normalized_uuid}.jsonl")
        if path.is_file()
    )
    return matches[-1] if matches else None


def find_transcript(session_uuid: str, explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit if explicit.is_file() else None

    codex_match = find_codex_transcript(session_uuid)
    current_codex_id = os.environ.get("CODEX_THREAD_ID", "")
    if codex_match and current_codex_id.lower() == session_uuid.lower():
        return codex_match

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
    return codex_match


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


def infer_codex_uuid(transcript_path: Path) -> str:
    meta = extract_codex_session_meta(transcript_path)
    session_id = meta.get("id") or meta.get("session_id")
    if isinstance(session_id, str) and UUID_RE.fullmatch(session_id):
        return session_id
    return codex_uuid_from_filename(transcript_path)


def infer_uuid(transcript_path: Path, source: str) -> str:
    if source == "claude":
        return infer_claude_uuid(transcript_path)
    if source == "codex":
        return infer_codex_uuid(transcript_path)
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
    elif source == "codex":
        user_ts = extract_codex_user_timestamps(transcript_path)
    else:
        user_ts = extract_cursor_user_timestamps(transcript_path)

    started = (
        extract_codex_started_at(transcript_path)
        if source == "codex"
        else (user_ts[0] if user_ts else None)
    )
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
        help="Path to a supported session transcript",
    )
    parser.add_argument(
        "--uuid",
        help="Session UUID; locates a Cursor, Claude, or Codex transcript",
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

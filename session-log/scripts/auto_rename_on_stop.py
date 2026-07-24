#!/usr/bin/env python3
"""Cursor/Claude Stop hook: run a final `/rename …` line through the CLI via tmux.

Reads Stop-hook JSON from stdin. Claude prefers `last_assistant_message`; both
platforms can fall back to their transcript. Always prints `{}` and fails open.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

RENAME_LINE_RE = re.compile(r"^/rename\s+(.+?)\s*$")


def emit_empty() -> None:
    sys.stdout.write("{}\n")


def assistant_text(message: object) -> str:
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
    return "\n".join(parts)


def transcript_state(transcript_path: Path) -> tuple[str, str | None]:
    last_text = ""
    latest_title: str | None = None
    with transcript_path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue

            if row.get("type") == "custom-title":
                title = row.get("customTitle")
                if isinstance(title, str):
                    latest_title = title
                continue

            message = row.get("message")
            is_assistant = (
                row.get("type") == "assistant"
                or row.get("role") == "assistant"
                or (isinstance(message, dict) and message.get("role") == "assistant")
            )
            if not is_assistant:
                continue
            text = assistant_text(message)
            if text.strip():
                last_text = text
    return last_text, latest_title


def rename_from_text(text: str) -> tuple[str, str] | None:
    for raw in reversed(text.splitlines()):
        candidate = raw.strip()
        if not candidate:
            continue
        match = RENAME_LINE_RE.fullmatch(candidate)
        if not match:
            return None
        title = match.group(1).strip()
        return candidate, title
    return None


def send_rename_via_tmux(pane: str, rename: str) -> bool:
    """Clear input line, type /rename …, Enter — so CLI slash handling runs."""
    try:
        subprocess.run(
            ["tmux", "send-keys", "-t", pane, "C-u"],
            check=False,
            capture_output=True,
            timeout=3,
        )
        subprocess.run(
            ["tmux", "send-keys", "-t", pane, "-l", "--", rename],
            check=False,
            capture_output=True,
            timeout=3,
        )
        subprocess.run(
            ["tmux", "send-keys", "-t", pane, "Enter"],
            check=False,
            capture_output=True,
            timeout=3,
        )
        return True
    except Exception:
        return False


def process_payload(payload: object, pane: str) -> bool:
    if not isinstance(payload, dict) or payload.get("stop_hook_active"):
        return False

    status = payload.get("status")
    hook_event = payload.get("hook_event_name")
    if status is not None and status != "completed":
        return False
    if status is None and hook_event != "Stop":
        return False

    path_raw = payload.get("transcript_path") or os.environ.get(
        "CURSOR_TRANSCRIPT_PATH"
    )
    path = Path(path_raw) if isinstance(path_raw, str) and path_raw else None

    transcript_text = ""
    latest_title: str | None = None
    if path and path.is_file():
        try:
            transcript_text, latest_title = transcript_state(path)
        except Exception:
            pass

    direct_text = payload.get("last_assistant_message")
    selected_text = (
        direct_text
        if isinstance(direct_text, str) and direct_text.strip()
        else transcript_text
    )
    requested = rename_from_text(selected_text)
    if not requested or not pane:
        return False

    rename, title = requested
    if latest_title == title:
        return False
    return send_rename_via_tmux(pane, rename)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        emit_empty()
        return 0

    pane = os.environ.get("TMUX_PANE", "").strip()
    try:
        process_payload(payload, pane)
    except Exception:
        pass

    emit_empty()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

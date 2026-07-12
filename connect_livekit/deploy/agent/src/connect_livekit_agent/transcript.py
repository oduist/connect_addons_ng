"""Extract a transcript payload from a finished AgentSession history."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def extract_messages(history) -> list[dict]:
    """Normalize the session chat history into role/text/ts dicts.

    Accepts either a livekit-agents ChatHistory-like object (``.items``)
    or an already-serialized dict; unknown item shapes are skipped so an
    SDK change never crashes the delivery path.
    """
    items = []
    if history is None:
        return items
    raw = getattr(history, "items", None)
    if raw is None and isinstance(history, dict):
        raw = history.get("items")
    for item in raw or []:
        role = getattr(item, "role", None)
        content = getattr(item, "content", None)
        if role is None and isinstance(item, dict):
            role = item.get("role")
            content = item.get("content")
        if role not in ("user", "assistant"):
            continue
        text = _content_text(content)
        if text:
            items.append({"role": role, "text": text})
    return items


def _content_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, (list, tuple)):
        parts = [c for c in content if isinstance(c, str)]
        return " ".join(parts).strip()
    return str(content).strip()


def build_payload(room_name, channel_sid, history, duration_secs,
                  summary="") -> dict:
    return {
        "room_name": room_name,
        "channel_sid": channel_sid,
        "messages": extract_messages(history),
        "summary": summary or "",
        "duration_secs": int(duration_secs or 0),
    }

"""Transcript extraction tests (no LiveKit runtime needed)."""
from connect_livekit_agent import transcript


class _Item:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class _History:
    def __init__(self, items):
        self.items = items


def test_extract_messages_from_objects():
    history = _History([
        _Item("user", "Hello"),
        _Item("assistant", "Hi, how can I help?"),
        _Item("system", "ignored"),
    ])
    msgs = transcript.extract_messages(history)
    assert msgs == [
        {"role": "user", "text": "Hello"},
        {"role": "assistant", "text": "Hi, how can I help?"},
    ]


def test_extract_messages_from_dicts():
    history = {"items": [
        {"role": "user", "content": ["Part one", "part two"]},
        {"role": "assistant", "content": ""},
    ]}
    msgs = transcript.extract_messages(history)
    assert msgs == [{"role": "user", "text": "Part one part two"}]


def test_extract_messages_none():
    assert transcript.extract_messages(None) == []


def test_build_payload():
    payload = transcript.build_payload(
        room_name="ai-out-abc", channel_sid="SIP_1",
        history=_History([_Item("user", "Hi")]),
        duration_secs=42, summary="Short call")
    assert payload["room_name"] == "ai-out-abc"
    assert payload["channel_sid"] == "SIP_1"
    assert payload["summary"] == "Short call"
    assert payload["duration_secs"] == 42
    assert payload["messages"] == [{"role": "user", "text": "Hi"}]

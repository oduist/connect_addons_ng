import json


REDACTED = '[redacted]'


def redact_telnyx_debug_payload(payload):
    """Return a debug-safe copy without signed recording URLs."""
    if isinstance(payload, dict):
        redacted = {}
        for key, value in payload.items():
            normalized_key = ''.join(
                char for char in str(key).lower() if char.isalnum()
            )
            if normalized_key == 'recordingurl':
                redacted[key] = REDACTED
            else:
                redacted[key] = redact_telnyx_debug_payload(value)
        return redacted
    if isinstance(payload, (list, tuple)):
        return [redact_telnyx_debug_payload(value) for value in payload]
    return payload


def format_telnyx_debug_payload(payload):
    return json.dumps(redact_telnyx_debug_payload(payload), indent=2)

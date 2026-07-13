"""Event selection rules — the agent-side half of the contract with the
``/asterisk/webhook/events`` controller in ``connect_asterisk``.

The agent forwards a fixed allowlist of AMI events with their original
field names; all semantics (status mapping, direction, user matching)
live in Odoo. Guard conditions below replicate what the legacy
``asterisk_plus.event`` registry expressed as code strings, so the
uninteresting 99% of AMI traffic never leaves the box.
"""

# Default forwarded events; Odoo can narrow/extend the list via /config.
DEFAULT_EVENTS = (
    "Newchannel",
    "Newstate",
    "Hangup",
    "NewConnectedLine",
    "OriginateResponse",
    "VarSet",
)

# AMI Events mask requested at login (class-level filter).
AMI_EVENT_MASK = "call,dialplan,user"

# Headers worth keeping when forwarding an event to Odoo. Everything
# else (account codes, language, priorities) is dropped to keep the
# payload small; Odoo never reads those fields.
FORWARDED_FIELDS = (
    "Event",
    "Uniqueid",
    "Linkedid",
    "Channel",
    "CallerIDNum",
    "CallerIDName",
    "ConnectedLineNum",
    "Exten",
    "Context",
    "ChannelStateDesc",
    "Cause",
    "Cause-txt",
    "Response",
    "Reason",
    "Variable",
    "Value",
)


def event_passes(event: dict) -> bool:
    """Per-event guard conditions (the cheap, mechanical filters)."""
    name = event.get("Event")
    channel = event.get("Channel", "")
    if channel.startswith("Local/"):
        return False
    if name == "Newstate":
        return event.get("ChannelStateDesc") == "Up"
    if name == "VarSet":
        return event.get("Variable") == "MIXMONITOR_FILENAME"
    if name == "OriginateResponse":
        return event.get("Response") == "Failure"
    return True

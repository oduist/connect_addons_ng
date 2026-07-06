"""AMI handler pipeline tests (filter → trim → stamp → enqueue)."""
from unittest.mock import MagicMock

from connect_asterisk_agent.ami_handler import AMIHandler
from connect_asterisk_agent.call_state import CallState


def _handler(recordings=None):
    odoo = MagicMock()
    state = CallState()
    handler = AMIHandler(
        odoo=odoo, call_state=state, recordings=recordings)
    return handler, odoo, state


def test_forwarded_event_trimmed_and_stamped():
    handler, odoo, _ = _handler()
    handler.handle({
        "Event": "Newchannel",
        "Uniqueid": "uid-1",
        "Linkedid": "uid-1",
        "Channel": "PJSIP/101-0001",
        "CallerIDNum": "101",
        "Exten": "102",
        "ChannelStateDesc": "Ring",
        "AccountCode": "noise",
        "Language": "en",
    })
    assert odoo.enqueue_event.call_count == 1
    payload = odoo.enqueue_event.call_args.args[0]
    assert payload["Event"] == "Newchannel"
    assert payload["Uniqueid"] == "uid-1"
    assert isinstance(payload["EventTime"], float)
    assert "AccountCode" not in payload
    assert "Language" not in payload


def test_disallowed_event_dropped():
    handler, odoo, _ = _handler()
    handler.handle({"Event": "PeerStatus", "Channel": "PJSIP/101"})
    handler.handle({"Event": "Newchannel", "Channel": "Local/1@x-0001;1"})
    assert odoo.enqueue_event.call_count == 0
    assert handler.dropped_count == 2


def test_hangup_schedules_recording_upload():
    recordings = MagicMock()
    handler, _, state = _handler(recordings=recordings)
    handler.handle({
        "Event": "Newchannel", "Uniqueid": "uid-1", "Linkedid": "uid-1",
        "Channel": "PJSIP/101-0001", "ChannelStateDesc": "Ring"})
    handler.handle({
        "Event": "VarSet", "Uniqueid": "uid-1",
        "Channel": "PJSIP/101-0001",
        "Variable": "MIXMONITOR_FILENAME", "Value": "/tmp/uid-1.wav"})
    handler.handle({
        "Event": "Hangup", "Uniqueid": "uid-1", "Linkedid": "uid-1",
        "Channel": "PJSIP/101-0001", "Cause": "16",
        "ChannelStateDesc": "Up"})
    recordings.schedule.assert_called_once_with("uid-1", "/tmp/uid-1.wav")


def test_set_events_narrows_allowlist():
    handler, odoo, _ = _handler()
    handler.set_events(["Hangup"])
    handler.handle({
        "Event": "Newchannel", "Uniqueid": "u", "Channel": "PJSIP/1-1",
        "ChannelStateDesc": "Ring"})
    assert odoo.enqueue_event.call_count == 0
    handler.handle({
        "Event": "Hangup", "Uniqueid": "u", "Channel": "PJSIP/1-1",
        "Cause": "16"})
    assert odoo.enqueue_event.call_count == 1

"""Event guard-condition tests (the agent-side contract half)."""
from connect_asterisk_agent.constants import event_passes


def test_local_channels_dropped():
    assert not event_passes({
        "Event": "Newchannel", "Channel": "Local/101@ctx-0001;2"})
    assert event_passes({
        "Event": "Newchannel", "Channel": "PJSIP/101-0001"})


def test_newstate_only_up():
    assert event_passes({
        "Event": "Newstate", "Channel": "PJSIP/101-1",
        "ChannelStateDesc": "Up"})
    assert not event_passes({
        "Event": "Newstate", "Channel": "PJSIP/101-1",
        "ChannelStateDesc": "Ringing"})


def test_varset_only_mixmonitor():
    assert event_passes({
        "Event": "VarSet", "Channel": "PJSIP/101-1",
        "Variable": "MIXMONITOR_FILENAME", "Value": "/tmp/x.wav"})
    assert not event_passes({
        "Event": "VarSet", "Channel": "PJSIP/101-1",
        "Variable": "SIPURI", "Value": "sip:x"})


def test_originate_response_only_failure():
    assert event_passes({
        "Event": "OriginateResponse", "Response": "Failure"})
    assert not event_passes({
        "Event": "OriginateResponse", "Response": "Success"})


def test_hangup_passes():
    assert event_passes({
        "Event": "Hangup", "Channel": "PJSIP/101-1", "Cause": "16"})

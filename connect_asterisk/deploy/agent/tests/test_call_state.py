"""Channel registry tests."""
import time

from connect_asterisk_agent.call_state import CallState


def _new(uid, channel="PJSIP/101-0001"):
    return {"Event": "Newchannel", "Uniqueid": uid, "Channel": channel}


def test_tracks_lifecycle():
    state = CallState()
    state.on_event(_new("uid-1"))
    assert state.active_uniqueids() == {"uid-1"}
    state.on_event({"Event": "Hangup", "Uniqueid": "uid-1"})
    assert state.active_uniqueids() == set()


def test_recording_path_capture_and_pop():
    state = CallState()
    state.on_event(_new("uid-1"))
    state.on_event({
        "Event": "VarSet", "Uniqueid": "uid-1",
        "Variable": "MIXMONITOR_FILENAME", "Value": "/tmp/uid-1.wav"})
    assert state.pop_recording("uid-1") == "/tmp/uid-1.wav"
    # Popping twice returns nothing.
    assert state.pop_recording("uid-1") == ""
    assert state.pop_recording("unknown") == ""


def test_varset_before_newchannel_creates_entry():
    state = CallState()
    state.on_event({
        "Event": "VarSet", "Uniqueid": "uid-2",
        "Variable": "MIXMONITOR_FILENAME", "Value": "/tmp/uid-2.wav"})
    assert state.pop_recording("uid-2") == "/tmp/uid-2.wav"


def test_evict_stale():
    state = CallState(ttl=10)
    state.on_event(_new("uid-old"))
    state.on_event(_new("uid-done"))
    state.on_event({"Event": "Hangup", "Uniqueid": "uid-done"})
    state._channels["uid-old"].created_at = time.time() - 100
    evicted = state.evict_stale()
    assert evicted == 2
    assert state.get("uid-old") is None
    assert state.get("uid-done") is None


def test_hung_up_with_pending_recording_not_evicted():
    state = CallState()
    state.on_event(_new("uid-rec"))
    state.on_event({
        "Event": "VarSet", "Uniqueid": "uid-rec",
        "Variable": "MIXMONITOR_FILENAME", "Value": "/tmp/uid-rec.wav"})
    state.on_event({"Event": "Hangup", "Uniqueid": "uid-rec"})
    state.evict_stale()
    # Still there: the uploader has not popped the recording yet.
    assert state.get("uid-rec") is not None

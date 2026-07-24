"""Event normalization and the participant registry."""
from unittest.mock import AsyncMock, MagicMock

from connect_3cx_agent.handler import (
    CallControlHandler,
    parse_participant_entity,
)
from connect_3cx_agent.state import ParticipantRegistry


def make_handler(entity_state=None):
    tcx = MagicMock()
    tcx.get_entity = AsyncMock(return_value=entity_state)
    odoo = MagicMock()
    registry = ParticipantRegistry()
    handler = CallControlHandler(tcx=tcx, odoo=odoo, registry=registry)
    return handler, tcx, odoo, registry


def emitted(odoo):
    return [call.args[0] for call in odoo.enqueue_event.call_args_list]


def test_parse_participant_entity():
    assert parse_participant_entity(
        "/callcontrol/101/participants/5") == ("101", "5")
    assert parse_participant_entity(
        "callcontrol/101/participants/5") == ("101", "5")
    assert parse_participant_entity("/callcontrol/101") is None
    assert parse_participant_entity(
        "/callcontrol/101/devices/abc") is None
    assert parse_participant_entity(None) is None


async def test_upsert_fetches_state_and_emits():
    state = {"status": "Ringing", "party_caller_id": "+15551234567",
             "callid": 17, "legid": 2}
    handler, tcx, odoo, registry = make_handler(state)
    await handler.handle_message({
        "sequence": 1,
        "event": {"event_type": 0,
                  "entity": "/callcontrol/101/participants/5"},
    })
    tcx.get_entity.assert_awaited_once_with(
        "/callcontrol/101/participants/5")
    events = emitted(odoo)
    assert len(events) == 1
    event = events[0]
    assert event["event"] == "upsert"
    assert event["dn"] == "101"
    assert event["participant_id"] == "5"
    assert event["state"] == state
    assert event["answered_at"] is None
    assert registry.get("/callcontrol/101/participants/5") is not None


async def test_connected_upsert_stamps_answered():
    handler, tcx, odoo, registry = make_handler(
        {"status": "Connected", "callid": 17, "legid": 2})
    await handler.handle_message({
        "event": {"event_type": 0,
                  "entity": "/callcontrol/101/participants/5"},
    })
    event = emitted(odoo)[0]
    assert event["answered_at"] is not None


async def test_remove_uses_last_known_state():
    handler, tcx, odoo, registry = make_handler(
        {"status": "Connected", "callid": 17, "legid": 2})
    entity = "/callcontrol/101/participants/5"
    await handler.handle_message(
        {"event": {"event_type": 0, "entity": entity}})
    await handler.handle_message(
        {"event": {"event_type": 1, "entity": entity}})
    events = emitted(odoo)
    assert events[1]["event"] == "remove"
    assert events[1]["state"]["callid"] == 17
    assert events[1]["answered_at"] is not None
    assert registry.get(entity) is None


async def test_remove_unknown_participant_still_emits():
    handler, tcx, odoo, registry = make_handler()
    await handler.handle_message({
        "event": {"event_type": 1,
                  "entity": "/callcontrol/102/participants/9"},
    })
    event = emitted(odoo)[0]
    assert event["event"] == "remove"
    assert event["dn"] == "102"
    assert event["state"] == {}


async def test_upsert_fetch_failure_keeps_last_state():
    handler, tcx, odoo, registry = make_handler(
        {"status": "Ringing", "callid": 3, "legid": 1})
    entity = "/callcontrol/101/participants/5"
    await handler.handle_message(
        {"event": {"event_type": 0, "entity": entity}})
    # Second upsert: the participant is already gone on the PBX.
    tcx.get_entity = AsyncMock(side_effect=Exception("410 gone"))
    await handler.handle_message(
        {"event": {"event_type": 0, "entity": entity}})
    events = emitted(odoo)
    assert len(events) == 2
    assert events[1]["state"]["callid"] == 3


async def test_non_participant_and_dtmf_dropped():
    handler, tcx, odoo, registry = make_handler({"status": "Ringing"})
    await handler.handle_message(
        {"event": {"event_type": 0, "entity": "/callcontrol/101"}})
    await handler.handle_message(
        {"event": {"event_type": 2,
                   "entity": "/callcontrol/101/participants/5"}})
    assert not odoo.enqueue_event.called
    assert handler.dropped_count == 2


def test_synthetic_remove():
    handler, tcx, odoo, registry = make_handler()
    registry.on_upsert("/callcontrol/101/participants/5", "101", "5",
                       {"status": "Connected", "callid": 8, "legid": 1})
    handler.emit_synthetic_remove("/callcontrol/101/participants/5")
    event = emitted(odoo)[0]
    assert event["event"] == "remove"
    assert event["state"]["callid"] == 8
    assert registry.active_entities() == set()

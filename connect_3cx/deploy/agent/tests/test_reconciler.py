"""Config pull and participant reconciliation."""
from unittest.mock import AsyncMock, MagicMock

from connect_3cx_agent.handler import CallControlHandler
from connect_3cx_agent.reconciler import (
    Reconciler,
    live_participant_entities,
)
from connect_3cx_agent.state import ParticipantRegistry


def test_live_participant_entities_defensive():
    dump = [
        {"dn": "101", "participants": [{"id": 5}, {"id": 6}]},
        {"number": "102", "participants": [{"id": 1}]},
        {"dn": "103"},                     # no participants key
        {"participants": [{"id": 9}]},     # no dn -> skipped
        "garbage",
    ]
    assert live_participant_entities(dump) == {
        "/callcontrol/101/participants/5",
        "/callcontrol/101/participants/6",
        "/callcontrol/102/participants/1",
    }
    assert live_participant_entities(None) == set()
    assert live_participant_entities({"dn": "101"}) == set()


async def test_reconcile_emits_removes_for_stale(settings):
    registry = ParticipantRegistry()
    registry.on_upsert("/callcontrol/101/participants/5", "101", "5",
                       {"status": "Connected", "callid": 1, "legid": 1})
    registry.on_upsert("/callcontrol/101/participants/6", "101", "6",
                       {"status": "Ringing", "callid": 2, "legid": 1})
    tcx = MagicMock()
    tcx.configured.return_value = True
    tcx.callcontrol_state = AsyncMock(return_value=[
        {"dn": "101", "participants": [{"id": 6}]},
    ])
    odoo = MagicMock()
    handler = CallControlHandler(tcx=tcx, odoo=odoo, registry=registry)
    reconciler = Reconciler(settings=settings, odoo=odoo, tcx=tcx,
                            handler=handler, registry=registry)
    await reconciler.run_once({"participants"})
    events = [call.args[0] for call in odoo.enqueue_event.call_args_list]
    assert len(events) == 1
    assert events[0]["event"] == "remove"
    assert events[0]["entity"] == "/callcontrol/101/participants/5"
    assert registry.active_entities() == {
        "/callcontrol/101/participants/6"}


async def test_config_pull_updates_credentials(settings, tmp_path):
    odoo = MagicMock()
    odoo.get = AsyncMock(return_value={
        "pbx_url": "https://new-pbx.test",
        "client_id": "new-id",
        "client_secret": "new-secret",
        "recordings_enabled": False,
    })
    tcx = MagicMock()
    registry = ParticipantRegistry()
    handler = CallControlHandler(tcx=tcx, odoo=odoo, registry=registry)
    reconciler = Reconciler(settings=settings, odoo=odoo, tcx=tcx,
                            handler=handler, registry=registry)
    await reconciler.run_once({"config"})
    assert settings.pbx_url == "https://new-pbx.test"
    assert settings.client_id == "new-id"
    assert settings.recordings_enabled is False
    tcx.invalidate_token.assert_called()
    cache_path = tmp_path / "config.json"
    assert cache_path.is_file()
    assert "new-secret" in cache_path.read_text()

"""Agent HTTP API: auth middleware and originate."""
import time
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from connect_3cx_agent.http_server import build_app

TOKEN = "test-agent-token-0123456789abcdef"


def make_client(settings, makecall_result=None, makecall_error=None):
    tcx = MagicMock()
    tcx.configured.return_value = True
    tcx.last_token_ok = True
    if makecall_error is not None:
        tcx.makecall = AsyncMock(side_effect=makecall_error)
    else:
        tcx.makecall = AsyncMock(
            return_value=makecall_result or {"result": {"callid": 7}})
    odoo = MagicMock()
    odoo.last_call_ok = True
    odoo.outbox_depth.return_value = 0
    handler = MagicMock()
    handler.forwarded_count = 3
    handler.dropped_count = 1
    ws = MagicMock()
    ws.is_connected = True
    recordings = MagicMock()
    recordings.uploaded_count = 2
    recordings.failed_count = 0
    reconciler = MagicMock()
    app = build_app(settings, tcx, odoo, handler, ws, recordings,
                    reconciler, time.time())
    return TestClient(app), tcx, reconciler


def auth():
    return {"Authorization": "Bearer " + TOKEN}


def test_healthz_unauthenticated(settings):
    client, _, _ = make_client(settings)
    assert client.get("/healthz").status_code == 200
    assert client.get("/3cx/healthz").status_code == 200


def test_api_requires_bearer(settings):
    client, _, _ = make_client(settings)
    assert client.get("/api/status").status_code == 401
    assert client.post("/originate", json={}).status_code == 401
    response = client.get("/api/status", headers=auth())
    assert response.status_code == 200
    assert response.json()["ws_connected"] is True


def test_originate(settings):
    client, tcx, _ = make_client(settings)
    response = client.post("/originate", headers=auth(), json={
        "dn": "101", "destination": "+15551234567", "timeout": 25})
    assert response.status_code == 200
    assert response.json()["response"]["result"]["callid"] == 7
    tcx.makecall.assert_awaited_once_with(
        "101", "+15551234567", timeout=25, device_id="")


def test_originate_validation_and_errors(settings):
    client, _, _ = make_client(settings)
    assert client.post("/originate", headers=auth(),
                       json={"dn": "101"}).status_code == 400
    client, _, _ = make_client(settings,
                               makecall_error=Exception("pbx down"))
    response = client.post("/originate", headers=auth(), json={
        "dn": "101", "destination": "1"})
    assert response.status_code == 502


def test_sync_triggers_reconciler(settings):
    client, _, reconciler = make_client(settings)
    response = client.post("/sync", headers=auth(),
                           json={"scope": "participants"})
    assert response.status_code == 200
    reconciler.trigger.assert_called_once_with(scope="participants")

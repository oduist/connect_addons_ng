"""Token manager and 3CX request plumbing."""
import json

import httpx
import pytest

from connect_3cx_agent.tcx_api import ThreeCXClient, ThreeCXError


def make_client(settings, handler):
    tcx = ThreeCXClient(settings)
    tcx._http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler))
    return tcx


async def test_token_cached_and_form_encoded(settings):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.path == "/connect/token"
        body = request.content.decode()
        assert "grant_type=client_credentials" in body
        assert "client_id=agent-client" in body
        return httpx.Response(200, json={
            "token_type": "Bearer", "access_token": "tok-1",
            "expires_in": 3600})

    tcx = make_client(settings, handler)
    assert await tcx.token() == "tok-1"
    assert await tcx.token() == "tok-1"
    assert len(calls) == 1
    assert tcx.last_token_ok


async def test_token_failure_raises_and_flags(settings):
    def handler(request):
        return httpx.Response(401, json={"error": "invalid_client"})

    tcx = make_client(settings, handler)
    with pytest.raises(ThreeCXError):
        await tcx.token()
    assert not tcx.last_token_ok


async def test_request_retries_once_on_401(settings):
    state = {"tokens": 0, "gets": 0}

    def handler(request):
        if request.url.path == "/connect/token":
            state["tokens"] += 1
            return httpx.Response(200, json={
                "access_token": "tok-%d" % state["tokens"],
                "expires_in": 3600})
        state["gets"] += 1
        auth = request.headers.get("Authorization")
        if auth == "Bearer tok-1":
            # First token was invalidated PBX-side.
            return httpx.Response(401)
        return httpx.Response(200, json={"ok": True})

    tcx = make_client(settings, handler)
    result = await tcx.get_json("/callcontrol/101")
    assert result == {"ok": True}
    assert state["tokens"] == 2
    assert state["gets"] == 2


async def test_makecall_paths(settings):
    seen = []

    def handler(request):
        if request.url.path == "/connect/token":
            return httpx.Response(200, json={
                "access_token": "tok", "expires_in": 3600})
        seen.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"result": {"callid": 7}})

    tcx = make_client(settings, handler)
    await tcx.makecall("101", "+155501", timeout=25)
    await tcx.makecall("101", "+155502", device_id="dev1")
    assert seen[0] == ("/callcontrol/101/makecall",
                       {"destination": "+155501", "timeout": 25})
    assert seen[1][0] == "/callcontrol/101/devices/dev1/makecall"


async def test_list_recordings_after_parses_odata(settings):
    def handler(request):
        if request.url.path == "/connect/token":
            return httpx.Response(200, json={
                "access_token": "tok", "expires_in": 3600})
        assert "/xapi/v1/Recordings" in str(request.url)
        assert "Id%20gt%2010" in str(request.url) or \
            "Id gt 10" in str(request.url)
        return httpx.Response(200, json={
            "value": [{"Id": 11}, {"Id": 12}]})

    tcx = make_client(settings, handler)
    rows = await tcx.list_recordings_after(10)
    assert [r["Id"] for r in rows] == [11, 12]


def test_ws_url(settings):
    tcx = ThreeCXClient(settings)
    assert tcx.ws_url == "wss://pbx.test/callcontrol/ws"
    settings.pbx_url = "http://pbx.lan:5000"
    assert tcx.ws_url == "ws://pbx.lan:5000/callcontrol/ws"

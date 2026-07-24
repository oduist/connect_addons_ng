"""HTTP client for the 3CX PBX: OAuth2 tokens, Call Control, XAPI.

Both 3CX web APIs authenticate with client_credentials tokens from
``POST /connect/token`` (60-minute lifetime). 3CX keeps a SINGLE active
token per client application — issuing a new token invalidates the
previous one — so this class is the process-wide token owner: it
refreshes proactively at ~80% of ``expires_in``, single-flight, and
every consumer (WebSocket, REST, XAPI poller) goes through it.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 20.0
DOWNLOAD_TIMEOUT = 120.0
TOKEN_REFRESH_FACTOR = 0.8


class ThreeCXError(Exception):
    pass


class ThreeCXClient:
    def __init__(self, settings):
        # The settings object is shared with the reconciler, which
        # updates pbx_url/client_id/client_secret from the Odoo config
        # pull — read them lazily on every call.
        self.settings = settings
        self._http: httpx.AsyncClient | None = None
        self._token: str = ""
        self._token_expires_at: float = 0.0
        self._token_lock = asyncio.Lock()
        self.last_token_ok: bool = False

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------

    @property
    def base_url(self) -> str:
        return (self.settings.pbx_url or "").rstrip("/")

    @property
    def ws_url(self) -> str:
        base = self.base_url
        if base.startswith("https://"):
            return "wss://" + base[len("https://"):] + "/callcontrol/ws"
        if base.startswith("http://"):
            return "ws://" + base[len("http://"):] + "/callcontrol/ws"
        return ""

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=REQUEST_TIMEOUT,
                verify=self.settings.verify_tls,
            )
        return self._http

    async def close(self) -> None:
        if self._http is not None:
            try:
                await self._http.aclose()
            except Exception:
                pass
            self._http = None

    def configured(self) -> bool:
        return bool(self.base_url and self.settings.client_id
                    and self.settings.client_secret)

    def invalidate_token(self) -> None:
        self._token = ""
        self._token_expires_at = 0.0

    # ------------------------------------------------------------------
    # OAuth2 client_credentials
    # ------------------------------------------------------------------

    async def token(self) -> str:
        if self._token and time.time() < self._token_expires_at:
            return self._token
        async with self._token_lock:
            if self._token and time.time() < self._token_expires_at:
                return self._token
            if not self.configured():
                raise ThreeCXError("3CX PBX URL / API client not configured")
            try:
                resp = await self._client().post(
                    self.base_url + "/connect/token",
                    data={
                        "client_id": self.settings.client_id,
                        "client_secret": self.settings.client_secret,
                        "grant_type": "client_credentials",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                self._token = data.get("access_token") or ""
                expires_in = int(data.get("expires_in") or 3600)
                if not self._token:
                    raise ThreeCXError("Empty access_token from 3CX")
                self._token_expires_at = (
                    time.time() + expires_in * TOKEN_REFRESH_FACTOR)
                self.last_token_ok = True
                logger.debug("3CX token refreshed (expires_in=%s)",
                             expires_in)
                return self._token
            except Exception as exc:
                self.last_token_ok = False
                self.invalidate_token()
                raise ThreeCXError(
                    "3CX token request failed: {}".format(exc)) from exc

    async def _request(self, method: str, path: str,
                       timeout: float = REQUEST_TIMEOUT,
                       **kwargs) -> httpx.Response:
        """Authenticated request with a single retry on 401 (the PBX may
        have invalidated our token, e.g. after a service restart)."""
        url = self.base_url + path
        for attempt in (1, 2):
            token = await self.token()
            resp = await self._client().request(
                method, url, timeout=timeout,
                headers={"Authorization": "Bearer " + token},
                **kwargs)
            if resp.status_code == 401 and attempt == 1:
                logger.info("3CX replied 401 on %s; refreshing token", path)
                self.invalidate_token()
                continue
            resp.raise_for_status()
            return resp
        raise ThreeCXError("Unreachable")  # pragma: no cover

    async def get_json(self, path: str) -> Any:
        resp = await self._request("GET", path)
        return resp.json() if resp.content else None

    async def post_json(self, path: str, payload: Any) -> Any:
        resp = await self._request("POST", path, json=payload)
        return resp.json() if resp.content else None

    # ------------------------------------------------------------------
    # Call Control API
    # ------------------------------------------------------------------

    async def callcontrol_state(self) -> Any:
        """Full visible state: all monitored DNs with devices and
        participants."""
        return await self.get_json("/callcontrol")

    async def get_entity(self, entity: str) -> Any:
        """Fetch an entity by the path delivered in a WS event
        (e.g. /callcontrol/101/participants/5)."""
        if not entity.startswith("/"):
            entity = "/" + entity
        return await self.get_json(entity)

    async def makecall(self, dn: str, destination: str,
                       timeout: int = 30, device_id: str = "") -> Any:
        """Originate a call from a DN (optionally from a specific
        device)."""
        if device_id:
            path = "/callcontrol/{}/devices/{}/makecall".format(
                dn, device_id)
        else:
            path = "/callcontrol/{}/makecall".format(dn)
        return await self.post_json(
            path, {"destination": destination, "timeout": timeout})

    # ------------------------------------------------------------------
    # XAPI (Configuration API)
    # ------------------------------------------------------------------

    async def list_recordings_after(self, last_id: int,
                                    top: int = 50) -> list:
        """List recordings with Id greater than last_id, oldest first."""
        path = ("/xapi/v1/Recordings?$filter=Id gt {}"
                "&$orderby=Id asc&$top={}").format(int(last_id), int(top))
        data = await self.get_json(path.replace(" ", "%20"))
        if isinstance(data, dict):
            return data.get("value") or []
        return data or []

    async def download_recording(self, rec_id: int) -> bytes:
        resp = await self._request(
            "GET",
            "/xapi/v1/Recordings/Pbx.DownloadRecording(recId={})".format(
                int(rec_id)),
            timeout=DOWNLOAD_TIMEOUT,
        )
        return resp.content

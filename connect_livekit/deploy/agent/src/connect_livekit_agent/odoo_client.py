"""Thin HTTP client for the Odoo LiveKit endpoints (Bearer auth)."""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OdooClient:
    def __init__(self, base_url: str, agent_token: str, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.agent_token = agent_token
        self.timeout = timeout

    def _bearer_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.agent_token}"}

    def post_heartbeat_sync(self) -> None:
        """Best-effort liveness marker (settings 'Worker Last Seen')."""
        try:
            httpx.post(
                f"{self.base_url}/livekit/api/heartbeat",
                headers=self._bearer_headers(),
                timeout=10.0,
            )
        except httpx.HTTPError as exc:
            logger.warning("Heartbeat failed: %s", exc)

    async def post_heartbeat(self) -> None:
        """Async variant used from the job entrypoint."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                await client.post(
                    f"{self.base_url}/livekit/api/heartbeat",
                    headers=self._bearer_headers(),
                )
        except httpx.HTTPError as exc:
            logger.warning("Heartbeat failed: %s", exc)

    async def get_agent_config(self, agent_id: int) -> dict[str, Any]:
        """Fetch per-agent configuration from /livekit/api/agent_config."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{self.base_url}/livekit/api/agent_config",
                params={"agent_id": agent_id},
                headers=self._bearer_headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def call_tool(
        self, agent_id: int, tool_token: str, tool_name: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Invoke a server-side tool; authed by the per-agent tool token."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/livekit/webhook/agent/{agent_id}/tool/"
                f"{tool_name}",
                json=payload,
                headers={"X-Odoo-LiveKit-Token": tool_token},
            )
            if resp.status_code >= 400:
                logger.warning("Tool %s failed: HTTP %s %s", tool_name,
                               resp.status_code, resp.text[:200])
                return {"ok": False, "error": f"http_{resp.status_code}"}
            return resp.json()

    async def post_transcript(
        self, agent_id: int, tool_token: str, payload: dict[str, Any],
    ) -> None:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/livekit/webhook/agent/{agent_id}/transcript",
                json=payload,
                headers={"X-Odoo-LiveKit-Token": tool_token},
            )
            resp.raise_for_status()

    def upload_recording_sync(self, filename: str, data: bytes) -> bool:
        """Blocking PUT of one egress file (used by the uploader thread)."""
        try:
            resp = httpx.put(
                f"{self.base_url}/livekit/webhook/recording/{filename}",
                content=data,
                headers=self._bearer_headers(),
                timeout=120.0,
            )
            if resp.status_code >= 400:
                logger.warning("Upload %s failed: HTTP %s", filename,
                               resp.status_code)
                return False
            return True
        except httpx.HTTPError as exc:
            logger.warning("Upload %s error: %s", filename, exc)
            return False

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)


class OdooClient:
    def __init__(self, base_url: str, token: str):
        self._base_url = base_url.rstrip('/')
        self._client = httpx.AsyncClient(
            headers={'Authorization': 'Bearer {}'.format(token)}, timeout=10.0,
        )

    async def close(self):
        await self._client.aclose()

    async def _request(self, method: str, path: str, *, json=None, retries=3):
        error = None
        for attempt in range(retries):
            try:
                response = await self._client.request(
                    method, self._base_url + path, json=json,
                )
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                error = exc
                if attempt + 1 < retries:
                    await asyncio.sleep(0.5 * (2 ** attempt))
        raise RuntimeError('Odoo request {} failed: {}'.format(path, error)) from error

    async def get_agent(self, agent_id: int):
        return await self._request('GET', '/pipecat/agent/{}'.format(agent_id))

    async def post_call_result(self, call_uuid: str, transcript: str, summary: str):
        # The FreeSWITCH CDR can land just after the media WebSocket closes.
        # A longer retry window lets Odoo create the connect.channel first.
        return await self._request('POST', '/pipecat/call-result', json={
            'call_uuid': call_uuid,
            'transcript': transcript,
            'summary': summary,
        }, retries=6)

    async def hangup(self, call_uuid: str):
        return await self._request('POST', '/pipecat/hangup', json={
            'call_uuid': call_uuid,
        })

    async def transfer(self, call_uuid: str, agent_id: int):
        return await self._request('POST', '/pipecat/transfer', json={
            'call_uuid': call_uuid,
            'agent_id': agent_id,
        })

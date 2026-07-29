"""XAPI recording poller.

Unlike Asterisk (files pushed from a mounted monitor directory), 3CX
recordings are fetched over HTTPS: the poller tracks the highest seen
recording Id in the agent state file, lists newer ``Recordings`` rows
through the XAPI, downloads each audio file and PUTs it to the Odoo
recording webhook together with whatever metadata the row carried.

The Recordings row shape is only partially documented, so metadata is
passed through defensively: a candidate list of field names is probed
and forwarded as query parameters; Odoo matches the channel by call id
when present and keeps the recording as an orphan otherwise.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from urllib.parse import quote, urlencode

from .odoo_client import OdooClient
from .tcx_api import ThreeCXClient

logger = logging.getLogger(__name__)

# Candidate metadata fields observed in community XAPI dumps; unknown
# names are simply absent from a given PBX version and get skipped.
META_FIELDS = {
    "CallId": "callid",
    "FromCallerNumber": "caller",
    "ToCallerNumber": "called",
    "FromDn": "from_dn",
    "ToDn": "to_dn",
    "StartTime": "start_time",
    "EndTime": "end_time",
    "Duration": "duration",
    "RecordingUrl": "recording_url",
}
POLL_FAIL_DELAY = 15.0


class RecordingPoller:
    def __init__(self, tcx: ThreeCXClient, odoo: OdooClient,
                 settings, state_path: str):
        self.tcx = tcx
        self.odoo = odoo
        self.settings = settings
        self.state_path = state_path
        self.last_rec_id = 0
        self.uploaded_count = 0
        self.failed_count = 0
        self._load_state()

    # ------------------------------------------------------------------
    # Local state (last seen recording id)
    # ------------------------------------------------------------------

    def _load_state(self) -> None:
        path = Path(self.state_path)
        if not path.is_file():
            return
        try:
            data = json.loads(path.read_text())
            self.last_rec_id = int(data.get("last_rec_id") or 0)
        except Exception as exc:
            logger.warning("Cannot read recorder state %s: %s",
                           self.state_path, exc)

    def _save_state(self) -> None:
        path = Path(self.state_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"last_rec_id": self.last_rec_id}))
        except Exception as exc:
            logger.warning("Cannot write recorder state %s: %s",
                           self.state_path, exc)

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    async def worker(self) -> None:
        while True:
            if not (self.settings.recordings_enabled
                    and self.tcx.configured()):
                await asyncio.sleep(self.settings.recording_poll_interval)
                continue
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Recording poll failed: %s", exc)
                await asyncio.sleep(POLL_FAIL_DELAY)
                continue
            await asyncio.sleep(self.settings.recording_poll_interval)

    async def poll_once(self) -> int:
        """List and upload new recordings; return how many were sent."""
        rows = await self.tcx.list_recordings_after(self.last_rec_id)
        sent = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            rec_id = row.get("Id")
            if not isinstance(rec_id, int):
                continue
            try:
                await self._upload(rec_id, row)
                sent += 1
            except Exception as exc:
                self.failed_count += 1
                logger.warning("Recording %s upload failed: %s",
                               rec_id, exc)
                # Do not advance past a failed row: it is retried on the
                # next poll (Odoo deduplicates by recording id).
                break
            self.last_rec_id = max(self.last_rec_id, rec_id)
            self._save_state()
        return sent

    async def _upload(self, rec_id: int, row: dict) -> None:
        audio = await self.tcx.download_recording(rec_id)
        max_bytes = self.settings.recording_max_mb * 1024 * 1024
        if not audio:
            raise ValueError("empty download")
        if len(audio) > max_bytes:
            raise ValueError("file exceeds {} MB".format(
                self.settings.recording_max_mb))
        meta = {}
        for source_key, target_key in META_FIELDS.items():
            value = row.get(source_key)
            if value not in (None, "", False):
                meta[target_key] = str(value)
        filename = "{}.wav".format(rec_id)
        path = "/3cx/webhook/recording/{}".format(quote(filename))
        if meta:
            path += "?" + urlencode(meta)
        await self.odoo.put_file(path, audio)
        self.uploaded_count += 1
        logger.info("Recording %s uploaded (%d bytes)", rec_id, len(audio))

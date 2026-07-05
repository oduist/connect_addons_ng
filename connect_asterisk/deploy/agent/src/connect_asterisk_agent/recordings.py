"""Recording upload pipeline.

MixMonitor writes files on the Asterisk host; the agent runs next to it
with the monitor directory mounted. After a channel with a known
``MIXMONITOR_FILENAME`` hangs up, the uploader waits for the file to
stabilize (MixMonitor finalizes asynchronously), then PUTs it to
``/asterisk/webhook/recording/<uniqueid>.<ext>``. Pending uploads are
persisted to the state file so a restart doesn't lose them.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path

from .odoo_client import OdooClient

logger = logging.getLogger(__name__)

RETRY_DELAY_START = 5.0
RETRY_DELAY_MAX = 600.0
STABLE_POLL_DELAY = 2.0
STABLE_POLL_TRIES = 10


class RecordingUploader:
    def __init__(
        self,
        odoo: OdooClient,
        state_path: str,
        upload_delay: float = 5.0,
        max_mb: int = 200,
        retry_hours: int = 24,
        delete_after_upload: bool = False,
    ):
        self.odoo = odoo
        self.state_path = state_path
        self.upload_delay = upload_delay
        self.max_bytes = max_mb * 1024 * 1024
        self.retry_seconds = retry_hours * 3600
        self.delete_after_upload = delete_after_upload
        self._queue: asyncio.Queue[tuple[str, str, float]] = asyncio.Queue()
        self._pending: dict[str, str] = {}  # uniqueid -> path
        self.uploaded_count = 0
        self.failed_count = 0
        self._load_pending()

    # ------------------------------------------------------------------
    # Persistence of pending uploads
    # ------------------------------------------------------------------

    def _load_pending(self) -> None:
        path = Path(self.state_path)
        if not path.is_file():
            return
        try:
            state = json.loads(path.read_text())
            for uniqueid, file_path in state.get(
                    "pending_recordings", {}).items():
                self.schedule(uniqueid, file_path, persist=False)
            if self._pending:
                logger.info("Restored %d pending recording upload(s)",
                            len(self._pending))
        except Exception as exc:
            logger.warning("Cannot read state file %s: %s",
                           self.state_path, exc)

    def _save_pending(self) -> None:
        path = Path(self.state_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            state = {}
            if path.is_file():
                try:
                    state = json.loads(path.read_text())
                except Exception:
                    state = {}
            state["pending_recordings"] = dict(self._pending)
            path.write_text(json.dumps(state, indent=2, sort_keys=True))
        except Exception as exc:
            logger.warning("Cannot write state file %s: %s",
                           self.state_path, exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def schedule(self, uniqueid: str, file_path: str,
                 persist: bool = True) -> None:
        if uniqueid in self._pending:
            return
        self._pending[uniqueid] = file_path
        self._queue.put_nowait((uniqueid, file_path, time.time()))
        if persist:
            self._save_pending()

    def pending_count(self) -> int:
        return len(self._pending)

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    async def _wait_stable(self, path: str) -> bool:
        """Wait until the file stops growing (MixMonitor finished)."""
        last_size = -1
        for _ in range(STABLE_POLL_TRIES):
            try:
                size = os.path.getsize(path)
            except OSError:
                return False
            if size == last_size and size > 0:
                return True
            last_size = size
            await asyncio.sleep(STABLE_POLL_DELAY)
        return last_size > 0

    async def _upload(self, uniqueid: str, path: str) -> bool:
        if not os.path.isfile(path):
            logger.warning("Recording %s not found at %s", uniqueid, path)
            return False
        if not await self._wait_stable(path):
            logger.warning("Recording %s never stabilized at %s",
                           uniqueid, path)
            return False
        size = os.path.getsize(path)
        if size > self.max_bytes:
            logger.warning("Recording %s is %d bytes (limit %d); skipped",
                           uniqueid, size, self.max_bytes)
            return False
        ext = os.path.splitext(path)[1].lstrip(".") or "wav"
        with open(path, "rb") as fh:
            data = fh.read()
        await self.odoo.put_file(
            "/asterisk/webhook/recording/{}.{}".format(uniqueid, ext), data)
        logger.info("Uploaded recording %s (%d bytes)", uniqueid, size)
        if self.delete_after_upload:
            try:
                os.unlink(path)
            except OSError as exc:
                logger.warning("Cannot delete %s: %s", path, exc)
        return True

    async def worker(self) -> None:
        while True:
            uniqueid, path, queued_at = await self._queue.get()
            await asyncio.sleep(self.upload_delay)
            delay = RETRY_DELAY_START
            while True:
                try:
                    ok = await self._upload(uniqueid, path)
                    if ok:
                        self.uploaded_count += 1
                    else:
                        self.failed_count += 1
                    break
                except Exception as exc:
                    if time.time() - queued_at > self.retry_seconds:
                        logger.error(
                            "Giving up on recording %s after %ds: %s",
                            uniqueid, self.retry_seconds, exc)
                        self.failed_count += 1
                        break
                    logger.warning(
                        "Recording %s upload failed (%s); retry in %.0fs",
                        uniqueid, exc, delay)
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, RETRY_DELAY_MAX)
            self._pending.pop(uniqueid, None)
            self._save_pending()

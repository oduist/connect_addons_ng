"""Egress recording uploader.

Watches the shared egress-out volume; when a file stops growing it PUTs
it to /livekit/webhook/recording/<filename> (Bearer auth) and records
the delivery in a state file so a restart does not re-upload. Adapted
from the Asterisk agent's RecordingUploader.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from .config import AgentSettings
from .odoo_client import OdooClient

logger = logging.getLogger(__name__)

STABLE_POLL_TRIES = 10
STABLE_POLL_DELAY = 2.0
AUDIO_EXTENSIONS = (".ogg", ".mp4", ".webm", ".mp3", ".wav", ".m4a")


class Uploader:
    def __init__(self, settings: AgentSettings, odoo: OdooClient):
        self.settings = settings
        self.odoo = odoo
        self.out_dir = Path(settings.egress_out_dir)
        self.state_path = Path(settings.state_dir) / "uploaded.json"
        self.uploaded = self._load_state()

    def _load_state(self) -> set[str]:
        if not self.state_path.is_file():
            return set()
        try:
            return set(json.loads(self.state_path.read_text()))
        except Exception as exc:
            logger.warning("Cannot read state %s: %s", self.state_path, exc)
            return set()

    def _save_state(self) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(sorted(self.uploaded)))
        except Exception as exc:
            logger.warning("Cannot write state %s: %s", self.state_path, exc)

    def _is_stable(self, path: Path) -> bool:
        last = -1
        for _ in range(STABLE_POLL_TRIES):
            try:
                size = path.stat().st_size
            except OSError:
                return False
            if size == last and size > 0:
                return True
            last = size
            time.sleep(STABLE_POLL_DELAY)
        return last > 0

    def scan_once(self) -> None:
        if not self.out_dir.is_dir():
            return
        for path in sorted(self.out_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            if path.name in self.uploaded:
                continue
            if not self._is_stable(path):
                continue
            try:
                data = path.read_bytes()
            except OSError as exc:
                logger.warning("Cannot read %s: %s", path, exc)
                continue
            if self.odoo.upload_recording_sync(path.name, data):
                logger.info("Uploaded %s (%d bytes)", path.name, len(data))
                self.uploaded.add(path.name)
                self._save_state()

    def run(self) -> None:
        logger.info("Uploader watching %s", self.out_dir)
        while True:
            try:
                self.scan_once()
            except Exception as exc:
                logger.exception("Uploader scan error: %s", exc)
            time.sleep(self.settings.poll_interval)


def run(settings: AgentSettings | None = None):
    settings = settings or AgentSettings()
    logging.basicConfig(level=settings.log_level.upper())
    odoo = OdooClient(settings.odoo_url, settings.agent_token)
    Uploader(settings, odoo).run()

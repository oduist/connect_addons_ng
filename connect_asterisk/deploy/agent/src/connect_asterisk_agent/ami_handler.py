"""AMI event pipeline: filter → trim → stamp → enqueue.

No business logic here — direction, status mapping and user matching
live in Odoo. The handler keeps only the mechanical filters (allowlist,
guard conditions), trims events to the forwarded field set, stamps
``EventTime`` with the agent clock (Asterisk events carry no usable
timestamp by default) and feeds the recording uploader.
"""
from __future__ import annotations

import logging
import time

from .call_state import CallState
from .constants import DEFAULT_EVENTS, FORWARDED_FIELDS, event_passes
from .odoo_client import OdooClient
from .recordings import RecordingUploader

logger = logging.getLogger(__name__)


class AMIHandler:
    def __init__(
        self,
        odoo: OdooClient,
        call_state: CallState,
        recordings: RecordingUploader | None,
        events: tuple[str, ...] = DEFAULT_EVENTS,
        trace: bool = False,
    ):
        self.odoo = odoo
        self.call_state = call_state
        self.recordings = recordings
        self.allowed = set(events)
        self.trace = trace
        self.forwarded_count = 0
        self.dropped_count = 0

    def set_events(self, events: list[str]) -> None:
        if events:
            self.allowed = set(events)

    def handle(self, event: dict) -> None:
        name = event.get("Event", "")
        if self.trace:
            logger.debug("AMI recv: %s", event)
        if name not in self.allowed or not event_passes(event):
            self.dropped_count += 1
            return
        self.call_state.on_event(event)
        trimmed = {key: event[key] for key in FORWARDED_FIELDS
                   if key in event}
        trimmed["EventTime"] = time.time()
        self.odoo.enqueue_event(trimmed)
        self.forwarded_count += 1
        if name == "Hangup" and self.recordings is not None:
            uniqueid = event.get("Uniqueid", "")
            path = self.call_state.pop_recording(uniqueid)
            if path:
                self.recordings.schedule(uniqueid, path)

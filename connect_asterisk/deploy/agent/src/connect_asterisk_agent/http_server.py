"""FastAPI app — the Odoo → agent direction.

Endpoints:
  POST /originate        — click-to-call AMI Originate
  POST /ami_action       — generic AMI action passthrough
  POST /recording_fetch  — re-upload a recording file
  POST /sync             — nudge the reconciler (config/channels)
  GET  /api/status       — version, AMI/Odoo health, counters
  GET  /healthz          — liveness (unauthenticated, always 200)
  GET  /asterisk/healthz — readiness (503 unless AMI is connected)

Everything except the health probes requires ``Authorization: Bearer
<agent_token>``. No allowlist on /ami_action — the Bearer token is the
trust boundary (ADR-015 rationale); real privilege limits belong in the
AMI user's write classes in manager.conf.
"""
from __future__ import annotations

import logging
import secrets
import time

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from . import __version__
from .ami import AMIClient
from .ami_handler import AMIHandler
from .call_state import CallState
from .config import AgentSettings
from .odoo_client import OdooClient
from .recordings import RecordingUploader
from .reconciler import Reconciler

logger = logging.getLogger(__name__)


def _check_bearer(request: Request, token: str) -> bool:
    if not token:
        return False
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return False
    return secrets.compare_digest(auth[7:].strip(), token)


def build_app(
    settings: AgentSettings,
    ami: AMIClient,
    odoo: OdooClient,
    handler: AMIHandler,
    call_state: CallState,
    recordings: RecordingUploader | None,
    reconciler: Reconciler,
    started_at: float,
) -> FastAPI:
    app = FastAPI(title="connect-asterisk-agent")

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        if request.url.path in ("/healthz", "/asterisk/healthz"):
            return await call_next(request)
        if _check_bearer(request, settings.agent_token):
            return await call_next(request)
        return JSONResponse(
            {"error": "unauthorized"},
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/asterisk/healthz")
    async def readiness():
        if not ami.is_connected:
            return JSONResponse(
                {"status": "degraded", "ami_connected": False},
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return {"status": "ok", "ami_connected": True}

    @app.get("/api/status")
    async def api_status():
        return {
            "version": __version__,
            "ami_connected": ami.is_connected,
            "asterisk_banner": ami.asterisk_banner,
            "odoo_ok": odoo.last_call_ok,
            "uptime_seconds": int(time.time() - started_at),
            "outbox_depth": odoo.outbox_depth(),
            "events_forwarded": handler.forwarded_count,
            "events_dropped": handler.dropped_count,
            "recordings_pending": recordings.pending_count()
                                  if recordings else 0,
            "recordings_uploaded": recordings.uploaded_count
                                   if recordings else 0,
        }

    @app.post("/sync")
    async def sync_endpoint(request: Request):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        scope = (payload or {}).get("scope", "all")
        reconciler.trigger(scope=scope)
        return {"status": "queued", "scope": scope}

    @app.post("/ami_action")
    async def ami_action(request: Request):
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"error": "bad_json"}, status_code=400)
        action = (payload or {}).get("action")
        if not isinstance(action, dict) or not action.get("Action"):
            return JSONResponse({"error": "bad_action"}, status_code=400)
        collect = bool(payload.get("collect_events"))
        timeout = float(payload.get("timeout") or 10)
        try:
            response = await ami.action(
                action, timeout=timeout, collect_events=collect)
        except Exception as exc:
            logger.warning("AMI action %s failed: %s",
                           action.get("Action"), exc)
            return JSONResponse({"error": str(exc)}, status_code=502)
        return {"response": response}

    @app.post("/originate")
    async def originate(request: Request):
        # Originate is just an AMI action, but kept as a dedicated
        # endpoint so the API reads explicitly and can grow originate-
        # specific logic (e.g. pending-ChannelId bookkeeping) without
        # touching the generic passthrough.
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"error": "bad_json"}, status_code=400)
        action = (payload or {}).get("action")
        if not isinstance(action, dict) or \
                action.get("Action") != "Originate":
            return JSONResponse({"error": "bad_action"}, status_code=400)
        try:
            response = await ami.action(action, timeout=15)
        except Exception as exc:
            logger.warning("Originate failed: %s", exc)
            return JSONResponse({"error": str(exc)}, status_code=502)
        return {"response": response}

    @app.post("/recording_fetch")
    async def recording_fetch(request: Request):
        if recordings is None:
            return JSONResponse(
                {"error": "recordings_disabled"}, status_code=400)
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"error": "bad_json"}, status_code=400)
        uniqueid = (payload or {}).get("sid") or ""
        path = (payload or {}).get("path") or ""
        if not path:
            info = call_state.get(uniqueid)
            path = info.recording_path if info else ""
        if not uniqueid or not path:
            return JSONResponse({"error": "unknown_recording"},
                                status_code=404)
        recordings.schedule(uniqueid, path)
        return {"status": "queued", "sid": uniqueid, "path": path}

    return app

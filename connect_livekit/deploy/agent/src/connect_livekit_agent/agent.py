"""LiveKit Agents worker entrypoint.

Registered under the agent name ``connect-livekit-agent`` (explicit
dispatch only, ADR-036). On dispatch it reads ``agent_id`` from the job
metadata, pulls the agent configuration from Odoo, builds an
AgentSession with the per-agent plugin cascade, runs the conversation
under a time limit and posts the transcript back to Odoo on close.
"""
from __future__ import annotations

import asyncio
import json
import logging

from livekit import agents
from livekit.agents import Agent, JobContext, WorkerOptions

from .config import AgentSettings
from .odoo_client import OdooClient
from .session_factory import build_session
from .tools import build_tools
from . import transcript as transcript_mod

logger = logging.getLogger(__name__)

AGENT_NAME = "connect-livekit-agent"


def _job_metadata(ctx: JobContext) -> dict:
    """Read dispatch metadata (job first, then the room)."""
    raw = ""
    if ctx.job and ctx.job.metadata:
        raw = ctx.job.metadata
    elif ctx.room and ctx.room.metadata:
        raw = ctx.room.metadata
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except ValueError:
        logger.warning("Invalid dispatch metadata: %r", raw)
        return {}


def _find_sip_channel_sid(ctx: JobContext) -> str:
    """The SIP participant's call id is the connect.channel sid."""
    for participant in ctx.room.remote_participants.values():
        attrs = participant.attributes or {}
        if attrs.get("sip.callID"):
            return attrs["sip.callID"]
    return ""


async def entrypoint(ctx: JobContext, settings: AgentSettings | None = None):
    settings = settings or AgentSettings()
    odoo = OdooClient(settings.odoo_url, settings.agent_token)

    await ctx.connect()
    metadata = _job_metadata(ctx)
    agent_id = metadata.get("agent_id")
    if not agent_id:
        logger.error("Dispatch without agent_id; leaving room.")
        return

    config = await odoo.get_agent_config(int(agent_id))
    tool_token = config.get("tool_token") or ""

    # The SIP participant may connect slightly after the agent; resolve
    # the channel sid lazily so tools always see the current value.
    channel_sid_holder = {"sid": _find_sip_channel_sid(ctx)}

    def get_channel_sid() -> str:
        if not channel_sid_holder["sid"]:
            channel_sid_holder["sid"] = _find_sip_channel_sid(ctx)
        return channel_sid_holder["sid"]

    tools = build_tools(
        odoo, int(agent_id), tool_token,
        config.get("tools") or [], get_channel_sid)

    instructions = config.get("instructions") or ""
    dynamic = metadata.get("dynamic_variables") or {}
    if dynamic:
        instructions += "\n\nKnown caller details: " + json.dumps(dynamic)

    session = build_session(config, settings)
    agent = Agent(instructions=instructions, tools=tools)

    time_limit = int(config.get("time_limit_secs") or 1800)
    delivered = {"done": False}

    async def deliver_transcript():
        if delivered["done"]:
            return
        delivered["done"] = True
        try:
            history = getattr(session, "history", None)
            payload = transcript_mod.build_payload(
                room_name=ctx.room.name,
                channel_sid=get_channel_sid(),
                history=history,
                duration_secs=0,
            )
            await odoo.post_transcript(int(agent_id), tool_token, payload)
        except Exception as exc:
            logger.exception("Transcript delivery failed: %s", exc)

    ctx.add_shutdown_callback(deliver_transcript)

    await session.start(agent=agent, room=ctx.room)
    greeting = config.get("greeting")
    if greeting:
        await session.say(greeting)

    # Enforce the call time limit, then say goodbye and end the room.
    try:
        await asyncio.sleep(time_limit)
        await session.say("Thank you for calling. Goodbye!")
    except asyncio.CancelledError:
        pass
    finally:
        await deliver_transcript()
        await ctx.room.disconnect()


def run(settings: AgentSettings | None = None):
    settings = settings or AgentSettings()
    logging.basicConfig(level=settings.log_level.upper())

    async def _entry(ctx: JobContext):
        await entrypoint(ctx, settings)

    agents.cli.run_app(WorkerOptions(
        entrypoint_fnc=_entry,
        agent_name=AGENT_NAME,
        ws_url=settings.livekit_url,
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
    ))

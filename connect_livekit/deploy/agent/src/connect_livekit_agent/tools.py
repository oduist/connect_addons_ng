"""Function tools exposed to the LLM, backed by Odoo webhooks.

Each tool forwards its arguments to
/livekit/webhook/agent/<id>/tool/<name> (authed by the per-agent tool
token) and returns the JSON result to the model. The set of tools is
decided by Odoo (agent config ``tools`` list) so disabled capabilities
never reach the model.
"""
from __future__ import annotations

import logging
from typing import Any

from livekit.agents import function_tool, RunContext

logger = logging.getLogger(__name__)


def build_tools(odoo, agent_id: int, tool_token: str, enabled: list[str],
                get_channel_sid) -> list:
    """Return the livekit-agents function tools enabled for this agent.

    get_channel_sid is a callable returning the current SIP call id so
    Odoo can resolve the partner from the live channel.
    """
    tools: list = []

    async def _call(tool_name: str, payload: dict[str, Any]) -> dict:
        payload = dict(payload)
        channel_sid = get_channel_sid()
        if channel_sid:
            payload["channel_sid"] = channel_sid
        return await odoo.call_tool(agent_id, tool_token, tool_name, payload)

    if "lookup_contact" in enabled:
        @function_tool
        async def lookup_contact(
            context: RunContext, phone: str = "",
        ) -> dict:
            """Look up the caller in Odoo by phone number.

            Args:
                phone: E.164 phone number; empty to use the live caller.
            """
            return await _call("lookup_contact", {"phone": phone})
        tools.append(lookup_contact)

    if "add_contact_note" in enabled:
        @function_tool
        async def add_contact_note(
            context: RunContext, note: str, phone: str = "",
        ) -> dict:
            """Log a note on the caller's Odoo contact.

            Args:
                note: The note to record.
                phone: Optional E.164 number identifying the contact.
            """
            return await _call(
                "add_contact_note", {"note": note, "phone": phone})
        tools.append(add_contact_note)

    if "upsert_crm_lead" in enabled:
        @function_tool
        async def upsert_crm_lead(
            context: RunContext, title: str, note: str = "", phone: str = "",
        ) -> dict:
            """Create or update a CRM lead for the caller.

            Args:
                title: Short lead title / subject.
                note: Optional details to append to the lead.
                phone: Optional E.164 number identifying the caller.
            """
            return await _call(
                "upsert_crm_lead",
                {"title": title, "note": note, "phone": phone})
        tools.append(upsert_crm_lead)

    if "upsert_helpdesk_ticket" in enabled:
        @function_tool
        async def upsert_helpdesk_ticket(
            context: RunContext, title: str, note: str = "", phone: str = "",
        ) -> dict:
            """Create or update a helpdesk ticket for the caller.

            Args:
                title: Short ticket title / subject.
                note: Optional details to append to the ticket.
                phone: Optional E.164 number identifying the caller.
            """
            return await _call(
                "upsert_helpdesk_ticket",
                {"title": title, "note": note, "phone": phone})
        tools.append(upsert_helpdesk_ticket)

    return tools

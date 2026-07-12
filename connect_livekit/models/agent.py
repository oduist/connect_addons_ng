# -*- coding: utf-8 -*-
import logging
import secrets
from urllib.parse import urljoin

from markupsafe import escape

from odoo import api, fields, models
from odoo.exceptions import ValidationError

logger = logging.getLogger(__name__)

DEFAULT_INSTRUCTIONS = (
    "You are a helpful phone assistant of our company. Answer briefly and "
    "politely. Use the available tools to look up the caller and record "
    "the outcome of the conversation. If you cannot help, say so honestly."
)


class LivekitAgent(models.Model):
    """A voice-AI agent served by the oduist/livekit-agent worker.

    Unlike Telnyx AI assistants there is no remote copy to sync: the
    worker pulls this configuration from Odoo at dispatch time
    (/livekit/api/agent_config), so edits apply to the next call
    immediately (ADR-037).
    """
    _name = 'connect.livekit.agent'
    _description = 'LiveKit AI Agent'
    _order = 'id'

    name = fields.Char(required=True)
    description = fields.Char()
    active = fields.Boolean(default=True)
    instructions = fields.Text(required=True, default=DEFAULT_INSTRUCTIONS)
    greeting = fields.Text(default="Hello! How can I help you today?")
    mode = fields.Selection([
        ('pipeline', 'STT → LLM → TTS'),
        ('realtime', 'OpenAI Realtime'),
    ], default='pipeline', required=True)
    # Plugin cascade (owner decision, ADR-037): per-agent provider choice.
    stt_provider = fields.Selection([
        ('deepgram', 'Deepgram'),
        ('openai', 'OpenAI Whisper'),
    ], default='openai', required=True, string='STT Provider')
    stt_model = fields.Char(
        default='whisper-1',
        help="deepgram: e.g. nova-3; openai: e.g. whisper-1 / "
             "gpt-4o-mini-transcribe.")
    llm_model = fields.Char(default='gpt-4o-mini', required=True)
    tts_provider = fields.Selection([
        ('openai', 'OpenAI'),
        ('elevenlabs', 'ElevenLabs'),
    ], default='openai', required=True, string='TTS Provider')
    tts_model = fields.Char(
        default='tts-1',
        help="openai: tts-1 / gpt-4o-mini-tts; elevenlabs: e.g. "
             "eleven_turbo_v2_5.")
    voice = fields.Char(
        default='alloy',
        help="OpenAI voice name or ElevenLabs voice ID.")
    language = fields.Char(
        help="BCP-47 hint for STT, e.g. en, de, ru. Empty = auto.")
    time_limit_secs = fields.Integer(default=1800)
    record_calls = fields.Boolean()
    enable_contact_tools = fields.Boolean(
        default=True,
        help="lookup_contact and add_contact_note tools.")
    enable_crm_tools = fields.Boolean(
        help="upsert_crm_lead (published only when CRM is installed).")
    enable_helpdesk_tools = fields.Boolean(
        help="upsert_helpdesk_ticket (published only when Helpdesk is "
             "installed).")
    tool_token = fields.Char(
        readonly=True, copy=False,
        groups="connect.group_admin,base.group_erp_manager")

    @api.constrains('time_limit_secs')
    def _check_time_limit(self):
        for rec in self:
            if rec.time_limit_secs and not (
                    30 <= rec.time_limit_secs <= 14400):
                raise ValidationError(
                    'The call time limit must be between 30 and 14400 '
                    'seconds.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('tool_token', secrets.token_urlsafe(32))
        return super().create(vals_list)

    def action_rotate_tool_token(self):
        for rec in self:
            rec.sudo().write({'tool_token': secrets.token_urlsafe(32)})
        self.env['connect.settings'].connect_notify(
            'Tool token rotated.', title='LiveKit AI Agent')

    def action_call_with_agent(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Call with Agent',
            'res_model': 'connect.livekit.ai_call_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_agent': self.id},
        }

    def _enabled_tools(self):
        self.ensure_one()
        tools = []
        if self.enable_contact_tools:
            tools += ['lookup_contact', 'add_contact_note']
        if self.enable_crm_tools and 'crm.lead' in self.env:
            tools.append('upsert_crm_lead')
        if self.enable_helpdesk_tools and 'helpdesk.ticket' in self.env:
            tools.append('upsert_helpdesk_ticket')
        return tools

    def _agent_config_payload(self):
        """Worker contract: everything the sidecar needs for one session.

        Called with sudo from the Bearer-authenticated bootstrap route;
        includes the per-agent tool token and the AI vendor keys from
        connect.settings (worker env vars are the fallback).
        """
        self.ensure_one()
        settings = self.env['connect.settings'].sudo()
        api_url = settings.get_param('api_url') or ''
        return {
            'id': self.id,
            'name': self.name,
            'instructions': self.instructions,
            'greeting': self.greeting or '',
            'mode': self.mode,
            'stt_provider': self.stt_provider,
            'stt_model': self.stt_model or '',
            'llm_model': self.llm_model,
            'tts_provider': self.tts_provider,
            'tts_model': self.tts_model or '',
            'voice': self.voice or '',
            'language': self.language or '',
            'time_limit_secs': self.time_limit_secs or 1800,
            'record_calls': self.record_calls,
            'tools': self._enabled_tools(),
            'tool_token': self.sudo().tool_token,
            'webhook_base': urljoin(
                api_url, '/livekit/webhook/agent/{}'.format(self.id)),
            'keys': {
                'openai': settings.get_param('openai_api_key') or '',
                'deepgram': settings.get_param('deepgram_api_key') or '',
                'elevenlabs': settings.get_param('elevenlabs_api_key') or '',
            },
        }

    @api.model
    def _partner_values(self, partner):
        if not partner:
            return {"found": False}
        return {
            "found": True,
            "partner_id": partner.id,
            "customer_name": partner.display_name,
            "company_name": partner.parent_id.display_name or (
                partner.display_name if partner.is_company else ""
            ),
            "email": partner.email or "",
            "language": partner.lang or "",
        }

    def _resolve_partner(self, payload, channel_sid=None):
        self.ensure_one()
        phone = payload.get("phone")
        if phone:
            return self.env["res.partner"].sudo().get_partner_by_number(phone)
        if channel_sid:
            channel = self.env["connect.channel"].sudo().search(
                [("sid", "=", channel_sid)], limit=1
            )
            if channel.call.partner:
                return channel.call.partner
        return self.env["res.partner"]

    def execute_tool(self, tool_name, payload, channel_sid=None):
        # Adaptation of the Telnyx AI assistant tool executor
        # (connect_telnyx/models/ai_assistant.py) — same allowlist and
        # capability guards, keyed by connect.channel sid.
        self.ensure_one()
        allowed = {
            "lookup_contact", "add_contact_note", "upsert_crm_lead",
            "upsert_helpdesk_ticket",
        }
        if tool_name not in allowed:
            raise ValidationError("Unknown AI agent tool.")
        if (tool_name in ("lookup_contact", "add_contact_note")
                and not self.enable_contact_tools):
            raise ValidationError("Contact tools are disabled.")
        partner = self._resolve_partner(payload, channel_sid)
        phone = payload.get("phone") or (
            partner.phone or partner.mobile if partner else ""
        )
        if tool_name == "lookup_contact":
            return self._partner_values(partner)
        note = (payload.get("note") or "").strip()
        if len(note) > 4000:
            raise ValidationError("Tool note is too long.")
        if tool_name == "add_contact_note":
            if not partner:
                return {"ok": False, "error": "contact_not_found"}
            partner.sudo().message_post(
                body=escape(note), subtype_xmlid="mail.mt_note"
            )
            return {"ok": True, "partner_id": partner.id}
        title = (payload.get("title") or "").strip()[:255]
        if not title:
            raise ValidationError("A title is required.")
        if tool_name == "upsert_crm_lead":
            if not self.enable_crm_tools or "crm.lead" not in self.env:
                return {"ok": False, "error": "crm_not_available"}
            Lead = self.env["crm.lead"].sudo()
            lead = Lead.get_lead_by_number(phone) if phone else Lead
            if not lead:
                lead = Lead.create({
                    "name": title,
                    "phone": phone,
                    "partner_id": partner.id if partner else False,
                })
            if note:
                lead.message_post(
                    body=escape(note), subtype_xmlid="mail.mt_note")
            return {"ok": True, "lead_id": lead.id}
        if not self.enable_helpdesk_tools or "helpdesk.ticket" not in self.env:
            return {"ok": False, "error": "helpdesk_not_available"}
        Ticket = self.env["helpdesk.ticket"].sudo()
        ticket = Ticket.get_ticket_by_number(phone) if phone else Ticket
        if not ticket:
            ticket = Ticket.create({
                "name": title,
                "partner_id": partner.id if partner else False,
                "partner_phone": phone,
            })
        if note:
            ticket.message_post(body=escape(note), subtype_xmlid="mail.mt_note")
        return {"ok": True, "ticket_id": ticket.id}

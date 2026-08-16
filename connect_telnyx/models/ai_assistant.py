# -*- coding: utf-8 -*-
import logging
import secrets
from urllib.parse import urljoin

from markupsafe import escape

from odoo import api, fields, models, release
from odoo.exceptions import ValidationError
if release.version_info[0] >= 19:
    from odoo.models import Constraint

logger = logging.getLogger(__name__)

# Telnyx validates the voice id against the account; this one ships with
# every account and is used when the configured voice is unavailable.
DEFAULT_VOICE = "AWS.Polly.Joanna-Neural"

REMOTE_FIELDS = {
    "name", "description", "instructions", "greeting", "model",
    "voice", "voice_speed", "transcription_model",
    "transcription_language", "time_limit_secs", "record_calls",
    "memory_enabled", "enable_contact_tools", "enable_crm_tools",
    "enable_helpdesk_tools", "active",
}


class TelnyxAIAssistant(models.Model):
    _name = "connect.telnyx.ai_assistant"
    _description = "Telnyx AI Assistant"
    _order = "name"

    sid = fields.Char(string="Telnyx ID", readonly=True, copy=False, index=True)
    version_id = fields.Char(readonly=True, copy=False)
    name = fields.Char(required=True)
    description = fields.Text()
    instructions = fields.Text(
        required=True,
        default=(
            "You are a helpful voice assistant. Be concise, transparent, "
            "and use the available Odoo tools only when they are needed."
        ),
    )
    greeting = fields.Text(default="Hello! How can I help you today?")
    model = fields.Char(help="Leave empty to use the Telnyx default model.")
    voice = fields.Char(
        default=DEFAULT_VOICE,
        help="Telnyx voice identifier, for example AWS.Polly.Joanna-Neural. "
             "The available ids are listed by the Telnyx text-to-speech "
             "voices endpoint.")
    voice_speed = fields.Float(default=1.0)
    transcription_model = fields.Char(
        help="For example deepgram/nova-3. Leave empty for Telnyx default."
    )
    transcription_language = fields.Char()
    time_limit_secs = fields.Integer(default=1800, required=True)
    record_calls = fields.Boolean(default=False)
    memory_enabled = fields.Boolean(default=False)
    enable_contact_tools = fields.Boolean(default=True)
    enable_crm_tools = fields.Boolean(default=False)
    enable_helpdesk_tools = fields.Boolean(default=False)
    active = fields.Boolean(default=True)
    imported = fields.Boolean(readonly=True, copy=False)
    last_sync_at = fields.Datetime(readonly=True, copy=False)
    tool_token = fields.Char(
        readonly=True, copy=False,
        groups="connect.group_admin,base.group_erp_manager",
    )

    if release.version_info[0] >= 19:
        _sid_unique = Constraint(
            "UNIQUE(sid)", "A Telnyx AI Assistant ID must be unique."
        )
    else:
        _sql_constraints = [
            (
                "sid_unique",
                "UNIQUE(sid)",
                "A Telnyx AI Assistant ID must be unique.",
            )
        ]

    @api.constrains("time_limit_secs")
    def _check_time_limit(self):
        for rec in self:
            if rec.time_limit_secs < 30 or rec.time_limit_secs > 14400:
                raise ValidationError(
                    "The AI assistant call limit must be between 30 and "
                    "14,400 seconds."
                )

    @api.model
    def _unwrap(self, response):
        if isinstance(response, dict) and "data" in response:
            return response["data"]
        return response

    def _variables_url(self):
        self.ensure_one()
        api_url = self.env["connect.settings"].sudo().get_param("api_url")
        return urljoin(
            api_url, "telnyx/webhook/assistant/{}/variables".format(self.id)
        )

    def _tool_url(self, tool_name):
        self.ensure_one()
        api_url = self.env["connect.settings"].sudo().get_param("api_url")
        return urljoin(
            api_url,
            "telnyx/webhook/assistant/{}/tool/{}".format(self.id, tool_name),
        )

    def _webhook_tool(self, name, description, properties, required=None):
        self.ensure_one()
        return {
            "type": "webhook",
            "webhook": {
                "name": name,
                "description": description,
                "url": self._tool_url(name),
                "method": "POST",
                "headers": [
                    {
                        "name": "X-Odoo-Telnyx-Token",
                        "value": self.sudo().tool_token,
                    }
                ],
                "body_parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required or [],
                    "additionalProperties": False,
                },
                "timeout_ms": 5000,
            },
        }

    def _tool_payload(self):
        self.ensure_one()
        # An assistant imported from Telnyx already carries its own
        # hangup tool; sending ours would add a second one and Telnyx
        # rejects the update ("Only one tool of type 'hangup'").
        tools = [] if (self.imported and self.sid) else [
            {"type": "hangup", "hangup": {}}]
        if self.enable_contact_tools:
            tools.extend([
                self._webhook_tool(
                    "lookup_contact",
                    "Find the Odoo contact for the caller or a supplied phone.",
                    {
                        "phone": {
                            "type": "string",
                            "description": "Phone number; omit for current caller.",
                        }
                    },
                ),
                self._webhook_tool(
                    "add_contact_note",
                    "Add an internal note to the current Odoo contact.",
                    {
                        "phone": {"type": "string"},
                        "note": {
                            "type": "string",
                            "description": "Short factual note from the call.",
                        },
                    },
                    ["note"],
                ),
            ])
        if self.enable_crm_tools and "crm.lead" in self.env:
            tools.append(self._webhook_tool(
                "upsert_crm_lead",
                "Create or update the open CRM lead for this caller.",
                {
                    "phone": {"type": "string"},
                    "title": {"type": "string"},
                    "note": {"type": "string"},
                },
                ["title", "note"],
            ))
        if self.enable_helpdesk_tools and "helpdesk.ticket" in self.env:
            tools.append(self._webhook_tool(
                "upsert_helpdesk_ticket",
                "Create or update the open Helpdesk ticket for this caller.",
                {
                    "phone": {"type": "string"},
                    "title": {"type": "string"},
                    "note": {"type": "string"},
                },
                ["title", "note"],
            ))
        return tools

    def _remote_payload(self):
        self.ensure_one()
        payload = {
            "name": self.name,
            "description": self.description or "",
            "instructions": self.instructions,
            "greeting": self.greeting or "",
            "enabled_features": ["telephony"],
            "dynamic_variables_webhook_url": self._variables_url(),
            "dynamic_variables_webhook_timeout_ms": 1500,
            "tools": self._tool_payload(),
            "telephony_settings": {
                "time_limit_secs": self.time_limit_secs,
                "recording_settings": {
                    "enabled": self.record_calls,
                    "channels": "dual",
                    "format": "mp3",
                    "stop_on_conversation_end": True,
                },
            },
            "privacy_settings": {"data_retention": True},
        }
        if self.model:
            payload["model"] = self.model
        if self.voice:
            payload["voice_settings"] = {
                "voice": self.voice,
                "voice_speed": self.voice_speed,
            }
        transcription = {}
        if self.transcription_model:
            transcription["model"] = self.transcription_model
        if self.transcription_language:
            transcription["language"] = self.transcription_language
        if transcription:
            payload["transcription"] = transcription
        group_id = self.env["connect.settings"].sudo().get_param(
            "telnyx_ai_summary_group_id"
        )
        if group_id:
            payload["insight_settings"] = {"insight_group_id": group_id}
        return payload

    @api.model
    def _remote_values(self, data, imported=False):
        voice_settings = data.get("voice_settings") or {}
        transcription = data.get("transcription") or {}
        telephony = data.get("telephony_settings") or {}
        recording = telephony.get("recording_settings") or {}
        vals = {
            "sid": data.get("id"),
            "version_id": data.get("version_id"),
            "name": data.get("name") or "Telnyx AI Assistant",
            "description": data.get("description") or "",
            "instructions": data.get("instructions") or "Be helpful.",
            "greeting": data.get("greeting") or "",
            "model": data.get("model") or "",
            "voice": voice_settings.get("voice") or "",
            "voice_speed": (
                voice_settings.get("voice_speed")
                or voice_settings.get("speed") or 1.0
            ),
            "transcription_model": transcription.get("model") or "",
            "transcription_language": transcription.get("language") or "",
            "time_limit_secs": telephony.get("time_limit_secs") or 1800,
            "record_calls": bool(recording.get("enabled")),
            "imported": imported,
            "last_sync_at": fields.Datetime.now(),
        }
        return vals

    def _apply_remote_data(self, data):
        self.ensure_one()
        self.with_context(skip_telnyx_ai_sync=True).write(
            self._remote_values(data, imported=self.imported)
        )

    def _push_remote(self, path):
        """POST the assistant payload, recovering from an unusable voice.

        The account-level default voice can point at a deleted custom
        voice, and an imported assistant carries whatever voice id Telnyx
        reported, which Telnyx itself may then reject. Retry once with a
        known-good voice instead of failing the whole synchronization.
        """
        self.ensure_one()
        settings = self.env["connect.settings"]
        payload = self._remote_payload()
        try:
            return self._unwrap(
                settings.telnyx_api_request("POST", path, payload=payload))
        except ValidationError as e:
            message = str(e)
            if "Voice" not in message or "not found" not in message:
                raise
            if payload.get("voice_settings", {}).get("voice") == DEFAULT_VOICE:
                raise
            logger.warning(
                "Telnyx rejected voice %s for assistant '%s', falling back "
                "to %s.", self.voice or "(account default)", self.name,
                DEFAULT_VOICE)
            payload["voice_settings"] = {
                "voice": DEFAULT_VOICE,
                "voice_speed": self.voice_speed or 1.0,
            }
            data = self._unwrap(
                settings.telnyx_api_request("POST", path, payload=payload))
            settings.connect_notify(
                "Voice of the AI assistant '{}' was not available in Telnyx "
                "and was replaced with {}.".format(self.name, DEFAULT_VOICE),
                title="AI Assistant Voice", warning=True, sticky=True)
            return data

    def _create_remote(self):
        self.ensure_one()
        self._ensure_summary_group()
        self._apply_remote_data(self._push_remote("ai/assistants"))

    def _update_remote(self):
        self.ensure_one()
        if not self.sid:
            return self._create_remote()
        self._apply_remote_data(
            self._push_remote("ai/assistants/{}".format(self.sid)))

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [dict(vals) for vals in vals_list]
        for vals in vals_list:
            vals.setdefault("tool_token", secrets.token_urlsafe(32))
        records = super().create(vals_list)
        if (self.env.context.get("install_mode")
                or self.env.context.get("skip_telnyx_ai_sync")
                or not self.env["connect.settings"].sudo().get_param(
                    "telnyx_auto_sync"
                )):
            return records
        for rec in records:
            rec._create_remote()
        return records

    def write(self, vals):
        res = super().write(vals)
        if (self.env.context.get("skip_telnyx_ai_sync")
                or not REMOTE_FIELDS.intersection(vals)
                or not self.env["connect.settings"].sudo().get_param(
                    "telnyx_auto_sync"
                )):
            return res
        for rec in self:
            rec._update_remote()
        return res

    def unlink(self):
        if (not self.env.context.get("skip_telnyx_ai_sync")
                and self.env["connect.settings"].sudo().get_param(
                    "telnyx_auto_sync"
                )):
            for rec in self.filtered("sid"):
                self.env["connect.settings"].telnyx_api_request(
                    "DELETE", "ai/assistants/{}".format(rec.sid)
                )
        return super().unlink()

    @api.model
    def _ensure_summary_group(self):
        settings = self.env["connect.settings"].sudo()
        insight_id = settings.get_param("telnyx_ai_summary_insight_id")
        group_id = settings.get_param("telnyx_ai_summary_group_id")
        if insight_id and group_id:
            return group_id
        api_url = settings.get_param("api_url")
        webhook = urljoin(api_url, "telnyx/webhook/assistant/insights")
        if not insight_id:
            insight = self._unwrap(settings.telnyx_api_request(
                "POST", "ai/conversations/insights", payload={
                    "name": "Odoo Connect Summary",
                    "instructions": (
                        "Summarize this conversation in 2-3 factual sentences. "
                        "Include the request, outcome, and follow-up actions."
                    ),
                }
            ))
            insight_id = insight.get("id")
            settings.set_param("telnyx_ai_summary_insight_id", insight_id)
        if not group_id:
            group = self._unwrap(settings.telnyx_api_request(
                "POST", "ai/conversations/insight-groups", payload={
                    "name": "Odoo Connect Summary",
                    "description": "Conversation summaries synchronized to Odoo.",
                    "webhook": webhook,
                }
            ))
            group_id = group.get("id")
            settings.set_param("telnyx_ai_summary_group_id", group_id)
        settings.telnyx_api_request(
            "POST",
            "ai/conversations/insight-groups/{}/insights/{}/assign".format(
                group_id, insight_id
            ),
        )
        return group_id

    @api.model
    def sync(self):
        self._ensure_summary_group()
        response = self.env["connect.settings"].telnyx_api_request(
            "GET", "ai/assistants"
        )
        data = self._unwrap(response) or []
        if isinstance(data, dict):
            data = data.get("assistants") or data.get("items") or []
        for item in data:
            sid = item.get("id")
            if not sid:
                continue
            rec = self.search([("sid", "=", sid)], limit=1)
            vals = self._remote_values(
                item, imported=rec.imported if rec else True)
            if rec:
                rec.with_context(skip_telnyx_ai_sync=True).write(vals)
            else:
                vals["tool_token"] = secrets.token_urlsafe(32)
                rec = self.with_context(skip_telnyx_ai_sync=True).create(vals)
                # Once imported, Odoo becomes the source of truth and adds
                # its signed variables webhook plus the allowlisted tools.
                # A single assistant with an invalid remote config (e.g. a
                # decommissioned model) must not abort the whole account sync.
                try:
                    rec._update_remote()
                except Exception as e:
                    logger.warning(
                        "AI assistant '%s' (model %s) push failed: %s",
                        rec.name, rec.model or "default", e)
                    self.env["connect.settings"].connect_notify(
                        "AI assistant '{}' could not be synchronized "
                        "(model '{}'): {}".format(
                            rec.name, rec.model or "default", e),
                        title="AI Assistant Sync Warning", warning=True,
                        sticky=True)
        return True

    def action_pull_from_telnyx(self):
        for rec in self:
            if not rec.sid:
                rec._create_remote()
                continue
            data = self._unwrap(
                self.env["connect.settings"].telnyx_api_request(
                    "GET", "ai/assistants/{}".format(rec.sid)
                )
            )
            rec._apply_remote_data(data)
        return True

    def action_push_to_telnyx(self):
        for rec in self:
            rec._update_remote()
        return True

    def action_rotate_tool_token(self):
        for rec in self:
            rec.sudo().with_context(skip_telnyx_ai_sync=True).tool_token = (
                secrets.token_urlsafe(32)
            )
            rec._update_remote()
        return True

    def action_call_with_assistant(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Call with Assistant",
            "res_model": "connect.telnyx.ai_call_wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_assistant": self.id},
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

    def _resolve_partner(self, payload, call_control_id=None):
        self.ensure_one()
        phone = payload.get("phone")
        if phone:
            return self.env["res.partner"].sudo().get_partner_by_number(phone)
        if call_control_id:
            channel = self.env["connect.channel"].sudo().search(
                [("sid", "=", call_control_id)], limit=1
            )
            if channel.call.partner:
                return channel.call.partner
        return self.env["res.partner"]

    def execute_tool(self, tool_name, payload, call_control_id=None):
        self.ensure_one()
        allowed = {
            "lookup_contact", "add_contact_note", "upsert_crm_lead",
            "upsert_helpdesk_ticket",
        }
        if tool_name not in allowed:
            raise ValidationError("Unknown AI assistant tool.")
        if (tool_name in ("lookup_contact", "add_contact_note")
                and not self.enable_contact_tools):
            raise ValidationError("Contact tools are disabled.")
        partner = self._resolve_partner(payload, call_control_id)
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
                lead.message_post(body=escape(note), subtype_xmlid="mail.mt_note")
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

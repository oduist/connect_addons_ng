# -*- coding: utf-8 -*-
import logging
import secrets
from urllib.parse import urljoin

from markupsafe import escape

from odoo import api, fields, models, release
from odoo.exceptions import ValidationError
from odoo.addons.connect.models.res_partner import format_number
if release.version_info[0] >= 19:
    from odoo.models import Constraint

from .settings import DEFAULT_AI_SUMMARY_INSTRUCTIONS
from .texml_response import Connect, VoiceResponse

logger = logging.getLogger(__name__)

# Telnyx validates the voice id against the account; this one ships with
# every account and is used when the configured voice is unavailable.
DEFAULT_VOICE = "AWS.Polly.Joanna-Neural"

# Telnyx documents [0.25, 2.0] for Natural voices only. Other voices reject
# a speed they do not support, and the failure is invisible until a call
# arrives: the assistant cannot synthesize its greeting and hangs up after
# one second with Reason=greeting_error. Telnyx Ultra answers 400 (code
# 90103) on the text-to-speech endpoint at 0.5 and at 1.8 or more, so the
# guarded range stays inside the values a supported voice can honor and
# administrators still verify their own voice (ADR-068).
MIN_VOICE_SPEED = 0.5
MAX_VOICE_SPEED = 1.5

DEFAULT_INSTRUCTIONS = (
    "You are a professional voice receptionist. Be concise, transparent, "
    "and use the available Odoo tools only when they are needed."
)
DEFAULT_GREETING = (
    "Hello! I can register your request or connect you with a colleague. "
    "Before I do, could you briefly tell me what you are calling about?"
)
CONTACT_GREETING = (
    "Hello, %(customer_name)s. Am I speaking with %(customer_name)s? "
    "I can register your request or connect you with a colleague. Before I "
    "do, could you briefly tell me what you are calling about?"
)
DEFAULT_WARM_TRANSFER_INSTRUCTIONS = (
    "Greet the recipient and briefly explain the caller's confirmed identity, "
    "the reason for the call, the relevant context, and the agreed next step. "
    "Ask whether the recipient is ready, then bridge the caller. Never present "
    "an unconfirmed identity as fact."
)

REMOTE_FIELDS = {
    "name", "description", "instructions", "greeting", "model",
    "voice", "voice_speed", "language_boost", "expressive_mode",
    "transcription_model",
    "transcription_language", "time_limit_secs", "record_calls",
    "language_mode", "default_lang",
    "memory_enabled", "enable_contact_tools", "enable_crm_tools",
    "enable_helpdesk_tools", "active", "receptionist_mode",
    "transfer_enabled", "manager", "transfer_callflows",
    "check_registration_before_transfer", "warm_transfer_instructions",
    "warm_transfer_message_delay_ms",
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
        default=DEFAULT_INSTRUCTIONS,
    )
    greeting = fields.Text(default=DEFAULT_GREETING)
    model = fields.Char(help="Leave empty to use the Telnyx default model.")
    voice = fields.Char(
        default=DEFAULT_VOICE,
        help="Telnyx voice identifier, for example AWS.Polly.Joanna-Neural. "
             "The available ids are listed by the Telnyx text-to-speech "
             "voices endpoint. Choose a multilingual voice such as Azure "
             "Multilingual, MiniMax, or Inworld when one assistant must "
             "speak several languages.")
    voice_speed = fields.Float(
        default=1.0,
        help="Speech rate multiplier between 0.5 and 1.5. Telnyx rejects a "
             "speed the selected voice does not support, and such a call "
             "ends after one second without a greeting. Telnyx Ultra needs "
             "at least 0.8; keep 1.0 when unsure.")
    language_boost = fields.Char(
        string="Voice Language Boost",
        help="Optional Telnyx TTS language hint. Use auto for supported "
             "multilingual voices, an explicit provider-supported language, "
             "or leave empty to keep the provider default.",
    )
    expressive_mode = fields.Boolean(
        string="Expressive Mode",
        help="Allow supported voices such as Telnyx Ultra to add contextual "
             "expression. Leave disabled for voices that do not support it.",
    )
    transcription_model = fields.Char(
        default="deepgram/nova-3",
        help="Speech recognition model. Telnyx recommends deepgram/nova-3 "
             "for multilingual assistants."
    )
    transcription_language = fields.Char(
        default="auto",
        help="Speech recognition language. Use auto for multilingual "
             "detection, or a supported language code to constrain it."
    )
    language_mode = fields.Selection(
        [
            ("contact", "Contact Language, Then Auto-Detect"),
            ("fixed", "Fixed Agent Language"),
            ("automatic", "Automatic Detection"),
        ],
        default="contact", required=True,
        help="Contact mode uses the language of the single contact matched "
             "by phone, then follows an explicit caller language change. "
             "Fixed mode always uses the agent language. Automatic mode "
             "starts with the agent language and detects the caller's "
             "language from speech.",
    )
    default_lang = fields.Many2one(
        "res.lang", string="Agent Language", ondelete="restrict",
        default=lambda self: self.env["res.lang"].search([
            ("code", "=", self.env.user.lang or "en_US")
        ], limit=1),
        help="Greeting and fallback conversation language when no unique "
             "contact language is available. Activate additional Odoo "
             "languages before assigning them to contacts."
    )
    time_limit_secs = fields.Integer(default=1800, required=True)
    record_calls = fields.Boolean(default=False)
    memory_enabled = fields.Boolean(
        default=False,
        help="Let Telnyx retrieve recent conversations for the same caller. "
             "This is Telnyx conversation memory, not Odoo Connect Memory.",
    )
    enable_contact_tools = fields.Boolean(
        default=True,
        help="Allow the assistant to find one unambiguous Odoo contact and "
             "add internal notes to it.",
    )
    enable_crm_tools = fields.Boolean(
        default=False,
        help="Allow the assistant to create or update an Odoo CRM lead.",
    )
    enable_helpdesk_tools = fields.Boolean(
        default=False,
        help="Allow the assistant to create or update an Odoo Helpdesk ticket.",
    )
    receptionist_mode = fields.Selection(
        [("personal", "Personal Receptionist"),
         ("company", "Company Receptionist")],
        required=True, default="personal",
    )
    transfer_enabled = fields.Boolean(default=True)
    manager = fields.Many2one(
        "connect.user", ondelete="set null",
        help="The manager represented by a personal receptionist.",
    )
    transfer_callflows = fields.Many2many(
        "connect.telnyx.callflow",
        "connect_telnyx_ai_assistant_callflow_rel",
        "assistant_id", "callflow_id",
        string="Department Call Flows",
        help="Company departments the assistant may transfer to. Their ring "
             "users become the available human recipients.",
    )
    check_registration_before_transfer = fields.Boolean(
        default=True,
        help="Use Telnyx live SIP registration status to omit definitely "
             "offline SIP and WebRTC devices. API errors remain advisory.",
    )
    warm_transfer_instructions = fields.Text(
        required=True, default=DEFAULT_WARM_TRANSFER_INSTRUCTIONS,
    )
    warm_transfer_message_delay_ms = fields.Integer(
        string="Warm Transfer Message Delay (ms)",
        default=2000,
        help="Wait after the recipient answers before playing the private "
             "briefing. Set to 0 to restore immediate playback if the delay "
             "does not improve WebRTC audio.",
    )
    domain = fields.Many2one(
        "connect.telnyx.domain", ondelete="set null",
        default=lambda self: self.env["connect.telnyx.domain"].search(
            [], limit=1),
        help="SIP domain used to call this assistant by extension.",
    )
    exten = fields.Many2one(
        "connect.telnyx.exten", ondelete="set null", readonly=True,
        string="Telnyx Extension",
    )
    exten_number = fields.Char(
        related="exten.number", store=True, string="Extension Number",
    )
    sip_uri = fields.Char(compute="_compute_sip_uri", string="SIP URI")
    transfer_tool_sid = fields.Char(
        string="Telnyx Transfer Tool ID", readonly=True, copy=False,
    )
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

    @api.constrains("voice_speed")
    def _check_voice_speed(self):
        for rec in self:
            if not (MIN_VOICE_SPEED <= rec.voice_speed <= MAX_VOICE_SPEED):
                raise ValidationError(
                    "The AI assistant voice speed must be between {} and "
                    "{}. Telnyx rejects a speed the selected voice does not "
                    "support and the assistant then hangs up without a "
                    "greeting.".format(MIN_VOICE_SPEED, MAX_VOICE_SPEED)
                )

    @api.constrains("warm_transfer_message_delay_ms")
    def _check_warm_transfer_message_delay(self):
        for rec in self:
            if rec.warm_transfer_message_delay_ms < 0:
                raise ValidationError(
                    "The warm transfer message delay cannot be negative."
                )

    @api.depends("exten.number", "domain.domain_name")
    def _compute_sip_uri(self):
        for rec in self:
            if rec.exten and rec.domain and rec.domain.domain_name:
                rec.sip_uri = "sip:{}@{}".format(
                    rec.exten.number, rec.domain.domain_name)
            else:
                rec.sip_uri = ""

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
        tools.append(self._webhook_tool(
            "register_call_request",
            "Register the caller's qualified request on the current Odoo call.",
            {
                "title": {
                    "type": "string",
                    "description": "Short request title.",
                },
                "summary": {
                    "type": "string",
                    "description": (
                        "Factual summary of the reason, context, and outcome."
                    ),
                },
                "requested_action": {
                    "type": "string",
                    "description": "Agreed next step or requested follow-up.",
                },
            },
            ["title", "summary"],
        ))
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

    def _effective_instructions(self):
        self.ensure_one()
        mode_text = (
            "You represent the configured manager."
            if self.receptionist_mode == "personal"
            else "You replace the company IVR and choose the appropriate "
                 "configured department."
        )
        policy = (
            "Odoo receptionist policy:\n"
            "- {}\n"
            "- Explain that you can register a request or connect the caller.\n"
            "- Begin in {{{{conversation_language_name}}}} "
            "({{{{conversation_language}}}}). The selected language source is "
            "{{{{conversation_language_source}}}}.\n"
            "- If {{{{language_switch_allowed}}}} is true and the caller clearly "
            "uses another language, switch to it and continue in that "
            "language. Otherwise keep using the selected language.\n"
            "- Before any transfer, determine why the caller is calling, the "
            "relevant context, and the requested outcome.\n"
            "- If customer_name is present, ask whether you are speaking with "
            "that person. Do not treat the identity as confirmed until the "
            "caller explicitly confirms it.\n"
            "- Never guess an identity when the contact match is ambiguous.\n"
            "- Use the Transfer tool only for a target it currently offers. "
            "If no target is available, offer to register the request instead.\n"
            "- Use register_call_request after the caller agrees that the "
            "qualified request should be saved.\n"
            "- During a warm transfer, brief the recipient before bridging the "
            "caller."
        ).format(mode_text)
        return "{}\n\n{}".format((self.instructions or "").strip(), policy)

    def _has_transfer_configuration(self):
        self.ensure_one()
        if not self.transfer_enabled:
            return False
        if self.receptionist_mode == "personal":
            return bool(self.manager)
        return bool(self.transfer_callflows)

    def _transfer_tool_payload(self):
        self.ensure_one()
        return {
            "type": "transfer",
            "display_name": "Odoo warm transfer - {}".format(self.name),
            "transfer": {
                "targets": "{{transfer_targets}}",
                "from": "{{telnyx_agent_target}}",
                "warm_transfer_instructions": (
                    self.warm_transfer_instructions
                    or DEFAULT_WARM_TRANSFER_INSTRUCTIONS
                ),
                "warm_message_delay_ms": (
                    self.warm_transfer_message_delay_ms or None
                ),
                "voicemail_detection": {
                    "detection_mode": "premium",
                    "on_voicemail_detected": {"action": "stop_transfer"},
                },
            },
            "timeout_ms": 5000,
        }

    def _delete_transfer_tool(self):
        self.ensure_one()
        if not self.transfer_tool_sid:
            return
        try:
            self.env["connect.settings"].telnyx_api_request(
                "DELETE", "ai/tools/{}".format(self.transfer_tool_sid))
        except ValidationError as exc:
            if "HTTP 404" not in str(exc):
                raise
        self.with_context(skip_telnyx_ai_sync=True).transfer_tool_sid = False

    def _sync_transfer_tool(self):
        self.ensure_one()
        if not self._has_transfer_configuration():
            self._delete_transfer_tool()
            return False
        settings = self.env["connect.settings"]
        payload = self._transfer_tool_payload()
        if self.transfer_tool_sid:
            try:
                settings.telnyx_api_request(
                    "PATCH", "ai/tools/{}".format(self.transfer_tool_sid),
                    payload=payload,
                )
            except ValidationError as exc:
                if "HTTP 404" not in str(exc):
                    raise
                self.with_context(
                    skip_telnyx_ai_sync=True).transfer_tool_sid = False
                return self._sync_transfer_tool()
            return self.transfer_tool_sid
        data = self._unwrap(settings.telnyx_api_request(
            "POST", "ai/tools", payload=payload)) or {}
        tool_sid = data.get("id")
        if not tool_sid:
            raise ValidationError("Telnyx did not return a Transfer tool ID.")
        self.with_context(skip_telnyx_ai_sync=True).transfer_tool_sid = tool_sid
        return tool_sid

    def _remote_payload(self):
        self.ensure_one()
        payload = {
            "name": self.name,
            "description": self.description or "",
            "instructions": self._effective_instructions(),
            "greeting": "{{odoo_initial_greeting}}",
            "dynamic_variables": self._partner_values(
                self.env["res.partner"], match_count=0
            ),
            "enabled_features": ["telephony"],
            "dynamic_variables_webhook_url": self._variables_url(),
            "dynamic_variables_webhook_timeout_ms": 5000,
            "tools": self._tool_payload(),
            "tool_ids": (
                [self.transfer_tool_sid] if self.transfer_tool_sid else []
            ),
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
            voice_settings = {
                "voice": self.voice,
                "voice_speed": self.voice_speed,
                "expressive_mode": self.expressive_mode,
            }
            if self.language_boost:
                voice_settings["language_boost"] = self.language_boost
            payload["voice_settings"] = voice_settings
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
    def _clamp_voice_speed(self, speed):
        """Keep a remote speed inside the range Odoo accepts.

        A speed set outside Odoo would otherwise fail the local constraint
        and break the whole synchronization for one unusable value.
        """
        try:
            speed = float(speed)
        except (TypeError, ValueError):
            return 1.0
        return min(max(speed, MIN_VOICE_SPEED), MAX_VOICE_SPEED)

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
            "voice_speed": self._clamp_voice_speed(
                voice_settings.get("voice_speed")
                or voice_settings.get("speed") or 1.0
            ),
            "language_boost": voice_settings.get("language_boost") or "",
            "expressive_mode": bool(voice_settings.get("expressive_mode")),
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
        self.with_context(skip_telnyx_ai_sync=True).write({
            "sid": data.get("id") or self.sid,
            "version_id": data.get("version_id") or self.version_id,
            "last_sync_at": fields.Datetime.now(),
        })

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
                "expressive_mode": False,
            }
            data = self._unwrap(
                settings.telnyx_api_request("POST", path, payload=payload))
            self.with_context(skip_telnyx_ai_sync=True).write({
                "voice": DEFAULT_VOICE,
                "language_boost": False,
                "expressive_mode": False,
            })
            settings.connect_notify(
                "Voice of the AI assistant '{}' was not available in Telnyx "
                "and was replaced with {}.".format(self.name, DEFAULT_VOICE),
                title="AI Assistant Voice", warning=True, sticky=True)
            return data

    def _create_remote(self):
        self.ensure_one()
        self._ensure_summary_group()
        self._sync_transfer_tool()
        self._apply_remote_data(self._push_remote("ai/assistants"))

    def _update_remote(self):
        self.ensure_one()
        if not self.sid:
            return self._create_remote()
        self._sync_transfer_tool()
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
            for rec in self:
                if rec.sid:
                    self.env["connect.settings"].telnyx_api_request(
                        "DELETE", "ai/assistants/{}".format(rec.sid)
                    )
                rec._delete_transfer_tool()
        return super().unlink()

    @api.model
    def _ensure_summary_group(self, instructions=None):
        settings = self.env["connect.settings"].sudo()
        insight_id = settings.get_param("telnyx_ai_summary_insight_id")
        group_id = settings.get_param("telnyx_ai_summary_group_id")
        if insight_id and group_id:
            return group_id
        api_url = settings.get_param("api_url")
        webhook = urljoin(api_url, "telnyx/webhook/assistant/insights")
        if not insight_id:
            # The caller passes the text when it was just edited: get_param
            # still serves the cached value inside that write.
            if instructions is None:
                instructions = settings.get_param(
                    "telnyx_ai_summary_instructions")
            insight = self._unwrap(settings.telnyx_api_request(
                "POST", "ai/conversations/insights", payload={
                    "name": "Odoo Connect Summary",
                    "instructions": (
                        instructions or DEFAULT_AI_SUMMARY_INSTRUCTIONS
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
        for rec in self.search([]):
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

    def create_extension(self):
        self.ensure_one()
        return self.env["connect.telnyx.exten"].create_extension(
            self, self._name)

    def render(self, request=None, params=None):
        self.ensure_one()
        if not self.sid:
            return "<Response><Say>AI assistant is not synchronized.</Say></Response>"
        response = VoiceResponse()
        connect = Connect()
        connect.ai_assistant(self.sid)
        response.append(connect)
        return response.to_xml()

    def _transfer_users(self):
        self.ensure_one()
        if self.receptionist_mode == "personal":
            return [(self.manager.name, self.manager)] if self.manager else []
        values = []
        for callflow in self.transfer_callflows:
            users = callflow.ring_users
            for user in users:
                label = callflow.name
                if len(users) > 1:
                    label = "{} - {}".format(callflow.name, user.name)
                values.append((label, user))
        return values

    def _transfer_targets(self):
        self.ensure_one()
        if not self._has_transfer_configuration():
            return [], []
        targets = []
        unavailable = []
        seen = set()
        for label, user in self._transfer_users():
            target = user._telnyx_transfer_target(
                check_registration=self.check_registration_before_transfer)
            if not target:
                unavailable.append(label)
                continue
            key = (label, target["to"])
            if key in seen:
                continue
            seen.add(key)
            targets.append({"name": label, "to": target["to"]})
        return targets, unavailable

    @api.model
    def _strict_partner_match(self, phone):
        Partner = self.env["res.partner"].sudo()
        if not phone:
            return Partner, 0
        found = Partner.search([("phone_mobile_search", "=", phone)])
        country = self.env.company.country_id.code
        normalized = format_number(Partner, phone, country)
        if normalized and normalized != phone:
            found |= Partner.search([
                ("phone_mobile_search", "=", normalized)])
        if normalized and "phone_sanitized" in Partner._fields:
            found |= Partner.search([("phone_sanitized", "=", normalized)])
        return (found if len(found) == 1 else Partner), len(found)

    def _language_values(self, partner=None):
        self.ensure_one()
        fallback = self.default_lang
        if not fallback:
            fallback = self.env["res.lang"].sudo().search([
                ("code", "=", self.env.user.lang or "en_US")
            ], limit=1)
        language_code = fallback.code or self.env.user.lang or "en_US"
        source = "agent"
        switch_allowed = self.language_mode != "fixed"
        if (self.language_mode == "contact" and partner
                and partner.lang):
            language_code = partner.lang
            source = "contact"
        elif self.language_mode == "automatic":
            source = "automatic"
        language = self.env["res.lang"].sudo().search([
            ("code", "=", language_code)
        ], limit=1)
        bcp47 = language_code.replace("_", "-")
        return {
            "conversation_language": bcp47,
            "conversation_language_code": bcp47.split("-", 1)[0].lower(),
            "conversation_language_name": language.name or bcp47,
            "conversation_language_source": source,
            "language_switch_allowed": switch_allowed,
        }

    def _initial_greeting(self, partner=None, language_code=None):
        self.ensure_one()
        language_code = language_code or self.env.user.lang or "en_US"
        localized_env = self.with_context(lang=language_code).env
        language_base = language_code.replace("-", "_").split("_", 1)[0]
        if partner:
            # Keep translatable strings literal so Odoo's extractor catalogs them.
            localized = localized_env._(
                "Hello, %(customer_name)s. Am I speaking with "
                "%(customer_name)s? I can register your request or connect "
                "you with a colleague. Before I do, could you briefly tell "
                "me what you are calling about?",
                customer_name=partner.display_name,
            )
            source = CONTACT_GREETING % {
                "customer_name": partner.display_name,
            }
            if language_base != "en" and localized == source:
                return self.greeting or DEFAULT_GREETING
            return localized
        localized = localized_env._(
            "Hello! I can register your request or connect you with a "
            "colleague. Before I do, could you briefly tell me what you are "
            "calling about?"
        )
        if language_base != "en" and localized != DEFAULT_GREETING:
            return localized
        return self.greeting or localized

    def _partner_values(self, partner, match_count=None):
        self.ensure_one()
        language_values = self._language_values(partner)
        language_code = language_values["conversation_language"].replace(
            "-", "_"
        )
        if not partner:
            count = match_count or 0
            values = {
                "found": False,
                "ambiguous": count > 1,
                "match_count": count,
                "customer_name": "",
                "customer_email": "",
                "customer_language": "",
            }
            values.update(language_values)
            values["odoo_initial_greeting"] = self._initial_greeting(
                language_code=language_code)
            return values
        values = {
            "found": True,
            "ambiguous": False,
            "match_count": 1,
            "identity_confirmation_required": True,
            "partner_id": partner.id,
            "customer_name": partner.display_name,
            "company_name": partner.parent_id.display_name or (
                partner.display_name if partner.is_company else ""
            ),
            "email": partner.email or "",
            "language": partner.lang or "",
            "customer_email": partner.email or "",
            "customer_language": partner.lang or "",
        }
        values.update(language_values)
        values["odoo_initial_greeting"] = self._initial_greeting(
            partner=partner, language_code=language_code)
        return values

    def _resolve_partner_match(self, payload, call_control_id=None):
        self.ensure_one()
        phone = payload.get("phone")
        if phone:
            return self._strict_partner_match(phone)
        if call_control_id:
            channel = self.env["connect.channel"].sudo().search(
                [("sid", "=", call_control_id)], limit=1
            )
            phone = channel.call.caller or channel.caller
            if phone:
                return self._strict_partner_match(phone)
        return self.env["res.partner"], 0

    def _resolve_partner(self, payload, call_control_id=None):
        return self._resolve_partner_match(payload, call_control_id)[0]

    def execute_tool(self, tool_name, payload, call_control_id=None):
        self.ensure_one()
        allowed = {
            "register_call_request", "lookup_contact", "add_contact_note",
            "upsert_crm_lead", "upsert_helpdesk_ticket",
        }
        if tool_name not in allowed:
            raise ValidationError("Unknown AI assistant tool.")
        if (tool_name in ("lookup_contact", "add_contact_note")
                and not self.enable_contact_tools):
            raise ValidationError("Contact tools are disabled.")
        partner, match_count = self._resolve_partner_match(
            payload, call_control_id)
        phone = payload.get("phone") or (
            partner.phone or partner.mobile if partner else ""
        )
        if tool_name == "register_call_request":
            channel = self.env["connect.channel"].sudo().search(
                [("sid", "=", call_control_id)], limit=1
            ) if call_control_id else self.env["connect.channel"]
            call = channel.call
            if not call:
                return {"ok": False, "error": "call_not_found"}
            title = (payload.get("title") or "").strip()[:255]
            summary = (payload.get("summary") or "").strip()
            requested_action = (
                payload.get("requested_action") or "").strip()
            if not title or not summary:
                raise ValidationError("A request title and summary are required.")
            if len(summary) + len(requested_action) > 8000:
                raise ValidationError("The registered request is too long.")
            body = "<strong>{}</strong><br/>{}".format(
                escape(title), escape(summary))
            if requested_action:
                body += "<br/><strong>Requested action:</strong> {}".format(
                    escape(requested_action))
            call.sudo().message_post(body=body, subtype_xmlid="mail.mt_note")
            if partner and not call.partner:
                call.sudo().partner = partner
            return {"ok": True, "call_id": call.id}
        if tool_name == "lookup_contact":
            return self._partner_values(partner, match_count=match_count)
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

# -*- coding: utf-8 -*-
import logging
import re
from urllib.parse import urljoin, urlparse

from odoo import fields, models, api, release
from odoo.exceptions import ValidationError

from voiceml import Client
from voiceml.models import CreateCallRequest

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)

MAX_EXTEN_LEN = 4

VOICEML_PROTECTED_FIELDS = [
    "display_api_key",
]


def format_connect_response(text):
    if not isinstance(text, str):
        text = str(text)
    return re.sub(r"\x1b\[[\d;]+m", "", text)


def strip_number(number):
    if not isinstance(number, str):
        return number
    return re.sub(r"[\s\(\)\-\+]", "", number).lstrip("0")


class Settings(models.Model):
    _inherit = "connect.settings"

    account_sid = fields.Char(string="Account SID")
    # API key is both the VoiceML SDK auth token and the X-Twilio-Signature
    # verification key for inbound webhooks. Admin-only, like connect_twilio's
    # auth_token: the webhook controllers read it via sudo().
    api_key = fields.Char(groups="base.group_erp_manager")
    display_api_key = fields.Char()
    voiceml_base_url = fields.Char(
        string="VoiceML API URL",
        help="Base URL of the VoiceML REST API, e.g. "
        "https://voiceml.voicetel.com. The VoiceML SDK is pointed here.",
    )
    voiceml_wss_url = fields.Char(
        string="WebRTC WSS URL",
        help="wss:// URL of the OpenSIPS registrar the browser softphone "
        "registers against (e.g. wss://<node>:8443).",
    )
    voiceml_auto_sync = fields.Boolean(default=True)
    voiceml_verify_requests = fields.Boolean(
        default=True, string="Verify VoiceML Requests"
    )

    @api.model
    def get_media_auth(self, media_url):
        """Recording media on VoiceML is Basic-authed with the tenant key.

        Only attach credentials for our own API host: an externally-hosted
        media URL (presigned S3 bucket) must not receive the API key.
        """
        host = (urlparse(media_url or '').hostname or '').lower()
        base_host = (urlparse(self.sudo().get_param('voiceml_base_url') or '').hostname or '').lower()
        if not base_host or host != base_host:
            return super().get_media_auth(media_url)
        account_sid = self.sudo().get_param('account_sid')
        api_key = self.sudo().get_param('api_key')
        if not (account_sid and api_key):
            return super().get_media_auth(media_url)
        return (account_sid, api_key)

    @api.model
    def get_client(self):
        try:
            account_sid = self.sudo().get_param("account_sid")
            api_key = self.sudo().get_param("api_key")
            base_url = self.sudo().get_param("voiceml_base_url")
            kwargs = {"account_sid": account_sid, "api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            return Client(**kwargs)
        except Exception as e:
            if "Credentials are required" in str(e):
                raise ValidationError("Set VoiceML API keys first!")
            raise

    def _webhook_url(self, path):
        api_url = self.sudo().get_param("api_url")
        return urljoin(api_url, path)

    def sync(self):
        if not (
            self.sudo().get_param("account_sid")
            and self.sudo().get_param("api_key")
        ):
            raise ValidationError("You must set Account SID and API key!")
        api_url_check = self.check_api_url()
        if api_url_check:
            raise ValidationError(api_url_check)
        try:
            self.env["connect.voiceml.application"].sync()
            self.env["connect.voiceml.domain"].sync()
            self.env["connect.voiceml.number"].sync()
            self.env["connect.voiceml.outgoing_callerid"].sync()
            self.connect_notify(
                "VoiceML account synced successfully", title="Sync Complete"
            )
        except Exception as e:
            if '20003' in str(e):
                raise ValidationError(
                    'Error authenticating requests to the VoiceML API! Check your API key!'
                )
            raise

    def compute_sip_uri(self, user):
        return "sip:{}".format(user.connect_user.uri)

    def get_external_call_route(self, number, callerId, status_url):
        call_duration_limit = int(self.sudo().get_param('call_duration_limit'))
        from .twiml_builder import TwiMLResponse
        response = TwiMLResponse()
        response.dial(
            callerId=callerId, timeLimit=call_duration_limit
        ).number(
            number, statusCallback=status_url,
            statusCallbackEvent='initiated answered completed',
        )
        return response.to_string()

    @api.model
    def originate_call(self, number, res_model=None, res_id=None, user=None, **kwargs):
        if self._get_originate_provider(user) != 'voiceml':
            return super().originate_call(
                number, res_model=res_model, res_id=res_id, user=user, **kwargs)
        number = strip_number(number)
        if len(number) > MAX_EXTEN_LEN:
            number = "+{}".format(number)
        client = self.get_client()
        partner_id = False
        caller_name = ""
        obj = self.env[res_model].browse(res_id) if res_model and res_id else False
        if res_model == "res.partner" and obj:
            partner_id = res_id
            caller_name = obj.display_name
        elif obj and hasattr(obj, "partner_id") and obj.partner_id:
            partner_id = obj.partner_id.id
            caller_name = obj.partner_id.display_name
        elif obj and hasattr(obj, "partner") and obj.partner:
            partner_id = obj.partner.id
            caller_name = obj.partner.display_name
        if not user:
            user = self.env.user
        if not user.connect_user:
            raise ValidationError("User does not have a SIP username defined!")
        to = self.compute_sip_uri(user)
        exten = self.env["connect.voiceml.exten"].search(
            [("number", "=", number)], limit=1
        )
        status_url = self._webhook_url("voiceml/webhook/callstatus")
        if exten:
            callerId = user.connect_user.voiceml_caller_id()
            twiml = exten.sudo().render()
        else:
            default_number = self.env[
                "connect.voiceml.outgoing_callerid"
            ].search([("is_default", "=", True)], limit=1)
            callerId = (
                user.connect_user.voiceml_outgoing_callerid.number
                or default_number.number
            )
            twiml = self.get_external_call_route(number, callerId, status_url)
        debug(self, 'Originate destination TwiML: {}'.format(twiml))
        record = user.connect_user.record_calls
        record_status_url = self._webhook_url("voiceml/webhook/recordingstatus")
        channel = client.calls.create(CreateCallRequest(
            to=to,
            from_=callerId,
            twiml=twiml,
            status_callback=status_url,
            status_callback_event=["initiated", "answered", "completed"],
            record=record,
            recording_channels="dual",
            recording_status_callback=record_status_url,
            recording_status_callback_event="completed",
        ))
        self.env["connect.channel"].sudo().create(
            {
                "sid": channel.sid,
                "technical_direction": "outbound-api",
                "call_type": 'phone',
                "caller_user": user.id,
                "caller_pbx_user": user.connect_user.id,
                "partner": partner_id,
                "called": number,
                "caller": callerId,
            }
        )

    def write(self, vals):
        if self.env.context.get("skip_protected_fields"):
            return super(Settings, self).write(vals)
        res = super(Settings, self).write(vals)
        changed_fields = {}
        for field_name in VOICEML_PROTECTED_FIELDS:
            if vals.get(field_name):
                changed_fields.update(
                    {
                        field_name.replace("display_", ""): vals.get(field_name),
                        field_name: "*" * len(vals.get(field_name)),
                    }
                )
        if changed_fields:
            self.with_context(skip_protected_fields=True).sudo().write(changed_fields)
        if release.version_info[0] >= 17:
            self.env.registry.clear_cache()
        else:
            self.clear_caches()

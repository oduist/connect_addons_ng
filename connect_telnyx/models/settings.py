# -*- coding: utf-8 -*-
import logging
import re
from urllib.parse import urljoin

from odoo import fields, models, api, release
from odoo.exceptions import ValidationError
from telnyx import Telnyx

from odoo.addons.connect.models.license import ODUIST_MODULES
from odoo.addons.connect.models.settings import debug

from .texml_response import pretty_xml

ODUIST_MODULES.append('connect_telnyx')


logger = logging.getLogger(__name__)

MAX_EXTEN_LEN = 4

TELNYX_PROTECTED_FIELDS = [
    "display_telnyx_api_key",
]


def format_connect_response(text):
    if not isinstance(text, str):
        text = str(text)
    symbol_pattern = re.compile(r"(\x08.)|\x08")
    text = symbol_pattern.sub("", text)
    color_pattern = re.compile(r"\x1b\[[\d;]+m")
    text = color_pattern.sub("", text)
    return text


def strip_number(number):
    """Strip number formatting"""
    if not isinstance(number, str):
        return number
    pattern = r"[\s\(\)\-\+]"
    return re.sub(pattern, "", number).lstrip("0")


class Settings(models.Model):
    _inherit = "connect.settings"

    # Never grant this to connect.group_webhook: the webhook user is the
    # identity of all public webhook controllers, and get_param() returns
    # groups-restricted fields to group members (ADR-025).
    telnyx_api_key = fields.Char(groups="base.group_erp_manager")
    display_telnyx_api_key = fields.Char(string="Telnyx API Key")
    # The Ed25519 public key from Mission Control used to verify webhook
    # signatures. Not a secret.
    telnyx_public_key = fields.Char(string="Telnyx Public Key")
    # TeXML Account SID (the Telnyx account/user ID from Mission Control).
    # Required for the TeXML REST originate API; Telnyx has no discovery
    # endpoint for it (ADR-032).
    telnyx_account_sid = fields.Char(string="Telnyx Account SID")
    telnyx_messaging_profile_id = fields.Char(readonly=True)
    telnyx_balance = fields.Char(readonly=True)
    telnyx_auto_sync = fields.Boolean(default=True)
    telnyx_verify_requests = fields.Boolean(
        default=True, string="Verify Telnyx Requests"
    )
    telnyx_fetch_call_prices = fields.Boolean(
        default=False,
        string="Fetch Call Prices",
        help="Enable fetching call costs from Telnyx detail records after call completion."
    )

    @api.model
    def get_telnyx_client(self):
        # connect.settings is admin-only; credentials are read with sudo()
        # below, so no caller-level model access check is needed here.
        api_key = self.sudo().get_param("telnyx_api_key")
        if not api_key:
            raise ValidationError("Set Telnyx API key first!")
        public_key = self.sudo().get_param("telnyx_public_key")
        return Telnyx(api_key=api_key, public_key=public_key or None)

    def telnyx_sync(self):
        if not self.sudo().get_param("telnyx_api_key"):
            raise ValidationError("You must set the Telnyx API key!")
        api_url_check = self.check_api_url()
        if api_url_check:
            raise ValidationError(api_url_check)
        try:
            self._ensure_telnyx_messaging_profile()
            self.env["connect.telnyx.texml"].sync()
            self.env["connect.telnyx.domain"].sync()
            self.env["connect.telnyx.number"].sync()
            self.env["connect.telnyx.outgoing_callerid"].sync()
            # WhatsApp/RCS onboarding is optional on the Telnyx account —
            # keep their sync failures non-fatal (ADR-033).
            for model, title in [
                ("connect.telnyx.whatsapp_sender", "WhatsApp Senders"),
                ("connect.telnyx.whatsapp_template", "WhatsApp Templates"),
                ("connect.telnyx.rcs_agent", "RCS Agents"),
            ]:
                try:
                    self.env[model].sync()
                except Exception as e:
                    logger.warning('%s sync failed: %s', title, e)
                    self.connect_notify(
                        "{} sync failed: {}".format(title, e),
                        title="Sync Warning", warning=True)
            self.connect_notify(
                "Telnyx account synced successfully", title="Sync Complete")
        except Exception as e:
            if 'Authentication failed' in str(e) or '401' in str(e):
                raise ValidationError(
                    'Error authenticating requests to the Telnyx API! '
                    'Check your API key!'
                )
            else:
                raise

    def _ensure_telnyx_messaging_profile(self):
        """Get or create the messaging profile used for Odoo messaging."""
        client = self.get_telnyx_client()
        api_url = self.sudo().get_param('api_url')
        webhook_url = urljoin(api_url, 'telnyx/webhook/message')
        profile_id = self.sudo().get_param('telnyx_messaging_profile_id')
        if profile_id:
            try:
                client.messaging_profiles.update(
                    profile_id, webhook_url=webhook_url)
                return profile_id
            except Exception as e:
                if 'not found' not in str(e).lower() and '404' not in str(e):
                    raise
                debug(self, 'Messaging profile {} not found, recreating.'.format(
                    profile_id))
        for profile in client.messaging_profiles.list():
            if profile.name == 'Odoo Connect':
                self.sudo().set_param(
                    'telnyx_messaging_profile_id', profile.id)
                client.messaging_profiles.update(
                    profile.id, webhook_url=webhook_url)
                return profile.id
        profile = client.messaging_profiles.create(
            name='Odoo Connect', webhook_url=webhook_url)
        self.sudo().set_param('telnyx_messaging_profile_id', profile.data.id)
        return profile.data.id

    def compute_telnyx_sip_uri(self, user):
        return "sip:{}".format(self.env.user.connect_user.telnyx_uri)

    def get_telnyx_external_call_route(self, number, callerId, status_url):
        call_duration_limit = int(self.sudo().get_param('call_duration_limit'))
        texml = """
        <Response>
            <Dial callerId="{}" timeLimit="{}"><Number statusCallback='{}' statusCallbackEvent='initiated answered completed'>{}</Number></Dial>
        </Response>
        """.format(
            callerId, call_duration_limit, status_url, number
        )
        return texml

    @api.model
    def originate_call(self, number, res_model=None, res_id=None, user=None, **kwargs):
        # Dispatch by the user's click-to-call provider; fall through to
        # other installed telephony modules when it is not Telnyx.
        if self._get_originate_provider(user) != 'telnyx':
            return super().originate_call(
                number, res_model=res_model, res_id=res_id, user=user, **kwargs)
        self.env["oduist.license"].check_license("connect", silent=False)
        account_sid = self.sudo().get_param("telnyx_account_sid")
        if not account_sid:
            raise ValidationError(
                "Set the Telnyx Account SID in Telnyx settings first!")
        number = strip_number(number)
        if len(number) > MAX_EXTEN_LEN:
            number = "+{}".format(number)
        client = self.get_telnyx_client()
        partner_id = False
        obj = self.env[res_model].browse(res_id) if res_model and res_id else False
        caller_name = ""
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
        connect_user = user.connect_user
        if not connect_user:
            raise ValidationError("User does not have a PBX user defined!")
        first_flow = self.env['connect.telnyx.user_callflow'].search([
            ('user', '=', connect_user.id),
            ('callflow_type', 'in', ['client', 'sip'])
        ], order='prio', limit=1)
        if first_flow.callflow_type == 'sip':
            to = 'sip:{}@sip.telnyx.com'.format(connect_user.telnyx_sip_username)
        else:
            # X- URI parameters surface as custom headers in the TelnyxRTC
            # notification, mirroring Twilio's client: URL parameters.
            to = (
                'sip:{}@sip.telnyx.com?X-autoAnswer=yes&X-Partner={}'
                '&X-CallerName={}&X-From={}'.format(
                    connect_user.telnyx_client_username,
                    partner_id or '',
                    caller_name or '',
                    (number or '').replace('+', ''),
                )
            )
        exten = self.env["connect.telnyx.exten"].search(
            [("number", "=", number)], limit=1
        )
        api_url = self.sudo().get_param("api_url")
        status_url = urljoin(api_url, "telnyx/webhook/callstatus")
        if exten:
            callerId = connect_user.telnyx_exten.number
            texml = exten.render()
        else:
            default_number = self.env[
                "connect.telnyx.outgoing_callerid"
            ].search([("is_default", "=", True)], limit=1)
            if connect_user.telnyx_outgoing_callerid:
                callerId = connect_user.telnyx_outgoing_callerid.number
            else:
                callerId = default_number.number
            texml = self.get_telnyx_external_call_route(
                number, callerId, status_url
            )
        record = connect_user.record_calls
        record_status_url = urljoin(api_url, "telnyx/webhook/recordingstatus")
        debug(self, 'Originate destination TeXML: {}'.format(texml))
        call_kwargs = {
            'texml': str(texml),
            'to': to,
            'from_': callerId,
            'status_callback': status_url,
            'status_callback_event': 'initiated answered completed',
        }
        if record:
            call_kwargs.update({
                'record': True,
                'recording_channels': 'dual',
                'recording_status_callback': record_status_url,
                'recording_status_callback_event': 'completed',
            })
        channel = client.texml.accounts.calls.calls(account_sid, **call_kwargs)
        # The SDK types the TeXML originate response narrowly, but the
        # Twilio-compatible payload carries the call `sid` as an extra field.
        channel_sid = getattr(channel, 'sid', None)
        if not channel_sid:
            raise ValidationError(
                'Telnyx originate response has no call SID: {}'.format(channel))
        self.env["connect.channel"].sudo().create(
            {
                "sid": channel_sid,
                "technical_direction": "outbound-api",
                "caller_user": user.id,
                "caller_pbx_user": connect_user.id,
                "partner": partner_id,
                "called": number,
                "caller": callerId,
            }
        )

    def get_telnyx_balance(self):
        """Fetch current Telnyx account balance"""
        try:
            client = self.get_telnyx_client()
            balance_item = client.balance.retrieve()
            data = balance_item.data
            balance = "{} {}".format(
                getattr(data, 'balance', '0.00'),
                getattr(data, 'currency', 'USD'),
            )
            self.set_param('telnyx_balance', balance)
            self.connect_notify(
                "Telnyx Balance: {}".format(balance), title="Balance Update"
            )
            return balance
        except Exception as e:
            error_msg = "Failed to fetch Telnyx balance: {}".format(str(e))
            self.connect_notify(error_msg, title="Balance Error", warning=True)
            raise ValidationError(error_msg)

    def write(self, vals):
        if self.env.context.get("skip_protected_fields"):
            return super(Settings, self).write(vals)
        res = super(Settings, self).write(vals)
        changed_fields = {}
        for field_name in TELNYX_PROTECTED_FIELDS:
            if vals.get(field_name):
                changed_fields.update(
                    {
                        field_name.replace("display_", ""): vals.get(
                            field_name
                        ),
                        field_name: "*" * len(vals.get(field_name)),
                    }
                )
        if changed_fields:
            self.with_context(
                skip_protected_fields=True
            ).sudo().write(changed_fields)
        if release.version_info[0] >= 17:
            self.env.registry.clear_cache()
        else:
            self.clear_caches()

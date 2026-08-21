# -*- coding: utf-8 -*-
import logging
import re
from urllib.parse import urljoin

from odoo import fields, models, api, release
from odoo.exceptions import ValidationError
from twilio.rest import Client

from odoo.addons.connect.models.license import ODUIST_MODULES
from odoo.addons.connect.models.settings import debug

ODUIST_MODULES.append('connect_twilio')


logger = logging.getLogger(__name__)

TWILIO_LOG_LEVEL = logging.WARNING

MAX_EXTEN_LEN = 4

TWILIO_PROTECTED_FIELDS = [
    "display_auth_token",
    "display_twilio_api_secret",
]

TWILIO_EDGES = [
    ('ashburn', 'US East Coast (Virginia)'),
    ('umatilla', 'US West Coast (Oregon)'),
    ('dublin', 'Ireland'),
    ('frankfurt', 'Frankfurt'),
    ('sydney', 'Australia'),
    ('sao-paulo', 'Brazil'),
    ('tokyo', 'Japan'),
    ('singapore', 'Singapore'),
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

    account_sid = fields.Char(string="Account SID")
    # Never grant this to connect.group_webhook: the webhook user is the
    # identity of all public webhook controllers, and get_param() returns
    # groups-restricted fields to group members. Signature validation in
    # the controllers reads the token via sudo() and is not affected.
    auth_token = fields.Char(groups="base.group_erp_manager")
    display_auth_token = fields.Char()
    twilio_api_key = fields.Char()
    twilio_api_secret = fields.Char(groups="base.group_erp_manager")
    display_twilio_api_secret = fields.Char()
    twilio_balance = fields.Char(readonly=True)
    twilio_region = fields.Selection([
        ('us1', 'US East (Virginia)'),
        ('ie1', 'Ireland (Dublin)'),
        ('au1', 'Australia (Sydney)'),
    ], default='us1', required=True)
    twilio_edge = fields.Selection(
        selection=TWILIO_EDGES, required=True, default='ashburn'
    )
    twilio_auto_sync = fields.Boolean(default=True)
    twilio_verify_requests = fields.Boolean(
        default=True, string="Verify Twilio Requests"
    )
    fetch_call_prices = fields.Boolean(
        default=False,
        string="Fetch Call Prices",
        help="Enable fetching call prices from Twilio API after call completion."
    )

    @api.model
    def get_client(self):
        try:
            # connect.settings is admin-only; credentials are read with sudo()
            # below, so no caller-level model access check is needed here.
            account_sid = self.sudo().get_param("account_sid")
            auth_token = self.sudo().get_param("auth_token")
            client = Client(account_sid, auth_token)
            twilio_region = self.sudo().get_param("twilio_region")
            if twilio_region:
                client.region = twilio_region
            twilio_edge = self.sudo().get_param("twilio_edge")
            if twilio_edge:
                client.edge = twilio_edge
            client.http_client.logger.setLevel(TWILIO_LOG_LEVEL)
            return client
        except Exception as e:
            if "Credentials are required" in str(e):
                raise ValidationError("Set Twilio API keys first!")
            else:
                raise

    def sync(self):
        if not (
            self.sudo().get_param("account_sid")
            and self.sudo().get_param("auth_token")
        ):
            raise ValidationError("You must set account SID and Auth token!")
        api_url_check = self.check_api_url()
        if api_url_check:
            raise ValidationError(api_url_check)
        try:
            self.env["connect.twilio.twiml"].sync()
            self.env["connect.twilio.domain"].sync()
            self.env["connect.twilio.number"].sync()
            self.env["connect.twilio.outgoing_callerid"].sync()
            self.env["connect.whatsapp_sender"].sync()
            self.env["connect.message_content_template"].sync()
            self.connect_notify("Twilio account synced successfully", title="Sync Complete")
        except Exception as e:
            if 'errors/20003' in str(e):
                raise ValidationError(
                    'Error authenticating requests to the Twilio API! Check your Auth Key!'
                )
            else:
                raise

    def compute_sip_uri(self, user):
        return "sip:{}".format(self.env.user.connect_user.uri)

    def get_external_call_route(self, number, callerId, status_url):
        call_duration_limit = int(self.sudo().get_param('call_duration_limit'))
        twiml = """
        <Response>
            <Dial callerId="{}" timeLimit="{}"><Number statusCallback='{}' statusCallbackEvent='initiated answered completed'>{}</Number></Dial>
        </Response>
        """.format(
            callerId, call_duration_limit, status_url, number
        )
        return twiml

    @api.model
    def originate_call(self, number, res_model=None, res_id=None, user=None, whatsapp_call=False, **kwargs):
        # Dispatch by the user's click-to-call provider; fall through to
        # other installed telephony modules when it is not Twilio.
        if self._get_originate_provider(user) != 'twilio':
            return super().originate_call(
                number, res_model=res_model, res_id=res_id, user=user, **kwargs)
        self.env["oduist.license"].check_license("connect", silent=False)
        number = strip_number(number)
        if len(number) > MAX_EXTEN_LEN:
            number = "+{}".format(number)
        client = self.get_client()
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
        if not user.connect_user:
            raise ValidationError("User does not have a SIP username defined!")
        first_flow = self.env['connect.twilio.user_callflow'].search([
            ('user', '=', user.id),
            ('callflow_type', 'in', ['client', 'sip'])
        ], order='prio', limit=1)
        if first_flow.callflow_type == 'sip':
            to = self.compute_sip_uri(user)
        else:
            to = (
                "client:{}?autoAnswer=yes&Partner={}&CallerName={}".format(
                    self.env.user.connect_user.uri,
                    partner_id or '',
                    caller_name or ''
                )
            )
        if "client:" in to:
            to += "&From={}".format((number or '').replace("+", ""))
        exten = self.env["connect.twilio.exten"].search(
            [("number", "=", number)], limit=1
        )
        api_url = self.sudo().get_param("api_url")
        edge = (
            self.twilio_edge
            or self.env['connect.settings'].get_param('twilio_edge')
        )
        status_url = urljoin(
            api_url, "twilio/webhook/callstatus#e={}".format(edge)
        )
        if exten:
            # An extension-less caller must still present an identity: an
            # empty caller ID makes Twilio substitute an arbitrary number.
            callerId = user.connect_user.twilio_caller_id()
            # Rendering the destination dialplan is system work: it reads the
            # callee's connect.user, which the record rules keep private to
            # its owner. Without sudo, calling a colleague's extension fails
            # with an AccessError on connect.user.
            twiml = exten.sudo().render()
        else:
            if whatsapp_call:
                pbx_user = user.connect_user
                sender = self.env['connect.whatsapp_sender'].get_default_sender(
                    pbx_user
                )
                caller_number = sender.number if sender else False
                if not caller_number:
                    raise ValidationError(
                        "You must configure a WhatsApp sender!"
                    )
                callerId = "whatsapp:{}".format(caller_number)
                twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial callerId="{}">
        <WhatsApp statusCallback="{}" statusCallbackEvent="ringing answered completed">{}</WhatsApp>
    </Dial>
</Response>""".format(callerId, status_url, number)
            else:
                default_number = self.env[
                    "connect.twilio.outgoing_callerid"
                ].search([("is_default", "=", True)], limit=1)
                if user.connect_user.twilio_outgoing_callerid:
                    callerId = user.connect_user.twilio_outgoing_callerid.number
                else:
                    callerId = default_number.number
                twiml = self.get_external_call_route(
                    number, callerId, status_url
                )
        record = self.env.user.connect_user.record_calls
        record_status_url = urljoin(
            api_url, "twilio/webhook/recordingstatus#e={}".format(edge)
        )
        debug(self, 'Originate destination TwiML: {}'.format(twiml))
        channel = client.calls.create(
            twiml=twiml,
            to=to,
            from_=callerId,
            status_callback=status_url,
            record=record,
            recording_channels="dual",
            recording_status_callback=record_status_url,
            recording_status_callback_event=["completed"],
            status_callback_event=["initiated", "answered", "completed"],
        )
        self.env["connect.channel"].sudo().create(
            {
                "sid": channel.sid,
                "technical_direction": "outbound-api",
                "caller_user": user.id,
                "caller_pbx_user": user.connect_user.id,
                "partner": partner_id,
                "called": number,
                "caller": callerId,
            }
        )

    @api.onchange('twilio_region')
    def _reset_twilio_edge(self):
        if self.twilio_region == 'us1':
            self.twilio_edge = 'ashburn'
        elif self.twilio_region == 'ie1':
            self.twilio_edge = 'dublin'
        elif self.twilio_region == 'au1':
            self.twilio_edge = 'sydney'

    def get_twilio_balance(self):
        """Fetch current Twilio account balance"""
        try:
            client = self.get_client()
            try:
                balance_item = client.api.v2010.account.balance.fetch()
                currency = getattr(balance_item, 'currency', 'USD')
                balance_value = getattr(balance_item, 'balance', '0.00')
                balance = "${} {}".format(balance_value, currency)
            except Exception as balance_error:
                if (
                    '20404' in str(balance_error)
                    or 'not found' in str(balance_error).lower()
                ):
                    balance = "Balance API not available for this account"
                    self.set_param('twilio_balance', balance)
                    self.connect_notify(
                        "Twilio Balance: {}. The balance endpoint may not be "
                        "available for your account type or region.".format(
                            balance
                        ),
                        title="Balance Info",
                    )
                    return balance
                else:
                    raise balance_error
            self.set_param('twilio_balance', balance)
            self.connect_notify(
                "Twilio Balance: {}".format(balance), title="Balance Update"
            )
            return balance
        except Exception as e:
            error_msg = "Failed to fetch Twilio balance: {}".format(str(e))
            self.connect_notify(error_msg, title="Balance Error", warning=True)
            raise ValidationError(error_msg)

    def write(self, vals):
        if self.env.context.get("skip_protected_fields"):
            return super(Settings, self).write(vals)
        res = super(Settings, self).write(vals)
        changed_fields = {}
        for field_name in TWILIO_PROTECTED_FIELDS:
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

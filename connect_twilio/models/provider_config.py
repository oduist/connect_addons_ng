"""Twilio per-provider configuration singleton (ADR-025 / ODU-22).

Moves Twilio-specific fields and methods off the flat `connect.settings`
notebook into a dedicated singleton owned by `connect_twilio`. Same
pattern as `connect.provider.elevenlabs.config` (ODU-11).

Field-name renames (strip `twilio_` prefix, drop the `display_` mirror
prefix to a per-protected-field local pattern):
  twilio_api_key       → api_key
  twilio_api_secret    → api_secret
  display_twilio_api_secret → display_api_secret
  twilio_balance       → balance
  twilio_region        → region
  twilio_edge          → edge
  twilio_auto_sync     → auto_sync
  twilio_verify_requests → verify_requests
  (account_sid / auth_token / display_auth_token / fetch_call_prices
   were not prefixed; names stay)
"""
import logging
from urllib.parse import urljoin

from twilio.rest import Client

from odoo import api, fields, models, release
from odoo.exceptions import ValidationError

from odoo.addons.connect.models.settings import debug
from .settings import (
    MAX_EXTEN_LEN, TWILIO_EDGES, TWILIO_LOG_LEVEL,
    strip_number,
)

logger = logging.getLogger(__name__)

PROTECTED_FIELDS = {'display_auth_token', 'display_api_secret'}


class ConnectProviderTwilioConfig(models.Model):
    _name = 'connect.provider.twilio.config'
    _description = 'Twilio Provider Configuration'

    account_sid = fields.Char(string='Account SID')
    auth_token = fields.Char(groups='base.group_erp_manager,connect.group_webhook')
    display_auth_token = fields.Char()
    api_key = fields.Char()
    api_secret = fields.Char(groups='base.group_erp_manager')
    display_api_secret = fields.Char()
    balance = fields.Char(readonly=True)
    region = fields.Selection([
        ('us1', 'US East (Virginia)'),
        ('ie1', 'Ireland (Dublin)'),
        ('au1', 'Australia (Sydney)'),
    ], default='us1', required=True)
    edge = fields.Selection(selection=TWILIO_EDGES, required=True, default='ashburn')
    auto_sync = fields.Boolean(default=True)
    verify_requests = fields.Boolean(
        default=True, string='Verify Twilio Requests',
    )
    fetch_call_prices = fields.Boolean(
        default=False, string='Fetch Call Prices',
        help='Enable fetching call prices from Twilio API after call completion.',
    )

    @api.model
    def _get(self):
        """Singleton accessor. Creates the record on first use."""
        rec = self.sudo().search([], limit=1)
        if not rec:
            rec = self.sudo().with_context(skip_protected_fields=True).create({})
        return rec

    def write(self, vals):
        if self.env.context.get('skip_protected_fields'):
            return super().write(vals)
        res = super().write(vals)
        changed = {}
        for fname in PROTECTED_FIELDS:
            if vals.get(fname):
                value = vals[fname]
                changed[fname.replace('display_', '')] = value
                changed[fname] = '*' * len(value)
        if changed:
            self.with_context(skip_protected_fields=True).sudo().write(changed)
        return res

    @api.onchange('region')
    def _reset_edge(self):
        if self.region == 'us1':
            self.edge = 'ashburn'
        elif self.region == 'ie1':
            self.edge = 'dublin'
        elif self.region == 'au1':
            self.edge = 'sydney'

    @api.model
    def get_client(self):
        try:
            cfg = self._get()
            (
                cfg.check_access_rule('read')
                if release.version_info[0] < 18
                else cfg.check_access('read')
            )
            cfg_su = cfg.sudo()
            client = Client(cfg_su.account_sid, cfg_su.auth_token)
            if cfg_su.region:
                client.region = cfg_su.region
            if cfg_su.edge:
                client.edge = cfg_su.edge
            client.http_client.logger.setLevel(TWILIO_LOG_LEVEL)
            return client
        except Exception as e:
            if 'Credentials are required' in str(e):
                raise ValidationError('Set Twilio API keys first!')
            raise

    def sync(self):
        cfg = self.sudo()
        if not (cfg.account_sid and cfg.auth_token):
            raise ValidationError('You must set account SID and Auth token!')
        api_url_check = self.env['connect.settings'].check_api_url()
        if api_url_check:
            raise ValidationError(api_url_check)
        try:
            self.env['connect.twiml'].sync()
            self.env['connect.domain'].sync()
            self.env['connect.number'].sync()
            self.env['connect.outgoing_callerid'].sync()
            self.env['connect.whatsapp_sender'].sync()
            self.env['connect.message_content_template'].sync()
            self.env['connect.settings'].connect_notify(
                'Twilio account synced successfully', title='Sync Complete')
        except Exception as e:
            if 'errors/20003' in str(e):
                raise ValidationError(
                    'Error authenticating requests to the Twilio API! Check your Auth Key!'
                )
            raise

    def compute_sip_uri(self, user):
        return 'sip:{}'.format(self.env.user.connect_user.uri)

    def get_external_call_route(self, number, callerId, status_url):
        call_duration_limit = int(
            self.env['connect.settings'].sudo().get_param('call_duration_limit'))
        return """
        <Response>
            <Dial callerId="{}" timeLimit="{}"><Number statusCallback='{}' statusCallbackEvent='initiated answered completed'>{}</Number></Dial>
        </Response>
        """.format(callerId, call_duration_limit, status_url, number)

    def get_balance(self):
        """Fetch current Twilio account balance."""
        try:
            client = self.get_client()
            try:
                balance_item = client.api.v2010.account.balance.fetch()
                currency = getattr(balance_item, 'currency', 'USD')
                balance_value = getattr(balance_item, 'balance', '0.00')
                balance = '${} {}'.format(balance_value, currency)
            except Exception as balance_error:
                if ('20404' in str(balance_error)
                        or 'not found' in str(balance_error).lower()):
                    balance = 'Balance API not available for this account'
                    self.sudo().balance = balance
                    self.env['connect.settings'].connect_notify(
                        'Twilio Balance: {}. The balance endpoint may not be '
                        'available for your account type or region.'.format(balance),
                        title='Balance Info',
                    )
                    return balance
                raise balance_error
            self.sudo().balance = balance
            self.env['connect.settings'].connect_notify(
                'Twilio Balance: {}'.format(balance), title='Balance Update')
            return balance
        except Exception as e:
            error_msg = 'Failed to fetch Twilio balance: {}'.format(str(e))
            self.env['connect.settings'].connect_notify(
                error_msg, title='Balance Error', warning=True)
            raise ValidationError(error_msg)

    @api.model
    def _originate_call(self, number, res_model=None, res_id=None, user=None, whatsapp_call=False, **_):
        """Twilio impl of outbound origination. Called from
        TwilioProvider._originate_call (ADR-023 façade)."""
        self.env['oduist.license'].check_license('connect', silent=False)
        number = strip_number(number)
        if len(number) > MAX_EXTEN_LEN:
            number = '+{}'.format(number)
        client = self.get_client()
        cfg = self._get().sudo()
        partner_id = False
        obj = self.env[res_model].browse(res_id) if res_model and res_id else False
        caller_name = ''
        if res_model == 'res.partner' and obj:
            partner_id = res_id
            caller_name = obj.display_name
        elif obj and hasattr(obj, 'partner_id') and obj.partner_id:
            partner_id = obj.partner_id.id
            caller_name = obj.partner_id.display_name
        elif obj and hasattr(obj, 'partner') and obj.partner:
            partner_id = obj.partner.id
            caller_name = obj.partner.display_name
        if not user:
            user = self.env.user
        if not user.connect_user:
            raise ValidationError('User does not have a SIP username defined!')
        first_flow = self.env['connect.user_callflow'].search([
            ('user', '=', user.id),
            ('callflow_type', 'in', ['client', 'sip'])
        ], order='prio', limit=1)
        if first_flow.callflow_type == 'sip':
            to = self.compute_sip_uri(user)
        else:
            to = ('client:{}?autoAnswer=yes&Partner={}&CallerName={}'.format(
                self.env.user.connect_user.uri,
                partner_id or '',
                caller_name or '',
            ))
        if 'client:' in to:
            to += '&From={}'.format((number or '').replace('+', ''))
        exten = self.env['connect.exten'].search([('number', '=', number)], limit=1)
        api_url = self.env['connect.settings'].sudo().get_param('api_url')
        edge = cfg.edge
        status_url = urljoin(api_url, 'twilio/webhook/callstatus#e={}'.format(edge))
        if exten:
            callerId = user.connect_user.exten.number
            twiml = exten.render()
        else:
            if whatsapp_call:
                pbx_user = user.connect_user
                sender = self.env['connect.whatsapp_sender'].get_default_sender(pbx_user)
                caller_number = sender.number if sender else False
                if not caller_number:
                    raise ValidationError('You must configure a WhatsApp sender!')
                callerId = 'whatsapp:{}'.format(caller_number)
                twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial callerId="{}">
        <WhatsApp statusCallback="{}" statusCallbackEvent="ringing answered completed">{}</WhatsApp>
    </Dial>
</Response>""".format(callerId, status_url, number)
            else:
                default_number = self.env['connect.outgoing_callerid'].search(
                    [('is_default', '=', True)], limit=1)
                if user.connect_user.outgoing_callerid:
                    callerId = user.connect_user.outgoing_callerid.number
                else:
                    callerId = default_number.number
                twiml = self.get_external_call_route(number, callerId, status_url)
        record = self.env.user.connect_user.record_calls
        record_status_url = urljoin(api_url, 'twilio/webhook/recordingstatus#e={}'.format(edge))
        debug(self, 'Originate destination TwiML: {}'.format(twiml))
        channel = client.calls.create(
            twiml=twiml, to=to, from_=callerId,
            status_callback=status_url, record=record,
            recording_channels='dual',
            recording_status_callback=record_status_url,
            recording_status_callback_event=['completed'],
            status_callback_event=['initiated', 'answered', 'completed'],
        )
        self.env['connect.channel'].sudo().create({
            'sid': channel.sid,
            'technical_direction': 'outbound-api',
            'caller_user': user.id,
            'caller_pbx_user': user.connect_user.id,
            'partner': partner_id,
            'called': number,
            'caller': callerId,
        })

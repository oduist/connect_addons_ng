# -*- coding: utf-8 -*-
import logging
import re
from urllib.parse import urljoin

from odoo import fields, models, api, release
from odoo.exceptions import ValidationError

from vonage import Auth, HttpClientOptions, Vonage
from vonage_application import (
    ApplicationConfig,
    ApplicationUrl,
    Capabilities,
    MessagesWebhooks,
    Rtc,
    RtcWebhooks,
    VoiceUrl,
    VoiceWebhooks,
)
from vonage_application import Messages as MessagesCapability
from vonage_application import Voice as VoiceCapability
from vonage_jwt import JwtClient

from odoo.addons.connect.models.license import ODUIST_MODULES
from odoo.addons.connect.models.settings import debug

ODUIST_MODULES.append('connect_vonage')

logger = logging.getLogger(__name__)

MAX_EXTEN_LEN = 4

VONAGE_PROTECTED_FIELDS = [
    'display_vonage_api_secret',
    'display_vonage_private_key',
    'display_vonage_signature_secret',
]

VONAGE_REGIONS = [
    ('na-east', 'North America East (Virginia)'),
    ('na-west', 'North America West (Oregon)'),
    ('eu-west', 'Europe West (Dublin)'),
    ('eu-east', 'Europe East (Frankfurt)'),
    ('apac-sng', 'Asia Pacific (Singapore)'),
    ('apac-australia', 'Asia Pacific (Sydney)'),
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


def to_vonage_number(number):
    """Vonage APIs take bare E.164 digits without the leading +."""
    if not isinstance(number, str):
        return number
    return re.sub(r'[^\d]', '', number)


def to_e164(number):
    """Normalize a webhook-supplied number to +E.164 for storage.

    Short strings (extensions, client user names) are returned as is.
    """
    if not isinstance(number, str):
        return number
    if re.match(r'^\d+$', number) and len(number) > MAX_EXTEN_LEN:
        return '+{}'.format(number)
    return number


class Settings(models.Model):
    _inherit = 'connect.settings'

    vonage_api_key = fields.Char(string='Vonage API Key')
    # Never grant the secrets below to connect.group_webhook: the webhook
    # user is the identity of all public webhook controllers, and
    # get_param() returns groups-restricted fields to group members.
    # Signature validation in the controllers reads secrets via sudo().
    vonage_api_secret = fields.Char(groups="base.group_erp_manager")
    display_vonage_api_secret = fields.Char()
    vonage_application_id = fields.Char(string='Vonage Application ID')
    vonage_private_key = fields.Text(groups="base.group_erp_manager")
    display_vonage_private_key = fields.Text()
    vonage_signature_secret = fields.Char(groups="base.group_erp_manager")
    display_vonage_signature_secret = fields.Char()
    vonage_region = fields.Selection(
        selection=VONAGE_REGIONS, string='Vonage Region')
    vonage_balance = fields.Char(readonly=True)
    vonage_auto_sync = fields.Boolean(default=True)
    vonage_verify_requests = fields.Boolean(
        default=True, string='Verify Vonage Requests')

    @api.model
    def get_client(self):
        # connect.settings is admin-only; credentials are read with sudo()
        # below, so no caller-level model access check is needed here.
        api_key = self.sudo().get_param('vonage_api_key')
        api_secret = self.sudo().get_param('vonage_api_secret')
        application_id = self.sudo().get_param('vonage_application_id')
        private_key = self.sudo().get_param('vonage_private_key')
        auth_kwargs = {}
        if api_key and api_secret:
            auth_kwargs.update({'api_key': api_key, 'api_secret': api_secret})
        if application_id and private_key:
            auth_kwargs.update({
                'application_id': application_id,
                'private_key': private_key,
            })
        if not auth_kwargs:
            raise ValidationError('Set Vonage API keys first!')
        try:
            return Vonage(Auth(**auth_kwargs), HttpClientOptions())
        except Exception as e:
            raise ValidationError(format_connect_response(e))

    @api.model
    def get_jwt_client(self):
        """JWT factory for the web phone tokens (RS256, application key)."""
        application_id = self.sudo().get_param('vonage_application_id')
        private_key = self.sudo().get_param('vonage_private_key')
        if not (application_id and private_key):
            raise ValidationError(
                'Vonage application is not configured! Run Vonage sync first.')
        return JwtClient(application_id, private_key)

    @api.model
    def get_vonage_webhook_url(self, path):
        api_url = self.sudo().get_param('api_url')
        return urljoin(api_url, 'vonage/webhook/{}'.format(path))

    def _get_application_config(self):
        voice_capability = VoiceCapability(
            webhooks=VoiceWebhooks(
                answer_url=VoiceUrl(
                    address=self.get_vonage_webhook_url('answer'),
                    http_method='POST',
                ),
                event_url=VoiceUrl(
                    address=self.get_vonage_webhook_url('event'),
                    http_method='POST',
                ),
            ),
            signed_callbacks=True,
        )
        region = self.sudo().get_param('vonage_region')
        if region:
            voice_capability.region = region
        return ApplicationConfig(
            name='Odoo Connect',
            capabilities=Capabilities(
                voice=voice_capability,
                messages=MessagesCapability(
                    webhooks=MessagesWebhooks(
                        inbound_url=ApplicationUrl(
                            address=self.get_vonage_webhook_url('message'),
                            http_method='POST',
                        ),
                        status_url=ApplicationUrl(
                            address=self.get_vonage_webhook_url(
                                'message_status'),
                            http_method='POST',
                        ),
                    ),
                    version='v1',
                ),
                rtc=Rtc(
                    webhooks=RtcWebhooks(
                        event_url=ApplicationUrl(
                            address=self.get_vonage_webhook_url('rtc'),
                            http_method='POST',
                        ),
                    ),
                    signed_callbacks=True,
                ),
            ),
        )

    def sync_vonage_application(self):
        """Create the Vonage Application or re-point its webhook URLs.

        The private key is returned by Vonage only on creation, so it is
        stored immediately in the protected settings fields.
        """
        client = self.get_client()
        config = self._get_application_config()
        application_id = self.sudo().get_param('vonage_application_id')
        if application_id:
            client.application.update_application(application_id, config)
            debug(self, 'Vonage application {} updated.'.format(
                application_id))
        else:
            app_data = client.application.create_application(config)
            private_key = getattr(app_data.keys, 'private_key', None)
            settings = self.sudo().with_context(skip_protected_fields=True)
            settings.set_param('vonage_application_id', app_data.id)
            if private_key:
                settings.set_param('vonage_private_key', private_key)
                settings.set_param(
                    'display_vonage_private_key', '*' * 16)
            debug(self, 'Vonage application {} created.'.format(app_data.id))
        return True

    def sync(self):
        if not (
            self.sudo().get_param('vonage_api_key')
            and self.sudo().get_param('vonage_api_secret')
        ):
            raise ValidationError('You must set Vonage API key and secret!')
        api_url_check = self.check_api_url()
        if api_url_check:
            raise ValidationError(api_url_check)
        try:
            self.sync_vonage_application()
            self.env['connect.user'].sync_vonage_users()
            self.env['connect.number'].sync()
            self.env['connect.outgoing_callerid'].sync()
            self.connect_notify(
                'Vonage account synced successfully', title='Sync Complete')
        except ValidationError:
            raise
        except Exception as e:
            if 'Authentication failed' in str(e) or '401' in str(e):
                raise ValidationError(
                    'Error authenticating requests to the Vonage API! '
                    'Check your API key and secret!')
            raise ValidationError(format_connect_response(e))

    def get_vonage_balance(self):
        try:
            client = self.get_client()
            balance = client.account.get_balance()
            value = '{:.2f} EUR'.format(float(balance.value))
            self.set_param('vonage_balance', value)
            self.connect_notify(
                'Vonage Balance: {}'.format(value), title='Balance Update')
            return value
        except Exception as e:
            error_msg = 'Failed to fetch Vonage balance: {}'.format(
                format_connect_response(e))
            self.connect_notify(error_msg, title='Balance Error', warning=True)
            raise ValidationError(error_msg)

    @api.model
    def vonage_create_call(self, payload):
        """POST /v1/calls with a raw payload.

        The SDK's CreateCallRequest does not model `app` endpoints in its
        `to` field, so calls to a Client SDK user are placed through the
        HTTP client directly (JWT auth, JSON body).
        """
        client = self.get_client()
        http_client = client.voice.http_client
        return http_client.post(http_client.api_host, '/v1/calls', payload)

    @api.model
    def originate_call(self, number, res_model=None, res_id=None, user=None,
                       whatsapp_call=False):
        self.env['oduist.license'].check_license('connect', silent=False)
        if whatsapp_call:
            raise ValidationError(
                'WhatsApp calls are not supported by the Vonage module!')
        number = strip_number(number)
        if len(number) > MAX_EXTEN_LEN:
            number = '+{}'.format(number)
        partner_id = False
        obj = self.env[res_model].browse(res_id) if res_model and res_id else False
        if res_model == 'res.partner' and obj:
            partner_id = res_id
        elif obj and hasattr(obj, 'partner_id') and obj.partner_id:
            partner_id = obj.partner_id.id
        elif obj and hasattr(obj, 'partner') and obj.partner:
            partner_id = obj.partner.id
        if not user:
            user = self.env.user
        if not user.connect_user:
            raise ValidationError('User does not have a PBX user defined!')
        if not user.connect_user.username:
            raise ValidationError('User does not have a username defined!')
        api_url = self.sudo().get_param('api_url')
        event_url = urljoin(api_url, 'vonage/webhook/event')
        exten = self.env['connect.exten'].search(
            [('number', '=', number)], limit=1)
        if exten:
            callerId = user.connect_user.exten.number or number
            ncco = exten.render()
        else:
            if user.connect_user.outgoing_callerid:
                callerId = user.connect_user.outgoing_callerid.number
            else:
                default_number = self.env['connect.outgoing_callerid'].search(
                    [('is_default', '=', True)], limit=1)
                callerId = default_number.number
            if not callerId:
                raise ValidationError(
                    'You must configure a default number for caller ID!')
            call_duration_limit = int(
                self.sudo().get_param('call_duration_limit'))
            ncco = []
            if user.connect_user.record_calls:
                ncco.append({
                    'action': 'record',
                    'format': 'mp3',
                    'split': 'conversation',
                    'eventUrl': [self.get_vonage_webhook_url('recording')],
                    'eventMethod': 'POST',
                })
            ncco.append({
                'action': 'connect',
                'endpoint': [{
                    'type': 'phone',
                    'number': to_vonage_number(number),
                }],
                'from': to_vonage_number(callerId),
                'limit': call_duration_limit,
                'eventUrl': [event_url],
                'eventMethod': 'POST',
            })
        payload = {
            'to': [{'type': 'app', 'user': user.connect_user.username}],
            'from': {
                'type': 'phone',
                'number': to_vonage_number(callerId or number),
            },
            'ncco': ncco,
            'event_url': [event_url],
            'event_method': 'POST',
        }
        debug(self, 'Originate NCCO: {}'.format(ncco))
        response = self.vonage_create_call(payload)
        self.env['connect.channel'].sudo().create({
            'sid': response['uuid'],
            'conversation_uuid': response.get('conversation_uuid'),
            'technical_direction': 'outbound-api',
            'caller_user': user.id,
            'caller_pbx_user': user.connect_user.id,
            'partner': partner_id,
            'called': number,
            'caller': callerId,
        })

    def write(self, vals):
        if self.env.context.get('skip_protected_fields'):
            return super(Settings, self).write(vals)
        res = super(Settings, self).write(vals)
        changed_fields = {}
        for field_name in VONAGE_PROTECTED_FIELDS:
            if vals.get(field_name):
                changed_fields.update({
                    field_name.replace('display_', ''): vals.get(field_name),
                    field_name: '*' * len(vals.get(field_name)),
                })
        if changed_fields:
            self.with_context(
                skip_protected_fields=True).sudo().write(changed_fields)
        if release.version_info[0] >= 17:
            self.env.registry.clear_cache()
        else:
            self.clear_caches()
        return res

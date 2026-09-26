# -*- coding: utf-8 -*-
import logging
import random
import re
import string
from urllib.parse import urljoin

from odoo import fields, models, api, release
from odoo.exceptions import ValidationError
if release.version_info[0] >= 19:
    from odoo.models import Constraint

from odoo.addons.connect.models.settings import debug
from .settings import MAX_EXTEN_LEN, format_connect_response
from .twiml_builder import TwiMLResponse

logger = logging.getLogger(__name__)


class User(models.Model):
    _inherit = 'connect.user'

    username = fields.Char()

    if release.version_info[0] >= 19:
        _username_uniq = Constraint('UNIQUE(username)', 'This PBX username is already defined!')
    else:
        _sql_constraints = [
            ('username_uniq', 'UNIQUE(username)', 'This PBX username is already defined!'),
        ]

    @api.constrains('username')
    def _check_username(self):
        for rec in self:
            if rec.username and not rec.username.isalnum():
                raise ValidationError('Username must be alphanumeric!')

    @api.constrains('sip_enabled', 'client_enabled', 'username', 'domain')
    def _check_voiceml_account(self):
        for rec in self:
            if (rec.sip_enabled or rec.client_enabled) and not (rec.username and rec.domain):
                raise ValidationError(
                    'Username and SIP domain are required to enable the '
                    'VoiceML SIP or web phone for user {}!'.format(rec.name))

    @api.model
    def _pbx_number_fields(self):
        return super()._pbx_number_fields() + ['voiceml_exten_number']

    originate_provider = fields.Selection(
        selection_add=[('voiceml', 'VoiceML')],
        ondelete={'voiceml': 'set null'},
    )
    message_provider = fields.Selection(
        selection_add=[('voiceml', 'VoiceML')],
        ondelete={'voiceml': 'set null'},
    )
    voiceml_exten = fields.Many2one(
        'connect.voiceml.exten', ondelete='set null', readonly=True,
        string='VoiceML Extension')
    voiceml_exten_number = fields.Char(
        related='voiceml_exten.number', store=True,
        string='VoiceML Extension Number')
    voiceml_outgoing_callerid = fields.Many2one(
        'connect.voiceml.outgoing_callerid', ondelete='set null',
        string='VoiceML Outgoing CallerID')

    sid = fields.Char('SIP Credential SID', readonly=True)
    password = fields.Char(groups="connect.group_admin,connect.group_user")
    domain = fields.Many2one(
        'connect.voiceml.domain',
        ondelete='cascade',
        default=lambda self: self._default_voiceml_domain(),
    )
    sip_enabled = fields.Boolean('SIP Phone Enabled')
    client_enabled = fields.Boolean('Web Phone Enabled')
    sip_ring_timeout = fields.Integer(required=True, default=30, string='SIP ring timeout')
    client_ring_timeout = fields.Integer(required=True, default=10, string='Web client ring timeout')
    uri = fields.Char('SIP URI', compute='_get_sip_uri')
    application = fields.Many2one('connect.voiceml.application')

    @api.model
    def _default_voiceml_domain(self):
        self.env.cr.execute(
            "SELECT 1 FROM information_schema.tables"
            " WHERE table_name = 'connect_voiceml_domain'")
        if not self.env.cr.fetchone():
            return False
        return self.env['connect.voiceml.domain'].search([], limit=1)

    @api.depends('username', 'domain')
    def _get_sip_uri(self):
        for rec in self:
            rec.uri = '{}@{}'.format(
                rec.username, rec.domain.domain_name
            ) if rec.username and rec.domain else ''

    def get_client_identity(self):
        return '{}@{}'.format(self.username, self.domain.domain_name)

    def voiceml_caller_id(self):
        self.ensure_one()
        if self.voiceml_exten and self.voiceml_exten.number:
            return self.voiceml_exten.number
        callerid = (
            self.voiceml_outgoing_callerid.number
            or self.env['connect.voiceml.outgoing_callerid']
            .sudo().search([('is_default', '=', True)], limit=1).number
        )
        return callerid or ''

    @api.model
    def get_user_by_uri(self, userinfo):
        if not userinfo:
            return super().get_user_by_uri(userinfo)
        re_call_uri = re.compile(r'^(?:sip|client):([^@]+)@')
        found_username = re_call_uri.search(userinfo)
        if found_username:
            user = self.env['connect.user'].search([
                ('username', '=', found_username.group(1))])
            if user:
                return user
        return super().get_user_by_uri(userinfo)

    # --- SIP credential provisioning (VoiceML SIP Domains/CredentialLists) ---

    @staticmethod
    def generate_password():
        password_chars = [
            random.choice(string.ascii_lowercase),
            random.choice(string.ascii_uppercase),
            random.choice(string.digits),
        ]
        password_chars += random.choices(string.ascii_letters + string.digits, k=9)
        random.shuffle(password_chars)
        return ''.join(password_chars)

    def _create_sip_account(self, username, password, client=None):
        self.ensure_one()
        try:
            client = client or self.env['connect.settings'].get_client()
            credential = (
                client.sip.credential_lists
                .credentials(self.domain.cred_list_sid)
                .create(username=username, password=password)
            )
            return credential.sid
        except Exception as e:
            raise ValidationError(format_connect_response(str(e)))

    def _update_sip_password(self, password):
        self.ensure_one()
        if not self.sid:
            return
        client = self.env['connect.settings'].get_client()
        try:
            client.sip.credential_lists.credentials(
                self.domain.cred_list_sid
            ).update(self.sid, password=password)
        except Exception as e:
            raise ValidationError(format_connect_response(str(e)))

    def delete_sip_account(self):
        self.ensure_one()
        if not self.sid:
            return
        client = self.env['connect.settings'].get_client()
        try:
            client.sip.credential_lists.credentials(
                self.domain.cred_list_sid
            ).delete(self.sid)
        except Exception:
            logger.exception('Failed to delete SIP account %s', self.username)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get('no_voiceml_create'):
            for rec in recs:
                try:
                    if rec.sip_enabled and rec.password:
                        if not self.env.context.get('skip_create_credential'):
                            rec.sid = rec._create_sip_account(
                                username=rec.username, password=rec.password)
                except Exception as e:
                    raise ValidationError(format_connect_response(str(e)))
        return recs

    def write(self, vals):
        if self.env.context.get('skip_sync'):
            return super().write(vals)
        if 'username' in vals and any(
                rec.username and rec.username != vals['username'] for rec in self):
            raise ValidationError('Username cannot be changed!')
        for rec in self:
            if vals.get('password') and self.env["connect.settings"].get_param("voiceml_auto_sync"):
                if rec.sid:
                    rec._update_sip_password(vals['password'])
                else:
                    vals['sid'] = rec._create_sip_account(rec.username, vals['password'])
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if self.env["connect.settings"].get_param("voiceml_auto_sync"):
                rec.delete_sip_account()
        return super().unlink()

    # --- Rendering (TwiML for VoiceML) ---

    def _get_caller_id(self, request, params):
        caller_user = self.env['connect.user'].get_user_by_uri(request.get('Caller'))
        return caller_user.voiceml_caller_id() if caller_user else request.get('Caller')

    def _get_caller_name(self, request, params):
        caller_user = self.env['connect.user'].get_user_by_uri(request.get('Caller'))
        return params.get('CallerName') or (caller_user.name if caller_user else '')

    def get_greeting_message(self, response):
        if self.greeting_message:
            response.say(
                self.greeting_message,
                language=self.language or 'en-US',
            )

    def render(self, request={}, params={}):
        self.ensure_one()
        response = TwiMLResponse()
        self.get_greeting_message(response)
        api_url = self.env['connect.settings'].sudo().get_param('api_url')
        status_url = urljoin(api_url, 'voiceml/webhook/callstatus')
        record_status_url = urljoin(api_url, 'voiceml/webhook/recordingstatus')
        dial_kwargs = {'timeout': self.client_ring_timeout}
        if self.record_calls:
            dial_kwargs.update({
                'recordingStatusCallback': record_status_url,
                'record': 'record-from-answer-dual',
            })
        response.dial(**dial_kwargs).sip(
            'sip:{}'.format(self.uri),
            statusCallbackEvent='initiated answered completed',
            statusCallback=status_url,
        )
        return response.to_string()

    # --- Softphone config (JsSIP against the OpenSIPS WSS edge) ---

    @api.model
    def get_phone_config(self):
        """RPC payload the browser softphone uses to register via JsSIP.

        Unlike connect_twilio (JWT VoiceGrant to the Twilio gateway), the
        VoiceML web phone is a SIP-over-WebRTC client: it registers against
        the OpenSIPS WSS edge with the SIP credentials provisioned above.
        """
        has_group = self.env.user.has_group('connect.group_user') or \
            self.env.user.has_group('connect.group_admin')
        if not has_group:
            return {'ok': False}
        user = self.search([('user', '=', self.env.user.id)])
        if not user or not user.client_enabled or not (user.username and user.domain):
            return {'ok': False}
        return {
            'ok': True,
            'username': user.username,
            'password': user.password,
            'domain': user.domain.domain_name,
            'realm': user.domain.domain_name,
            'wss_url': self.env['connect.settings'].sudo().get_param('voiceml_wss_url'),
            'uri': user.uri,
            'record_calls': bool(user.record_calls),
            'exten': user.voiceml_exten_number or '',
            'outgoing_callerid': (
                user.voiceml_outgoing_callerid.number
                or self.env['connect.voiceml.outgoing_callerid']
                .sudo().search([('is_default', '=', True)], limit=1).number
                or ''
            ),
        }

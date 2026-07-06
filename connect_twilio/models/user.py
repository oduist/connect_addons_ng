# -*- coding: utf-8 -*-
import jinja2
import logging
import random
import re
import string
from urllib.parse import urljoin

from odoo import fields, models, api, release
from odoo.exceptions import ValidationError
if release.version_info[0] >= 19:
    from odoo.models import Constraint
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.twiml.voice_response import Client, Dial, VoiceResponse

from odoo.addons.connect.models.settings import debug
from .settings import TWILIO_EDGES, strip_number, format_connect_response
from .twiml import pretty_xml

logger = logging.getLogger(__name__)

SIP_TWILIO_EDGES = TWILIO_EDGES.copy()
SIP_TWILIO_EDGES.insert(0, ['roaming', 'Global Low-latency Roaming'])


class User(models.Model):
    _inherit = 'connect.user'

    # Not field-level required: with several telephony modules installed a
    # user may have no Twilio account at all. Username/domain become
    # mandatory only when a Twilio phone (SIP or web client) is enabled.
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
    def _check_twilio_account(self):
        for rec in self:
            if (rec.sip_enabled or rec.client_enabled) and not (rec.username and rec.domain):
                raise ValidationError(
                    'Username and SIP domain are required to enable the '
                    'Twilio SIP or web phone for user {}!'.format(rec.name))

    @api.model
    def _twilio_is_only_provider(self):
        """True when connect_twilio is the only telephony module installed."""
        other = self.env['ir.module.module'].sudo().search_count([
            ('name', 'in', ['connect_freeswitch', 'connect_asterisk']),
            ('state', '=', 'installed'),
        ])
        return not other

    @api.model
    def _pbx_number_fields(self):
        return super()._pbx_number_fields() + ['twilio_exten_number']

    originate_provider = fields.Selection(
        selection_add=[('twilio', 'Twilio')],
        ondelete={'twilio': 'set null'},
    )
    twilio_exten = fields.Many2one('connect.twilio.exten', ondelete='set null', readonly=True, string='Twilio Extension')
    twilio_exten_number = fields.Char(
        related='twilio_exten.number', store=True,
        string='Twilio Extension Number')
    twilio_outgoing_callerid = fields.Many2one(
        'connect.twilio.outgoing_callerid', ondelete='set null',
        string='Twilio Outgoing CallerID')

    def create_twilio_extension(self):
        self.ensure_one()
        return self.env['connect.twilio.exten'].create_extension(
            self, 'connect.user', current_exten=self.twilio_exten)

    @api.model
    def get_user_by_uri(self, userinfo):
        """Lookup connect.user by SIP/client URI using username."""
        if not userinfo:
            return self.env['connect.user']
        re_call_uri = re.compile(r'^(?:sip|client):([^@]+)@')
        found_username = re_call_uri.search(userinfo)
        if found_username:
            user = self.env['connect.user'].search([
                ('username', '=', found_username.group(1))])
            if user:
                debug(self, 'Found user: {} by {}.'.format(user.name, userinfo))
            return user
        return self.env['connect.user']

    sid = fields.Char('SID', readonly=True)
    password = fields.Char(
        groups="connect.group_admin,connect.group_user"
    )
    domain = fields.Many2one(
        'connect.twilio.domain',
        ondelete='cascade',
        default=lambda self: self._default_twilio_domain(),
    )

    @api.model
    def _default_twilio_domain(self):
        # During module installation on a database with existing
        # connect.user rows the new column is initialized before the
        # domain table exists — return no default in that case.
        self.env.cr.execute(
            "SELECT 1 FROM information_schema.tables"
            " WHERE table_name = 'connect_twilio_domain'")
        if not self.env.cr.fetchone():
            return False
        return self.env['connect.twilio.domain'].search(
            [('subdomain', 'not like', 'byoc')], limit=1)
    sip_enabled = fields.Boolean('SIP Phone Enabled')
    sip_priority = fields.Selection(
        [('1', '1'), ('2', '2')], required=True, default='2'
    )
    # Enabled out of the box only when Twilio is the sole telephony module;
    # in multi-provider databases the admin enables the Twilio web phone
    # explicitly per user.
    client_enabled = fields.Boolean(
        'Web Phone Enabled',
        default=lambda self: self._twilio_is_only_provider())
    client_priority = fields.Selection(
        [('1', '1'), ('2', '2')], required=True, default='1'
    )
    sip_ring_timeout = fields.Integer(
        required=True, default=30, string='SIP ring timeout'
    )
    client_ring_timeout = fields.Integer(
        required=True, default=10, string='Web client ring timeout'
    )
    uri = fields.Char('SIP URI', compute='_get_sip_uri')
    connect_uri = fields.Char(
        'SIP Connect URI', compute='_get_sip_uri'
    )
    application = fields.Many2one('connect.twilio.twiml')
    whatsapp_sender_id = fields.Many2one(
        'connect.whatsapp_sender',
        string='WhatsApp Sender',
        ondelete='set null',
    )
    twilio_edge = fields.Selection(
        selection=SIP_TWILIO_EDGES,
        required=True,
        default='roaming',
    )

    @api.depends('username', 'domain', 'twilio_edge')
    def _get_sip_uri(self):
        settings = self.env['connect.settings']
        default_edge = settings.get_param('twilio_edge') or 'roaming'
        for rec in self:
            edge = rec.twilio_edge or default_edge
            rec.uri = '{}@{}'.format(
                rec.username, rec.domain.domain_name
            )
            if edge == 'roaming':
                rec.connect_uri = '{}@{}'.format(
                    rec.username, rec.domain.domain_name
                )
            else:
                rec.connect_uri = '{}@{}.sip.{}.twilio.com'.format(
                    rec.username, rec.domain.subdomain, edge
                )

    def _create_sip_account(self, username, password, client=None):
        self.ensure_one()
        try:
            client = client or self.env['connect.settings'].get_client()
            credential = (
                client.sip.credential_lists(
                    self.domain.cred_list_sid
                )
                .credentials.create(
                    username=username, password=password
                )
            )
            if not credential:
                raise ValidationError('Cannot create a SIP user!')
            return credential.sid
        except Exception as e:
            if 'A strong password is required' in str(e):
                msg = (
                    'A strong password is required. It must have a minimum '
                    'length of 12, at least one number, uppercase char and '
                    'lowercase character.'
                )
                raise ValidationError(msg)
            elif 'already exists' in str(e):
                debug(
                    self,
                    'SIP credential {} already exists in Twilio - importing existing SID'.format(
                        username
                    ),
                )
                return self._import_existing_sip_credential(
                    username, client
                )
            else:
                raise ValidationError(format_connect_response(e))

    def _import_existing_sip_credential(self, username, client=None):
        """Import existing SIP credential from Twilio by username."""
        self.ensure_one()
        client = client or self.env['connect.settings'].get_client()
        try:
            credentials = (
                client.sip.credential_lists(
                    self.domain.cred_list_sid
                )
                .credentials.list()
            )
            matching_credential = None
            for credential in credentials:
                if credential.username == username:
                    matching_credential = credential
                    break
            if matching_credential:
                debug(
                    self,
                    'Found existing SIP credential for {} with SID {}'.format(
                        username, matching_credential.sid
                    ),
                )
                return matching_credential.sid
            else:
                debug(
                    self,
                    'Could not find existing credential for {} in credential list'.format(
                        username
                    ),
                    level='error',
                )
                raise ValidationError(
                    'SIP credential "{}" already exists but could not be found in credential list'.format(
                        username
                    )
                )
        except Exception as e:
            debug(
                self,
                'Error importing existing SIP credential for {}: {}'.format(
                    username, str(e)
                ),
                level='error',
            )
            raise ValidationError(
                'Failed to import existing SIP credential for "{}": {}'.format(
                    username, format_connect_response(e)
                )
            )

    def _update_sip_password(self, password):
        self.ensure_one()
        if not self.sid:
            logger.warning(
                'SIP account %s SID not set, not updating.', self.id
            )
            return
        try:
            client = self.env['connect.settings'].get_client()
            client.sip.credential_lists(
                self.domain.cred_list_sid
            ).credentials(self.sid).update(password=password)
        except Exception as e:
            if 'A strong password is required.' in str(e):
                msg = (
                    'A strong password is required. It must have a minimum '
                    'length of 12, at least one number, uppercase char and '
                    'lowercase character.'
                )
                raise ValidationError(msg)
            elif 'not found' in str(e):
                debug(
                    self,
                    'SIP cred {} SID {} not found in Twilio'.format(
                        self.username, self.sid
                    ),
                )
                self._create_sip_account(self.username, password)
            else:
                raise ValidationError(format_connect_response(e))

    def delete_sip_account(self):
        self.ensure_one()
        if not self.sid:
            logger.warning(
                'Attempt to delete SIP account %s (%s) without SID!',
                self.id,
                self.name,
            )
            return
        try:
            client = self.env['connect.settings'].get_client()
            client.sip.credential_lists(
                self.domain.cred_list_sid
            ).credentials(self.sid).delete()
            debug(
                self,
                'Deleted SIP account {}.'.format(self.username),
            )
            return True
        except Exception as e:
            if 'not found' in str(e):
                logger.warning(
                    'SIP account %s was not present in Twilio.',
                    self.username,
                )
            else:
                raise ValidationError(format_connect_response(e))

    @staticmethod
    def generate_twilio_password():
        """Generate a strong password for Twilio SIP credentials."""
        password_chars = [
            random.choice(string.ascii_lowercase),
            random.choice(string.ascii_uppercase),
            random.choice(string.digits),
        ]
        all_chars = string.ascii_letters + string.digits
        password_chars += random.choices(
            all_chars, k=12 - len(password_chars)
        )
        random.shuffle(password_chars)
        return ''.join(password_chars)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get('no_twilio_create'):
            for rec in recs:
                try:
                    if rec.sip_enabled and rec.password:
                        if not self.env.context.get(
                            'skip_create_credential'
                        ):
                            rec.sid = rec._create_sip_account(
                                username=rec.username,
                                password=rec.password,
                            )
                        rec.with_context(
                            skip_sync=True
                        ).password = '*' * len(rec.password)
                except Exception as e:
                    if 'A strong password is required' in str(e):
                        msg = (
                            'A strong password is required. It must have a '
                            'minimum length of 12, at least one number, '
                            'uppercase char and lowercase character.'
                        )
                        raise ValidationError(msg)
                    else:
                        raise ValidationError(
                            format_connect_response(e)
                        )
        return recs

    def write(self, vals):
        if self.env.context.get('skip_sync'):
            res = super().write(vals)
            return res
        if 'username' in vals and any(
                rec.username and rec.username != vals['username'] for rec in self):
            raise ValidationError('Username cannot be changed!')
        for rec in self:
            if vals.get('password'):
                if not self.env["connect.settings"].get_param(
                    "twilio_auto_sync"
                ):
                    vals['password'] = '*' * len(vals['password'])
                else:
                    if rec.sid:
                        rec._update_sip_password(vals['password'])
                    else:
                        vals['sid'] = self._create_sip_account(
                            rec.username, vals['password']
                        )
                    vals['password'] = '*' * len(vals['password'])
        res = super().write(vals)
        return res

    def unlink(self):
        for rec in self:
            if self.env["connect.settings"].get_param(
                "twilio_auto_sync"
            ):
                rec.delete_sip_account()
        return super(User, self).unlink()

    def render_client(self, response, request, params):
        caller_name = self._get_caller_name(request, params)
        callerId = self._get_caller_id(request, params)
        api_url = (
            self.env['connect.settings']
            .sudo()
            .get_param('api_url')
        )
        edge = (
            self.env['connect.settings']
            .sudo()
            .get_param('twilio_edge')
        )
        record_status_url = urljoin(
            api_url,
            'twilio/webhook/recordingstatus#e={}'.format(edge),
        )
        status_url = urljoin(
            api_url,
            'twilio/webhook/callstatus#e={}'.format(edge),
        )
        dial_action_url = urljoin(
            api_url,
            'twilio/webhook/connect.user/call_action/{}#e={}'.format(
                self.id, edge
            ),
        )
        dial_client_kwargs = {
            'timeout': self.client_ring_timeout,
            'callerId': callerId,
        }
        if params.get('dial_action_url'):
            dial_client_kwargs['action'] = params['dial_action_url']
        else:
            dial_client_kwargs['action'] = dial_action_url
        if self.record_calls:
            dial_client_kwargs.update(
                {
                    'record': 'record-from-answer',
                    'recordingStatusCallback': record_status_url,
                }
            )
        dial_client = Dial(**dial_client_kwargs)
        client = Client(
            statusCallbackEvent='initiated answered completed',
            statusCallback=status_url,
        )
        client.identity(self.get_client_identity())
        if caller_name:
            client.parameter(name='CallerName', value=caller_name)
        channel = self.env['connect.channel'].search(
            [('sid', '=', request.get('CallSid'))]
        )
        call = channel.call
        if call and call.partner:
            partner_id = call.partner.id
            if not caller_name:
                client.parameter(
                    name="CallerName", value=call.partner.name
                )
        elif channel and channel.caller_user:
            partner_id = channel.caller_user.partner_id.id
            if not caller_name:
                client.parameter(
                    name="CallerName",
                    value=channel.caller_user.partner_id.name,
                )
        else:
            partner_id = False
        client.parameter(name='Partner', value=partner_id)
        dial_client.append(client)
        response.append(dial_client)

    def render_sip(self, response, request, params):
        callerId = self._get_caller_id(request, params)
        api_url = (
            self.env['connect.settings']
            .sudo()
            .get_param('api_url')
        )
        edge = self.env['connect.settings'].get_param('twilio_edge')
        dial_action_url = urljoin(
            api_url,
            'twilio/webhook/connect.user/call_action/{}#e={}'.format(
                self.id, edge
            ),
        )
        record_status_url = urljoin(
            api_url,
            'twilio/webhook/recordingstatus#e={}'.format(edge),
        )
        status_url = urljoin(
            api_url,
            'twilio/webhook/callstatus#e={}'.format(edge),
        )
        dial_sip_kwargs = {
            'timeout': self.sip_ring_timeout,
            'callerId': callerId,
        }
        if params.get('dial_action_url'):
            dial_sip_kwargs['action'] = params['dial_action_url']
        else:
            dial_sip_kwargs['action'] = dial_action_url
        if self.record_calls:
            dial_sip_kwargs.update(
                {
                    'recordingStatusCallback': record_status_url,
                    'record': 'record-from-answer-dual',
                }
            )
        dial_sip = Dial(**dial_sip_kwargs)
        dial_sip.sip(
            'sip:{}'.format(self.uri),
            statusCallbackEvent='initiated answered completed',
            statusCallback=status_url,
        )
        response.append(dial_sip)

    def render_voicemail_prompt(self):
        self.ensure_one()
        environment = jinja2.Environment()
        template = environment.from_string(self.voicemail_prompt)
        return template.render({'user': self})

    def get_greeting_message(self, response):
        self.ensure_one()
        response.say(self.greeting_message)

    def get_voicemail_prompt(self, response):
        self.ensure_one()
        voicemail_prompt = self.render_voicemail_prompt()
        response.say(voicemail_prompt)

    def render_voicemail(self, response, request, params):
        api_url = (
            self.env['connect.settings']
            .sudo()
            .get_param('api_url')
        )
        edge = (
            self.env['connect.settings']
            .sudo()
            .get_param('twilio_edge')
        )
        voicemail_record_status_url = urljoin(
            api_url,
            'twilio/webhook/vm_recordingstatus#e={}'.format(edge),
        )
        self.get_voicemail_prompt(response)
        response.record(
            maxLength=120,
            finishOnKey='#',
            playBeep=True,
            recordingStatusCallback=voicemail_record_status_url,
        )

    def render(self, request={}, params={}):
        self.ensure_one()
        channel = self.env['connect.channel'].search(
            [('sid', '=', request.get('CallSid'))], order='id desc'
        )
        call = channel.call
        response = VoiceResponse()
        if call:
            done_callflow_ids = (
                self.env['connect.twilio.user_callflow_call']
                .sudo()
                .search([('call', '=', call.id)])
                .mapped('callflow')
                .mapped('id')
            )
            if not done_callflow_ids and self.greeting_message:
                self.get_greeting_message(response)
            next_call_flow = (
                self.env['connect.twilio.user_callflow']
                .sudo()
                .search(
                    [
                        ('user', '=', self.id),
                        ('id', 'not in', done_callflow_ids),
                    ],
                    order='prio',
                    limit=1,
                )
            )
            if next_call_flow:
                self.env['connect.twilio.user_callflow_call'].sudo().create(
                    {
                        'call': call.id,
                        'callflow': next_call_flow.id,
                    }
                )
                getattr(self, next_call_flow.method)(
                    response, request, params
                )
                debug(self, pretty_xml(response.to_xml()))
                return response.to_xml()
            else:
                callflows = (
                    self.env['connect.twilio.user_callflow_call']
                    .sudo()
                    .search([('call', '=', call.id)])
                )
                callflows.sudo().unlink()
                response.hangup()
                return response.to_xml()
        else:
            all_flows = (
                self.env['connect.twilio.user_callflow']
                .sudo()
                .search(
                    [('user', '=', self.id)], order='prio'
                )
            )
            for flow in all_flows:
                getattr(self, flow.method)(response, request, params)
            return response.to_xml()

    def get_client_identity(self):
        return '{}@{}'.format(
            self.username, self.domain.domain_name
        )

    @api.model
    def get_client_token(self):
        try:
            has_user_group = self.env.user.has_group(
                'connect.group_user'
            )
            has_admin_group = self.env.user.has_group(
                'connect.group_admin'
            )
            if not (has_user_group or has_admin_group):
                return {'token': False}
            user = self.search(
                [('user', '=', self.env.user.id)]
            )
            if not user:
                logger.info(
                    "User %s not found!", self.env.user.id
                )
                return {'token': False}
            if not user.client_enabled:
                logger.info(
                    "Client for user %s not enabled!",
                    self.env.user.id,
                )
                return {'token': False}
            if not (user.username and user.domain):
                logger.info(
                    "Twilio username/domain not set for user %s!",
                    self.env.user.id,
                )
                return {'token': False}
            account_sid = (
                self.env['connect.settings']
                .sudo()
                .get_param('account_sid')
            )
            api_key = (
                self.env['connect.settings']
                .sudo()
                .get_param('twilio_api_key')
            )
            api_secret = (
                self.env['connect.settings']
                .sudo()
                .get_param('twilio_api_secret')
            )
            identity = user.get_client_identity()
            token = AccessToken(
                account_sid,
                api_key,
                api_secret,
                identity=identity,
                ttl=3600,
                region=self.env['connect.settings']
                .sudo()
                .get_param('twilio_region'),
            )
            voice_grant = VoiceGrant(
                outgoing_application_sid=(
                    user.application.sid
                    or user.domain.application.sid
                ),
                outgoing_application_params={},
                incoming_allow=True,
            )
            token.add_grant(voice_grant)
            return {
                'token': token.to_jwt(),
                'edge': (
                    user.twilio_edge
                    or self.env['connect.settings']
                    .sudo()
                    .get_param('twilio_edge')
                ),
            }
        except Exception as e:
            logger.exception('Error getting Twilio JWT:')
            return {'error': str(e)}

    def _get_caller_id(self, request, params):
        caller_user = self.env['connect.user'].get_user_by_uri(
            request.get('Caller')
        )
        if caller_user:
            callerId = caller_user.twilio_exten.number or ''
            if not callerId:
                logger.warning(
                    'Exten not set for user %s', caller_user.name
                )
        else:
            callerId = request.get('Caller')
        return callerId

    def _get_caller_name(self, request, params):
        caller_user = self.env['connect.user'].get_user_by_uri(
            request.get('Caller')
        )
        caller_name = params.get('CallerName', False)
        if caller_user:
            caller_name = caller_user.name
        return caller_name

    @api.constrains('sip_enabled', 'sip_priority')
    def _manage_sip_callflow(self):
        if self.sip_enabled:
            self._manage_channel_callflow('sip', True)
        else:
            self._manage_channel_callflow('sip', False)

    @api.constrains('client_enabled', 'client_priority')
    def _manage_client_callflow(self):
        if self.client_enabled:
            self._manage_channel_callflow('client', True)
        else:
            self._manage_channel_callflow('client', False)

    @api.constrains('voicemail_enabled')
    def _manage_voicemail_enabled(self):
        if self.voicemail_enabled:
            if not self.env['connect.twilio.user_callflow'].search(
                    [('user', '=', self.id),
                     ('callflow_type', '=', 'voicemail')]):
                self.env['connect.twilio.user_callflow'].create({
                    'user': self.id,
                    'prio': 10,
                    'callflow_type': 'voicemail',
                    'method': 'render_voicemail'
                })
        else:
            self.env['connect.twilio.user_callflow'].search(
                [('user', '=', self.id),
                 ('callflow_type', '=', 'voicemail')]).unlink()

    def _manage_channel_callflow(self, channel, enable):
        if enable:
            callflow = self.env['connect.twilio.user_callflow'].search(
                [
                    ('user', '=', self.id),
                    ('callflow_type', '=', channel),
                ]
            )
            if not callflow:
                self.env['connect.twilio.user_callflow'].create(
                    {
                        'user': self.id,
                        'callflow_type': channel,
                        'prio': int(
                            getattr(
                                self, '{}_priority'.format(channel)
                            )
                        ),
                        'method': 'render_{}'.format(channel),
                    }
                )
            else:
                callflow.prio = getattr(
                    self, '{}_priority'.format(channel)
                )
        else:
            self.env['connect.twilio.user_callflow'].search(
                [
                    ('user', '=', self.id),
                    ('callflow_type', '=', channel),
                ]
            ).unlink()

    @api.onchange('domain')
    def _restrict_sip_domain_change(self):
        if self.sip_enabled and self.sid:
            raise ValidationError(
                'You cannot change SIP domain for existing SIP account! '
                'Disable SIP account first!'
            )

    @api.onchange('sip_enabled')
    def _make_blank_password(self):
        if self.sip_enabled:
            self.password = ''

    @api.model
    def on_call_action(self, record_id, request):
        user = self.browse(record_id)
        call_status = request.get('CallStatus')
        if not call_status:
            call_status = request.get('DialCallStatus')
        if call_status != 'completed':
            dialplan = user.render(request)
            return dialplan
        else:
            response = VoiceResponse()
            response.hangup()
            return response.to_xml()

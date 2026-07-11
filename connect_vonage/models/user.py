# -*- coding: utf-8 -*-
import json
import logging
import re
import time

import jinja2

from odoo import fields, models, api, release
from odoo.exceptions import ValidationError
if release.version_info[0] >= 19:
    from odoo.models import Constraint

from vonage_users import ListUsersFilter
from vonage_users import User as VonageUser

from odoo.addons.connect.models.settings import debug
from .settings import format_connect_response, to_e164, to_vonage_number
from .channel import VONAGE_FAIL_STATUSES

logger = logging.getLogger(__name__)

# Standard ACL paths for a Vonage Client SDK session token.
CLIENT_ACL_PATHS = {
    '/*/users/**': {},
    '/*/conversations/**': {},
    '/*/sessions/**': {},
    '/*/devices/**': {},
    '/*/image/**': {},
    '/*/media/**': {},
    '/*/applications/**': {},
    '/*/push/**': {},
    '/*/knocking/**': {},
    '/*/legs/**': {},
}


class User(models.Model):
    _inherit = 'connect.user'

    username = fields.Char(required=True)
    vonage_user_id = fields.Char('Vonage User ID', readonly=True)
    client_enabled = fields.Boolean('Web Phone Enabled', default=True)
    client_ring_timeout = fields.Integer(
        required=True, default=30, string='Web client ring timeout')

    if release.version_info[0] >= 19:
        _username_uniq = Constraint(
            'UNIQUE(username)', 'This PBX username is already defined!')
    else:
        _sql_constraints = [
            ('username_uniq', 'UNIQUE(username)',
             'This PBX username is already defined!'),
        ]

    @api.constrains('username')
    def _check_username(self):
        for rec in self:
            if rec.username and not rec.username.isalnum():
                raise ValidationError('Username must be alphanumeric!')

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

    # ------------------------------------------------------------------
    # Vonage Users API lifecycle
    # ------------------------------------------------------------------

    def _find_vonage_user_id(self, client):
        self.ensure_one()
        users, _ = client.users.list_users(
            ListUsersFilter(name=self.username))
        for user in users:
            if user.name == self.username:
                return user.id
        return False

    def _create_vonage_user(self, client=None):
        self.ensure_one()
        client = client or self.env['connect.settings'].get_client()
        try:
            vonage_user = client.users.create_user(VonageUser(
                name=self.username,
                display_name=self.name or self.username,
            ))
            self.vonage_user_id = vonage_user.id
            debug(self, 'Created Vonage user {}.'.format(self.username))
        except Exception as e:
            if 'already exists' in str(e).lower() or 'unique' in str(e).lower():
                existing_id = self._find_vonage_user_id(client)
                if existing_id:
                    debug(self, 'Imported existing Vonage user {}.'.format(
                        self.username))
                    self.vonage_user_id = existing_id
                    return
            raise ValidationError(format_connect_response(e))

    def delete_vonage_user(self):
        self.ensure_one()
        if not self.vonage_user_id:
            return
        try:
            client = self.env['connect.settings'].get_client()
            client.users.delete_user(self.vonage_user_id)
            debug(self, 'Deleted Vonage user {}.'.format(self.username))
        except Exception as e:
            if 'not found' in str(e).lower():
                logger.warning(
                    'Vonage user %s was not present in Vonage.', self.username)
            else:
                raise ValidationError(format_connect_response(e))

    @api.model
    def sync_vonage_users(self):
        client = self.env['connect.settings'].get_client()
        for rec in self.search([('vonage_user_id', '=', False)]):
            if rec.username:
                rec._create_vonage_user(client)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get('no_vonage_create'):
            auto_sync = self.env['connect.settings'].sudo().get_param(
                'vonage_auto_sync')
            if auto_sync:
                for rec in recs:
                    rec._create_vonage_user()
        return recs

    def write(self, vals):
        if self.env.context.get('skip_sync'):
            return super().write(vals)
        if 'username' in vals:
            for rec in self:
                if rec.username and rec.username != vals['username']:
                    raise ValidationError('Username cannot be changed!')
        return super().write(vals)

    def unlink(self):
        auto_sync = self.env['connect.settings'].sudo().get_param(
            'vonage_auto_sync')
        for rec in self:
            if auto_sync:
                rec.delete_vonage_user()
        return super(User, self).unlink()

    # ------------------------------------------------------------------
    # NCCO rendering (user callflow engine)
    # ------------------------------------------------------------------

    def _resolve_call(self, request):
        """Find the connect.call for an answer/event payload."""
        channel = self.env['connect.channel'].sudo().search(
            [('sid', '=', request.get('uuid'))], order='id desc', limit=1)
        call = channel.call
        if not call and request.get('conversation_uuid'):
            first_channel = self.env['connect.channel'].sudo().search(
                [('conversation_uuid', '=', request.get('conversation_uuid'))],
                order='id asc', limit=1)
            call = first_channel.call
        return call

    def _get_caller_id(self, request, params):
        """CallerId for the connect action: an extension for internal
        calls, otherwise the external caller number (bare digits)."""
        caller_uri = self.env['connect.channel']._vonage_endpoint_to_uri(
            request.get('from'))
        caller_user = self.env['connect.user'].get_user_by_uri(caller_uri)
        if caller_user:
            callerId = caller_user.exten.number or ''
            if not callerId:
                logger.warning('Exten not set for user %s', caller_user.name)
        else:
            callerId = caller_uri
        # Vonage requires a phone number in the connect `from` field. Fall
        # back to the default outgoing callerid for internal callers
        # without a usable number.
        digits = to_vonage_number(callerId or '')
        if not digits or len(digits) <= 4:
            default_number = self.env['connect.outgoing_callerid'].sudo().search(
                [('is_default', '=', True)], limit=1)
            if default_number:
                digits = to_vonage_number(default_number.number)
        return digits

    def _make_record_action(self):
        return {
            'action': 'record',
            'format': 'mp3',
            'split': 'conversation',
            'eventUrl': [self.env['connect.settings'].get_vonage_webhook_url(
                'recording')],
            'eventMethod': 'POST',
        }

    def render_client(self, ncco, request, params):
        callerId = self._get_caller_id(request, params)
        call_action_url = self.env['connect.settings'].get_vonage_webhook_url(
            'connect.user/call_action/{}'.format(self.id))
        if self.record_calls:
            ncco.append(self._make_record_action())
        connect_action = {
            'action': 'connect',
            'endpoint': [{'type': 'app', 'user': self.username}],
            'timeout': self.client_ring_timeout,
            'eventType': 'synchronous',
            'eventUrl': [params.get('call_action_url') or call_action_url],
            'eventMethod': 'POST',
        }
        if callerId:
            connect_action['from'] = callerId
        else:
            connect_action['randomFromNumber'] = True
        ncco.append(connect_action)

    def render_voicemail_prompt(self):
        self.ensure_one()
        environment = jinja2.Environment()
        template = environment.from_string(self.voicemail_prompt)
        return template.render({'user': self})

    def get_greeting_message(self, ncco):
        self.ensure_one()
        ncco.append({'action': 'talk', 'text': self.greeting_message})

    def get_voicemail_prompt(self, ncco):
        self.ensure_one()
        ncco.append({'action': 'talk', 'text': self.render_voicemail_prompt()})

    def render_voicemail(self, ncco, request, params):
        vm_recording_url = self.env['connect.settings'].get_vonage_webhook_url(
            'vm_recording')
        self.get_voicemail_prompt(ncco)
        ncco.append({
            'action': 'record',
            'format': 'mp3',
            'endOnKey': '#',
            'beepStart': True,
            'timeOut': 120,
            'eventUrl': [vm_recording_url],
            'eventMethod': 'POST',
        })

    def render(self, request={}, params={}):
        """Render the next user callflow step as an NCCO list."""
        self.ensure_one()
        request = dict(request or {})
        params = dict(params or {})
        call = self._resolve_call(request)
        ncco = []
        if call:
            done_callflow_ids = (
                self.env['connect.user_callflow_call'].sudo()
                .search([('call', '=', call.id)])
                .mapped('callflow').mapped('id'))
            if not done_callflow_ids and self.greeting_message:
                self.get_greeting_message(ncco)
            next_call_flow = self.env['connect.user_callflow'].sudo().search(
                [('user', '=', self.id), ('id', 'not in', done_callflow_ids)],
                order='prio', limit=1)
            if next_call_flow:
                self.env['connect.user_callflow_call'].sudo().create({
                    'call': call.id,
                    'callflow': next_call_flow.id,
                })
                getattr(self, next_call_flow.method)(ncco, request, params)
                debug(self, json.dumps(ncco, indent=2))
                return ncco
            else:
                self.env['connect.user_callflow_call'].sudo().search(
                    [('call', '=', call.id)]).unlink()
                # An empty NCCO terminates the call.
                return []
        else:
            all_flows = self.env['connect.user_callflow'].sudo().search(
                [('user', '=', self.id)], order='prio')
            for flow in all_flows:
                getattr(self, flow.method)(ncco, request, params)
            return ncco

    def get_client_identity(self):
        return self.username

    @api.model
    def get_client_token(self):
        """Web phone bootstrap: mint a Client SDK JWT for the current user.

        Returns the dict consumed by static/src/js/main.js; {'token': False}
        disables the widget, {'error': ...} surfaces a startup problem.
        """
        try:
            has_user_group = self.env.user.has_group('connect.group_user')
            has_admin_group = self.env.user.has_group('connect.group_admin')
            if not (has_user_group or has_admin_group):
                return {'token': False}
            user = self.search([('user', '=', self.env.user.id)])
            if not user:
                logger.info('User %s not found!', self.env.user.id)
                return {'token': False}
            if not user.client_enabled:
                logger.info(
                    'Client for user %s not enabled!', self.env.user.id)
                return {'token': False}
            ttl = 3600
            jwt_client = self.env['connect.settings'].get_jwt_client()
            token = jwt_client.generate_application_jwt({
                'sub': user.username,
                'exp': int(time.time()) + ttl,
                'acl': {'paths': CLIENT_ACL_PATHS},
            })
            if isinstance(token, bytes):
                token = token.decode('utf-8')
            return {
                'token': token,
                'ttl': ttl,
                'username': user.username,
            }
        except Exception as e:
            logger.exception('Error getting Vonage JWT:')
            return {'error': str(e)}

    @api.constrains('client_enabled')
    def _manage_client_callflow(self):
        self._manage_channel_callflow('client', self.client_enabled)

    @api.constrains('voicemail_enabled')
    def _manage_voicemail_enabled(self):
        if self.voicemail_enabled:
            if not self.env['connect.user_callflow'].search(
                    [('user', '=', self.id),
                     ('callflow_type', '=', 'voicemail')]):
                self.env['connect.user_callflow'].create({
                    'user': self.id,
                    'prio': 10,
                    'callflow_type': 'voicemail',
                    'method': 'render_voicemail',
                })
        else:
            self.env['connect.user_callflow'].search(
                [('user', '=', self.id),
                 ('callflow_type', '=', 'voicemail')]).unlink()

    def _manage_channel_callflow(self, channel, enable):
        if enable:
            callflow = self.env['connect.user_callflow'].search(
                [('user', '=', self.id), ('callflow_type', '=', channel)])
            if not callflow:
                self.env['connect.user_callflow'].create({
                    'user': self.id,
                    'callflow_type': channel,
                    'prio': 1,
                    'method': 'render_{}'.format(channel),
                })
        else:
            self.env['connect.user_callflow'].search(
                [('user', '=', self.id),
                 ('callflow_type', '=', channel)]).unlink()

    @api.model
    def on_client_call(self, params):
        """Answer webhook for a call placed from the Client SDK web phone.

        Builds the outbound NCCO (optional record + connect to the dialed
        number) and pre-creates the client leg channel so the call gets
        the outbound-api direction.
        """
        if not self.env['oduist.license'].check_license('connect', silent=True):
            return [{'action': 'talk', 'text': 'Service unavailable.'}]
        user = self.sudo().search(
            [('username', '=', params.get('from_user'))], limit=1)
        if not user:
            logger.error('Unknown client user %s!', params.get('from_user'))
            return [{'action': 'talk', 'text': 'Unknown user. Goodbye!'}]
        custom_data = params.get('custom_data') or {}
        number = custom_data.get('to') or params.get('to')
        if not number:
            return [{'action': 'talk', 'text': 'No destination. Goodbye!'}]
        number = to_e164(str(number))
        # Pre-create the client leg channel.
        self.env['connect.channel'].sudo().create({
            'sid': params.get('uuid'),
            'conversation_uuid': params.get('conversation_uuid'),
            'technical_direction': 'outbound-api',
            'caller_user': user.user.id,
            'caller_pbx_user': user.id,
            'caller': 'client:{}@vonage'.format(user.username),
            'called': number,
        })
        exten = self.env['connect.exten'].sudo().search(
            [('number', '=', number)], limit=1)
        if exten:
            return exten.render(request=params)
        if user.outgoing_callerid:
            callerId = user.outgoing_callerid.number
        else:
            default_number = self.env['connect.outgoing_callerid'].sudo().search(
                [('is_default', '=', True)], limit=1)
            callerId = default_number.number
        if not callerId:
            return [{'action': 'talk',
                     'text': 'You must configure a default number for '
                             'caller ID!'}]
        settings = self.env['connect.settings']
        call_duration_limit = int(
            settings.sudo().get_param('call_duration_limit'))
        ncco = []
        if user.record_calls:
            ncco.append(user._make_record_action())
        ncco.append({
            'action': 'connect',
            'endpoint': [{
                'type': 'phone',
                'number': to_vonage_number(number),
            }],
            'from': to_vonage_number(callerId),
            'limit': call_duration_limit,
            'eventUrl': [settings.get_vonage_webhook_url('event')],
            'eventMethod': 'POST',
        })
        return ncco

    @api.model
    def on_call_action(self, record_id, request):
        """Synchronous connect event handler (the Twilio Dial action analog).

        Failure statuses return the next callflow step's NCCO; any other
        event returns None so the controller replies with an empty body
        and the call continues normally.
        """
        user = self.browse(record_id)
        # Record the connect leg state: its events are delivered here
        # instead of the application event_url.
        self.env['connect.call'].on_voice_event(request)
        if request.get('status') in VONAGE_FAIL_STATUSES:
            return user.render(request)
        return None

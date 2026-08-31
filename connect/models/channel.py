import logging
import re
from odoo import fields, models, api, release
from odoo.exceptions import AccessError, UserError
from .settings import debug

logger = logging.getLogger(__name__)

CALL_END_STATUSES = ('completed', 'busy', 'failed', 'no-answer', 'canceled')


class Channel(models.Model):
    _name = 'connect.channel'
    _description = 'Channel'
    _inherit = 'mail.thread'
    _rec_name = 'id'
    _order = 'id desc'

    sid = fields.Char('SID', readonly=True, index=True)
    call = fields.Many2one('connect.call', ondelete='cascade')
    parent_channel = fields.Many2one('connect.channel', ondelete='cascade', tracking=True)
    parent_sid = fields.Char('Parent SID', tracking=True, readonly=True)
    partner = fields.Many2one('res.partner', ondelete='set null', tracking=True)
    called = fields.Char(tracking=True)
    to = fields.Char(tracking=True)
    technical_direction = fields.Char(tracking=True, string='Direction')
    status = fields.Char(tracking=True)
    duration = fields.Integer(string='Seconds', tracking=True)
    duration_minutes = fields.Float(string='Minutes', tracking=True)
    duration_billing = fields.Integer(string='Bill Minutes', tracking=True)
    duration_human = fields.Char(compute='_get_duration_human', string='Duration', store=True, tracking=True)
    caller = fields.Char(tracking=True)
    call_type = fields.Selection([
        ('phone', 'Phone'),
        ('whatsapp', 'WhatsApp')
    ], default='phone', index=True, tracking=True)
    caller_pbx_user = fields.Many2one('connect.user', ondelete='set null', string='Caller PBX User', tracking=True)
    called_pbx_user = fields.Many2one('connect.user', ondelete='set null', string='Called PBX User', tracking=True)
    caller_user = fields.Many2one('res.users', string='Caller User', tracking=True)
    called_user = fields.Many2one('res.users', string='Called User', tracking=True)
    caller_number = fields.Char(compute='_get_channel_numbers', store=True, index=True)
    called_number = fields.Char(compute='_get_channel_numbers', store=True, index=True)
    recording_state = fields.Selection([
        ('off', 'Off'),
        ('on', 'On'),
        ('starting', 'Starting'),
        ('stopping', 'Stopping'),
        ('error', 'Error'),
    ], default='off', copy=False, tracking=True)
    recording_control_ref = fields.Char(copy=False, readonly=True)
    recording_control_path = fields.Char(copy=False, readonly=True)
    recording_control_error = fields.Char(copy=False, readonly=True)

    @api.depends('caller', 'called')
    def _get_channel_numbers(self):
        re_number_domain = re.compile(
            r'^(?:(?:sip|client):)?([^@]+)@(.+)$')
        re_client_number = re.compile(r'^client:(\d{8})$')
        re_number = re.compile(r'^(\+?[0-9]+)$')
        re_whatsapp = re.compile(r'^whatsapp:(\+?[0-9]+)$')

        def _get_number(callinfo):
            if not isinstance(callinfo, str):
                return ''
            if re_number.search(callinfo):
                return callinfo
            elif re_whatsapp.search(callinfo):
                return re_whatsapp.search(callinfo).group(1)
            elif re_number_domain.search(callinfo):
                user_or_number = re_number_domain.search(callinfo).group(1)
                user = self.env['connect.user'].get_user_by_uri(callinfo)
                if user:
                    return user.get_pbx_number() or user_or_number
                else:
                    return user_or_number
            elif re_client_number.search(callinfo):
                return re_client_number.search(callinfo).group(1)
            else:
                return ''

        for rec in self:
            rec.caller_number = _get_number(rec.caller)
            rec.called_number = _get_number(rec.called)

    @api.model
    def process_channel_event(self, params):
        """Process a channel event from any provider.

        Provider modules map their webhook data to a generic dict and call this.

        Args:
            params: dict with keys:
                sid (str): Provider channel identifier (required)
                caller (str): Caller number or URI
                called (str): Called number or URI
                to (str): Original To field (optional)
                technical_direction (str): 'inbound', 'outbound-api', 'outbound-dial'
                status (str): Channel status
                duration (int): Duration in seconds
                call_type (str): 'phone' or 'whatsapp' (default: 'phone')
                parent_sid (str): Parent channel SID (optional)
                caller_pbx_user_id (int): Direct connect.user ID (optional, skips URI lookup)
                called_pbx_user_id (int): Direct connect.user ID (optional, skips URI lookup)

        Returns:
            connect.channel record
        """
        self = self.sudo()

        channel = self.search([('sid', '=', params['sid'])], limit=1, order='id asc')
        if channel:
            # Update existing channel
            data = {
                'called': params.get('called'),
                'to': params.get('to'),
                'technical_direction': params.get('technical_direction'),
                'status': params.get('status'),
                'duration': int(params.get('duration', 0)),
                'caller': params.get('caller'),
                'call_type': params.get('call_type', 'phone'),
            }
            # Click-to-call stores the real destination on the channel it
            # creates, then the first status event for that same leg reports
            # the transport-level target -- the agent's client:/sip: URI --
            # as Called, and the ledger ends up showing the agent's own
            # extension instead of the number that was dialed. The URI is
            # already preserved in "to", so keep the dialed destination.
            new_called = params.get('called')
            if (channel.called
                    and not channel.called.startswith(('client:', 'sip:'))
                    and isinstance(new_called, str)
                    and new_called.startswith(('client:', 'sip:'))):
                del data['called']
            # Same asymmetry for the call type. A WhatsApp click-to-call
            # rings the agent over ordinary voice -- the outer leg must not
            # carry a "whatsapp:" identity, or Twilio ends the call before
            # the WhatsApp verb runs -- so its status events describe a
            # plain phone leg. The originator is the only party that knows
            # better, so let it win: an upgrade to whatsapp still applies,
            # a downgrade back to phone does not.
            if (channel.call_type == 'whatsapp'
                    and data.get('call_type') != 'whatsapp'):
                del data['call_type']
            # Link parent if not yet linked
            if not channel.parent_channel:
                parent_sid = channel.parent_sid or params.get('parent_sid')
                if parent_sid:
                    parent_channel = self.search([('sid', '=', parent_sid)])
                    if parent_channel:
                        data['parent_channel'] = parent_channel.id
            channel.write(data)
            debug(self, 'Channel %s updated.' % channel.id)
        else:
            # Create new channel
            data = {
                'sid': params['sid'],
                'called': params.get('called'),
                'to': params.get('to'),
                'technical_direction': params.get('technical_direction'),
                'status': params.get('status'),
                'duration': int(params.get('duration', 0)),
                'caller': params.get('caller'),
                'call_type': params.get('call_type', 'phone'),
            }
            # Link parent
            parent_sid = params.get('parent_sid')
            if parent_sid:
                data['parent_sid'] = parent_sid
                parent_channel = self.search([('sid', '=', parent_sid)])
                if parent_channel:
                    data['parent_channel'] = parent_channel.id

            # Find caller PBX user
            caller_pbx_user = None
            called_pbx_user = None

            if params.get('caller_pbx_user_id'):
                caller_pbx_user = self.env['connect.user'].browse(
                    params['caller_pbx_user_id'])
            elif params.get('caller'):
                caller_pbx_user = self.env['connect.user'].get_user_by_uri(
                    params['caller'])

            if caller_pbx_user:
                data['caller_pbx_user'] = caller_pbx_user.id
                if caller_pbx_user.user:
                    data['caller_user'] = caller_pbx_user.user.id

            # Find called PBX user
            if params.get('called_pbx_user_id'):
                called_pbx_user = self.env['connect.user'].browse(
                    params['called_pbx_user_id'])
            elif params.get('called'):
                called_pbx_user = self.env['connect.user'].get_user_by_uri(
                    params['called'])

            if called_pbx_user:
                data['called_pbx_user'] = called_pbx_user.id
                if called_pbx_user.user:
                    data['called_user'] = called_pbx_user.user.id

            # Find partner
            partner = self._find_partner(
                caller_pbx_user, called_pbx_user,
                params.get('caller'), params.get('called'),
                params.get('technical_direction')
            )
            if partner:
                data['partner'] = partner.id

            channel = self.with_context(tracking_disable=True).create(data)
            debug(self, 'Channel %s created.' % channel.id)

        return channel

    def _find_partner(self, caller_pbx_user, called_pbx_user, caller, called, direction):
        """Determine which number is external and find the partner."""
        Partner = self.env['res.partner']

        if caller_pbx_user and called:
            debug(self, 'Setting partner by called number (caller is PBX user).')
            return Partner.get_partner_by_number(called)
        elif called_pbx_user and caller:
            debug(self, 'Setting partner by caller number (called is PBX user).')
            return Partner.get_partner_by_number(caller)
        elif direction == 'outbound-dial' and called:
            debug(self, 'Setting partner for outbound dial by called.')
            return Partner.get_partner_by_number(called)
        elif direction == 'inbound' and caller:
            debug(self, 'Incoming call. Get the partner from caller number.')
            return Partner.get_partner_by_number(caller)
        else:
            debug(self, 'Not setting channel partner without channel users.')
        return self.env['res.partner']

    def _softphone_recording_payload(self, supported=True):
        self.ensure_one()
        return {
            'supported': supported,
            'state': self.recording_state or 'off',
            'recording_ref': self.recording_control_ref or '',
            'recording_path': self.recording_control_path or '',
            'error': self.recording_control_error or '',
            'channel_sid': self.sid or '',
        }

    @api.model
    def _softphone_recording_unsupported(self):
        return {
            'supported': False,
            'state': 'unsupported',
            'recording_ref': '',
            'recording_path': '',
            'error': 'Recording control is not supported for this provider.',
            'channel_sid': '',
        }

    @api.model
    def _softphone_recording_channel(self, payload):
        payload = payload or {}
        channel_sid = payload.get('channel_sid') or payload.get('call_sid')
        if not channel_sid:
            raise UserError('Missing active call identifier.')
        request_user = self.env.user
        channel = self.sudo().search([('sid', '=', channel_sid)], limit=1)
        if not channel:
            raise UserError('Active call was not found.')
        channel._check_softphone_recording_access(request_user)
        return channel

    def _check_softphone_recording_access(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        if user.has_group('connect.group_admin'):
            return True
        user_ids = set()
        for field_name in ['caller_user', 'called_user']:
            rec = self[field_name]
            if rec:
                user_ids.add(rec.id)
        if self.call:
            for field_name in ['caller_user', 'answered_user']:
                rec = self.call[field_name]
                if rec:
                    user_ids.add(rec.id)
            user_ids.update(self.call.called_users.ids)
        if user.id in user_ids:
            return True
        raise AccessError('You can control recording only for your own calls.')

    def _check_softphone_recording_active(self):
        self.ensure_one()
        if self.status in CALL_END_STATUSES:
            raise UserError('Recording can be controlled only during an active call.')
        return True

    @api.model
    def _dispatch_softphone_recording(self, payload, action):
        payload = payload or {}
        provider = payload.get('provider')
        if not provider:
            raise UserError('Missing recording provider.')
        method = '_softphone_recording_{}_{}'.format(action, provider)
        if not hasattr(self, method):
            return self._softphone_recording_unsupported()
        return getattr(self, method)(payload)

    @api.model
    def get_softphone_recording_state(self, payload):
        return self._dispatch_softphone_recording(payload, 'state')

    @api.model
    def start_softphone_recording(self, payload):
        return self._dispatch_softphone_recording(payload, 'start')

    @api.model
    def stop_softphone_recording(self, payload):
        return self._dispatch_softphone_recording(payload, 'stop')

    @api.depends('duration')
    def _get_duration_human(self):
        for record in self:
            if record.duration is not None:
                minutes = record.duration // 60
                seconds = record.duration % 60
                record.duration_human = '{:02}:{:02}'.format(minutes, seconds)
                record.duration_minutes = record.duration / 60.0
            else:
                record.duration_minutes = 0
                record.duration_human = "00:00"

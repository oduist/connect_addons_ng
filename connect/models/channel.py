import logging
import re
from odoo import fields, models, api, release
from .settings import debug

logger = logging.getLogger(__name__)


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

    @api.depends('caller', 'called')
    def _get_channel_numbers(self):
        re_number_domain = re.compile(r'^(sip|client):(.+)@(.+)$')
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
                user_or_number = re_number_domain.search(callinfo).group(2)
                user = self.env['connect.user'].get_user_by_uri(callinfo)
                if user:
                    return user.exten.number
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

    @api.model
    def reconcile_bridge_link(self, sid):
        """Link `sid`'s channel to its bridge sibling (and merge calls).

        Callers run this in a fresh transaction (typically after committing
        the CDR webhook handler) to recover from snapshot races: when two
        bridged-leg CDRs arrive concurrently, Odoo's REPEATABLE READ
        isolation can leave the second worker unable to see the first
        worker's freshly-created sibling row, so `process_channel_event`
        creates an unlinked channel and `process_call_event` mints a
        duplicate `connect.call`. With a fresh snapshot both legs are
        visible; this helper performs the parent_channel link and merges
        the orphan call into the parent's call.

        Idempotent — repeated invocations short-circuit cleanly.
        """
        ch = self.search([('sid', '=', sid)], limit=1)
        if not ch:
            return
        # Forward link — we know our parent_sid but didn't see the row.
        if not ch.parent_channel and ch.parent_sid:
            parent = self.search([('sid', '=', ch.parent_sid)], limit=1)
            if parent:
                ch.parent_channel = parent.id
                self._merge_calls(ch, parent)
        # Reverse link — another leg arrived first referencing us as parent.
        orphans = self.search([
            ('parent_sid', '=', sid),
            ('parent_channel', '=', False),
            ('id', '!=', ch.id),
        ])
        for orphan in orphans:
            orphan.parent_channel = ch.id
            self._merge_calls(orphan, ch)

    @api.model
    def _merge_calls(self, child, parent):
        """Move `child` onto `parent.call`; drop child's old call if empty.

        Before unlinking the orphan call, rescue caller/called/partner
        into the surviving call if survivor's slots are empty: under the
        bridge-pair CDR race the orphan may carry the dialed digits while
        the survivor was minted from the opaque-token leg (see ADR-022).
        """
        if not child.call or not parent.call or child.call == parent.call:
            return
        old_call = child.call
        child.call = parent.call.id
        backfill = {}
        if not parent.call.called and old_call.called:
            backfill['called'] = old_call.called
        if not parent.call.caller and old_call.caller:
            backfill['caller'] = old_call.caller
        if not parent.call.partner and old_call.partner:
            backfill['partner'] = old_call.partner.id
        if backfill:
            parent.call.write(backfill)
        if not old_call.channels:
            old_call.unlink()

    def _find_partner(self, caller_pbx_user, called_pbx_user, caller, called, direction):
        """Determine which number is external and find the partner."""
        Partner = self.env['res.partner']

        if caller_pbx_user and called:
            if (called or '').startswith('+'):
                debug(self, 'Setting partner by called number (caller is PBX user).')
                return Partner.get_partner_by_number(called)
        elif called_pbx_user and caller:
            if (caller or '').startswith('+'):
                debug(self, 'Setting partner by caller number (called is PBX user).')
                return Partner.get_partner_by_number(caller)
        elif direction == 'outbound-dial' and called:
            debug(self, 'Setting partner for outbound dial by called.')
            return Partner.get_partner_by_number(called)
        elif (direction == 'inbound'
              and (called or '').startswith('+')
              and (caller or '').startswith('+')):
            debug(self, 'Incoming DID call. Get the partner from caller number.')
            return Partner.get_partner_by_number(caller)
        else:
            debug(self, 'Not setting channel partner without channel users.')
        return self.env['res.partner']

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

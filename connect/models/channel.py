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
        """Collapse the whole bridge `sid` belongs to into one call.

        A bridged call is N legs, not two: FreeSWITCH forks the b-leg to
        every callee contact (the winner answers, the losers tear down) and
        posts a CDR per leg, so one logical call spans an a-leg plus M
        b-legs — all sharing the a-leg as their `signal_bond` parent (stored
        in `parent_sid`). Callers run this post-commit (see the FreeSWITCH
        CDR controller) so a fresh snapshot sees every committed leg.

        Walk the bridge component (the `parent_sid` <-> `sid` closure),
        set each channel's `parent_channel` where the parent is resolvable,
        then converge every distinct `call` in the component into one.
        Unlike the per-leg merge it replaces, convergence is driven by call
        inequality inside the component — not by whether `parent_channel`
        was just established — so a leg that ended up linked but on its own
        duplicate call (the concurrent-CDR race) is still collapsed.

        Idempotent: a component already on one call is a no-op. Order-
        independent: whichever leg's reconcile runs last sees the full
        component; an out-of-order late leg converges on its own pass.
        """
        ch = self.search([('sid', '=', sid)], limit=1)
        if not ch:
            return
        component = self._bridge_component(ch)
        # Keep parent_channel links current (used by the UI and the
        # connect_twilio recording lookup) wherever the parent is present.
        for c in component:
            if not c.parent_channel and c.parent_sid:
                parent = component.filtered(lambda x: x.sid == c.parent_sid)
                if parent:
                    c.parent_channel = parent[0].id
        self._converge_calls(component)

    @api.model
    def _bridge_component(self, channel):
        """All channels bridged to `channel`, gathered by bounded BFS over
        the symmetric signal_bond relation (`parent_sid` <-> `sid`)."""
        component = channel
        frontier = channel
        while frontier:
            sids = [c.sid for c in frontier if c.sid]
            parent_sids = [c.parent_sid for c in frontier if c.parent_sid]
            neighbours = self.search([
                '|',
                ('parent_sid', 'in', sids),
                ('sid', 'in', parent_sids),
            ])
            frontier = neighbours - component
            component |= frontier
        return component

    @api.model
    def _converge_calls(self, channels):
        """Move every channel in `channels` onto one canonical call.

        Canonical = the oldest call (min id); each other call is backfilled
        into it (so caller/called/partner survive — see ADR-022) and dropped
        once empty. Channels reassign before the unlink, so the cascade on
        `connect.channel.call` never deletes a real leg.
        """
        calls = channels.mapped('call')
        if len(calls) <= 1:
            return
        canonical = min(calls, key=lambda c: c.id)
        for channel in channels:
            old_call = channel.call
            if not old_call or old_call == canonical:
                continue
            channel.call = canonical.id
            self._backfill_call(canonical, old_call)
            if not old_call.channels:
                old_call.unlink()

    @api.model
    def _backfill_call(self, survivor, orphan):
        """Copy the orphan call's caller/called/partner into `survivor`
        wherever the survivor's slot is still empty (ADR-022)."""
        backfill = {}
        if not survivor.called and orphan.called:
            backfill['called'] = orphan.called
        if not survivor.caller and orphan.caller:
            backfill['caller'] = orphan.caller
        if not survivor.partner and orphan.partner:
            backfill['partner'] = orphan.partner.id
        if backfill:
            survivor.write(backfill)

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

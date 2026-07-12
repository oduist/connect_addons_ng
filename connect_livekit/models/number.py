# -*- coding: utf-8 -*-
import json
import logging
import re

from odoo import api, fields, models, release
if release.version_info[0] >= 19:
    from odoo.models import Constraint
from odoo.exceptions import ValidationError

from livekit import api as lk_api

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)

# The worker registers under this agent name; dispatch is explicit only
# (ADR-037).
LIVEKIT_AGENT_NAME = 'connect-livekit-agent'


class LivekitNumber(models.Model):
    """A DID routed through the LiveKit SIP bridge.

    Each number owns one LiveKit dispatch rule; the destination decides
    its shape: user → individual rooms (did-<id>- prefix) + web phone
    ring, agent → individual rooms with an explicit agent dispatch,
    room → direct dispatch into a meeting room.
    """
    _name = 'connect.livekit.number'
    _description = 'LiveKit Number'
    _order = 'phone_number'
    _rec_names_search = ['phone_number', 'friendly_name']

    name = fields.Char(compute='_get_name')
    phone_number = fields.Char(required=True)
    friendly_name = fields.Char()
    trunk = fields.Many2one(
        'connect.livekit.trunk', required=True, ondelete='restrict')
    destination = fields.Selection([
        ('user', 'User'),
        ('agent', 'AI Agent'),
        ('room', 'Room'),
    ], default='user', required=True)
    user = fields.Many2one('connect.user', ondelete='set null')
    agent = fields.Many2one('connect.livekit.agent', ondelete='set null')
    room = fields.Many2one('connect.livekit.room', ondelete='set null')
    dispatch_rule_sid = fields.Char(readonly=True, copy=False)

    if release.version_info[0] >= 19:
        _phone_number_uniq = Constraint(
            'UNIQUE(phone_number)', 'This number is already used!')
    else:
        _sql_constraints = [
            ('phone_number_uniq', 'UNIQUE(phone_number)',
             'This number is already used!'),
        ]

    def _get_name(self):
        for rec in self:
            rec.name = '{} "{}"'.format(
                rec.phone_number, rec.friendly_name or rec.phone_number)

    @api.constrains('phone_number')
    def _check_phone_number(self):
        # Iterate: a constraint receives a (possibly multi-record)
        # recordset. Duplicated across providers by design (ADR-031).
        for rec in self:
            if rec.phone_number and not re.match(
                    r'^\+[0-9]+$', rec.phone_number):
                raise ValidationError(
                    'Number must be in E.164 form: a + followed by digits '
                    'only.')

    @api.constrains('destination', 'user', 'agent', 'room')
    def _check_destination(self):
        for rec in self:
            if rec.destination == 'user' and not rec.user:
                raise ValidationError('Select the destination user!')
            if rec.destination == 'agent' and not rec.agent:
                raise ValidationError('Select the destination AI agent!')
            if rec.destination == 'room' and not rec.room:
                raise ValidationError('Select the destination room!')

    def _room_prefix(self):
        self.ensure_one()
        return 'did-{}-'.format(self.id)

    def _delete_remote_rule(self):
        for rec in self:
            if not rec.dispatch_rule_sid:
                continue
            try:
                self.env['connect.settings'].livekit_api_call(
                    'sip.delete_sip_dispatch_rule',
                    lk_api.DeleteSIPDispatchRuleRequest(
                        sip_dispatch_rule_id=rec.dispatch_rule_sid))
            except ValidationError as e:
                logger.warning('LiveKit delete dispatch rule %s: %s',
                               rec.dispatch_rule_sid, e)
            rec.with_context(skip_livekit_sync=True).write(
                {'dispatch_rule_sid': False})

    def _dispatch_rule_request(self):
        self.ensure_one()
        if self.destination == 'room':
            self.room._ensure_livekit_room()
            rule = lk_api.SIPDispatchRule(
                dispatch_rule_direct=lk_api.SIPDispatchRuleDirect(
                    room_name=self.room.room_name))
        else:
            rule = lk_api.SIPDispatchRule(
                dispatch_rule_individual=lk_api.SIPDispatchRuleIndividual(
                    room_prefix=self._room_prefix()))
        request = lk_api.CreateSIPDispatchRuleRequest(
            rule=rule,
            trunk_ids=[self.trunk.inbound_trunk_sid],
            inbound_numbers=[self.phone_number],
            name='odoo-number-{}'.format(self.id),
            metadata=json.dumps({
                'number_id': self.id,
                'destination': self.destination,
            }),
        )
        if self.destination == 'agent':
            request.room_config.agents.append(lk_api.RoomAgentDispatch(
                agent_name=LIVEKIT_AGENT_NAME,
                metadata=json.dumps({'agent_id': self.agent.id})))
        return request

    def _push_dispatch_rule(self):
        for rec in self:
            if not rec.trunk.inbound_trunk_sid:
                rec.trunk._push_inbound()
            rec._delete_remote_rule()
            resp = self.env['connect.settings'].livekit_api_call(
                'sip.create_sip_dispatch_rule', rec._dispatch_rule_request())
            rec.with_context(skip_livekit_sync=True).write(
                {'dispatch_rule_sid': resp.sip_dispatch_rule_id})
            debug(self, 'LiveKit dispatch rule for {} pushed as {}.'.format(
                rec.phone_number, resp.sip_dispatch_rule_id))

    @api.model
    def sync(self):
        self.search([])._push_dispatch_rule()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._clean_destination_vals(vals)
        recs = super().create(vals_list)
        if (self.env['connect.settings'].sudo().get_param('livekit_auto_sync')
                and not self.env.context.get('skip_livekit_sync')):
            # The inbound trunk carries the number list — re-push first.
            recs.mapped('trunk')._push_inbound()
            recs._push_dispatch_rule()
        return recs

    def write(self, vals):
        self._clean_destination_vals(vals)
        res = super().write(vals)
        if (self.env['connect.settings'].sudo().get_param('livekit_auto_sync')
                and not self.env.context.get('skip_livekit_sync')):
            self.mapped('trunk')._push_inbound()
            self._push_dispatch_rule()
        return res

    @api.model
    def _clean_destination_vals(self, vals):
        # Null the non-selected destination targets so stale links do not
        # linger (the Telnyx number pattern).
        destination = vals.get('destination')
        if destination == 'user':
            vals.update({'agent': False, 'room': False})
        elif destination == 'agent':
            vals.update({'user': False, 'room': False})
        elif destination == 'room':
            vals.update({'user': False, 'agent': False})
        return vals

    def unlink(self):
        self._delete_remote_rule()
        trunks = self.mapped('trunk')
        res = super().unlink()
        if (self.env['connect.settings'].sudo().get_param('livekit_auto_sync')
                and not self.env.context.get('skip_livekit_sync')):
            trunks._push_inbound()
        return res

    @api.model
    def get_number_for_room(self, room_name):
        """Resolve a did-<id>-... room back to its number record."""
        match = re.match(r'^did-(\d+)-', room_name or '')
        if not match:
            return self.browse()
        return self.sudo().browse(int(match.group(1))).exists()

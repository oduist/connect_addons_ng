# -*- coding: utf-8 -*-
import logging
import re
from odoo import fields, models, api, release
if release.version_info[0] >= 19:
    from odoo.models import Constraint
from odoo.exceptions import ValidationError
from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)


class OutgoingCallerID(models.Model):
    """Outbound caller IDs.

    LiveKit has no caller-ID validation API, so this model only holds
    numbers the carrier allows on the linked outbound trunk; the number
    list is pushed onto the LiveKit outbound trunk (ADR-036).
    """
    _name = 'connect.livekit.outgoing_callerid'
    _description = 'LiveKit Outgoing CallerId'
    _order = 'number'
    _rec_names_search = ['number', 'friendly_name']

    name = fields.Char(compute='_get_name')
    friendly_name = fields.Char(required=True)
    number = fields.Char(required=True)
    is_default = fields.Boolean(string='Default')
    trunk = fields.Many2one(
        'connect.livekit.trunk', required=True, ondelete='restrict',
        help="The outbound trunk that carries this number.")
    callerid_users = fields.One2many(
        comodel_name='connect.user',
        inverse_name='livekit_outgoing_callerid', string='callerId Users')

    if release.version_info[0] >= 19:
        _number_uniq = Constraint('UNIQUE(number)', 'This number is already used!')
    else:
        _sql_constraints = [('number_uniq', 'UNIQUE(number)', 'This number is already used!')]

    def _get_name(self):
        for rec in self:
            rec.name = '{} "{}"'.format(rec.number, rec.friendly_name)

    @api.constrains('number')
    def _check_number(self):
        # Iterate: a constraint receives a (possibly multi-record)
        # recordset, so self.number would raise "Expected singleton" on a
        # batch create. The single regex also covers the +-prefix check.
        # Duplicated in connect_twilio/connect_freeswitch/connect_telnyx
        # by design — apply fixes to all copies (ADR-031/ADR-032).
        for rec in self:
            if rec.number and not re.match(r'^\+[0-9]+$', rec.number):
                raise ValidationError(
                    'Number must be in E.164 form: a + followed by digits only.')

    @api.constrains('is_default')
    def _reset_default(self):
        if self.env.context.get('skip_reset_default'):
            return
        # Only clear the other records when this one is BECOMING the
        # default.
        for rec in self:
            if rec.is_default:
                self.with_context(skip_reset_default=True).search(
                    [('id', '!=', rec.id)]).write({'is_default': False})

    @api.model
    def sync(self):
        # The caller-ID list lives on the LiveKit outbound trunks.
        self.search([]).mapped('trunk')._push_outbound()

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if (self.env['connect.settings'].sudo().get_param('livekit_auto_sync')
                and not self.env.context.get('skip_livekit_sync')):
            recs.mapped('trunk')._push_outbound()
        return recs

    def write(self, vals):
        old_trunks = self.mapped('trunk') if 'trunk' in vals else self.env[
            'connect.livekit.trunk']
        res = super().write(vals)
        if (vals.get('number') or vals.get('trunk')) and (
                self.env['connect.settings'].sudo().get_param(
                    'livekit_auto_sync')
                and not self.env.context.get('skip_livekit_sync')):
            (old_trunks | self.mapped('trunk'))._push_outbound()
        return res

    def unlink(self):
        trunks = self.mapped('trunk')
        res = super().unlink()
        if (self.env['connect.settings'].sudo().get_param('livekit_auto_sync')
                and not self.env.context.get('skip_livekit_sync')):
            trunks._push_outbound()
        return res

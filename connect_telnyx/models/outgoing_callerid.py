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

    Telnyx has no Twilio-style external caller-ID validation API, so this
    model only holds numbers owned in the Telnyx account, synced from the
    phone numbers list (ADR-032).
    """
    _name = 'connect.telnyx.outgoing_callerid'
    _description = 'Telnyx Outgoing CallerId'
    _order = 'number'
    _rec_names_search = ['number', 'friendly_name']

    name = fields.Char(compute='_get_name')
    friendly_name = fields.Char(required=True)
    number = fields.Char(required=True)
    is_default = fields.Boolean(string='Default')
    callerid_users = fields.One2many(
        comodel_name='connect.user',
        inverse_name='telnyx_outgoing_callerid', string='callerId Users')
    sid = fields.Char(readonly=True)

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
        # Duplicated in connect_twilio/connect_freeswitch by design —
        # apply fixes to all copies (ADR-031/ADR-032).
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
        client = self.env['connect.settings'].get_telnyx_client()
        numbers = list(client.phone_numbers.list())
        for number in numbers:
            existing_number = self.env[self._name].search([
                ('sid', '=', number.id)])
            if not existing_number:
                existing_number = self.env[self._name].search([
                    ('number', '=', number.phone_number)])
            data = {
                'sid': number.id,
                'number': number.phone_number,
                'friendly_name': number.customer_reference or number.phone_number,
            }
            callerid_count = self.search_count([])
            if callerid_count == 0:
                data['is_default'] = True
            if not existing_number:
                self.create(data)
                debug(self, 'CallerID {} ({}) created in Odoo.'.format(
                    number.phone_number, data['friendly_name']))
            else:
                existing_number.write(data)
        recs_to_remove = self.env[self._name].search(
            [('sid', 'not in', [k.id for k in numbers])])
        if recs_to_remove:
            debug(self, 'Removing CallerIds: {}'.format(
                [k.number for k in recs_to_remove]))
            recs_to_remove.unlink()

import re
from odoo import fields, models, api, release
if release.version_info[0] >= 19:
    from odoo.models import Constraint
from odoo.exceptions import ValidationError


class OutgoingCallerID(models.Model):
    _name = 'connect.outgoing_callerid'
    _description = 'Outgoing CallerId'
    _order = 'number'
    _rec_names_search = ['number', 'friendly_name']

    name = fields.Char(compute='_get_name')
    friendly_name = fields.Char(required=True)
    number = fields.Char(required=True)
    callerid_type = fields.Selection(
        [('outgoing_callerid', 'CallerID'), ('number', 'DID Number')],
        required=True, default='outgoing_callerid')
    is_default = fields.Boolean(string='Default')
    callerid_users = fields.One2many(
        comodel_name='connect.user',
        inverse_name='outgoing_callerid', string='callerId Users')

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
        for rec in self:
            if rec.number and not re.match(r'^\+[0-9]+$', rec.number):
                raise ValidationError(
                    'Number must be in E.164 form: a + followed by digits only.')

    @api.constrains('is_default')
    def _reset_default(self):
        if self.env.context.get('skip_reset_default'):
            return
        # Only clear the other records when this one is BECOMING the
        # default. The previous version reset every record (including the
        # current default) on any is_default write, so setting a record's
        # is_default to False wiped the default flag everywhere and left no
        # default at all.
        for rec in self:
            if rec.is_default:
                self.with_context(skip_reset_default=True).search(
                    [('id', '!=', rec.id)]).write({'is_default': False})


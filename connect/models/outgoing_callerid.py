import logging
import re
from odoo import fields, models, api, release
if release.version_info[0] >= 19:
    from odoo.models import Constraint
from odoo.exceptions import ValidationError
from .settings import debug

logger = logging.getLogger(__name__)


class OutgoingCallerID(models.Model):
    _name = 'connect.outgoing_callerid'
    _description = 'Outgoing CallerId'
    _order = 'number'

    name = fields.Char(compute='_get_name')
    friendly_name = fields.Char(required=True)
    number = fields.Char(required=True)
    status = fields.Char(readonly=True)
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
        if self.number and not self.number.startswith('+'):
            raise ValidationError('Number must start with +')
        if self.number and not re.search(r'^\+[0-9]+$', self.number):
            raise ValidationError('Number must contain only digits!')

    @api.constrains('is_default')
    def _reset_default(self):
        for rec in self:
            if not self.env.context.get('skip_reset_default'):
                context = {
                    'skip_reset_default': True,
                }
                default = rec.is_default
                self.with_context(context).search(
                    []).write({'is_default': False})
                rec.with_context(context).is_default = default

    @api.constrains('is_default')
    def _check_default(self):
        for rec in self:
            if rec.is_default:
                if rec.callerid_type == 'outgoing_callerid' and rec.status != 'validated':
                    raise ValidationError('Validate the number first!')

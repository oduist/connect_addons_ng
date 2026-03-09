import logging
from odoo import fields, models, api
from .settings import debug

logger = logging.getLogger(__name__)


class Number(models.Model):
    _name = 'connect.number'
    _description = 'Phone Number'
    _rec_name = 'phone_number'
    _order = 'phone_number'

    is_ignored = fields.Boolean('Ignored')
    is_default = fields.Boolean(string='Default')
    phone_number = fields.Char(required=True)
    friendly_name = fields.Char()
    destination = fields.Selection(selection=[
        ('user', 'User'),
        ('callflow', 'CallFlow'),
    ], ondelete='set null')
    callflow = fields.Many2one('connect.callflow', ondelete='set null')
    user = fields.Many2one('connect.user', ondelete='set null')

    def write(self, vals):
        if 'destination' in vals:
            for field in ['user', 'callflow']:
                if field != vals['destination']:
                    vals.update({field: None})
        return super().write(vals)

    def render(self, request={}, params={}):
        self.ensure_one()
        if self.destination == 'user' and self.user:
            return self.user.render(request)
        elif self.destination == 'callflow' and self.callflow:
            return self.callflow.render(request)
        else:
            return '<Response><Say>Number not configured. Goodbye!</Say></Response>'

    @api.model
    def route_call(self, request, params={}):
        debug(self, 'Route number call: %s' % request)
        number = self.sudo().search([('phone_number', '=', request.get('Called'))])
        if not number:
            return '<Response><Say>Number not found. Goodbye!</Say></Response>'
        return number.render(request=request, params=params)

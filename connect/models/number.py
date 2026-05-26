from odoo import fields, models


class Number(models.Model):
    _name = 'connect.number'
    _description = 'Phone Number'
    _rec_name = 'phone_number'
    _order = 'phone_number'

    is_default = fields.Boolean(string='Default')
    phone_number = fields.Char(required=True)
    friendly_name = fields.Char()
    destination = fields.Selection(selection=[
        ('user', 'User'),
        ('callflow', 'CallFlow'),
    ], ondelete='set null')
    callflow = fields.Many2one('connect.callflow', ondelete='set null')
    user = fields.Many2one('connect.user', ondelete='set null')
    provider_id = fields.Many2one(
        'connect.provider', ondelete='set null', index=True, copy=False,
        help='Telephony provider that owns this DID.',
    )

    def write(self, vals):
        if 'destination' in vals:
            for field in ['user', 'callflow']:
                if field != vals['destination']:
                    vals.update({field: None})
        return super().write(vals)

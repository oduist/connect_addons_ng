from odoo import fields, models


class Call(models.Model):
    _name = 'connect.call'
    _description = 'Call'

    name = fields.Char(string='Name', required=True)
    state = fields.Selection([
        ('new', 'New'),
        ('active', 'Active'),
        ('ended', 'Ended'),
    ], string='State', default='new', required=True)
    direction = fields.Selection([
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing'),
    ], string='Direction', required=True)
    started_at = fields.Datetime(string='Started At')
    ended_at = fields.Datetime(string='Ended At')

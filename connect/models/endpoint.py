from odoo import fields, models


class ConnectEndpoint(models.Model):
    _name = 'connect.endpoint'
    _description = 'Connect Endpoint'

    name = fields.Char(string='Name', required=True)
    connect_user_id = fields.Many2one('connect.user', string='Connect User', required=True, ondelete='cascade')
    active = fields.Boolean(default=True)

from odoo import fields, models


class ConnectUser(models.Model):
    _name = 'connect.user'
    _description = 'Connect User'

    name = fields.Char(string='Name', required=True)
    extension = fields.Char(string='Extension')
    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade')
    active = fields.Boolean(default=True)

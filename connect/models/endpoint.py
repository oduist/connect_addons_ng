from odoo import fields, models


class ConnectEndpoint(models.Model):
    _name = 'connect.endpoint'
    _description = 'Connect Endpoint'

    name = fields.Char(string='Name', required=True)
    connect_user_id = fields.Many2one('connect.user', string='Connect User', ondelete='cascade')
    exten = fields.Many2one('connect.exten', ondelete='set null', readonly=True)
    exten_number = fields.Char(related='exten.number', store=True)
    active = fields.Boolean(default=True)

    def create_extension(self):
        self.ensure_one()
        return self.env['connect.exten'].create_extension(self, 'endpoint')

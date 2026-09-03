from odoo import api, fields, models


class Project(models.Model):
    _inherit = 'project.project'

    connect_calls = fields.One2many('connect.call', 'project')
    connect_calls_count = fields.Integer(
        compute='_get_connect_calls_count', string='Calls', store=True,
    )
    recorded_calls = fields.One2many('connect.recording', 'project')
    partner_phone = fields.Char(related='partner_id.phone')
    partner_mobile = fields.Char(related='partner_id.mobile')

    @api.depends('connect_calls')
    def _get_connect_calls_count(self):
        for rec in self:
            rec.connect_calls_count = self.env['connect.call'].search_count(
                [('project', '=', rec.id)],
            )

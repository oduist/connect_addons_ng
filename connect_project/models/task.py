from odoo import api, fields, models


class Task(models.Model):
    _inherit = 'project.task'

    connect_calls = fields.One2many('connect.call', 'task')
    connect_calls_count = fields.Integer(
        compute='_get_connect_calls_count', string='Calls', store=True,
    )
    recorded_calls = fields.One2many('connect.recording', 'task')
    partner_phone = fields.Char(related='partner_id.phone')
    partner_mobile = fields.Char(related='partner_id.mobile')

    @api.depends('connect_calls')
    def _get_connect_calls_count(self):
        for rec in self:
            rec.connect_calls_count = self.env['connect.call'].search_count(
                [('task', '=', rec.id)],
            )

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if self.env.context.get('connect_call_id') and recs:
            call = self.env['connect.call'].sudo().browse(self.env.context['connect_call_id'])
            call.task = recs[0]
        if recs:
            self.env.registry.clear_cache()
        return recs

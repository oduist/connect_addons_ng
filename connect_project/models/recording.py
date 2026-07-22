from odoo import api, fields, models


class Recording(models.Model):
    _inherit = 'connect.recording'

    task = fields.Many2one('project.task', ondelete='set null', readonly=True)
    project = fields.Many2one('project.project', ondelete='set null', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            if rec.call.task:
                rec.task = rec.call.task
            elif rec.call.project:
                rec.project = rec.call.project
        return recs

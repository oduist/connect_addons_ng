import logging

from odoo import api, fields, models

logger = logging.getLogger(__name__)


class Recording(models.Model):
    _inherit = 'connect.recording'

    task = fields.Many2one('project.task', ondelete='set null', readonly=True)
    project = fields.Many2one('project.project', ondelete='set null', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env['oduist.license'].check_license('connect_project', silent=True):
            return recs
        try:
            for rec in recs:
                if rec.call.task:
                    rec.task = rec.call.task
                elif rec.call.project:
                    rec.project = rec.call.project
        except Exception:
            logger.exception('Project recording link error (handled):')
        return recs

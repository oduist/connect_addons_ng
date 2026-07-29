import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)


class ProjectCall(models.Model):
    _inherit = 'connect.call'

    task = fields.Many2one('project.task', ondelete='set null', tracking=True)
    project = fields.Many2one('project.project', ondelete='set null', tracking=True)
    ref = fields.Reference(selection_add=[
        ('project.task', 'Task'), ('project.project', 'Project')])

    def _get_ref(self):
        for rec in self:
            if rec.task:
                rec.ref = 'project.task,{}'.format(rec.task.id)
            elif rec.project:
                rec.ref = 'project.project,{}'.format(rec.project.id)
            else:
                super(ProjectCall, rec)._get_ref()

    @api.model
    def process_call_event(self, channel, error_data=None):
        call_id = super().process_call_event(channel, error_data=error_data)
        if not call_id:
            return call_id
        if not self.env['oduist.license'].check_license('connect_project', silent=True):
            return call_id
        call = self.browse(call_id)
        try:
            if not call.task and not call.project and call.partner:
                task = self.env['project.task'].sudo().search(
                    [('partner_id', '=', call.partner.id),
                     ('stage_id.fold', '=', False)], order='id desc', limit=1)
                if task:
                    debug(self, 'Call {} assign task <{}> "{}"'.format(
                        call.id, task.id, task.name))
                    call.task = task
                else:
                    project = self.env['project.project'].sudo().search(
                        [('partner_id', '=', call.partner.id)], order='id desc', limit=1)
                    if project:
                        debug(self, 'Call {} assign project <{}> "{}"'.format(
                            call.id, project.id, project.name))
                        call.project = project
        except Exception:
            logger.exception('Project process_call_event error:')
        return call_id

    def create_task_button(self):
        self.ensure_one()
        if not self.env['oduist.license'].check_license('connect_project', silent=True):
            raise ValidationError('Connect Project license is not activated!')
        context = {
            'connect_call_id': self.id,
            'default_partner_id': self.partner.id,
            'default_name': 'Call from {}'.format(self.partner.name or self.caller),
        }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'res_id': self.task.id if self.task else False,
            'name': self.task.name if self.task else 'New Task',
            'view_mode': 'form',
            'target': 'current',
            'context': context,
        }

    def unlink_task(self):
        self.ensure_one()
        self.task = False
        self.project = False

    def get_widget_fields(self):
        fields = super().get_widget_fields()
        fields.append('task')
        fields.append('project')
        return fields

    @api.constrains('summary')
    def register_project_call_summary(self):
        if not self.env['oduist.license'].check_license('connect_project', silent=True):
            return False
        if not self.env['connect.settings'].sudo().get_param('register_summary'):
            return
        reload_view = False
        for rec in self:
            target = rec.task or rec.project
            if target and rec.summary:
                self.register_summary_to_rec(target, rec.summary)
                reload_view = True
        if reload_view:
            self.env['connect.settings'].connect_reload_view('project.task')

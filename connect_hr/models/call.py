import logging

from odoo import api, fields, models

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)


class HrCall(models.Model):
    _inherit = 'connect.call'

    employee = fields.Many2one('hr.employee', ondelete='set null', tracking=True)
    ref = fields.Reference(selection_add=[('hr.employee', 'Employee')])

    def _get_ref(self):
        for rec in self:
            if rec.employee:
                rec.ref = 'hr.employee,{}'.format(rec.employee.id)
            else:
                super(HrCall, rec)._get_ref()

    @api.model
    def process_call_event(self, channel, error_data=None):
        call_id = super().process_call_event(channel, error_data=error_data)
        if not call_id:
            return call_id
        if not self.env['oduist.license'].check_license('connect_hr', silent=True):
            return call_id
        call = self.browse(call_id)
        try:
            if not call.employee:
                number = call.caller if call.direction == 'incoming' else call.called
                employee = self.env['hr.employee'].get_employee_by_number(number)
                if employee:
                    debug(self, 'Call {} assign employee <{}> "{}"'.format(
                        call.id, employee.id, employee.name))
                    call.employee = employee
        except Exception:
            logger.exception('HR process_call_event error:')
        return call_id

    def unlink_employee(self):
        self.ensure_one()
        self.employee = False

    def get_widget_fields(self):
        fields = super().get_widget_fields()
        fields.append('employee')
        return fields

    def _get_registration_targets(self):
        targets = super()._get_registration_targets()
        if not self.env['oduist.license'].check_license('connect_hr', silent=True):
            return targets
        record = self.employee
        if record:
            targets.append(record)
        return targets

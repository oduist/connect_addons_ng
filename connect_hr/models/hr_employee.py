import logging

from odoo import api, fields, models

from odoo.addons.connect.models.settings import debug, MAX_EXTEN_LEN
from odoo.addons.connect.models.res_partner import strip_number

logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    connect_calls = fields.One2many('connect.call', 'employee')
    connect_calls_count = fields.Integer(
        compute='_get_connect_calls_count', string='Calls', store=True,
    )
    phone_normalized = fields.Char(
        compute='_get_phone_normalized', index=True, store=True,
    )
    mobile_normalized = fields.Char(
        compute='_get_phone_normalized', index=True, store=True,
    )

    @api.depends('connect_calls')
    def _get_connect_calls_count(self):
        for rec in self:
            rec.connect_calls_count = self.env['connect.call'].search_count(
                [('employee', '=', rec.id)],
            )

    @api.depends('work_phone', 'mobile_phone')
    def _get_phone_normalized(self):
        for rec in self:
            rec.phone_normalized = (
                self.env['res.partner']._normalize_phone(rec.work_phone)
                if rec.work_phone else False
            )
            rec.mobile_normalized = (
                self.env['res.partner']._normalize_phone(rec.mobile_phone)
                if rec.mobile_phone else False
            )

    def _search_employee_by_number(self, number):
        found = self.env['hr.employee'].sudo().search(
            ['|', ('phone_normalized', '=', number), ('mobile_normalized', '=', number)],
            order='id desc',
        )
        debug(self, 'Number {} belongs to employees: {}'.format(number, found.mapped('id')))
        return found[:1]

    def get_employee_by_number(self, number, country=None):
        number = strip_number(number)
        if not number or len(number) < MAX_EXTEN_LEN:
            return self.env['hr.employee']
        employee = self._search_employee_by_number('+{}'.format(number))
        if employee:
            return employee
        employee = self._search_employee_by_number(number)
        if employee:
            return employee
        return self.env['hr.employee']

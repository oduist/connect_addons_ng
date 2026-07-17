# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResourceCalendarLeaves(models.Model):
    _inherit = 'resource.calendar.leaves'

    prompt_message = fields.Text(
        help='Optional message played to callers when an inbound call '
             'arrives during this public holiday / closure.')

    def _schedule_affected_calendars(self):
        """Calendars whose connect.schedule slots depend on these leaves.

        Schedules only consider global leaves (global_leave_ids, i.e.
        resource_id=False), so resource-specific leaves (e.g. employee
        time off from hr_holidays) never change any schedule and must not
        trigger a slot rebuild.
        """
        return self.filtered(lambda l: not l.resource_id).calendar_id

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env['connect.schedule'].regenerate_slots_for_calendars(
            records._schedule_affected_calendars())
        return records

    def write(self, vals):
        calendars_before = self._schedule_affected_calendars()
        res = super().write(vals)
        self.env['connect.schedule'].regenerate_slots_for_calendars(
            calendars_before | self._schedule_affected_calendars())
        return res

    def unlink(self):
        calendars = self._schedule_affected_calendars()
        res = super().unlink()
        self.env['connect.schedule'].regenerate_slots_for_calendars(calendars)
        return res

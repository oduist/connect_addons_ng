# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResourceCalendarLeaves(models.Model):
    _inherit = 'resource.calendar.leaves'

    prompt_message = fields.Text(
        help='Optional message played to callers when an inbound call '
             'arrives during this public holiday / closure.')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env['connect.schedule'].regenerate_slots_for_calendars(
            records.calendar_id)
        return records

    def write(self, vals):
        calendars_before = self.calendar_id
        res = super().write(vals)
        self.env['connect.schedule'].regenerate_slots_for_calendars(
            calendars_before | self.calendar_id)
        return res

    def unlink(self):
        calendars = self.calendar_id
        res = super().unlink()
        self.env['connect.schedule'].regenerate_slots_for_calendars(calendars)
        return res

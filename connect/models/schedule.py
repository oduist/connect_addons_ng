# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta, time

import pytz
from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Default number of days materialized as availability slots and scanned
# when searching for the next opening moment.
DEFAULT_HORIZON_DAYS = 60
HORIZON_PARAM = 'connect.schedule_slot_horizon_days'


def float_to_local_datetime(day, value, tz):
    """Convert a float hour (e.g. 8.5) on a date into a tz-aware datetime.

    24.0 maps to midnight of the next day so a window may end exactly at
    the end of the day.
    """
    if value >= 24.0:
        return tz.localize(datetime.combine(day + timedelta(days=1), time.min))
    hours = int(value)
    minutes = int(round((value - hours) * 60))
    if minutes == 60:
        hours, minutes = hours + 1, 0
    return tz.localize(datetime.combine(day, time(hours, minutes)))


class Schedule(models.Model):
    _name = 'connect.schedule'
    _description = 'Working Schedule'
    _order = 'name'

    name = fields.Char(required=True)
    calendar_id = fields.Many2one(
        'resource.calendar', string='Working Hours', required=True,
        ondelete='restrict',
        help='Weekly working hours and timezone. The calendar\'s global '
             'time off entries act as public holidays.')
    tz = fields.Selection(related='calendar_id.tz')
    special_day_ids = fields.Many2many(
        'connect.schedule.special_day',
        'connect_schedule_special_day_rel', 'schedule_id', 'special_day_id',
        string='Special Working Days')
    holiday_ids = fields.One2many(
        related='calendar_id.global_leave_ids', string='Public Holidays',
        readonly=False)
    slot_ids = fields.One2many('connect.schedule.slot', 'schedule_id')
    preview_html = fields.Html(
        string='Preview', compute='_compute_preview_html', sanitize=False)

    def _get_tz(self):
        self.ensure_one()
        return pytz.timezone(self.calendar_id.tz or 'UTC')

    @api.model
    def _get_horizon_days(self):
        try:
            return int(self.env['ir.config_parameter'].sudo().get_param(
                HORIZON_PARAM, DEFAULT_HORIZON_DAYS))
        except (TypeError, ValueError):
            return DEFAULT_HORIZON_DAYS

    # -------------------------------------------------------------------
    # Evaluation engine
    # -------------------------------------------------------------------

    def _get_calendar_intervals(self, date_start, days):
        """Raw attendance and global-leave intervals over [date_start,
        date_start + days), as tz-aware (start, stop, records) tuples in
        the calendar timezone.
        """
        self.ensure_one()
        tz = self._get_tz()
        start_dt = tz.localize(datetime.combine(date_start, time.min))
        stop_dt = start_dt + timedelta(days=days)
        calendar = self.calendar_id
        attendances = calendar._attendance_intervals_batch(
            start_dt, stop_dt)[False]
        leaves = calendar._leave_intervals_batch(start_dt, stop_dt)[False]
        att = [(s.astimezone(tz), e.astimezone(tz), r) for s, e, r in attendances]
        lv = [(s.astimezone(tz), e.astimezone(tz), r) for s, e, r in leaves]
        return att, lv

    def get_day_data(self, date_start, days):
        """Per-day effective working windows with all contributing layers.

        Returns a list of dicts, one per day:
        - date: the day (in the calendar timezone)
        - windows: effective [(start, stop)] tz-aware local datetimes
        - attendances: raw weekly-calendar [(start, stop)] for that day
        - leaves: [(start, stop, leave record)] clipped to that day
        - specials: [(start, stop, special day record)]
        - source: 'special' | 'holiday' | 'schedule' — layer that decided
          the day (holiday only when leaves closed an otherwise open day)
        - label: name(s) of the special days / leaves shaping the day
        """
        self.ensure_one()
        tz = self._get_tz()
        attendances, leaves = self._get_calendar_intervals(date_start, days)
        specials_by_date = {}
        for special in self.special_day_ids:
            specials_by_date.setdefault(special.date, []).append(special)

        result = []
        for offset in range(days):
            day = date_start + timedelta(days=offset)
            day_start = tz.localize(datetime.combine(day, time.min))
            day_stop = day_start + timedelta(days=1)
            day_att = [(s, e) for s, e, _r in attendances
                       if s < day_stop and e > day_start]
            day_leaves = [(max(s, day_start), min(e, day_stop), r)
                          for s, e, r in leaves
                          if s < day_stop and e > day_start]
            day_specials = sorted(
                specials_by_date.get(day, []), key=lambda d: d.work_from)

            data = {
                'date': day,
                'attendances': day_att,
                'leaves': day_leaves,
                'specials': [],
                'windows': [],
                'source': 'schedule',
                'label': False,
            }
            if day_specials:
                # Special working days fully define the day and override
                # both the weekly schedule and public holidays.
                windows = [
                    (float_to_local_datetime(day, d.work_from, tz),
                     float_to_local_datetime(day, d.work_to, tz), d)
                    for d in day_specials]
                data['specials'] = windows
                data['windows'] = [(s, e) for s, e, _d in windows]
                data['source'] = 'special'
                data['label'] = ', '.join(d.name for d in day_specials)
            else:
                windows = []
                for att_start, att_stop in day_att:
                    parts = [(att_start, att_stop)]
                    for lv_start, lv_stop, _r in day_leaves:
                        parts = [
                            piece
                            for start, stop in parts
                            for piece in (
                                (start, min(stop, lv_start)),
                                (max(start, lv_stop), stop),
                            )
                            if piece[0] < piece[1]]
                    windows.extend(parts)
                data['windows'] = sorted(windows)
                if day_leaves:
                    data['label'] = ', '.join(
                        r.name for _s, _e, r in day_leaves if r.name)
                    if day_att and not windows:
                        data['source'] = 'holiday'
            result.append(data)
        return result

    def get_status(self, at_dt=None):
        """Availability of the schedule at a given moment.

        :param at_dt: naive UTC datetime (defaults to now)
        :return: dict with keys:
            available (bool), source ('special'|'holiday'|'schedule'),
            label (str|False), prompt_message (str|False, holiday message
            to play to the caller), until (naive UTC datetime the current
            open window ends, when available), next_open (naive UTC
            datetime of the next opening moment, when unavailable).
        """
        self.ensure_one()
        tz = self._get_tz()
        now_utc = at_dt or fields.Datetime.now()
        now = pytz.utc.localize(now_utc).astimezone(tz)
        day_data = self.get_day_data(now.date(), 1)[0]

        status = {
            'available': False,
            'source': day_data['source'],
            'label': day_data['label'],
            'prompt_message': False,
            'until': False,
            'next_open': False,
        }
        for start, stop in day_data['windows']:
            if start <= now < stop:
                status['available'] = True
                status['until'] = stop.astimezone(pytz.utc).replace(tzinfo=None)
                return status

        # Closed: identify the layer that closed this very moment and
        # find the next opening.
        if day_data['source'] != 'special':
            active_leaves = [
                r for start, stop, r in day_data['leaves']
                if start <= now < stop]
            if active_leaves:
                status['source'] = 'holiday'
                status['label'] = ', '.join(
                    r.name for r in active_leaves if r.name) or status['label']
                prompts = [
                    r.prompt_message for r in active_leaves
                    if r.prompt_message]
                status['prompt_message'] = prompts[0] if prompts else False
        status['next_open'] = self._get_next_open(now)
        return status

    def _get_next_open(self, now):
        """Next opening moment after ``now`` (tz-aware local), as a naive
        UTC datetime, scanning up to the configured horizon."""
        self.ensure_one()
        horizon = self._get_horizon_days()
        for day_data in self.get_day_data(now.date(), horizon):
            for start, _stop in day_data['windows']:
                if start > now:
                    return start.astimezone(pytz.utc).replace(tzinfo=None)
        return False

    # -------------------------------------------------------------------
    # Form preview
    # -------------------------------------------------------------------

    @api.depends('calendar_id', 'special_day_ids',
                 'calendar_id.attendance_ids', 'calendar_id.global_leave_ids')
    def _compute_preview_html(self):
        for rec in self:
            if not rec.calendar_id:
                rec.preview_html = False
                continue
            tz = rec._get_tz()
            today = datetime.now(tz).date()
            rows = []
            for day in rec.get_day_data(today, 14):
                if day['windows']:
                    hours = ', '.join(
                        '{:%H:%M} – {:%H:%M}'.format(s, e)
                        for s, e in day['windows'])
                else:
                    hours = self.env._('Closed')
                label = ' ({})'.format(escape(day['label'])) if day['label'] else ''
                rows.append(
                    '<tr><td class="pe-3">{:%A, %d.%m.%Y}</td>'
                    '<td>{}{}</td></tr>'.format(
                        day['date'], escape(hours), label))
            rec.preview_html = Markup(
                '<table class="table table-sm o_main_table">{}</table>'.format(
                    ''.join(rows)))

    # -------------------------------------------------------------------
    # Slot materialization
    # -------------------------------------------------------------------

    @api.model
    def _cron_generate_slots(self):
        self.search([]).generate_slots()

    def generate_slots(self):
        """Rebuild the availability slots of these schedules over the
        rolling horizon. Slots are derived data: safe to delete and
        recreate at any time."""
        horizon = self._get_horizon_days()
        Slot = self.env['connect.schedule.slot'].sudo()
        for rec in self:
            tz = rec._get_tz()
            today = datetime.now(tz).date()
            rec.slot_ids.sudo().unlink()
            vals_list = []

            def utc(dt_local):
                return dt_local.astimezone(pytz.utc).replace(tzinfo=None)

            for day in rec.get_day_data(today, horizon):
                day_start = tz.localize(
                    datetime.combine(day['date'], time.min))
                day_stop = day_start + timedelta(days=1)
                for start, stop in day['windows']:
                    vals_list.append({
                        'schedule_id': rec.id,
                        'slot_type': 'available',
                        'name': '{}: {}'.format(
                            rec.name, self.env._('Available')),
                        'start': utc(start), 'stop': utc(stop),
                    })
                for start, stop in day['attendances']:
                    vals_list.append({
                        'schedule_id': rec.id,
                        'slot_type': 'schedule',
                        'name': '{}: {}'.format(
                            rec.name, self.env._('Working Schedule')),
                        'start': utc(start), 'stop': utc(stop),
                    })
                for start, stop, leave in day['leaves']:
                    allday = start <= day_start and stop >= day_stop
                    vals_list.append({
                        'schedule_id': rec.id,
                        'slot_type': 'holiday',
                        'name': '{}: {}'.format(
                            rec.name,
                            leave.name or self.env._('Public Holiday')),
                        'start': utc(start),
                        # All-day events ending exactly at next midnight
                        # would render on the next day too.
                        'stop': utc(stop - timedelta(seconds=1))
                        if allday else utc(stop),
                        'allday': allday,
                    })
                for start, stop, special in day['specials']:
                    vals_list.append({
                        'schedule_id': rec.id,
                        'slot_type': 'special',
                        'name': '{}: {}'.format(rec.name, special.name),
                        'start': utc(start), 'stop': utc(stop),
                    })
                if not day['windows']:
                    vals_list.append({
                        'schedule_id': rec.id,
                        'slot_type': 'closed',
                        'name': '{}: {}'.format(
                            rec.name, self.env._('Closed')),
                        'start': utc(day_start),
                        'stop': utc(day_stop - timedelta(seconds=1)),
                        'allday': True,
                    })
            Slot.create(vals_list)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.generate_slots()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'calendar_id' in vals or 'special_day_ids' in vals:
            self.generate_slots()
        return res

    @api.model
    def regenerate_slots_for_calendars(self, calendars):
        """Rebuild slots of all schedules using any of the given
        resource.calendar records (called from leave/attendance hooks)."""
        if calendars:
            self.search([('calendar_id', 'in', calendars.ids)]).generate_slots()

    def action_view_slots(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Availability'),
            'res_model': 'connect.schedule.slot',
            'view_mode': 'calendar,list',
            'domain': [('schedule_id', '=', self.id)],
            'context': {
                'search_default_filter_available': 1,
                'search_default_filter_closed': 1,
            },
        }


class ScheduleSpecialDay(models.Model):
    _name = 'connect.schedule.special_day'
    _description = 'Special Working Day'
    _order = 'date desc, work_from'

    name = fields.Char(required=True)
    date = fields.Date(required=True)
    work_from = fields.Float(string='Work From', required=True)
    work_to = fields.Float(string='Work To', required=True)
    schedule_ids = fields.Many2many(
        'connect.schedule',
        'connect_schedule_special_day_rel', 'special_day_id', 'schedule_id',
        string='Working Schedules')

    @api.depends('name', 'date')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '{} ({})'.format(rec.name, rec.date or '')

    @api.constrains('work_from', 'work_to')
    def _check_times(self):
        for rec in self:
            if not (0.0 <= rec.work_from < 24.0) or not (0.0 < rec.work_to <= 24.0):
                raise ValidationError(
                    'Special working day times must be within 00:00-24:00!')
            if rec.work_from >= rec.work_to:
                raise ValidationError(
                    'Special working day "Work From" must be before "Work To"! '
                    'To close a full day use a public holiday instead.')

    @api.constrains('date', 'work_from', 'work_to', 'schedule_ids')
    def _check_overlap(self):
        for rec in self:
            for schedule in rec.schedule_ids:
                others = (schedule.special_day_ids - rec).filtered(
                    lambda o: o.date == rec.date)
                for other in others:
                    if rec.work_from < other.work_to and \
                            other.work_from < rec.work_to:
                        raise ValidationError(
                            'Special working days "{}" and "{}" overlap on '
                            '{} for schedule "{}"!'.format(
                                rec.name, other.name, rec.date,
                                schedule.name))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.schedule_ids.generate_slots()
        return records

    def write(self, vals):
        schedules_before = self.schedule_ids
        res = super().write(vals)
        (schedules_before | self.schedule_ids).generate_slots()
        return res

    def unlink(self):
        schedules = self.schedule_ids
        res = super().unlink()
        schedules.generate_slots()
        return res


class ScheduleSlot(models.Model):
    _name = 'connect.schedule.slot'
    _description = 'Working Schedule Availability Slot'
    _order = 'start'

    schedule_id = fields.Many2one(
        'connect.schedule', required=True, ondelete='cascade', index=True)
    name = fields.Char(required=True)
    start = fields.Datetime(required=True)
    stop = fields.Datetime(required=True)
    slot_type = fields.Selection([
        ('available', 'Available'),
        ('schedule', 'Working Schedule'),
        ('holiday', 'Public Holiday'),
        ('special', 'Special Working Day'),
        ('closed', 'Closed'),
    ], required=True, index=True)
    allday = fields.Boolean('All Day')

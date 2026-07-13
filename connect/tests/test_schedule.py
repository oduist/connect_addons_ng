# -*- coding: utf-8 -*-
from datetime import datetime, date, timedelta

import pytz

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged, new_test_user

from .common import ConnectTestCommon


@tagged('at_install', '-post_install')
class TestSchedule(ConnectTestCommon):
    """Working schedule evaluation engine.

    The calendar works Mon-Fri 08:00-12:00 and 13:00-17:00 in
    Europe/Zurich. All test dates are in August 2026 (CEST, UTC+2):
    local 08:00 == 06:00 UTC. 2026-08-10 is a Monday.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        attendances = []
        for dayofweek in range(5):
            attendances.extend([
                (0, 0, {
                    'name': 'Morning', 'dayofweek': str(dayofweek),
                    'hour_from': 8.0, 'hour_to': 12.0,
                    'day_period': 'morning',
                }),
                (0, 0, {
                    'name': 'Afternoon', 'dayofweek': str(dayofweek),
                    'hour_from': 13.0, 'hour_to': 17.0,
                    'day_period': 'afternoon',
                }),
            ])
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'Office Hours',
            'tz': 'Europe/Zurich',
            'attendance_ids': attendances,
        })
        cls.schedule = cls.env['connect.schedule'].create({
            'name': 'Office',
            'calendar_id': cls.calendar.id,
        })

    def _status(self, at_dt):
        return self.schedule.get_status(at_dt=at_dt)

    def test_open_during_working_hours(self):
        # Wednesday 2026-08-12 09:00 local == 07:00 UTC.
        status = self._status(datetime(2026, 8, 12, 7, 0))
        self.assertTrue(status['available'])
        self.assertEqual(status['source'], 'schedule')
        # Open until 12:00 local == 10:00 UTC.
        self.assertEqual(status['until'], datetime(2026, 8, 12, 10, 0))

    def test_closed_lunch_and_evening(self):
        # Lunch break 12:30 local == 10:30 UTC.
        status = self._status(datetime(2026, 8, 12, 10, 30))
        self.assertFalse(status['available'])
        # Next open 13:00 local == 11:00 UTC same day.
        self.assertEqual(status['next_open'], datetime(2026, 8, 12, 11, 0))
        # Evening 20:00 local == 18:00 UTC -> next open Thursday 08:00.
        status = self._status(datetime(2026, 8, 12, 18, 0))
        self.assertFalse(status['available'])
        self.assertEqual(status['next_open'], datetime(2026, 8, 13, 6, 0))

    def test_closed_weekend_next_open_monday(self):
        # Saturday 2026-08-15 10:00 local.
        status = self._status(datetime(2026, 8, 15, 8, 0))
        self.assertFalse(status['available'])
        self.assertEqual(status['source'], 'schedule')
        # Next open Monday 2026-08-17 08:00 local == 06:00 UTC.
        self.assertEqual(status['next_open'], datetime(2026, 8, 17, 6, 0))

    def test_holiday_closes_day_with_prompt(self):
        # Friday 2026-08-14, full local day.
        self.env['resource.calendar.leaves'].create({
            'name': 'Swiss National Holiday',
            'calendar_id': self.calendar.id,
            'date_from': datetime(2026, 8, 13, 22, 0),
            'date_to': datetime(2026, 8, 14, 22, 0),
            'prompt_message': 'We are closed today.',
        })
        status = self._status(datetime(2026, 8, 14, 7, 0))
        self.assertFalse(status['available'])
        self.assertEqual(status['source'], 'holiday')
        self.assertEqual(status['label'], 'Swiss National Holiday')
        self.assertEqual(status['prompt_message'], 'We are closed today.')
        # Next open Monday.
        self.assertEqual(status['next_open'], datetime(2026, 8, 17, 6, 0))

    def test_partial_day_leave_shortens_hours(self):
        # Thursday 2026-08-13, leave 15:00-17:00 local == 13:00-15:00 UTC.
        self.env['resource.calendar.leaves'].create({
            'name': 'Team event',
            'calendar_id': self.calendar.id,
            'date_from': datetime(2026, 8, 13, 13, 0),
            'date_to': datetime(2026, 8, 13, 15, 0),
        })
        day = self.schedule.get_day_data(date(2026, 8, 13), 1)[0]
        # 08:00-12:00 and 13:00-15:00 remain.
        self.assertEqual(len(day['windows']), 2)
        self.assertEqual(day['windows'][1][1].hour, 15)
        self.assertEqual(day['label'], 'Team event')
        self.assertEqual(day['source'], 'schedule')
        # Open at 14:00 local, closed at 16:00 local.
        self.assertTrue(self._status(datetime(2026, 8, 13, 12, 0))['available'])
        status = self._status(datetime(2026, 8, 13, 14, 0))
        self.assertFalse(status['available'])
        self.assertEqual(status['source'], 'holiday')

    def test_special_day_overrides_holiday(self):
        self.env['resource.calendar.leaves'].create({
            'name': 'Swiss National Holiday',
            'calendar_id': self.calendar.id,
            'date_from': datetime(2026, 8, 13, 22, 0),
            'date_to': datetime(2026, 8, 14, 22, 0),
            'prompt_message': 'We are closed today.',
        })
        self.env['connect.schedule.special_day'].create({
            'name': 'Emergency line open',
            'date': date(2026, 8, 14),
            'work_from': 10.0,
            'work_to': 14.0,
            'schedule_ids': [(4, self.schedule.id)],
        })
        # 11:00 local == 09:00 UTC -> open despite the holiday.
        status = self._status(datetime(2026, 8, 14, 9, 0))
        self.assertTrue(status['available'])
        self.assertEqual(status['source'], 'special')
        # 09:00 local -> closed, but no holiday prompt: the special day
        # fully defines the date.
        status = self._status(datetime(2026, 8, 14, 7, 0))
        self.assertFalse(status['available'])
        self.assertEqual(status['source'], 'special')
        self.assertFalse(status['prompt_message'])
        # Next open is the special window at 10:00 local == 08:00 UTC.
        self.assertEqual(status['next_open'], datetime(2026, 8, 14, 8, 0))

    def test_special_day_extends_hours_on_weekend(self):
        self.env['connect.schedule.special_day'].create({
            'name': 'Saturday sale',
            'date': date(2026, 8, 15),
            'work_from': 9.0,
            'work_to': 11.0,
            'schedule_ids': [(4, self.schedule.id)],
        })
        # Saturday 10:00 local == 08:00 UTC -> open.
        status = self._status(datetime(2026, 8, 15, 8, 0))
        self.assertTrue(status['available'])
        self.assertEqual(status['source'], 'special')
        self.assertEqual(status['until'], datetime(2026, 8, 15, 9, 0))

    def test_multiple_special_windows_same_date(self):
        for hours in [(8.0, 12.0), (13.0, 16.0)]:
            self.env['connect.schedule.special_day'].create({
                'name': 'Window %s' % hours[0],
                'date': date(2026, 8, 15),
                'work_from': hours[0],
                'work_to': hours[1],
                'schedule_ids': [(4, self.schedule.id)],
            })
        day = self.schedule.get_day_data(date(2026, 8, 15), 1)[0]
        self.assertEqual(len(day['windows']), 2)
        self.assertEqual(day['source'], 'special')

    def test_special_day_overlap_rejected(self):
        self.env['connect.schedule.special_day'].create({
            'name': 'First',
            'date': date(2026, 8, 15),
            'work_from': 8.0,
            'work_to': 12.0,
            'schedule_ids': [(4, self.schedule.id)],
        })
        with self.assertRaises(ValidationError):
            self.env['connect.schedule.special_day'].create({
                'name': 'Second',
                'date': date(2026, 8, 15),
                'work_from': 11.0,
                'work_to': 14.0,
                'schedule_ids': [(4, self.schedule.id)],
            })

    def test_special_day_invalid_times_rejected(self):
        with self.assertRaises(ValidationError):
            self.env['connect.schedule.special_day'].create({
                'name': 'Backwards',
                'date': date(2026, 8, 15),
                'work_from': 14.0,
                'work_to': 10.0,
            })

    def test_slots_generated(self):
        slots = self.schedule.slot_ids
        self.assertTrue(slots)
        types = set(slots.mapped('slot_type'))
        # Working days produce available+schedule, weekends produce closed.
        self.assertIn('available', types)
        self.assertIn('schedule', types)
        self.assertIn('closed', types)
        # Weekend all-day closed markers exist.
        self.assertTrue(slots.filtered(
            lambda s: s.slot_type == 'closed' and s.allday))

    def test_slots_regenerated_on_special_day(self):
        # A date safely inside the slot horizon, in the calendar timezone
        # (the slots' UTC start may fall on the previous local date).
        target = datetime.now(pytz.timezone('Europe/Zurich')).date() + \
            timedelta(days=7)
        special = self.env['connect.schedule.special_day'].create({
            'name': 'Extra day',
            'date': target,
            'work_from': 20.0,
            'work_to': 22.0,
            'schedule_ids': [(4, self.schedule.id)],
        })
        self.assertTrue(self.schedule.slot_ids.filtered(
            lambda s: s.slot_type == 'special'))
        special.unlink()
        self.assertFalse(self.schedule.slot_ids.filtered(
            lambda s: s.slot_type == 'special'))

    def test_preview_html(self):
        self.assertIn('table', self.schedule.preview_html)

    def test_user_access(self):
        connect_user = new_test_user(
            self.env, login='connect_schedule_user',
            groups='base.group_user,connect.group_user')
        schedule = self.env['connect.schedule'].with_user(connect_user)
        self.assertTrue(schedule.search([], limit=1))
        with self.assertRaises(AccessError):
            schedule.create({
                'name': 'Nope', 'calendar_id': self.calendar.id})
        with self.assertRaises(AccessError):
            self.schedule.with_user(connect_user).write({'name': 'Nope'})

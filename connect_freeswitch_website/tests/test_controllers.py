# -*- coding: utf-8 -*-
"""Public JSON endpoints backing the phone status / opening hours snippets."""
from datetime import datetime, timedelta

from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install', 'connect_freeswitch_website')
class TestScheduleEndpoints(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.open_calendar = cls.env['resource.calendar'].create({
            'name': 'Always Open',
            'tz': 'UTC',
            'attendance_ids': [
                (0, 0, {
                    'name': 'All day', 'dayofweek': str(day),
                    'hour_from': 0.0, 'hour_to': 24.0,
                }) for day in range(7)
            ],
        })
        cls.closed_calendar = cls.env['resource.calendar'].create({
            'name': 'Always Closed',
            'tz': 'UTC',
            'attendance_ids': [],
        })
        cls.open_schedule = cls.env['connect.schedule'].create({
            'name': 'Open Schedule', 'calendar_id': cls.open_calendar.id})
        cls.closed_schedule = cls.env['connect.schedule'].create({
            'name': 'Closed Schedule', 'calendar_id': cls.closed_calendar.id})
        cls.number = cls.env['connect.freeswitch.number'].create({
            'phone_number': '+41215121140',
            'schedule_enabled': True,
            'schedule_id': cls.open_schedule.id,
        })
        cls.closed_number = cls.env['connect.freeswitch.number'].create({
            'phone_number': '+41215121141',
            'schedule_enabled': True,
            'schedule_id': cls.closed_schedule.id,
        })
        cls.plain_number = cls.env['connect.freeswitch.number'].create({
            'phone_number': '+41215121142',
        })

    def test_status_available(self):
        resp = self.url_open(
            '/freeswitch/schedule/status/%d' % self.number.id)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['available'])
        self.assertEqual(data['phone_number'], '+41215121140')

    def test_status_unavailable(self):
        resp = self.url_open(
            '/freeswitch/schedule/status/%d' % self.closed_number.id)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data['available'])

    def test_status_no_schedule_404(self):
        resp = self.url_open(
            '/freeswitch/schedule/status/%d' % self.plain_number.id)
        self.assertEqual(resp.status_code, 404)

    def test_status_unknown_404(self):
        resp = self.url_open('/freeswitch/schedule/status/99999999')
        self.assertEqual(resp.status_code, 404)

    def test_opening_hours_days(self):
        resp = self.url_open(
            '/freeswitch/schedule/opening_hours/%d?days=5' % self.number.id)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['days']), 5)
        day = data['days'][0]
        self.assertFalse(day['closed'])
        self.assertIn('–', day['hours'])
        self.assertTrue(day['date_short'])
        self.assertTrue(day['date_long'])

    def test_opening_hours_days_clamped(self):
        resp = self.url_open(
            '/freeswitch/schedule/opening_hours/%d?days=500' % self.number.id)
        self.assertEqual(len(resp.json()['days']), 60)
        resp = self.url_open(
            '/freeswitch/schedule/opening_hours/%d?days=bogus' % self.number.id)
        self.assertEqual(len(resp.json()['days']), 10)

    def test_opening_hours_closed_calendar(self):
        resp = self.url_open(
            '/freeswitch/schedule/opening_hours/%d?days=3'
            % self.closed_number.id)
        data = resp.json()
        self.assertTrue(all(day['closed'] for day in data['days']))

    def test_opening_hours_holiday_label(self):
        now = datetime.utcnow()
        self.env['resource.calendar.leaves'].create({
            'name': 'Company Day',
            'calendar_id': self.open_calendar.id,
            'date_from': now - timedelta(days=1),
            'date_to': now + timedelta(days=1),
        })
        resp = self.url_open(
            '/freeswitch/schedule/opening_hours/%d?days=1' % self.number.id)
        day = resp.json()['days'][0]
        self.assertIn('Company Day', day['label'])

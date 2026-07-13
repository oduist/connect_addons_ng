# -*- coding: utf-8 -*-
"""Working-schedule routing on inbound DIDs (issue #57, ADR-037).

The schedule state is evaluated per call in generate_dialplan(): during
working hours the regular destination fields route the call, outside of
them the closed_* fields take over, and a public-holiday prompt_message
is spoken via piper TTS before the transfer.
"""
from datetime import datetime, timedelta

from odoo.tests import tagged, new_test_user
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "connect_freeswitch", "schedule_routing")
class TestScheduleRouting(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Number = cls.env["connect.freeswitch.number"]

        def make_user(login, exten_number):
            odoo_user = new_test_user(cls.env, login=login)
            user = cls.env["connect.user"].with_context(
                no_clear_cache=True).create({"user": odoo_user.id})
            exten = cls.env["connect.freeswitch.exten"].create({
                "number": exten_number,
                "model": "connect.user",
                "res_id": user.id,
            })
            user.freeswitch_exten = exten
            return user

        cls.day_user = make_user("fs_sched_day", "7021")
        cls.night_user = make_user("fs_sched_night", "7022")

        # A 24/7 calendar (always open) and an empty one (always closed)
        # make generate_dialplan() deterministic regardless of the real
        # clock the test runs at.
        cls.open_calendar = cls.env["resource.calendar"].create({
            "name": "Always Open",
            "tz": "UTC",
            "attendance_ids": [
                (0, 0, {
                    "name": "All day", "dayofweek": str(day),
                    "hour_from": 0.0, "hour_to": 24.0,
                }) for day in range(7)
            ],
        })
        cls.closed_calendar = cls.env["resource.calendar"].create({
            "name": "Always Closed",
            "tz": "UTC",
            "attendance_ids": [],
        })
        cls.open_schedule = cls.env["connect.schedule"].create({
            "name": "Open Schedule", "calendar_id": cls.open_calendar.id})
        cls.closed_schedule = cls.env["connect.schedule"].create({
            "name": "Closed Schedule", "calendar_id": cls.closed_calendar.id})

        cls.number = cls.Number.create({
            "phone_number": "+41215121140",
            "destination": "user",
            "user": cls.day_user.id,
            "closed_destination": "user",
            "closed_user": cls.night_user.id,
        })

    def _add_holiday_now(self, schedule, prompt=None):
        now = datetime.utcnow()
        return self.env["resource.calendar.leaves"].create({
            "name": "Holiday",
            "calendar_id": schedule.calendar_id.id,
            "date_from": now - timedelta(days=1),
            "date_to": now + timedelta(days=1),
            "prompt_message": prompt,
        })

    def test_schedule_disabled_routes_to_available(self):
        xml = self.number.generate_dialplan({})
        self.assertIn('data="7021 XML default"', xml)
        self.assertNotIn("speak", xml)

    def test_open_schedule_routes_to_available(self):
        self.number.write({
            "schedule_enabled": True,
            "schedule_id": self.open_schedule.id,
        })
        xml = self.number.generate_dialplan({})
        self.assertIn('data="7021 XML default"', xml)
        self.assertNotIn("speak", xml)

    def test_closed_schedule_routes_to_unavailable(self):
        self.number.write({
            "schedule_enabled": True,
            "schedule_id": self.closed_schedule.id,
        })
        xml = self.number.generate_dialplan({})
        self.assertIn('data="7022 XML default"', xml)
        self.assertNotIn('data="7021 XML default"', xml)
        # No holiday -> no prompt.
        self.assertNotIn("speak", xml)

    def test_holiday_prompt_spoken_before_transfer(self):
        self.number.write({
            "schedule_enabled": True,
            "schedule_id": self.open_schedule.id,
            "schedule_prompt_language": "de-DE",
        })
        self._add_holiday_now(
            self.open_schedule, prompt='Closed today & tomorrow <sorry>')
        xml = self.number.generate_dialplan({})
        self.assertIn('data="7022 XML default"', xml)
        self.assertIn('<action application="answer"/>', xml)
        # The prompt is XML-escaped and spoken in the configured language.
        self.assertIn(
            'data="piper|de-DE|Closed today &amp; tomorrow &lt;sorry&gt;"',
            xml)
        # The prompt must be spoken before the transfer action.
        self.assertLess(xml.index("piper|"), xml.index("7022 XML default"))

    def test_holiday_without_prompt_no_speak(self):
        self.number.write({
            "schedule_enabled": True,
            "schedule_id": self.open_schedule.id,
        })
        self._add_holiday_now(self.open_schedule)
        xml = self.number.generate_dialplan({})
        self.assertIn('data="7022 XML default"', xml)
        self.assertNotIn("speak", xml)

    def test_closed_without_destination_hangs_up_after_prompt(self):
        self.number.write({
            "schedule_enabled": True,
            "schedule_id": self.open_schedule.id,
            "closed_destination": False,
            "closed_user": False,
        })
        self._add_holiday_now(self.open_schedule, prompt="Closed.")
        xml = self.number.generate_dialplan({})
        self.assertIn("piper|", xml)
        self.assertIn('application="hangup"', xml)
        self.assertNotIn('application="respond"', xml)

    def test_closed_without_destination_no_prompt_404(self):
        self.number.write({
            "schedule_enabled": True,
            "schedule_id": self.closed_schedule.id,
            "closed_destination": False,
            "closed_user": False,
        })
        xml = self.number.generate_dialplan({})
        self.assertIn('application="respond" data="404"', xml)

    def test_closed_destination_cleared_on_type_change(self):
        self.assertTrue(self.number.closed_user)
        self.number.write({"closed_destination": "callflow"})
        self.assertFalse(self.number.closed_user)

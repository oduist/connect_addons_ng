# -*- coding: utf-8 -*-
"""Calendar tool webhooks the ElevenLabs agent calls during a conversation.

These routes are `auth='public'`: the request runs as the public user, and a
failure surfaces to the caller as "I am not able to create the booking" — so
both the access path and the timezone arithmetic are worth pinning.
"""
import json

from odoo.tests import HttpCase, tagged, new_test_user

AGENT_TOKEN = 'calendar_tool_test_token'


@tagged('post_install', '-at_install')
class TestCalendarTools(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['connect.settings'].sudo().set_param(
            'elevenlabs_agent_token', AGENT_TOKEN)
        cls.organizer = new_test_user(
            cls.env, login='el_calendar_owner', groups='base.group_user')

    def _post(self, path, payload, token=AGENT_TOKEN):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['x-elevenlabs-agent-token'] = token
        return self.url_open(
            '/connect_elevenlabs/' + path,
            data=json.dumps(payload),
            headers=headers,
        )

    def test_create_event_books_for_the_target_user(self):
        """The event is created despite the route running as the public user.

        with_user() after sudo() drops the sudo flag; the deferred write of
        the computed partner_ids was then checked as the public user and the
        route answered 403.
        """
        response = self._post('create_event', {
            'user_id': self.organizer.id,
            'name': 'Meeting with Jack',
            'start': '2026-08-25 14:00:00',
            'stop': '2026-08-25 15:00:00',
            'timezone': '2',
        })

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['status'], 201)
        event = self.env['calendar.event'].sudo().search(
            [('name', '=', 'Meeting with Jack'),
             ('user_id', '=', self.organizer.id)])
        self.assertEqual(len(event), 1)
        # 14:00 at UTC+2 is 12:00 UTC, and the event belongs to the user the
        # agent booked for -- not to the public user the request ran as.
        self.assertEqual(str(event.start), '2026-08-25 12:00:00')
        self.assertEqual(event.create_uid, self.organizer)

    def test_create_event_is_idempotent(self):
        payload = {
            'user_id': self.organizer.id,
            'name': 'Repeat booking',
            'start': '2026-08-26 09:00:00',
            'stop': '2026-08-26 10:00:00',
            'timezone': '2',
        }
        self._post('create_event', payload)

        again = self._post('create_event', payload)

        self.assertEqual(again.json()['status'], 200)
        self.assertEqual(again.json()['detail'], 'Event already exist!')
        self.assertEqual(self.env['calendar.event'].sudo().search_count(
            [('name', '=', 'Repeat booking')]), 1)

    def test_free_slots_are_labelled_in_the_caller_timezone(self):
        """East of UTC the day window used to come back as the day before."""
        response = self._post('get_available_slots', {
            'user_id': self.organizer.id,
            'start': '2026-08-27',
            'timezone': '2',
        })

        slots = response.json()
        self.assertEqual(slots, [{'start': '2026-08-27 08:00:00',
                                  'stop': '2026-08-27 18:00:00'}])

    def test_free_slots_split_around_a_booking(self):
        self._post('create_event', {
            'user_id': self.organizer.id,
            'name': 'Busy hour',
            'start': '2026-08-28 14:00:00',
            'stop': '2026-08-28 15:00:00',
            'timezone': '2',
        })

        slots = self._post('get_available_slots', {
            'user_id': self.organizer.id,
            'start': '2026-08-28',
            'timezone': '2',
        }).json()

        self.assertEqual([s['stop'] for s in slots][0], '2026-08-28 14:00:00')
        self.assertEqual([s['start'] for s in slots][1], '2026-08-28 15:00:00')

    def test_tools_reject_a_missing_token(self):
        response = self._post('create_event', {
            'user_id': self.organizer.id,
            'name': 'Unauthorized',
            'start': '2026-08-29 14:00:00',
            'stop': '2026-08-29 15:00:00',
        }, token=None)

        self.assertEqual(response.status_code, 401)
        self.assertFalse(self.env['calendar.event'].sudo().search_count(
            [('name', '=', 'Unauthorized')]))

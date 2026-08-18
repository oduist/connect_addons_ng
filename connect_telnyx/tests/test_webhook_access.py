# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.tests import tagged

from .common import TelnyxTestCommon


@tagged('post_install', '-at_install')
class TestTelnyxWebhookAccess(TelnyxTestCommon):
    """Webhook handlers run as the restricted webhook user, which has no
    access to connect.user and the PBX configuration models."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['connect.settings'].sudo().set_param('telnyx_auto_sync', False)
        cls.user = cls._create_web_phone_user('telnyx_webhook_acl')
        cls.exten = cls.env['connect.telnyx.exten'].create({
            'number': '101',
            'dst': 'connect.user,{}'.format(cls.user.id),
        })
        cls.callflow = cls.env['connect.telnyx.callflow'].create({
            'name': 'ACL IVR',
            'prompt_message': 'Press one.',
            'gather_input': True,
            'gather_digits': 1,
        })
        cls.env['connect.telnyx.callflow_choice'].create({
            'callflow': cls.callflow.id,
            'choice_digits': '1',
            'exten': cls.exten.id,
        })
        cls.webhook_user = cls.env.ref('connect.user_connect_webhook')

    def _as_webhook(self, model):
        return self.env[model].with_user(self.webhook_user)

    def test_gather_action_routes_to_a_user_choice(self):
        result = str(self._as_webhook('connect.telnyx.callflow').gather_action(
            self.callflow.id, {'Digits': '1'}))
        self.assertIn('<Dial', result)

    def test_gather_action_replays_prompt_on_invalid_input(self):
        result = str(self._as_webhook('connect.telnyx.callflow').gather_action(
            self.callflow.id, {'Digits': '9'}))
        self.assertIn('<Gather', result)

    def test_user_call_action_completed_dial_wins_over_parent_status(self):
        with patch.object(
                type(self.env['connect.user']), 'telnyx_render',
                autospec=True) as render:
            result = str(
                self._as_webhook('connect.user').telnyx_on_call_action(
                    self.user.id,
                    {
                        'CallStatus': 'in-progress',
                        'DialCallStatus': 'completed',
                    },
                )
            )

        render.assert_not_called()
        self.assertIn('<Hangup', result)
        self.assertNotIn('<Dial', result)
        self.assertNotIn('<Say', result)
        self.assertNotIn('<Record', result)

    def test_user_call_action_explicit_failure_advances(self):
        for status in ('busy', 'no-answer', 'failed', 'canceled'):
            with self.subTest(status=status), patch.object(
                    type(self.env['connect.user']), 'telnyx_render',
                    autospec=True, return_value='next-step') as render:
                result = self._as_webhook(
                    'connect.user'
                ).telnyx_on_call_action(
                    self.user.id,
                    {
                        'CallStatus': 'completed',
                        'DialCallStatus': status,
                    },
                )

            self.assertEqual(result, 'next-step')
            render.assert_called_once()

    def test_user_call_action_unknown_or_missing_status_hangs_up(self):
        requests = (
            {},
            {'DialCallStatus': ''},
            {'DialCallStatus': 'unexpected'},
        )
        for request in requests:
            with self.subTest(request=request), patch.object(
                    type(self.env['connect.user']), 'telnyx_render',
                    autospec=True) as render:
                result = str(
                    self._as_webhook(
                        'connect.user'
                    ).telnyx_on_call_action(self.user.id, request)
                )

            render.assert_not_called()
            self.assertIn('<Hangup', result)

    def test_user_call_action_uses_legacy_parent_status_fallback(self):
        with patch.object(
                type(self.env['connect.user']), 'telnyx_render',
                autospec=True, return_value='next-step') as render:
            result = self._as_webhook(
                'connect.user'
            ).telnyx_on_call_action(
                self.user.id, {'CallStatus': 'no-answer'}
            )

        self.assertEqual(result, 'next-step')
        render.assert_called_once()

        with patch.object(
                type(self.env['connect.user']), 'telnyx_render',
                autospec=True) as render:
            result = str(
                self._as_webhook('connect.user').telnyx_on_call_action(
                    self.user.id, {'CallStatus': 'completed'}
                )
            )

        render.assert_not_called()
        self.assertIn('<Hangup', result)

    def test_callflow_call_action_renders_the_next_step(self):
        result = str(self._as_webhook('connect.telnyx.callflow').on_call_action(
            self.callflow.id, {'DialCallStatus': 'no-answer'}))
        self.assertIn('<Response', result)

    def test_number_route_call_renders_for_the_webhook_user(self):
        number = self.env['connect.telnyx.number'].with_context(
            skip_telnyx_sync=True).create({
                'phone_number': '+15550004444',
                'sid': 'acl-number',
                'destination': 'user',
                'user': self.user.id,
            })
        with patch.object(type(self.env['connect.call']),
                          'on_telnyx_call_status', autospec=True):
            result = str(self._as_webhook('connect.telnyx.number').route_call({
                'To': number.phone_number,
                'Called': number.phone_number,
                'CallSid': 'acl-call',
            }))
        self.assertIn('<Dial', result)

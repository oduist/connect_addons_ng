# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import BirdTestCommon, BirdApiMock, patch_bird_request


@tagged('at_install', '-post_install')
class TestBirdMessageStatus(BirdTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.number = cls._make_number('+15550001', 'sms')

    def _make_message(self, bird_id='m1', status='sent'):
        return self.env['connect.message'].sudo().create({
            'bird_message_id': bird_id,
            'bird_number': self.number.id,
            'from_number': self.number.number,
            'to_number': '+31612345678',
            'body': 'out',
            'status': status,
        })

    def test_status_from_event_name(self):
        message = self._make_message('m-status')
        self.env['connect.message'].update_bird_status(
            {'sms_id': 'm-status', 'to': '+31612345678',
             'from': '+15550001'},
            'sms.delivered')
        self.assertEqual(message.status, 'delivered')

    def test_failed_event_sets_error(self):
        message = self._make_message('m-fail')
        self.env['connect.message'].update_bird_status({
            'sms_id': 'm-fail',
            'to': '+31612345678',
            'from': '+15550001',
            'error': {'code': 'blocked_by_carrier',
                      'description': 'Carrier rejected'},
        }, 'sms.undelivered')
        self.assertEqual(message.status, 'failed')
        self.assertTrue(message.has_error)
        self.assertEqual(message.error_code, 'blocked_by_carrier')
        self.assertEqual(message.error_message, 'Carrier rejected')

    def test_rejected_with_last_error(self):
        # Message objects carry the failure as last_error (live shape:
        # insufficient_balance on the probe workspace).
        message = self._make_message('m-rej')
        self.env['connect.message'].update_bird_status({
            'sms_id': 'm-rej',
            'to': '+31612345678',
            'from': '+15550001',
            'last_error': {'code': 'insufficient_balance',
                           'description': 'insufficient wallet balance',
                           'carrier_error_code': None},
        }, 'sms.rejected')
        self.assertEqual(message.status, 'failed')
        self.assertTrue(message.has_error)
        self.assertEqual(message.error_code, 'insufficient_balance')
        self.assertEqual(message.error_message,
                         'insufficient wallet balance')

    def test_poll_status_updates_from_message_object(self):
        # No sms.* webhook subscriptions exist on the platform yet: the
        # cron polls GET /v1/sms/messages/{id} (live rejected shape).
        message = self._make_message('sms_poll1')
        wa_message = self._make_message('wam_poll2')
        mock = BirdApiMock({
            ('GET', '/sms/messages/sms_poll1'): {
                'id': 'sms_poll1',
                'status': 'rejected',
                'last_error': {'code': 'insufficient_balance',
                               'description': 'insufficient wallet balance'},
            },
            ('GET', '/whatsapp/messages/wam_poll2'): {
                'id': 'wam_poll2',
                'status': 'delivered',
                'last_error': None,
            },
        })
        with patch_bird_request(mock):
            self.env['connect.message']._cron_poll_bird_status()
        self.assertEqual(message.status, 'failed')
        self.assertTrue(message.has_error)
        self.assertEqual(message.error_code, 'insufficient_balance')
        self.assertEqual(wa_message.status, 'delivered')
        self.assertFalse(wa_message.has_error)
        # Terminal statuses are not polled again.
        with patch_bird_request(mock):
            self.env['connect.message']._cron_poll_bird_status()
        self.assertEqual(len(mock.calls), 2)

    def test_unknown_message_upserted(self):
        # A message sent outside Odoo (or a webhook racing our send
        # commit) creates an outgoing ledger row.
        self.env['connect.message'].update_bird_status({
            'whatsapp_id': 'm-external',
            'from': '+15550001',
            'to': '+31687654321',
        }, 'whatsapp.sent')
        message = self.env['connect.message'].search(
            [('bird_message_id', '=', 'm-external')])
        self.assertEqual(len(message), 1)
        self.assertEqual(message.to_number, '+31687654321')
        self.assertEqual(message.from_number, '+15550001')
        self.assertEqual(message.message_type, 'WhatsApp')
        self.assertEqual(message.status, 'sent')
        self.assertEqual(message.bird_number, self.number)

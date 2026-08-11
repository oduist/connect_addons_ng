# -*- coding: utf-8 -*-
"""Messages API tests: send, inbound webhook mapping, delivery status
(ADR-036)."""
from unittest.mock import MagicMock

from odoo.tests import tagged

from .common import VonageTestCommon


def inbound_message(message_uuid='msg-in-1', from_='15550002222',
                    to='15550001111', channel='sms', text='Hello Odoo',
                    **kwargs):
    params = {
        'message_uuid': message_uuid,
        'from': from_,
        'to': to,
        'channel': channel,
        'message_type': 'text',
        'text': text,
        'timestamp': '2026-07-11T10:00:00Z',
    }
    params.update(kwargs)
    return params


@tagged('at_install', '-post_install')
class TestVonageMessage(VonageTestCommon):

    def test_send_sms(self):
        response = MagicMock()
        response.message_uuid = 'msg-out-1'
        with self.mock_license_check(), self.mock_vonage_client() as client:
            client.messages.send.return_value = response
            self.env['connect.message'].send(
                '+15550002222', 'Test body',
                outgoing_callerid='+15550001111')
        sms = client.messages.send.call_args[0][0]
        self.assertEqual(sms.to, '15550002222')
        self.assertEqual(sms.from_, '15550001111')
        self.assertEqual(sms.text, 'Test body')
        message = self.env['connect.message'].search(
            [('message_sid', '=', 'msg-out-1')])
        self.assertTrue(message)
        self.assertEqual(message.direction, 'outgoing')
        self.assertEqual(message.status, 'sent')
        self.assertEqual(message.partner, self.partner)

    def test_receive_sms(self):
        with self.mock_license_check():
            self.env['connect.message'].receive(inbound_message())
        message = self.env['connect.message'].search(
            [('message_sid', '=', 'msg-in-1')])
        self.assertTrue(message)
        self.assertEqual(message.from_number, '+15550002222')
        self.assertEqual(message.to_number, '+15550001111')
        self.assertEqual(message.body, 'Hello Odoo')
        self.assertEqual(message.status, 'received')
        self.assertEqual(message.direction, 'incoming')
        self.assertEqual(message.partner, self.partner)

    def test_receive_sms_retry_is_idempotent(self):
        params = inbound_message(message_uuid='msg-retry-1')
        with self.mock_license_check():
            self.env['connect.message'].receive(params)
            self.env['connect.message'].receive(params)
        messages = self.env['connect.message'].search(
            [('message_sid', '=', 'msg-retry-1')])
        self.assertEqual(len(messages), 1)

    def test_receive_whatsapp_image(self):
        params = inbound_message(
            message_uuid='msg-in-2', channel='whatsapp',
            message_type='image', text=False,
            image={'url': 'https://api.example.com/img.jpg',
                   'caption': 'Look at this'})
        with self.mock_license_check():
            self.env['connect.message'].receive(params)
        message = self.env['connect.message'].search(
            [('message_sid', '=', 'msg-in-2')])
        self.assertEqual(message.message_type, 'WhatsApp')
        self.assertEqual(
            message.media_url, 'https://api.example.com/img.jpg')
        self.assertEqual(message.num_media, 1)
        self.assertEqual(message.body, 'Look at this')

    def test_update_message_status(self):
        message = self.env['connect.message'].create({
            'message_sid': 'msg-st-1',
            'from_number': '+15550001111',
            'to_number': '+15550002222',
            'status': 'sent',
        })
        self.env['connect.message'].update_message_status({
            'message_uuid': 'msg-st-1',
            'status': 'delivered',
        })
        self.assertEqual(message.status, 'delivered')

    def test_update_message_status_error(self):
        message = self.env['connect.message'].create({
            'message_sid': 'msg-st-2',
            'from_number': '+15550001111',
            'to_number': '+15550002222',
            'status': 'sent',
        })
        self.env['connect.message'].update_message_status({
            'message_uuid': 'msg-st-2',
            'status': 'rejected',
            'error': {'type': 1330, 'title': 'Not a mobile number'},
        })
        self.assertEqual(message.status, 'rejected')
        self.assertTrue(message.has_error)
        self.assertEqual(message.error_message, 'Not a mobile number')

    def test_update_status_unknown_message(self):
        result = self.env['connect.message'].update_message_status({
            'message_uuid': 'msg-does-not-exist',
            'status': 'delivered',
        })
        self.assertFalse(result)

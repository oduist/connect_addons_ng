# -*- coding: utf-8 -*-
import json
from unittest.mock import patch

from odoo.tests import tagged
from odoo.exceptions import ValidationError, UserError

from odoo.addons.connect.models.settings import Settings as CoreSettings

from .common import BirdTestCommon, BirdApiMock, patch_bird_request

# Live response of POST /v1/sms/messages (trimmed).
SMS_SEND_RESPONSE = {
    'id': 'sms_01kxb21qw0e9kr9hg9h609ba2n',
    'status': 'accepted',
    'direction': 'outbound',
    'from': '30300',
    'to': '+15005550006',
    'text': '123456 is your verification code. Do not share it.',
    'category': 'authentication',
    'last_error': None,
}

# Live response of POST /v1/whatsapp/messages (trimmed).
WA_SEND_RESPONSE = {
    'id': 'wam_01kxb23s0jf9erh6cjnn9af04n',
    'status': 'accepted',
    'direction': 'outbound',
    'business': {'phone_number': '+13124495569'},
    'contact': {'phone_number': '+15005550006'},
    'template': {'name': 'bird_otp', 'language': 'en',
                 'category': 'authentication', 'components': []},
    'last_error': None,
}


@tagged('at_install', '-post_install')
class TestBirdMessageSend(BirdTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sms_number = cls._make_number('+15550001', 'sms',
                                          is_default=True)
        cls.connect_user = cls._create_connect_user(
            'bird_sender', message_provider='bird',
            bird_message_number=cls.sms_number.id)
        cls.Message = cls.env['connect.message'].with_user(
            cls.connect_user.user)

    def test_send_sms_payload_and_ledger(self):
        mock = BirdApiMock(default=dict(SMS_SEND_RESPONSE, id='msg-out-1'))
        with patch_bird_request(mock):
            self.Message.send('+31612345678', 'Hi from Odoo')
        calls = mock.calls_to('POST', '/sms/messages')
        self.assertEqual(len(calls), 1)
        payload = calls[0]['payload']
        self.assertEqual(payload['to'], '+31612345678')
        self.assertEqual(payload['from'], '+15550001')
        self.assertEqual(payload['text'], 'Hi from Odoo')
        self.assertEqual(payload['category'], 'transactional')
        message = self.env['connect.message'].search(
            [('bird_message_id', '=', 'msg-out-1')])
        self.assertEqual(message.status, 'sent')
        self.assertEqual(message.direction, 'outgoing')
        # The rendered text and actual sender come from the response.
        self.assertEqual(message.from_number, '30300')
        self.assertEqual(
            message.body,
            '123456 is your verification code. Do not share it.')
        self.assertEqual(message.message_type, 'sms')
        self.assertEqual(message.sender_user, self.connect_user.user)

    def test_send_without_configured_number(self):
        # The platform assigns a shared sender when 'from' is omitted.
        self.connect_user.bird_message_number = False
        self.sms_number.is_default = False
        mock = BirdApiMock(default=dict(SMS_SEND_RESPONSE, id='msg-out-nf'))
        with patch_bird_request(mock):
            self.Message.send('+31612345678', 'No sender configured')
        payload = mock.calls_to('POST', '/sms/messages')[0]['payload']
        self.assertNotIn('from', payload)
        message = self.env['connect.message'].search(
            [('bird_message_id', '=', 'msg-out-nf')])
        self.assertEqual(message.from_number, '30300')

    def test_send_api_error_surfaces(self):
        # bird_request raises (e.g. "Free-form SMS is not yet generally
        # available"): the error must reach the user.
        def gated(payload, params):
            raise ValidationError(
                'Bird API error: Free-form SMS is not yet generally '
                'available. Send a predefined template instead. (403)')

        mock = BirdApiMock({('POST', '/sms/messages'): gated})
        with patch_bird_request(mock):
            with self.assertRaises(ValidationError):
                self.Message.send('+31612345678', 'Nope')

    def test_send_dispatch_falls_through(self):
        # Another provider key resolves: the chain must end in the core
        # terminal UserError, Bird must not handle the message.
        mock = BirdApiMock(default=SMS_SEND_RESPONSE)
        with patch_bird_request(mock), \
                patch.object(CoreSettings, '_get_message_provider',
                             return_value='other-provider'):
            with self.assertRaises(UserError):
                self.Message.send('+31612345678', 'Wrong provider')
        self.assertEqual(mock.calls, [])

    def test_send_sms_template(self):
        template = self.env['connect.bird.message_template'].create({
            'sid': 'smt_6w8134jzjbadbteeca4p9e0dtm',
            'product': 'sms',
            'name': 'bird_otp_verification',
            'locale': 'en',
            'status': 'active',
            'variables': json.dumps([
                {'key': 'code', 'type': 'code', 'required': True}]),
            'body_preview': '{{ code }} is your verification code.',
        })
        mock = BirdApiMock(default=dict(SMS_SEND_RESPONSE, id='msg-tpl-sms'))
        with patch_bird_request(mock):
            self.Message.send_bird_template(
                '+31612345678', template, params={'code': '123456'})
        payload = mock.calls_to('POST', '/sms/messages')[0]['payload']
        self.assertEqual(payload['template'], {
            'id': 'smt_6w8134jzjbadbteeca4p9e0dtm',
            'parameters': {'code': '123456'},
        })
        message = self.env['connect.message'].search(
            [('bird_message_id', '=', 'msg-tpl-sms')])
        self.assertEqual(message.message_type, 'sms')
        # Rendered text from the response is stored as the body.
        self.assertEqual(
            message.body,
            '123456 is your verification code. Do not share it.')

    def test_send_whatsapp_template(self):
        template = self.env['connect.bird.message_template'].create({
            'sid': 'wa:bird_otp:en',
            'product': 'whatsapp',
            'name': 'bird_otp',
            'locale': 'en',
            'status': 'approved',
            'variables': json.dumps([
                {'key': '1', 'type': 'text', 'required': True}]),
            'body_preview': '*{{1}}* is your verification code.',
        })
        mock = BirdApiMock(default=dict(WA_SEND_RESPONSE, id='msg-tpl-wa'))
        with patch_bird_request(mock):
            self.Message.send_bird_template(
                '+31612345678', template, params={'1': '123456'})
        payload = mock.calls_to('POST', '/whatsapp/messages')[0]['payload']
        self.assertEqual(payload['to'], '+31612345678')
        self.assertEqual(payload['template'], {
            'name': 'bird_otp',
            'components': [{
                'type': 'body',
                'parameters': [{'type': 'text', 'text': '123456'}],
            }],
        })
        message = self.env['connect.message'].search(
            [('bird_message_id', '=', 'msg-tpl-wa')])
        self.assertEqual(message.message_type, 'WhatsApp')
        # The WhatsApp sender comes from the response business object.
        self.assertEqual(message.from_number, '+13124495569')

    def test_send_explicit_sender(self):
        other = self._make_number('+15550002', 'sms')
        mock = BirdApiMock(default=dict(SMS_SEND_RESPONSE, id='msg-out-3',
                                        **{'from': '+15550002'}))
        with patch_bird_request(mock):
            self.Message.send(
                '+31612345678', 'Explicit', outgoing_callerid='+15550002')
        payload = mock.calls_to('POST', '/sms/messages')[0]['payload']
        self.assertEqual(payload['from'], '+15550002')
        message = self.env['connect.message'].search(
            [('bird_message_id', '=', 'msg-out-3')])
        self.assertEqual(message.bird_number, other)

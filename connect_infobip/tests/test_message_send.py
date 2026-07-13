# -*- coding: utf-8 -*-
"""connect.message.send() via /sms/2/text/advanced (mocked HTTP)."""
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import InfobipTestCommon, make_response

REQUESTS_PATH = 'odoo.addons.connect_infobip.models.settings.requests.request'


@tagged('at_install', '-post_install')
class TestInfobipMessageSend(InfobipTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.callerid = cls.env['connect.infobip.outgoing_callerid'].create({
            'number': '+15550001111',
            'friendly_name': 'Main',
            'is_default': True,
        })
        # send() resolves the sender from env.user.connect_user.
        cls.env['connect.user'].with_context(no_clear_cache=True).create({
            'user': cls.env.user.id,
            'message_provider': 'infobip',
            'infobip_outgoing_callerid': cls.callerid.id,
        })

    def _send_response(self, group_name='PENDING'):
        return make_response(
            json_data={
                'bulkId': 'bulk-1',
                'messages': [{
                    'to': '15550002222',
                    'messageId': 'msg-1',
                    'status': {'groupId': 1, 'groupName': group_name,
                               'id': 26, 'name': 'PENDING_ACCEPTED'},
                }],
            },
            content=b'{"messages": []}')

    def test_send_creates_message(self):
        with patch(REQUESTS_PATH) as mock_request:
            mock_request.return_value = self._send_response()
            self.env['connect.message'].send('+15550002222', 'Hello!')
        message = self.env['connect.message'].search(
            [('message_sid', '=', 'msg-1')], limit=1)
        self.assertTrue(message)
        self.assertEqual(message.status, 'sent')
        self.assertEqual(message.from_number, '+15550001111')
        self.assertEqual(message.to_number, '+15550002222')
        self.assertEqual(message.infobip_bulk_id, 'bulk-1')
        self.assertEqual(message.direction, 'outgoing')
        # The API payload carries MSISDNs without the + prefix and a
        # per-send DLR notifyUrl (ADR-036).
        args, kwargs = mock_request.call_args
        payload = kwargs['json']['messages'][0]
        self.assertEqual(payload['from'], '15550001111')
        self.assertEqual(payload['destinations'][0]['to'], '15550002222')
        self.assertIn('/infobip/webhook/message_status', payload['notifyUrl'])

    def test_send_rejected_marks_error(self):
        with patch(REQUESTS_PATH) as mock_request:
            mock_request.return_value = self._send_response(
                group_name='REJECTED')
            self.env['connect.message'].send('+15550002222', 'Hello!')
        message = self.env['connect.message'].search(
            [('message_sid', '=', 'msg-1')], limit=1)
        self.assertEqual(message.status, 'rejected')
        self.assertTrue(message.has_error)

    def test_send_without_callerid_raises(self):
        self.env.user.connect_user.infobip_outgoing_callerid = False
        with self.assertRaises(ValidationError):
            self.env['connect.message'].send('+15550002222', 'Hello!')

# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import TwilioTestCommon


@tagged('at_install', '-post_install')
class TestInboundMessageRouting(TwilioTestCommon):
    """connect.message.receive() runs as the webhook user.

    The routing configuration it consults is admin-only by design, so the
    lookup has to be sudo'd. Without it the read raised AccessError, the
    handler's own except swallowed it, and the inbound message was dropped
    with only "Error handling incoming SMS" in the log.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.webhook_user = cls.env.ref('connect.user_connect_webhook')
        cls.account_sid = 'AC' + '0' * 32
        cls.env['connect.settings'].sudo().set_param(
            'account_sid', cls.account_sid)

    def _params(self, sid, body='hello'):
        return {
            'AccountSid': self.account_sid,
            'SmsStatus': 'received',
            'MessageSid': sid,
            'From': 'whatsapp:+15550009999',
            'To': 'whatsapp:+15550001111',
            'Body': body,
            'NumMedia': '0',
        }

    def test_webhook_user_cannot_read_the_configuration(self):
        """Guards the premise: the model stays admin-only."""
        self.assertFalse(
            self.webhook_user.has_group('connect.group_admin'))
        with self.assertRaises(Exception):
            self.env['connect.twilio.message_configuration'].with_user(
                self.webhook_user).search([], limit=1)

    def test_inbound_message_is_stored_as_the_webhook_user(self):
        Message = self.env['connect.message']
        before = Message.sudo().search_count([])
        Message.with_user(self.webhook_user).receive(
            self._params('SMinboundtest0001'))
        self.assertEqual(Message.sudo().search_count([]), before + 1)
        stored = Message.sudo().search(
            [('message_sid', '=', 'SMinboundtest0001')], limit=1)
        self.assertTrue(
            stored, 'the inbound message must not be silently dropped')

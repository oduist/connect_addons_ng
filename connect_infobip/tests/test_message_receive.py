# -*- coding: utf-8 -*-
"""Inbound SMS / WhatsApp webhooks and delivery reports."""
from odoo.tests import tagged

from .common import InfobipTestCommon


@tagged('at_install', '-post_install')
class TestInfobipMessageReceive(InfobipTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.number = cls.env['connect.infobip.number'].with_context(
            skip_infobip_sync=True).create({
                'phone_number': '+15550001111',
                'number_key': 'NK1',
                'capabilities': 'SMS,VOICE',
            })

    def _inbound_event(self, text='Hi there', message_id='in-1'):
        return {
            'results': [{
                'messageId': message_id,
                'from': '15550002222',
                'to': '15550001111',
                'text': text,
                'cleanText': text,
            }],
            'messageCount': 1,
            'pendingMessageCount': 0,
        }

    def test_receive_sms(self):
        self.env['connect.message'].infobip_receive(self._inbound_event())
        message = self.env['connect.message'].search(
            [('message_sid', '=', 'in-1')], limit=1)
        self.assertTrue(message)
        self.assertEqual(message.status, 'received')
        self.assertEqual(message.direction, 'incoming')
        self.assertEqual(message.from_number, '+15550002222')
        self.assertEqual(message.to_number, '+15550001111')
        self.assertEqual(message.body, 'Hi there')
        self.assertEqual(message.message_type, 'sms')

    def test_receive_routes_to_new_partner(self):
        self.env['connect.infobip.message_configuration'].create({
            'number': self.number.id,
            'destination': 'res.partner',
            'default_values': "{'name': 'SMS Partner'}",
        })
        self.env['connect.message'].infobip_receive(self._inbound_event())
        message = self.env['connect.message'].search(
            [('message_sid', '=', 'in-1')], limit=1)
        self.assertEqual(message.res_model, 'res.partner')
        self.assertTrue(message.res_id)

    def test_receive_threads_on_last_message(self):
        partner = self.env['res.partner'].create({'name': 'Threaded'})
        self.env['connect.message'].sudo().create({
            'message_type': 'sms',
            'from_number': '+15550001111',
            'to_number': '+15550002222',
            'body': 'outbound',
            'status': 'sent',
            'res_model': 'res.partner',
            'res_id': partner.id,
        })
        self.env['connect.message'].infobip_receive(self._inbound_event())
        message = self.env['connect.message'].search(
            [('message_sid', '=', 'in-1')], limit=1)
        self.assertEqual(message.res_model, 'res.partner')
        self.assertEqual(message.res_id, partner.id)

    def test_receive_whatsapp_text(self):
        event = {
            'results': [{
                'messageId': 'wa-1',
                'from': '15550002222',
                'to': '15550001111',
                'message': {'type': 'TEXT', 'text': 'WA hello'},
            }],
        }
        self.env['connect.message'].infobip_receive_whatsapp(event)
        message = self.env['connect.message'].search(
            [('message_sid', '=', 'wa-1')], limit=1)
        self.assertTrue(message)
        self.assertEqual(message.message_type, 'WhatsApp')
        self.assertEqual(message.body, 'WA hello')

    def test_delivery_report_updates_status(self):
        message = self.env['connect.message'].sudo().create({
            'message_type': 'sms',
            'from_number': '+15550001111',
            'to_number': '+15550002222',
            'body': 'outbound',
            'status': 'sent',
            'message_sid': 'dlr-1',
        })
        event = {
            'results': [{
                'messageId': 'dlr-1',
                'status': {'groupName': 'DELIVERED', 'name': 'DELIVERED_TO_HANDSET'},
            }],
        }
        self.env['connect.message'].infobip_process_delivery_report(event)
        self.assertEqual(message.status, 'delivered')

    def test_delivery_report_failure_sets_error(self):
        message = self.env['connect.message'].sudo().create({
            'message_type': 'sms',
            'from_number': '+15550001111',
            'to_number': '+15550002222',
            'body': 'outbound',
            'status': 'sent',
            'message_sid': 'dlr-2',
        })
        event = {
            'results': [{
                'messageId': 'dlr-2',
                'status': {'groupName': 'UNDELIVERABLE',
                           'description': 'Message undeliverable'},
                'error': {'id': 11, 'name': 'EC_ABSENT_SUBSCRIBER',
                          'description': 'Absent Subscriber'},
            }],
        }
        self.env['connect.message'].infobip_process_delivery_report(event)
        self.assertEqual(message.status, 'undeliverable')
        self.assertTrue(message.has_error)
        self.assertEqual(message.error_message, 'Absent Subscriber')

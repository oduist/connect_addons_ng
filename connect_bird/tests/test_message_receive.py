# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import BirdTestCommon


def inbound_data(message_id='msg-in-1', sender='+31612345678',
                 to='+15550001', text='Hello there', **extra):
    data = {
        'sms_id': message_id,
        'from': sender,
        'to': to,
        'text': text,
        'direction': 'inbound',
    }
    data.update(extra)
    return data


@tagged('at_install', '-post_install')
class TestBirdMessageReceive(BirdTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.number = cls._make_number('+15550001', 'sms')

    def test_inbound_sms_creates_message(self):
        self.env['connect.message'].receive_bird(
            inbound_data(), 'sms.received')
        message = self.env['connect.message'].search(
            [('bird_message_id', '=', 'msg-in-1')])
        self.assertEqual(len(message), 1)
        self.assertEqual(message.from_number, '+31612345678')
        self.assertEqual(message.to_number, '+15550001')
        self.assertEqual(message.body, 'Hello there')
        self.assertEqual(message.status, 'received')
        self.assertEqual(message.direction, 'incoming')
        self.assertEqual(message.message_type, 'sms')
        self.assertEqual(message.bird_number, self.number)

    def test_inbound_is_idempotent(self):
        data = inbound_data(message_id='msg-dup')
        self.env['connect.message'].receive_bird(data, 'sms.received')
        self.env['connect.message'].receive_bird(data, 'sms.received')
        self.assertEqual(self.env['connect.message'].search_count(
            [('bird_message_id', '=', 'msg-dup')]), 1)

    def test_inbound_whatsapp_type(self):
        data = inbound_data(message_id='msg-wa')
        del data['sms_id']
        data['whatsapp_id'] = 'msg-wa'
        self.env['connect.message'].receive_bird(data, 'whatsapp.received')
        message = self.env['connect.message'].search(
            [('bird_message_id', '=', 'msg-wa')])
        self.assertEqual(message.message_type, 'WhatsApp')

    def test_inbound_whatsapp_object_shape(self):
        # WhatsApp objects carry contact/business phone number objects
        # instead of plain from/to.
        self.env['connect.message'].receive_bird({
            'id': 'wam-in-1',
            'direction': 'inbound',
            'contact': {'phone_number': '+31655555555'},
            'business': {'phone_number': '+15550001'},
            'text': 'hello from wa',
        }, 'whatsapp.received')
        message = self.env['connect.message'].search(
            [('bird_message_id', '=', 'wam-in-1')])
        self.assertEqual(len(message), 1)
        self.assertEqual(message.from_number, '+31655555555')
        self.assertEqual(message.to_number, '+15550001')
        self.assertEqual(message.bird_number, self.number)
        self.assertEqual(message.message_type, 'WhatsApp')

    def test_inbound_media(self):
        data = inbound_data(
            message_id='msg-img', text='see this',
            media=[{'url': 'https://media.example.com/a.jpg',
                    'content_type': 'image/jpeg'}])
        self.env['connect.message'].receive_bird(data, 'sms.received')
        message = self.env['connect.message'].search(
            [('bird_message_id', '=', 'msg-img')])
        self.assertEqual(message.media_url, 'https://media.example.com/a.jpg')
        self.assertEqual(message.media_content_type, 'image/jpeg')
        self.assertEqual(message.num_media, 1)
        self.assertEqual(message.body, 'see this')

    def test_inbound_links_partner(self):
        partner = self.env['res.partner'].create({
            'name': 'Bird Caller',
            'phone': '+31699999999',
        })
        self.env['connect.message'].receive_bird(
            inbound_data(message_id='msg-partner', sender='+31699999999'),
            'sms.received')
        message = self.env['connect.message'].search(
            [('bird_message_id', '=', 'msg-partner')])
        self.assertEqual(message.partner, partner)

    def test_message_configuration_routing(self):
        self.env['connect.bird.message_configuration'].create({
            'number': self.number.id,
            'destination': 'res.partner',
            'default_values': "{'comment': 'from bird'}",
        })
        self.env['connect.message'].receive_bird(
            inbound_data(message_id='msg-route', sender='+31688888888'),
            'sms.received')
        message = self.env['connect.message'].search(
            [('bird_message_id', '=', 'msg-route')])
        self.assertEqual(message.res_model, 'res.partner')
        self.assertTrue(message.res_id)
        partner = self.env['res.partner'].browse(message.res_id)
        self.assertEqual(partner.phone, '+31688888888')

    def test_inbound_threads_into_conversation(self):
        # An earlier outgoing message established the conversation target.
        partner = self.env['res.partner'].create({
            'name': 'Thread Partner', 'phone': '+31677777777'})
        first = self.env['connect.message'].sudo().create({
            'bird_message_id': 'msg-out-th',
            'from_number': self.number.number,
            'to_number': '+31677777777',
            'body': 'hi',
            'status': 'sent',
            'res_model': 'res.partner',
            'res_id': partner.id,
        })
        self.env['connect.message'].receive_bird(
            inbound_data(message_id='msg-reply', sender='+31677777777'),
            'sms.received')
        message = self.env['connect.message'].search(
            [('bird_message_id', '=', 'msg-reply')])
        self.assertEqual(message.parent_message, first)
        self.assertEqual(message.res_model, 'res.partner')
        self.assertEqual(message.res_id, partner.id)

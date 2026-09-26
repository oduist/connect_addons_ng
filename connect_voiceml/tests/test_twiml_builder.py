# -*- coding: utf-8 -*-
"""Tests for the minimal TwiML builder."""

from odoo.tests.common import TransactionCase

from odoo.addons.connect_voiceml.models.twiml_builder import TwiMLResponse


class TestTwiMLBuilder(TransactionCase):

    def test_say_hangup(self):
        r = TwiMLResponse()
        r.say('Hello')
        r.hangup()
        xml = r.to_string()
        self.assertIn('<?xml version="1.0" encoding="UTF-8"?>', xml)
        self.assertIn('<Response>', xml)
        self.assertIn('<Say>Hello</Say>', xml)
        self.assertIn('<Hangup />', xml)

    def test_dial_sip(self):
        r = TwiMLResponse()
        r.dial(callerId='+100', timeout='10').sip(
            'sip:1001@example.com',
            statusCallback='https://x/cb',
            statusCallbackEvent='initiated answered completed',
        )
        xml = r.to_string()
        self.assertIn('callerId="+100"', xml)
        self.assertIn('<Sip', xml)
        self.assertIn('>sip:1001@example.com</Sip>', xml)

    def test_dial_number(self):
        r = TwiMLResponse()
        r.dial(timeLimit='7200').number('+18005551234')
        xml = r.to_string()
        self.assertIn('<Number>+18005551234</Number>', xml)

    def test_gather_say(self):
        r = TwiMLResponse()
        g = r.gather(action='https://x/gather', method='POST', timeout='5')
        g.say('Please enter an extension')
        xml = r.to_string()
        self.assertIn('action="https://x/gather"', xml)
        self.assertIn('<Gather', xml)
        self.assertIn('<Say>Please enter an extension</Say>', xml)

    def test_reject_and_pause(self):
        r = TwiMLResponse()
        r.pause(length='1')
        r.reject(reason='busy')
        xml = r.to_string()
        self.assertIn('<Pause length="1" />', xml)
        self.assertIn('<Reject reason="busy" />', xml)

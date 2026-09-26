# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestNumberRouting(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Settings = self.env['connect.settings']
        self.settings = self.Settings.search([], limit=1)
        if not self.settings:
            self.settings = self.Settings.create({})
        self.Application = self.env['connect.voiceml.application']

    def _make_application(self, twiml):
        return self.Application.with_context(install_mode=True).create({
            'name': 'Test App',
            'code_type': 'twiml',
            'twiml': twiml,
        })

    def test_render_application_destination(self):
        app = self._make_application(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response><Say>Hello</Say></Response>')
        number = self.env['connect.voiceml.number'].create({
            'phone_number': '+18005551234',
            'destination': 'application',
            'application': app.id,
        })
        xml = number.render()
        self.assertIn('<Say>Hello</Say>', xml)

    def test_route_call_finds_number(self):
        app = self._make_application(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response><Hangup /></Response>')
        self.env['connect.voiceml.number'].create({
            'phone_number': '+18005551234',
            'destination': 'application',
            'application': app.id,
        })
        # route_call feeds connect.call.on_call_status, which expects the full
        # inbound webhook parameter set, not just the called number.
        xml = self.env['connect.voiceml.number'].route_call({
            'Called': '+18005551234',
            'CallSid': 'CA-test-1',
            'Caller': '+15551234567',
            'To': '+18005551234',
            'Direction': 'inbound',
            'CallStatus': 'ringing',
            'CallDuration': '0',
        })
        self.assertIn('<Hangup', xml)

    def test_unconfigured_number_greets(self):
        number = self.env['connect.voiceml.number'].create({
            'phone_number': '+18005559999',
        })
        xml = number.render()
        self.assertIn('Number not configured', xml)

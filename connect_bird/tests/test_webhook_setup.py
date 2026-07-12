# -*- coding: utf-8 -*-
from odoo.tests import tagged

from odoo.addons.connect_bird.models.settings import (
    BIRD_WEBHOOK_EVENTS,
    BIRD_WEBHOOK_EVENTS_SAFE,
)

from .common import BirdTestCommon, BirdApiMock, patch_bird_request


@tagged('at_install', '-post_install')
class TestBirdWebhookSetup(BirdTestCommon):

    def test_setup_registers_endpoint_and_stores_secret(self):
        Settings = self.env['connect.settings'].sudo()
        Settings.set_param('bird_webhook_signing_key', False)

        def create_endpoint(payload, params):
            self.assertEqual(payload['url'],
                             'https://odoo.example.com/bird/webhook')
            self.assertEqual(payload['events'], BIRD_WEBHOOK_EVENTS)
            return {
                'id': 'we-1',
                'secret': 'whsec_dGVzdA==',
                'status': 'enabled',
                'events': payload['events'],
            }

        mock = BirdApiMock({('POST', '/webhooks'): create_endpoint})
        # Scope assertions to this test's URL: the database may already
        # carry endpoints (e.g. registered manually in the dashboard).
        domain = [('url', '=', 'https://odoo.example.com/bird/webhook')]
        with patch_bird_request(mock):
            self.settings.setup_bird_webhooks()
        endpoint = self.env['connect.bird.webhook'].search(domain)
        self.assertEqual(len(endpoint), 1)
        self.assertEqual(endpoint.sid, 'we-1')
        self.assertEqual(Settings.get_param('bird_webhook_signing_key'),
                         'whsec_dGVzdA==')
        self.assertEqual(
            Settings.get_param('display_bird_webhook_signing_key'),
            '*' * len('whsec_dGVzdA=='))
        # Second run: the endpoint exists and the one-time secret is
        # already stored — no new registration.
        with patch_bird_request(mock):
            self.settings.setup_bird_webhooks()
        self.assertEqual(len(mock.calls_to('POST', '/webhooks')), 1)
        self.assertEqual(
            self.env['connect.bird.webhook'].search_count(domain), 1)

    def test_setup_falls_back_to_safe_events(self):
        # The platform rejects unknown event names: the registration is
        # retried with the published SMS subset.
        Settings = self.env['connect.settings'].sudo()
        Settings.set_param('bird_webhook_signing_key', False)
        attempts = []

        def create_endpoint(payload, params):
            attempts.append(payload['events'])
            if payload['events'] != BIRD_WEBHOOK_EVENTS_SAFE:
                return False
            return {'id': 'we-2', 'secret': 'whsec_dGVzdA==',
                    'status': 'enabled', 'events': payload['events']}

        mock = BirdApiMock({('POST', '/webhooks'): create_endpoint})
        with patch_bird_request(mock):
            self.settings.setup_bird_webhooks()
        self.assertEqual(attempts,
                         [BIRD_WEBHOOK_EVENTS, BIRD_WEBHOOK_EVENTS_SAFE])
        endpoint = self.env['connect.bird.webhook'].search(
            [('sid', '=', 'we-2')])
        self.assertEqual(len(endpoint), 1)

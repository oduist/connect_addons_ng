# -*- coding: utf-8 -*-
"""/3cx/webhook/* controller tests: API-key auth, contact lookup, call
journaling into the ledger, and contact creation."""
import json

from odoo.tests import tagged, HttpCase, new_test_user

from .common import API_KEY, setup_threecx_settings

START_MS = 1751900000000


@tagged('post_install', '-at_install', 'connect_3cx')
class TestThreeCXWebhooks(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        setup_threecx_settings(cls.env)
        cls.Settings = cls.env['connect.settings']
        cls.Channel = cls.env['connect.channel']
        cls.Call = cls.env['connect.call']
        cls.odoo_user = new_test_user(
            cls.env, login='tcx_http_101', groups='base.group_user')
        cls.connect_user = cls.env['connect.user'].with_context(
            no_clear_cache=True).create({
                'user': cls.odoo_user.id,
                'threecx_exten': '101',
            })
        cls.partner = cls.env['res.partner'].with_context(
            no_clear_cache=True).create({
                'name': '3CX HTTP Partner',
                'phone': '+15551234567',
            })

    def _get(self, path, token=API_KEY):
        headers = {}
        if token:
            headers['X-Connect-Api-Key'] = token
        return self.url_open(path, headers=headers)

    def _post(self, path, payload, token=API_KEY):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['X-Connect-Api-Key'] = token
        return self.url_open(path, data=json.dumps(payload), headers=headers)

    def _journal(self, **overrides):
        payload = {
            'call_type': 'Inbound',
            'direction': 'Inbound',
            'number': '+15551234567',
            'contact_name': '',
            'entity_id': '',
            'entity_type': '',
            'queue_extension': '',
            'agent': '101',
            'agent_email': '',
            'duration': '00:00:42',
            'start_utc_millis': str(START_MS),
            'established_utc_millis': str(START_MS + 5000),
            'end_utc_millis': str(START_MS + 47000),
            'recording_url': '',
            'transcription': '',
            'summary': '',
            'sentiment': '',
        }
        payload.update(overrides)
        return self._post('/3cx/webhook/report_call', payload)

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def test_requires_token(self):
        self.assertEqual(
            self._get('/3cx/webhook/lookup?number=123',
                      token=None).status_code, 401)
        self.assertEqual(
            self._get('/3cx/webhook/lookup?number=123',
                      token='wrong-token-wrong-token').status_code, 401)
        self.assertEqual(
            self._post('/3cx/webhook/report_call', {},
                       token=None).status_code, 401)
        self.assertEqual(
            self._post('/3cx/webhook/create_contact', {},
                       token=None).status_code, 401)

    def test_bearer_token_accepted(self):
        response = self.url_open(
            '/3cx/webhook/lookup?number=%2B15551234567',
            headers={'Authorization': 'Bearer %s' % API_KEY})
        self.assertEqual(response.status_code, 200)

    def test_disabled_integration_rejects(self):
        self.Settings.set_param('threecx_enabled', False)
        try:
            response = self._get('/3cx/webhook/lookup?number=123')
            self.assertEqual(response.status_code, 401)
        finally:
            self.Settings.set_param('threecx_enabled', True)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def test_lookup_found(self):
        response = self._get('/3cx/webhook/lookup?number=%2B15551234567')
        self.assertEqual(response.status_code, 200)
        contact = response.json()['contact']
        self.assertEqual(contact['id'], self.partner.id)
        self.assertEqual(contact['last_name'], '3CX HTTP Partner')
        self.assertEqual(contact['entity_type'], 'Person')
        self.assertEqual(contact['phone_business'], '+15551234567')
        self.assertIn(
            'id=%s&model=res.partner' % self.partner.id, contact['url'])
        self.assertTrue(self.Settings.get_param('threecx_last_lookup'))

    def test_lookup_no_match(self):
        response = self._get('/3cx/webhook/lookup?number=%2B19998887766')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('contact', response.json())

    def test_lookup_requires_number(self):
        self.assertEqual(
            self._get('/3cx/webhook/lookup').status_code, 400)

    # ------------------------------------------------------------------
    # Call journaling
    # ------------------------------------------------------------------

    def test_inbound_answered(self):
        response = self._journal()
        self.assertEqual(response.status_code, 200)
        sid = response.json()['sid']
        channel = self.Channel.search([('sid', '=', sid)])
        self.assertTrue(channel)
        self.assertEqual(channel.technical_direction, 'inbound')
        self.assertEqual(channel.status, 'completed')
        self.assertEqual(channel.duration, 42)
        self.assertEqual(channel.called_pbx_user, self.connect_user)
        self.assertEqual(channel.partner, self.partner)
        call = channel.call
        self.assertTrue(call)
        self.assertEqual(call.direction, 'incoming')
        self.assertEqual(call.status, 'completed')
        self.assertEqual(call.duration, 42)
        self.assertEqual(call.partner, self.partner)
        self.assertTrue(self.Settings.get_param('threecx_last_journal'))

    def test_journal_replay_is_idempotent(self):
        first = self._journal().json()
        second = self._journal().json()
        self.assertEqual(first['sid'], second['sid'])
        channels = self.Channel.search([('sid', '=', first['sid'])])
        self.assertEqual(len(channels), 1)
        self.assertEqual(len(channels.call), 1)

    def test_inbound_missed(self):
        response = self._journal(
            call_type='Missed', established_utc_millis='',
            duration='', start_utc_millis=str(START_MS + 1))
        channel = self.Channel.search([('sid', '=', response.json()['sid'])])
        self.assertEqual(channel.status, 'no-answer')
        self.assertEqual(channel.duration, 0)
        self.assertEqual(channel.call.direction, 'incoming')
        self.assertEqual(channel.call.status, 'no-answer')

    def test_outbound_answered(self):
        response = self._journal(
            call_type='Outbound', direction='Outbound',
            start_utc_millis=str(START_MS + 2))
        channel = self.Channel.search([('sid', '=', response.json()['sid'])])
        self.assertEqual(channel.technical_direction, 'outbound-api')
        self.assertEqual(channel.caller_pbx_user, self.connect_user)
        self.assertEqual(channel.partner, self.partner)
        self.assertEqual(channel.call.direction, 'outgoing')
        self.assertEqual(channel.call.status, 'completed')

    def test_outbound_not_answered(self):
        response = self._journal(
            call_type='Notanswered', direction='Outbound',
            established_utc_millis='', duration='',
            start_utc_millis=str(START_MS + 3))
        channel = self.Channel.search([('sid', '=', response.json()['sid'])])
        self.assertEqual(channel.status, 'no-answer')
        self.assertEqual(channel.call.direction, 'outgoing')

    def test_duration_fallback_to_hhmmss(self):
        response = self._journal(
            established_utc_millis='', end_utc_millis='',
            duration='00:01:05', start_utc_millis=str(START_MS + 4))
        channel = self.Channel.search([('sid', '=', response.json()['sid'])])
        self.assertEqual(channel.duration, 65)

    def test_entity_id_backfills_partner(self):
        # Number that matches no partner, but EntityId (returned by our
        # own lookup earlier in the call) carries the partner id.
        response = self._journal(
            number='+10000000001', entity_id=str(self.partner.id),
            start_utc_millis=str(START_MS + 5))
        channel = self.Channel.search([('sid', '=', response.json()['sid'])])
        self.assertEqual(channel.partner, self.partner)

    def test_recording_reference_created(self):
        response = self._journal(
            recording_url='https://pbx.example.com/recordings/42.wav',
            transcription='Hello, this is a test call.',
            summary='Customer asked about pricing.',
            sentiment='Positive',
            start_utc_millis=str(START_MS + 6))
        sid = response.json()['sid']
        recording = self.env['connect.recording'].search(
            [('call_sid', '=', sid)])
        self.assertEqual(len(recording), 1)
        self.assertEqual(
            recording.media_url, 'https://pbx.example.com/recordings/42.wav')
        self.assertEqual(recording.transcript, 'Hello, this is a test call.')
        self.assertIn('Customer asked about pricing.', recording.summary)
        self.assertIn('Sentiment: Positive', recording.summary)
        self.assertEqual(recording.source, '3cx')
        # Never queued for core OpenAI transcription: the media URL is
        # not downloadable at this tier.
        self.assertFalse(recording.transcription_pending)
        channel = self.Channel.search([('sid', '=', sid)])
        self.assertEqual(recording.channel, channel)
        self.assertEqual(recording.call, channel.call)
        self.assertIn('Customer asked about pricing.', channel.call.summary)

    def test_journal_bad_payload(self):
        self.assertEqual(
            self._post('/3cx/webhook/report_call',
                       {'call_type': 'Weird'}).status_code, 400)
        response = self.url_open(
            '/3cx/webhook/report_call', data='{not json',
            headers={'Content-Type': 'application/json',
                     'X-Connect-Api-Key': API_KEY})
        self.assertEqual(response.status_code, 400)

    # ------------------------------------------------------------------
    # Contact creation
    # ------------------------------------------------------------------

    def test_create_contact(self):
        response = self._post('/3cx/webhook/create_contact', {
            'first_name': 'John',
            'last_name': 'Doe',
            'number': '+15559998877',
            'email': 'john@example.com',
            'company': 'ACME',
        })
        self.assertEqual(response.status_code, 200)
        contact = response.json()['contact']
        partner = self.env['res.partner'].browse(contact['id'])
        self.assertEqual(partner.name, 'John Doe')
        self.assertEqual(partner.phone, '+15559998877')
        self.assertEqual(partner.email, 'john@example.com')
        self.assertEqual(partner.company_name, 'ACME')
        self.assertEqual(contact['entity_type'], 'Person')

    def test_create_contact_requires_data(self):
        self.assertEqual(
            self._post('/3cx/webhook/create_contact', {}).status_code, 400)

    # ------------------------------------------------------------------
    # Template download route
    # ------------------------------------------------------------------

    def test_template_route_requires_login(self):
        # Anonymous users are redirected to login — the template (which
        # embeds the API key) is never served.
        response = self.url_open('/3cx/template', allow_redirects=False)
        self.assertIn(response.status_code, (302, 303))
        self.assertNotIn(API_KEY, response.text)

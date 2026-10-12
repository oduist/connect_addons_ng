# -*- coding: utf-8 -*-
"""Click-to-call origin and chatter registration targets."""
import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import ConnectTestCommon


@tagged('post_install', '-at_install')
class TestCallOrigin(ConnectTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env['connect.settings'].sudo()
        cls.pbx_user = cls._create_connect_user('origin_agent')
        cls.agent = cls.pbx_user.user
        # Any mail.thread record with a contact field can be an origin; a
        # connect.call with a partner is the one core itself provides.
        cls.origin = cls._create_call(
            caller='+15550000001', called='+441865600008',
            partner=cls.partner.id)

    def _messages(self, record):
        return self.env['mail.message'].search([
            ('model', '=', record._name), ('res_id', '=', record.id),
        ])

    def _remember(self, number='+44 1865 600008', record=None):
        record = record or self.origin
        self.settings._remember_originate_origin(
            number, record._name, record.id, self.agent)

    def _outgoing_channel(self, sid, called='+441865600008', **kwargs):
        vals = {
            'technical_direction': 'outbound-api',
            'caller_user': self.agent.id,
            'caller_pbx_user': self.pbx_user.id,
        }
        vals.update(kwargs)
        return self._create_channel(sid, caller='+48221811500', called=called, **vals)

    def test_originate_wrapper_remembers_origin(self):
        Settings = type(self.settings)
        self.assertTrue(Settings.originate_call._connect_remembers_origin)
        with patch.object(Settings, '_get_originate_provider', return_value='none'), \
                patch.object(Settings, '_remember_originate_origin') as remember:
            with self.assertRaises(UserError):
                self.settings.originate_call(
                    '+441865600008', 'connect.call', self.origin.id, user=self.agent)
        remember.assert_called_once_with(
            '+441865600008', 'connect.call', self.origin.id, self.agent)

    def test_outgoing_call_claims_origin(self):
        self._remember()
        pending = json.loads(self.pbx_user.originate_origin)
        self.assertEqual(pending['number'], '865600008')
        channel = self._outgoing_channel('origin-claim')
        with self.mock_connect_reload_view():
            call = self.env['connect.call'].browse(
                self.env['connect.call'].process_call_event(channel))
        self.assertEqual(call.direction, 'outgoing')
        self.assertEqual(call.origin_ref, self.origin)
        self.assertFalse(self.pbx_user.originate_origin)

    def test_origin_not_claimed_by_other_number_or_after_ttl(self):
        self._remember()
        channel = self._outgoing_channel('origin-other', called='+15557770000')
        with self.mock_connect_reload_view():
            call = self.env['connect.call'].browse(
                self.env['connect.call'].process_call_event(channel))
        self.assertFalse(call.origin_model)
        self.assertTrue(self.pbx_user.originate_origin)

        pending = json.loads(self.pbx_user.originate_origin)
        pending['at'] = fields.Datetime.to_string(
            fields.Datetime.now() - timedelta(minutes=30))
        self.pbx_user._set_originate_origin(pending)
        channel = self._outgoing_channel('origin-late')
        with self.mock_connect_reload_view():
            call = self.env['connect.call'].browse(
                self.env['connect.call'].process_call_event(channel))
        self.assertFalse(call.origin_model)
        self.assertFalse(self.pbx_user.originate_origin)

    def test_registration_records_add_contact_without_duplicates(self):
        call = self._create_call(
            direction='outgoing', partner=self.partner.id,
            origin_model='connect.call', origin_res_id=self.origin.id)
        self.assertEqual(call._get_registration_records(), [self.origin, self.partner])

        no_partner = self._create_call(
            direction='outgoing',
            origin_model='connect.call', origin_res_id=self.origin.id)
        # The origin's own contact is added even when the call has none.
        self.assertEqual(
            no_partner._get_registration_records(), [self.origin, self.partner])

    def test_call_log_and_summary_reach_origin_and_contact_once(self):
        self.settings.set_param('register_summary', True)
        call = self._create_call(
            direction='outgoing', status='completed', partner=self.partner.id,
            origin_model='connect.call', origin_res_id=self.origin.id)
        channel = self._outgoing_channel(
            'origin-register', call=call.id, status='completed')
        origin_before = len(self._messages(self.origin))
        partner_before = len(self._messages(self.partner))
        with self.mock_connect_reload_view():
            call.register_call(channel, {})
            call.summary = '<p>Customer will call back tomorrow.</p>'
        origin_new = self._messages(self.origin)[:len(self._messages(self.origin)) - origin_before]
        partner_new = self._messages(self.partner)[:len(self._messages(self.partner)) - partner_before]
        for new in (origin_new, partner_new):
            self.assertEqual(len(new), 2)
            self.assertTrue(any('outgoing call' in (m.body or '') for m in new))
            self.assertTrue(any('call back tomorrow' in (m.body or '') for m in new))

    def test_short_transcript_is_not_summarized(self):
        Recording = self.env['connect.recording']
        self.assertFalse(Recording._is_summarizable('00:00:00 you\n'))
        self.assertFalse(Recording._is_summarizable('00:00:00 Hello.\n00:00:01 Yes.\n'))
        self.assertTrue(Recording._is_summarizable(
            '00:00:00 Hello, I am calling about the delivery of my order.\n'))
        recording = Recording.with_context(skip_transcription=True).create({
            'sid': 'RE-short', 'media_url': 'https://example.com/RE-short.mp3'})
        with self.mock_connect_reload_view():
            recording.update_transcript({
                'transcript': '00:00:00 you\n',
                'summary': '<p>The transcript is too short to summarize.</p>',
            })
        self.assertEqual(recording.transcript, '00:00:00 you\n')
        self.assertFalse(recording.summary)

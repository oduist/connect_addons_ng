# -*- coding: utf-8 -*-
"""FreeSWITCH user voicemail fallback tests."""
import base64
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase

from .common import FsTestCommon


@tagged('post_install', '-at_install', 'connect_freeswitch', 'voicemail')
class TestUserVoicemailDialplan(FsTestCommon):

    def _set_webhook_config(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'web.base.url', 'https://odoo.example')
        self.env['connect.settings'].sudo().set_param(
            'freeswitch_webhook_token', 'test-token-test-token-test-token')

    def _create_user_with_exten(self, login, number, **vals):
        user = self._create_connect_user(login, **vals)
        self.env['connect.freeswitch.exten'].create({
            'number': number,
            'model': 'connect.user',
            'res_id': user.id,
        })
        return user

    def test_voicemail_disabled_renders_no_fallback(self):
        self._set_webhook_config()
        user = self._create_user_with_exten(
            'fs_vm_disabled', '9101',
            record_calls=False,
            voicemail_enabled=False,
        )

        xml = user.generate_dialplan({})

        self.assertIn('application="bridge"', xml)
        self.assertNotIn('/freeswitch/webhook/voicemail/', xml)
        self.assertNotIn('tone_stream://', xml)

    def test_voicemail_enabled_renders_prompt_and_recording(self):
        self._set_webhook_config()
        user = self._create_user_with_exten(
            'fs_vm_enabled', '9102',
            record_calls=False,
            voicemail_enabled=True,
            voicemail_prompt='Hello {{ user.name }} & "friends"',
        )
        user.user.name = 'Jane & "QA"'

        xml = user.generate_dialplan({})

        self.assertIn(
            'data="piper|en-US|Hello Jane &amp; &quot;QA&quot; '
            '&amp; &quot;friends&quot;"',
            xml,
        )
        self.assertIn('data="tone_stream://%(1000,0,640)"', xml)
        self.assertIn(
            'application="record" data="https://odoo.example/freeswitch/'
            'webhook/voicemail/test-token-test-token-test-token/'
            '${uuid}.wav 120 200 5"',
            xml,
        )
        self.assertLess(
            xml.index('application="bridge"'),
            xml.index('/freeswitch/webhook/voicemail/'),
        )


@tagged('post_install', '-at_install', 'connect_freeswitch', 'voicemail')
class TestVoicemailWebhook(HttpCase):

    def _token(self):
        token = 'test-token-test-token-test-token'
        self.env['connect.settings'].sudo().set_param(
            'freeswitch_webhook_token', token)
        return token

    def test_voicemail_rejects_wrong_path_token(self):
        resp = self.opener.put(
            self.base_url()
            + '/freeswitch/webhook/voicemail/wrong/u1.wav',
            data=b'RIFFxxxx')
        self.assertEqual(resp.status_code, 401)

    def test_voicemail_accepts_path_token(self):
        resp = self.opener.put(
            self.base_url()
            + '/freeswitch/webhook/voicemail/%s/u1.wav' % self._token(),
            data=b'')
        self.assertEqual(resp.status_code, 400)

    def test_voicemail_upload_creates_recording(self):
        uuid = 'vm-upload-1'
        resp = self.opener.put(
            self.base_url()
            + '/freeswitch/webhook/voicemail/%s/%s.wav'
            % (self._token(), uuid),
            data=b'RIFFxxxx')

        self.assertEqual(resp.status_code, 200)
        recording = self.env['connect.recording'].sudo().search([
            ('call_sid', '=', uuid),
            ('source', '=', 'freeswitch_voicemail'),
        ], limit=1)
        self.assertTrue(recording)
        self.assertEqual(recording.recording_filename, '%s.wav' % uuid)
        self.assertTrue(recording.recording_attachment)

    def test_voicemail_upload_updates_existing_call(self):
        uuid = 'vm-existing-call-1'
        call = self.env['connect.call'].with_context(
            tracking_disable=True).create({
                'caller': '+15550001111',
                'called': '9102',
                'status': 'no-answer',
                'direction': 'incoming',
            })
        self.env['connect.channel'].with_context(tracking_disable=True).create({
            'sid': uuid,
            'call': call.id,
            'caller': '+15550001111',
            'called': '9102',
            'status': 'no-answer',
            'technical_direction': 'inbound',
            'duration': 12,
        })
        self.env.cr.commit()

        resp = self.opener.put(
            self.base_url()
            + '/freeswitch/webhook/voicemail/%s/%s.wav'
            % (self._token(), uuid),
            data=b'RIFFxxxx')

        self.assertEqual(resp.status_code, 200)
        call.invalidate_recordset(['voicemail_url', 'voicemail_duration'])
        self.assertIn('/web/content?model=connect.recording', call.voicemail_url)
        self.assertIn('field=recording_attachment', call.voicemail_url)
        self.assertEqual(call.voicemail_duration, 12)
        self.assertIn('fa-envelope-o', call.voicemail_icon)
        self.assertIn('/web/content?model=connect.recording', call.voicemail_widget)


@tagged('post_install', '-at_install', 'connect_freeswitch', 'voicemail')
class TestVoicemailCdrLink(TransactionCase):

    def test_orphan_voicemail_upload_links_to_call_on_cdr(self):
        uuid = 'vm-orphan-cdr-1'
        recording = self.env['connect.recording'].sudo().create({
            'call_sid': uuid,
            'status': 'completed',
            'source': 'freeswitch_voicemail',
            'recording_attachment': base64.b64encode(b'RIFFxxxx'),
            'recording_filename': '%s.wav' % uuid,
        })
        cdr_data = {
            'uuid': uuid,
            'caller': '+15550001111',
            'called': '9103',
            'direction': 'inbound',
            'hangup_cause': 'NO_ANSWER',
            'duration': 9,
            'odoo_call_direction': 'inbound',
        }

        with patch.object(
            type(self.env['oduist.license']),
            'check_license',
            return_value=True,
        ), patch.object(
            type(self.env['connect.settings']),
            'connect_reload_view',
        ):
            call_id = self.env['connect.call']._process_cdr_locked(cdr_data)

        call = self.env['connect.call'].browse(call_id)
        recording.invalidate_recordset(['call', 'channel'])
        self.assertEqual(recording.call, call)
        self.assertTrue(recording.channel)
        self.assertIn('/web/content?model=connect.recording', call.voicemail_url)
        self.assertIn('field=recording_attachment', call.voicemail_url)
        self.assertEqual(call.voicemail_duration, 9)

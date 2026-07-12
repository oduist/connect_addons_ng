# -*- coding: utf-8 -*-
"""Tests for the shared-token authentication of FreeSWITCH -> Odoo
HTTP endpoints (ADR-025): /freeswitch/xml, /freeswitch/webhook/cdr,
/freeswitch/webhook/recording/<token>/<filename>, and
/freeswitch/webhook/voicemail/<token>/<filename>.

Parking webhook auth is covered in test_parking.py.
"""
import base64
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase


@tagged('post_install', '-at_install', 'connect_freeswitch_webhook_token')
class WebhookTokenHttpCase(HttpCase):

    def _token(self):
        return self.env['connect.settings'].sudo().get_param(
            'freeswitch_webhook_token')

    def _basic(self, token):
        cred = base64.b64encode(
            ('freeswitch:%s' % token).encode()).decode()
        return {'Authorization': 'Basic %s' % cred}

    # ------------------------------------------------------------------
    # /freeswitch/xml (mod_xml_curl)
    # ------------------------------------------------------------------

    def test_xml_token_is_generated(self):
        token = self._token()
        self.assertTrue(token)
        self.assertGreaterEqual(len(token), 24)

    def test_xml_rejects_without_auth(self):
        resp = self.url_open('/freeswitch/xml', data={'section': 'directory'})
        self.assertEqual(resp.status_code, 401)

    def test_xml_non_ascii_token_is_401_not_500(self):
        # secrets.compare_digest raises TypeError on a non-ASCII str; the
        # token check must reject such input with the uniform 401 rather
        # than a 500 error page (attacker-triggerable on this open route).
        # The token query param is the reachable vector — HTTP headers are
        # latin-1 so a non-ASCII Authorization value can't be transmitted.
        resp = self.url_open(
            '/freeswitch/xml?token=пароль', data={'section': 'directory'})
        self.assertEqual(resp.status_code, 401)

    def test_xml_rejects_wrong_basic_password(self):
        resp = self.url_open(
            '/freeswitch/xml', data={'section': 'directory'},
            headers=self._basic('wrong-token-wrong-token-wrong'))
        self.assertEqual(resp.status_code, 401)

    def test_xml_accepts_basic_auth(self):
        resp = self.url_open(
            '/freeswitch/xml', data={'section': 'unknown'},
            headers=self._basic(self._token()))
        self.assertEqual(resp.status_code, 200)
        # Unknown section -> the controller answers with the not-found XML.
        self.assertIn('not found', resp.text)

    def test_xml_accepts_bearer_auth(self):
        resp = self.url_open(
            '/freeswitch/xml', data={'section': 'unknown'},
            headers={'Authorization': 'Bearer %s' % self._token()})
        self.assertEqual(resp.status_code, 200)

    def test_xml_directory_serves_with_token_only(self):
        # An authorized directory lookup for an unknown user must not 401.
        resp = self.url_open(
            '/freeswitch/xml',
            data={'section': 'directory', 'user': 'no-such-user',
                  'action': 'sip_auth'},
            headers=self._basic(self._token()))
        self.assertEqual(resp.status_code, 200)

    # ------------------------------------------------------------------
    # /freeswitch/webhook/cdr (mod_xml_cdr)
    # ------------------------------------------------------------------

    def test_cdr_rejects_without_auth(self):
        resp = self.url_open('/freeswitch/webhook/cdr', data={'cdr': 'x'})
        self.assertEqual(resp.status_code, 401)

    def test_cdr_authorized_bad_xml_is_400(self):
        resp = self.url_open(
            '/freeswitch/webhook/cdr', data={'cdr': 'not-xml'},
            headers=self._basic(self._token()))
        self.assertEqual(resp.status_code, 400)

    # ------------------------------------------------------------------
    # /freeswitch/webhook/recording/<token>/<filename> (record_session)
    # ------------------------------------------------------------------

    def test_recording_rejects_wrong_path_token(self):
        resp = self.opener.put(
            self.base_url() + '/freeswitch/webhook/recording/wrong/u1.wav',
            data=b'RIFFxxxx')
        self.assertEqual(resp.status_code, 401)

    def test_recording_accepts_path_token(self):
        resp = self.opener.put(
            self.base_url()
            + '/freeswitch/webhook/recording/%s/u1.wav' % self._token(),
            data=b'')
        # Authorized but empty body -> validation 400, not 401.
        self.assertEqual(resp.status_code, 400)

    # ------------------------------------------------------------------
    # /freeswitch/webhook/voicemail/<token>/<filename>
    # ------------------------------------------------------------------

    def test_voicemail_rejects_wrong_path_token(self):
        resp = self.opener.put(
            self.base_url() + '/freeswitch/webhook/voicemail/wrong/u1.wav',
            data=b'RIFFxxxx')
        self.assertEqual(resp.status_code, 401)

    def test_voicemail_upload_sets_call_voicemail_url(self):
        call = self.env['connect.call'].sudo().create({
            'caller': '+15551111111',
            'called': '+15552222222',
            'status': 'completed',
            'direction': 'incoming',
        })
        self.env['connect.channel'].sudo().create({
            'sid': 'vm-http-existing',
            'call': call.id,
            'caller': '+15551111111',
            'called': '+15552222222',
            'status': 'completed',
            'technical_direction': 'inbound',
            'call_type': 'phone',
        })

        resp = self.opener.put(
            self.base_url()
            + '/freeswitch/webhook/voicemail/%s/vm-http-existing.wav'
            % self._token(),
            data=b'RIFFxxxx')

        self.assertEqual(resp.status_code, 200)
        recording = self.env['connect.recording'].sudo().search([
            ('call_sid', '=', 'vm-http-existing'),
            ('source', '=', 'freeswitch_voicemail'),
        ], limit=1)
        self.assertTrue(recording)
        call.invalidate_recordset()
        self.assertEqual(call.voicemail_url, recording.get_attachment_media_url())


@tagged('post_install', '-at_install', 'connect_freeswitch_webhook_token')
class RecordingUrlCase(TransactionCase):

    def test_recording_webhook_url_embeds_token(self):
        settings = self.env['connect.settings']
        token = settings.sudo().get_param('freeswitch_webhook_token')
        url = settings.get_recording_webhook_url()
        self.assertTrue(url.endswith('/freeswitch/webhook/recording/%s'
                                     % token))

    def test_recording_webhook_url_empty_without_token(self):
        self.env['connect.settings'].sudo().set_param(
            'freeswitch_webhook_token', False)
        self.assertEqual(
            self.env['connect.settings'].get_recording_webhook_url(), '')

    def test_voicemail_webhook_url_embeds_token(self):
        settings = self.env['connect.settings']
        token = settings.sudo().get_param('freeswitch_webhook_token')
        url = settings.get_voicemail_webhook_url()
        self.assertTrue(url.endswith('/freeswitch/webhook/voicemail/%s'
                                     % token))

    def test_voicemail_webhook_url_empty_without_token(self):
        self.env['connect.settings'].sudo().set_param(
            'freeswitch_webhook_token', False)
        self.assertEqual(
            self.env['connect.settings'].get_voicemail_webhook_url(), '')

    def test_orphan_voicemail_upload_is_linked_by_cdr(self):
        recording = self.env['connect.recording'].with_context(
            skip_transcription=True).create({
                'call_sid': 'vm-cdr-orphan',
                'status': 'completed',
                'source': 'freeswitch_voicemail',
                'recording_attachment': base64.b64encode(b'RIFFxxxx'),
                'recording_filename': 'vm-cdr-orphan.wav',
            })

        with patch.object(
                type(self.env['oduist.license']),
                'check_license',
                return_value=True), patch.object(
                    type(self.env['connect.settings']),
                    'connect_reload_view'):
            self.env['connect.call']._process_cdr_locked({
                'uuid': 'vm-cdr-orphan',
                'caller': '+15551111111',
                'called': '+15552222222',
                'direction': 'inbound',
                'hangup_cause': 'NORMAL_CLEARING',
                'duration': 7,
            })

        recording.invalidate_recordset()
        self.assertTrue(recording.call)
        self.assertEqual(
            recording.call.voicemail_url,
            recording.get_attachment_media_url())

# -*- coding: utf-8 -*-
"""VoiceML signature validation on webhook URLs that carry a query string.

VoiceTel signs the request URL — query string included — plus the POST body
parameters. Odoo merges the query string into the route kwargs, so
validating with those counts every query parameter twice: the
``?done_callflows=`` marker on the ``<Dial>`` action URL made every rejected
call answer "Invalid VoiceTel request!".
"""
from voiceml.webhooks import RequestValidator

from odoo.tests import HttpCase, tagged, new_test_user

API_KEY = 'sig_test_api_key'
PAYLOAD = {
    'CallSid': 'CAsignaturetest',
    'CallStatus': 'in-progress',
    'DialCallStatus': 'busy',
}


@tagged('post_install', '-at_install')
class TestWebhookSignature(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        settings = cls.env['connect.settings'].sudo()
        settings.set_param('voicetel_api_key', API_KEY)
        settings.set_param('voicetel_verify_requests', True)
        odoo_user = new_test_user(cls.env, login='sig_test_user')
        cls.pbx_user = cls.env['connect.user'].with_context(
            no_clear_cache=True, no_voicetel_create=True).create({
                'user': odoo_user.id,
                'voicetel_sip_enabled': False,
            })

    def _post(self, path, signed_path=None):
        url = self.base_url() + path
        # The controller https-izes the URL before validating, because that
        # is the scheme VoiceTel signed.
        signature = RequestValidator(API_KEY).compute_signature(
            (self.base_url() + (signed_path or path)).replace(
                'http:', 'https:'),
            PAYLOAD,
        )
        return self.url_open(
            url, data=PAYLOAD, headers={'X-Twilio-Signature': signature})

    def test_action_url_with_query_string_validates(self):
        response = self._post(
            '/voicetel/webhook/connect.user/call_action/{}'
            '?done_callflows=1'.format(self.pbx_user.id))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Invalid VoiceTel request', response.text)

    def test_action_url_without_query_string_still_validates(self):
        response = self._post(
            '/voicetel/webhook/connect.user/call_action/{}'.format(
                self.pbx_user.id))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Invalid VoiceTel request', response.text)

    def test_a_forged_signature_is_still_rejected(self):
        """The fix must not turn validation off."""
        response = self._post(
            '/voicetel/webhook/connect.user/call_action/{}'
            '?done_callflows=1'.format(self.pbx_user.id),
            signed_path='/voicetel/webhook/connect.user/call_action/{}'
                        '?done_callflows=999'.format(self.pbx_user.id),
        )

        self.assertIn('Invalid VoiceTel request', response.text)

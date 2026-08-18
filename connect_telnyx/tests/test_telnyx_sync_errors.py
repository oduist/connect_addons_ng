# -*- coding: utf-8 -*-
from contextlib import ExitStack
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError

from odoo.addons.connect_telnyx.models.settings import Settings


def _telnyx_error(text, status=None):
    """Build an exception shaped like a telnyx SDK API error."""
    err = Exception(text)
    if status is not None:
        err.status_code = status
    return err


# A real Telnyx 403 when the account is not authorized for Voice/TeXML.
_NOT_AUTHORIZED = (
    "Error code: 403 - {'errors': [{'code': '10006', 'title': "
    "'Not authorized', 'detail': 'You are not authorized to access the "
    "requested resource.'}]}"
)


@tagged('at_install', '-post_install')
class TestTelnyxSyncErrors(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Settings = cls.env['connect.settings']
        # telnyx_sync() guards on a set API key and a secure api_url.
        cls.Settings.set_param('telnyx_api_key', 'KEYtest')
        cls.env['ir.config_parameter'].sudo().set_param(
            'connect.api_url', 'https://example.odoo.com')

    def test_not_authorized_maps_to_friendly_error(self):
        # A 403 raised anywhere in the sync (here: the first sub-step) must
        # surface as a clear ValidationError, not a raw Odoo traceback.
        with patch.object(Settings, '_ensure_telnyx_messaging_profile',
                          side_effect=_telnyx_error(_NOT_AUTHORIZED, 403)):
            with self.assertRaises(ValidationError) as cm:
                self.Settings.telnyx_sync()
        message = str(cm.exception)
        self.assertIn('403', message)
        self.assertIn('Mission Control', message)

    def test_not_authorized_matched_by_body_without_status(self):
        # Even if the exception carries no status_code, the 10006 / "not
        # authorized" body is enough to recognise the access error.
        with patch.object(Settings, '_ensure_telnyx_messaging_profile',
                          side_effect=_telnyx_error(_NOT_AUTHORIZED)):
            with self.assertRaises(ValidationError) as cm:
                self.Settings.telnyx_sync()
        self.assertIn('Mission Control', str(cm.exception))

    def test_authentication_error_maps_to_key_message(self):
        with patch.object(Settings, '_ensure_telnyx_messaging_profile',
                          side_effect=_telnyx_error('Error code: 401', 401)):
            with self.assertRaises(ValidationError) as cm:
                self.Settings.telnyx_sync()
        self.assertIn('API key', str(cm.exception))

    def test_unrelated_error_is_reraised_unchanged(self):
        with patch.object(Settings, '_ensure_telnyx_messaging_profile',
                          side_effect=_telnyx_error('boom')):
            with self.assertRaises(Exception) as cm:
                self.Settings.telnyx_sync()
        self.assertNotIsInstance(cm.exception, ValidationError)
        self.assertEqual(str(cm.exception), 'boom')

    def test_sub_sync_validation_error_is_preserved(self):
        with patch.object(Settings, '_ensure_telnyx_messaging_profile',
                          side_effect=ValidationError('WhatsApp not enabled')):
            with self.assertRaises(ValidationError) as cm:
                self.Settings.telnyx_sync()
        self.assertEqual(str(cm.exception), 'WhatsApp not enabled')

    def test_optional_sync_error_notification_is_sticky(self):
        sync_models = [
            'connect.telnyx.texml',
            'connect.telnyx.ai_assistant',
            'connect.telnyx.domain',
            'connect.telnyx.number',
            'connect.telnyx.outgoing_callerid',
            'connect.telnyx.whatsapp_sender',
            'connect.telnyx.whatsapp_template',
            'connect.telnyx.rcs_agent',
        ]
        with ExitStack() as stack:
            stack.enter_context(patch.object(
                Settings, '_ensure_telnyx_messaging_profile',
                autospec=True, return_value=True))
            stack.enter_context(patch.object(
                Settings, '_sync_telnyx_tts_voices',
                autospec=True, return_value=[]))
            for model_name in sync_models:
                kwargs = {'autospec': True, 'return_value': True}
                if model_name == 'connect.telnyx.whatsapp_sender':
                    kwargs = {
                        'autospec': True,
                        'side_effect': ValidationError('Not enabled'),
                    }
                stack.enter_context(patch.object(
                    type(self.env[model_name]), 'sync', **kwargs))
            notify_mock = stack.enter_context(patch.object(
                type(self.Settings), 'connect_notify', autospec=True))

            self.Settings.telnyx_sync()

        warning_call = next(
            call for call in notify_mock.call_args_list
            if call.kwargs.get('title') == 'Sync Warning'
        )
        self.assertTrue(warning_call.kwargs.get('sticky'))

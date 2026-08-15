# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.connect_telnyx.models.settings import Settings

from .common import TelnyxTestCommon


@tagged('post_install', '-at_install')
class TestTelnyxRouting(TelnyxTestCommon):
    """Inbound routing of calls arriving on a Telnyx number."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env['connect.settings'].sudo()
        cls.settings.set_param('telnyx_auto_sync', False)
        cls.number = cls.env['connect.telnyx.number'].with_context(
            skip_telnyx_sync=True).create({
                'phone_number': '+15550001111',
                'sid': 'number-sid',
            })
        cls.user = cls._create_web_phone_user('telnyx_routing')

    def _request(self, **kwargs):
        request = {
            'To': '+15550001111',
            'Called': '+15550001111',
            'From': '+15550002222',
            'Caller': '+15550002222',
            'CallSid': 'inbound-test',
            'CallStatus': 'initiated',
        }
        request.update(kwargs)
        return request

    def test_inbound_number_call_uses_its_destination(self):
        self.number.with_context(skip_telnyx_sync=True).write({
            'destination': 'user',
            'user': self.user.id,
        })
        with patch.object(type(self.env['connect.call']),
                          'on_telnyx_call_status', autospec=True):
            result = str(self.env['connect.telnyx.number'].route_call(
                self._request()))
        self.assertIn('<Dial', result)
        self.assertNotIn('Number not found', result)

    def test_inbound_number_call_falls_back_to_extension(self):
        self.env['connect.telnyx.exten'].create({
            'number': '+15550001111',
            'dst': 'connect.user,{}'.format(self.user.id),
        })
        with patch.object(type(self.env['connect.call']),
                          'on_telnyx_call_status', autospec=True):
            result = str(self.env['connect.telnyx.number'].route_call(
                self._request()))
        self.assertIn('<Dial', result)

    def test_unconfigured_number_does_not_dial_itself(self):
        with patch.object(type(self.env['connect.call']),
                          'on_telnyx_call_status', autospec=True):
            result = str(self.env['connect.telnyx.number'].route_call(
                self._request()))
        self.assertIn('Number not configured', result)
        self.assertNotIn('<Dial', result)

    def test_domain_routes_pstn_leg_to_the_number(self):
        """Numbers attached to the domain application before the number
        application existed still land in domain.route_call()."""
        self.number.with_context(skip_telnyx_sync=True).write({
            'destination': 'user',
            'user': self.user.id,
        })
        with patch.object(type(self.env['connect.call']),
                          'on_telnyx_call_status', autospec=True):
            result = str(self.env['connect.telnyx.domain'].route_call(
                self._request()))
        self.assertIn('<Sip', result)
        self.assertNotIn('<Number', result)

    def test_domain_never_dials_out_for_a_pstn_caller(self):
        """An inbound PSTN leg for an unknown destination must not
        re-originate an outbound call to the dialled number."""
        self.env['connect.telnyx.outgoing_callerid'].create({
            'number': '+15550003333',
            'friendly_name': 'Default',
            'is_default': True,
        })
        request = self._request(To='+15550009999', Called='+15550009999')
        with patch.object(type(self.env['connect.call']),
                          'on_telnyx_call_status', autospec=True):
            result = str(self.env['connect.telnyx.domain'].route_call(request))
        self.assertIn('Extension not found', result)
        self.assertNotIn('<Dial', result)

    def test_domain_dials_out_for_a_sip_caller(self):
        self.env['connect.telnyx.outgoing_callerid'].create({
            'number': '+15550003333',
            'friendly_name': 'Default',
            'is_default': True,
        })
        request = self._request(
            To='+15550009999', Called=False,
            Caller='sip:user@example.sip.telnyx.com')
        with patch.object(type(self.env['connect.call']),
                          'on_telnyx_call_status', autospec=True):
            result = str(self.env['connect.telnyx.domain'].route_call(request))
        self.assertIn('<Number', result)

    def test_messaging_failure_does_not_abort_the_number_update(self):
        class Messaging:
            @staticmethod
            def update(*args, **kwargs):
                raise Exception('409 Messaging activation failed')

        class PhoneNumbers:
            messaging = Messaging()

            @staticmethod
            def update(*args, **kwargs):
                return True

        class Client:
            phone_numbers = PhoneNumbers()

        self.settings.set_param(
            'telnyx_messaging_profile_id', 'profile-test')
        self.env['connect.telnyx.number'].get_number_app().with_context(
            skip_telnyx_sync=True).write({'sid': 'number-app-sid'})
        # Must not raise: a number without SMS capability may still be
        # used for voice.
        self.number.update_telnyx_number(Client())

    def test_account_sid_is_taken_from_whoami(self):
        self.settings.set_param('telnyx_account_sid', False)

        def api_response(_self, method, path, **kwargs):
            self.assertEqual(path, 'whoami')
            return {'data': {'organization_id': 'org-test',
                             'user_id': 'user-test'}}

        with patch.object(Settings, 'telnyx_api_request', autospec=True,
                          side_effect=api_response):
            account_sid = self.settings._ensure_telnyx_account_sid()
        self.assertEqual(account_sid, 'org-test')
        self.assertEqual(
            self.settings.get_param('telnyx_account_sid'), 'org-test')


@tagged('post_install', '-at_install')
class TestTelnyxChannelMapping(TelnyxTestCommon):
    """Telnyx reports the call parties differently depending on the
    webhook, and the ledger has to store them either way."""

    def test_application_webhook_params(self):
        mapped = self.env['connect.channel']._map_telnyx_params({
            'CallSid': 'call-1',
            'Caller': '+15550001111',
            'Called': '+15550002222',
            'To': '+15550002222',
            'CallStatus': 'ringing',
            'Direction': 'inbound',
        })
        self.assertEqual(mapped['caller'], '+15550001111')
        self.assertEqual(mapped['called'], '+15550002222')

    def test_call_progress_params_use_from_and_to(self):
        mapped = self.env['connect.channel']._map_telnyx_params({
            'CallSid': 'call-2',
            'From': '+15550001111',
            'To': '+15550002222',
            'CallerId': '+15550001111',
            'CallStatus': 'completed',
            'CallDuration': '9',
            'Direction': 'inbound',
        })
        self.assertEqual(mapped['caller'], '+15550001111')
        self.assertEqual(mapped['called'], '+15550002222')
        self.assertEqual(mapped['duration'], 9)

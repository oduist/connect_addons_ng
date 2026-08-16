# -*- coding: utf-8 -*-
from contextlib import ExitStack
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.connect.models.settings import Settings as CoreSettings
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

    def test_inbound_dialplan_carries_the_caller_id(self):
        """The web phone shows who is calling only if the Dial verb has
        a caller ID; an inbound PSTN webhook reports it as From."""
        user = self._create_web_phone_user('telnyx_caller_id')
        request = {
            'To': '+15550001111', 'Called': '+15550001111',
            'From': '+15550007777', 'CallerId': '+15550007777',
            'CallSid': 'caller-id-test', 'CallStatus': 'initiated',
        }
        result = str(user.telnyx_render(request=request))
        self.assertIn('callerId="+15550007777"', result)


@tagged('post_install', '-at_install')
class TestTelnyxOutboundVoiceProfile(TelnyxTestCommon):
    """Telnyx rejects an outbound call from a connection that carries no
    outbound voice profile, before any webhook reaches Odoo."""

    def test_profile_is_taken_from_the_account(self):
        self.env['connect.settings'].sudo().set_param(
            'telnyx_outbound_voice_profile_id', False)

        def api_response(_self, method, path, **kwargs):
            self.assertEqual((method, path), ('GET', 'outbound_voice_profiles'))
            return {'data': [{'id': 'ovp-1', 'name': 'Default', 'enabled': True}]}

        with patch.object(Settings, 'telnyx_api_request', autospec=True,
                          side_effect=api_response):
            profile_id = self.env[
                'connect.settings']._ensure_telnyx_outbound_voice_profile()
        self.assertEqual(profile_id, 'ovp-1')

    def test_texml_app_params_carry_the_profile(self):
        self.env['connect.settings'].sudo().set_param(
            'telnyx_outbound_voice_profile_id', 'ovp-1')
        params = self.env['connect.telnyx.number'].get_number_app(
        )._texml_app_params()
        self.assertEqual(
            params['outbound'], {'outbound_voice_profile_id': 'ovp-1'})

    def test_sync_resolves_the_profile_up_front(self):
        """The profile is provisioned by the account sync, not by hand."""
        self.settings = self.env['connect.settings'].sudo()
        self.settings.set_param('telnyx_outbound_voice_profile_id', False)
        paths = []

        def api_response(_self, method, path, **kwargs):
            paths.append(path)
            if path == 'outbound_voice_profiles':
                return {'data': [{'id': 'ovp-sync', 'enabled': True}]}
            return {'data': {}}

        sync_models = [
            'connect.telnyx.texml', 'connect.telnyx.ai_assistant',
            'connect.telnyx.domain', 'connect.telnyx.number',
            'connect.telnyx.outgoing_callerid',
            'connect.telnyx.whatsapp_sender',
            'connect.telnyx.whatsapp_template', 'connect.telnyx.rcs_agent',
        ]
        with ExitStack() as stack:
            stack.enter_context(patch.object(
                Settings, 'telnyx_api_request', autospec=True,
                side_effect=api_response))
            stack.enter_context(patch.object(
                Settings, '_ensure_telnyx_messaging_profile', autospec=True,
                return_value='profile'))
            for model_name in sync_models:
                stack.enter_context(patch.object(
                    type(self.env[model_name]), 'sync', autospec=True,
                    return_value=True))
            stack.enter_context(patch.object(
                CoreSettings, 'connect_notify', autospec=True))
            self.env['connect.settings'].telnyx_sync()
        self.assertIn('outbound_voice_profiles', paths)
        self.assertEqual(
            self.env['connect.settings'].get_param(
                'telnyx_outbound_voice_profile_id'), 'ovp-sync')

    def test_missing_profile_does_not_break_the_resource(self):
        """A profile that cannot be resolved is logged, not raised."""
        self.env['connect.settings'].sudo().set_param(
            'telnyx_outbound_voice_profile_id', False)

        def api_error(_self, method, path, **kwargs):
            raise ValidationError('Telnyx API returned HTTP 403')

        with patch.object(Settings, 'telnyx_api_request', autospec=True,
                          side_effect=api_error):
            params = self.env['connect.telnyx.number'].get_number_app(
            )._texml_app_params()
        self.assertNotIn('outbound', params)

    def test_blocked_destination_is_reported(self):
        """A profile that forbids our own country is the reason outbound
        calls die before any webhook — say so instead of staying silent."""
        settings = self.env['connect.settings'].sudo()
        settings.set_param('telnyx_outbound_voice_profile_id', 'ovp-1')
        self.env['connect.telnyx.outgoing_callerid'].create({
            'number': '+48221811500',
            'friendly_name': 'PL number',
        })

        def api_response(_self, method, path, **kwargs):
            return {'data': {'id': 'ovp-1', 'name': 'Default',
                             'whitelisted_destinations': ['US', 'CA']}}

        with patch.object(Settings, 'telnyx_api_request', autospec=True,
                          side_effect=api_response), patch.object(
                              CoreSettings, 'connect_notify',
                              autospec=True) as notify:
            ok = settings._check_telnyx_outbound_destinations()
        self.assertFalse(ok)
        message = notify.call_args[0][1]
        self.assertIn('PL', message)
        self.assertIn('rejected by Telnyx', message)

    def test_allowed_destination_is_not_reported(self):
        settings = self.env['connect.settings'].sudo()
        settings.set_param('telnyx_outbound_voice_profile_id', 'ovp-1')
        self.env['connect.telnyx.outgoing_callerid'].create({
            'number': '+15550004321',
            'friendly_name': 'US number',
        })

        def api_response(_self, method, path, **kwargs):
            return {'data': {'id': 'ovp-1', 'name': 'Default',
                             'whitelisted_destinations': ['US', 'CA']}}

        with patch.object(Settings, 'telnyx_api_request', autospec=True,
                          side_effect=api_response), patch.object(
                              CoreSettings, 'connect_notify',
                              autospec=True) as notify:
            ok = settings._check_telnyx_outbound_destinations()
        self.assertTrue(ok)
        notify.assert_not_called()

    def test_destinations_typed_in_settings_reach_telnyx(self):
        """The administrator edits the allowed regions in Odoo."""
        settings = self.env['connect.settings'].sudo()
        settings.set_param('telnyx_outbound_voice_profile_id', 'ovp-1')
        captured = {}

        def api_response(_self, method, path, **kwargs):
            captured['method'] = method
            captured['path'] = path
            captured['payload'] = kwargs.get('payload')
            return {'data': {'id': 'ovp-1'}}

        with patch.object(Settings, 'telnyx_api_request', autospec=True,
                          side_effect=api_response):
            settings.search([], limit=1).write(
                {'telnyx_outbound_destinations': 'pl , de,US'})
        self.assertEqual(captured['method'], 'PATCH')
        self.assertEqual(captured['path'], 'outbound_voice_profiles/ovp-1')
        self.assertEqual(
            captured['payload'], {'whitelisted_destinations': ['PL', 'DE', 'US']})

    def test_empty_destinations_allow_everything(self):
        settings = self.env['connect.settings'].sudo()
        settings.set_param('telnyx_outbound_voice_profile_id', 'ovp-1')
        captured = {}

        def api_response(_self, method, path, **kwargs):
            captured['payload'] = kwargs.get('payload')
            return {'data': {'id': 'ovp-1'}}

        with patch.object(Settings, 'telnyx_api_request', autospec=True,
                          side_effect=api_response):
            settings.search([], limit=1).write(
                {'telnyx_outbound_destinations': ''})
        self.assertEqual(captured['payload'], {'whitelisted_destinations': []})

    def test_connection_params_carry_the_profile(self):
        self.env['connect.settings'].sudo().set_param(
            'telnyx_outbound_voice_profile_id', 'ovp-1')
        self.assertEqual(
            self.domain._connection_outbound_params(),
            {'outbound_voice_profile_id': 'ovp-1'})


@tagged('post_install', '-at_install')
class TestTelnyxCredentialUri(TelnyxTestCommon):
    """A credential answers on the SIP domain of its own connection, and
    Telnyx rejects a leg carrying an empty X- header."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls._create_web_phone_user('telnyx_uri')

    def test_uri_rings_the_generic_host(self):
        """A credential is rung at sip.telnyx.com; the domain subdomain
        is the inbound side and would loop the leg back into Odoo."""
        uri = self.user._telnyx_credential_uri('client-user')
        self.assertEqual(uri, 'sip:client-user@sip.telnyx.com')
        self.assertNotIn(self.domain.subdomain, uri)

    def test_empty_headers_are_dropped(self):
        uri = self.user._telnyx_credential_uri(
            'client-user', [('X-CallerName', ''), ('X-Partner', 7)])
        self.assertEqual(uri, 'sip:client-user@sip.telnyx.com?X-Partner=7')
        self.assertNotIn('=&', uri)
        self.assertFalse(uri.endswith('='))

    def test_inbound_dialplan_has_no_empty_headers(self):
        """An inbound PSTN call has neither partner nor caller name, and
        that used to render '?X-CallerName=&X-Partner=' — Telnyx answered
        'The custom_headers parameter is invalid' and dropped the leg."""
        request = {
            'To': '+15550001111', 'Called': '+15550001111',
            'From': '+15550009999', 'CallSid': 'uri-test',
            'CallStatus': 'initiated',
        }
        result = str(self.user.telnyx_render(request=request))
        self.assertIn('@sip.telnyx.com', result)
        self.assertNotIn('=&', result)
        self.assertNotIn('X-CallerName=<', result)
        self.assertNotIn('sip.telnyx.com?X-CallerName=&', result)

    def test_domain_refuses_a_credential_leg(self):
        """A leg addressed at a credential must never be re-routed by the
        subdomain application: that is an infinite loop."""
        request = {
            'To': 'client-telnyx_uri@test-connect.sip.telnyx.com',
            'From': '+15550009999', 'CallSid': 'loop-test',
            'CallStatus': 'initiated',
        }
        with patch.object(type(self.env['connect.call']),
                          'on_telnyx_call_status', autospec=True):
            result = str(self.env['connect.telnyx.domain'].route_call(request))
        self.assertIn('loop', result.lower())
        self.assertNotIn('<Dial', result)

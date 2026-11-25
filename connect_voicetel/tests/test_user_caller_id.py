# -*- coding: utf-8 -*-
"""Caller ID presented for calls a VoiceTel PBX user places.

An empty caller ID is not neutral: the platform replaces it with a number of
its own, which then shows on the callee's phone and lands in the ledger as a
bogus caller.
"""
from unittest.mock import patch

from odoo.tests import tagged
from odoo.addons.connect_voicetel.models.voiceml_response import VoiceResponse

from .common import VoiceTelTestCommon


@tagged('at_install', '-post_install')
class TestUserCallerId(VoiceTelTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'connect.api_url', 'https://odoo.test/')
        cls.env['ir.config_parameter'].sudo().set_param(
            'web.base.url', 'https://odoo.test/')
        Settings = type(cls.env['connect.settings'])
        with patch.object(Settings, 'get_voicetel_client', return_value=None):
            cls.domain = cls.env['connect.voicetel.domain'].with_context(
                no_voicetel_create=True).create({
                    'friendly_name': 'callerid-test',
                    'subdomain': 'calleridtest',
                })
        cls.pbx_user = cls._create_connect_user(
            'calleriduser', voicetel_username='calleriduser',
            voicetel_domain=cls.domain.id, voicetel_sip_enabled=True)
        cls.uri = cls.pbx_user.voicetel_uri
        taken = set(
            cls.env['connect.voicetel.exten'].search([]).mapped('number'))
        cls.number = next(
            str(n) for n in range(7100, 8000) if str(n) not in taken)
        cls.env['connect.voicetel.outgoing_callerid'].search(
            [('is_default', '=', True)]).is_default = False

    def _default_callerid(self, number='+15550009999'):
        # callerid_type 'number' is an owned number: no validation step, so
        # it may be the default straight away.
        return self.env['connect.voicetel.outgoing_callerid'].create({
            'friendly_name': 'Default',
            'number': number,
            'callerid_type': 'number',
            'is_default': True,
        })

    def test_sip_uri_is_built_from_label_and_suffix(self):
        self.assertEqual(self.domain.domain_name, 'calleridtest.vml.voice.tel')
        self.assertEqual(self.uri, 'calleriduser@calleridtest.vml.voice.tel')
        self.assertEqual(
            self.domain.wss_url, 'wss://calleridtest.vml.voice.tel:8443')

    def test_extension_is_the_caller_id(self):
        self._default_callerid()
        self.env['connect.voicetel.exten'].create({
            'number': self.number,
            'dst': 'connect.user,{}'.format(self.pbx_user.id),
        })

        self.assertEqual(self.pbx_user.voicetel_caller_id(), self.number)

    def test_without_extension_falls_back_to_the_default_callerid(self):
        default = self._default_callerid()

        self.assertEqual(self.pbx_user.voicetel_caller_id(), default.number)

    def test_own_outgoing_callerid_wins_over_the_default(self):
        self._default_callerid()
        own = self.env['connect.voicetel.outgoing_callerid'].create({
            'friendly_name': 'Own',
            'number': '+15550008888',
            'callerid_type': 'number',
        })
        self.pbx_user.voicetel_outgoing_callerid = own

        self.assertEqual(self.pbx_user.voicetel_caller_id(), own.number)

    def test_last_resort_is_the_sip_username(self):
        """With no number to present, the caller is still not anonymous."""
        self.assertEqual(
            self.pbx_user.voicetel_caller_id(), self.pbx_user.voicetel_username)

    def test_dialplan_caller_id_resolves_the_calling_user(self):
        """_voicetel_get_caller_id maps the calling SIP URI to its caller ID."""
        self._default_callerid()
        self.env['connect.voicetel.exten'].create({
            'number': self.number,
            'dst': 'connect.user,{}'.format(self.pbx_user.id),
        })

        caller_id = self.env['connect.user']._voicetel_get_caller_id(
            {'Caller': 'sip:{}'.format(self.uri)}, {})

        self.assertEqual(caller_id, self.number)

    def test_a_user_on_another_domain_is_not_matched(self):
        """Same username, foreign host: left to the other provider."""
        user = self.env['connect.user'].get_user_by_uri(
            'sip:calleriduser@other.sip.example.com')

        self.assertNotEqual(user, self.pbx_user)

    def test_unknown_caller_is_passed_through(self):
        caller_id = self.env['connect.user']._voicetel_get_caller_id(
            {'Caller': '+19789814066'}, {})

        self.assertEqual(caller_id, '+19789814066')

    def test_user_leg_is_one_sip_noun_on_the_tenant_domain(self):
        """Browser and desk phones share the credential: one <Sip> rings all."""
        response = VoiceResponse()
        self.pbx_user.voicetel_render_sip(response, {'Caller': '+19789814066'}, {})
        dialplan = str(response)

        self.assertIn('<Sip', dialplan)
        self.assertIn('sip:{}'.format(self.uri), dialplan)
        self.assertNotIn('<Client', dialplan)
        self.assertIn('callerId="+19789814066"', dialplan)
        self.assertIn(
            'https://odoo.test/voicetel/webhook/connect.user/call_action/{}'.format(
                self.pbx_user.id),
            dialplan)
        self.assertNotIn('#e=', dialplan)

    def test_enabling_sip_registers_the_sip_callflow(self):
        flows = self.env['connect.voicetel.user_callflow'].search(
            [('user', '=', self.pbx_user.id)])

        self.assertEqual(flows.mapped('callflow_type'), ['sip'])
        self.assertEqual(flows.method, 'voicetel_render_sip')

# -*- coding: utf-8 -*-
"""Caller ID presented for calls a PBX user places.

An empty caller ID is not neutral: Twilio replaces it with an arbitrary
number of its own, which then shows on the callee's phone and lands in the
ledger as a bogus caller.
"""
from unittest.mock import patch

from odoo.tests import tagged

from .common import TwilioTestCommon


@tagged('at_install', '-post_install')
class TestUserCallerId(TwilioTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Settings = type(cls.env['connect.settings'])
        with patch.object(Settings, 'get_client', return_value=None):
            cls.domain = cls.env['connect.twilio.domain'].with_context(
                no_twilio_create=True).create({
                    'friendly_name': 'callerid-test',
                    'subdomain': 'calleridtest',
                })
        cls.pbx_user = cls._create_connect_user(
            'calleriduser', username='calleriduser', domain=cls.domain.id)
        cls.identity = cls.pbx_user.get_client_identity()
        taken = set(
            cls.env['connect.twilio.exten'].search([]).mapped('number'))
        cls.number = next(
            str(n) for n in range(7100, 8000) if str(n) not in taken)
        cls.env['connect.twilio.outgoing_callerid'].search(
            [('is_default', '=', True)]).is_default = False

    def _default_callerid(self, number='+15550009999'):
        # callerid_type 'number' is a Twilio-owned number: no validation
        # step, so it may be the default straight away.
        return self.env['connect.twilio.outgoing_callerid'].create({
            'friendly_name': 'Default',
            'number': number,
            'callerid_type': 'number',
            'is_default': True,
        })

    def test_extension_is_the_caller_id(self):
        self._default_callerid()
        self.env['connect.twilio.exten'].create({
            'number': self.number,
            'dst': 'connect.user,{}'.format(self.pbx_user.id),
        })

        self.assertEqual(self.pbx_user.twilio_caller_id(), self.number)

    def test_without_extension_falls_back_to_the_default_callerid(self):
        default = self._default_callerid()

        self.assertEqual(self.pbx_user.twilio_caller_id(), default.number)

    def test_own_outgoing_callerid_wins_over_the_default(self):
        self._default_callerid()
        own = self.env['connect.twilio.outgoing_callerid'].create({
            'friendly_name': 'Own',
            'number': '+15550008888',
            'callerid_type': 'number',
        })
        self.pbx_user.twilio_outgoing_callerid = own

        self.assertEqual(self.pbx_user.twilio_caller_id(), own.number)

    def test_last_resort_is_the_client_identity(self):
        """With no number to present, the caller is still not anonymous."""
        self.assertEqual(
            self.pbx_user.twilio_caller_id(),
            'client:{}'.format(self.identity),
        )

    def test_caller_id_is_never_empty_for_a_registered_user(self):
        """The fallback is what keeps Twilio from inventing a number."""
        self.assertTrue(self.pbx_user.twilio_caller_id())

    def test_dialplan_caller_id_resolves_the_calling_user(self):
        """_get_caller_id maps the calling client URI to its own caller ID."""
        self._default_callerid()
        self.env['connect.twilio.exten'].create({
            'number': self.number,
            'dst': 'connect.user,{}'.format(self.pbx_user.id),
        })

        caller_id = self.env['connect.user']._get_caller_id(
            {'Caller': 'client:{}'.format(self.identity)}, {})

        self.assertEqual(caller_id, self.number)

    def test_unknown_caller_is_passed_through(self):
        caller_id = self.env['connect.user']._get_caller_id(
            {'Caller': '+19789814066'}, {})

        self.assertEqual(caller_id, '+19789814066')

    def test_client_identity_fallback_resolves_back_to_the_user(self):
        """The ledger has to read the fallback back as the calling user."""
        channel = self.env['connect.channel'].create({
            'sid': 'CAcalleridfallback',
            'caller': self.pbx_user.twilio_caller_id(),
        })

        self.assertEqual(channel.caller_number, self.pbx_user.username)

    def test_web_phone_is_told_the_extension_not_the_e164_form(self):
        """Twilio hands the callee '+101'; the widget must show '101'."""
        from twilio.twiml.voice_response import VoiceResponse

        exten = self.env['connect.twilio.exten'].create({
            'number': self.number,
            'dst': 'connect.user,{}'.format(self.pbx_user.id),
        })
        response = VoiceResponse()
        self.pbx_user.render_client(
            response,
            {'Caller': 'client:{}'.format(self.identity)},
            {},
        )
        dialplan = str(response)

        self.assertIn('callerId="{}"'.format(exten.number), dialplan)
        self.assertIn(
            '<Parameter name="From" value="{}"'.format(exten.number),
            dialplan,
        )

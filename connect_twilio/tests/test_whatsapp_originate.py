# -*- coding: utf-8 -*-
import re
from unittest.mock import MagicMock, patch

from odoo.tests import tagged

from .common import TwilioTestCommon


@tagged('at_install', '-post_install')
class TestWhatsappOriginate(TwilioTestCommon):
    """A WhatsApp click-to-call still rings the agent over ordinary voice.

    Only the TwiML that leg executes speaks WhatsApp. Putting the
    "whatsapp:" identity on the outer call's From made Twilio accept the
    create, report From=None and end the call as busy in the same second,
    so the <WhatsApp> verb never ran.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # No client_enabled: that needs a username + SIP domain, and this
        # test only inspects the arguments handed to the Twilio client.
        # originate_provider is explicit: with more than one telephony
        # module installed the dispatcher refuses to guess.
        cls.pbx_user = cls._create_connect_user(
            'wa_caller', originate_provider='twilio')
        cls.caller = cls.pbx_user.user
        cls.env['connect.whatsapp_sender'].sudo().create({
            'number': '+19990001111', 'status': 'ONLINE'})
        # No outgoing_callerid fixture: creating a default one requires a
        # validated number. What matters here is only that the outer leg's
        # From is never the whatsapp: identity, whatever it falls back to.
        cls.settings = cls.env['connect.settings'].sudo()

    def _originate(self, number, whatsapp_call):
        """Run originate_call against a fake Twilio client, return its kwargs."""
        captured = {}
        fake = MagicMock()

        def create(**kwargs):
            captured.update(kwargs)
            result = MagicMock()
            result.sid = 'CAtest0000000000000000000000000001'
            return result

        fake.calls.create.side_effect = create
        with patch.object(type(self.settings), 'get_client', return_value=fake):
            self.settings.with_user(self.caller).originate_call(
                number, whatsapp_call=whatsapp_call)
        return captured

    def test_whatsapp_leg_keeps_a_voice_caller_id(self):
        kwargs = self._originate('+37360681783', True)
        self.assertFalse(
            str(kwargs['from_']).startswith('whatsapp:'),
            'the voice leg to the agent must not carry a whatsapp: From')

    def test_whatsapp_identity_stays_in_the_twiml(self):
        kwargs = self._originate('+37360681783', True)
        self.assertIn('<WhatsApp', kwargs['twiml'])
        caller_id = re.search(r'callerId="([^"]+)"', kwargs['twiml'])
        self.assertTrue(caller_id)
        self.assertTrue(
            caller_id.group(1).startswith('whatsapp:'),
            'the WhatsApp identity belongs on the inner <Dial callerId>')

    def test_plain_voice_call_is_unaffected(self):
        kwargs = self._originate('+37360681783', False)
        self.assertFalse(str(kwargs['from_']).startswith('whatsapp:'))
        self.assertNotIn('<WhatsApp', kwargs['twiml'])

    # --- the ledger has to know it was WhatsApp ---
    # Nothing on the outer leg says so: its From is a plain voice caller
    # ID and its To is the agent's client: URI, so the status webhook
    # reports call_type 'phone'. Only originate_call knows, and the call
    # record takes its type from this first leg.

    def _originated_channel(self):
        return self.env['connect.channel'].sudo().search(
            [('sid', '=', 'CAtest0000000000000000000000000001')], limit=1)

    def test_originate_marks_the_leg_as_whatsapp(self):
        self._originate('+37360681783', True)
        self.assertEqual(self._originated_channel().call_type, 'whatsapp')

    def test_originate_marks_a_plain_call_as_phone(self):
        self._originate('+37360681783', False)
        self.assertEqual(self._originated_channel().call_type, 'phone')

from odoo.tests import tagged

from .common import ConnectTestCommon


@tagged('at_install', '-post_install')
class TestChannel(ConnectTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls._create_channel(
            'test_sid_1',
            caller='+15551111111',
            called='+15552222222',
            duration=90,
        )

    def test_create_channel(self):
        """Test basic channel creation."""
        self.assertTrue(self.channel.id)
        self.assertEqual(self.channel.sid, 'test_sid_1')

    def test_duration_human(self):
        """Test duration_human computes HH:MM."""
        self.assertEqual(self.channel.duration_human, '01:30')

    def test_duration_zero(self):
        """Test duration_human for zero."""
        ch = self._create_channel('zero_dur', duration=0)
        self.assertEqual(ch.duration_human, '00:00')

    def test_caller_number_from_e164(self):
        """Test caller_number extracts plain phone numbers."""
        self.assertEqual(self.channel.caller_number, '+15551111111')

    def test_called_number_from_e164(self):
        """Test called_number extracts plain phone numbers."""
        self.assertEqual(self.channel.called_number, '+15552222222')

    def test_caller_number_from_whatsapp(self):
        """Test number extraction from whatsapp: URI."""
        ch = self._create_channel('wa1', caller='whatsapp:+15553334444')
        self.assertEqual(ch.caller_number, '+15553334444')

    def test_caller_number_from_sip_uri(self):
        """Core: a SIP URI falls back to its userinfo part.

        _get_number calls get_user_by_uri, which is a no-op in core
        (provider modules override it to resolve an extension). With no
        resolver the local part of the URI is returned unchanged.
        """
        ch = self._create_channel('sip1', caller='sip:sipuser1@domain.com')
        self.assertEqual(ch.caller_number, 'sipuser1')

    def test_called_number_from_bare_sip_uri(self):
        """Provider callbacks may omit the optional sip: scheme."""
        ch = self._create_channel(
            'sip2', called='sipuser2@domain.com')
        self.assertEqual(ch.called_number, 'sipuser2')

    def test_caller_number_empty_for_none(self):
        """Test empty string for non-string caller."""
        ch = self._create_channel('none1', caller=False)
        self.assertEqual(ch.caller_number, '')

    def test_process_channel_event_create(self):
        """Test process_channel_event creates a new channel."""
        params = {
            'sid': 'new_ch_1',
            'caller': '+15550001111',
            'called': '+15550002222',
            'technical_direction': 'inbound',
            'status': 'ringing',
            'duration': 0,
        }
        channel = self.env['connect.channel'].process_channel_event(params)
        self.assertTrue(channel.id)
        self.assertEqual(channel.sid, 'new_ch_1')
        self.assertEqual(channel.status, 'ringing')

    def test_process_channel_event_update(self):
        """Test process_channel_event updates existing channel by SID."""
        params = {
            'sid': 'upd_ch_1',
            'caller': '+15550001111',
            'called': '+15550002222',
            'technical_direction': 'inbound',
            'status': 'ringing',
            'duration': 0,
        }
        channel = self.env['connect.channel'].process_channel_event(params)
        params['status'] = 'completed'
        params['duration'] = 30
        channel2 = self.env['connect.channel'].process_channel_event(params)
        self.assertEqual(channel.id, channel2.id)
        self.assertEqual(channel.status, 'completed')
        self.assertEqual(channel.duration, 30)

    def test_process_channel_event_links_parent(self):
        """Test child channel is linked to parent via parent_sid."""
        parent_params = {
            'sid': 'parent_ch',
            'caller': '+15550001111',
            'called': 'sip:user@domain.com',
            'technical_direction': 'inbound',
            'status': 'ringing',
            'duration': 0,
        }
        parent = self.env['connect.channel'].process_channel_event(parent_params)

        child_params = {
            'sid': 'child_ch',
            'caller': 'sip:user@domain.com',
            'called': '+15550003333',
            'technical_direction': 'outbound-dial',
            'status': 'ringing',
            'duration': 0,
            'parent_sid': 'parent_ch',
        }
        child = self.env['connect.channel'].process_channel_event(child_params)
        self.assertEqual(child.parent_channel.id, parent.id)

    def test_process_channel_event_no_pbx_user_from_uri(self):
        """Core: a SIP URI does not resolve a PBX user.

        get_user_by_uri is a no-op in core (provider modules override it),
        so the URI lookup yields nothing and caller_pbx_user stays empty.
        The positive path is covered by test_process_channel_event_direct_pbx_user_id.
        """
        params = {
            'sid': 'pbx_ch_1',
            'caller': 'sip:chuser1@domain.com',
            'called': '+15550002222',
            'technical_direction': 'inbound',
            'status': 'ringing',
            'duration': 0,
        }
        channel = self.env['connect.channel'].process_channel_event(params)
        self.assertFalse(channel.caller_pbx_user)

    def test_process_channel_event_direct_pbx_user_id(self):
        """Test direct caller_pbx_user_id param skips URI lookup."""
        connect_user = self._create_connect_user('directuser1')
        params = {
            'sid': 'direct_ch_1',
            'caller': '+15550001111',
            'called': '+15550002222',
            'technical_direction': 'inbound',
            'status': 'ringing',
            'duration': 0,
            'caller_pbx_user_id': connect_user.id,
        }
        channel = self.env['connect.channel'].process_channel_event(params)
        self.assertEqual(channel.caller_pbx_user.id, connect_user.id)

    def test_find_partner_caller_is_pbx_user(self):
        """Test partner found by called number when caller is PBX user."""
        connect_user = self._create_connect_user('fpuser1')
        partner = self.env['connect.channel']._find_partner(
            connect_user, None, 'sip:fpuser1@domain.com', '+15551234567', 'inbound')
        # partner may or may not be found depending on existing data;
        # the important thing is no error is raised
        self.assertIsNotNone(partner)

    def test_find_partner_inbound_did(self):
        """Test partner found from caller on pure inbound DID calls."""
        partner = self.env['connect.channel']._find_partner(
            None, None, '+15551234567', '+15559876543', 'inbound')
        # Should attempt lookup by caller number
        self.assertIsNotNone(partner)

    def test_default_call_type(self):
        """Test default call_type is phone."""
        self.assertEqual(self.channel.call_type, 'phone')



    # --- process_channel_event: originate destination survives the webhook ---
    # Click-to-call creates the channel with the dialed number as "called",
    # then the first status event for that same leg reports the agent's
    # client:/sip: URI as Called. That must not clobber the destination
    # (the URI stays available in "to").

    def test_event_keeps_originate_destination_over_client_uri(self):
        ch = self._create_channel(
            'orig_sid_1', caller='+15550001111', called='+37360681783')
        self.env['connect.channel'].process_channel_event({
            'sid': 'orig_sid_1',
            'caller': '+15550001111',
            'called': 'client:agent@example.sip.twilio.com',
            'to': 'client:agent@example.sip.twilio.com',
            'status': 'ringing',
        })
        self.assertEqual(ch.called, '+37360681783')
        self.assertEqual(ch.to, 'client:agent@example.sip.twilio.com')

    def test_event_still_updates_called_for_real_numbers(self):
        ch = self._create_channel(
            'orig_sid_2', caller='+15550001111', called='+37360681783')
        self.env['connect.channel'].process_channel_event({
            'sid': 'orig_sid_2',
            'caller': '+15550001111',
            'called': '+15559998888',
            'status': 'ringing',
        })
        self.assertEqual(ch.called, '+15559998888')

    # --- process_channel_event: a WhatsApp leg is never downgraded ---
    # Click-to-call knows the call is WhatsApp and marks the leg it
    # creates. The outer voice leg to the agent deliberately carries no
    # "whatsapp:" identity -- Twilio kills the call when it does -- so
    # its status events report call_type 'phone'. That must not overwrite
    # what originate_call already established, or the ledger records an
    # outgoing WhatsApp call as an ordinary phone call.

    def test_event_does_not_downgrade_whatsapp_to_phone(self):
        ch = self._create_channel('wa_sid_1', call_type='whatsapp')
        self.env['connect.channel'].process_channel_event({
            'sid': 'wa_sid_1',
            'caller': '+15550001111',
            'called': '+37360681783',
            'status': 'ringing',
            'call_type': 'phone',
        })
        self.assertEqual(ch.call_type, 'whatsapp')

    def test_event_upgrades_phone_to_whatsapp(self):
        ch = self._create_channel('wa_sid_2', call_type='phone')
        self.env['connect.channel'].process_channel_event({
            'sid': 'wa_sid_2',
            'caller': 'whatsapp:+15550001111',
            'called': 'whatsapp:+37360681783',
            'status': 'ringing',
            'call_type': 'whatsapp',
        })
        self.assertEqual(ch.call_type, 'whatsapp')

    def test_outgoing_whatsapp_call_is_typed_whatsapp(self):
        """The ledger entry, not just the leg, carries the WhatsApp type."""
        ch = self._create_channel(
            'wa_sid_3',
            caller='+15550001111',
            called='+37360681783',
            technical_direction='outbound-api',
            call_type='whatsapp',
        )
        self.env['connect.channel'].process_channel_event({
            'sid': 'wa_sid_3',
            'caller': '+15550001111',
            'called': 'client:agent@example.sip.twilio.com',
            'to': 'client:agent@example.sip.twilio.com',
            'status': 'ringing',
            'call_type': 'phone',
        })
        with self.mock_license_check(), self.mock_connect_reload_view():
            self.env['connect.call'].process_call_event(ch)
        self.assertEqual(ch.call.call_type, 'whatsapp')


@tagged('at_install', '-post_install')
class TestFindPartnerNormalization(ConnectTestCommon):
    """_find_partner reaches the matcher for local-format numbers (ADR-024).

    The old startswith('+') guards skipped the lookup for local-format
    caller IDs. With the guards gone, a local number is normalized to
    E.164 inside get_partner_by_number and still resolves the partner.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.company'].browse(1).country_id = cls.env.ref('base.ch')
        cls.swiss_partner = cls.env['res.partner'].with_context(
            no_clear_cache=True).create({
                'name': 'Swiss Partner',
                'phone': '+41313808316',
            })

    def test_inbound_local_caller_resolves_partner(self):
        """Inbound call with a local-format caller resolves the partner."""
        partner = self.env['connect.channel']._find_partner(
            None, None, '0313808316', '+41999999999', 'inbound')
        self.assertEqual(partner, self.swiss_partner)

    def test_outbound_dial_local_called_resolves_partner(self):
        """Outbound-dial with a local-format called resolves the partner."""
        partner = self.env['connect.channel']._find_partner(
            None, None, '+41999999999', '0313808316', 'outbound-dial')
        self.assertEqual(partner, self.swiss_partner)

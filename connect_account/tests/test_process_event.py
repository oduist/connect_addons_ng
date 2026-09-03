from .common import ConnectAccountTestCommon


class TestProcessEvent(ConnectAccountTestCommon):

    def test_incoming_call_links_unpaid_invoice(self):
        """Drive the real connect.call.process_call_event() hook end-to-end
        (first-leg channel -> call creation) and assert the Account bridge's
        invoice-by-partner auto-link runs as a side effect, rather than
        faking the link by hand."""
        invoice = self._post_invoice(move_type='out_invoice')
        self.env.flush_all()
        # Set the channel's partner directly: connect core's number-matching
        # (_find_partner) is exercised by the core module's own tests, not
        # here — we only need call.partner populated so the Account bridge's
        # invoice-by-partner lookup has something to act on.
        channel = self._create_channel(
            'account-pce1', caller=self.partner.phone, called='+380670000001',
            partner=self.partner.id,
        )
        with self.mock_license_check(True), self.mock_connect_reload_view():
            call_id = self.Call.process_call_event(channel)
        self.assertTrue(call_id)
        self.assertEqual(channel.call.partner, self.partner)
        self.assertEqual(channel.call.invoice, invoice)

    def test_incoming_call_does_not_link_vendor_bill(self):
        self._post_invoice(move_type='in_invoice')
        self.env.flush_all()
        channel = self._create_channel(
            'account-pce2', caller=self.partner.phone, called='+380670000001',
            partner=self.partner.id,
        )
        with self.mock_license_check(True), self.mock_connect_reload_view():
            call_id = self.Call.process_call_event(channel)
        self.assertTrue(call_id)
        self.assertFalse(channel.call.invoice)

    def test_get_ref_reflects_invoice(self):
        invoice = self._post_invoice(move_type='out_invoice')
        call = self._create_call()
        call.invoice = invoice
        self.assertEqual(call.ref, invoice)

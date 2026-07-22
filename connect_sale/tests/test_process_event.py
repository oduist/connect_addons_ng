from .common import ConnectSaleTestCommon


class TestProcessEvent(ConnectSaleTestCommon):

    def test_incoming_call_links_open_order(self):
        """Drive the real connect.call.process_call_event() hook end-to-end
        (first-leg channel -> call creation) and assert the Sale bridge's
        order-by-partner auto-link runs as a side effect, rather than faking
        the link by hand."""
        order = self.Order.create({'partner_id': self.partner.id})
        self.env.flush_all()
        # Set the channel's partner directly: connect core's number-matching
        # (_find_partner) is exercised by the core module's own tests, not
        # here — we only need call.partner populated so the Sale bridge's
        # order-by-partner lookup has something to act on.
        channel = self._create_channel(
            'sale-pce1', caller=self.partner.phone, called='+380670000001',
            partner=self.partner.id,
        )
        with self.mock_license_check(True), self.mock_connect_reload_view():
            call_id = self.Call.process_call_event(channel)
        self.assertTrue(call_id)
        self.assertEqual(channel.call.partner, self.partner)
        self.assertEqual(channel.call.sale_order, order)

    def test_get_ref_reflects_sale_order(self):
        order = self.Order.create({'partner_id': self.partner.id})
        call = self._create_call()
        call.sale_order = order
        self.assertEqual(call.ref, order)

    def test_create_with_connect_call_id_backlinks_call(self):
        call = self._create_call()
        order = self.Order.with_context(connect_call_id=call.id).create({
            'partner_id': self.partner.id,
        })
        self.env.flush_all()
        self.assertEqual(call.sale_order, order)

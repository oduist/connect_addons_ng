from .common import ConnectAccountTestCommon


class TestInvoiceLookup(ConnectAccountTestCommon):

    def test_vendor_bill_is_ignored(self):
        self._post_invoice(move_type='in_invoice')  # vendor bill for self.partner
        self.assertFalse(self.Move.get_invoice_by_partner(self.partner))

    def test_customer_unpaid_invoice_found(self):
        inv = self._post_invoice(move_type='out_invoice')
        self.assertEqual(self.Move.get_invoice_by_partner(self.partner), inv)

    def test_paid_invoice_is_ignored(self):
        inv = self._post_invoice(move_type='out_invoice', pay=True)
        self.assertEqual(inv.payment_state, 'paid')
        self.assertFalse(self.Move.get_invoice_by_partner(self.partner))

    def test_no_partner_returns_empty(self):
        self.assertFalse(self.Move.get_invoice_by_partner(self.env['res.partner']))

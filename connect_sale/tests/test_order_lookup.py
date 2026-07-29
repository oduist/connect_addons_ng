from .common import ConnectSaleTestCommon


class TestOrderLookup(ConnectSaleTestCommon):

    def test_returns_open_order(self):
        order = self.Order.create({'partner_id': self.partner.id})
        self.env.flush_all()
        self.assertEqual(self.Order.get_order_by_partner(self.partner), order)

    def test_no_partner_returns_empty(self):
        self.assertFalse(self.Order.get_order_by_partner(self.env['res.partner']))

    def test_returns_newest_open_order(self):
        self.Order.create({'partner_id': self.partner.id})
        newest = self.Order.create({'partner_id': self.partner.id})
        self.env.flush_all()
        self.assertEqual(self.Order.get_order_by_partner(self.partner), newest)

    def test_cancelled_only_returns_empty(self):
        order = self.Order.create({'partner_id': self.partner.id})
        order.action_cancel()
        self.env.flush_all()
        self.assertFalse(self.Order.get_order_by_partner(self.partner))

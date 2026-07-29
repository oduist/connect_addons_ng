# -*- coding: utf-8 -*-
import json

from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestElevenlabsSaleTools(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.token = 'test-elevenlabs-token'
        cls.env['connect.settings'].sudo().set_param(
            'elevenlabs_agent_token', cls.token)
        cls.partner = cls.env['res.partner'].create({
            'name': 'Sale Caller',
            'phone': '+15550101010',
        })
        cls.manager = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Sales Manager',
                'login': 'elevenlabs_sale_manager',
                'email': 'elevenlabs-sale-manager@example.com',
                'groups_id': [(6, 0, [cls.env.ref('base.group_user').id])],
            })
        cls.connect_user = cls.env['connect.user'].create({
            'user': cls.manager.id,
        })
        cls.exten = cls.env['connect.twilio.exten'].create({
            'number': '901',
            'model': 'connect.user',
            'res_id': cls.connect_user.id,
        })
        cls.template = cls.env['product.template'].create({
            'name': 'Agent Product',
            'list_price': 42.0,
            'is_published': True,
        })
        cls.product = cls.template.product_variant_id

    def _post_json(self, path, payload):
        return self.opener.post(
            self.base_url() + path,
            data=json.dumps(payload),
            headers={
                'Content-Type': 'application/json',
                'x-elevenlabs-agent-token': self.token,
            })

    def test_get_products_returns_variant_id(self):
        response = self._post_json('/connect_elevenlabs_sale/get_products', {})
        self.assertEqual(response.status_code, 200)
        products = response.json()
        item = next(
            product for product in products
            if product['product_template_id'] == self.template.id)
        self.assertEqual(item['product_id'], self.product.id)
        self.assertEqual(item['product_name'], self.template.name)

    def test_create_order_uses_product_variant(self):
        response = self._post_json('/connect_elevenlabs_sale/create_order', {
            'partner_id': self.partner.id,
            'product_id': self.product.id,
            'product_quantity': 2,
        })
        self.assertEqual(response.status_code, 200)
        order = self.env['sale.order'].search([
            ('name', '=', response.json()['order_name'])], limit=1)
        self.assertEqual(order.order_line.product_id, self.product)
        self.assertEqual(order.order_line.product_uom_qty, 2)

    def test_get_order_returns_twilio_extension(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'user_id': self.manager.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': self.product.get_product_multiline_description_sale(),
                'product_uom': self.product.uom_id.id,
                'product_uom_qty': 1,
                'price_unit': self.product.lst_price,
            })],
        })
        response = self._post_json('/connect_elevenlabs_sale/get_order', {
            'partner_id': self.partner.id,
            'order_name': order.name,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['orders'][0]['manager_extension'], '901')

    def test_get_orders_does_not_require_call_id(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': self.product.get_product_multiline_description_sale(),
                'product_uom': self.product.uom_id.id,
                'product_uom_qty': 1,
                'price_unit': self.product.lst_price,
            })],
        })

        response = self._post_json('/connect_elevenlabs_sale/get_orders', {
            'partner_id': self.partner.id,
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn(order.name, response.json()['orders'])

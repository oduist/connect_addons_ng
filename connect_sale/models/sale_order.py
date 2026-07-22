import logging

from odoo import api, fields, models

logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    connect_calls = fields.One2many('connect.call', 'sale_order')
    connect_calls_count = fields.Integer(
        compute='_get_connect_calls_count', string='Calls', store=True,
    )
    partner_phone = fields.Char(related='partner_id.phone')
    partner_mobile = fields.Char(related='partner_id.mobile')

    @api.depends('connect_calls')
    def _get_connect_calls_count(self):
        for rec in self:
            rec.connect_calls_count = self.env['connect.call'].search_count(
                [('sale_order', '=', rec.id)],
            )

    @api.model
    def get_order_by_partner(self, partner):
        if not partner:
            return self.env['sale.order']
        return self.env['sale.order'].sudo().search(
            [('partner_id', '=', partner.id), ('state', 'in', ('draft', 'sent', 'sale'))],
            order='id desc', limit=1,
        )

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if self.env.context.get('connect_call_id') and recs:
            call = self.env['connect.call'].sudo().browse(self.env.context['connect_call_id'])
            call.sale_order = recs[0]
        if recs:
            self.env.registry.clear_cache()
        return recs

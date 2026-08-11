import logging

from odoo import api, fields, models

logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    connect_calls = fields.One2many('connect.call', 'invoice')
    connect_calls_count = fields.Integer(
        compute='_get_connect_calls_count', string='Calls', store=True,
    )
    partner_phone = fields.Char(related='partner_id.phone')
    partner_mobile = fields.Char(related='partner_id.mobile')

    @api.depends('connect_calls')
    def _get_connect_calls_count(self):
        for rec in self:
            rec.connect_calls_count = self.env['connect.call'].search_count(
                [('invoice', '=', rec.id)],
            )

    @api.model
    def get_invoice_by_partner(self, partner):
        if not partner:
            return self.env['account.move']
        return self.env['account.move'].sudo().search(
            [
                ('partner_id', '=', partner.id),
                ('state', '=', 'posted'),
                ('move_type', '=', 'out_invoice'),
                ('payment_state', '!=', 'paid'),
            ],
            order='invoice_date desc, id desc', limit=1,
        )

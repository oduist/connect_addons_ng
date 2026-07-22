import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)


class SaleCall(models.Model):
    _inherit = 'connect.call'

    sale_order = fields.Many2one('sale.order', ondelete='set null', tracking=True)
    ref = fields.Reference(selection_add=[('sale.order', 'Sale Order')])

    def _get_ref(self):
        for rec in self:
            if rec.sale_order:
                rec.ref = 'sale.order,{}'.format(rec.sale_order.id)
            else:
                super(SaleCall, rec)._get_ref()

    @api.model
    def process_call_event(self, channel, error_data=None):
        call_id = super().process_call_event(channel, error_data=error_data)
        if not call_id:
            return call_id
        if not self.env['oduist.license'].check_license('connect_sale', silent=True):
            return call_id
        call = self.browse(call_id)
        try:
            if not call.sale_order and call.partner:
                order = self.env['sale.order'].get_order_by_partner(call.partner)
                if order:
                    debug(self, 'Call {} assign order <{}> "{}"'.format(
                        call.id, order.id, order.name))
                    call.sale_order = order
        except Exception:
            logger.exception('Sale process_call_event error:')
        return call_id

    def create_sale_order_button(self):
        self.ensure_one()
        if not self.env['oduist.license'].check_license('connect_sale', silent=True):
            raise ValidationError('Connect Sale license is not activated!')
        context = {'connect_call_id': self.id, 'default_partner_id': self.partner.id}
        if not self.sale_order and self.partner:
            order = self.env['sale.order'].get_order_by_partner(self.partner)
            if order:
                self.sudo().sale_order = order
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order.id if self.sale_order else False,
            'name': self.sale_order.name if self.sale_order else 'New Sale Order',
            'view_mode': 'form',
            'target': 'current',
            'context': context,
        }

    def unlink_sale_order(self):
        self.ensure_one()
        self.sale_order = False

    def get_widget_fields(self):
        fields = super().get_widget_fields()
        fields.append('sale_order')
        return fields

    @api.constrains('summary')
    def register_sale_order_call_summary(self):
        if not self.env['oduist.license'].check_license('connect_sale', silent=True):
            return False
        if not self.env['connect.settings'].sudo().get_param('register_summary'):
            return
        reload_view = False
        for rec in self:
            if rec.sale_order and rec.summary:
                self.register_summary_to_rec(rec.sale_order, rec.summary)
                reload_view = True
        if reload_view:
            self.env['connect.settings'].connect_reload_view('sale.order')

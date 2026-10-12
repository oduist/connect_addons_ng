import logging

from odoo import api, fields, models

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)


class AccountCall(models.Model):
    _inherit = 'connect.call'

    invoice = fields.Many2one('account.move', ondelete='set null', tracking=True)
    ref = fields.Reference(selection_add=[('account.move', 'Invoice')])

    def _get_ref(self):
        for rec in self:
            if rec.invoice:
                rec.ref = 'account.move,{}'.format(rec.invoice.id)
            else:
                super(AccountCall, rec)._get_ref()

    @api.model
    def process_call_event(self, channel, error_data=None):
        call_id = super().process_call_event(channel, error_data=error_data)
        if not call_id:
            return call_id
        if not self.env['oduist.license'].check_license('connect_account', silent=True):
            return call_id
        call = self.browse(call_id)
        try:
            if not call.invoice and call.partner:
                invoice = self.env['account.move'].get_invoice_by_partner(call.partner)
                if invoice:
                    debug(self, 'Call {} assign invoice <{}> "{}"'.format(
                        call.id, invoice.id, invoice.name))
                    call.invoice = invoice
        except Exception:
            logger.exception('Account process_call_event error:')
        return call_id

    def unlink_invoice(self):
        self.ensure_one()
        self.invoice = False

    def get_widget_fields(self):
        fields = super().get_widget_fields()
        fields.append('invoice')
        return fields

    def _get_registration_targets(self):
        targets = super()._get_registration_targets()
        if not self.env['oduist.license'].check_license('connect_account', silent=True):
            return targets
        record = self.invoice
        if record:
            targets.append(record)
        return targets

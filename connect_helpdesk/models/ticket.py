import logging

from odoo import api, fields, models

from odoo.addons.connect.models.settings import debug, MAX_EXTEN_LEN
from odoo.addons.connect.models.res_partner import strip_number

logger = logging.getLogger(__name__)


class Ticket(models.Model):
    _inherit = 'helpdesk.ticket'

    connect_calls = fields.One2many('connect.call', 'ticket')
    connect_calls_count = fields.Integer(
        compute='_get_connect_calls_count', string='Calls', store=True,
    )
    phone_normalized = fields.Char(
        compute='_get_phone_normalized', index=True, store=True,
    )

    @api.depends('connect_calls')
    def _get_connect_calls_count(self):
        for rec in self:
            rec.connect_calls_count = self.env['connect.call'].search_count(
                [('ticket', '=', rec.id)],
            )

    @api.depends('partner_phone')
    def _get_phone_normalized(self):
        for rec in self:
            if rec.partner_phone:
                rec.phone_normalized = '+{}'.format(strip_number(rec.partner_phone))
            else:
                rec.phone_normalized = ''

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if self.env.context.get('connect_call_id') and recs:
            call = self.env['connect.call'].sudo().browse(
                self.env.context['connect_call_id'],
            )
            call.ticket = recs[0]
        if recs:
            self.env.registry.clear_cache()
        return recs

    def _search_ticket_by_number(self, number):
        open_stages_ids = self.env['helpdesk.stage'].sudo().search(
            [('fold', '=', False)],
        ).ids
        domain = [
            ('active', '=', True),
            '|',
            ('stage_id', 'in', open_stages_ids),
            ('stage_id', '=', False),
            ('phone_normalized', '=', number),
        ]
        found = self.env['helpdesk.ticket'].sudo().search(domain, order='id desc')
        if len(found) > 1:
            logger.warning(
                '[CONNECT_HELPDESK] MULTIPLE OPEN TICKETS FOUND BY NUMBER %s, '
                'SELECTING THE 1ST', number,
            )
        debug(self, 'Number {} belongs to tickets: {}'.format(
            number, found.mapped('id'),
        ))
        return found[:1]

    def get_ticket_by_number(self, number, country=None):
        number = strip_number(number)
        if not number or len(number) < MAX_EXTEN_LEN:
            debug(self, 'Ticket by number {}: skip search'.format(number))
            return self.env['helpdesk.ticket']
        ticket = self._search_ticket_by_number('+{}'.format(number))
        if ticket:
            return ticket
        ticket = self._search_ticket_by_number(number)
        if ticket:
            return ticket
        return self.env['helpdesk.ticket']

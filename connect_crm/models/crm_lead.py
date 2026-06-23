import logging

from odoo import api, fields, models

from odoo.addons.connect.models.settings import debug, MAX_EXTEN_LEN
from odoo.addons.connect.models.res_partner import strip_number, format_number

logger = logging.getLogger(__name__)


class Lead(models.Model):
    _inherit = 'crm.lead'

    connect_calls = fields.One2many('connect.call', 'lead')
    connect_calls_count = fields.Integer(
        compute='_get_connect_calls_count', string='Calls', store=True,
    )
    mobile = fields.Char()
    phone_normalized = fields.Char(
        compute='_get_phone_normalized', index=True, store=True,
    )
    mobile_normalized = fields.Char(
        compute='_get_phone_normalized', index=True, store=True,
    )

    @api.model
    def create_record_from_message(self, message, default_values=None):
        from_number = message.from_number
        lead = self.get_lead_by_number(from_number)
        if lead:
            return lead
        data = {
            'name': from_number,
            'phone': from_number,
        }
        if isinstance(default_values, dict):
            data.update(default_values)
        return self.create(data)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env['oduist.license'].check_license('connect_crm', silent=True):
            return super().create(vals_list)
        call = None
        if self.env.context.get('connect_call_id'):
            call = self.env['connect.call'].sudo().browse(
                self.env.context['connect_call_id'],
            )
            for vals in vals_list:
                source = self.env['utm.source'].sudo().search(
                    [('phone', '=', call.called)], limit=1,
                )
                if source:
                    vals['source_id'] = source.id
        recs = super().create(vals_list)
        if call and recs:
            call.lead = recs[0]
        if recs:
            self.env.registry.clear_cache()
        return recs

    def write(self, values):
        res = super().write(values)
        if res:
            self.env.registry.clear_cache()
        return res

    def unlink(self):
        res = super().unlink()
        if res:
            self.env.registry.clear_cache()
        return res

    @api.depends('phone', 'mobile', 'country_id', 'partner_id', 'partner_id.phone', 'partner_id.mobile')
    def _get_phone_normalized(self):
        for rec in self:
            if rec.phone:
                rec.phone_normalized = self.env['res.partner']._normalize_phone(rec.phone)
            else:
                rec.phone_normalized = False
            if rec.mobile:
                rec.mobile_normalized = self.env['res.partner']._normalize_phone(rec.mobile)
            else:
                rec.mobile_normalized = False

    @api.depends('connect_calls')
    def _get_connect_calls_count(self):
        for rec in self:
            rec.connect_calls_count = self.env['connect.call'].search_count(
                [('lead', '=', rec.id)],
            )

    def _search_lead_by_number(self, number):
        try:
            open_stages_ids = self.env['crm.stage'].sudo().search(
                [('is_won', '=', False)],
            ).ids
        except Exception:
            open_stages_ids = self.env['crm.stage'].sudo().search([]).ids
        domain = [
            ('active', '=', True),
            '|',
            ('stage_id', 'in', open_stages_ids),
            ('stage_id', '=', False),
            '|',
            ('phone_normalized', '=', number),
            ('mobile_normalized', '=', number),
        ]
        found = self.env['crm.lead'].sudo().search(domain, order='id desc')
        if len(found) > 1:
            logger.warning('[CONNECT_CRM] MULTIPLE LEADS FOUND BY NUMBER %s', number)
        debug(self, 'Number {} belongs to leads: {}'.format(
            number, found.mapped('id'),
        ))
        return found[:1]

    def get_lead_by_number(self, number, country=None):
        number = strip_number(number)
        if (not number or 'unknown' in number or number == 's'
                or len(number) < MAX_EXTEN_LEN):
            debug(self, '{} skip search'.format(number))
            return self.env['crm.lead']
        number_plus = '+' + number
        lead = self._search_lead_by_number(number_plus)
        if lead:
            return lead
        lead = self._search_lead_by_number(number)
        if lead:
            return lead
        e164_number = format_number(
            self, number, country=country, format_type='e164',
        )
        if e164_number not in [number, number_plus]:
            lead = self._search_lead_by_number(e164_number)
        if lead:
            return lead
        return self.env['crm.lead']

import logging
import phonenumbers
import re
from phonenumbers import phonenumberutil
from odoo import models, fields, api, release
from .settings import debug

logger = logging.getLogger(__name__)


def strip_number(number):
    if not isinstance(number, str):
        return number
    pattern = r'[\s\(\)\-\+]'
    return re.sub(pattern, '', number).lstrip('0')


def format_number(self, number, country=None, format_type='e164'):
    res = False
    try:
        phone_nbr = phonenumbers.parse(number, country)
        if not phonenumbers.is_possible_number(phone_nbr):
            debug(self, '{} country {} parse impossible'.format(
                number, country
            ))
        elif format_type == 'e164':
            res = phonenumbers.format_number(
                phone_nbr, phonenumbers.PhoneNumberFormat.E164)
        else:
            logger.error('WRONG FORMATTING PASSED: %s', format_type)
    except phonenumberutil.NumberParseException:
        debug(self, '{} {} {} got NumberParseException'.format(
            number, country, format_type
        ))
    except Exception:
        logger.exception('FORMAT NUMBER ERROR: ')
    finally:
        debug(self, '{} county {} format {}: {}'.format(
            number, country, format_type, res))
        return res or number


class Partner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def create_record_from_message(self, message, default_values=None):
        number = message.from_number
        partner = self.get_partner_by_number(number)
        if partner:
            return partner
        vals = {
            'name': number,
            'phone': number,
        }
        if isinstance(default_values, dict):
            vals.update(default_values)
        return self.create(vals)

    connect_calls_count = fields.Integer(compute='_get_connect_calls_count')
    connect_messages_count = fields.Integer(compute='_get_connect_messages_count')
    connect_recorded_calls = fields.One2many('connect.recording', 'partner')
    connect_user = fields.Many2one('connect.user', compute='_get_connect_user')
    if release.version_info[0] >= 19:
        mobile = fields.Char()

    def _get_connect_user(self):
        for rec in self:
            user = self.env['res.users'].sudo().search([('partner_id', '=', rec.id)])
            rec.connect_user = user.connect_user

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        try:
            if self.env.context.get('connect_call_id'):
                call = self.env['connect.call'].sudo().browse(
                    self.env.context['connect_call_id'])
                call.partner = res[0]
        except Exception as e:
            logger.exception(e)
        if res and not self.env.context.get('no_clear_cache'):
            if release.version_info[0] >= 17:
                self.env.registry.clear_cache()
            else:
                self.clear_caches()
        return res

    def write(self, values):
        res = super().write(values)
        if res and not self.env.context.get('no_clear_cache'):
            if release.version_info[0] >= 17:
                self.env.registry.clear_cache()
            else:
                self.clear_caches()
        return res

    def unlink(self):
        res = super().unlink()
        if res and not self.env.context.get('no_clear_cache'):
            if release.version_info[0] >= 17:
                self.env.registry.clear_cache()
            else:
                self.clear_caches()
        return res

    def _normalize_phone(self, number):
        if self.env['connect.settings'].sudo().get_param('disable_phone_format'):
            return number
        country = self._get_country()
        try:
            phone_nbr = phonenumbers.parse(number, country)
            if phonenumbers.is_possible_number(phone_nbr) or \
                    phonenumbers.is_valid_number(phone_nbr):
                number = phonenumbers.format_number(
                    phone_nbr, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.phonenumberutil.NumberParseException:
            number = '+{}'.format(strip_number(number))
        except Exception as e:
            logger.warning('Normalize phone error: %s', e)
        return number

    @api.model
    def get_partner_by_number(self, number):
        found = self.sudo().search([('phone_mobile_search', '=', number)])
        if not found:
            country = self.env['res.company'].sudo().browse(1).country_id.code
            normalized = format_number(self, number, country)
            if normalized and normalized != number:
                found = self.sudo().search(
                    [('phone_mobile_search', '=', normalized)])
                debug(self, '{} normalized to {} for partner lookup'.format(
                    number, normalized
                ))
        debug(self, '{} belongs to partners: {}'.format(
            number, found.mapped('id')
        ))
        parents = found.mapped('parent_id')
        if len(found) == 1:
            return found
        elif len(parents) == 0 and len(found) > 1:
            logger.warning('MANY PARTNERS FOR NUMBER %s', number)
            return found[0]
        elif len(parents) > 1 and len(found) > 1:
            logger.warning(
                'MANY PARTNERS DIFFERENT COMPANIES FOR NUMBER %s', number)
            return self.env['res.partner']
        elif len(parents) == 1 and len(found) == 2 and len(
                found.filtered(
                    lambda r: r.parent_id.id in [k.id for k in parents])) == 1:
            debug(self, 'one partner from one parent found')
            return found.filtered(
                lambda r: r.parent_id in [k for k in parents])[0]
        elif len(parents) == 1 and len(found) > 1 and len(found.filtered(
                lambda r: r.parent_id in [k for k in parents])) > 1:
            debug(self, 'MANY PARTNERS SAME PARENT COMPANY {}'.format(number))
            return parents[0]
        else:
            return self.env['res.partner']

    def _get_country(self):
        partner = self
        if partner and partner.country_id:
            return partner.country_id.code
        elif partner and partner.parent_id and partner.parent_id.country_id:
            return partner.parent_id.country_id.code
        elif partner and partner.company_id and partner.company_id.country_id:
            return partner.company_id.country_id.code
        elif self.env.user and self.env.user.company_id.country_id:
            return self.env.user.company_id.country_id.code

    def _get_connect_calls_count(self):
        for rec in self:
            if rec.is_company:
                rec.connect_calls_count = self.env[
                    'connect.call'].sudo().search_count(
                    ['|', ('partner', '=', rec.id),
                          ('partner.parent_id', '=', rec.id)])
            else:
                rec.connect_calls_count = self.env[
                    'connect.call'].sudo().search_count(
                    [('partner', '=', rec.id)])

    def _get_connect_messages_count(self):
        for rec in self:
            if rec.is_company:
                rec.connect_messages_count = self.env['connect.message'].sudo().search_count(
                    ['|', ('partner', '=', rec.id), ('partner.parent_id', '=', rec.id)]
                )
            else:
                rec.connect_messages_count = self.env['connect.message'].sudo().search_count(
                    [('partner', '=', rec.id)]
                )

    def _phone_format(self, number=None, country=None, company=None, force_format='E164', **kwargs):
        version_info = release.version_info
        if version_info[0] < 16:
            return super(Partner, self)._phone_format(number, country=country, company=company)
        elif version_info[0] == 16:
            return super(Partner, self)._phone_format(number, country=country, company=company, force_format=force_format)
        else:
            fname = kwargs.get('fname', False)
            return super(Partner, self)._phone_format(fname=fname, number=number, country=country, force_format=force_format)

    @api.model
    def api_get_partner(self, number):
        partner = self.get_partner_by_number(number)
        if partner:
            return {'id': partner.id, 'name': partner.display_name}
        else:
            return {'id': False, 'name': 'Unknown'}

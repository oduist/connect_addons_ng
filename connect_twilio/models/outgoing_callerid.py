# -*- coding: utf-8 -*-
import logging
from urllib.parse import urljoin
from odoo import fields, models, api, release
from odoo.exceptions import ValidationError
from odoo.addons.connect.models.settings import debug
from .settings import format_connect_response

logger = logging.getLogger(__name__)


class OutgoingCallerID(models.Model):
    _inherit = 'connect.outgoing_callerid'

    sid = fields.Char(readonly=True)
    status = fields.Char(readonly=True)
    validation_code = fields.Char(readonly=True)

    @api.constrains('is_default')
    def _check_default(self):
        for rec in self:
            if rec.is_default:
                if rec.callerid_type == 'outgoing_callerid' and rec.status != 'validated':
                    raise ValidationError('Validate the number first!')

    def sync_outgoing_callerid(self, callerid_type):
        client = self.env['connect.settings'].sudo().get_client()
        if callerid_type == 'outgoing_callerid':
            numbers = client.outgoing_caller_ids.list()
        elif callerid_type == 'number':
            numbers = client.incoming_phone_numbers.list()
        else:
            numbers = []
        for number in numbers:
            existing_number = self.env['connect.outgoing_callerid'].search([
                ('sid', '=', number.sid)])
            if not existing_number:
                existing_number = self.env['connect.outgoing_callerid'].search([
                    ('number', '=', number.phone_number)])
            data = {
                'sid': number.sid,
                'callerid_type': callerid_type,
                'number': number.phone_number,
                'friendly_name': number.friendly_name,
            }
            callerid_count = self.search_count([])
            if callerid_count == 0:
                data['is_default'] = True
            if callerid_type == 'outgoing_callerid':
                data['status'] = 'validated'
            if not existing_number:
                self.with_context(skip_validation=True).create(data)
                debug(self, 'CallerID {} ({}) created in Odoo from {}'.format(
                    number.phone_number, number.friendly_name, callerid_type))
            else:
                existing_number.with_context(skip_number_check=True).write(data)
                if number.friendly_name != existing_number.friendly_name:
                    debug(self, 'Update CallerID {} friendly name.'.format(existing_number.number))
                    if callerid_type == 'outgoing_callerid':
                        client.outgoing_caller_ids(existing_number.sid).update(
                            friendly_name=existing_number.friendly_name)
                    else:
                        client.incoming_phone_numbers(existing_number.sid).update(
                            friendly_name=existing_number.friendly_name)
        recs_to_remove = self.env['connect.outgoing_callerid'].search(
            [('sid', 'not in', [k.sid for k in numbers]), ('callerid_type', '=', callerid_type)])
        debug(self, 'Removing {} CallerIds: {}'.format(callerid_type, [k.number for k in recs_to_remove]))
        recs_to_remove.unlink()

    @api.model
    def sync(self):
        self.sync_outgoing_callerid('outgoing_callerid')
        self.sync_outgoing_callerid('number')

    @api.model
    def update_status(self, params):
        self = self.sudo()
        number = self.search([('number', '=', params['Called']),
                              ('callerid_type', '=', 'outgoing_callerid')])
        if not number:
            logger.error('Unknown validation request for number %s', params['Called'])
            return False
        if params['VerificationStatus'] == 'success':
            number.write({'status': 'validated', 'sid': params['OutgoingCallerIdSid']})
        else:
            number.status = 'validation failed'
        self.env['connect.settings'].connect_reload_view('connect.outgoing_callerid')
        return True

    def validate(self):
        self.ensure_one()
        if self.env['connect.settings'].sudo()._get().twilio_region != 'us1':
            raise ValidationError('Outgoing CallerIds are supported in US1 region only!')
        if self.sid:
            raise ValidationError('Outgoing callerid is already validated!')
        api_url = self.env['connect.settings'].sudo().get_param('api_url')
        edge = self.env['connect.settings'].sudo()._get().twilio_edge
        status_url = urljoin(api_url, 'twilio/webhook/outgoing_callerid#e={}'.format(edge))
        client = self.env['connect.settings'].sudo().get_client()
        try:
            validation_request = client.validation_requests.create(
                status_callback=status_url,
                friendly_name=self.friendly_name, phone_number=self.number)
            self.validation_code = validation_request.validation_code
        except Exception as e:
            if 'Phone number is already verified.' in str(e):
                self.unlink()
                self.sync()
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'connect.outgoing_callerid',
                    'view_mode': 'list',
                    'name': 'Outgoing CallerIds',
                }
            else:
                logger.error('Validate request error: %s', e)
                raise ValidationError('Validate request error: {}'.format(format_connect_response(e)))

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('skip_validation'):
            return super().create(vals_list)
        for vals in vals_list:
            if vals.get('callerid_type') == 'outgoing_callerid':
                vals['status'] = 'not validated'
        return super().create(vals_list)

    @api.constrains('friendly_name')
    def _change_number_friendly_name(self):
        for rec in self:
            if rec.sid and rec.callerid_type == 'outgoing_callerid':
                if self.env['connect.settings'].sudo()._get().twilio_auto_sync:
                    client = self.env['connect.settings'].sudo().get_client()
                    client.outgoing_caller_ids(rec.sid).update(friendly_name=self.friendly_name)
            elif rec.sid and rec.callerid_type == 'number':
                number = self.env['connect.number'].search([('phone_number', '=', rec.number)])
                number.friendly_name = rec.friendly_name

    def unlink(self):
        if not self.env['connect.settings'].sudo()._get().twilio_auto_sync:
            return super().unlink()
        sids = {}
        for rec in self:
            if rec.callerid_type == 'number':
                raise ValidationError('Remove Twilio numbers from Twilio Console and use Twilio Sync button!')
            if rec.sid and rec.callerid_type == 'outgoing_callerid':
                sids[rec.sid] = rec.number
        res = super().unlink()
        client = self.env['connect.settings'].sudo().get_client()
        for sid in sids.keys():
            try:
                client.outgoing_caller_ids(sid).delete()
            except Exception as e:
                logger.error('Could not delete outgoing callerid number %s', sids[sid])
        return res

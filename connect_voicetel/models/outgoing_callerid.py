# -*- coding: utf-8 -*-
import logging
import re
from voiceml.exceptions import ApiError

from odoo import fields, models, api, release
if release.version_info[0] >= 19:
    from odoo.models import Constraint
from odoo.exceptions import ValidationError
from odoo.addons.connect.models.settings import debug
from .settings import format_connect_response

logger = logging.getLogger(__name__)


class OutgoingCallerID(models.Model):
    _name = 'connect.voicetel.outgoing_callerid'
    _description = 'VoiceTel Outgoing CallerId'
    _order = 'number'
    _rec_names_search = ['number', 'friendly_name']

    name = fields.Char(compute='_get_name')
    friendly_name = fields.Char(required=True)
    number = fields.Char(required=True)
    callerid_type = fields.Selection(
        [('outgoing_callerid', 'CallerID'), ('number', 'DID Number')],
        required=True, default='outgoing_callerid')
    is_default = fields.Boolean(string='Default')
    callerid_users = fields.One2many(
        comodel_name='connect.user',
        inverse_name='voicetel_outgoing_callerid', string='callerId Users')
    sid = fields.Char(readonly=True)
    status = fields.Char(readonly=True)
    validation_code = fields.Char(readonly=True)

    if release.version_info[0] >= 19:
        _number_uniq = Constraint('UNIQUE(number)', 'This number is already used!')
    else:
        _sql_constraints = [('number_uniq', 'UNIQUE(number)', 'This number is already used!')]

    def _get_name(self):
        for rec in self:
            rec.name = '{} "{}"'.format(rec.number, rec.friendly_name)

    @api.constrains('number')
    def _check_number(self):
        # Iterate: a constraint receives a (possibly multi-record)
        # recordset, so self.number would raise "Expected singleton" on a
        # batch create. The single regex also covers the +-prefix check.
        for rec in self:
            if rec.number and not re.match(r'^\+[0-9]+$', rec.number):
                raise ValidationError(
                    'Number must be in E.164 form: a + followed by digits only.')

    @api.constrains('is_default')
    def _reset_default(self):
        if self.env.context.get('skip_reset_default'):
            return
        # Only clear the other records when this one is BECOMING the
        # default.
        for rec in self:
            if rec.is_default:
                self.with_context(skip_reset_default=True).search(
                    [('id', '!=', rec.id)]).write({'is_default': False})

    @api.constrains('is_default')
    def _check_default(self):
        for rec in self:
            if rec.is_default:
                if rec.callerid_type == 'outgoing_callerid' and rec.status != 'validated':
                    raise ValidationError('Validate the number first!')

    def sync_outgoing_callerid(self, callerid_type):
        client = self.env['connect.settings'].get_voicetel_client()
        if callerid_type == 'outgoing_callerid':
            numbers = client.outgoing_caller_ids.iter()
        elif callerid_type == 'number':
            numbers = client.incoming_phone_numbers.iter()
        else:
            numbers = []
        for number in numbers:
            existing_number = self.env[self._name].search([
                ('sid', '=', number.sid)])
            if not existing_number:
                existing_number = self.env[self._name].search([
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
                        client.outgoing_caller_ids.update(
                            existing_number.sid,
                            friendly_name=existing_number.friendly_name)
                    # An owned number's friendly_name is derived server-side
                    # from the number itself and cannot be set (SDK 0.9.3+).

        recs_to_remove = self.env[self._name].search(
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
        called = params.get('Called') or params.get('To')
        number = self.search([('number', '=', called),
                              ('callerid_type', '=', 'outgoing_callerid')])
        if not number:
            logger.error('Unknown validation request for number %s', called)
            return False
        if params.get('VerificationStatus') == 'success':
            number.write({'status': 'validated', 'sid': params.get('OutgoingCallerIdSid')})
        else:
            number.status = 'validation failed'
        self.env['connect.settings'].connect_reload_view(self._name)
        return True

    def validate(self):
        self.ensure_one()
        if self.sid:
            raise ValidationError('Outgoing callerid is already validated!')
        status_url = self.env['connect.settings'].sudo().voicetel_webhook_url(
            'voicetel/webhook/outgoing_callerid')
        client = self.env['connect.settings'].get_voicetel_client()
        try:
            validation_request = client.outgoing_caller_ids.create(
                phone_number=self.number,
                friendly_name=self.friendly_name,
                status_callback=status_url,
            )
            self.validation_code = validation_request.validation_code
        except Exception as e:
            if isinstance(e, ApiError) and 'already verified' in str(e):
                self.unlink()
                self.sync()
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': self._name,
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
                if self.env["connect.settings"].get_param("voicetel_auto_sync"):
                    client = self.env['connect.settings'].get_voicetel_client()
                    client.outgoing_caller_ids.update(rec.sid, friendly_name=self.friendly_name)
            elif rec.sid and rec.callerid_type == 'number':
                number = self.env['connect.voicetel.number'].search([('phone_number', '=', rec.number)])
                number.friendly_name = rec.friendly_name

    def unlink(self):
        if not self.env["connect.settings"].get_param("voicetel_auto_sync"):
            return super().unlink()
        sids = {}
        for rec in self:
            if rec.callerid_type == 'number':
                raise ValidationError('Owned numbers are managed on the VoiceML account; use the VoiceTel Sync button!')
            if rec.sid and rec.callerid_type == 'outgoing_callerid':
                sids[rec.sid] = rec.number
        res = super().unlink()
        client = self.env['connect.settings'].get_voicetel_client()
        for sid in sids.keys():
            try:
                client.outgoing_caller_ids.delete(sid)
            except Exception:
                logger.error('Could not delete outgoing callerid number %s', sids[sid])
        return res

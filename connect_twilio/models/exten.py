# -*- coding: utf-8 -*-
import logging
from odoo import fields, models, api, release
if release.version_info[0] >= 19:
    from odoo.models import Constraint
from twilio.twiml.voice_response import VoiceResponse

logger = logging.getLogger(__name__)


class Exten(models.Model):
    _name = 'connect.twilio.exten'
    _description = 'Twilio Extension'
    _order = 'number'

    name = fields.Char(compute='_get_name', copy=False)
    number = fields.Char('Extension Number', required=True, copy=False)
    model = fields.Char('AppModel')
    model_friendly = fields.Char('Model', compute='_get_model_friendly', store=True, copy=False)
    res_id = fields.Integer()
    dst = fields.Reference(
        string='Destination',
        ondelete='cascade',
        required=False,
        selection=[
            ('connect.user', 'User'),
            ('connect.twilio.callflow', 'Call Flow'),
            ('connect.twilio.twiml', 'TwiML'),
        ],
        compute='_get_dst', inverse='_set_dst')
    dst_name = fields.Char(compute='_get_dst')
    dialplan = fields.Text('Dialplan', compute='_get_dialplan', readonly=True)

    if release.version_info[0] >= 19:
        _number_uniq = Constraint('UNIQUE(number)', 'This extension number is already defined!')
    else:
        _sql_constraints = [
            ('number_uniq', 'UNIQUE(number)', 'This extension number is already defined!')
        ]

    @api.model
    def _dst_exten_field(self, dst):
        """Name of the back-link field on the destination record."""
        if dst._name == 'connect.user':
            return 'twilio_exten'
        return 'exten' if 'exten' in dst._fields else None

    def _link_dst(self, dst, exten):
        if not dst:
            return
        field_name = self._dst_exten_field(dst)
        if field_name:
            dst[field_name] = exten

    def _get_name(self):
        for rec in self:
            try:
                rec.name = "{} <{}>".format(rec.number, rec.dst.name if rec.dst else '')
            except Exception:
                logger.exception('Exten name error:')
                rec.name = 'See Odoo Error Log'

    @api.depends('model')
    def _get_model_friendly(self):
        for rec in self:
            try:
                rec.model_friendly = dict(
                    self.env[self._name]._fields['dst'].selection).get(rec.model)
            except Exception:
                logger.exception('Exten Model friendly error:')
                rec.model_friendly = ''

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            exten = self.search([('number', '=', vals['number'])])
            if exten and not exten.dst:
                exten.write(vals)
                return exten
        res = super().create(vals_list)
        for record in res:
            if record.dst:
                self._link_dst(record.dst, record)
        return res

    def write(self, vals):
        if (self.model is not False) and ('model' in vals) and ('res_id' in vals):
            if self.dst:
                self._link_dst(self.dst, False)
            self.env[self._name].search([
                ('res_id', '=', vals['res_id']), ('model', '=', vals['model'])]).update({'res_id': False})
        res = super().write(vals)
        if self.dst:
            self._link_dst(self.dst, self)
        return res

    def unlink(self):
        for rec in self:
            if rec.dst:
                self._link_dst(rec.dst, False)
        return super().unlink()

    def copy_data(self, default=None):
        default = dict(default or {})
        data_list = super().copy_data(default)
        extensions = self.search([('model', '=', data_list[0]['model'])])
        last_number = extensions[-1].number
        new_number = int(last_number) + 1
        data_list[0]['number'] = str(new_number)
        return data_list

    def _get_dst(self):
        for rec in self:
            if rec.model and rec.model in self.env:
                try:
                    rec.dst = '%s,%s' % (rec.model, rec.res_id or 0)
                    rec.dst_name = self.env[rec.model]._description
                except ValueError as e:
                    logger.error('Exten dst error: %s', e)
                    rec.dst = None
                    rec.dst_name = None
            else:
                rec.dst = None
                rec.dst_name = None

    def _set_dst(self):
        for rec in self:
            # Capture the destination before writing model/res_id: reading
            # rec.dst again after the write can transiently recompute to None
            # (non-stored Reference field), which broke the back-link and
            # crashed _link_dst with an AttributeError on None.
            dst = rec.dst
            if dst:
                rec.write({'model': dst._name, 'res_id': dst.id})
                self._link_dst(dst, rec)
            else:
                rec.write({'model': False, 'res_id': False})

    @api.model
    def create_extension(self, rec, dst_model, current_exten=None):
        exten = current_exten
        if exten is None:
            exten = rec.exten if 'exten' in rec._fields else False
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': exten.id if exten else False,
            'target': 'new' if not exten else 'current',
            'context': {
                'default_dst': '{},{}'.format(dst_model, rec.id)
            }
        }

    def _get_dialplan(self):
        for rec in self:
            try:
                result = rec.dst.render({})
                rec.dialplan = str(result) if result else ''
            except Exception as e:
                logger.warning('Cannot render exten: %s', e)
                rec.dialplan = 'Render error (normal case with dynamic values)'

    def render(self, request=None, params=None):
        self.ensure_one()
        if not self.dst:
            response = VoiceResponse()
            response.say('Extension not configured!')
            return response.to_xml()
        # Copy before adding keys: the {} default was a shared object and
        # writing ExtenID/ExtenNumber into it (or into a caller's dict)
        # leaked across calls.
        params = dict(params or {})
        params['ExtenID'] = self.id
        params['ExtenNumber'] = self.number
        # Normalize request too: callers such as connect.settings.originate
        # invoke exten.render() with no request, and the downstream
        # connect.user / connect.callflow render() still default to {} and
        # call request.get(...). Forwarding a bare None would crash them.
        return self.dst.render(request=dict(request or {}), params=params)

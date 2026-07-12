# -*- coding: utf-8 -*-
import json

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class BirdWhatsappComposer(models.TransientModel):
    """Send a WhatsApp message through a Bird number. Free-form text only
    works inside the 24-hour customer-service window; a template starts a
    conversation at any time.
    """
    _name = 'connect.bird.whatsapp_composer'
    _description = 'Send WhatsApp Message via Bird'

    res_model = fields.Char('Related Model')
    res_id = fields.Integer('Related Record')
    number_id = fields.Many2one(
        'connect.bird.number', string='Sender',
        help='Optional: the platform assigns the workspace WhatsApp '
             'sender when empty.')
    phone = fields.Char(string='To', required=True)
    # WhatsApp on the Bird platform is template-only (free-form text is
    # rejected by the API), so a template is mandatory.
    template_id = fields.Many2one(
        'connect.bird.message_template', string='Template', required=True,
        domain="[('product', '=', 'whatsapp'),"
               " ('status', 'in', ('active', 'approved'))]")
    template_variables = fields.Text(string='Template Variables (JSON)')
    body = fields.Text(string='Preview', readonly=True)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        ctx = dict(self.env.context or {})
        res_model = ctx.get('active_model') or ctx.get('default_res_model')
        res_id = ctx.get('active_id') or ctx.get('default_res_id')
        vals.update({'res_model': res_model, 'res_id': res_id})
        number = self.env.user.connect_user.bird_message_number
        if not number or not number.has_capability('whatsapp'):
            candidates = self.env['connect.bird.number'].search(
                [], order='is_default desc, id')
            number = next(
                (n for n in candidates if n.has_capability('whatsapp')),
                self.env['connect.bird.number'])
        if number:
            vals['number_id'] = number.id
        phone = ctx.get('default_phone')
        try:
            if not phone and res_model and res_id and res_model in self.env:
                rec = self.env[res_model].browse(res_id)
                phone = rec.phone_sanitized
            if phone:
                phone = self.env['res.partner']._phone_format(number=phone)
        except Exception:
            pass
        if phone:
            vals['phone'] = phone
        return vals

    @api.onchange('template_id')
    def _onchange_template(self):
        if self.template_id:
            keys = self.template_id.get_variable_keys()
            self.template_variables = json.dumps({key: '' for key in keys})
            self.body = self.template_id.body_preview
        else:
            self.template_variables = False
            self.body = False

    def action_send_whatsapp(self):
        self.ensure_one()
        if not self.phone:
            raise ValidationError('Recipient number is required')
        params = {}
        if (self.template_variables or '').strip():
            try:
                params = json.loads(self.template_variables)
            except ValueError as e:
                raise ValidationError(
                    'Template variables must be a JSON object, e.g. '
                    '{"1": "value"}') from e
            if not isinstance(params, dict):
                raise ValidationError(
                    'Template variables must be a JSON object!')
        # Direct Bird transport: the composer itself is the explicit
        # provider choice, no message_provider dispatch.
        self.env['connect.message'].send_bird_template(
            self.phone, self.template_id, params=params,
            res_id=self.res_id or None, res_model=self.res_model or None,
            outgoing_callerid=self.number_id or None)
        return {'type': 'ir.actions.act_window_close'}

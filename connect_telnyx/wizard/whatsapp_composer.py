# -*- coding: utf-8 -*-
import json
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TelnyxWhatsappComposer(models.TransientModel):
    _name = 'connect.telnyx.whatsapp_composer'
    _description = 'Send WhatsApp Message (Telnyx)'

    res_model = fields.Char('Related Model')
    res_id = fields.Integer('Related Record')
    whatsapp_sender_id = fields.Many2one(
        'connect.telnyx.whatsapp_sender',
        string='Sender',
        required=True,
        domain="[('no_sync', '=', False)]"
    )
    phone = fields.Char(string='To', required=True)
    template_id = fields.Many2one('connect.telnyx.whatsapp_template', string='Template',
                                  domain="[('status', '=', 'APPROVED')]")
    template_variables = fields.Text(string='Template Variables (JSON)')
    body = fields.Text(string='Message')

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        ctx = dict(self.env.context or {})
        res_model = ctx.get('active_model') or ctx.get('default_res_model')
        res_id = ctx.get('active_id') or ctx.get('default_res_id')
        vals.update({'res_model': res_model, 'res_id': res_id})
        sender = self.env['connect.telnyx.whatsapp_sender'].get_default_sender(self.env.user)
        if sender:
            vals['whatsapp_sender_id'] = sender.id
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

    def _extract_template_variables(self, template_body):
        indices = re.findall(r"{{\s*(\d+)\s*}}", template_body or "")
        seen = set()
        ordered_unique = []
        for idx in indices:
            if idx not in seen:
                seen.add(idx)
                ordered_unique.append(idx)
        return {i: "" for i in ordered_unique}

    def _render_preview(self, template_body, variables_json):
        if not template_body:
            return False
        try:
            mapping = json.loads(variables_json) if variables_json else {}
        except Exception:
            mapping = {}

        def repl(match):
            key = match.group(1).strip()
            return str(mapping.get(key, match.group(0)))
        return re.sub(r"{{\s*(\d+)\s*}}", repl, template_body)

    @api.onchange('template_id')
    def _onchange_template(self):
        if self.template_id:
            tmpl_vars_json = (self.template_id.variables or '').strip()
            parsed = None
            if tmpl_vars_json:
                try:
                    parsed = json.loads(tmpl_vars_json)
                    if not isinstance(parsed, dict):
                        parsed = None
                except Exception:
                    parsed = None
            if parsed is None:
                parsed = self._extract_template_variables(self.template_id.body)
            try:
                self.template_variables = json.dumps(parsed) if parsed is not None else False
            except Exception:
                self.template_variables = str(parsed)
            self.body = self._render_preview(self.template_id.body, self.template_variables)
        else:
            self.template_variables = False
            self.body = False

    @api.onchange('template_variables')
    def _onchange_template_variables(self):
        if self.template_id:
            self.body = self._render_preview(self.template_id.body, self.template_variables)

    def action_send_whatsapp(self):
        self.ensure_one()
        if not self.phone:
            raise ValidationError('Recipient number is required')
        if not self.template_id and not (self.body and self.body.strip()):
            raise ValidationError('Message body is required')
        kwargs = {}
        body_to_send = self.body
        if self.template_id:
            kwargs['template'] = self.template_id
            json_text = (self.template_variables or '').strip() \
                or (self.template_id.variables or '').strip()
            kwargs['template_variables'] = self.template_id._ordered_variable_values(json_text)
            body_to_send = self._render_preview(self.template_id.body, json_text)
        self.whatsapp_sender_id.send_whatsapp(
            recipient=self.phone,
            body=body_to_send,
            res_model=self.res_model,
            res_id=self.res_id,
            **kwargs,
        )
        return {'type': 'ir.actions.act_window_close'}

# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TelnyxRcsComposer(models.TransientModel):
    _name = 'connect.telnyx.rcs_composer'
    _description = 'Send RCS Message (Telnyx)'

    res_model = fields.Char('Related Model')
    res_id = fields.Integer('Related Record')
    rcs_agent_id = fields.Many2one(
        'connect.telnyx.rcs_agent',
        string='Agent',
        required=True,
        domain="[('enabled', '=', True)]"
    )
    phone = fields.Char(string='To', required=True)
    body = fields.Text(string='Message', required=True)
    sms_fallback = fields.Boolean(
        string='SMS Fallback', default=True,
        help='Deliver the message as SMS when the recipient is not RCS-capable.')
    sms_fallback_from = fields.Char(
        string='Fallback From',
        help='E.164 sender used for the SMS fallback.')

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        ctx = dict(self.env.context or {})
        res_model = ctx.get('active_model') or ctx.get('default_res_model')
        res_id = ctx.get('active_id') or ctx.get('default_res_id')
        vals.update({'res_model': res_model, 'res_id': res_id})
        agent = self.env['connect.telnyx.rcs_agent'].get_default_agent()
        if agent:
            vals['rcs_agent_id'] = agent.id
        default_callerid = self.env['connect.telnyx.outgoing_callerid'].search(
            [('is_default', '=', True)], limit=1)
        if default_callerid:
            vals['sms_fallback_from'] = default_callerid.number
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

    def action_send_rcs(self):
        self.ensure_one()
        if not self.phone:
            raise ValidationError('Recipient number is required')
        if self.sms_fallback and not self.sms_fallback_from:
            raise ValidationError(
                'Set the fallback sender number or disable the SMS fallback.')
        self.rcs_agent_id.send_rcs(
            recipient=self.phone,
            body=self.body,
            res_model=self.res_model,
            res_id=self.res_id,
            sms_fallback_from=self.sms_fallback_from if self.sms_fallback else None,
        )
        return {'type': 'ir.actions.act_window_close'}

# -*- coding: utf-8 -*-
import logging

from odoo import models, api, SUPERUSER_ID
from odoo.exceptions import ValidationError

logger = logging.getLogger(__name__)


class ConnectMessage(models.Model):
    _inherit = 'connect.message'

    @api.depends('status', 'sender_user')
    def _compute_direction(self):
        for rec in self:
            if rec.sender_user:
                rec.direction = 'outgoing'
            elif rec.status == 'received':
                rec.direction = 'incoming'
            else:
                our_numbers = self.env['connect.voiceml.number'].search([]).mapped('phone_number')
                rec.direction = 'outgoing' if rec.from_number in set(our_numbers) else 'incoming'

    @api.model
    def receive(self, params):
        # SMS-only for the scaffold; WhatsApp is not yet modelled on VoiceML.
        try:
            if params.get('SmsStatus') == 'received':
                from_number = params.get('From')
                to_number = params.get('To')
                values = self.get_receive_message_values(params)
                partner = self.env['res.partner'].get_partner_by_number(from_number)
                if partner:
                    values.update({'partner': partner.id})
                self.env['connect.message'].sudo().create(values)
            else:
                message = self.env['connect.message'].sudo().search(
                    [('message_sid', '=', params.get('MessageSid'))])
                if message:
                    message.update({'status': params.get('SmsStatus')})
                    if params.get('SmsStatus') == 'failed':
                        message.update({
                            'error_code': params.get('ErrorCode'),
                            'error_message': params.get('ErrorMessage'),
                            'has_error': True,
                        })
        except Exception as e:
            logger.error('Error handling incoming SMS: %s', e)
        return 'OK'

    def send(self, recipient, body, res_id=None, res_model=None,
             outgoing_callerid=None, **kwargs):
        if self.env['connect.settings']._get_message_provider() != 'voiceml':
            return super().send(
                recipient, body, res_id=res_id, res_model=res_model,
                outgoing_callerid=outgoing_callerid, **kwargs)
        sender_user = self.env.user
        if outgoing_callerid:
            sender = outgoing_callerid
        else:
            number = sender_user.connect_user.voiceml_outgoing_callerid
            if not number:
                raise ValidationError('You dont have an outgoing callerid number!')
            sender = number.number
        client = self.env['connect.settings'].get_client()
        message = client.messages.create(to=recipient, from_=sender, body=body)
        if getattr(message, 'error_code', None):
            raise ValidationError('Unexpected error! Contact admin or maintainer!')
        partner = self.env['res.partner'].get_partner_by_number(recipient)
        self.env['connect.message'].sudo().create({
            'message_sid': message.sid,
            'from_number': sender,
            'to_number': recipient,
            'body': body,
            'sender_user': sender_user.id,
            'res_id': res_id,
            'res_model': res_model,
            'status': 'sent',
            'message_type': 'sms',
            'partner': partner.id if partner else False,
        })
        if res_model and res_id:
            obj = self.env[res_model].with_user(SUPERUSER_ID).browse(res_id)
            if hasattr(obj, 'message_post'):
                obj.with_context(mail_create_nosubscribe=True).message_post(
                    body=body, subtype_id=self.env.ref('mail.mt_note').id)

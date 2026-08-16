# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import ValidationError


class TelnyxAICallWizard(models.TransientModel):
    _name = 'connect.telnyx.ai_call_wizard'
    _description = 'Call with Telnyx AI Assistant'

    assistant = fields.Many2one(
        'connect.telnyx.ai_assistant', required=True, ondelete='cascade'
    )
    caller_id = fields.Many2one(
        'connect.telnyx.outgoing_callerid', required=True,
    )
    to_number = fields.Char(required=True)
    partner = fields.Many2one('res.partner', ondelete='set null')

    def _texml_connection_id(self):
        # Outbound AI calls run through the number application, the same
        # one click-to-call uses; a SIP domain is not required for them.
        connection_id = self.env['connect.telnyx.number'].get_number_app().sid
        if not connection_id:
            raise ValidationError(
                'Synchronize the Telnyx TeXML applications first.'
            )
        return connection_id

    def action_call(self):
        self.ensure_one()
        if not self.assistant.sid:
            raise ValidationError('Synchronize the AI assistant first.')
        if not self.caller_id.number:
            raise ValidationError('Select a valid Telnyx caller ID.')
        number = self.to_number.strip()
        if not number.startswith('+'):
            number = '+{}'.format(number)
        dynamic_variables = {}
        if self.partner:
            dynamic_variables = {
                'customer_name': self.partner.display_name,
                'odoo_partner_id': str(self.partner.id),
                'customer_email': self.partner.email or '',
                'customer_language': self.partner.lang or '',
            }
        response = self.env['connect.settings'].telnyx_api_request(
            'POST', 'texml/ai_calls/{}'.format(self._texml_connection_id()),
            payload={
                'From': self.caller_id.number,
                'To': number,
                'AIAssistantId': self.assistant.sid,
                'AIAssistantDynamicVariables': dynamic_variables,
            })
        data = response.get('data', response)
        call_sid = data.get('CallSid') or data.get('call_sid') or data.get('id')
        if call_sid:
            self.env['connect.channel'].sudo().create({
                'sid': call_sid,
                'technical_direction': 'outbound-api',
                'status': 'initiated',
                'caller': self.caller_id.number,
                'called': number,
                'partner': self.partner.id,
            })
        self.env['connect.settings'].connect_notify(
            'Telnyx AI call started.', title='AI Assistant'
        )
        return {'type': 'ir.actions.act_window_close'}

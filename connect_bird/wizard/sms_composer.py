# -*- coding: utf-8 -*-
import re
from odoo import api, models, fields, release


class SendSMS(models.TransientModel):
    _inherit = 'sms.composer'

    outgoing_callerid = fields.Selection(selection='_list_all_numbers')

    @api.model
    def _list_all_numbers(self):
        # Chain other messaging providers' sender numbers (e.g. Twilio)
        # when co-installed: both modules define this selection method and
        # the MRO-resolved one must expose the union.
        parent = super()
        numbers = (parent._list_all_numbers()
                   if hasattr(parent, '_list_all_numbers') else [])
        bird_numbers = self.env['connect.bird.number'].search([])
        existing = {n[0] for n in numbers}
        numbers += [
            (n.number, n.number) for n in bird_numbers
            if n.number and n.number not in existing
            and (n.has_capability('sms') or n.has_capability('whatsapp'))]
        return numbers

    def _action_send_sms(self):
        number = self.recipient_single_number or self.recipient_single_number_itf
        if release.version_info[0] < 17:
            number = re.sub(r"[^\d+]+", "", number)
        else:
            number = self._phone_format(number=number)
        # connect.message.send() dispatches by the user's message_provider,
        # so this override stays correct when several providers are installed.
        self.env['connect.message'].send(
            number, self.body, self.res_id, self.res_model, self.outgoing_callerid)

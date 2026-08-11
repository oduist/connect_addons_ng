# -*- coding: utf-8 -*-
import logging

from odoo import models, api

from odoo.addons.connect.models.settings import debug
from .settings import to_e164

logger = logging.getLogger(__name__)


class OutgoingCallerID(models.Model):
    _inherit = 'connect.outgoing_callerid'

    @api.model
    def sync(self):
        """Seed outgoing caller ids from the owned Vonage numbers.

        Vonage has no verified-caller-id API, so only own numbers can be
        used as outgoing caller ids (callerid_type='number').
        """
        numbers = self.env['connect.number'].search([('country', '!=', False)])
        known = []
        for number in numbers:
            phone_number = to_e164(number.phone_number)
            known.append(phone_number)
            existing = self.search([('number', '=', phone_number)], limit=1)
            data = {
                'callerid_type': 'number',
                'number': phone_number,
                'friendly_name': number.friendly_name or phone_number,
            }
            if not existing:
                if not self.search_count([]):
                    data['is_default'] = True
                self.create(data)
                debug(self, 'CallerID {} created in Odoo from number.'.format(
                    phone_number))
            else:
                existing.with_context(skip_number_check=True).write(data)
        recs_to_remove = self.search(
            [('number', 'not in', known), ('callerid_type', '=', 'number')])
        if recs_to_remove:
            debug(self, 'Removing CallerIds: {}'.format(
                [k.number for k in recs_to_remove]))
            recs_to_remove.unlink()

# -*- coding: utf-8 -*-

import logging
from urllib.parse import urlparse

from odoo import models, fields, release, api
from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)


class ElevenlabsNumber(models.Model):
    _inherit = 'connect.number'

    elevenlabs_agent = fields.Many2one('connect.elevenlabs_agent', ondelete='set null')

    def write(self, vals):
        # ODU-12: 'elevenlabs_agent' is no longer a destination Selection
        # value. The agent now routes via destination='provider' +
        # destination_provider_id == elevenlabs.
        if 'destination_provider_id' in vals or 'destination' in vals:
            if vals.get('destination') and vals['destination'] != 'provider':
                vals.setdefault('elevenlabs_agent', False)
            elif vals.get('destination_provider_id') is False:
                vals.setdefault('elevenlabs_agent', False)
        return super().write(vals)

    def _is_elevenlabs_destination(self):
        return (self.destination == 'provider'
                and self.destination_provider_id
                and self.destination_provider_id.code == 'elevenlabs')

    @api.model
    def route_call(self, request):
        if not self.env['oduist.license'].check_license('connect_elevenlabs', silent=True):
            return super().route_call(request)
        res = super().route_call(request)
        number = self.search([('phone_number', '=', request['Called'])])
        if number._is_elevenlabs_destination() and number.elevenlabs_agent:
            return number.elevenlabs_agent.render(request)
        return res

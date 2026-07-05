# -*- coding: utf-8 -*-
import logging
from odoo import fields, models
from twilio.twiml.voice_response import VoiceResponse

logger = logging.getLogger(__name__)


class Exten(models.Model):
    _inherit = 'connect.exten'

    dst = fields.Reference(
        selection_add=[('connect.twiml', 'TwiML')],
    )
    dialplan = fields.Text('Dialplan', compute='_get_dialplan', readonly=True)

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

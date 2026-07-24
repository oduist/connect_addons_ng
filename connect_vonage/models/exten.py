# -*- coding: utf-8 -*-
import json
import logging

from odoo import fields, models

logger = logging.getLogger(__name__)


class Exten(models.Model):
    _inherit = 'connect.exten'

    dst = fields.Reference(
        selection_add=[('connect.ncco', 'NCCO')],
    )
    dialplan = fields.Text('Dialplan', compute='_get_dialplan', readonly=True)

    def _get_dialplan(self):
        for rec in self:
            try:
                result = rec.dst.render({})
                rec.dialplan = json.dumps(result, indent=2) if result else ''
            except Exception as e:
                logger.warning('Cannot render exten: %s', e)
                rec.dialplan = 'Render error (normal case with dynamic values)'

    def render(self, request=None, params=None):
        self.ensure_one()
        if not self.dst:
            return [{'action': 'talk', 'text': 'Extension not configured!'}]
        params = dict(params or {})
        params['ExtenID'] = self.id
        params['ExtenNumber'] = self.number
        return self.dst.render(request=request, params=params)

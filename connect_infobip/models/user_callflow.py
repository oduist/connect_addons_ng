# -*- coding: utf-8 -*-
from odoo import fields, models


class UserCallflow(models.Model):
    """Ordered ring steps of a user (web client and/or external phone).

    Unlike the TwiML/TeXML providers there is no per-call progress model:
    ring progress lives on the parent connect.channel
    (infobip_route_step), and the per-step timer is Infobip's
    connectTimeout — no rendering method column is needed (ADR-036).
    """
    _name = 'connect.infobip.user_callflow'
    _description = 'Infobip User Callflow'
    _order = 'prio'

    user = fields.Many2one('connect.user', required=True, ondelete='cascade')
    prio = fields.Integer(required=True, default=1)
    callflow_type = fields.Char(string='Type', required=True)
    ring_timeout = fields.Integer(required=True, default=30)

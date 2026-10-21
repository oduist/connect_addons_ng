# -*- coding: utf-8 -*-
from odoo import fields, models


class UserCallflowCall(models.Model):
    _name = 'connect.voicetel.user_callflow_call'
    _log_access = False
    _description = 'VoiceTel User Callflow Call'

    call = fields.Many2one('connect.call', required=True, ondelete='cascade')
    callflow = fields.Many2one('connect.voicetel.user_callflow', required=True, ondelete='cascade')


class UserCallflow(models.Model):
    _name = 'connect.voicetel.user_callflow'
    _description = 'VoiceTel User Callflow'

    user = fields.Many2one('connect.user', required=True, ondelete='cascade')
    prio = fields.Integer(required=True, default=1)
    callflow_type = fields.Char(string='Type', required=True)
    method = fields.Char(required=True)

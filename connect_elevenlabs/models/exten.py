# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, release, api

logger = logging.getLogger(__name__)


class Exten(models.Model):
    _inherit = 'connect.twilio.exten'

    dst = fields.Reference(selection_add=[('connect.elevenlabs_agent', 'Agent')])
    agent = fields.Many2one('connect.elevenlabs_agent')
    # Not present on connect.twilio.exten (it lived on the old monolithic core
    # connect.exten). The agent transfer tool and the conversation-initiation
    # payload expose only published extensions to the AI, so the add-on owns it.
    is_published = fields.Boolean('Published')

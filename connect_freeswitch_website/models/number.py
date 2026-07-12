# -*- coding: utf-8 -*-
from odoo import fields, models


class Number(models.Model):
    _inherit = 'connect.freeswitch.number'

    # The website builder record picker (html_builder SelectMany2X) always
    # reads the `name` field of the model it browses, but the number model
    # uses phone_number as _rec_name and has no `name` column. Mirror it so
    # the snippet options "Phone Number" picker works.
    name = fields.Char(related='phone_number', string='Name')

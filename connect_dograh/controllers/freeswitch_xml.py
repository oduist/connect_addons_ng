# -*- coding: utf-8 -*-
"""Dialplan hook for Dograh outbound legs.

``connect.settings.dograh_originate`` hunts the answered outbound leg
into the ``dograh_outbound`` destination; this override serves its
dialplan (attach mod_audio_fork to the ``dograh_ws_url`` channel
variable and park). Everything else falls through to the standard
connect_freeswitch routing.
"""
from odoo.http import request

from odoo.addons.connect_freeswitch.controllers.freeswitch_xml import (
    FreeSwitchXMLController,
)


class DograhFreeSwitchXMLController(FreeSwitchXMLController):

    def _route_internal(self, destination, params):
        if destination == 'dograh_outbound':
            return request.env['connect.freeswitch.template'].sudo().render(
                'dialplan_dograh_outbound', {})
        return super()._route_internal(destination, params)

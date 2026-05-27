"""Thin remnant of FS settings.

ODU-23: FreeSWITCH fields (~25) and methods (freeswitch_api,
check_freeswitch_status, get_webrtc_config, validation/write override)
moved to `connect.provider.freeswitch.config`. This module-level file
is kept only to register `ODUIST_MODULES` and provide back-compat
method shims on `connect.settings` so JSON-RPC callers
(notably the phone_service.js → orm.call('connect.settings',
'get_webrtc_config')) keep working without a JS change.
"""
# -*- coding: utf-8 -*-
import logging

from odoo import api, models
from odoo.addons.connect.models.license import ODUIST_MODULES

ODUIST_MODULES.append('connect_freeswitch')

logger = logging.getLogger(__name__)


class Settings(models.Model):
    _inherit = 'connect.settings'

    # Back-compat method shims — delegate to the new config singleton.
    # Kept so external/JSON-RPC callers (e.g. phone_service.js calling
    # `connect.settings.get_webrtc_config`) don't need a sync update.

    @api.model
    def get_webrtc_config(self):
        return self.env['connect.provider.freeswitch.config'].get_webrtc_config()

    @api.model
    def freeswitch_api(self, command, args=''):
        return self.env['connect.provider.freeswitch.config'].freeswitch_api(command, args)

    def check_freeswitch_status(self):
        return self.env['connect.provider.freeswitch.config']._get().check_status()

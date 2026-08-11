# -*- coding: utf-8 -*-
import logging

from odoo import models, api

logger = logging.getLogger(__name__)


class Call(models.Model):
    _inherit = 'connect.call'

    @api.model
    def on_voice_event(self, params):
        """Vonage webhook adapter: map params, delegate to core."""
        self = self.sudo()
        channel = self.env['connect.channel'].on_voice_event(params)
        if not channel:
            # Not a per-leg status event (e.g. NCCO fetch errors) — ignore.
            return False

        error_data = None
        if params.get('status') in ('failed', 'rejected'):
            reason = params.get('reason') or params.get('detail')
            if reason:
                error_data = {
                    'error_code': params.get('status'),
                    'error_message': reason,
                }

        call_id = self.process_call_event(channel, error_data)

        # Notify the caller about outgoing call errors.
        if error_data and channel.call:
            user = channel.caller_user or channel.call.caller_user
            if channel.call.direction == 'outgoing' and user:
                self.env['connect.settings'].connect_notify(
                    notify_uid=user.id,
                    title='Call Error',
                    message=error_data['error_message'],
                    warning=True,
                )

        return call_id

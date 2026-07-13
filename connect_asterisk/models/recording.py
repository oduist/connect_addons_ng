# -*- coding: utf-8 -*-
import logging

from odoo import models

logger = logging.getLogger(__name__)


class Recording(models.Model):
    _inherit = 'connect.recording'

    def action_fetch_from_asterisk(self):
        """Ask the agent to re-upload the recording file for this channel.

        Pull fallback for uploads missed while Odoo was unreachable. The
        agent re-reads the file from the monitor directory and PUTs it to
        the recording webhook.
        """
        self.ensure_one()
        sid = self.call_sid or (self.channel and self.channel.sid)
        path = self.channel.asterisk_recording_file if self.channel else None
        self.env['connect.settings'].asterisk_agent_request(
            '/recording_fetch', {'sid': sid, 'path': path})
        self.env['connect.settings'].connect_notify(
            'Recording re-upload requested from the Asterisk agent.',
            notify_uid=self.env.user.id)
        return True

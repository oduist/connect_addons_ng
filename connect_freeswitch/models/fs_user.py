import logging
import re
from xml.etree import ElementTree as ET
from odoo import models

logger = logging.getLogger(__name__)


class User(models.Model):
    _inherit = 'connect.user'

    def generate_dialplan(self, context_el, params, exten=None):
        """Generate FreeSWITCH dialplan to bridge to this user's endpoints."""
        self.ensure_one()
        number = exten.number if exten else self.exten_number or self.username
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''

        ext = ET.SubElement(context_el, 'extension', name='user_{}'.format(number))
        condition = ET.SubElement(ext, 'condition',
            field='destination_number', expression='^{}$'.format(re.escape(number)))

        # Tracking variables
        ET.SubElement(condition, 'action', application='set',
            data='odoo_called_user_id={}'.format(self.id))
        if exten:
            ET.SubElement(condition, 'action', application='set',
                data='odoo_exten_id={}'.format(exten.id))

        # Call recording
        if self.record_calls and base_url:
            recording_url = '{}freeswitch/webhook/recording'.format(
                base_url if base_url.endswith('/') else base_url + '/')
            ET.SubElement(condition, 'action', application='set',
                data='RECORD_STEREO=true')
            ET.SubElement(condition, 'action', application='set',
                data='media_bug_answer_req=true')
            ET.SubElement(condition, 'action', application='set',
                data='execute_on_answer=record_session {}/{}.wav'.format(
                    recording_url, '${uuid}'))

        # Export parent UUID to B-leg for CDR linking
        ET.SubElement(condition, 'action', application='export',
            data='nolocal:odoo_parent_uuid=${uuid}')

        # Bridge settings
        ET.SubElement(condition, 'action', application='set',
            data='call_timeout=30')
        ET.SubElement(condition, 'action', application='set',
            data='hangup_after_bridge=true')
        ET.SubElement(condition, 'action', application='set',
            data='continue_on_fail=true')

        fs_domain = self.env['connect.settings'].sudo().get_param('freeswitch_domain') or '${domain}'

        # Bridge to user (uses dial-string from directory which includes SIP + Verto)
        ET.SubElement(condition, 'action', application='bridge',
            data='user/{}@{}'.format(number, fs_domain))

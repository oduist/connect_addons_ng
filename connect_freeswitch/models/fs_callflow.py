import logging
import re
from xml.etree import ElementTree as ET
from odoo import models

logger = logging.getLogger(__name__)


class CallFlow(models.Model):
    _inherit = 'connect.callflow'

    def generate_dialplan(self, context_el, params, exten=None):
        """Generate FreeSWITCH dialplan XML for this callflow.

        For IVR (gather_input): generates play_and_get_digits with inline
        condition branches for each choice.
        For ring groups (ring_users without gather): generates bridge to all users.
        """
        self.ensure_one()
        number = exten.number if exten else self.exten_number or str(self.id)

        if self.gather_input and self.prompt_message and self.choices:
            self._generate_ivr_dialplan(context_el, number)
        elif self.ring_users:
            self._generate_ring_group_dialplan(context_el, number, exten)
        else:
            # No actions configured
            ext = ET.SubElement(context_el, 'extension', name='callflow_{}'.format(self.id))
            condition = ET.SubElement(ext, 'condition',
                field='destination_number', expression='^{}$'.format(re.escape(number)))
            ET.SubElement(condition, 'action', application='respond', data='404')

    def _generate_ivr_dialplan(self, context_el, number):
        """Generate IVR dialplan with play_and_get_digits + inline choice conditions."""
        ext = ET.SubElement(context_el, 'extension', name='callflow_{}'.format(self.id))

        # First condition: match destination number
        main_condition = ET.SubElement(ext, 'condition',
            field='destination_number',
            expression='^{}$'.format(re.escape(number)))
        main_condition.set('break', 'on-false')

        ET.SubElement(main_condition, 'action', application='answer')
        ET.SubElement(main_condition, 'action', application='sleep', data='500')

        # Build play_and_get_digits parameters
        # Syntax: <min> <max> <tries> <timeout> <terminators> <file> <invalid_file>
        #         <var_name> <regexp> <digit_timeout> [<transfer_on_failure>]
        var_name = 'cf_digit_{}'.format(self.id)
        min_digits = 1
        max_digits = self.gather_digits or 1
        tries = 3
        timeout = (self.gather_timeout or 5) * 1000  # Convert to milliseconds
        prompt = self.prompt_message or ''
        invalid_msg = self.invalid_input_message or ''
        lang = self._get_piper_language()

        prompt_file = "'speak:piper|{}|{}'".format(lang, prompt) if prompt else 'silence_stream://250'
        invalid_file = "'speak:piper|{}|{}'".format(lang, invalid_msg) if invalid_msg else 'silence_stream://250'

        # Collect valid digit patterns from choices
        valid_digits = '|'.join(
            re.escape(c.choice_digits) for c in self.choices if c.choice_digits)
        digit_regexp = '^({})$'.format(valid_digits) if valid_digits else r'\d+'

        pgd_data = "{min} {max} {tries} {timeout} # {prompt} {invalid} {var} {regexp}".format(
            min=min_digits, max=max_digits, tries=tries, timeout=timeout,
            prompt=prompt_file, invalid=invalid_file, var=var_name, regexp=digit_regexp)

        ET.SubElement(main_condition, 'action', application='play_and_get_digits',
            data=pgd_data)

        # Add inline conditions for each choice
        for choice in self.choices:
            if not choice.choice_digits or not choice.exten:
                continue

            choice_condition = ET.SubElement(ext, 'condition',
                field='${{{}}}'.format(var_name),
                expression='^{}$'.format(re.escape(choice.choice_digits)))
            choice_condition.set('break', 'on-true')

            # Generate the choice destination's actions inline
            dst = choice.exten.dst
            if dst:
                if dst._name == 'connect.user':
                    self._add_user_bridge_actions(choice_condition, dst)
                elif dst._name == 'connect.callflow':
                    # Nested callflow: transfer to it
                    nested_number = choice.exten.number
                    ET.SubElement(choice_condition, 'action',
                        application='transfer',
                        data='{} XML default'.format(nested_number))
                else:
                    ET.SubElement(choice_condition, 'action',
                        application='transfer',
                        data='{} XML default'.format(choice.exten.number))

    def _generate_ring_group_dialplan(self, context_el, number, exten=None):
        """Generate ring group dialplan bridging to multiple users."""
        ext = ET.SubElement(context_el, 'extension', name='callflow_ring_{}'.format(self.id))
        condition = ET.SubElement(ext, 'condition',
            field='destination_number', expression='^{}$'.format(re.escape(number)))

        if exten:
            ET.SubElement(condition, 'action', application='set',
                data='odoo_exten_id={}'.format(exten.id))

        # Call recording
        if self.record_calls:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
            if base_url:
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

        ET.SubElement(condition, 'action', application='set', data='call_timeout=30')
        ET.SubElement(condition, 'action', application='set', data='hangup_after_bridge=true')

        # Build bridge string with all users
        bridge_parts = []
        for user in self.ring_users:
            endpoint = self.env['connect.endpoint'].sudo().search([
                ('connect_user_id', '=', user.id),
                ('active', '=', True),
                '|', ('sip_enabled', '=', True), ('webrtc_enabled', '=', True)
            ], limit=1)
            fs_domain = self.env['connect.settings'].sudo().get_param('freeswitch_domain') or '${domain}'
            user_number = user.exten_number or user.username
            bridge_parts.append('user/{}@{}'.format(user_number, fs_domain))

        if bridge_parts:
            ET.SubElement(condition, 'action', application='bridge',
                data=','.join(bridge_parts))

    def _get_piper_language(self):
        """Map callflow language (e.g. 'en-US') to piper short code (e.g. 'en')."""
        lang = self.language or 'en-US'
        return lang.split('-')[0]

    def _add_user_bridge_actions(self, parent_el, user):
        """Add bridge actions for a user directly into a parent XML element."""
        fs_domain = self.env['connect.settings'].sudo().get_param('freeswitch_domain') or '${domain}'
        user_number = user.exten_number or user.username

        ET.SubElement(parent_el, 'action', application='set',
            data='odoo_called_user_id={}'.format(user.id))
        ET.SubElement(parent_el, 'action', application='export',
            data='nolocal:odoo_parent_uuid=${uuid}')
        ET.SubElement(parent_el, 'action', application='set', data='call_timeout=30')
        ET.SubElement(parent_el, 'action', application='set', data='hangup_after_bridge=true')
        ET.SubElement(parent_el, 'action', application='set', data='continue_on_fail=true')
        ET.SubElement(parent_el, 'action', application='bridge',
            data='user/{}@{}'.format(user_number, fs_domain))

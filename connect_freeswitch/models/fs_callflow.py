import logging
import re
from odoo import models

logger = logging.getLogger(__name__)


class CallFlow(models.Model):
    _inherit = 'connect.callflow'

    def generate_dialplan(self, params, exten=None):
        """Generate FreeSWITCH dialplan XML for this callflow.

        For IVR (gather_input): generates play_and_get_digits with inline
        condition branches for each choice.
        For ring groups (ring_users without gather): generates bridge to all users.
        """
        self.ensure_one()
        number = exten.number if exten else self.exten_number or str(self.id)

        if self.gather_input and self.prompt_message and self.choices:
            return self._generate_ivr_dialplan(number)
        elif self.ring_users:
            return self._generate_ring_group_dialplan(number, exten)
        else:
            return ('<extension name="callflow_{id}">'
                    '<condition field="destination_number" expression="^{number}$">'
                    '<action application="respond" data="404"/>'
                    '</condition></extension>').format(
                        id=self.id, number=re.escape(number))

    def _generate_ivr_dialplan(self, number):
        """Generate IVR dialplan with play_and_get_digits + inline choice conditions."""
        var_name = 'cf_digit_{}'.format(self.id)
        min_digits = 1
        max_digits = self.gather_digits or 1
        tries = 3
        timeout = (self.gather_timeout or 5) * 1000
        prompt = self.prompt_message or ''
        invalid_msg = self.invalid_input_message or ''
        lang = self._get_piper_language()

        # Replace spaces with \s in TTS text — play_and_get_digits splits
        # arguments by spaces, so literal spaces in the prompt break parsing.
        # FreeSWITCH speak protocol interprets \s as a space character.
        prompt_escaped = prompt.replace(' ', '\\s')
        invalid_escaped = invalid_msg.replace(' ', '\\s')

        prompt_file = 'speak:piper|{}|{}'.format(lang, prompt_escaped) if prompt else 'silence_stream://250'
        invalid_file = 'speak:piper|{}|{}'.format(lang, invalid_escaped) if invalid_msg else 'silence_stream://250'


        valid_digits = '|'.join(
            re.escape(c.choice_digits) for c in self.choices if c.choice_digits)
        digit_regexp = '^({})$'.format(valid_digits) if valid_digits else r'\d+'

        pgd_data = (
            "{min} {max} {tries} {timeout} # "
            "{prompt} {invalid} "
            "{var} {regexp}"
        ).format(
            min=min_digits, max=max_digits, tries=tries, timeout=timeout,
            prompt=prompt_file, invalid=invalid_file,
            var=var_name, regexp=digit_regexp)

        fs_domain = self.env['connect.settings'].sudo().get_param('freeswitch_domain') or '${domain}'

        choices = []
        for choice in self.choices:
            if not choice.choice_digits or not choice.exten:
                continue
            dst = choice.exten.dst
            if dst and dst._name == 'connect.user':
                user_number = dst.exten_number or dst.username
                choices.append({
                    'digits_escaped': re.escape(choice.choice_digits),
                    'dst_type': 'user',
                    'user_id': dst.id,
                    'user_number': user_number,
                    'transfer_target': '',
                })
            else:
                choices.append({
                    'digits_escaped': re.escape(choice.choice_digits),
                    'dst_type': 'other',
                    'user_id': '',
                    'user_number': '',
                    'transfer_target': choice.exten.number,
                })

        return self.env['connect.freeswitch.template'].render('dialplan_ivr', {
            'callflow_id': self.id,
            'number': re.escape(number),
            'pgd_data': pgd_data,
            'var_name': var_name,
            'choices': choices,
            'fs_domain': fs_domain,
        })

    def _generate_ring_group_dialplan(self, number, exten=None):
        """Generate ring group dialplan bridging to multiple users."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        recording_url = ''
        if self.record_calls and base_url:
            recording_url = '{}freeswitch/webhook/recording'.format(
                base_url if base_url.endswith('/') else base_url + '/')

        fs_domain = self.env['connect.settings'].sudo().get_param('freeswitch_domain') or '${domain}'

        bridge_parts = []
        for user in self.ring_users:
            endpoint = self.env['connect.endpoint'].sudo().search([
                ('connect_user_id', '=', user.id),
                ('active', '=', True),
                '|', ('sip_enabled', '=', True), ('webrtc_enabled', '=', True)
            ], limit=1)
            user_number = user.exten_number or user.username
            bridge_parts.append('user/{}@{}'.format(user_number, fs_domain))

        return self.env['connect.freeswitch.template'].render('dialplan_ring_group', {
            'callflow_id': self.id,
            'number': re.escape(number),
            'exten_id': exten.id if exten else None,
            'record_calls': self.record_calls,
            'recording_url': recording_url,
            'bridge_string': ','.join(bridge_parts),
        })

    def _get_piper_language(self):
        """Map callflow language (e.g. 'en-US') to piper short code (e.g. 'en')."""
        lang = self.language or 'en-US'
        return lang.split('-')[0]

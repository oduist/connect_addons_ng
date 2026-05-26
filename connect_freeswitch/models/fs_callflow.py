import logging
import re
from odoo import fields, models

logger = logging.getLogger(__name__)


class CallFlow(models.Model):
    _inherit = 'connect.callflow'

    fs_fifo_id = fields.Many2one(
        'connect.fs_fifo', string='FS Queue', ondelete='set null',
        help='Fallback queue. Used after ring_users do not answer; '
             'also used as default destination when IVR gets no choice.',
    )

    def generate_dialplan(self, params, exten=None):
        """Generate FreeSWITCH dialplan XML for this callflow.

        For IVR (gather_input): generates bind_digit_action bindings plus speak (TTS)
        so a DTMF press during the prompt instantly triggers the matching action.
        For ring groups (ring_users without gather): generates bridge to all users.
        """
        self.ensure_one()
        number = exten.number if exten else self.exten_number or str(self.id)

        if self.gather_input and self.prompt_message and self.choices:
            return self._generate_ivr_dialplan(number)
        elif self.ring_users:
            return self._generate_ring_group_dialplan(number, exten)
        elif self.fs_fifo_id:
            return self._generate_fifo_fallback_dialplan(number)
        else:
            return ('<extension name="callflow_{id}">'
                    '<condition field="destination_number" expression="^{number}$">'
                    '<action application="respond" data="404"/>'
                    '</condition></extension>').format(
                        id=self.id, number=re.escape(number))

    def _ivr_choice_data(self):
        """Build the list of {digits, dst_type, ...} dicts used by IVR templates."""
        choices = []
        for choice in self.choices:
            if not choice.choice_digits or not choice.exten:
                continue
            dst = choice.exten.dst
            if dst and dst._name == 'connect.user':
                choices.append({
                    'digits': choice.choice_digits,
                    'dst_type': 'user',
                    'user_id': dst.id,
                    'user_number': dst.exten_number or '',
                    'transfer_target': '',
                })
            else:
                choices.append({
                    'digits': choice.choice_digits,
                    'dst_type': 'other',
                    'user_id': '',
                    'user_number': '',
                    'transfer_target': choice.exten.number,
                })
        return choices

    def _generate_ivr_dialplan(self, number):
        """Generate IVR dialplan that uses bind_digit_action so DTMF interrupts speak."""
        timeout = (self.gather_timeout or 5) * 1000
        prompt = self.prompt_message or ''
        lang = self._get_piper_language()

        fs_domain = self.env['connect.settings'].sudo().get_param('freeswitch_domain') or '${domain}'

        fifo_number = ''
        if self.fs_fifo_id and self.fs_fifo_id.exten_number:
            fifo_number = self.fs_fifo_id.exten_number

        ring_parts = []
        for user in self.ring_users:
            if user.exten_number:
                ring_parts.append('user/{}@{}'.format(user.exten_number, fs_domain))
        ring_bridge = ','.join(ring_parts)

        return self.env['connect.freeswitch.template'].render('dialplan_ivr', {
            'callflow_id': self.id,
            'number': re.escape(number),
            'lang': lang,
            'prompt': prompt,
            'timeout': timeout,
            'choices': self._ivr_choice_data(),
            'fs_domain': fs_domain,
            'ring_bridge': ring_bridge,
            'fifo_number': fifo_number,
        })

    def _generate_ivr_choice_dialplan(self, digits):
        """Generate dialplan for an IVR user-choice landing extension.

        Called by the controller when FreeSWITCH routes destination=cf_call_<id>_<digits>
        after a bind_digit_action fired. Returns an extension that sets the per-call
        variables (so the Odoo event handler knows which user was rung) and bridges.
        """
        self.ensure_one()
        for choice in self._ivr_choice_data():
            if choice['digits'] == digits and choice['dst_type'] == 'user':
                fs_domain = self.env['connect.settings'].sudo().get_param(
                    'freeswitch_domain') or '${domain}'
                return self.env['connect.freeswitch.template'].render(
                    'dialplan_ivr_choice', {
                        'callflow_id': self.id,
                        'digits': digits,
                        'digits_escaped': re.escape(digits),
                        'user_id': choice['user_id'],
                        'user_number': choice['user_number'],
                        'fs_domain': fs_domain,
                    })
        return ''

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
            user_number = user.exten_number
            if not user_number:
                continue
            bridge_parts.append('user/{}@{}'.format(user_number, fs_domain))

        fifo_number = ''
        if self.fs_fifo_id and self.fs_fifo_id.exten_number:
            fifo_number = self.fs_fifo_id.exten_number

        voicemail_user_number = ''
        if self.voicemail_enabled:
            first_user = self.ring_users[:1]
            if first_user and first_user.exten_number:
                voicemail_user_number = first_user.exten_number

        return self.env['connect.freeswitch.template'].render('dialplan_ring_group', {
            'callflow_id': self.id,
            'number': re.escape(number),
            'exten_id': exten.id if exten else None,
            'record_calls': self.record_calls,
            'recording_url': recording_url,
            'bridge_string': ','.join(bridge_parts),
            'fifo_number': fifo_number,
            'voicemail_enabled': bool(self.voicemail_enabled),
            'voicemail_user_number': voicemail_user_number,
        })

    def _generate_fifo_fallback_dialplan(self, number):
        """Callflow with only fs_fifo_id: act as a thin transfer-to-queue wrapper."""
        fifo_number = self.fs_fifo_id.exten_number or str(self.fs_fifo_id.id)
        return (
            '<extension name="callflow_fifo_{id}">'
            '<condition field="destination_number" expression="^{number}$">'
            '<action application="transfer" data="{fifo} XML default"/>'
            '</condition></extension>'
        ).format(id=self.id, number=re.escape(number), fifo=fifo_number)

    def _get_piper_language(self):
        """Map callflow language (e.g. 'en-US') to piper short code (e.g. 'en')."""
        lang = self.language or 'en-US'
        return lang.split('-')[0]

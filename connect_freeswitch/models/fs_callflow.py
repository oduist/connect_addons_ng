import logging
import re
from odoo import fields, models, api

logger = logging.getLogger(__name__)


class CallFlow(models.Model):
    _name = 'connect.freeswitch.callflow'
    _description = 'FreeSWITCH Call Flow'
    _order = 'name asc'

    name = fields.Char(required=True)
    exten = fields.Many2one('connect.freeswitch.exten', ondelete='set null', readonly=True)
    exten_number = fields.Char(related='exten.number', store=True)
    language = fields.Selection(
        selection=lambda self: self._get_language_selection(),
        default='en-US',
        required=True,
        string='Language',
    )
    gather_input = fields.Boolean()
    # FreeSWITCH IVR is DTMF-only (bind_digit_action).
    gather_input_type = fields.Selection(string='Input Type',
        selection=[('dtmf', 'DTMF')],
        required=True, default='dtmf')
    gather_timeout = fields.Integer(string='Timeout', default=5)
    gather_hints = fields.Char('Hints', default='This is a phrase I expect to hear, department name or extension number')
    prompt_message = fields.Text('Prompt Message',
        default='Welcome to our company! Please enter the extension number of person '
                'you wish to dial or wait 5 seconds till I start connecting your call')
    invalid_input_message = fields.Text(default='We received wrong input. Please try again!')
    gather_digits = fields.Integer(required=True, default=1)
    choices = fields.One2many('connect.freeswitch.callflow_choice', 'callflow')
    ring_users = fields.Many2many('connect.user')
    record_calls = fields.Boolean()
    voicemail_prompt = fields.Text(
        help='Message played before recording callflow voicemail. '
             'Callflow voicemail takes precedence over user voicemail inside '
             'callflows; direct user routing keeps user voicemail behavior.')
    voicemail_enabled = fields.Boolean(
        help='Enable callflow voicemail after no callflow action handles the '
             'caller. Requires a voicemail prompt. FS Queue voicemail is '
             'configured separately on the queue timeout settings.')
    fs_fifo_id = fields.Many2one(
        'connect.fs_fifo', string='FS Queue', ondelete='set null',
        help='Fallback queue. Used after ring_users do not answer; '
             'also used as default destination when IVR gets no choice.',
    )

    def create_extension(self):
        self.ensure_one()
        return self.env['connect.freeswitch.exten'].create_extension(self, self._name)

    @api.model
    def _get_language_selection(self):
        """Languages supported by Piper TTS (medium models).

        Codes are BCP-47; ``mod_piper_tts`` looks them up against the
        ``<model language="...">`` entries in ``piper_tts.conf.xml``.
        Duplicated in connect_twilio, connect_telnyx and core connect.user
        by design — the providers are fully independent; keep all four
        lists in sync when editing (ADR-031/ADR-037).
        """
        return [
            ('ca-ES', 'Catalan (Spain)'),
            ('cs-CZ', 'Czech'),
            ('da-DK', 'Danish'),
            ('de-DE', 'German'),
            ('en-GB', 'English (UK)'),
            ('en-US', 'English (US)'),
            ('es-ES', 'Spanish (Spain)'),
            ('es-MX', 'Spanish (Mexico)'),
            ('fi-FI', 'Finnish'),
            ('fr-FR', 'French'),
            ('hu-HU', 'Hungarian'),
            ('is-IS', 'Icelandic'),
            ('it-IT', 'Italian'),
            ('nl-BE', 'Dutch (Belgium)'),
            ('nl-NL', 'Dutch (Netherlands)'),
            ('pl-PL', 'Polish'),
            ('pt-BR', 'Portuguese (Brazil)'),
            ('pt-PT', 'Portuguese (Portugal)'),
            ('ro-RO', 'Romanian'),
            ('ru-RU', 'Russian'),
            ('sk-SK', 'Slovak'),
            ('sv-SE', 'Swedish'),
            ('tr-TR', 'Turkish'),
            ('uk-UA', 'Ukrainian'),
            ('vi-VN', 'Vietnamese'),
            ('zh-CN', 'Chinese (Mandarin)'),
        ]

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
        elif self._get_voicemail_context()['voicemail_enabled']:
            return self._generate_voicemail_dialplan(number, exten)
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
                    'user_number': dst.freeswitch_exten_number or '',
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

        voicemail_context = self._get_voicemail_context()

        ring_parts = []
        for user in self.ring_users:
            if user.freeswitch_exten_number:
                ring_parts.append('user/{}@{}'.format(user.freeswitch_exten_number, fs_domain))
        ring_bridge = ','.join(ring_parts)

        choices = self._ivr_choice_data()

        # gather_digits drives both the bind_digit_digit_timeout (inter-digit
        # wait inside FreeSWITCH dmachine) and the invalid-input regex length.
        # For single-digit IVRs we shrink the timeout to ~100ms so a press
        # fires almost instantly instead of the 1500ms dmachine default.
        gather_digits = max(int(self.gather_digits or 1), 1)
        dmachine_timeout = 100 if gather_digits == 1 else 1500

        invalid_msg = (self.invalid_input_message or '').strip()
        invalid_regex = ''
        if invalid_msg:
            used_chars = set()
            for choice in choices:
                used_chars.update(choice['digits'])
            allowed = [c for c in '0123456789*#' if c not in used_chars]
            if allowed:
                quant = '' if gather_digits == 1 else '{{1,{}}}'.format(gather_digits)
                # FreeSWITCH digit parser treats `~` as a regex pattern.
                # Match digits that are NOT among the bound choices, so exact
                # bindings (1, 2, ...) win for valid input.
                invalid_regex = '~^[{}]{}$'.format(''.join(allowed), quant)

        return self.env['connect.freeswitch.template'].render('dialplan_ivr', {
            'callflow_id': self.id,
            'number': re.escape(number),
            'lang': lang,
            'prompt': prompt,
            'timeout': timeout,
            'choices': choices,
            'fs_domain': fs_domain,
            'ring_bridge': ring_bridge,
            'fifo_number': fifo_number,
            'voicemail_enabled': voicemail_context['voicemail_enabled'],
            'voicemail_prompt': voicemail_context['voicemail_prompt'],
            'voicemail_url': voicemail_context['voicemail_url'],
            'invalid_regex': invalid_regex,
            'dmachine_timeout': dmachine_timeout,
        })

    def _generate_ivr_invalid_dialplan(self):
        """Generate the IVR catch-all extension that speaks invalid_input_message
        and routes back into the IVR. Returns empty XML if no message is set."""
        self.ensure_one()
        msg = (self.invalid_input_message or '').strip()
        if not msg:
            return ''
        number = self.exten_number or str(self.id)
        return self.env['connect.freeswitch.template'].render(
            'dialplan_ivr_invalid', {
                'callflow_id': self.id,
                'number': number,
                'lang': self._get_piper_language(),
                'invalid_msg': msg,
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
        recording_url = ''
        if self.record_calls:
            recording_url = self.env['connect.settings'].get_recording_webhook_url()

        fs_domain = self.env['connect.settings'].sudo().get_param('freeswitch_domain') or '${domain}'

        bridge_parts = []
        for user in self.ring_users:
            user_number = user.freeswitch_exten_number
            if not user_number:
                continue
            bridge_parts.append('user/{}@{}'.format(user_number, fs_domain))

        fifo_number = ''
        if self.fs_fifo_id and self.fs_fifo_id.exten_number:
            fifo_number = self.fs_fifo_id.exten_number

        voicemail_context = self._get_voicemail_context()

        return self.env['connect.freeswitch.template'].render('dialplan_ring_group', {
            'callflow_id': self.id,
            'number': re.escape(number),
            'exten_id': exten.id if exten else None,
            'record_calls': self.record_calls,
            'recording_url': recording_url,
            'bridge_string': ','.join(bridge_parts),
            'fifo_number': fifo_number,
            'voicemail_enabled': voicemail_context['voicemail_enabled'],
            'voicemail_prompt': voicemail_context['voicemail_prompt'],
            'voicemail_url': voicemail_context['voicemail_url'],
            'lang': voicemail_context['lang'],
        })

    def _get_voicemail_context(self):
        prompt = (self.voicemail_prompt or '').strip()
        voicemail_url = ''
        if self.voicemail_enabled and prompt:
            voicemail_url = self.env['connect.settings'].get_voicemail_webhook_url()
        return {
            'voicemail_enabled': bool(self.voicemail_enabled and prompt and voicemail_url),
            'voicemail_prompt': prompt,
            'voicemail_url': voicemail_url,
            'lang': self._get_piper_language(),
        }

    def _generate_voicemail_dialplan(self, number, exten=None):
        voicemail_context = self._get_voicemail_context()
        return self.env['connect.freeswitch.template'].render(
            'dialplan_callflow_voicemail', {
                'callflow_id': self.id,
                'number': re.escape(number),
                'exten_id': exten.id if exten else None,
                'voicemail_prompt': voicemail_context['voicemail_prompt'],
                'voicemail_url': voicemail_context['voicemail_url'],
                'lang': voicemail_context['lang'],
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
        """Return the BCP-47 language code used as the Piper TTS model key.

        The full BCP-47 tag (e.g. ``en-US``, ``pt-BR``) is matched against
        ``<model language="..."/>`` entries in ``piper_tts.conf.xml`` so that
        regional variants such as ``pt-BR`` and ``pt-PT`` resolve to distinct
        voices.
        """
        return self.language or 'en-US'


class CallflowChoice(models.Model):
    _name = 'connect.freeswitch.callflow_choice'
    _description = 'FreeSWITCH Callflow Choice'

    callflow = fields.Many2one('connect.freeswitch.callflow', required=True, ondelete='cascade')
    choice_digits = fields.Char(required=True)
    exten = fields.Many2one('connect.freeswitch.exten', ondelete='restrict', required=True)

import logging
from odoo import fields, models, api

logger = logging.getLogger(__name__)


class CallFlow(models.Model):
    _name = 'connect.callflow'
    _description = 'Call Flow'
    _order = 'name asc'

    name = fields.Char(required=True)
    provider_id = fields.Many2one(
        'connect.provider', ondelete='set null', index=True, copy=False,
        help='Telephony provider that renders this callflow.',
    )
    exten = fields.Many2one('connect.exten', ondelete='set null', readonly=True)
    exten_number = fields.Char(related='exten.number', store=True)
    language = fields.Selection(
        selection=lambda self: self._get_language_selection(),
        default='en-US',
        required=True,
        string='Language',
    )
    voice = fields.Char(required=True, default='Woman')
    gather_input = fields.Boolean()
    # Core only ships DTMF. Speech-aware backends (e.g. connect_twilio) extend
    # this selection via selection_add. FreeSWITCH stays DTMF-only.
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
    choices = fields.One2many('connect.callflow_choice', 'callflow')
    ring_users = fields.Many2many('connect.user')
    record_calls = fields.Boolean()
    voicemail_prompt = fields.Text()
    voicemail_enabled = fields.Boolean()

    def create_extension(self):
        self.ensure_one()
        return self.env['connect.exten'].create_extension(self, 'callflow')

    @api.model
    def _get_language_selection(self):
        """Languages supported by both Twilio Say (Polly) and Piper TTS (medium).

        Codes are BCP-47 and are passed verbatim to Twilio Say; on the
        FreeSWITCH side ``mod_piper_tts`` looks them up against the
        ``<model language="...">`` entries in ``piper_tts.conf.xml``.
        Override in an extension module to narrow or extend the list.
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
